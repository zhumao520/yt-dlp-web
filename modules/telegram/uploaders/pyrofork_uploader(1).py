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
        """发送文本消息"""
        if not self.is_available():
            logger.debug("⚠️ Pyrofork 不可用，跳过消息发送")
            return False

        try:
            return self._run_async(self._async_send_message(message, parse_mode))
        except Exception as e:
            logger.error(f"❌ Pyrofork 消息发送失败: {e}")
            return False

    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """发送文件"""
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
            
            await client.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            logger.debug("✅ Pyrofork 消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pyrofork 异步消息发送失败: {e}")
            return False

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
            
            # 根据文件类型选择发送方法
            if file_type == 'video':
                await self._send_video(client, file_path, caption, metadata)
            elif file_type == 'audio':
                await self._send_audio(client, file_path, caption, metadata)
            elif file_type == 'photo':
                await self._send_photo(client, file_path, caption)
            else:
                await self._send_document(client, file_path, caption)
            
            logger.info(f"✅ Pyrofork 文件上传成功: {file_path_obj.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pyrofork 异步文件发送失败: {e}")
            return False

    async def _send_video(self, client, file_path: str, caption: str, metadata: Dict[str, Any]):
        """发送视频文件"""
        await client.send_video(
            chat_id=self.chat_id,
            video=file_path,
            caption=caption or '',
            duration=int(metadata.get('duration', 0)),
            width=metadata.get('width', 1280),
            height=metadata.get('height', 720),
            supports_streaming=True,
            progress=self._progress_callback_wrapper
        )

    async def _send_audio(self, client, file_path: str, caption: str, metadata: Dict[str, Any]):
        """发送音频文件"""
        await client.send_audio(
            chat_id=self.chat_id,
            audio=file_path,
            caption=caption or '',
            duration=int(metadata.get('duration', 0)),
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

    async def _send_document(self, client, file_path: str, caption: str):
        """发送文档文件"""
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
            if not self.client:
                from pyrogram import Client

                session_name = os.path.join(self._session_dir, "ytdlp_session")
                logger.debug(f"🔧 创建 Pyrofork 客户端: {session_name}")

                # 创建客户端配置
                self.client = Client(
                    name=session_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    bot_token=self.bot_token,
                    workdir=self._session_dir,
                    in_memory=True,  # 使用内存会话
                    no_updates=True  # 禁用更新处理，减少资源占用
                )

            # 检查并建立连接
            if not self.client.is_connected:
                logger.debug("🔗 启动 Pyrofork 客户端连接...")

                try:
                    # 启动客户端，增加超时时间
                    await asyncio.wait_for(self.client.start(), timeout=90)
                    logger.debug("✅ Pyrofork 客户端启动成功")

                    # 验证连接 - 获取机器人信息
                    try:
                        bot_info = await asyncio.wait_for(self.client.get_me(), timeout=15)
                        logger.debug(f"✅ Pyrofork 客户端验证成功: @{bot_info.username}")
                    except Exception as verify_error:
                        logger.warning(f"⚠️ 客户端验证失败，但连接已建立: {verify_error}")

                except asyncio.TimeoutError:
                    logger.error("❌ Pyrofork 客户端启动超时（90秒）")
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

    def _run_async(self, coro):
        """在新线程中运行异步操作 - 改进版本"""
        result = [None]
        exception = [None]
        completed = [False]

        def run_in_thread():
            """在独立线程中运行异步操作"""
            try:
                # 强制创建新的事件循环，避免冲突
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                logger.debug("🔧 创建新的事件循环用于 Pyrofork 操作")

                try:
                    # 设置合理的超时时间
                    timeout = 300  # 5分钟超时
                    result[0] = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
                    completed[0] = True
                    logger.debug("✅ Pyrofork 异步操作完成")

                except asyncio.TimeoutError:
                    exception[0] = Exception("Pyrofork 操作超时（5分钟）")
                    completed[0] = True
                    logger.error("❌ Pyrofork 操作超时")

                except Exception as e:
                    exception[0] = e
                    completed[0] = True
                    logger.error(f"❌ Pyrofork 异步操作失败: {e}")

                finally:
                    # 安全的资源清理
                    try:
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
                                        timeout=5  # 减少清理超时时间
                                    )
                                )
                            except (asyncio.TimeoutError, RuntimeError):
                                logger.debug("⚠️ 任务清理超时或循环已关闭，继续关闭")

                    except Exception as cleanup_error:
                        logger.debug(f"⚠️ 清理任务时出错: {cleanup_error}")

                    finally:
                        # 安全关闭事件循环
                        try:
                            if not loop.is_closed():
                                loop.close()
                                logger.debug("✅ 事件循环已安全关闭")
                        except Exception as close_error:
                            logger.debug(f"⚠️ 关闭事件循环时出错: {close_error}")

            except Exception as e:
                exception[0] = e
                completed[0] = True
                logger.error(f"❌ 异步线程运行失败: {e}")

        # 启动线程
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # 等待完成，最多10分钟
        thread.join(timeout=600)

        if not completed[0] or thread.is_alive():
            logger.error("❌ 异步操作超时或未完成")
            raise TimeoutError("异步操作超时")

        if exception[0]:
            logger.error(f"❌ 异步操作异常: {exception[0]}")
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

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """设置进度回调函数"""
        self._progress_callback = callback

    def _update_progress_display(self, current: int, total: int):
        """更新进度显示（实现抽象方法）"""
        try:
            # 计算进度百分比
            if total > 0:
                progress = int((current / total) * 100)
                logger.debug(f"📊 Pyrofork 上传进度: {progress}% ({current}/{total})")
        except Exception as e:
            logger.debug(f"进度显示更新失败: {e}")
