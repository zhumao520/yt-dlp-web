#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统优化和清理工具
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class SystemOptimizer:
    """系统优化器"""
    
    def __init__(self):
        self.optimizations = []
        self.errors = []
    
    def run_optimization(self) -> Dict[str, Any]:
        """运行系统优化"""
        logger.info("🚀 开始系统优化...")
        
        self.optimizations = []
        self.errors = []
        
        # 清理下载目录
        self._cleanup_downloads()
        
        # 清理日志文件
        self._cleanup_logs()
        
        # 清理临时文件
        self._cleanup_temp_files()
        
        # 优化数据库
        self._optimize_database()
        
        # 检查磁盘空间
        self._check_disk_space()
        
        # 清理会话文件
        self._cleanup_sessions()
        
        result = {
            "success": len(self.errors) == 0,
            "optimizations": self.optimizations,
            "errors": self.errors,
            "total_optimizations": len(self.optimizations)
        }
        
        if result["success"]:
            logger.info(f"✅ 系统优化完成，应用了 {len(self.optimizations)} 个优化")
        else:
            logger.warning(f"⚠️ 系统优化完成，但有 {len(self.errors)} 个错误")
        
        return result
    
    def _cleanup_downloads(self):
        """清理下载目录"""
        try:
            download_dir = Path("data/downloads")
            if not download_dir.exists():
                return
            
            # 清理超过7天的文件
            cutoff_time = time.time() - (7 * 24 * 3600)  # 7天
            cleaned_count = 0
            cleaned_size = 0
            
            for file_path in download_dir.iterdir():
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                            cleaned_size += file_size
                    except Exception as e:
                        logger.warning(f"无法删除文件 {file_path}: {e}")
            
            if cleaned_count > 0:
                size_mb = cleaned_size / (1024 * 1024)
                self.optimizations.append(f"清理了 {cleaned_count} 个旧下载文件 ({size_mb:.1f}MB)")
            
        except Exception as e:
            self.errors.append(f"下载目录清理失败: {e}")
    
    def _cleanup_logs(self):
        """清理日志文件"""
        try:
            log_dir = Path("data/logs")
            if not log_dir.exists():
                return
            
            # 保留最新的10个日志文件
            log_files = list(log_dir.glob("*.log*"))
            if len(log_files) > 10:
                log_files.sort(key=lambda x: x.stat().st_mtime)
                old_logs = log_files[:-10]
                
                cleaned_size = 0
                for log_file in old_logs:
                    try:
                        cleaned_size += log_file.stat().st_size
                        log_file.unlink()
                    except Exception as e:
                        logger.warning(f"无法删除日志文件 {log_file}: {e}")
                
                if old_logs:
                    size_mb = cleaned_size / (1024 * 1024)
                    self.optimizations.append(f"清理了 {len(old_logs)} 个旧日志文件 ({size_mb:.1f}MB)")
            
        except Exception as e:
            self.errors.append(f"日志清理失败: {e}")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            temp_dirs = [
                Path("data/temp"),
                Path("temp"),
                Path("/tmp/yt-dlp") if os.name != 'nt' else Path("C:/temp/yt-dlp")
            ]
            
            cleaned_count = 0
            cleaned_size = 0
            
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    for temp_file in temp_dir.rglob("*"):
                        if temp_file.is_file():
                            try:
                                # 删除超过1小时的临时文件
                                if time.time() - temp_file.stat().st_mtime > 3600:
                                    file_size = temp_file.stat().st_size
                                    temp_file.unlink()
                                    cleaned_count += 1
                                    cleaned_size += file_size
                            except Exception as e:
                                logger.warning(f"无法删除临时文件 {temp_file}: {e}")
            
            if cleaned_count > 0:
                size_mb = cleaned_size / (1024 * 1024)
                self.optimizations.append(f"清理了 {cleaned_count} 个临时文件 ({size_mb:.1f}MB)")
            
        except Exception as e:
            self.errors.append(f"临时文件清理失败: {e}")
    
    def _optimize_database(self):
        """优化数据库"""
        try:
            from app.core.database import get_database
            db = get_database()
            
            # 执行数据库优化
            with db.get_connection() as conn:
                # 清理旧的下载记录（保留最近100条）
                conn.execute('''
                    DELETE FROM downloads 
                    WHERE id NOT IN (
                        SELECT id FROM downloads 
                        ORDER BY created_at DESC 
                        LIMIT 100
                    )
                ''')
                
                # 优化数据库
                conn.execute('VACUUM')
                conn.execute('ANALYZE')
                conn.commit()
            
            self.optimizations.append("优化数据库并清理旧记录")
            
        except Exception as e:
            self.errors.append(f"数据库优化失败: {e}")
    
    def _check_disk_space(self):
        """检查磁盘空间"""
        try:
            import shutil
            
            # 检查主要目录的磁盘使用情况
            dirs_to_check = [
                ("下载目录", "data/downloads"),
                ("日志目录", "data/logs"),
                ("数据目录", "data")
            ]
            
            for name, dir_path in dirs_to_check:
                path = Path(dir_path)
                if path.exists():
                    total, used, free = shutil.disk_usage(str(path))
                    free_gb = free / (1024**3)
                    
                    if free_gb < 1.0:  # 少于1GB可用空间
                        self.errors.append(f"{name} 磁盘空间不足: {free_gb:.1f}GB可用")
                    elif free_gb < 5.0:  # 少于5GB发出警告
                        self.optimizations.append(f"{name} 磁盘空间警告: {free_gb:.1f}GB可用")
            
        except Exception as e:
            self.errors.append(f"磁盘空间检查失败: {e}")
    
    def _cleanup_sessions(self):
        """清理会话文件"""
        try:
            session_files = [
                "app/ytdlp_bot.session",
                "app/ytdlp_bot.session-journal",
                "app/ytdlp_uploader.session",
                "ytdlp_bot.session",
                "ytdlp_bot.session-journal"
            ]
            
            cleaned_count = 0
            for session_file in session_files:
                path = Path(session_file)
                if path.exists():
                    try:
                        # 检查文件是否超过30天未修改
                        if time.time() - path.stat().st_mtime > (30 * 24 * 3600):
                            path.unlink()
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"无法删除会话文件 {path}: {e}")
            
            if cleaned_count > 0:
                self.optimizations.append(f"清理了 {cleaned_count} 个旧会话文件")
            
        except Exception as e:
            self.errors.append(f"会话文件清理失败: {e}")


def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    optimizer = SystemOptimizer()
    result = optimizer.run_optimization()
    
    print("\n" + "="*50)
    print("系统优化报告")
    print("="*50)
    
    if result["optimizations"]:
        print("\n✅ 已应用的优化:")
        for opt in result["optimizations"]:
            print(f"  + {opt}")
    
    if result["errors"]:
        print("\n❌ 发现的问题:")
        for error in result["errors"]:
            print(f"  - {error}")
    
    print(f"\n📊 总计: {result['total_optimizations']} 个优化")
    print("="*50)
    
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
