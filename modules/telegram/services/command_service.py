# -*- coding: utf-8 -*-
"""
Telegram命令服务 - 处理机器人命令逻辑
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class TelegramCommandService:
    """Telegram命令服务 - 解耦命令处理逻辑"""
    
    def __init__(self):
        pass
    
    def handle_start_command(self) -> str:
        """处理/start命令"""
        return """🤖 **YT-DLP Web 机器人**

欢迎使用！我可以帮您下载视频。

**使用方法：**
• 直接发送视频链接，我会自动下载并发送给您
• 支持 YouTube、Bilibili、Twitter 等 1000+ 网站

**📋 基础命令：**
/start - 显示此帮助信息
/status - 查看系统状态
/downloads - 查看下载任务列表
/files - 查看已下载文件列表

**🎮 交互命令：**
/cancel <ID> - 取消下载任务
/send <文件名> - 发送指定文件
/delete <文件名> - 删除指定文件
/cleanup - 清理7天前的旧文件

**🔧 调试命令：**
/debug - 查看调试信息

**示例：**
`https://www.youtube.com/watch?v=dQw4w9WgXcQ`
`/cancel a1b2c3d4`
`/send video.mp4`"""
    
    def handle_status_command(self) -> str:
        """处理/status命令"""
        try:
            # 获取基础信息
            active_count = self._get_active_downloads_count()
            server_url = self._get_server_url()
            
            # 尝试获取系统信息
            try:
                import psutil
                return self._get_detailed_status(active_count, server_url)
            except ImportError:
                return self._get_simple_status(active_count, server_url)
                
        except Exception as e:
            logger.error(f"❌ 获取状态失败: {e}")
            return f"""❌ **系统状态获取失败**

错误: {str(e)}

🤖 **机器人状态**: 正常运行"""
    
    def handle_downloads_command(self) -> str:
        """处理/downloads命令"""
        try:
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            downloads = download_manager.get_all_downloads()
            
            recent_downloads = downloads[:5]  # 最近5个
            
            if not recent_downloads:
                return "📋 **最近下载**\n\n暂无下载记录"
            
            downloads_text = "📋 **最近下载**\n\n"
            for i, download in enumerate(recent_downloads, 1):
                status_emoji = {
                    'pending': '⏳',
                    'downloading': '🔄',
                    'completed': '✅',
                    'failed': '❌'
                }.get(download['status'], '❓')
                
                title = download.get('title', 'Unknown')[:30]
                downloads_text += f"{i}. {status_emoji} {title}\n"
            
            return downloads_text
            
        except Exception as e:
            logger.error(f"❌ 获取下载列表失败: {e}")
            return f"📋 **最近下载**\n\n❌ 获取失败: {str(e)}"
    
    def handle_files_command(self) -> str:
        """处理/files命令"""
        try:
            from core.config import get_config
            
            download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
            
            if not download_dir.exists():
                return "📁 **文件列表**\n\n下载文件夹不存在"
            
            files = []
            for file_path in download_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        'name': file_path.name,
                        'size': stat.st_size,
                        'modified': stat.st_mtime
                    })
            
            # 按修改时间倒序排列，取最近5个
            files.sort(key=lambda x: x['modified'], reverse=True)
            recent_files = files[:5]
            
            if not recent_files:
                return "📁 **文件列表**\n\n暂无下载文件"
            
            files_text = f"📁 **文件列表** (共{len(files)}个文件)\n\n"
            for i, file_info in enumerate(recent_files, 1):
                name = file_info['name'][:30]
                size_mb = file_info['size'] / (1024 * 1024)
                files_text += f"{i}. 📄 {name}\n   💾 {size_mb:.1f} MB\n\n"
            
            if len(files) > 5:
                files_text += f"... 还有 {len(files) - 5} 个文件"
            
            return files_text
            
        except Exception as e:
            logger.error(f"❌ 获取文件列表失败: {e}")
            return f"📁 **文件列表**\n\n❌ 读取失败: {str(e)}"
    
    def handle_debug_command(self) -> str:
        """处理/debug命令"""
        try:
            import sys
            
            debug_text = f"""🔍 **调试信息**

