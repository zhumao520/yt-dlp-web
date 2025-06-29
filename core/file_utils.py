"""
统一的文件工具类 - 消除重复的文件操作代码
"""

import os
import logging
from pathlib import Path
from typing import Union, Optional, Dict, Any

logger = logging.getLogger(__name__)


class PathUtils:
    """统一的路径处理工具类"""

    @staticmethod
    def normalize_path(path: Union[str, Path]) -> Path:
        """标准化路径 - 跨平台兼容"""
        try:
            path_obj = Path(path)
            # 解析相对路径和符号链接
            return path_obj.resolve()
        except Exception as e:
            logger.debug(f"路径标准化失败 {path}: {e}")
            return Path(path)

    @staticmethod
    def ensure_path_exists(path: Union[str, Path], is_file: bool = False) -> Path:
        """确保路径存在，如果不存在则创建"""
        path_obj = PathUtils.normalize_path(path)

        try:
            if is_file:
                # 如果是文件路径，确保父目录存在
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            else:
                # 如果是目录路径，确保目录存在
                path_obj.mkdir(parents=True, exist_ok=True)

            return path_obj
        except Exception as e:
            logger.error(f"创建路径失败 {path}: {e}")
            raise

    @staticmethod
    def safe_join(*paths) -> Path:
        """安全的路径拼接 - 防止路径遍历攻击"""
        try:
            # 使用 pathlib 进行安全拼接
            result = Path()
            for path in paths:
                if path:
                    # 移除可能的路径遍历字符
                    clean_path = str(path).replace('..', '').replace('//', '/')
                    result = result / clean_path

            return PathUtils.normalize_path(result)
        except Exception as e:
            logger.error(f"路径拼接失败 {paths}: {e}")
            raise

    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Path:
        """获取相对路径"""
        try:
            path_obj = PathUtils.normalize_path(path)
            base_obj = PathUtils.normalize_path(base)
            return path_obj.relative_to(base_obj)
        except Exception as e:
            logger.debug(f"获取相对路径失败 {path} -> {base}: {e}")
            return Path(path)

    @staticmethod
    def is_safe_path(path: Union[str, Path], base_dir: Union[str, Path]) -> bool:
        """检查路径是否安全（在指定目录内）"""
        try:
            path_obj = PathUtils.normalize_path(path)
            base_obj = PathUtils.normalize_path(base_dir)

            # 检查路径是否在基础目录内
            try:
                path_obj.relative_to(base_obj)
                return True
            except ValueError:
                return False

        except Exception as e:
            logger.debug(f"路径安全检查失败 {path}: {e}")
            return False


