# -*- coding: utf-8 -*-
"""
核心模块 - 提供基础功能和框架
"""

from .app import create_app
from .config import Config, get_config, set_config
from .events import EventBus, emit, emit_async, on, Events
from .database import Database, get_database
from .auth import AuthManager, get_auth_manager, auth_required, admin_required

__all__ = [
    "create_app",
    "Config",
    "get_config",
    "set_config",
    "EventBus",
    "emit",
    "emit_async",
    "on",
    "Events",
    "Database",
    "get_database",
    "AuthManager",
    "get_auth_manager",
    "auth_required",
    "admin_required",
]
