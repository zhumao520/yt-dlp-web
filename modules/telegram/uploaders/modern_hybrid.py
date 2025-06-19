# -*- coding: utf-8 -*-
"""
现代化混合上传器
智能选择最佳上传方式，优化用户体验
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .bot_api import BotAPIUploader
from .pyrofork_uploader import PyroForkUploader
from ..base import BaseUploader

logger = logging.getLogger(__name__)


class ModernHybridUploader(BaseUploader):
    """现代化混合上传器 - 智能选择最佳上传策略"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.config = config
        
        # 初始化上传器
        self.bot_api_uploader = None
        self.pyrofork_uploader = None
        
        # 配置参数
        self.auto_fallback = config.get('auto_fallback', True)
        self.prefer_pyrofork = config.get('prefer_pyrofork', False)
        
        self._initialize_uploaders()

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
        """发送文本消息"""
        # 优先使用 Bot API（更快）
        if self.bot_api_uploader:
            return self.bot_api_uploader.send_message(message, parse_mode)
        elif self.pyrofork_uploader:
            return self.pyrofork_uploader.send_message(message, parse_mode)
        else:
            logger.error("❌ 没有可用的上传器发送消息")
            return False

    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """智能发送文件"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path}")
                return False
            
            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            file_type = self._detect_file_type(file_path)
            
            logger.info(f"📤 智能发送 {file_type} 文件: {file_path_obj.name} ({file_size_mb:.1f}MB)")
            
            # 选择最佳上传器
            uploader = self._select_best_uploader(file_size_mb, file_type)
            if not uploader:
                return self._handle_no_uploader_available(file_path_obj, file_size_mb)
            
            uploader_name = self._get_uploader_name(uploader)
            logger.info(f"🎯 选择使用 {uploader_name} 上传器")
            
            # 尝试上传
            success = uploader.send_file(file_path, caption, **kwargs)
            
            # 自动回退机制
            if not success and self.auto_fallback:
                fallback_uploader = self._get_fallback_uploader(uploader, file_size_mb)
                if fallback_uploader:
                    fallback_name = self._get_uploader_name(fallback_uploader)
                    logger.warning(f"⚠️ {uploader_name} 失败，尝试 {fallback_name} 回退")
                    success = fallback_uploader.send_file(file_path, caption, **kwargs)
            
            # 处理最终结果
            if success:
                logger.info(f"✅ 文件发送成功: {file_path_obj.name}")
            else:
                self._handle_upload_failure(file_path_obj, file_size_mb)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 智能文件发送失败: {e}")
            return False

    def send_media_group(self, files: List[str], caption: str = None) -> bool:
        """发送媒体组"""
        if not files:
            return False
        
        try:
            # 检查文件总大小
            total_size_mb = sum(Path(f).stat().st_size for f in files if Path(f).exists()) / (1024 * 1024)
            
            # 选择上传器（媒体组优先使用 Pyrofork）
            if self.pyrofork_uploader and (total_size_mb > 50 or self.prefer_pyrofork):
                uploader = self.pyrofork_uploader
                uploader_name = "Pyrofork"
            elif self.bot_api_uploader and total_size_mb <= 50:
                uploader = self.bot_api_uploader
                uploader_name = "Bot API"
            else:
                logger.error("❌ 没有合适的上传器发送媒体组")
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

    def _select_best_uploader(self, file_size_mb: float, file_type: str) -> Optional[BaseUploader]:
        """选择最佳上传器"""
        # 策略1: 用户偏好
        if self.prefer_pyrofork and self.pyrofork_uploader:
            return self.pyrofork_uploader
        
        # 策略2: 大文件必须使用 Pyrofork
        if file_size_mb > 50:
            if self.pyrofork_uploader:
                return self.pyrofork_uploader
            else:
                logger.warning(f"⚠️ 大文件({file_size_mb:.1f}MB)但 Pyrofork 不可用")
                return self.bot_api_uploader  # 尝试 Bot API，可能会失败但会给出明确提示
        
        # 策略3: 小文件优先使用 Bot API（更快）
        if file_size_mb <= 50 and self.bot_api_uploader:
            return self.bot_api_uploader
        
        # 策略4: 回退到可用的上传器
        return self.pyrofork_uploader or self.bot_api_uploader

    def _get_fallback_uploader(self, current_uploader: BaseUploader, file_size_mb: float) -> Optional[BaseUploader]:
        """获取回退上传器"""
        if current_uploader == self.bot_api_uploader:
            # Bot API 失败，尝试 Pyrofork
            return self.pyrofork_uploader
        elif current_uploader == self.pyrofork_uploader:
            # Pyrofork 失败，如果是小文件可以尝试 Bot API
            if file_size_mb <= 50:
                return self.bot_api_uploader
        
        return None

    def _handle_no_uploader_available(self, file_path: Path, file_size_mb: float) -> bool:
        """处理没有可用上传器的情况"""
        error_msg = f"""❌ **无法发送文件**

📄 **文件**: {file_path.name[:50]}...
💾 **大小**: {file_size_mb:.1f} MB

⚠️ **原因**: 没有可用的上传器

💡 **解决方案**:
1. **检查配置**: 确认 Bot Token 已正确配置
2. **大文件支持**: 配置 API ID 和 API Hash 以支持大文件
3. **网络连接**: 检查网络连接是否正常

📖 **获取 API 凭据**: https://my.telegram.org"""
        
        # 尝试发送错误消息
        if self.bot_api_uploader:
            self.bot_api_uploader.send_message(error_msg)
        
        logger.error(f"❌ 没有可用的上传器: {file_path.name}")
        return False

    def _handle_upload_failure(self, file_path: Path, file_size_mb: float):
        """处理上传失败"""
        if file_size_mb > 50:
            error_msg = f"""📁 **大文件发送失败**

📄 **文件**: {file_path.name[:50]}...
💾 **大小**: {file_size_mb:.1f} MB

⚠️ **可能原因**:
• 文件超过 50MB，需要 Pyrofork 支持
• 网络连接不稳定
• API 配置问题

💡 **解决方案**:
1. **配置 Pyrofork**: 添加 API ID 和 API Hash
2. **检查网络**: 确保网络连接稳定
3. **重试上传**: 稍后再次尝试

📖 **获取 API 凭据**: https://my.telegram.org"""
        else:
            error_msg = f"""📁 **文件发送失败**

📄 **文件**: {file_path.name[:50]}...
💾 **大小**: {file_size_mb:.1f} MB

⚠️ **可能原因**:
• 网络连接问题
• 文件格式不支持
• 临时服务器问题

💡 **建议**: 请稍后重试"""
        
        # 发送错误提示
        if self.bot_api_uploader:
            self.bot_api_uploader.send_message(error_msg)

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

    def _update_progress_display(self, current: int, total: int):
        """更新进度显示（实现抽象方法）"""
        try:
            # 计算进度百分比
            if total > 0:
                progress = int((current / total) * 100)
                logger.debug(f"📊 上传进度: {progress}% ({current}/{total})")
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
