# -*- coding: utf-8 -*-
"""
日志配置模块 - 统一日志管理
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


class LoggingConfig:
    """日志配置管理器"""
    
    def __init__(self):
        self.log_dir = Path("data/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def setup_logging(self, 
                     level: str = "INFO",
                     log_file: Optional[str] = None,
                     max_size: int = 10 * 1024 * 1024,  # 10MB
                     backup_count: int = 5,
                     console_output: bool = True) -> None:
        """设置日志配置"""
        
        # 清除现有的处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 设置日志级别
        log_level = getattr(logging, level.upper(), logging.INFO)
        root_logger.setLevel(log_level)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 文件处理器
        if log_file:
            log_path = self.log_dir / log_file
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        
        # 设置第三方库的日志级别
        self._configure_third_party_loggers()
        
        logging.info(f"日志系统初始化完成 - 级别: {level}, 文件: {log_file}")
    
    def _configure_third_party_loggers(self):
        """配置第三方库的日志级别"""
        # 设置第三方库日志级别，避免过多输出
        third_party_loggers = {
            'urllib3': logging.WARNING,
            'requests': logging.WARNING,
            'werkzeug': logging.WARNING,
            'pyrogram': logging.WARNING,
            'yt_dlp': logging.WARNING,
        }
        
        for logger_name, level in third_party_loggers.items():
            logging.getLogger(logger_name).setLevel(level)
    
    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器"""
        return logging.getLogger(name)


# 全局日志配置实例
_logging_config = None

def get_logging_config() -> LoggingConfig:
    """获取日志配置实例"""
    global _logging_config
    if _logging_config is None:
        _logging_config = LoggingConfig()
    return _logging_config

def setup_application_logging():
    """设置应用日志"""
    try:
        # 从环境变量或配置文件获取日志配置
        log_level = os.environ.get('LOG_LEVEL', 'INFO')
        log_file = os.environ.get('LOG_FILE', 'app.log')
        
        # 在容器环境中可能不需要文件日志
        is_container = os.environ.get('DOCKER_CONTAINER') or os.path.exists('/.dockerenv')
        use_file_logging = not is_container or os.environ.get('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
        
        logging_config = get_logging_config()
        logging_config.setup_logging(
            level=log_level,
            log_file=log_file if use_file_logging else None,
            console_output=True
        )
        
        return True
        
    except Exception as e:
        # 如果日志配置失败，使用基本配置
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.error(f"日志配置失败，使用基本配置: {e}")
        return False
