# -*- coding: utf-8 -*-
"""
简化版混合上传器 - 学习ytdlbot简洁风格
优先使用Pyrofork，Bot API作为回退
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .pyrofork_uploader import PyroForkUploader
from .bot_api import BotAPIUploader
from ..base import BaseUploader

logger = logging.getLogger(__name__)


class ModernHybridUploader(BaseUploader):
    """简化版混合上传器 - 学习ytdlbot风格"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.config = config

        # 从配置中获取关键属性，提供合理的默认值
        self.auto_fallback = config.get('auto_fallback', True)  # 默认启用自动回退
        self.prefer_pyrofork = config.get('prefer_pyrofork', False)  # 默认优先使用 Bot API（更稳定）
        self.pyrofork_timeout = config.get('pyrofork_timeout', 30)  # Pyrofork 连接超时时间

        # 网络错误统计 - 用于智能调整策略
        self._network_error_count = {'bot_api': 0, 'pyrofork': 0}
        self._last_error_time = {'bot_api': 0, 'pyrofork': 0}

        # 简化：只初始化需要的上传器
        self.pyrofork_uploader = None
        self.bot_api_uploader = None

        logger.info("🔧 初始化简化版混合上传器")
        logger.debug(f"🔧 配置: auto_fallback={self.auto_fallback}, prefer_pyrofork={self.prefer_pyrofork}")
        self._initialize_uploaders()

    def _record_error(self, uploader_type: str, error_msg: str):
        """记录上传器错误，用于智能策略调整"""
        import time
        current_time = time.time()

        if uploader_type in self._network_error_count:
            self._network_error_count[uploader_type] += 1
            self._last_error_time[uploader_type] = current_time

            # 如果某个上传器连续失败次数过多，记录警告
            if self._network_error_count[uploader_type] >= 3:
                logger.warning(f"⚠️ {uploader_type} 连续失败 {self._network_error_count[uploader_type]} 次")

                # 重置计数器，避免无限累积
                if self._network_error_count[uploader_type] >= 10:
                    logger.info(f"🔄 重置 {uploader_type} 错误计数器")
                    self._network_error_count[uploader_type] = 3

    def _should_skip_uploader(self, uploader_type: str) -> bool:
        """判断是否应该跳过某个上传器（基于错误历史）"""
        import time
        current_time = time.time()

        if uploader_type not in self._network_error_count:
            return False

        error_count = self._network_error_count[uploader_type]
        last_error_time = self._last_error_time[uploader_type]

        # 如果最近5分钟内连续失败超过5次，暂时跳过
        if error_count >= 5 and (current_time - last_error_time) < 300:
            logger.debug(f"🚫 暂时跳过 {uploader_type}（连续失败 {error_count} 次）")
            return True

        return False

    def _initialize_uploaders(self):
        """初始化所有上传器"""
        try:
            # 初始化 Bot API 上传器
            if self.config.get('bot_token'):
                self.bot_api_uploader = BotAPIUploader(self.config)
                if self.bot_api_uploader.is_available():
                    logger.info("✅ Bot API 上传器初始化成功")
                else:
                    logger.warning("⚠️ Bot API 上传器不可用")
                    self.bot_api_uploader = None
            
            # 初始化 Pyrofork 上传器
            if all([self.config.get('api_id'), self.config.get('api_hash'), self.config.get('bot_token')]):
                self.pyrofork_uploader = PyroForkUploader(self.config)
                if self.pyrofork_uploader.is_available():
                    logger.info("✅ Pyrofork 上传器初始化成功")
                else:
                    logger.warning("⚠️ Pyrofork 上传器不可用")
                    self.pyrofork_uploader = None
            else:
                logger.info("ℹ️ 缺少 Pyrofork 配置，仅使用 Bot API")
            
        except Exception as e:
            logger.error(f"❌ 混合上传器初始化失败: {e}")

    def is_available(self) -> bool:
        """检查是否有可用的上传器"""
        return bool(self.bot_api_uploader or self.pyrofork_uploader)

    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """发送文本消息 - 优雅的回退机制"""
        if not message:
            logger.warning("⚠️ 消息内容为空，跳过发送")
            return False

        # 智能选择上传器优先级 - 考虑网络稳定性和错误历史
        primary_uploader = None
        fallback_uploader = None
        primary_type = None
        fallback_type = None

        # 检查各上传器的可用性和错误历史
        bot_api_available = (self.bot_api_uploader and
                           self.bot_api_uploader.is_available() and
                           not self._should_skip_uploader('bot_api'))

        pyrofork_available = (self.pyrofork_uploader and
                            self.pyrofork_uploader.is_available() and
                            not self._should_skip_uploader('pyrofork'))

        # 智能选择策略
        if self.prefer_pyrofork and pyrofork_available:
            primary_uploader = self.pyrofork_uploader
            primary_type = 'pyrofork'
            fallback_uploader = self.bot_api_uploader if bot_api_available else None
            fallback_type = 'bot_api' if bot_api_available else None
            logger.debug("📤 优先使用 Pyrofork（用户配置）")
        elif bot_api_available:
            primary_uploader = self.bot_api_uploader
            primary_type = 'bot_api'
            fallback_uploader = self.pyrofork_uploader if pyrofork_available else None
            fallback_type = 'pyrofork' if pyrofork_available else None
            logger.debug("📤 优先使用 Bot API（默认/稳定性）")
        elif pyrofork_available:
            primary_uploader = self.pyrofork_uploader
            primary_type = 'pyrofork'
            fallback_uploader = None
            fallback_type = None
            logger.debug("📤 仅使用 Pyrofork（Bot API 不可用）")
        else:
            logger.error("❌ 没有可用的消息发送器（可能因为连续错误被暂时禁用）")
            return False

        # 尝试主要上传器 - 添加超时控制
        primary_success = False
        primary_error = None

        try:
            logger.debug(f"📤 使用主要上传器发送消息: {type(primary_uploader).__name__}")

            # 对于 Pyrofork，添加额外的超时保护
            if hasattr(primary_uploader, '_run_async'):
                # 这是 Pyrofork 上传器，可能会有长时间连接问题
                import asyncio
                try:
                    # 使用较短的超时时间，避免长时间等待
                    result = primary_uploader.send_message(message, parse_mode)
                    if result is True:
                        primary_success = True
                        return True
                    elif result is False:
                        logger.warning(f"⚠️ {type(primary_uploader).__name__} 消息发送明确失败")
                        primary_error = "明确失败"
                        self._record_error(primary_type, primary_error)
                    else:
                        logger.warning(f"⚠️ {type(primary_uploader).__name__} 消息发送异常返回: {result}")
                        primary_error = f"异常返回: {result}"
                        self._record_error(primary_type, primary_error)
                except Exception as pyro_error:
                    logger.warning(f"⚠️ {type(primary_uploader).__name__} 发送异常: {pyro_error}")
                    primary_error = str(pyro_error)
                    self._record_error(primary_type, primary_error)
            else:
                # Bot API 上传器，通常更快更稳定
                result = primary_uploader.send_message(message, parse_mode)
                if result is True:
                    primary_success = True
                    return True
                elif result is False:
                    logger.warning(f"⚠️ {type(primary_uploader).__name__} 消息发送明确失败")
                    primary_error = "明确失败"
                    self._record_error(primary_type, primary_error)
                else:
                    logger.warning(f"⚠️ {type(primary_uploader).__name__} 消息发送异常返回: {result}")
                    primary_error = f"异常返回: {result}"
                    self._record_error(primary_type, primary_error)

        except Exception as e:
            logger.error(f"❌ {type(primary_uploader).__name__} 消息发送异常: {e}")
            primary_error = str(e)
            self._record_error(primary_type, primary_error)

        # 智能回退逻辑
        if not primary_success and self.auto_fallback and fallback_uploader:
            try:
                logger.info(f"🔄 主要上传器失败（{primary_error}），尝试回退到 {type(fallback_uploader).__name__}")

                # 检查回退上传器的可用性
                if not fallback_uploader.is_available():
                    logger.warning(f"⚠️ 回退上传器 {type(fallback_uploader).__name__} 不可用")
                    logger.error("❌ 所有消息发送方式都不可用")
                    return False

                result = fallback_uploader.send_message(message, parse_mode)
                if result is True:
                    logger.info("✅ 回退发送成功")
                    return True
                else:
                    logger.error(f"❌ 回退发送也失败: {result}")
                    self._record_error(fallback_type, f"回退失败: {result}")

            except Exception as e:
                logger.error(f"❌ 回退发送异常: {e}")
                self._record_error(fallback_type, f"回退异常: {e}")
                import traceback
                logger.debug(f"🔍 回退异常详情: {traceback.format_exc()}")

        # 所有方式都失败
        if primary_success:
            return True
        else:
            logger.error(f"❌ 所有消息发送方式都失败。主要错误: {primary_error}")
            return False

    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """发送文件 - 简化版本，学习ytdlbot"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path}")
                return False

            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            logger.info(f"📤 发送文件: {file_path_obj.name} ({file_size_mb:.1f}MB)")

            # 简化策略：大文件用Pyrofork，小文件优先Bot API（使用配置的限制）
            file_size_limit = self.config.get('file_size_limit', 50)
            if file_size_mb > file_size_limit and self.pyrofork_uploader:
                # 大文件直接用Pyrofork
                logger.info(f"🎯 大文件({file_size_mb:.1f}MB > {file_size_limit}MB)，使用 Pyrofork")
                return self.pyrofork_uploader.send_file(file_path, caption, **kwargs)

            # 小文件优先Bot API，失败则回退Pyrofork
            if self.bot_api_uploader:
                try:
                    result = self.bot_api_uploader.send_file(file_path, caption, **kwargs)
                    if result:
                        return True
                except Exception as e:
                    logger.debug(f"Bot API 发送失败: {e}")

            # 回退到Pyrofork
            if self.pyrofork_uploader:
                logger.warning("⚠️ Bot API 文件发送失败，尝试 Pyrofork 回退")
                return self.pyrofork_uploader.send_file(file_path, caption, **kwargs)

            logger.error("❌ 没有可用的文件上传器")
            return False

        except Exception as e:
            logger.error(f"❌ 文件发送失败: {e}")
            return False

    def send_media_group(self, files: List[str], caption: str = None) -> bool:
        """发送媒体组"""
        if not files:
            return False
        
        try:
            # 检查文件总大小
            total_size_mb = sum(Path(f).stat().st_size for f in files if Path(f).exists()) / (1024 * 1024)
            
            # 选择上传器（基于文件大小优先选择，使用配置的限制）
            file_size_limit = self.config.get('file_size_limit', 50)
            if total_size_mb > file_size_limit:
                # 大文件必须使用 Pyrofork
                if self.pyrofork_uploader:
                    uploader = self.pyrofork_uploader
                    uploader_name = "Pyrofork"
                    logger.info(f"🎯 媒体组大文件({total_size_mb:.1f}MB > {file_size_limit}MB) → 选择 Pyrofork")
                else:
                    logger.error(f"❌ 媒体组文件过大({total_size_mb:.1f}MB > {file_size_limit}MB)但 Pyrofork 不可用")
                    return False
            else:
                # 小文件优先使用 Bot API
                if self.bot_api_uploader:
                    uploader = self.bot_api_uploader
                    uploader_name = "Bot API"
                    logger.info(f"🎯 媒体组小文件({total_size_mb:.1f}MB ≤ {file_size_limit}MB) → 选择 Bot API（更快）")
                elif self.pyrofork_uploader:
                    uploader = self.pyrofork_uploader
                    uploader_name = "Pyrofork"
                    logger.info(f"🎯 媒体组小文件({total_size_mb:.1f}MB ≤ {file_size_limit}MB) → Bot API不可用，使用 Pyrofork")
                else:
                    logger.error("❌ 没有可用的上传器发送媒体组")
                    return False
            
            logger.info(f"📤 使用 {uploader_name} 发送媒体组 ({len(files)} 个文件, {total_size_mb:.1f}MB)")
            
            success = uploader.send_media_group(files, caption)
            
            if success:
                logger.info(f"✅ 媒体组发送成功")
            else:
                logger.error(f"❌ 媒体组发送失败")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 媒体组发送异常: {e}")
            return False

    # 简化版本：移除复杂的选择器逻辑，直接在send_file中处理

    # 简化版本：移除复杂的错误处理方法

    def _detect_file_type(self, file_path: str) -> str:
        """检测文件类型"""
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv']:
            return 'video'
        elif ext in ['.mp3', '.wav', '.flac', '.m4a', '.ogg']:
            return 'audio'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            return 'photo'
        else:
            return 'document'

    def _get_uploader_name(self, uploader: BaseUploader) -> str:
        """获取上传器名称"""
        if uploader == self.bot_api_uploader:
            return "Bot API"
        elif uploader == self.pyrofork_uploader:
            return "Pyrofork"
        else:
            return "Unknown"

    def get_uploader_status(self) -> Dict[str, Any]:
        """获取上传器状态 - 为前端提供正确的字段名"""
        # 检查各个上传器的真实可用性
        bot_api_available = bool(self.bot_api_uploader and self.bot_api_uploader.is_available())
        pyrofork_available = bool(self.pyrofork_uploader and self.pyrofork_uploader.is_available())

        status = {
            # 前端期望的字段名
            'bot_api_available': bot_api_available,
            'pyrofork_available': pyrofork_available,
            # 配置信息
            'auto_fallback': self.auto_fallback,
            'prefer_pyrofork': self.prefer_pyrofork,
            # 总体状态
            'has_available_uploader': bot_api_available or pyrofork_available
        }

        # 记录状态用于调试
        logger.debug(f"📊 上传器状态: Bot API={bot_api_available}, Pyrofork={pyrofork_available}")

        return status

    def _update_progress_display(self, text: str, file_id: str = None):
        """更新进度显示（实现抽象方法）"""
        try:
            # 混合上传器通过子上传器处理进度显示
            logger.debug(f"📊 混合上传器进度: {text}")
        except Exception as e:
            logger.debug(f"进度显示更新失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            if self.bot_api_uploader:
                self.bot_api_uploader.cleanup()

            if self.pyrofork_uploader:
                self.pyrofork_uploader.cleanup()

            super().cleanup()

        except Exception as e:
            logger.error(f"❌ 混合上传器清理失败: {e}")
