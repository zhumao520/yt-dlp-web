"""
路径常量管理 - 解决硬编码和跨平台兼容性问题
"""

from pathlib import Path
from typing import Dict, Any
import os

class PathConstants:
    """路径常量管理器 - 统一管理所有路径配置"""
    
    # 基础目录常量
    BASE_DATA_DIR = "data"
    
    # 子目录常量
    DOWNLOADS_SUBDIR = "downloads"
    TEMP_SUBDIR = "temp"
    LOGS_SUBDIR = "logs"
    COOKIES_SUBDIR = "cookies"
    DATABASE_SUBDIR = "database"
    
    # 完整路径常量（使用pathlib确保跨平台兼容）
    @classmethod
    def get_data_dir(cls) -> Path:
        """获取数据目录路径"""
        return Path(cls.BASE_DATA_DIR)
    
    @classmethod
    def get_downloads_dir(cls) -> Path:
        """获取下载目录路径"""
        return cls.get_data_dir() / cls.DOWNLOADS_SUBDIR
    
    @classmethod
    def get_temp_dir(cls) -> Path:
        """获取临时目录路径"""
        return cls.get_data_dir() / cls.TEMP_SUBDIR
    
    @classmethod
    def get_logs_dir(cls) -> Path:
        """获取日志目录路径"""
        return cls.get_data_dir() / cls.LOGS_SUBDIR
    
    @classmethod
    def get_cookies_dir(cls) -> Path:
        """获取cookies目录路径"""
        return cls.get_data_dir() / cls.COOKIES_SUBDIR
    
    @classmethod
    def get_database_dir(cls) -> Path:
        """获取数据库目录路径"""
        return cls.get_data_dir() / cls.DATABASE_SUBDIR
    
    @classmethod
    def get_default_paths(cls) -> Dict[str, str]:
        """获取默认路径配置字典（用于配置系统）"""
        return {
            'downloader.output_dir': str(cls.get_downloads_dir()),
            'downloader.temp_dir': str(cls.get_temp_dir()),
            'logging.log_dir': str(cls.get_logs_dir()),
            'cookies.storage_dir': str(cls.get_cookies_dir()),
            'database.data_dir': str(cls.get_database_dir()),
        }
    
    @classmethod
    def ensure_directories_exist(cls) -> None:
        """确保所有必要目录存在"""
        directories = [
            cls.get_data_dir(),
            cls.get_downloads_dir(),
            cls.get_temp_dir(),
            cls.get_logs_dir(),
            cls.get_cookies_dir(),
            cls.get_database_dir(),
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                # 使用print而不是logger避免循环依赖
                print(f"警告: 无法创建目录 {directory}: {e}")
    
    @classmethod
    def get_absolute_path(cls, relative_path: Path) -> Path:
        """将相对路径转换为绝对路径"""
        if relative_path.is_absolute():
            return relative_path
        return Path.cwd() / relative_path
    
    @classmethod
    def normalize_path(cls, path_str: str) -> Path:
        """规范化路径字符串为Path对象"""
        # 处理用户目录展开
        if path_str.startswith('~'):
            path = Path(path_str).expanduser()
        else:
            path = Path(path_str)

        # 如果是相对路径，转换为绝对路径
        if not path.is_absolute():
            path = Path.cwd() / path

        # 解析符号链接和相对路径组件
        try:
            path = path.resolve()
        except (OSError, RuntimeError):
            # 如果resolve失败，至少确保路径是绝对的
            pass

        return path

class DefaultPaths:
    """默认路径提供器 - 为向后兼容性提供字符串路径"""
    
    @staticmethod
    def get_downloads_dir_str() -> str:
        """获取下载目录字符串（向后兼容）"""
        return str(PathConstants.get_downloads_dir())
    
    @staticmethod
    def get_temp_dir_str() -> str:
        """获取临时目录字符串（向后兼容）"""
        return str(PathConstants.get_temp_dir())
    
    @staticmethod
    def get_logs_dir_str() -> str:
        """获取日志目录字符串（向后兼容）"""
        return str(PathConstants.get_logs_dir())
    
    @staticmethod
    def get_cookies_dir_str() -> str:
        """获取cookies目录字符串（向后兼容）"""
        return str(PathConstants.get_cookies_dir())

# 便捷函数
def get_default_download_dir() -> str:
    """获取默认下载目录（字符串格式）"""
    return DefaultPaths.get_downloads_dir_str()

def get_default_temp_dir() -> str:
    """获取默认临时目录（字符串格式）"""
    return DefaultPaths.get_temp_dir_str()

def get_default_logs_dir() -> str:
    """获取默认日志目录（字符串格式）"""
    return DefaultPaths.get_logs_dir_str()

def get_default_cookies_dir() -> str:
    """获取默认cookies目录（字符串格式）"""
    return DefaultPaths.get_cookies_dir_str()

# 初始化时确保目录存在
try:
    PathConstants.ensure_directories_exist()
except Exception as e:
    print(f"警告: 路径常量初始化时出错: {e}")

# 导出主要接口
__all__ = [
    'PathConstants',
    'DefaultPaths', 
    'get_default_download_dir',
    'get_default_temp_dir',
    'get_default_logs_dir',
    'get_default_cookies_dir',
]
