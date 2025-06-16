# -*- coding: utf-8 -*-
"""
现代化 Telegram 命令服务
优化的命令处理逻辑，支持依赖注入和配置驱动
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ModernTelegramCommandService:
    """现代化 Telegram 命令服务 - 解耦、可测试、可配置"""
    
    def __init__(self, notifier=None):
        self.notifier = notifier
        self._downloads_cache = {}
        self._files_cache = {}
        self._cache_timeout = 300  # 5分钟缓存
    
    def get_notifier(self):
        """获取通知器实例（延迟加载）"""
        if not self.notifier:
            from ..notifier import get_telegram_notifier
            self.notifier = get_telegram_notifier()
        return self.notifier
    
    def handle_start_command(self) -> str:
        """处理/start命令 - 现代化帮助信息"""
        return """🤖 **YT-DLP Web 机器人**

欢迎使用！我可以帮您下载视频并智能发送文件。

**📥 下载功能：**
• 发送视频链接即可开始下载
• 支持 YouTube、Bilibili、Twitter 等平台
• 自动选择最佳质量和格式
• 实时进度更新

**🎛️ 交互命令：**
• `/status` - 查看系统状态
• `/downloads` - 查看下载列表
• `/files` - 查看可用文件
• `/send <序号|文件名>` - 发送指定文件
• `/delete <序号|文件名>` - 删除指定文件
• `/cancel <下载ID>` - 取消正在下载的任务
• `/cleanup` - 清理旧文件

**🔧 系统特性：**
• 智能文件发送（自动选择 Bot API 或 Pyrofork）
• 大文件支持（最大 2GB）
• 自动回退机制
• 进度实时更新

**💡 使用提示：**
• 大文件会自动使用 Pyrofork 发送
• 可以随时取消正在进行的下载
• 文件会保留一段时间供您下载

开始使用吧！发送一个视频链接试试 🚀"""

    def handle_status_command(self) -> str:
        """处理/status命令 - 显示系统状态"""
        try:
            notifier = self.get_notifier()
            status = notifier.get_status()
            
            # 获取下载管理器状态
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()

            # 兼容性处理 - 适配不同的 API
            try:
                if hasattr(download_manager, 'get_active_downloads'):
                    active_downloads = download_manager.get_active_downloads()
                else:
                    # 回退到获取所有下载并过滤活跃的
                    all_downloads = download_manager.get_all_downloads()
                    active_downloads = [d for d in all_downloads if d.get('status') in ['pending', 'downloading']]
            except Exception as e:
                logger.warning(f"获取活跃下载失败: {e}")
                active_downloads = []
            
            # 获取文件统计
            files_info = self._get_files_info()
            
            # 构建状态消息
            status_msg = f"""📊 **系统状态报告**

**🤖 Telegram 模块:**
• 状态: {status['status']}
• 实现: {status['implementation']}
• 活跃下载: {status.get('active_downloads', 0)} 个

**📥 下载管理器:**
• 活跃任务: {len(active_downloads)} 个
• 队列状态: {'正常' if len(active_downloads) < 5 else '繁忙'}

**📁 文件管理:**
• 可用文件: {files_info['count']} 个
• 总大小: {files_info['total_size_mb']:.1f} MB
• 最新文件: {files_info['latest_file']}

**⚙️ 上传器状态:**"""

            # 添加上传器状态
            uploaders = status.get('uploaders', {})
            if uploaders.get('bot_api_available'):
                status_msg += "\n• Bot API: ✅ 可用"
            else:
                status_msg += "\n• Bot API: ❌ 不可用"
                
            if uploaders.get('pyrofork_available'):
                status_msg += "\n• Pyrofork: ✅ 可用"
            else:
                status_msg += "\n• Pyrofork: ⚠️ 不可用（影响大文件发送）"
            
            # 添加配置信息
            config = status.get('config', {})
            status_msg += f"""

**🔧 配置状态:**
• Bot Token: {'✅' if config.get('bot_token_configured') else '❌'}
• Chat ID: {'✅' if config.get('chat_id_configured') else '❌'}
• API 凭据: {'✅' if config.get('api_credentials_configured') else '⚠️ 未配置（影响大文件）'}
• 自动回退: {'✅' if config.get('auto_fallback') else '❌'}

🕐 **更新时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}"""
            
            return status_msg
            
        except Exception as e:
            logger.error(f"❌ 获取状态失败: {e}")
            return f"❌ **状态获取失败**\n\n错误: {str(e)}"

    def handle_downloads_command(self) -> str:
        """处理/downloads命令 - 显示下载列表"""
        try:
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            
            # 获取活跃下载（兼容性处理）
            try:
                if hasattr(download_manager, 'get_active_downloads'):
                    active_downloads = download_manager.get_active_downloads()
                else:
                    all_downloads = download_manager.get_all_downloads()
                    active_downloads = [d for d in all_downloads if d.get('status') in ['pending', 'downloading']]
            except Exception as e:
                logger.warning(f"获取活跃下载失败: {e}")
                active_downloads = []

            # 获取最近完成的下载（兼容性处理）
            try:
                if hasattr(download_manager, 'get_recent_downloads'):
                    recent_downloads = download_manager.get_recent_downloads(limit=5)
                else:
                    all_downloads = download_manager.get_all_downloads()
                    completed_downloads = [d for d in all_downloads if d.get('status') == 'completed']
                    recent_downloads = sorted(completed_downloads, key=lambda x: x.get('completed_time', ''), reverse=True)[:5]
            except Exception as e:
                logger.warning(f"获取最近下载失败: {e}")
                recent_downloads = []
            
            if not active_downloads and not recent_downloads:
                return """📥 **下载列表**