**Python版本**: {sys.version.split()[0]}

**环境变量**:
SERVER_URL = `{os.getenv('SERVER_URL', '未设置')}`

**psutil检查**:"""
            
            try:
                import psutil
                debug_text += f"""
✅ psutil可用 (版本: {psutil.__version__})
CPU: {psutil.cpu_percent()}%
内存: {psutil.virtual_memory().percent:.1f}%"""
            except ImportError:
                debug_text += "\n❌ psutil不可用 - 未安装"
            except Exception as e:
                debug_text += f"\n❌ psutil错误: {e}"
            
            # 获取服务器URL
            server_url = self._get_server_url()
            debug_text += f"""

**最终URL**: `{server_url}`

**系统状态**: 正常运行"""
            
            return debug_text
            
        except Exception as e:
            logger.error(f"❌ 获取调试信息失败: {e}")
            return f"🔍 **调试信息**\n\n❌ 获取失败: {str(e)}"
    
    def _get_active_downloads_count(self) -> int:
        """获取活跃下载数量"""
        try:
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            downloads = download_manager.get_all_downloads()
            return len([d for d in downloads if d['status'] in ['pending', 'downloading']])
        except Exception as e:
            logger.error(f"❌ 获取活跃下载数量失败: {e}")
            return 0
    
    def _get_server_url(self) -> str:
        """获取服务器URL"""
        server_url = os.getenv('SERVER_URL', 'http://localhost:8080')
        if server_url == 'http://localhost:8080':
            try:
                from flask import request
                if request:
                    server_url = request.url_root.rstrip('/')
            except:
                pass
        return server_url
    
    def _get_detailed_status(self, active_count: int, server_url: str) -> str:
        """获取详细系统状态（需要psutil）"""
        try:
            import psutil
            from core.config import get_config
            
            # 获取系统信息
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 获取下载目录信息
            download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
            download_disk_usage = 0
            download_file_count = 0
            
            if download_dir.exists():
                try:
                    download_disk_usage = sum(f.stat().st_size for f in download_dir.rglob('*') if f.is_file())
                    download_file_count = len([f for f in download_dir.iterdir() if f.is_file()])
                except:
                    pass
            
            # 获取系统运行时间
            try:
                boot_time = psutil.boot_time()
                uptime_seconds = time.time() - boot_time
                uptime_days = int(uptime_seconds // 86400)
                uptime_hours = int((uptime_seconds % 86400) // 3600)
                uptime_str = f"{uptime_days}天{uptime_hours}小时"
            except:
                uptime_str = "未知"
            
            return f"""🖥️ **VPS系统状态**

💻 **CPU使用率**: {cpu_percent:.1f}%
🧠 **内存使用**: {memory.percent:.1f}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)
💾 **磁盘使用**: {disk.percent:.1f}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)
⏰ **运行时间**: {uptime_str}

📁 **下载目录**: {download_file_count} 个文件
📦 **占用空间**: {download_disk_usage / (1024**3):.2f} GB
🔄 **活跃下载**: {active_count} 个任务

🌐 **管理面板**:
`{server_url}`

🤖 **机器人状态**: 正常运行"""
            
        except Exception as e:
            logger.error(f"❌ 获取详细状态失败: {e}")
            return self._get_simple_status(active_count, server_url)
    
    def _get_simple_status(self, active_count: int, server_url: str) -> str:
        """获取简单系统状态"""
        return f"""📊 **系统状态**

⚠️ **系统监控模块未安装**
请安装 psutil: `pip install psutil`

🔄 **活跃下载**: {active_count}
🤖 **机器人状态**: 正常运行

🌐 **管理面板**:
`{server_url}`"""


# 全局命令服务实例
_command_service = None

def get_telegram_command_service() -> TelegramCommandService:
    """获取Telegram命令服务实例"""
    global _command_service
    if _command_service is None:
        _command_service = TelegramCommandService()
    return _command_service