class FileUtils:
    """统一的文件工具类"""
    
    @staticmethod
    def get_file_size(file_path: Union[str, Path]) -> int:
        """获取文件大小（字节）- 统一方法"""
        try:
            path_obj = Path(file_path)
            if path_obj.exists() and path_obj.is_file():
                return path_obj.stat().st_size
            return 0
        except Exception as e:
            logger.debug(f"⚠️ 获取文件大小失败 {file_path}: {e}")
            return 0
    
    @staticmethod
    def get_file_size_mb(file_path: Union[str, Path]) -> float:
        """获取文件大小（MB）- 统一方法"""
        size_bytes = FileUtils.get_file_size(file_path)
        return size_bytes / (1024 * 1024)
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小 - 统一方法"""
        if size_bytes == 0:
            return "0B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        
        for unit in units:
            if size < 1024.0:
                if unit == 'B':
                    return f"{int(size)}{unit}"
                else:
                    return f"{size:.1f}{unit}"
            size /= 1024.0
        
        return f"{size:.1f}PB"
    
    @staticmethod
    def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
        """获取文件完整信息 - 统一方法"""
        try:
            path_obj = Path(file_path)
            
            if not path_obj.exists():
                return {
                    'exists': False,
                    'size': 0,
                    'size_mb': 0.0,
                    'size_formatted': '0B',
                    'name': path_obj.name,
                    'path': str(path_obj)
                }
            
            size_bytes = path_obj.stat().st_size
            
            return {
                'exists': True,
                'size': size_bytes,
                'size_mb': size_bytes / (1024 * 1024),
                'size_formatted': FileUtils.format_file_size(size_bytes),
                'name': path_obj.name,
                'path': str(path_obj.absolute()),
                'is_file': path_obj.is_file(),
                'is_dir': path_obj.is_dir()
            }
            
        except Exception as e:
            logger.debug(f"⚠️ 获取文件信息失败 {file_path}: {e}")
            return {
                'exists': False,
                'size': 0,
                'size_mb': 0.0,
                'size_formatted': '0B',
                'name': Path(file_path).name,
                'path': str(file_path),
                'error': str(e)
            }
    
    @staticmethod
    def wait_for_file_stable(file_path: Union[str, Path], 
                           max_wait: int = 10, 
                           check_interval: float = 0.5) -> bool:
        """等待文件大小稳定 - 统一方法"""
        try:
            import time
            
            path_obj = Path(file_path)
            last_size = -1
            stable_count = 0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                if not path_obj.exists():
                    time.sleep(check_interval)
                    continue
                
                current_size = FileUtils.get_file_size(path_obj)
                
                if current_size == last_size and current_size > 0:
                    stable_count += 1
                    if stable_count >= 3:  # 连续3次大小相同
                        logger.debug(f"✅ 文件大小稳定: {path_obj.name} ({current_size} bytes)")
                        return True
                else:
                    stable_count = 0
                    last_size = current_size
                
                time.sleep(check_interval)
            
            logger.debug(f"⚠️ 文件大小稳定检查超时: {path_obj.name}")
            return False
            
        except Exception as e:
            logger.debug(f"⚠️ 文件稳定检查失败 {file_path}: {e}")
            return False
    
    @staticmethod
    def get_directory_size(dir_path: Union[str, Path]) -> int:
        """获取目录大小 - 统一方法"""
        try:
            path_obj = Path(dir_path)
            if not path_obj.exists() or not path_obj.is_dir():
                return 0
            
            total_size = 0
            for file_path in path_obj.rglob('*'):
                if file_path.is_file():
                    total_size += FileUtils.get_file_size(file_path)
            
            return total_size
            
        except Exception as e:
            logger.debug(f"⚠️ 获取目录大小失败 {dir_path}: {e}")
            return 0
    
    @staticmethod
    def safe_file_operation(operation_func, *args, **kwargs):
        """安全的文件操作包装器 - 统一错误处理"""
        try:
            return operation_func(*args, **kwargs)
        except PermissionError as e:
            logger.error(f"❌ 文件权限错误: {e}")
            return None
        except FileNotFoundError as e:
            logger.error(f"❌ 文件未找到: {e}")
            return None
        except OSError as e:
            logger.error(f"❌ 文件系统错误: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 文件操作失败: {e}")
            return None


class ProgressUtils:
    """统一的进度处理工具类"""
    
    @staticmethod
    def calculate_progress(current: int, total: int) -> int:
        """计算进度百分比 - 统一方法"""
        if total <= 0:
            return 0
        return max(0, min(100, int((current / total) * 100)))
    
    @staticmethod
    def format_progress_data(current: int, total: int, status: str = "downloading") -> Dict[str, Any]:
        """格式化进度数据 - 统一格式"""
        return {
            'status': status,
            'downloaded_bytes': max(0, current),
            'total_bytes': max(0, total),
            'progress_percent': ProgressUtils.calculate_progress(current, total)
        }
    
    @staticmethod
    def safe_progress_callback(callback, progress_data: Dict[str, Any]):
        """安全的进度回调 - 统一错误处理"""
        if not callback:
            return
        
        try:
            callback(progress_data)
        except Exception as e:
            logger.debug(f"⚠️ 进度回调失败: {e}")


class ChunkUtils:
    """统一的文件块处理工具类"""
    
    @staticmethod
    def calculate_optimal_chunk_size(file_size: int) -> int:
        """计算最优块大小 - 统一逻辑"""
        if file_size > 500 * 1024 * 1024:  # 500MB+
            return 2 * 1024 * 1024  # 2MB chunks
        elif file_size > 100 * 1024 * 1024:  # 100MB+
            return 1024 * 1024  # 1MB chunks
        else:
            return 512 * 1024  # 512KB chunks
    
    @staticmethod
    def generate_file_chunks(file_path: Union[str, Path], chunk_size: Optional[int] = None):
        """生成文件块 - 统一方法"""
        try:
            path_obj = Path(file_path)
            file_size = FileUtils.get_file_size(path_obj)
            
            if chunk_size is None:
                chunk_size = ChunkUtils.calculate_optimal_chunk_size(file_size)
            
            logger.debug(f"文件块传输: {FileUtils.format_file_size(file_size)}, 块大小: {FileUtils.format_file_size(chunk_size)}")
            
            with open(path_obj, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    
        except Exception as e:
            logger.error(f"❌ 文件块生成失败 {file_path}: {e}")
            raise


# 便捷函数
def get_file_size(file_path: Union[str, Path]) -> int:
    """便捷函数：获取文件大小"""
    return FileUtils.get_file_size(file_path)


def get_file_size_mb(file_path: Union[str, Path]) -> float:
    """便捷函数：获取文件大小（MB）"""
    return FileUtils.get_file_size_mb(file_path)


def format_file_size(size_bytes: int) -> str:
    """便捷函数：格式化文件大小"""
    return FileUtils.format_file_size(size_bytes)


def calculate_progress(current: int, total: int) -> int:
    """便捷函数：计算进度"""
    return ProgressUtils.calculate_progress(current, total)