当前没有活跃的下载任务。

💡 **提示**: 发送视频链接开始下载"""
            
            message = "📥 **下载列表**\n\n"
            
            # 活跃下载
            if active_downloads:
                message += "**🔄 正在下载:**\n"
                for i, download in enumerate(active_downloads, 1):
                    download_id = download.get('id', 'unknown')[:8]
                    title = download.get('title', 'Unknown')[:30]
                    progress = download.get('progress', 0)
                    status = download.get('status', 'unknown')
                    
                    progress_bar = self._generate_mini_progress_bar(progress)
                    message += f"{i}. **{title}**\n"
                    message += f"   ID: `{download_id}` | {progress_bar} {progress}%\n"
                    message += f"   状态: {status}\n\n"
            
            # 最近完成的下载
            if recent_downloads:
                message += "**✅ 最近完成:**\n"
                for i, download in enumerate(recent_downloads, 1):
                    title = download.get('title', 'Unknown')[:30]
                    completed_time = download.get('completed_time', '')
                    file_size = download.get('file_size_mb', 0)
                    
                    message += f"{i}. **{title}**\n"
                    message += f"   大小: {file_size:.1f}MB | 完成: {completed_time}\n\n"
            
            message += "💡 **命令提示**:\n"
            message += "• `/cancel <ID>` - 取消下载\n"
            message += "• `/files` - 查看可用文件"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ 获取下载列表失败: {e}")
            return f"❌ **获取下载列表失败**\n\n错误: {str(e)}"

    def handle_files_command(self) -> str:
        """处理/files命令 - 显示文件列表"""
        try:
            files_info = self._get_files_info(detailed=True)
            
            if not files_info['files']:
                return """📁 **文件列表**

当前没有可用文件。

💡 **提示**: 下载完成的文件会自动出现在这里"""
            
            message = f"""📁 **文件列表** ({files_info['count']} 个文件)

**总大小**: {files_info['total_size_mb']:.1f} MB

"""
            
            for i, file_info in enumerate(files_info['files'], 1):
                name = file_info['name'][:40]
                size_mb = file_info['size_mb']
                modified = file_info['modified']
                
                message += f"{i}. **{name}**\n"
                message += f"   大小: {size_mb:.1f}MB | 修改: {modified}\n\n"
            
            message += """💡 **命令提示**:
• `/send <序号>` - 发送指定文件 (如: `/send 1`)
• `/send <文件名>` - 按名称发送 (如: `/send video.mp4`)
• `/delete <序号>` - 删除指定文件
• `/cleanup` - 清理旧文件"""
            
            return message
            
        except Exception as e:
            logger.error(f"❌ 获取文件列表失败: {e}")
            return f"❌ **获取文件列表失败**\n\n错误: {str(e)}"

    def handle_send_command(self, args: str) -> str:
        """处理/send命令 - 发送文件"""
        try:
            if not args.strip():
                return "❌ **使用方法**: `/send <序号|文件名>`\n\n例如: `/send 1` 或 `/send video.mp4`"
            
            # 获取文件信息
            files_info = self._get_files_info(detailed=True)
            if not files_info['files']:
                return "❌ **没有可用文件**\n\n使用 `/files` 查看文件列表"
            
            # 解析参数
            target_file = None
            if args.isdigit():
                # 按序号选择
                index = int(args) - 1
                if 0 <= index < len(files_info['files']):
                    target_file = files_info['files'][index]
                else:
                    return f"❌ **序号无效**\n\n请使用 1-{len(files_info['files'])} 之间的序号"
            else:
                # 按文件名选择
                for file_info in files_info['files']:
                    if args.lower() in file_info['name'].lower():
                        target_file = file_info
                        break
                
                if not target_file:
                    return f"❌ **文件未找到**: {args}\n\n使用 `/files` 查看可用文件"
            
            # 发送文件
            notifier = self.get_notifier()
            file_path = target_file['path']
            caption = f"📁 **{target_file['name']}**\n💾 大小: {target_file['size_mb']:.1f}MB"
            
            success = notifier.send_file(file_path, caption)
            
            if success:
                return f"✅ **文件发送成功**\n\n📁 {target_file['name']}"
            else:
                return f"❌ **文件发送失败**\n\n📁 {target_file['name']}\n\n💡 请稍后重试或检查网络连接"
            
        except Exception as e:
            logger.error(f"❌ 发送文件失败: {e}")
            return f"❌ **发送文件失败**\n\n错误: {str(e)}"

    def handle_delete_command(self, args: str) -> str:
        """处理/delete命令 - 删除文件"""
        try:
            if not args.strip():
                return "❌ **使用方法**: `/delete <序号|文件名>`\n\n例如: `/delete 1` 或 `/delete video.mp4`"
            
            # 获取文件信息
            files_info = self._get_files_info(detailed=True)
            if not files_info['files']:
                return "❌ **没有可用文件**\n\n使用 `/files` 查看文件列表"
            
            # 解析参数
            target_file = None
            if args.isdigit():
                # 按序号选择
                index = int(args) - 1
                if 0 <= index < len(files_info['files']):
                    target_file = files_info['files'][index]
                else:
                    return f"❌ **序号无效**\n\n请使用 1-{len(files_info['files'])} 之间的序号"
            else:
                # 按文件名选择
                for file_info in files_info['files']:
                    if args.lower() in file_info['name'].lower():
                        target_file = file_info
                        break
                
                if not target_file:
                    return f"❌ **文件未找到**: {args}\n\n使用 `/files` 查看可用文件"
            
            # 删除文件
            file_path = Path(target_file['path'])
            if file_path.exists():
                file_path.unlink()
                return f"✅ **文件删除成功**\n\n📁 {target_file['name']}"
            else:
                return f"❌ **文件不存在**\n\n📁 {target_file['name']}"
            
        except Exception as e:
            logger.error(f"❌ 删除文件失败: {e}")
            return f"❌ **删除文件失败**\n\n错误: {str(e)}"

    def handle_cancel_command(self, args: str) -> str:
        """处理/cancel命令 - 取消下载"""
        try:
            if not args.strip():
                return "❌ **使用方法**: `/cancel <下载ID>`\n\n例如: `/cancel abc12345`"
            
            download_id = args.strip()
            
            # 取消下载
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            
            success = download_manager.cancel_download(download_id)
            
            if success:
                return f"✅ **下载已取消**\n\nID: `{download_id}`"
            else:
                return f"❌ **取消失败**\n\nID: `{download_id}`\n\n可能原因:\n• 下载ID不存在\n• 下载已完成\n• 下载已被取消"
            
        except Exception as e:
            logger.error(f"❌ 取消下载失败: {e}")
            return f"❌ **取消下载失败**\n\n错误: {str(e)}"

    def handle_cleanup_command(self) -> str:
        """处理/cleanup命令 - 清理旧文件"""
        try:
            # 获取下载目录
            downloads_dir = Path("downloads")
            if not downloads_dir.exists():
                return "❌ **下载目录不存在**"
            
            # 清理7天前的文件
            cutoff_time = time.time() - (7 * 24 * 60 * 60)  # 7天
            cleaned_files = []
            total_size_mb = 0
            
            for file_path in downloads_dir.rglob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_size_mb = file_path.stat().st_size / (1024 * 1024)
                    cleaned_files.append(file_path.name)
                    total_size_mb += file_size_mb
                    file_path.unlink()
            
            if cleaned_files:
                return f"""✅ **清理完成**

删除了 {len(cleaned_files)} 个文件
释放空间: {total_size_mb:.1f} MB

💡 已删除7天前的文件"""
            else:
                return "✅ **清理完成**\n\n没有需要清理的文件"
            
        except Exception as e:
            logger.error(f"❌ 清理文件失败: {e}")
            return f"❌ **清理失败**\n\n错误: {str(e)}"

    def _get_files_info(self, detailed: bool = False) -> Dict[str, Any]:
        """获取文件信息"""
        try:
            downloads_dir = Path("downloads")
            if not downloads_dir.exists():
                return {'count': 0, 'total_size_mb': 0, 'latest_file': '无', 'files': []}
            
            files = []
            total_size = 0
            latest_time = 0
            latest_file = '无'
            
            for file_path in downloads_dir.rglob("*"):
                if file_path.is_file():
                    stat = file_path.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    total_size += size_mb
                    
                    if stat.st_mtime > latest_time:
                        latest_time = stat.st_mtime
                        latest_file = file_path.name[:30]
                    
                    if detailed:
                        files.append({
                            'name': file_path.name,
                            'path': str(file_path),
                            'size_mb': size_mb,
                            'modified': time.strftime('%m-%d %H:%M', time.localtime(stat.st_mtime))
                        })
            
            # 按修改时间排序（最新的在前）
            if detailed:
                files.sort(key=lambda x: x['modified'], reverse=True)
            
            return {
                'count': len(files),
                'total_size_mb': total_size,
                'latest_file': latest_file,
                'files': files
            }
            
        except Exception as e:
            logger.error(f"❌ 获取文件信息失败: {e}")
            return {'count': 0, 'total_size_mb': 0, 'latest_file': '错误', 'files': []}

    def _generate_mini_progress_bar(self, progress: int, length: int = 10) -> str:
        """生成迷你进度条"""
        filled = int(length * progress / 100)
        bar = '█' * filled + '░' * (length - filled)
        return f"[{bar}]"
