# -*- coding: utf-8 -*-
"""
现代化 Pyrofork 上传器
基于 Pyrofork 2.3.41+ 实现的稳定、高效的 Telegram 文件上传器
"""

import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import tempfile
import os

from ..base import BaseUploader

logger = logging.getLogger(__name__)


class PyroForkUploader(BaseUploader):
    """现代化 Pyrofork 上传器 - 专为大文件和稳定性设计"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # 配置参数
        self.api_id = config.get('api_id')
        self.api_hash = config.get('api_hash')
        self.bot_token = config.get('bot_token')
        self.chat_id = int(config.get('chat_id', 0))
        
        # 客户端管理
        self.client = None
        self._session_dir = None
        self._is_available = False
        
        # 进度管理
        self._progress_callback: Optional[Callable] = None
        self._current_upload_id = None
        
        # 初始化
        self._initialize()

    def _initialize(self):
        """初始化 Pyrofork 上传器 - 完全避免事件循环问题"""
        try:
            # 延迟导入，避免在初始化时触发事件循环
            self._pyrogram_available = False
            self._tgcrypto_available = False

            # 基本配置验证
            if not all([self.api_id, self.api_hash, self.bot_token, self.chat_id]):
                logger.warning("⚠️ Pyrofork 配置不完整，大文件上传将不可用")
                self._is_available = False
                return

            # 创建会话目录
            self._session_dir = tempfile.mkdtemp(prefix="pyrofork_session_")

            # 代理配置将在实际使用时通过统一的代理转换器处理

            # 标记为可用，实际的依赖检查延迟到使用时
            self._is_available = True
            logger.info("✅ Pyrofork 上传器初始化成功（延迟依赖检查）")

        except Exception as e:
            logger.error(f"❌ Pyrofork 初始化失败: {e}")
            self._is_available = False

    def _check_dependencies(self) -> bool:
        """延迟检查依赖 - 只在实际使用时调用"""
        if hasattr(self, '_dependencies_checked'):
            return self._pyrogram_available

        try:
            # 只检查模块是否存在，不实际导入（避免触发事件循环）
            import importlib.util

            # 检查 pyrofork 包是否存在
            spec = importlib.util.find_spec('pyrogram')
            if spec is None:
                raise ImportError("pyrogram module not found")

            self._pyrogram_available = True

            # 获取版本信息（安全方式）
            version_info = self._get_pyrogram_version()
            logger.debug(f"✅ Pyrofork 版本: {version_info}")

            # 检查 TgCrypto - 支持多种包名和版本
            tgcrypto_variants = [
                ('TgCrypto', 'TgCrypto 标准版本'),
                ('tgcrypto', 'tgcrypto 小写版本'),
                ('TgCrypto-pyrofork', 'TgCrypto-pyrofork 专用版本')
            ]

            self._tgcrypto_available = False
            for module_name, description in tgcrypto_variants:
                try:
                    spec = importlib.util.find_spec(module_name)
                    if spec is not None:
                        self._tgcrypto_available = True
                        logger.debug(f"✅ {description} 可用，性能优化已启用")
                        break
                except ImportError:
                    continue

            if not self._tgcrypto_available:
                logger.debug("⚠️ TgCrypto 不可用，使用纯 Python 实现")

            logger.debug("✅ Pyrofork 依赖检查通过")

            self._dependencies_checked = True
            return True

        except ImportError as e:
            logger.warning(f"⚠️ Pyrofork 依赖缺失: {e}")
            self._pyrogram_available = False
            self._dependencies_checked = True
            return False
        except Exception as e:
            logger.error(f"❌ Pyrofork 依赖检查失败: {e}")
            self._pyrogram_available = False
            self._dependencies_checked = True
            return False

    def _get_pyrogram_version(self) -> str:
        """获取 Pyrogram/Pyrofork 版本信息 - 安全方式"""
        try:
            # 优先从包管理器获取版本，避免导入模块
            try:
                import importlib.metadata
                return importlib.metadata.version('pyrofork')
            except ImportError:
                # Python < 3.8 的兼容性
                try:
                    import pkg_resources
                    return pkg_resources.get_distribution('pyrofork').version
                except:
                    pass

            # 如果包管理器方式失败，尝试安全的模块检查
            try:
                import importlib.util
                import sys

                # 临时导入模块检查版本
                spec = importlib.util.find_spec('pyrogram')
                if spec and spec.origin:
                    # 尝试从模块文件中读取版本信息
                    module = importlib.util.module_from_spec(spec)
                    if hasattr(module, '__version__'):
                        return module.__version__

                return "2.3.66"  # 默认已知版本

            except Exception:
                return "2.3.66"  # 默认已知版本

        except Exception:
            return "版本检测失败"

    def is_available(self) -> bool:
        """检查上传器是否可用 - 使用延迟依赖检查"""
        # 基本可用性检查
        if not self._is_available:
            return False

        # 配置完整性检查
        if not all([self.api_id, self.api_hash, self.bot_token, self.chat_id]):
            logger.debug("⚠️ Pyrofork 配置不完整")
            return False

        # 延迟依赖检查
        return self._check_dependencies()

    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """发送文本消息 - 简化版本"""
        if not self.is_available():
            logger.debug("⚠️ Pyrofork 不可用，跳过消息发送")
            return False

        try:
            return self._run_async(self._async_send_message(message, parse_mode))
        except Exception as e:
            logger.error(f"❌ Pyrofork 消息发送失败: {e}")
            return False

    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """发送文件 - 简化版本"""
        if not self.is_available():
            logger.debug("⚠️ Pyrofork 不可用，跳过文件发送")
            return False

        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"文件不存在: {file_path}")
                return False

            # 设置进度回调
            self._current_upload_id = kwargs.get('upload_id', str(int(time.time())))

            # 异步发送文件
            return self._run_async(self._async_send_file(file_path, caption, **kwargs))

        except Exception as e:
            logger.error(f"❌ Pyrofork 文件发送失败: {e}")
            return False

    def send_media_group(self, files: List[str], caption: str = None) -> bool:
        """发送媒体组"""
        if not self.is_available():
            logger.debug("⚠️ Pyrofork 不可用，跳过媒体组发送")
            return False

        try:
            return self._run_async(self._async_send_media_group(files, caption))
        except Exception as e:
            logger.error(f"❌ Pyrofork 媒体组发送失败: {e}")
            return False

    async def _async_send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """异步发送消息"""
        try:
            client = await self._get_client()
            if not client:
                return False

            # 转换 parse_mode 格式 - Pyrofork 使用不同的枚举
            pyro_parse_mode = self._convert_parse_mode(parse_mode)

            await client.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=pyro_parse_mode
            )

            logger.debug("✅ Pyrofork 消息发送成功")
            return True

        except Exception as e:
            logger.error(f"❌ Pyrofork 异步消息发送失败: {e}")
            return False

    def _convert_parse_mode(self, parse_mode: str):
        """转换 parse_mode 格式"""
        if not parse_mode:
            return None

        parse_mode_lower = parse_mode.lower()

        try:
            from pyrogram.enums import ParseMode

            if parse_mode_lower in ['markdown', 'md']:
                return ParseMode.MARKDOWN
            elif parse_mode_lower in ['html']:
                return ParseMode.HTML
            else:
                # 默认返回 None（无格式化）
                logger.debug(f"🔧 未知的 parse_mode: {parse_mode}，使用无格式化")
                return None

        except ImportError:
            # 如果无法导入 ParseMode，尝试使用字符串
            logger.debug("⚠️ 无法导入 ParseMode，尝试使用字符串格式")
            if parse_mode_lower in ['markdown', 'md']:
                return 'markdown'
            elif parse_mode_lower in ['html']:
                return 'html'
            else:
                return None

    async def _async_send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """异步发送文件"""
        try:
            client = await self._get_client()
            if not client:
                return False
            
            file_path_obj = Path(file_path)
            file_size = file_path_obj.stat().st_size
            
            # 获取文件元数据
            metadata = self.get_file_metadata(file_path)
            file_type = metadata.get('file_type', 'document')
            
            logger.info(f"📤 开始上传 {file_type}: {file_path_obj.name} ({file_size / 1024 / 1024:.1f}MB)")
            
            # 根据文件类型选择发送方法 - 简化版本
            if file_type == 'video':
                await self._send_video_simple(client, file_path, caption)
            elif file_type == 'audio':
                await self._send_audio_simple(client, file_path, caption)
            else:
                await self._send_document_simple(client, file_path, caption)
            
            logger.info(f"✅ Pyrofork 文件上传成功: {file_path_obj.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pyrofork 异步文件发送失败: {e}")
            return False

    async def _send_video_simple(self, client, file_path: str, caption: str):
        """发送视频文件 - 简化版本"""
        await client.send_video(
            chat_id=self.chat_id,
            video=file_path,
            caption=caption or '',
            supports_streaming=True,
            progress=self._progress_callback_wrapper
        )

    async def _send_audio_simple(self, client, file_path: str, caption: str):
        """发送音频文件 - 简化版本"""
        await client.send_audio(
            chat_id=self.chat_id,
            audio=file_path,
            caption=caption or '',
            progress=self._progress_callback_wrapper
        )

    async def _send_photo(self, client, file_path: str, caption: str):
        """发送图片文件"""
        await client.send_photo(
            chat_id=self.chat_id,
            photo=file_path,
            caption=caption or '',
            progress=self._progress_callback_wrapper
        )

    async def _send_document_simple(self, client, file_path: str, caption: str):
        """发送文档文件 - 简化版本"""
        await client.send_document(
            chat_id=self.chat_id,
            document=file_path,
            caption=caption or '',
            progress=self._progress_callback_wrapper
        )

    async def _async_send_media_group(self, files: List[str], caption: str = None) -> bool:
        """异步发送媒体组"""
        try:
            from pyrogram.types import InputMediaVideo, InputMediaPhoto, InputMediaDocument
            
            client = await self._get_client()
            if not client:
                return False
            
            media = []
            for i, file_path in enumerate(files):
                metadata = self.get_file_metadata(file_path)
                file_type = metadata.get('file_type', 'document')
                
                if file_type == 'video':
                    media_item = InputMediaVideo(
                        media=file_path,
                        caption=caption if i == 0 else ''
                    )
                elif file_type == 'photo':
                    media_item = InputMediaPhoto(
                        media=file_path,
                        caption=caption if i == 0 else ''
                    )
                else:
                    media_item = InputMediaDocument(
                        media=file_path,
                        caption=caption if i == 0 else ''
                    )
                
                media.append(media_item)
            
            await client.send_media_group(
                chat_id=self.chat_id,
                media=media
            )
            
            logger.info(f"✅ Pyrofork 媒体组发送成功 ({len(media)} 个文件)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pyrofork 异步媒体组发送失败: {e}")
            return False

    async def _send_with_retry(self, send_func, max_retries: int = 3, **kwargs):
        """简化重试机制 - 学习ytdlbot的指数退避策略"""
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"📤 上传尝试 {attempt + 1}/{max_retries}")
                return await send_func(**kwargs)

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # 检查是否是可重试的错误
                if self._is_retryable_error(error_msg):
                    if attempt < max_retries - 1:
                        # 简单指数退避：2^attempt 秒
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(f"⚠️ 上传失败，{wait_time}秒后重试 (尝试 {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ 上传失败，已达到最大重试次数: {e}")
                        raise
                else:
                    # 不可重试的错误，直接抛出
                    logger.error(f"❌ 上传失败（不可重试）: {e}")
                    raise

        # 如果所有重试都失败，抛出最后一个异常
        raise last_exception

    def _is_retryable_error(self, error_msg: str) -> bool:
        """判断错误是否可重试"""
        retryable_errors = [
            'timeout',
            'timed out',
            'request timed out',
            'connection',
            'network',
            'temporary',
            'server error',
            'internal error',
            'flood',
            'too many requests',
            'rate limit',
            'file part expired',
            'upload failed'
        ]

        return any(error in error_msg for error in retryable_errors)

    async def _progress_callback_wrapper(self, current: int, total: int):
        """进度回调包装器"""
        try:
            if self._progress_callback:
                self._progress_callback(current, total)

            # 调用父类的进度处理
            self.upload_hook(current, total)

        except Exception as e:
            logger.debug(f"进度回调失败: {e}")

    async def _get_client(self):
        """获取 Pyrofork 客户端 - 改进版本"""
        try:
            # 如果客户端存在但连接有问题，先清理
            if self.client and not self.client.is_connected:
                logger.debug("🔄 检测到客户端连接异常，重新创建")
                await self._cleanup_failed_client()

            if not self.client:
                from pyrogram import Client

                # 使用内存会话，避免数据库锁定 - 学习ytdlbot简洁性
                session_name = "ytdlp_memory_session"
                logger.debug(f"🔧 创建 Pyrofork 客户端: {session_name} (内存会话)")

                # 获取代理配置
                proxy_config = self._get_proxy_config()

                # 简化客户端配置 - 学习ytdlbot的简洁性
                client_kwargs = {
                    'name': session_name,
                    'api_id': self.api_id,
                    'api_hash': self.api_hash,
                    'bot_token': self.bot_token,
                    'in_memory': True,  # 使用内存会话
                    'no_updates': True,  # 禁用更新处理
                    # 移除过度优化的参数，使用Pyrogram默认值
                }

                # 添加代理配置到客户端参数
                if proxy_config:
                    client_kwargs['proxy'] = proxy_config
                    logger.info(f"✅ Pyrofork 使用代理配置: {proxy_config.get('scheme')}://{proxy_config.get('hostname')}:{proxy_config.get('port')}")
                else:
                    logger.info("🌐 Pyrofork 使用直连模式")

                self.client = Client(**client_kwargs)

            # 检查并建立连接 - 简化版本
            if not self.client.is_connected:
                logger.debug("🔗 启动 Pyrofork 客户端连接...")

                try:
                    # 启动客户端 - 增加超时时间
                    logger.debug("🔗 正在启动 Pyrofork 客户端（60秒超时）...")
                    await asyncio.wait_for(self.client.start(), timeout=60.0)
                    logger.debug("✅ Pyrofork 客户端启动成功")

                    # 简单验证连接 - 添加超时
                    try:
                        bot_info = await asyncio.wait_for(self.client.get_me(), timeout=10.0)
                        logger.debug(f"✅ Pyrofork 客户端验证成功: @{bot_info.username}")
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ 客户端验证超时，但连接可能已建立")
                    except Exception as verify_error:
                        logger.warning(f"⚠️ 客户端验证失败，但连接已建立: {verify_error}")

                except asyncio.TimeoutError:
                    logger.error("❌ Pyrofork 客户端启动超时（60秒）")
                    await self._cleanup_failed_client()
                    return None
                except Exception as start_error:
                    logger.error(f"❌ Pyrofork 客户端启动失败: {start_error}")
                    await self._cleanup_failed_client()
                    return None

            return self.client

        except Exception as e:
            logger.error(f"❌ 获取 Pyrofork 客户端异常: {e}")
            await self._cleanup_failed_client()
            return None

    async def _cleanup_failed_client(self):
        """清理失败的客户端"""
        if self.client:
            try:
                if self.client.is_connected:
                    await asyncio.wait_for(self.client.stop(), timeout=10)
                    logger.debug("🧹 已停止失败的客户端连接")
            except Exception as cleanup_error:
                logger.debug(f"⚠️ 清理客户端时出错: {cleanup_error}")
            finally:
                self.client = None

    def _reset_client_state(self):
        """重置客户端状态 - 用于错误恢复"""
        logger.debug("🔄 重置 Pyrofork 客户端状态")
        self.client = None

    def _calculate_upload_timeout(self, coro) -> int:
        """根据操作类型计算超时时间"""
        try:
            # 检查是否是消息发送操作
            if hasattr(coro, 'cr_frame') and hasattr(coro.cr_frame, 'f_locals'):
                locals_dict = coro.cr_frame.f_locals
                # 如果是消息发送，使用较短的超时时间
                if 'message' in locals_dict and 'file_path' not in locals_dict:
                    logger.debug("🕐 检测到消息发送操作，使用短超时时间: 30秒")
                    return 30  # 消息发送30秒超时

            # 默认超时时间（30分钟）- 用于文件上传
            base_timeout = 1800

            # 尝试从协程中获取文件路径
            file_path = None
            if hasattr(coro, 'cr_frame') and hasattr(coro.cr_frame, 'f_locals'):
                locals_dict = coro.cr_frame.f_locals
                file_path = locals_dict.get('file_path')

            if file_path and Path(file_path).exists():
                from core.file_utils import FileUtils
                file_size_mb = FileUtils.get_file_size_mb(file_path)

                # 简化超时时间计算 - 学习ytdlbot的简洁策略
                if file_size_mb <= 50:          # 小文件 (≤50MB)
                    timeout = 600               # 10分钟
                elif file_size_mb <= 200:       # 中等文件 (≤200MB)
                    timeout = 1200              # 20分钟
                elif file_size_mb <= 500:       # 大文件 (≤500MB)
                    timeout = 1800              # 30分钟
                else:                            # 超大文件 (>500MB)
                    timeout = 3600              # 60分钟

                logger.info(f"🕐 文件大小: {file_size_mb:.1f}MB，设置超时时间: {timeout/60:.0f}分钟")
                return timeout

            logger.debug(f"🕐 使用默认超时时间: {base_timeout/60:.0f}分钟")
            return base_timeout

        except Exception as e:
            logger.debug(f"⚠️ 计算超时时间失败，使用默认值: {e}")
            return 1800  # 30分钟默认超时

    def _get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """简化代理配置 - 使用Pyrogram原生代理支持，支持用户开关控制"""
        try:
            # 首先检查用户是否启用了代理上传
            from modules.telegram.services.config_service import get_telegram_config_service
            config_service = get_telegram_config_service()

            if not config_service.use_proxy_for_upload():
                logger.info("🌐 PyroFork 用户已禁用代理上传，使用直连模式")
                return None

            # 用户启用了代理上传，读取系统代理配置
            from core.database import get_database
            db = get_database()
            proxy_config = db.get_proxy_config()

            if not proxy_config or not proxy_config.get('enabled'):
                logger.warning("⚠️ PyroFork 用户启用了代理上传，但系统代理未配置或未启用")
                return None

            proxy_host = proxy_config.get('host')
            proxy_port = proxy_config.get('port')

            if not proxy_host or not proxy_port:
                logger.warning("⚠️ 代理配置不完整，缺少host或port")
                return None

            # 使用Pyrogram原生代理格式
            pyrogram_proxy = {
                'scheme': 'socks5',  # 固定使用SOCKS5
                'hostname': proxy_host,
                'port': proxy_port
            }

            logger.info(f"✅ PyroFork使用用户启用的代理: socks5://{proxy_host}:{proxy_port}")
            return pyrogram_proxy

        except Exception as e:
            logger.error(f"❌ PyroFork 获取代理配置失败: {e}")
            return None





    # 移除复杂的PySocks设置，使用Pyrogram原生代理支持
    # def _setup_pysocks_proxy(self) -> bool:
    #     """已移除 - 使用Pyrogram原生代理支持"""
    #     return False



    def _run_async(self, coro):
        """在新线程中运行异步操作 - 改进版本"""
        result = [None]
        exception = [None]
        completed = [False]

        def run_in_thread():
            """在独立线程中运行异步操作"""
            loop = None
            try:
                # 确保当前线程没有事件循环
                try:
                    asyncio.get_running_loop()
                    logger.debug("⚠️ 检测到当前线程已有事件循环，将在新线程中运行")
                except RuntimeError:
                    # 没有运行中的事件循环，这是正常的
                    pass

                # 强制创建新的事件循环，避免冲突
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                logger.debug("🔧 创建新的事件循环用于 Pyrofork 操作")

                try:
                    # 根据文件大小动态设置超时时间
                    timeout = self._calculate_upload_timeout(coro)

                    result[0] = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
                    completed[0] = True
                    logger.debug("✅ Pyrofork 异步操作完成")

                except asyncio.TimeoutError:
                    exception[0] = Exception(f"Pyrofork 操作超时（{timeout/60:.0f}分钟）")
                    completed[0] = True
                    logger.error(f"❌ Pyrofork 操作超时（{timeout/60:.0f}分钟）")

                except Exception as e:
                    # 检查是否是队列绑定错误
                    error_msg = str(e).lower()
                    if "bound to a different event loop" in error_msg or "queue" in error_msg:
                        logger.warning("🔄 检测到队列绑定错误，重置客户端状态")
                        self.client = None
                        exception[0] = Exception(f"Pyrogram 队列绑定错误，已重置客户端: {str(e)}")
                    else:
                        exception[0] = e
                    completed[0] = True
                    logger.error(f"❌ Pyrofork 异步操作失败: {e}")

            except Exception as e:
                exception[0] = e
                completed[0] = True
                logger.error(f"❌ 异步线程运行失败: {e}")

            finally:
                # 强制清理资源和事件循环
                if loop is not None:
                    try:
                        # 强制停止客户端连接（如果存在）
                        if hasattr(self, 'client') and self.client:
                            try:
                                if self.client.is_connected:
                                    logger.debug("🔌 强制断开 Pyrofork 客户端连接")
                                    loop.run_until_complete(
                                        asyncio.wait_for(self.client.stop(), timeout=10)
                                    )
                            except Exception as client_error:
                                logger.debug(f"⚠️ 强制断开客户端时出错: {client_error}")

                        # 获取所有未完成的任务
                        try:
                            pending = asyncio.all_tasks(loop)
                        except RuntimeError:
                            # 如果循环已关闭，跳过任务清理
                            pending = []

                        if pending:
                            logger.debug(f"🧹 清理 {len(pending)} 个未完成的任务")

                            # 取消所有任务
                            for task in pending:
                                if not task.done():
                                    task.cancel()

                            # 等待任务完成，设置短超时
                            try:
                                loop.run_until_complete(
                                    asyncio.wait_for(
                                        asyncio.gather(*pending, return_exceptions=True),
                                        timeout=3  # 减少清理超时时间
                                    )
                                )
                            except (asyncio.TimeoutError, RuntimeError):
                                logger.debug("⚠️ 任务清理超时或循环已关闭，强制继续")

                    except Exception as cleanup_error:
                        logger.debug(f"⚠️ 清理任务时出错: {cleanup_error}")

                    finally:
                        # 强制关闭事件循环
                        try:
                            if not loop.is_closed():
                                loop.close()
                                logger.debug("✅ 事件循环已强制关闭")
                        except Exception as close_error:
                            logger.debug(f"⚠️ 关闭事件循环时出错: {close_error}")

                        # 清除线程的事件循环引用
                        try:
                            asyncio.set_event_loop(None)
                        except Exception:
                            pass

        # 启动线程
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # 等待完成，最多10分钟
        thread.join(timeout=600)

        if not completed[0] or thread.is_alive():
            logger.error("❌ Pyrofork 操作线程超时（10分钟）")
            # 强制重置客户端状态
            self.client = None
            raise Exception("Pyrofork 操作线程超时")

        if exception[0]:
            # 如果出现事件循环相关错误，重置客户端状态
            error_msg = str(exception[0]).lower()
            if any(keyword in error_msg for keyword in ["event loop", "queue", "bound to", "different event loop"]):
                logger.warning("🔄 检测到事件循环/队列错误，重置客户端状态")
                self.client = None
            raise exception[0]

        return result[0]

    def cleanup(self):
        """清理资源"""
        try:
            if self.client:
                def stop_client():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            if self.client.is_connected:
                                loop.run_until_complete(self.client.stop())
                        finally:
                            loop.close()
                    except:
                        pass
                
                thread = threading.Thread(target=stop_client, daemon=True)
                thread.start()
                thread.join(timeout=10)
                
                self.client = None
            
            # 清理会话目录
            if self._session_dir and os.path.exists(self._session_dir):
                import shutil
                try:
                    shutil.rmtree(self._session_dir)
                except:
                    pass
            
            super().cleanup()
            
        except Exception as e:
            logger.error(f"❌ Pyrofork 上传器清理失败: {e}")

    async def _diagnose_network(self) -> bool:
        """诊断网络连接"""
        try:
            import aiohttp
            import time

            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.telegram.org") as response:
                    latency = time.time() - start_time

                    if response.status == 200:
                        logger.info(f"🌐 网络诊断: Telegram API延迟 {latency*1000:.0f}ms")
                        return latency < 5.0  # 5秒内正常
                    else:
                        logger.warning(f"⚠️ 网络诊断: Telegram API返回状态 {response.status}")
                        return False

        except Exception as e:
            logger.warning(f"⚠️ 网络诊断失败: {e}")
            return False

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """设置进度回调函数"""
        self._progress_callback = callback

    def _update_progress_display(self, text: str, file_id: str = None):
        """更新进度显示（实现抽象方法）"""
        try:
            # 简单的日志记录，Pyrofork 主要通过回调处理进度
            logger.debug(f"📊 Pyrofork 进度: {text}")
        except Exception as e:
            logger.debug(f"进度显示更新失败: {e}")
