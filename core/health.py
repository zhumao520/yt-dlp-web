# -*- coding: utf-8 -*-
"""
健康检查模块 - 系统状态监控
"""

import logging
import time
import psutil
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        try:
            health_data = {
                "status": "healthy",
                "timestamp": int(time.time()),
                "uptime": int(time.time() - self.start_time),
                "checks": {}
            }
            
            # 数据库检查
            health_data["checks"]["database"] = self._check_database()
            
            # yt-dlp检查
            health_data["checks"]["ytdlp"] = self._check_ytdlp()
            
            # 磁盘空间检查
            health_data["checks"]["disk_space"] = self._check_disk_space()
            
            # 内存使用检查
            health_data["checks"]["memory"] = self._check_memory()
            
            # 下载目录检查
            health_data["checks"]["download_dir"] = self._check_download_dir()
            
            # 确定整体状态
            failed_checks = [name for name, check in health_data["checks"].items() 
                           if not check.get("healthy", False)]
            
            if failed_checks:
                health_data["status"] = "degraded" if len(failed_checks) <= 2 else "unhealthy"
                health_data["failed_checks"] = failed_checks
            
            return health_data
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return {
                "status": "unhealthy",
                "timestamp": int(time.time()),
                "error": str(e)
            }
    
    def _check_database(self) -> Dict[str, Any]:
        """检查数据库连接"""
        try:
            from .database import get_database
            db = get_database()
            db.execute_query('SELECT 1')
            return {
                "healthy": True,
                "message": "数据库连接正常"
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"数据库连接失败: {e}"
            }
    
    def _check_ytdlp(self) -> Dict[str, Any]:
        """检查yt-dlp可用性"""
        try:
            import yt_dlp
            return {
                "healthy": True,
                "message": f"yt-dlp可用，版本: {yt_dlp.version.__version__}",
                "version": yt_dlp.version.__version__
            }
        except ImportError:
            return {
                "healthy": False,
                "message": "yt-dlp未安装或不可用"
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"yt-dlp检查失败: {e}"
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """检查磁盘空间"""
        try:
            # 使用更简单的方法检查磁盘空间
            import shutil
            from .config import get_config
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

            if download_dir.exists():
                total, used, free = shutil.disk_usage(str(download_dir))
                free_gb = free / (1024**3)
                total_gb = total / (1024**3)
                used_percent = (used / total) * 100

                # 如果可用空间少于1GB或使用率超过95%，认为不健康
                healthy = free_gb > 1.0 and used_percent < 95.0

                return {
                    "healthy": healthy,
                    "message": f"磁盘空间: {free_gb:.1f}GB可用 / {total_gb:.1f}GB总计 ({used_percent:.1f}%已用)",
                    "free_gb": round(free_gb, 1),
                    "total_gb": round(total_gb, 1),
                    "used_percent": round(used_percent, 1)
                }
            else:
                return {
                    "healthy": False,
                    "message": f"下载目录不存在: {download_dir}"
                }

        except Exception as e:
            return {
                "healthy": False,
                "message": f"磁盘空间检查失败: {e}"
            }
    
    def _check_memory(self) -> Dict[str, Any]:
        """检查内存使用"""
        try:
            # 使用psutil检查内存，如果失败则跳过
            try:
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                available_gb = memory.available / (1024**3)

                # 如果内存使用率超过90%或可用内存少于500MB，认为不健康
                healthy = memory_percent < 90.0 and available_gb > 0.5

                return {
                    "healthy": healthy,
                    "message": f"内存使用: {memory_percent:.1f}% ({available_gb:.1f}GB可用)",
                    "used_percent": round(memory_percent, 1),
                    "available_gb": round(available_gb, 1)
                }
            except:
                # 如果psutil不可用，返回基本信息
                return {
                    "healthy": True,
                    "message": "内存检查不可用（psutil未安装）"
                }

        except Exception as e:
            return {
                "healthy": False,
                "message": f"内存检查失败: {e}"
            }
    
    def _check_download_dir(self) -> Dict[str, Any]:
        """检查下载目录"""
        try:
            from .config import get_config
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
            
            if not download_dir.exists():
                download_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查目录是否可写
            test_file = download_dir / '.health_check'
            try:
                test_file.write_text('test')
                test_file.unlink()
                writable = True
            except:
                writable = False
            
            return {
                "healthy": download_dir.exists() and writable,
                "message": f"下载目录: {download_dir} ({'可写' if writable else '不可写'})",
                "path": str(download_dir),
                "writable": writable
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "message": f"下载目录检查失败: {e}"
            }


# 全局健康检查器实例
_health_checker = None

def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
