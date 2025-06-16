# -*- coding: utf-8 -*-
"""
Telegram模块 - 现代化统一入口
支持智能上传、事件驱动、命令处理等完整功能
"""

from .notifier import get_telegram_notifier
from .modern_routes import get_modern_telegram_router
from .services.modern_command_service import ModernTelegramCommandService

__all__ = [
    'get_telegram_notifier',
    'get_modern_telegram_router',
    'ModernTelegramCommandService'
]
