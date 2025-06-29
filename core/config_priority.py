"""
统一的配置优先级管理器
解决配置优先级混乱问题

优先级顺序（从高到低）：
1. 环境变量 (最高优先级)
2. 数据库设置 (用户运行时设置)
3. 配置文件 (config.yml)
4. 默认值 (最低优先级)
"""

import os
import logging
from typing import Any, Optional, Union, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigPriorityManager:
    """统一的配置优先级管理器"""
    
    def __init__(self):
        self._cache = {}
        self._cache_enabled = True
    
    def get_value(self, key: str, default: Any = None, value_type: type = None) -> Any:
        """
        按优先级获取配置值
        
        Args:
            key: 配置键（支持点号分隔，如 'downloader.output_dir'）
            default: 默认值
            value_type: 期望的值类型（用于类型转换）
        
        Returns:
            配置值
        """
        # 检查缓存
        cache_key = f"{key}:{type(default).__name__}"
        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]
        
        # 按优先级顺序获取值
        value = None
        source = "default"
        
        # 1. 环境变量（最高优先级）
        env_value = self._get_from_env(key)
        if env_value is not None:
            value = env_value
            source = "environment"
        
        # 2. 数据库设置（用户运行时设置）
        elif self._get_from_database(key) is not None:
            value = self._get_from_database(key)
            source = "database"
        
        # 3. 配置文件
        elif self._get_from_config_file(key) is not None:
            value = self._get_from_config_file(key)
            source = "config_file"
        
        # 4. 默认值（最低优先级）
        else:
            value = default
            source = "default"
        
        # 类型转换
        if value is not None and value_type is not None:
            value = self._convert_type(value, value_type, key)
        elif value is not None and default is not None:
            # 根据默认值的类型进行转换
            value = self._convert_type(value, type(default), key)
        
        # 缓存结果
        if self._cache_enabled:
            self._cache[cache_key] = value
        
        logger.debug(f"🔧 配置获取: {key} = {value} (来源: {source})")
        return value
    
    def _get_from_env(self, key: str) -> Optional[str]:
        """从环境变量获取值"""
        try:
            # 转换配置键为环境变量名
            # 例如: downloader.output_dir -> DOWNLOADER_OUTPUT_DIR
            env_key = key.upper().replace('.', '_')
            
            # 也检查一些常见的环境变量别名
            env_aliases = {
                'app.host': 'HOST',
                'app.port': 'PORT',
                'app.debug': 'DEBUG',
                'app.secret_key': 'SECRET_KEY',
                'database.url': 'DATABASE_URL',
                'downloader.output_dir': 'DOWNLOAD_DIR',
                'telegram.bot_token': 'TELEGRAM_BOT_TOKEN',
                'telegram.chat_id': 'TELEGRAM_CHAT_ID',
                'telegram.api_id': 'TELEGRAM_API_ID',
                'telegram.api_hash': 'TELEGRAM_API_HASH',
            }
            
            # 先检查别名
            if key in env_aliases:
                alias_value = os.environ.get(env_aliases[key])
                if alias_value is not None:
                    return alias_value
            
            # 再检查标准格式
            return os.environ.get(env_key)
            
        except Exception as e:
            logger.debug(f"⚠️ 环境变量获取失败 {key}: {e}")
            return None
    
    def _get_from_database(self, key: str) -> Optional[Any]:
        """从数据库获取值"""
        try:
            from core.database import get_database
            db = get_database()
            return db.get_setting(key)
        except Exception as e:
            logger.debug(f"⚠️ 数据库设置获取失败 {key}: {e}")
            return None
    
    def _get_from_config_file(self, key: str) -> Optional[Any]:
        """从配置文件获取值"""
        try:
            from core.config import config
            return config.get(key)
        except Exception as e:
            logger.debug(f"⚠️ 配置文件获取失败 {key}: {e}")
            return None
    
    def _convert_type(self, value: Any, target_type: type, key: str) -> Any:
        """类型转换"""
        if value is None:
            return None
        
        try:
            # 如果已经是目标类型，直接返回
            if isinstance(value, target_type):
                return value
            
            # 字符串转换
            if isinstance(value, str):
                if target_type == bool:
                    return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
                elif target_type == int:
                    return int(value)
                elif target_type == float:
                    return float(value)
                elif target_type == Path:
                    return Path(value)
                elif target_type == str:
                    return value
            
            # 其他类型转换
            return target_type(value)
            
        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ 配置类型转换失败 {key}: {value} -> {target_type.__name__}: {e}")
            return value
    
    def set_database_value(self, key: str, value: Any) -> bool:
        """设置数据库值（用户运行时设置）"""
        try:
            from core.database import get_database
            db = get_database()
            db.set_setting(key, value)
            
            # 清除缓存
            self._clear_cache_for_key(key)
            
            logger.info(f"✅ 数据库设置更新: {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据库设置更新失败 {key}: {e}")
            return False
    
    def _clear_cache_for_key(self, key: str):
        """清除特定键的缓存"""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{key}:")]
        for k in keys_to_remove:
            del self._cache[k]
    
    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        logger.debug("🧹 配置缓存已清除")
    
    def get_config_source(self, key: str) -> str:
        """获取配置值的来源"""
        # 检查环境变量
        if self._get_from_env(key) is not None:
            return "environment"
        
        # 检查数据库
        if self._get_from_database(key) is not None:
            return "database"
        
        # 检查配置文件
        if self._get_from_config_file(key) is not None:
            return "config_file"
        
        return "default"
    
    def get_all_sources(self, key: str) -> Dict[str, Any]:
        """获取配置值在所有来源中的值"""
        return {
            'environment': self._get_from_env(key),
            'database': self._get_from_database(key),
            'config_file': self._get_from_config_file(key),
        }


# 全局实例
_priority_manager = ConfigPriorityManager()


def get_config_value(key: str, default: Any = None, value_type: type = None) -> Any:
    """
    统一的配置获取函数
    
    Args:
        key: 配置键
        default: 默认值
        value_type: 期望的值类型
    
    Returns:
        配置值
    """
    return _priority_manager.get_value(key, default, value_type)


def set_user_setting(key: str, value: Any) -> bool:
    """
    设置用户运行时设置（存储到数据库）
    
    Args:
        key: 配置键
        value: 配置值
    
    Returns:
        是否设置成功
    """
    return _priority_manager.set_database_value(key, value)


def get_config_source(key: str) -> str:
    """获取配置值的来源"""
    return _priority_manager.get_config_source(key)


def get_all_config_sources(key: str) -> Dict[str, Any]:
    """获取配置值在所有来源中的值"""
    return _priority_manager.get_all_sources(key)


def clear_config_cache():
    """清除配置缓存"""
    _priority_manager.clear_cache()


# 向后兼容的别名
get_setting = get_config_value
set_setting = set_user_setting
