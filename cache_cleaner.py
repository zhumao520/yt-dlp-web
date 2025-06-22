#!/usr/bin/env python3
"""
项目缓存清理脚本
用于清理项目中的各种缓存文件和临时文件
保留此脚本直到项目完成

使用方法:
    python cache_cleaner.py                    # 基础清理
    python cache_cleaner.py --all              # 清理所有
    python cache_cleaner.py --clean-downloads  # 包含下载文件
    python cache_cleaner.py --clean-logs       # 包含日志文件
"""

import os
import shutil
import glob
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse
import time

class CacheCleaner:
    """缓存清理器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.cleaned_files = []
        self.cleaned_dirs = []
        self.total_size_freed = 0
        
    def get_file_size(self, file_path: Path) -> int:
        """获取文件大小"""
        try:
            return file_path.stat().st_size
        except:
            return 0
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def clean_pycache(self) -> None:
        """清理 __pycache__ 目录"""
        print("🧹 清理 __pycache__ 目录...")
        
        for root, dirs, files in os.walk(self.project_root):
            if '__pycache__' in dirs:
                pycache_path = Path(root) / '__pycache__'
                try:
                    # 计算目录大小
                    dir_size = sum(self.get_file_size(f) for f in pycache_path.rglob('*') if f.is_file())
                    
                    shutil.rmtree(pycache_path)
                    self.cleaned_dirs.append(str(pycache_path))
                    self.total_size_freed += dir_size
                    print(f"  ✅ 删除: {pycache_path.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {pycache_path} - {e}")
    
    def clean_pyc_files(self) -> None:
        """清理 .pyc 和 .pyo 文件"""
        print("🧹 清理 .pyc/.pyo 文件...")
        
        pyc_files = list(self.project_root.rglob('*.pyc')) + list(self.project_root.rglob('*.pyo'))
        for pyc_file in pyc_files:
            try:
                file_size = self.get_file_size(pyc_file)
                pyc_file.unlink()
                self.cleaned_files.append(str(pyc_file))
                self.total_size_freed += file_size
                print(f"  ✅ 删除: {pyc_file.relative_to(self.project_root)}")
            except Exception as e:
                print(f"  ❌ 删除失败: {pyc_file} - {e}")
    
    def clean_temp_files(self) -> None:
        """清理临时文件"""
        print("🧹 清理临时文件...")
        
        temp_patterns = [
            '*.tmp', '*.temp', '*~', '*.bak', '*.swp', '*.swo',
            '.DS_Store', 'Thumbs.db', 'desktop.ini', '*.cache'
        ]
        
        for pattern in temp_patterns:
            temp_files = list(self.project_root.rglob(pattern))
            for temp_file in temp_files:
                try:
                    file_size = self.get_file_size(temp_file)
                    temp_file.unlink()
                    self.cleaned_files.append(str(temp_file))
                    self.total_size_freed += file_size
                    print(f"  ✅ 删除: {temp_file.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {temp_file} - {e}")
    
    def clean_log_files(self, keep_recent: bool = True) -> None:
        """清理日志文件"""
        print("🧹 清理日志文件...")
        
        log_patterns = ['*.log', '*.log.*']
        
        for pattern in log_patterns:
            log_files = list(self.project_root.rglob(pattern))
            for log_file in log_files:
                try:
                    # 如果保留最近的日志，跳过app.log
                    if keep_recent and log_file.name == 'app.log':
                        print(f"  ⏭️ 保留: {log_file.relative_to(self.project_root)}")
                        continue
                    
                    file_size = self.get_file_size(log_file)
                    log_file.unlink()
                    self.cleaned_files.append(str(log_file))
                    self.total_size_freed += file_size
                    print(f"  ✅ 删除: {log_file.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {log_file} - {e}")
    
    def clean_test_files(self) -> None:
        """清理测试文件"""
        print("🧹 清理测试文件...")
        
        test_patterns = [
            'test_*.py', '*_test.py', 'test*.py'
        ]
        
        # 排除正式的测试目录
        exclude_dirs = {'tests', 'test', 'testing'}
        
        for pattern in test_patterns:
            test_files = list(self.project_root.rglob(pattern))
            for test_file in test_files:
                # 检查是否在排除目录中
                if any(exclude_dir in test_file.parts for exclude_dir in exclude_dirs):
                    print(f"  ⏭️ 保留正式测试: {test_file.relative_to(self.project_root)}")
                    continue
                
                try:
                    file_size = self.get_file_size(test_file)
                    test_file.unlink()
                    self.cleaned_files.append(str(test_file))
                    self.total_size_freed += file_size
                    print(f"  ✅ 删除: {test_file.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {test_file} - {e}")
    
    def clean_download_files(self, confirm: bool = False) -> None:
        """清理下载文件（需要确认）"""
        if not confirm:
            print("⚠️ 跳过下载文件清理（需要 --clean-downloads 参数）")
            return
            
        print("🧹 清理下载文件...")
        
        downloads_dir = self.project_root / 'downloads'
        if downloads_dir.exists():
            download_files = [f for f in downloads_dir.iterdir() if f.is_file()]
            
            if download_files:
                print(f"  📁 发现 {len(download_files)} 个下载文件")
                for download_file in download_files:
                    try:
                        file_size = self.get_file_size(download_file)
                        download_file.unlink()
                        self.cleaned_files.append(str(download_file))
                        self.total_size_freed += file_size
                        print(f"  ✅ 删除: {download_file.relative_to(self.project_root)}")
                    except Exception as e:
                        print(f"  ❌ 删除失败: {download_file} - {e}")
            else:
                print("  ℹ️ 下载目录为空")
        else:
            print("  ℹ️ 下载目录不存在")
    
    def clean_node_modules(self, confirm: bool = False) -> None:
        """清理 node_modules 目录（如果存在）"""
        if not confirm:
            print("⚠️ 跳过 node_modules 清理（需要 --clean-node 参数）")
            return
            
        print("🧹 清理 node_modules 目录...")
        
        node_modules_dirs = list(self.project_root.rglob('node_modules'))
        for node_dir in node_modules_dirs:
            if node_dir.is_dir():
                try:
                    # 计算目录大小
                    dir_size = sum(self.get_file_size(f) for f in node_dir.rglob('*') if f.is_file())
                    
                    shutil.rmtree(node_dir)
                    self.cleaned_dirs.append(str(node_dir))
                    self.total_size_freed += dir_size
                    print(f"  ✅ 删除: {node_dir.relative_to(self.project_root)}")
                except Exception as e:
                    print(f"  ❌ 删除失败: {node_dir} - {e}")
    
    def generate_report(self) -> Dict[str, Any]:
        """生成清理报告"""
        return {
            'cleaned_files_count': len(self.cleaned_files),
            'cleaned_dirs_count': len(self.cleaned_dirs),
            'total_size_freed': self.total_size_freed,
            'total_size_freed_formatted': self.format_size(self.total_size_freed),
            'cleaned_files': self.cleaned_files,
            'cleaned_dirs': self.cleaned_dirs
        }
    
    def print_report(self) -> None:
        """打印清理报告"""
        report = self.generate_report()
        
        print(f"\n{'='*60}")
        print("🎉 清理完成报告")
        print(f"{'='*60}")
        print(f"📁 删除文件数量: {report['cleaned_files_count']}")
        print(f"📂 删除目录数量: {report['cleaned_dirs_count']}")
        print(f"💾 释放空间大小: {report['total_size_freed_formatted']}")
        print(f"{'='*60}")
        
        if report['cleaned_files_count'] == 0 and report['cleaned_dirs_count'] == 0:
            print("✨ 项目已经很干净了！")
        else:
            print("✅ 项目清理完成！")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='项目缓存清理脚本')
    parser.add_argument('--clean-downloads', action='store_true', help='清理下载文件')
    parser.add_argument('--clean-logs', action='store_true', help='清理所有日志文件')
    parser.add_argument('--clean-node', action='store_true', help='清理 node_modules 目录')
    parser.add_argument('--clean-tests', action='store_true', help='清理测试文件')
    parser.add_argument('--all', action='store_true', help='清理所有类型的缓存文件')
    
    args = parser.parse_args()
    
    print("🧹 项目缓存清理脚本启动...")
    print(f"📁 项目路径: {Path('.').resolve()}")
    print(f"⏰ 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    cleaner = CacheCleaner(".")
    
    # 基础清理（总是执行）
    cleaner.clean_pycache()
    cleaner.clean_pyc_files()
    cleaner.clean_temp_files()
    
    # 可选清理
    if args.all or args.clean_logs:
        cleaner.clean_log_files(keep_recent=not args.all)
    
    if args.all or args.clean_tests:
        cleaner.clean_test_files()
    
    if args.all or args.clean_downloads:
        cleaner.clean_download_files(confirm=True)
    
    if args.all or args.clean_node:
        cleaner.clean_node_modules(confirm=True)
    
    # 打印报告
    cleaner.print_report()
    
    print(f"\n⏰ 完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n💡 使用提示:")
    print("  python cache_cleaner.py                    # 基础清理")
    print("  python cache_cleaner.py --all              # 清理所有")
    print("  python cache_cleaner.py --clean-downloads  # 包含下载文件")
    print("  python cache_cleaner.py --clean-logs       # 包含日志文件")

if __name__ == "__main__":
    main()
