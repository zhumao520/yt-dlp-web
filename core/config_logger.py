#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置日志工具
提供统一的配置来源日志记录功能
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfigLogger:
    """配置日志记录器"""
    
    @staticmethod
    def get_config_with_log(key: str, default: Any = None, module_name: str = "系统") -> Any:
        """
        获取配置并记录来源
        
        Args:
            key: 配置键
            default: 默认值
            module_name: 模块名称（用于日志标识）
        
        Returns:
            配置值
        """
        try:
            # 1. 检查环境变量
            env_value = ConfigLogger._get_from_env(key)
            if env_value is not None:
                logger.info(f"🔧 {module_name}配置: {key} = {env_value} (来源: 环境变量)")
                return ConfigLogger._convert_type(env_value, type(default) if default is not None else str)
            
            # 2. 检查数据库设置
            db_value = ConfigLogger._get_from_database(key)
            if db_value is not None:
                logger.info(f"🔧 {module_name}配置: {key} = {db_value} (来源: 数据库)")
                return ConfigLogger._convert_type(db_value, type(default) if default is not None else type(db_value))
            
            # 3. 检查配置文件
            config_value = ConfigLogger._get_from_config_file(key)
            if config_value is not None:
                logger.info(f"🔧 {module_name}配置: {key} = {config_value} (来源: 配置文件)")
                return config_value
            
            # 4. 使用默认值
            logger.info(f"🔧 {module_name}配置: {key} = {default} (来源: 默认值)")
            return default
            
        except Exception as e:
            logger.warning(f"⚠️ {module_name}配置获取失败 {key}: {e}")
            return default
    
    @staticmethod
    def _get_from_env(key: str) -> Optional[str]:
        """从环境变量获取值"""
        try:
            import os
            # 转换配置键为环境变量名
            env_key = key.upper().replace('.', '_')
            return os.environ.get(env_key)
        except:
            return None
    
    @staticmethod
    def _get_from_database(key: str) -> Optional[Any]:
        """从数据库获取值"""
        try:
            from core.database import get_database
            db = get_database()
            return db.get_setting(key)
        except:
            return None
    
    @staticmethod
    def _get_from_config_file(key: str) -> Optional[Any]:
        """从配置文件获取值"""
        try:
            from core.config import get_config
            return get_config(key, None)
        except:
            return None
    
    @staticmethod
    def _convert_type(value: Any, target_type: type) -> Any:
        """类型转换"""
        try:
            if target_type == bool:
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif target_type == int:
                return int(value)
            elif target_type == float:
                return float(value)
            else:
                return value
        except:
            return value
    
    @staticmethod
    def log_config_summary(configs: dict, module_name: str = "系统"):
        """记录配置摘要"""
        logger.info(f"📋 {module_name}配置摘要:")
        for key, value in configs.items():
            # 隐藏敏感信息
            if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                display_value = "***" if value else "未设置"
            else:
                display_value = value
            logger.info(f"   {key}: {display_value}")
    
    @staticmethod
    def get_config_source(key: str) -> str:
        """获取配置值的来源"""
        if ConfigLogger._get_from_env(key) is not None:
            return "环境变量"
        elif ConfigLogger._get_from_database(key) is not None:
            return "数据库"
        elif ConfigLogger._get_from_config_file(key) is not None:
            return "配置文件"
        else:
            return "默认值"


# 便捷函数
def get_config_with_log(key: str, default: Any = None, module_name: str = "系统") -> Any:
    """便捷的配置获取函数"""
    return ConfigLogger.get_config_with_log(key, default, module_name)


def log_config_summary(configs: dict, module_name: str = "系统"):
    """便捷的配置摘要记录函数"""
    ConfigLogger.log_config_summary(configs, module_name)


def get_config_source(key: str) -> str:
    """便捷的配置来源获取函数"""
    return ConfigLogger.get_config_source(key)
