# -*- coding: utf-8 -*-
"""
错误处理和恢复机制
"""

import logging
import traceback
import functools
from typing import Callable, Any, Optional, Dict
from flask import jsonify, request

logger = logging.getLogger(__name__)


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_counts = {}
        self.recovery_strategies = {}
    
    def register_recovery_strategy(self, error_type: type, strategy: Callable):
        """注册错误恢复策略"""
        self.recovery_strategies[error_type] = strategy
    
    def handle_error(self, error: Exception, context: str = "") -> Optional[Any]:
        """处理错误并尝试恢复"""
        error_type = type(error)
        error_key = f"{error_type.__name__}:{context}"
        
        # 记录错误次数
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 记录错误
        logger.error(f"❌ 错误发生 [{context}]: {error}")
        logger.error(f"详细信息: {traceback.format_exc()}")
        
        # 尝试恢复
        if error_type in self.recovery_strategies:
            try:
                logger.info(f"🔧 尝试错误恢复: {error_type.__name__}")
                result = self.recovery_strategies[error_type](error, context)
                if result is not None:
                    logger.info(f"✅ 错误恢复成功: {error_type.__name__}")
                    return result
            except Exception as recovery_error:
                logger.error(f"❌ 错误恢复失败: {recovery_error}")
        
        return None
    
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计"""
        return self.error_counts.copy()


# 全局错误处理器
_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """获取错误处理器实例"""
    return _error_handler


def safe_execute(context: str = "", default_return=None, log_errors: bool = True):
    """安全执行装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    error_handler = get_error_handler()
                    result = error_handler.handle_error(e, context or func.__name__)
                    if result is not None:
                        return result
                
                return default_return
        return wrapper
    return decorator


def api_error_handler(func: Callable) -> Callable:
    """API错误处理装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"⚠️ 参数错误 [{func.__name__}]: {e}")
            return jsonify({"error": f"参数错误: {str(e)}"}), 400
        except PermissionError as e:
            logger.warning(f"⚠️ 权限错误 [{func.__name__}]: {e}")
            return jsonify({"error": "权限不足"}), 403
        except FileNotFoundError as e:
            logger.warning(f"⚠️ 文件未找到 [{func.__name__}]: {e}")
            return jsonify({"error": "资源未找到"}), 404
        except Exception as e:
            logger.error(f"❌ API错误 [{func.__name__}]: {e}")
            logger.error(f"详细信息: {traceback.format_exc()}")
            
            # 在调试模式下返回详细错误信息
            from core.config import get_config
            if get_config('app.debug', False):
                return jsonify({
                    "error": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }), 500
            else:
                return jsonify({"error": "内部服务器错误"}), 500
    
    return wrapper


def database_recovery_strategy(error: Exception, context: str) -> Optional[Any]:
    """数据库错误恢复策略"""
    try:
        import sqlite3
        if isinstance(error, sqlite3.OperationalError):
            if "database is locked" in str(error):
                logger.info("🔧 尝试解决数据库锁定问题...")
                import time
                time.sleep(0.1)  # 短暂等待
                return "retry"
            elif "no such table" in str(error):
                logger.info("🔧 尝试重新初始化数据库...")
                from .database import get_database
                db = get_database()
                db._initialize_database()
                return "recovered"
    except Exception as e:
        logger.error(f"数据库恢复策略失败: {e}")
    
    return None


def download_recovery_strategy(error: Exception, context: str) -> Optional[Any]:
    """下载错误恢复策略"""
    try:
        if "yt-dlp" in str(error).lower():
            logger.info("🔧 尝试重新安装yt-dlp...")
            from scripts.ytdlp_installer import YtdlpInstaller
            installer = YtdlpInstaller()
            if installer.ensure_ytdlp(force_update=True):
                return "recovered"
        
        if "permission" in str(error).lower():
            logger.info("🔧 尝试修复下载目录权限...")
            from .config import get_config
            from pathlib import Path
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
            download_dir.mkdir(parents=True, exist_ok=True)
            return "recovered"
            
    except Exception as e:
        logger.error(f"下载恢复策略失败: {e}")
    
    return None


def network_recovery_strategy(error: Exception, context: str) -> Optional[Any]:
    """网络错误恢复策略"""
    try:
        import requests
        if isinstance(error, (requests.exceptions.ConnectionError, 
                            requests.exceptions.Timeout)):
            logger.info("🔧 检测到网络问题，建议检查网络连接或代理设置")
            return "network_issue"
    except Exception as e:
        logger.error(f"网络恢复策略失败: {e}")
    
    return None


# 注册默认恢复策略
def register_default_strategies():
    """注册默认恢复策略"""
    error_handler = get_error_handler()
    
    # 数据库相关错误
    import sqlite3
    error_handler.register_recovery_strategy(sqlite3.OperationalError, database_recovery_strategy)
    error_handler.register_recovery_strategy(sqlite3.DatabaseError, database_recovery_strategy)
    
    # 网络相关错误
    try:
        import requests
        error_handler.register_recovery_strategy(requests.exceptions.ConnectionError, network_recovery_strategy)
        error_handler.register_recovery_strategy(requests.exceptions.Timeout, network_recovery_strategy)
    except ImportError:
        pass
    
    # 文件系统错误
    error_handler.register_recovery_strategy(PermissionError, download_recovery_strategy)
    error_handler.register_recovery_strategy(FileNotFoundError, download_recovery_strategy)


# 初始化默认策略
register_default_strategies()


class GracefulShutdown:
    """优雅关闭处理器"""
    
    def __init__(self):
        self.shutdown_handlers = []
        self.is_shutting_down = False
    
    def register_shutdown_handler(self, handler: Callable):
        """注册关闭处理器"""
        self.shutdown_handlers.append(handler)
    
    def shutdown(self):
        """执行优雅关闭"""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        logger.info("🔄 开始优雅关闭...")
        
        for handler in self.shutdown_handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"关闭处理器执行失败: {e}")
        
        logger.info("✅ 优雅关闭完成")


# 全局关闭处理器
_shutdown_handler = GracefulShutdown()


def get_shutdown_handler() -> GracefulShutdown:
    """获取关闭处理器实例"""
    return _shutdown_handler
