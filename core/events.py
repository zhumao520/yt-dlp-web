# -*- coding: utf-8 -*-
"""
事件总线 - 轻量化事件驱动系统
"""

import logging
import threading
from typing import Dict, List, Callable, Any

logger = logging.getLogger(__name__)


class EventBus:
    """轻量化事件总线"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._listeners: Dict[str, List[Callable]] = {}
            self._lock = threading.RLock()

    def on(self, event_name: str):
        """装饰器：注册事件监听器"""
        def decorator(func: Callable):
            self.add_listener(event_name, func)
            return func
        return decorator

    def add_listener(self, event_name: str, callback: Callable):
        """添加事件监听器"""
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []

            # 防止重复注册同一个回调函数
            if callback not in self._listeners[event_name]:
                self._listeners[event_name].append(callback)
                logger.debug(f"📡 注册事件监听器: {event_name} -> {callback.__name__}")
            else:
                logger.debug(f"📡 监听器已存在，跳过注册: {event_name} -> {callback.__name__}")

    def emit(self, event_name: str, data: Any = None):
        """发送事件"""
        with self._lock:
            listeners = self._listeners.get(event_name, []).copy()

        if not listeners:
            logger.debug(f"📡 事件无监听器: {event_name}")
            return

        logger.debug(f"📡 发送事件: {event_name} -> {len(listeners)} 个监听器")

        for callback in listeners:
            try:
                if data is not None:
                    callback(data)
                else:
                    callback()
            except Exception as e:
                logger.error(f"❌ 事件处理器错误 {event_name}->{callback.__name__}: {e}")

    def emit_async(self, event_name: str, data: Any = None):
        """异步发送事件"""
        import threading
        thread = threading.Thread(
            target=self.emit,
            args=(event_name, data),
            daemon=True
        )
        thread.start()


# 全局事件总线实例
event_bus = EventBus()

# 便捷函数
def on(event_name: str):
    return event_bus.on(event_name)

def emit(event_name: str, data: Any = None):
    event_bus.emit(event_name, data)

def emit_async(event_name: str, data: Any = None):
    event_bus.emit_async(event_name, data)

# 预定义事件名称
class Events:
    """事件名称常量"""

    # 应用生命周期
    APP_STARTED = 'app.started'
    APP_SHUTDOWN = 'app.shutdown'

    # 用户认证
    USER_LOGIN = 'user.login'
    USER_LOGOUT = 'user.logout'

    # 下载相关
    DOWNLOAD_STARTED = 'download.started'
    DOWNLOAD_PROGRESS = 'download.progress'
    DOWNLOAD_COMPLETED = 'download.completed'
    DOWNLOAD_FAILED = 'download.failed'

    # 文件相关
    FILE_CREATED = 'file.created'
    FILE_DELETED = 'file.deleted'

    # Telegram相关
    TELEGRAM_MESSAGE_RECEIVED = 'telegram.message_received'
    TELEGRAM_FILE_SENT = 'telegram.file_sent'

    # 扩展接口（预留）
    AI_ANALYSIS_COMPLETED = 'ai.analysis_completed'
    CLOUD_UPLOAD_COMPLETED = 'cloud.upload_completed'
