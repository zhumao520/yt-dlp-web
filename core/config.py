# -*- coding: utf-8 -*-
"""
配置管理 - 统一配置中心
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Config:
    """统一配置管理器"""
    
    _instance = None
    _config = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.load_config()
    
    def load_config(self):
        """加载配置"""
        try:
            # 默认配置
            self._config = self._get_default_config()
            
            # 加载配置文件
            config_file = self._find_config_file()
            if config_file and config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                self._merge_config(file_config)
                logger.info(f"✅ 配置文件加载成功: {config_file}")
            
            # 环境变量覆盖
            self._load_env_config()



            logger.info("✅ 配置加载完成")
            
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {e}")
            # 使用默认配置继续运行
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "app": {
                "name": "YT-DLP Web",
                "version": "2.0.0",
                "host": "0.0.0.0",
                "port": 8080,
                "debug": False,
                "secret_key": "change-this-secret-key-in-production",
            },
            "database": {"url": "sqlite:///app.db", "echo": False},
            "auth": {
                "session_timeout": 86400,  # 24小时
                "default_username": "admin",
                "default_password": "admin123",
            },
            "downloader": {
                "output_dir": "/app/downloads",
                "temp_dir": "/app/temp",
                "max_concurrent": 3,
                "timeout": 300,
                "auto_cleanup": True,
                "cleanup_interval": 3600,  # 1小时
                "max_file_age": 86400,  # 24小时
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
                "api_id": None,
                "api_hash": "",
                "push_mode": "file",  # file, notification, both
                "file_size_limit": 50,  # MB
            },
            "ytdlp": {
                "auto_update": True,
                "source": "github",  # github, pypi, local
                "version": "latest",
                "extract_flat": False,
                "format": "best[height<=720]",
            },

            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "/app/logs/app.log",
                "max_size": 10485760,  # 10MB
                "backup_count": 5,
            },
            "features": {
                "ai_analysis": False,  # 预留AI分析功能
                "cloud_storage": False,  # 预留云存储功能
                "multi_user": False,  # 预留多用户功能
                "monitoring": False,  # 预留监控功能
                "plugins": False,  # 预留插件系统
            },
        }
    
    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        possible_paths = [
            Path("config.yml"),
            Path("config.yaml"),
            Path("/app/config.yml"),
            Path("/app/config.yaml"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def _merge_config(self, new_config: Dict[str, Any]):
        """合并配置"""
        def merge_dict(base: dict, update: dict):
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
        
        merge_dict(self._config, new_config)
    
    def _load_env_config(self):
        """从环境变量加载配置"""
        env_mappings = {
            "APP_HOST": ("app", "host"),
            "APP_PORT": ("app", "port"),
            "APP_DEBUG": ("app", "debug"),
            "SECRET_KEY": ("app", "secret_key"),
            "DATABASE_URL": ("database", "url"),
            "DOWNLOAD_DIR": ("downloader", "output_dir"),
            "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
            "TELEGRAM_CHAT_ID": ("telegram", "chat_id"),
            "TELEGRAM_API_ID": ("telegram", "api_id"),
            "TELEGRAM_API_HASH": ("telegram", "api_hash"),

        }
        
        for env_key, (section, key) in env_mappings.items():
            value = os.environ.get(env_key)
            if value is not None:
                # 类型转换
                if key in ["port", "session_timeout", "max_concurrent", "api_id"]:
                    try:
                        value = int(value)
                    except ValueError:
                        continue
                elif key in ["debug", "enabled", "auto_cleanup"]:
                    value = value.lower() in ("true", "1", "yes", "on")
                
                if section not in self._config:
                    self._config[section] = {}
                self._config[section][key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值（支持点号分隔的路径）"""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value


    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段"""
        return self._config.get(section, {})

    def is_enabled(self, feature: str) -> bool:
        """检查功能是否启用"""
        return self.get(f"features.{feature}", False)
    
    def to_dict(self) -> Dict[str, Any]:
        """返回完整配置字典"""
        return self._config.copy()




# 全局配置实例
config = Config()


def get_config(key: str = None, default: Any = None) -> Any:
    """获取配置的便捷函数"""
    if key is None:
        return config.to_dict()
    return config.get(key, default)


def set_config(key: str, value: Any):
    """设置配置的便捷函数"""
    config.set(key, value)


def is_feature_enabled(feature: str) -> bool:
    """检查功能是否启用的便捷函数"""
    return config.is_enabled(feature)
