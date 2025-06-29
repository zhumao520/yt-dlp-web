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
            # 🔧 优先从数据库读取用户设置，然后才是配置文件
            auto_cleanup = self._get_setting('downloader.auto_cleanup', True)
            logger.info(f"🔧 清理器配置检查: auto_cleanup = {auto_cleanup} (来源: {'数据库' if self._has_db_setting('downloader.auto_cleanup') else '配置文件'})")

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
                from core.config import get_config
                
                # 获取清理间隔（小时）
                cleanup_interval = get_config('downloader.cleanup_interval', 1)
                interval_seconds = cleanup_interval * 3600  # 转换为秒
                
                # 执行清理
                self._perform_cleanup()
                
                # 等待下次清理（限制最大超时值避免系统限制）
                max_wait = min(interval_seconds, 86400)  # 最大24小时
                self.stop_event.wait(max_wait)
                
            except Exception as e:
                logger.error(f"❌ 清理循环出错: {e}")
                # 出错时等待5分钟再重试
                self.stop_event.wait(300)
    
    def _get_setting(self, key: str, default):
        """优先从数据库获取设置，然后是配置文件"""
        try:
            from core.database import get_database
            db = get_database()

            # 先尝试从数据库获取
            db_value = db.get_setting(key)
            if db_value is not None:
                # 转换数据类型
                if isinstance(default, bool):
                    return str(db_value).lower() in ('true', '1', 'yes', 'on')
                elif isinstance(default, int):
                    return int(db_value)
                elif isinstance(default, float):
                    return float(db_value)
                else:
                    return db_value

            # 如果数据库没有，从配置文件获取
            from core.config import get_config
            return get_config(key, default)

        except Exception as e:
            logger.warning(f"⚠️ 获取设置失败 {key}: {e}")
            # 出错时使用配置文件
            from core.config import get_config
            return get_config(key, default)

    def _has_db_setting(self, key: str) -> bool:
        """检查数据库中是否有该设置"""
        try:
            from core.database import get_database
            db = get_database()
            return db.get_setting(key) is not None
        except:
            return False

    def _perform_cleanup(self):
        """执行清理操作"""
        try:
            # 🔧 优先从数据库读取设置
            output_dir = Path(self._get_setting('downloader.output_dir', 'data/downloads'))
            if not output_dir.exists():
                return

            logger.info("🧹 开始执行下载文件清理...")

            # 获取清理配置（优先数据库）
            file_retention_hours = self._get_setting('downloader.file_retention_hours', 24)
            max_storage_mb = self._get_setting('downloader.max_storage_mb', 2048)
            keep_recent_files = self._get_setting('downloader.keep_recent_files', 20)
            
            # 获取所有下载文件
            files = self._get_download_files(output_dir)
            
            if not files:
                logger.debug("📁 下载目录为空，无需清理")
                return
            
            # 按修改时间排序（最新的在前）
            files.sort(key=lambda f: f['modified'], reverse=True)

            cleaned_count = 0
            cleaned_size = 0

            logger.info(f"📊 清理前统计: {len(files)} 个文件")
            logger.info(f"🔧 清理配置: 保留{keep_recent_files}个最近文件, {file_retention_hours}小时内文件, 最大{max_storage_mb}MB")

            # 🛡️ 修复后的清理逻辑：优先保护最近文件

            # 1. 首先保护最近的文件（无论多旧）
            protected_files = files[:keep_recent_files]  # 最近N个文件永远不删除
            candidate_files = files[keep_recent_files:]  # 可能被删除的文件

            logger.info(f"🛡️ 保护最近 {len(protected_files)} 个文件")
            logger.info(f"🔍 检查 {len(candidate_files)} 个候选文件")

            # 2. 对候选文件应用时间规则
            cutoff_time = time.time() - (file_retention_hours * 3600)
            files_to_keep = []

            for file_info in candidate_files:
                if file_info['modified'] >= cutoff_time:
                    # 在时间保护范围内，保留
                    files_to_keep.append(file_info)
                    logger.debug(f"⏰ 时间保护: {file_info['name']}")
                else:
                    # 超过时间限制，删除
                    if self._delete_file(file_info['path']):
                        cleaned_count += 1
                        cleaned_size += file_info['size']
                        logger.info(f"🗑️ 时间清理: {file_info['name']} (超过{file_retention_hours}小时)")

            # 3. 重新组合保留的文件
            remaining_files = protected_files + files_to_keep

            # 4. 基于存储空间的清理（只对非保护文件）
            total_size_mb = sum(f['size'] for f in remaining_files) / (1024 * 1024)
            if total_size_mb > max_storage_mb:
                logger.info(f"💾 存储空间超限: {total_size_mb:.1f}MB > {max_storage_mb}MB")

                # 只对非保护文件进行空间清理
                target_size = max_storage_mb * 0.8 * 1024 * 1024  # 保留80%空间
                current_size = sum(f['size'] for f in remaining_files)
                protected_size = sum(f['size'] for f in protected_files)

                # 从非保护文件中删除（最旧的优先）
                files_to_keep.sort(key=lambda f: f['modified'])  # 最旧的在前

                for file_info in files_to_keep[:]:
                    if current_size <= target_size or current_size <= protected_size:
                        break
                    if self._delete_file(file_info['path']):
                        cleaned_count += 1
                        cleaned_size += file_info['size']
                        current_size -= file_info['size']
                        files_to_keep.remove(file_info)
                        logger.info(f"🗑️ 空间清理: {file_info['name']}")
            
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
