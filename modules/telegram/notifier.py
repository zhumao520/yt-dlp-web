# -*- coding: utf-8 -*-
"""
统一 Telegram 通知器
整合现代化和传统实现，提供平滑的迁移路径
"""

import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class UnifiedTelegramNotifier:
    """统一 Telegram 通知器 - 智能选择最佳实现"""

    def __init__(self):
        self.config = None
        self.uploader = None
        self._lock = threading.RLock()
        
        # 进度跟踪
        self._active_downloads = {}
        self._progress_messages = {}
        
        # 实现选择
        self._use_modern = True  # 默认使用现代化实现
        
        # 初始化
        self._load_config()
        self._initialize_uploader()

    def _load_config(self):
        """加载配置 - 优先从数据库读取"""
        try:
            # 首先尝试从数据库读取配置
            try:
                from core.database import get_database
                db = get_database()
                db_config = db.get_telegram_config()

                if db_config:
                    # 从数据库读取配置
                    self.config = {
                        'enabled': bool(db_config.get('enabled', False)),
                        'bot_token': db_config.get('bot_token'),
                        'chat_id': str(db_config.get('chat_id', '')),
                        'api_id': db_config.get('api_id'),
                        'api_hash': db_config.get('api_hash'),
                        'auto_fallback': True,  # 默认启用
                        'prefer_pyrofork': False,  # 默认优先使用 Bot API（更稳定）
                        'use_modern': True  # 默认使用现代化实现
                    }
                    logger.info("✅ 从数据库加载 Telegram 配置成功")
                else:
                    raise Exception("数据库中没有 Telegram 配置")

            except Exception as db_error:
                logger.warning(f"⚠️ 从数据库加载配置失败: {db_error}")

                # 回退到环境变量/配置文件
                from core.config import get_config

                self.config = {
                    'enabled': get_config('telegram.enabled', False),
                    'bot_token': get_config('telegram.bot_token'),
                    'chat_id': get_config('telegram.chat_id'),
                    'api_id': get_config('telegram.api_id'),
                    'api_hash': get_config('telegram.api_hash'),
                    'auto_fallback': get_config('telegram.auto_fallback', True),
                    'prefer_pyrofork': get_config('telegram.prefer_pyrofork', False),  # 默认优先Bot API
                    'use_modern': get_config('telegram.use_modern', True)
                }
                logger.info("✅ 从环境变量/配置文件加载 Telegram 配置")

            self._use_modern = self.config.get('use_modern', True)

            # 调试信息
            logger.info(f"🔧 Telegram 配置: enabled={self.config.get('enabled')}, "
                       f"bot_token={'已配置' if self.config.get('bot_token') else '未配置'}, "
                       f"chat_id={self.config.get('chat_id')}")

        except Exception as e:
            logger.error(f"❌ 加载 Telegram 配置失败: {e}")
            self.config = {'enabled': False}

    def _initialize_uploader(self):
        """初始化上传器"""
        try:
            if not self.is_enabled():
                logger.debug("Telegram 未启用，跳过上传器初始化")
                return
            
            if self._use_modern:
                # 尝试使用现代化实现
                try:
                    from .uploaders.modern_hybrid import ModernHybridUploader
                    self.uploader = ModernHybridUploader(self.config)
                    
                    if self.uploader.is_available():
                        logger.info("✅ 现代化 Telegram 通知器初始化成功")
                        return
                    else:
                        logger.warning("⚠️ 现代化上传器不可用，回退到传统实现")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 现代化实现初始化失败，回退到传统实现: {e}")
            
            # 回退到传统实现
            try:
                from .uploaders.hybrid import HybridUploader
                self.uploader = HybridUploader(self.config)
                
                if hasattr(self.uploader, 'is_available') and callable(self.uploader.is_available):
                    available = self.uploader.is_available()
                else:
                    # 传统实现可能没有 is_available 方法
                    available = bool(self.uploader)
                
                if available:
                    logger.info("✅ 传统 Telegram 通知器初始化成功")
                else:
                    logger.warning("⚠️ 传统上传器也不可用")
                    self.uploader = None
                    
            except Exception as e:
                logger.error(f"❌ 传统实现初始化也失败: {e}")
                self.uploader = None
            
        except Exception as e:
            logger.error(f"❌ 初始化上传器失败: {e}")
            self.uploader = None

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return bool(
            self.config and 
            self.config.get('enabled') and 
            self.config.get('bot_token') and 
            self.config.get('chat_id')
        )

    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """发送文本消息 - 增强异常处理"""
        if not self.is_enabled():
            logger.debug("Telegram 未启用，跳过消息发送")
            return False

        if not self.uploader:
            logger.error("❌ Telegram 上传器不可用")
            # 尝试重新初始化上传器
            try:
                logger.info("🔄 尝试重新初始化 Telegram 上传器")
                self._initialize_uploader()
                if not self.uploader:
                    logger.error("❌ 重新初始化失败")
                    return False
            except Exception as init_error:
                logger.error(f"❌ 重新初始化异常: {init_error}")
                return False

        if not message or not message.strip():
            logger.warning("⚠️ 消息内容为空，跳过发送")
            return False

        try:
            logger.info(f"📤 发送 Telegram 消息，长度: {len(message)} 字符")
            success = self.uploader.send_message(message, parse_mode)

            if success:
                logger.info("✅ 消息发送成功")
                return True
            else:
                logger.error("❌ 消息发送失败")
                return False

        except AttributeError as e:
            logger.error(f"❌ 上传器属性错误: {e}")
            logger.error("🔧 这可能是由于上传器初始化不完整导致的")
            return False
        except Exception as e:
            logger.error(f"❌ 发送 Telegram 消息失败: {e}")
            logger.error(f"🔍 异常类型: {type(e).__name__}")
            import traceback
            logger.debug(f"🔍 详细堆栈: {traceback.format_exc()}")
            return False

    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """发送文件 - 增强异常处理"""
        if not self.is_enabled():
            logger.debug("Telegram 未启用，跳过文件发送")
            return False

        if not self.uploader:
            logger.error("❌ Telegram 上传器不可用")
            return False

        if not file_path:
            logger.error("❌ 文件路径为空")
            return False

        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"❌ 文件不存在: {file_path}")
                return False

            # 检查文件是否可读
            if not file_path_obj.is_file():
                logger.error(f"❌ 路径不是文件: {file_path}")
                return False

            try:
                file_size = file_path_obj.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
            except OSError as e:
                logger.error(f"❌ 无法获取文件信息: {e}")
                return False

            if file_size == 0:
                logger.error(f"❌ 文件为空: {file_path}")
                return False

            logger.info(f"📤 准备发送文件: {file_path_obj.name} ({file_size_mb:.1f}MB)")

            success = self.uploader.send_file(file_path, caption, **kwargs)

            if success:
                logger.info(f"✅ 文件发送成功: {file_path_obj.name}")
                return True
            else:
                logger.error(f"❌ 文件发送失败: {file_path_obj.name}")
                return False

        except PermissionError as e:
            logger.error(f"❌ 文件权限错误: {e}")
            return False
        except FileNotFoundError as e:
            logger.error(f"❌ 文件未找到: {e}")
            return False
        except OSError as e:
            logger.error(f"❌ 文件系统错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 发送 Telegram 文件失败: {e}")
            logger.error(f"🔍 异常类型: {type(e).__name__}")
            import traceback
            logger.debug(f"🔍 详细堆栈: {traceback.format_exc()}")
            return False

    def update_progress_message(self, download_id: str, message: str) -> bool:
        """更新进度消息"""
        if not self.is_enabled() or not self.uploader:
            return False
        
        try:
            # 发送进度更新消息
            success = self.send_message(message)
            if success:
                self._progress_messages[download_id] = time.time()
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 更新进度消息失败: {e}")
            return False

    def cancel_download_by_telegram(self, download_id: str) -> bool:
        """通过 Telegram 取消下载"""
        try:
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            
            success = download_manager.cancel_download(download_id)
            if success:
                # 清理进度消息记录
                with self._lock:
                    self._progress_messages.pop(download_id, None)
                    self._active_downloads.pop(download_id, None)
                
                logger.info(f"✅ 通过 Telegram 取消下载: {download_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 通过 Telegram 取消下载失败: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取通知器状态"""
        if not self.is_enabled():
            return {
                'enabled': False,
                'status': 'disabled',
                'message': 'Telegram 通知未启用',
                'implementation': '未知'
            }
        
        if not self.uploader:
            return {
                'enabled': True,
                'status': 'error',
                'message': '上传器初始化失败'
            }
        
        # 获取上传器状态
        uploader_status = {}
        if hasattr(self.uploader, 'get_uploader_status'):
            uploader_status = self.uploader.get_uploader_status()
        
        return {
            'enabled': True,
            'status': 'active',
            'message': '正常运行',
            'implementation': '现代化' if self._use_modern else '传统',
            'uploaders': uploader_status,
            'active_downloads': len(self._active_downloads),
            'config': {
                'bot_token_configured': bool(self.config.get('bot_token')),
                'chat_id_configured': bool(self.config.get('chat_id')),
                'api_credentials_configured': bool(
                    self.config.get('api_id') and self.config.get('api_hash')
                ),
                'auto_fallback': self.config.get('auto_fallback', True),
                'prefer_pyrofork': self.config.get('prefer_pyrofork', True)
            }
        }

    def test_connection(self) -> Dict[str, Any]:
        """测试 Telegram 连接"""
        try:
            if not self.is_enabled():
                return {
                    'success': False,
                    'error': 'Telegram 未启用',
                    'details': '请先配置 Bot Token 和 Chat ID',
                    'bot_api': False,
                    'pyrogrammod': False
                }

            # 获取上传器状态
            bot_api_status = False
            pyrogrammod_status = False

            if self.uploader and hasattr(self.uploader, 'get_uploader_status'):
                uploader_status = self.uploader.get_uploader_status()
                bot_api_status = uploader_status.get('bot_api_available', False)
                # 统一字段名：pyrofork_available -> pyrogrammod（保持向后兼容）
                pyrogrammod_status = uploader_status.get('pyrofork_available', False)
                logger.debug(f"📊 从上传器获取状态: Bot API={bot_api_status}, Pyrofork={pyrogrammod_status}")
            elif self.uploader:
                # 如果有上传器但没有状态方法，尝试检查基本可用性
                if hasattr(self.uploader, 'bot_api_uploader') and self.uploader.bot_api_uploader:
                    bot_api_status = self.uploader.bot_api_uploader.is_available()
                if hasattr(self.uploader, 'pyrofork_uploader') and self.uploader.pyrofork_uploader:
                    pyrogrammod_status = self.uploader.pyrofork_uploader.is_available()
                logger.debug(f"📊 从上传器组件获取状态: Bot API={bot_api_status}, Pyrofork={pyrogrammod_status}")
            else:
                logger.debug("📊 没有可用的上传器")

            # 发送测试消息
            test_message = "🤖 **连接测试**\n\n✅ Telegram 连接正常！"
            success = self.send_message(test_message)

            if success:
                return {
                    'success': True,
                    'message': '连接测试成功',
                    'implementation': self._use_modern if hasattr(self, '_use_modern') else '未知',
                    'bot_api': bot_api_status,
                    'pyrogrammod': pyrogrammod_status
                }
            else:
                return {
                    'success': False,
                    'error': '消息发送失败',
                    'details': '请检查 Bot Token 和网络连接',
                    'bot_api': bot_api_status,
                    'pyrogrammod': pyrogrammod_status
                }

        except Exception as e:
            logger.error(f"❌ 测试 Telegram 连接失败: {e}")
            return {
                'success': False,
                'error': f'连接测试异常: {str(e)}',
                'details': '请检查配置和网络连接',
                'bot_api': False,
                'pyrogrammod': False
            }

    def cleanup(self):
        """清理资源"""
        try:
            if self.uploader and hasattr(self.uploader, 'cleanup'):
                self.uploader.cleanup()
                self.uploader = None

            with self._lock:
                self._active_downloads.clear()
                self._progress_messages.clear()

            logger.info("✅ 统一 Telegram 通知器清理完成")

        except Exception as e:
            logger.error(f"❌ 清理统一 Telegram 通知器失败: {e}")


# 全局实例
_unified_notifier_instance = None
_unified_notifier_lock = threading.Lock()


def get_telegram_notifier() -> UnifiedTelegramNotifier:
    """获取统一 Telegram 通知器实例（单例）"""
    global _unified_notifier_instance
    
    if _unified_notifier_instance is None:
        with _unified_notifier_lock:
            if _unified_notifier_instance is None:
                _unified_notifier_instance = UnifiedTelegramNotifier()
    
    return _unified_notifier_instance


# 为了兼容性，提供旧的函数名和类名
get_modern_telegram_notifier = get_telegram_notifier
TelegramNotifier = UnifiedTelegramNotifier  # 兼容性别名


# ==================== 现代化事件监听器 ====================

from core.events import on, Events

@on(Events.DOWNLOAD_STARTED)
def handle_download_started(data):
    """处理下载开始事件"""
    try:
        # 检查数据有效性
        if not data or not isinstance(data, dict):
            logger.warning(f"📡 收到无效的下载开始事件数据: {data}")
            return

        download_id = data.get('download_id')
        url = data.get('url')
        options = data.get('options', {})

        # 验证必需字段
        if not download_id or not url:
            logger.warning(f"📡 下载开始事件缺少必需字段: download_id={download_id}, url={url}")
            return

        # 提前检查 Telegram 是否启用
        notifier = get_telegram_notifier()
        if not notifier or not notifier.is_enabled():
            logger.debug(f"📡 Telegram 未启用，跳过下载开始事件: {download_id}")
            return

        # 智能获取标题 - 优先使用事件数据，回退到自定义文件名或默认值
        title = data.get('title')  # 可能是自定义文件名或None
        source = 'web'

        # 安全地处理选项
        if options and isinstance(options, dict):
            source = options.get('source', 'web')

            # 如果事件中没有标题，尝试从选项中获取自定义文件名
            if not title and options.get('custom_filename'):
                title = options['custom_filename']
                logger.debug(f"📝 从选项中获取自定义文件名作为标题: {title}")

        # 最后的默认值
        if not title:
            title = 'Unknown'

        # 创建跟踪记录
        with notifier._lock:
            notifier._active_downloads[download_id] = {
                'title': title,
                'url': url,
                'last_progress': 0,
                'start_time': time.time(),
                'source': source
            }

        # 根据下载来源发送不同的开始通知
        if source == 'telegram_webhook':
            logger.info(f"📡 Telegram 下载开始跟踪: {download_id}")
        else:
            logger.info(f"📡 Web 下载开始跟踪: {download_id}")
            # 为 Web 下载发送开始通知
            start_message = f"📥 **开始下载**\n\n📹 **{title[:50]}**\n🔗 **来源**: Web 界面"
            notifier.send_message(start_message)

    except Exception as e:
        logger.error(f"❌ 处理下载开始事件失败: {e}")


@on(Events.DOWNLOAD_PROGRESS)
def handle_download_progress(data):
    """处理下载进度事件"""
    # 检查数据有效性
    if not data or not isinstance(data, dict):
        logger.debug(f"📡 收到无效的下载进度事件数据: {data}")
        return

    # 进度事件已重新启用，支持Web界面实时进度显示
    download_id = data.get('download_id')
    progress = data.get('progress', 0)
    status = data.get('status', 'downloading')

    logger.debug(f"📊 下载进度更新: {download_id} - {progress}% ({status})")


@on(Events.DOWNLOAD_COMPLETED)
def handle_download_completed(data):
    """处理下载完成事件 - 自动发送文件"""
    try:
        # 检查数据有效性
        if not data or not isinstance(data, dict):
            logger.warning(f"📡 收到无效的下载完成事件数据: {data}")
            return

        download_id = data.get('download_id')
        file_path = data.get('file_path')
        title = data.get('title', 'Unknown')

        # 验证必需字段
        if not download_id:
            logger.warning(f"📡 下载完成事件缺少download_id: {data}")
            return

        # 提前检查 Telegram 是否启用，避免不必要的处理
        notifier = get_telegram_notifier()
        if not notifier or not notifier.is_enabled():
            logger.debug(f"📡 Telegram 未启用，跳过下载完成事件: {download_id}")
            return

        # 检查是否有有效的上传器
        if not notifier.uploader:
            logger.debug(f"📡 Telegram 上传器不可用，跳过下载完成事件: {download_id}")
            return

        logger.info(f"📡 收到下载完成事件: {download_id} - {title}")

        # 发送完成通知和文件
        caption = f"✅ **下载完成**\n\n📹 **{title[:50]}**"

        if file_path and Path(file_path).exists():
            # 添加上传状态跟踪，防止重复上传
            upload_key = f"upload_{download_id}"

            # 检查是否已经在上传中
            with notifier._lock:
                if upload_key in notifier._active_downloads:
                    logger.warning(f"⚠️ 文件已在上传中，跳过重复上传: {download_id}")
                    return

                # 标记为上传中
                notifier._active_downloads[upload_key] = {
                    'status': 'uploading',
                    'start_time': time.time()
                }

            try:
                success = notifier.send_file(file_path, caption, upload_id=download_id)
                if success:
                    logger.info(f"✅ 文件自动发送成功: {title}")
                else:
                    # 发送失败，提供Web下载链接
                    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024) if Path(file_path).exists() else 0
                    filename = Path(file_path).name

                    # 获取Web面板URL
                    web_url = self._get_web_panel_url()
                    # 使用无需认证的API路径，避免登录重定向
                    download_url = f"{web_url}/api/shortcuts/file/{filename}"

                    if file_size_mb > 50:
                        # 大文件特殊处理
                        help_message = f"""{caption}

❌ **文件发送失败** (文件过大: {file_size_mb:.1f}MB)

📥 **直接下载链接**:
`{download_url}`

🔧 **其他解决方案**:
1. **配置 Pyrofork**: 支持最大 2GB 文件
   • 获取 API 凭据: https://my.telegram.org
   • 在网页管理界面配置 API ID 和 API Hash

2. **使用文件管理**:
   • 发送 `/files` 查看所有文件
   • 发送 `/send {filename}` 尝试发送

💡 **当前限制**: Bot API 最大 50MB，Client API 最大 2GB"""
                    else:
                        help_message = f"""{caption}

❌ **文件发送失败**

📥 **直接下载链接**:
`{download_url}`

💡 **提示**: 点击链接直接下载文件到您的设备"""

                    notifier.send_message(help_message)
            finally:
                # 清理上传状态
                with notifier._lock:
                    notifier._active_downloads.pop(upload_key, None)
        else:
            notifier.send_message(caption)

        # 清理跟踪记录
        with notifier._lock:
            notifier._active_downloads.pop(download_id, None)
            notifier._progress_messages.pop(download_id, None)

    except Exception as e:
        logger.error(f"❌ 处理下载完成事件失败: {e}")


