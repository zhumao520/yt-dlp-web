# -*- coding: utf-8 -*-
"""
Telegram上传器模块
"""

from .bot_api import BotAPIUploader
from .pyrofork_uploader import PyroForkUploader
from .modern_hybrid import ModernHybridUploader

# 保持向后兼容性的导入
try:
    from .pyrogram import PyrogramUploader
    from .hybrid import HybridUploader, create_uploader
    _legacy_available = True
except ImportError:
    # 如果旧模块不存在，创建兼容性别名
    PyrogramUploader = PyroForkUploader
    HybridUploader = ModernHybridUploader
    _legacy_available = False

    def create_uploader(config):
        """兼容性上传器创建函数"""
        return ModernHybridUploader(config)

__all__ = [
    'BotAPIUploader',
    'PyrogramUploader',
    'HybridUploader',
    'PyroForkUploader',
    'ModernHybridUploader',
    'create_uploader'
]
