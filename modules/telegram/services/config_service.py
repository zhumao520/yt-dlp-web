# -*- coding: utf-8 -*-
"""
Telegram配置服务 - 解耦配置访问逻辑
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TelegramConfigService:
    """Telegram配置服务 - 统一配置管理"""
    
    def __init__(self):
        self._config_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5分钟缓存
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """获取Telegram配置"""
        try:
            import time
            current_time = time.time()
            
            # 检查缓存是否有效
            if (self._config_cache is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                return self._config_cache
            
            # 从数据库获取配置
            from core.database import get_database
            db = get_database()
            config = db.get_telegram_config()
            
            # 更新缓存
            self._config_cache = config
            self._cache_timestamp = current_time
            
            return config
            
        except Exception as e:
            logger.error(f"❌ 获取Telegram配置失败: {e}")
            return None
    
    def is_enabled(self) -> bool:
        """检查Telegram是否启用"""
        config = self.get_config()
        if not config:
            return False
        
        return (config.get('enabled', False) and 
                config.get('bot_token') and 
                config.get('chat_id'))
    
    def get_bot_token(self) -> Optional[str]:
        """获取Bot Token"""
        config = self.get_config()
        return config.get('bot_token') if config else None
    
    def get_chat_id(self) -> Optional[str]:
        """获取Chat ID"""
        config = self.get_config()
        return config.get('chat_id') if config else None
    
    def get_push_mode(self) -> str:
        """获取推送模式"""
        config = self.get_config()
        return config.get('push_mode', 'file') if config else 'file'
    
    def get_file_size_limit(self) -> int:
        """获取文件大小限制"""
        config = self.get_config()
        return config.get('file_size_limit', 50) if config else 50
    
    def has_pyrogram_config(self) -> bool:
        """检查是否配置了Pyrogram"""
        config = self.get_config()
        if not config:
            return False
        
        return bool(config.get('api_id') and config.get('api_hash'))
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache = None
        self._cache_timestamp = 0
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, str]:
        """验证配置有效性"""
        errors = {}
        
        if not config.get('bot_token'):
            errors['bot_token'] = 'Bot Token不能为空'
        
        if not config.get('chat_id'):
            errors['chat_id'] = 'Chat ID不能为空'
        
        # 验证Chat ID格式
        chat_id = config.get('chat_id', '')
        if chat_id and not (chat_id.startswith('-') or chat_id.isdigit()):
            errors['chat_id'] = 'Chat ID格式无效'
        
        # 验证Pyrogram配置（如果提供）
        api_id = config.get('api_id')
        api_hash = config.get('api_hash')
        
        if api_id and not api_hash:
            errors['api_hash'] = '提供API ID时必须同时提供API Hash'
        elif api_hash and not api_id:
            errors['api_id'] = '提供API Hash时必须同时提供API ID'
        
        # 验证文件大小限制
        file_size_limit = config.get('file_size_limit', 50)
        if not isinstance(file_size_limit, (int, float)) or file_size_limit <= 0:
            errors['file_size_limit'] = '文件大小限制必须是正数'
        
        return errors


# 全局配置服务实例
_config_service = None

def get_telegram_config_service() -> TelegramConfigService:
    """获取Telegram配置服务实例"""
    global _config_service
    if _config_service is None:
        _config_service = TelegramConfigService()
    return _config_service