def _get_web_panel_url() -> str:
    """获取Web面板URL"""
    import os

    # 优先使用环境变量
    web_url = os.getenv('SERVER_URL', '')

    if not web_url or web_url == 'http://localhost:8090':
        try:
            # 尝试从Flask请求中获取
            from flask import request
            if request:
                web_url = request.url_root.rstrip('/')
        except:
            # 如果Flask不可用，使用默认值
            web_url = 'http://localhost:8090'

    return web_url


@on(Events.DOWNLOAD_FAILED)
def handle_download_failed(data):
    """处理下载失败事件"""
    try:
        # 检查数据有效性
        if not data or not isinstance(data, dict):
            logger.warning(f"📡 收到无效的下载失败事件数据: {data}")
            return

        download_id = data.get('download_id')
        error = data.get('error', 'Unknown error')
        title = data.get('title', 'Unknown')
        url = data.get('url', '')

        # 验证必需字段
        if not download_id:
            logger.warning(f"📡 下载失败事件缺少download_id: {data}")
            return

        # 提前检查 Telegram 是否启用
        notifier = get_telegram_notifier()
        if not notifier or not notifier.is_enabled():
            logger.debug(f"📡 Telegram 未启用，跳过下载失败事件: {download_id}")
            return

        logger.info(f"📡 收到下载失败事件: {url}")

        # 发送详细的失败通知 - 安全的消息格式
        # 清理标题和URL中的特殊字符
        safe_title = str(title)[:50].replace('*', '').replace('_', '').replace('[', '').replace(']', '')
        safe_url = str(url)[:50].replace('*', '').replace('_', '').replace('[', '').replace(']', '')
        safe_error = str(error)[:100].replace('*', '').replace('_', '').replace('[', '').replace(']', '')

        message = f"""❌ 下载失败

📹 标题: {safe_title}
🔗 链接: {safe_url}...
🔍 错误: {safe_error}

💡 建议:
• 检查链接是否有效
• 稍后重试
• 联系管理员"""

        notifier.send_message(message)

        # 清理跟踪记录
        with notifier._lock:
            notifier._active_downloads.pop(download_id, None)
            notifier._progress_messages.pop(download_id, None)

    except Exception as e:
        logger.error(f"❌ 处理下载失败事件失败: {e}")


def _generate_progress_bar(progress: int, length: int = 20) -> str:
    """生成现代化进度条"""
    filled = int(length * progress / 100)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {progress}%"


# 模块加载时的日志
logger.info("🔧 现代化 Telegram 事件监听器已注册")
