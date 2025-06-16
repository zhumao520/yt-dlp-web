# -*- coding: utf-8 -*-
"""
下载文件自动清理模块
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class DownloadCleanup:
    """下载文件自动清理器"""
    
    def __init__(self):
        self.cleanup_thread = None
        self.stop_event = threading.Event()
        self.running = False
        
    def start(self):
        """启动自动清理"""
        if self.running:
            return
            
        try:
            from ...core.config import get_config
            
            auto_cleanup = get_config('downloader.auto_cleanup', True)
            if not auto_cleanup:
                logger.info("🧹 自动清理已禁用")
                return
                
            self.running = True
            self.stop_event.clear()
            
            # 启动清理线程
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True,
                name="DownloadCleanup"
            )
            self.cleanup_thread.start()
            
            logger.info("✅ 下载文件自动清理已启动")
            
        except Exception as e:
            logger.error(f"❌ 启动自动清理失败: {e}")
    
    def stop(self):
        """停止自动清理"""
        if not self.running:
            return
            
        self.running = False
        self.stop_event.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
            
        logger.info("✅ 下载文件自动清理已停止")
    
    def _cleanup_loop(self):
        """清理循环"""
        while not self.stop_event.is_set():
            try:
                from ...core.config import get_config
                
                # 获取清理间隔（小时）
                cleanup_interval = get_config('downloader.cleanup_interval', 1)
                interval_seconds = cleanup_interval * 3600  # 转换为秒
                
                # 执行清理
                self._perform_cleanup()
                
                # 等待下次清理
                self.stop_event.wait(interval_seconds)
                
            except Exception as e:
                logger.error(f"❌ 清理循环出错: {e}")
                # 出错时等待5分钟再重试
                self.stop_event.wait(300)
    
    def _perform_cleanup(self):
        """执行清理操作"""
        try:
            from ...core.config import get_config
            
            output_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
            if not output_dir.exists():
                return
                
            logger.info("🧹 开始执行下载文件清理...")
            
            # 获取清理配置
            file_retention_hours = get_config('downloader.file_retention_hours', 24)
            max_storage_mb = get_config('downloader.max_storage_mb', 2048)
            keep_recent_files = get_config('downloader.keep_recent_files', 20)
            
            # 获取所有下载文件
            files = self._get_download_files(output_dir)
            
            if not files:
                logger.debug("📁 下载目录为空，无需清理")
                return
            
            # 按修改时间排序（最新的在前）
            files.sort(key=lambda f: f['modified'], reverse=True)
            
            cleaned_count = 0
            cleaned_size = 0
            
            # 1. 基于时间的清理
            cutoff_time = time.time() - (file_retention_hours * 3600)
            for file_info in files[:]:
                if file_info['modified'] < cutoff_time:
                    if self._delete_file(file_info['path']):
                        cleaned_count += 1
                        cleaned_size += file_info['size']
                        files.remove(file_info)
            
            # 2. 基于存储空间的清理
            total_size_mb = sum(f['size'] for f in files) / (1024 * 1024)
            if total_size_mb > max_storage_mb:
                # 删除最旧的文件直到满足存储限制
                target_size = max_storage_mb * 0.8 * 1024 * 1024  # 保留80%空间
                current_size = sum(f['size'] for f in files)
                
                for file_info in reversed(files):  # 从最旧的开始删除
                    if current_size <= target_size:
                        break
                    if self._delete_file(file_info['path']):
                        cleaned_count += 1
                        cleaned_size += file_info['size']
                        current_size -= file_info['size']
                        files.remove(file_info)
            
            # 3. 基于文件数量的清理
            if len(files) > keep_recent_files:
                files_to_delete = files[keep_recent_files:]
                for file_info in files_to_delete:
                    if self._delete_file(file_info['path']):
                        cleaned_count += 1
                        cleaned_size += file_info['size']
            
            if cleaned_count > 0:
                cleaned_size_mb = cleaned_size / (1024 * 1024)
                logger.info(f"🧹 清理完成: 删除 {cleaned_count} 个文件，释放 {cleaned_size_mb:.1f} MB 空间")
            else:
                logger.debug("🧹 清理完成: 无需删除文件")
                
        except Exception as e:
            logger.error(f"❌ 执行清理失败: {e}")
    
    def _get_download_files(self, directory: Path) -> List[Dict[str, Any]]:
        """获取下载文件列表"""
        files = []
        try:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        'path': file_path,
                        'name': file_path.name,
                        'size': stat.st_size,
                        'modified': stat.st_mtime
                    })
        except Exception as e:
            logger.error(f"❌ 获取文件列表失败: {e}")
        
        return files
    
    def _delete_file(self, file_path: Path) -> bool:
        """删除文件"""
        try:
            file_path.unlink()
            logger.debug(f"🗑️ 删除文件: {file_path.name}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除文件失败 {file_path.name}: {e}")
            return False
    
    def manual_cleanup(self) -> Dict[str, Any]:
        """手动执行清理"""
        try:
            logger.info("🧹 手动执行清理...")
            self._perform_cleanup()
            return {"success": True, "message": "清理完成"}
        except Exception as e:
            logger.error(f"❌ 手动清理失败: {e}")
            return {"success": False, "error": str(e)}


# 全局清理器实例
_cleanup_instance = None

def get_cleanup_manager() -> DownloadCleanup:
    """获取清理管理器实例"""
    global _cleanup_instance
    if _cleanup_instance is None:
        _cleanup_instance = DownloadCleanup()
    return _cleanup_instance
