# -*- coding: utf-8 -*-
"""
Telegram路由 - 机器人webhook和API接口
"""

import logging
import re
import os
import time
from pathlib import Path
from flask import Blueprint, request, jsonify
from core.auth import auth_required
from core.config import get_config

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)


# ==================== 现代化 API 端点 ====================

@telegram_bp.route('/api/test-message', methods=['POST'])
@auth_required
def send_test_message_modern():
    """发送测试消息 - 现代化版本"""
    try:
        from .notifier import get_telegram_notifier

        data = request.get_json() or {}
        message = data.get('message', '🤖 这是一条测试消息')

        notifier = get_telegram_notifier()

        if not notifier.is_enabled():
            return jsonify({
                'success': False,
                'error': 'Telegram 未启用'
            }), 400

        success = notifier.send_message(message)

        if success:
            return jsonify({
                'success': True,
                'message': '测试消息发送成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '消息发送失败'
            }), 400

    except Exception as e:
        logger.error(f'发送测试消息失败: {e}')
        return jsonify({'error': '发送失败'}), 500


# ==================== Webhook 接收端点 ====================

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Telegram Webhook接收端点"""
    try:
        logger.info("=== 收到 Telegram Webhook 请求 ===")
        logger.info(f"请求头: {dict(request.headers)}")
        logger.info(f"请求来源: {request.remote_addr}")

        # 获取配置
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()
        
        if not config or not config.get('enabled'):
            logger.warning("Telegram未启用，拒绝请求")
            return jsonify({'error': 'Telegram未启用'}), 403

        # 解析消息
        update = request.get_json()
        logger.info(f"收到的更新数据: {update}")

        if not update:
            logger.error("无效的消息格式")
            return jsonify({'error': '无效的消息格式'}), 400

        # 使用现代化路由处理器
        try:
            from modules.telegram.modern_routes import get_modern_telegram_router
            router = get_modern_telegram_router()
            result = router.process_telegram_message(update, config)
        except ImportError:
            # 回退到传统处理方式
            result = _process_telegram_message(update, config)
        logger.info(f"消息处理结果: {result}")

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        logger.error(f'Telegram webhook处理失败: {e}')
        return jsonify({'error': '处理失败'}), 500


def _process_telegram_message(update, config):
    """处理Telegram消息"""
    try:
        # 提取消息
        message = update.get('message')
        if not message:
            return {'action': 'ignored', 'reason': '非消息更新'}

        # 检查chat_id
        chat_id = str(message.get('chat', {}).get('id', ''))
        expected_chat_id = str(config.get('chat_id', ''))
        
        if chat_id != expected_chat_id:
            logger.warning(f"未授权的chat_id: {chat_id}, 期望: {expected_chat_id}")
            return {'action': 'ignored', 'reason': '未授权的聊天'}

        # 获取用户信息
        user = message.get('from', {})
        username = user.get('username', user.get('first_name', '未知用户'))
        logger.info(f"消息来自: {username} (ID: {user.get('id')})")

        # 获取消息文本
        text = message.get('text', '').strip()
        logger.info(f"消息内容: '{text}'")

        if not text:
            return {'action': 'ignored', 'reason': '空消息'}

        # 处理命令
        if text.startswith('/'):
            return _handle_command(text, config)

        # 检查是否为数字选择（分辨率选择）
        if text.isdigit():
            return _handle_quality_selection(int(text), config, chat_id)

        # 使用智能消息解析器
        from .services.message_parser import get_message_parser
        parser = get_message_parser()
        parsed_result = parser.parse_message(text)

        # 检查是否包含有效URL
        if not parsed_result['url'] or not parser.validate_url(parsed_result['url']):
            # 发送帮助信息
            _send_help_message(config)
            return {'action': 'help_sent', 'message': '已发送帮助信息'}

        # 处理下载链接 - 传递自定义文件名
        return _handle_url_with_quality_selection(parsed_result['url'], config, parsed_result['custom_filename'])
            
    except Exception as e:
        logger.error(f'处理Telegram消息失败: {e}')
        return {'action': 'error', 'error': str(e)}


def _handle_command(command, config):
    """处理命令"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        if command.startswith('/start'):
            help_text = """🤖 **YT-DLP Web 机器人**

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
/send <序号|文件名> - 发送指定文件
/delete <序号|文件名> - 删除指定文件
/cleanup - 清理7天前的旧文件

**🔧 调试命令：**
/debug - 查看调试信息

**示例：**
`https://www.youtube.com/watch?v=dQw4w9WgXcQ`
`/cancel a1b2c3d4`
`/send 4` 或 `/send 星巴克`"""

            notifier.send_message(help_text)
            return {'action': 'command_processed', 'command': 'start'}
            
        elif command.startswith('/status'):
            # 获取真实系统状态

            # 先获取基础信息（不依赖psutil）
            try:
                # 获取下载任务状态
                from modules.downloader.manager import get_download_manager
                download_manager = get_download_manager()
                downloads = download_manager.get_all_downloads()
                active_count = len([d for d in downloads if d['status'] in ['pending', 'downloading']])

                # 获取服务器URL
                server_url = os.getenv('SERVER_URL', 'http://localhost:8090')
                if server_url == 'http://localhost:8090':
                    try:
                        from flask import request
                        if request:
                            server_url = request.url_root.rstrip('/')
                    except:
                        pass

                # 尝试使用psutil获取系统信息
                try:
                    import psutil

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

                    status_text = f"""🖥️ **VPS系统状态**

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

                except ImportError:
                    # 如果没有psutil，显示简化版本
                    status_text = f"""📊 **系统状态**

⚠️ **系统监控模块未安装**
请安装 psutil: `pip install psutil`

🔄 **活跃下载**: {active_count}
🤖 **机器人状态**: 正常运行

🌐 **管理面板**:
`{server_url}`"""

                except Exception as e:
                    # psutil相关错误
                    status_text = f"""❌ **获取系统状态失败**

错误: {str(e)}

🔄 **活跃下载**: {active_count}
🤖 **机器人状态**: 正常运行

🌐 **管理面板**:
`{server_url}`"""

            except Exception as e:
                # 基础信息获取失败
                server_url = "未知"
                status_text = f"""❌ **系统状态获取失败**

错误: {str(e)}

🤖 **机器人状态**: 正常运行"""

            notifier.send_message(status_text)
            return {'action': 'command_processed', 'command': 'status'}
            
        elif command.startswith('/downloads'):
            # 获取最近下载 - 增强版本
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            downloads = download_manager.get_all_downloads()

            recent_downloads = downloads[:10]  # 最近10个

            if not recent_downloads:
                downloads_text = "📋 **下载任务列表**\n\n暂无下载记录"
            else:
                downloads_text = "📋 **下载任务列表**\n\n"
                active_count = 0

                for i, download in enumerate(recent_downloads, 1):
                    status = download['status']
                    status_emoji = {
                        'pending': '⏳',
                        'downloading': '🔄',
                        'completed': '✅',
                        'failed': '❌',
                        'cancelled': '🚫'
                    }.get(status, '❓')

                    title = download.get('title', 'Unknown')[:25]
                    download_id_short = download['id'][:8]

                    if status in ['pending', 'downloading']:
                        active_count += 1
                        progress = download.get('progress', 0)
                        downloads_text += f"{i}. {status_emoji} **{title}** ({progress}%)\n"
                        downloads_text += f"   📋 ID: `{download_id_short}` • `/cancel {download_id_short}`\n\n"
                    else:
                        downloads_text += f"{i}. {status_emoji} {title}\n"
                        if status == 'completed':
                            file_size = download.get('file_size', 0)
                            if file_size:
                                size_mb = file_size / (1024 * 1024)
                                downloads_text += f"   💾 {size_mb:.1f} MB\n"
                        downloads_text += "\n"

                if active_count > 0:
                    downloads_text += f"🔄 **活跃任务**: {active_count} 个\n"
                    downloads_text += "💡 使用 `/cancel <ID>` 取消下载"

            notifier.send_message(downloads_text)
            return {'action': 'command_processed', 'command': 'downloads'}

        elif command.startswith('/files'):
            # 获取文件列表 - 增强版本

            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

            # 添加调试信息
            debug_info = f"""🔍 **调试信息**:
📂 配置路径: `{get_config('downloader.output_dir', 'data/downloads')}`
📂 实际路径: `{download_dir.absolute()}`
📂 路径存在: `{download_dir.exists()}`
📂 当前工作目录: `{os.getcwd()}`

"""

            if not download_dir.exists():
                files_text = f"📁 **文件管理**\n\n❌ 下载文件夹不存在\n\n{debug_info}"
            else:
                try:
                    files = []
                    total_size = 0

                    for file_path in download_dir.iterdir():
                        if file_path.is_file():
                            stat = file_path.stat()
                            files.append({
                                'name': file_path.name,
                                'path': str(file_path),
                                'size': stat.st_size,
                                'modified': stat.st_mtime
                            })
                            total_size += stat.st_size

                    # 按修改时间倒序排列，取最近8个
                    files.sort(key=lambda x: x['modified'], reverse=True)
                    recent_files = files[:8]

                    if not recent_files:
                        files_text = f"📁 **文件管理**\n\n暂无下载文件\n\n{debug_info}"
                    else:
                        total_size_mb = total_size / (1024 * 1024)
                        files_text = f"📁 **文件管理** (共{len(files)}个文件，{total_size_mb:.1f} MB)\n\n"

                        for i, file_info in enumerate(recent_files, 1):
                            name = file_info['name'][:25]
                            size_mb = file_info['size'] / (1024 * 1024)

                            # 文件类型图标
                            ext = Path(file_info['name']).suffix.lower()
                            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm']:
                                icon = '🎬'
                            elif ext in ['.mp3', '.wav', '.flac', '.m4a']:
                                icon = '🎵'
                            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                                icon = '🖼️'
                            else:
                                icon = '📄'

                            files_text += f"{i}. {icon} **{name}**\n"
                            files_text += f"   💾 {size_mb:.1f} MB\n\n"

                        if len(files) > 8:
                            files_text += f"... 还有 {len(files) - 8} 个文件\n\n"

                        files_text += "💡 **文件操作**:\n"
                        files_text += "• `/send <序号|文件名>` - 发送文件\n"
                        files_text += "• `/delete <序号|文件名>` - 删除文件\n"
                        files_text += "• `/cleanup` - 清理旧文件\n\n"
                        files_text += "📝 **使用示例**:\n"
                        files_text += "• `/send 4` - 发送第4个文件\n"
                        files_text += "• `/send 星巴克` - 发送包含'星巴克'的文件"

                except Exception as e:
                    files_text = f"📁 **文件管理**\n\n❌ 读取失败: {str(e)}"

            notifier.send_message(files_text)
            return {'action': 'command_processed', 'command': 'files'}

        elif command.startswith('/debug'):
            # 调试命令 - 显示详细信息
            import os
            import sys

            debug_text = f"""🔍 **调试信息**

**Python版本**: {sys.version.split()[0]}

**环境变量**:
SERVER_URL = `{os.getenv('SERVER_URL', '未设置')}`

**Telegram配置**:"""

            # 检查Telegram配置
            try:
                from modules.telegram.services.config_service import TelegramConfigService
                telegram_config = TelegramConfigService()
                config_data = telegram_config.get_config()

                if config_data:
                    debug_text += f"""
✅ Telegram已配置
• 启用状态: {config_data.get('enabled', False)}
• Bot Token: {'已设置' if config_data.get('bot_token') else '未设置'}
• Chat ID: {'已设置' if config_data.get('chat_id') else '未设置'}
• 推送模式: {config_data.get('push_mode', 'file')}
• 文件大小限制: {config_data.get('file_size_limit', 50)}MB"""
                else:
                    debug_text += "\n❌ Telegram配置未找到"
            except Exception as e:
                debug_text += f"\n❌ 获取Telegram配置失败: {e}"

            debug_text += "\n\n**事件监听器检查**:"

            # 检查事件监听器
            try:
                from core.events import event_bus
                listeners = event_bus._listeners

                download_completed_listeners = listeners.get('download.completed', [])
                debug_text += f"""
• DOWNLOAD_COMPLETED监听器: {len(download_completed_listeners)} 个
• 监听器函数: {[func.__name__ for func in download_completed_listeners]}
• 总事件类型: {len(listeners)} 个"""

                # 检查Telegram通知器状态
                from modules.telegram.notifier import get_telegram_notifier
                notifier = get_telegram_notifier()
                if notifier:
                    debug_text += f"""
• Telegram通知器: 已创建
• 通知器启用: {notifier.is_enabled()}
• 上传器可用: {bool(notifier.uploader)}"""
                else:
                    debug_text += "\n• Telegram通知器: 未创建"

            except Exception as e:
                debug_text += f"\n❌ 检查事件监听器失败: {e}"

            debug_text += "\n\n**psutil检查**:"

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

            debug_text += "\n\n**Flask请求信息**:"
            try:
                from flask import request
                if request:
                    debug_text += f"""
url_root = `{request.url_root}`
host = `{request.host}`
scheme = `{request.scheme}`"""
                else:
                    debug_text += "\n❌ 无法获取request对象"
            except Exception as e:
                debug_text += f"\n❌ 获取请求信息失败: {e}"

            # 显示最终使用的URL
            server_url = os.getenv('SERVER_URL', 'http://localhost:8090')
            if server_url == 'http://localhost:8090':
                try:
                    from flask import request
                    if request:
                        server_url = request.url_root.rstrip('/')
                except:
                    pass

            debug_text += f"""

**最终URL**: `{server_url}`

**代码版本检查**:"""

            # 检查代码是否包含新功能
            try:
                import inspect
                source = inspect.getsource(lambda: None).__class__.__module__
                debug_text += f"\n模块路径: {source}"

                # 检查当前函数源码
                current_func = inspect.currentframe().f_code
                debug_text += f"\n当前函数: {current_func.co_name}"
                debug_text += f"\n行号: {current_func.co_firstlineno}"

            except Exception as e:
                debug_text += f"\n代码检查失败: {e}"

            notifier.send_message(debug_text)
            return {'action': 'command_processed', 'command': 'debug'}

        elif command.startswith('/cancel'):
            # 取消下载命令
            parts = command.split()
            if len(parts) < 2:
                notifier.send_message("❌ 用法: `/cancel <下载ID>`\n💡 使用 `/downloads` 查看活跃下载")
                return {'action': 'command_error', 'error': 'missing_download_id'}

            download_id_short = parts[1]

            # 查找完整的下载ID
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            downloads = download_manager.get_all_downloads()

            target_download = None
            for download in downloads:
                if download['id'].startswith(download_id_short):
                    target_download = download
                    break

            if not target_download:
                notifier.send_message(f"❌ 未找到下载任务: `{download_id_short}`\n💡 使用 `/downloads` 查看活跃下载")
                return {'action': 'command_error', 'error': 'download_not_found'}

            if target_download['status'] not in ['pending', 'downloading']:
                status_text = {
                    'completed': '已完成',
                    'failed': '已失败',
                    'cancelled': '已取消'
                }.get(target_download['status'], '未知状态')
                notifier.send_message(f"❌ 无法取消下载: 任务{status_text}")
                return {'action': 'command_error', 'error': 'cannot_cancel'}

            # 执行取消
            success = download_manager.cancel_download(target_download['id'])
            if success:
                title = target_download.get('title', 'Unknown')[:30]
                notifier.send_message(f"✅ **下载已取消**\n\n📹 **{title}**\n📋 **ID**: `{download_id_short}`")
                return {'action': 'command_processed', 'command': 'cancel', 'download_id': target_download['id']}
            else:
                notifier.send_message(f"❌ 取消下载失败: `{download_id_short}`")
                return {'action': 'command_error', 'error': 'cancel_failed'}

        elif command.startswith('/send'):
            # 发送文件命令 - 支持序号和文件名
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                notifier.send_message("❌ 用法: `/send <序号|文件名>`\n💡 使用 `/files` 查看可用文件")
                return {'action': 'command_error', 'error': 'missing_filename'}

            identifier = parts[1].strip()

            # 查找文件
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

            if not download_dir.exists():
                notifier.send_message("❌ 下载文件夹不存在")
                return {'action': 'command_error', 'error': 'dir_not_exists'}

            # 获取文件列表（按修改时间排序）
            files = []
            for file_path in download_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        'path': file_path,
                        'name': file_path.name,
                        'modified': stat.st_mtime
                    })

            files.sort(key=lambda x: x['modified'], reverse=True)

            target_file = None

            # 检查是否为序号
            if identifier.isdigit():
                index = int(identifier) - 1  # 转换为0基索引
                if 0 <= index < len(files):
                    target_file = files[index]['path']
                else:
                    notifier.send_message(f"❌ 序号超出范围: `{identifier}`\n💡 有效范围: 1-{len(files)}")
                    return {'action': 'command_error', 'error': 'invalid_index'}
            else:
                # 按文件名搜索（支持部分匹配）
                for file_info in files:
                    file_path = file_info['path']
                    if (file_path.name == identifier or
                        identifier.lower() in file_path.name.lower()):
                        target_file = file_path
                        break

            if not target_file:
                notifier.send_message(f"❌ 未找到文件: `{identifier}`\n💡 使用 `/files` 查看可用文件和序号")
                return {'action': 'command_error', 'error': 'file_not_found'}

            # 发送文件
            file_size_mb = target_file.stat().st_size / (1024 * 1024)
            caption = f"📁 **文件**: {target_file.name}\n💾 **大小**: {file_size_mb:.1f} MB"

            # 检查文件大小并提供预警（使用配置的限制）
            from modules.telegram.services.config_service import get_telegram_config_service
            config_service = get_telegram_config_service()
            file_size_limit = config_service.get_file_size_limit()

            if file_size_mb > file_size_limit:
                # 检查是否有PyrogramMod支持
                from modules.telegram.notifier import get_telegram_notifier
                notifier_instance = get_telegram_notifier()
                uploader = getattr(notifier_instance, 'uploader', None)

                if uploader and hasattr(uploader, 'pyrogram_uploader') and uploader.pyrogram_uploader:
                    # 有PyrogramMod支持，正常发送
                    notifier.send_message(f"📤 **准备发送大文件** ({file_size_mb:.1f}MB > {file_size_limit}MB)\n⏳ 请稍候，大文件上传需要更多时间...")
                else:
                    # 没有PyrogramMod支持，提前告知用户
                    notifier.send_message(f"⚠️ **大文件警告** ({file_size_mb:.1f}MB > {file_size_limit}MB)\n\n文件超过{file_size_limit}MB，可能发送失败。建议配置PyrogramMod以支持大文件传输。")

            success = notifier.send_file(str(target_file), caption)
            if success:
                notifier.send_message(f"✅ 文件发送成功: **{target_file.name[:30]}...**")
                return {'action': 'command_processed', 'command': 'send', 'filename': target_file.name}
            else:
                # 发送失败，但大文件处理提示已经在uploader中发送了
                if file_size_mb <= 50:
                    notifier.send_message(f"❌ 文件发送失败: **{target_file.name[:30]}...**")
                return {'action': 'command_error', 'error': 'send_failed'}

        elif command.startswith('/delete'):
            # 删除文件命令 - 支持序号和文件名
            parts = command.split(maxsplit=1)
            if len(parts) < 2:
                notifier.send_message("❌ 用法: `/delete <序号|文件名>`\n💡 使用 `/files` 查看可用文件")
                return {'action': 'command_error', 'error': 'missing_filename'}

            identifier = parts[1].strip()

            # 查找文件
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

            if not download_dir.exists():
                notifier.send_message("❌ 下载文件夹不存在")
                return {'action': 'command_error', 'error': 'dir_not_exists'}

            # 获取文件列表（按修改时间排序）
            files = []
            for file_path in download_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        'path': file_path,
                        'name': file_path.name,
                        'modified': stat.st_mtime
                    })

            files.sort(key=lambda x: x['modified'], reverse=True)

            target_file = None

            # 检查是否为序号
            if identifier.isdigit():
                index = int(identifier) - 1  # 转换为0基索引
                if 0 <= index < len(files):
                    target_file = files[index]['path']
                else:
                    notifier.send_message(f"❌ 序号超出范围: `{identifier}`\n💡 有效范围: 1-{len(files)}")
                    return {'action': 'command_error', 'error': 'invalid_index'}
            else:
                # 按文件名搜索（支持部分匹配）
                for file_info in files:
                    file_path = file_info['path']
                    if (file_path.name == identifier or
                        identifier.lower() in file_path.name.lower()):
                        target_file = file_path
                        break

            if not target_file:
                notifier.send_message(f"❌ 未找到文件: `{identifier}`\n💡 使用 `/files` 查看可用文件和序号")
                return {'action': 'command_error', 'error': 'file_not_found'}

            # 删除文件
            try:
                file_size_mb = target_file.stat().st_size / (1024 * 1024)
                file_name = target_file.name
                target_file.unlink()
                notifier.send_message(f"✅ **文件已删除**\n\n📄 **{file_name[:30]}...**\n💾 **释放空间**: {file_size_mb:.1f} MB")
                return {'action': 'command_processed', 'command': 'delete', 'filename': file_name}
            except Exception as e:
                notifier.send_message(f"❌ 删除文件失败: {str(e)}")
                return {'action': 'command_error', 'error': 'delete_failed'}

        elif command.startswith('/cleanup'):
            # 清理旧文件命令
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

            if not download_dir.exists():
                notifier.send_message("❌ 下载文件夹不存在")
                return {'action': 'command_error', 'error': 'dir_not_exists'}

            # 清理7天前的文件
            cutoff_time = time.time() - (7 * 24 * 3600)  # 7天
            deleted_files = []
            freed_space = 0

            try:
                for file_path in download_dir.iterdir():
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_files.append(file_path.name)
                        freed_space += file_size

                if deleted_files:
                    freed_mb = freed_space / (1024 * 1024)
                    cleanup_text = f"✅ **清理完成**\n\n🗑️ **删除文件**: {len(deleted_files)} 个\n💾 **释放空间**: {freed_mb:.1f} MB\n\n"

                    if len(deleted_files) <= 5:
                        cleanup_text += "**删除的文件**:\n"
                        for filename in deleted_files:
                            cleanup_text += f"• {filename[:30]}\n"
                    else:
                        cleanup_text += f"**删除的文件**: {deleted_files[0][:30]} 等 {len(deleted_files)} 个文件"
                else:
                    cleanup_text = "✅ **清理完成**\n\n没有需要清理的文件（7天内的文件保留）"

                notifier.send_message(cleanup_text)
                return {'action': 'command_processed', 'command': 'cleanup', 'deleted_count': len(deleted_files)}

            except Exception as e:
                notifier.send_message(f"❌ 清理失败: {str(e)}")
                return {'action': 'command_error', 'error': 'cleanup_failed'}

        else:
            # 未知命令
            notifier.send_message("❓ 未知命令，发送 /start 查看帮助")
            return {'action': 'unknown_command', 'command': command}
            
    except Exception as e:
        logger.error(f"处理命令失败: {e}")
        return {'action': 'command_error', 'error': str(e)}


def _handle_url_with_quality_selection(url, config, custom_filename=None):
    """处理URL并显示分辨率选择菜单"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        # 如果有自定义文件名，显示提示
        if custom_filename:
            notifier.send_message(f"📝 检测到自定义文件名: **{custom_filename}**")

        # 发送"正在获取视频信息"的消息
        notifier.send_message("🔍 正在获取视频信息，请稍候...")

        # 获取视频信息
        video_info = _get_video_info(url)

        if not video_info:
            notifier.send_message("❌ 无法获取视频信息，请检查链接是否有效")
            return {'action': 'video_info_failed', 'url': url}

        # 发送视频信息和分辨率选择菜单
        _send_quality_selection_menu(url, video_info, config, custom_filename)

        return {'action': 'quality_menu_sent', 'url': url, 'video_info': video_info, 'custom_filename': custom_filename}

    except Exception as e:
        logger.error(f"处理URL失败: {e}")
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()
        notifier.send_message(f"❌ 处理失败: {str(e)}")
        return {'action': 'url_error', 'error': str(e)}


def _get_video_info(url):
    """获取视频信息 - 使用统一API"""
    try:
        from modules.downloader.api import get_unified_download_api
        api = get_unified_download_api()

        # 使用统一API的智能回退机制
        result = api.get_video_info(url)

        if result['success']:
            data = result['data']
            return {
                'title': data['title'],
                'duration': data['duration'],
                'uploader': data['uploader'],
                'formats': data.get('formats', [])
            }
        else:
            raise Exception(result['error'])

    except Exception as e:
        logger.error(f"获取视频信息失败: {e}")
        raise


def _send_quality_selection_menu(url, video_info, config, custom_filename=None):
    """发送分辨率选择菜单"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        title = video_info.get('title', 'Unknown')[:50]
        duration = video_info.get('duration', 0)
        uploader = video_info.get('uploader', 'Unknown')

        # 格式化时长
        if duration:
            # 确保duration是数字类型并转换为整数
            duration_int = int(float(duration))
            minutes = duration_int // 60
            seconds = duration_int % 60
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "未知"

        # 分析可用格式并生成选择菜单
        quality_options = _analyze_available_qualities(video_info.get('formats', []))

        menu_text = f"""📹 **视频信息**

🎬 **标题**: {title}
👤 **作者**: {uploader}
⏱️ **时长**: {duration_str}"""

        # 如果有自定义文件名，显示在菜单中
        if custom_filename:
            menu_text += f"\n📝 **自定义文件名**: {custom_filename}"

        menu_text += f"""

📊 **可用分辨率**:
"""

        # 添加分辨率选项
        for i, option in enumerate(quality_options, 1):
            menu_text += f"{i}. {option['display']} ({option['size_info']})\n"

        menu_text += f"""
💡 **使用方法**:
回复数字选择分辨率，例如: `1`

🔗 **原链接**: {url}"""

        notifier.send_message(menu_text)

        # 存储选择状态（包含自定义文件名）
        _store_selection_state(config.get('chat_id'), url, video_info, quality_options, custom_filename)

    except Exception as e:
        logger.error(f"发送分辨率菜单失败: {e}")


def _analyze_available_qualities(formats):
    """分析可用的视频质量"""
    try:
        quality_map = {}

        for fmt in formats:
            height = fmt.get('height')
            if not height:
                continue

            # 分类分辨率
            if height >= 2160:
                quality_key = '4K'
                quality_display = f"4K ({height}p)"
            elif height >= 1440:
                quality_key = '1440p'
                quality_display = f"2K ({height}p)"
            elif height >= 1080:
                quality_key = '1080p'
                quality_display = f"1080p"
            elif height >= 720:
                quality_key = '720p'
                quality_display = f"720p"
            elif height >= 480:
                quality_key = '480p'
                quality_display = f"480p"
            elif height >= 360:
                quality_key = '360p'
                quality_display = f"360p"
            else:
                continue

            # 获取文件大小信息
            filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
            if filesize:
                size_mb = filesize / (1024 * 1024)
                size_info = f"~{size_mb:.1f}MB"
            else:
                size_info = "大小未知"

            # 保存最佳格式
            if quality_key not in quality_map or fmt.get('tbr', 0) > quality_map[quality_key].get('tbr', 0):
                quality_map[quality_key] = {
                    'display': quality_display,
                    'size_info': size_info,
                    'format_id': fmt.get('format_id'),
                    'quality_key': quality_key,
                    'height': height
                }

        # 按分辨率排序（从高到低）
        sorted_qualities = sorted(quality_map.values(), key=lambda x: x['height'], reverse=True)

        # 添加音频选项
        sorted_qualities.append({
            'display': '仅音频 (MP3)',
            'size_info': '音频文件',
            'format_id': 'audio_only',
            'quality_key': 'audio',
            'height': 0
        })

        return sorted_qualities[:6]  # 最多6个选项

    except Exception as e:
        logger.error(f"分析视频质量失败: {e}")
        return [
            {'display': '最高质量', 'size_info': '自动选择', 'format_id': 'best', 'quality_key': 'high', 'height': 9999},
            {'display': '中等质量 (720p)', 'size_info': '推荐', 'format_id': 'medium', 'quality_key': 'medium', 'height': 720},
            {'display': '低质量 (360p)', 'size_info': '节省流量', 'format_id': 'low', 'quality_key': 'low', 'height': 360}
        ]


def _store_selection_state(chat_id, url, video_info, quality_options, custom_filename=None):
    """存储选择状态（简单实现）"""
    try:
        # 这里应该存储到数据库或缓存中
        # 简单实现：存储到全局变量（实际项目中应该用Redis或数据库）
        global _selection_states
        if '_selection_states' not in globals():
            _selection_states = {}

        _selection_states[str(chat_id)] = {
            'url': url,
            'video_info': video_info,
            'quality_options': quality_options,
            'custom_filename': custom_filename,  # 添加自定义文件名
            'timestamp': __import__('time').time()
        }

    except Exception as e:
        logger.error(f"存储选择状态失败: {e}")


def _handle_quality_selection(selection, config, chat_id):
    """处理用户的分辨率选择"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        # 获取存储的选择状态
        global _selection_states
        if '_selection_states' not in globals():
            _selection_states = {}

        state = _selection_states.get(str(chat_id))
        if not state:
            notifier.send_message("❌ 选择已过期，请重新发送视频链接")
            return {'action': 'selection_expired'}

        # 检查选择是否有效
        quality_options = state.get('quality_options', [])
        if selection < 1 or selection > len(quality_options):
            notifier.send_message(f"❌ 无效选择，请输入 1-{len(quality_options)} 之间的数字")
            return {'action': 'invalid_selection', 'selection': selection}

        # 获取选择的质量选项
        selected_option = quality_options[selection - 1]
        url = state['url']
        video_info = state['video_info']
        custom_filename = state.get('custom_filename')  # 获取自定义文件名

        # 清除选择状态
        del _selection_states[str(chat_id)]

        # 发送确认消息
        confirm_msg = f"✅ 已选择: {selected_option['display']}"
        if custom_filename:
            confirm_msg += f"\n📝 文件名: {custom_filename}"
        confirm_msg += "\n⏳ 开始下载..."
        notifier.send_message(confirm_msg)

        # 开始下载（传递自定义文件名）
        return _start_download_with_quality(url, selected_option, config, video_info, custom_filename)

    except Exception as e:
        logger.error(f"处理质量选择失败: {e}")
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()
        notifier.send_message(f"❌ 处理选择失败: {str(e)}")
        return {'action': 'selection_error', 'error': str(e)}


def _start_download_with_quality(url, quality_option, config, video_info, custom_filename=None):
    """根据选择的质量开始下载"""
    try:
        from modules.downloader.api import get_unified_download_api
        api = get_unified_download_api()

        # 构建下载选项
        download_options = {
            'telegram_push': True,
            'telegram_push_mode': config.get('push_mode', 'file'),
            'source': 'telegram_webhook',
        }

        # 添加自定义文件名
        if custom_filename:
            download_options['custom_filename'] = custom_filename

        # 根据选择设置质量（智能格式选择器兼容）
        quality_key = quality_option.get('quality_key', 'high')
        if quality_key == 'audio':
            download_options['audio_only'] = True
            download_options['quality'] = '1080p'  # 音频下载时的视频质量基准
        elif quality_key == 'high':
            download_options['quality'] = '1080p'  # 高质量 -> 1080p
        elif quality_key == 'medium':
            download_options['quality'] = '720p'   # 中等质量 -> 720p
        elif quality_key == 'low':
            download_options['quality'] = '480p'   # 低质量 -> 480p
        elif quality_key == '4k':
            download_options['quality'] = '4K'     # 4K质量
        else:
            # 自定义格式或其他情况
            format_id = quality_option.get('format_id')
            if format_id and format_id not in ['best', 'medium', 'low']:
                download_options['format'] = format_id
            download_options['quality'] = '1080p'  # 默认1080p

        # 使用统一API创建下载任务
        result = api.create_download(url, download_options)

        if not result['success']:
            raise Exception(result['error'])

        download_id = result['data']['download_id']

        # 发送确认消息
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        title = video_info.get('title', 'Unknown')[:50]
        confirm_text = f"""🎬 **下载已开始**

📹 **视频**: {title}
📊 **质量**: {quality_option['display']}
📋 **任务ID**: `{download_id}`

⏳ 下载完成后会自动发送文件给您！"""

        notifier.send_message(confirm_text)

        return {
            'action': 'download_started',
            'download_id': download_id,
            'url': url,
            'quality': quality_option
        }

    except Exception as e:
        logger.error(f"开始下载失败: {e}")
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()
        notifier.send_message(f"❌ 下载失败: {str(e)}")
        return {'action': 'download_error', 'error': str(e)}


def _handle_download_request(url, config):
    """处理下载请求"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        # 构建下载选项（智能格式选择器兼容）
        download_options = {
            'telegram_push': True,
            'telegram_push_mode': config.get('push_mode', 'file'),
            'source': 'telegram_webhook',
            'quality': '1080p'  # 默认1080p（智能格式选择器）
        }

        # 创建下载任务
        download_id = download_manager.create_download(url, download_options)

        # 发送确认消息
        _send_confirmation_message(url, config, download_id=download_id)
        
        return {
            'action': 'download_started',
            'download_id': download_id,
            'url': url
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理下载请求失败: {error_msg}")

        # 发送错误消息
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        # 根据错误类型提供不同的建议
        if 'cookies' in error_msg.lower() or 'bot' in error_msg.lower():
            error_text = f"""❌ **下载失败 - 需要身份验证**

🔗 **链接**: {url}
⚠️ **错误**: {error_msg}

💡 **解决方案**:
1. 访问 Cookies 管理页面
2. 上传对应网站的 Cookies
3. 重新发送链接下载

📖 **获取Cookies教程**:
使用浏览器扩展或开发者工具导出cookies"""
        else:
            error_text = f"""❌ **下载失败**

🔗 **链接**: {url}
⚠️ **错误**: {error_msg}

💡 **建议**:
• 检查链接是否有效
• 稍后重试
• 联系管理员"""

        notifier.send_message(error_text)

        return {'action': 'download_error', 'error': error_msg}


def _send_help_message(config):
    """发送帮助信息"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        help_text = """🤖 **YT-DLP Web 机器人**

欢迎使用！我可以帮您下载视频。

**使用方法：**
• 直接发送视频链接，我会自动下载并发送给您
• 支持 YouTube、Bilibili、Twitter 等 1000+ 网站

**命令列表：**
/start - 显示此帮助信息
/status - 查看系统状态
/downloads - 查看下载任务列表
/files - 查看已下载文件列表
/debug - 查看调试信息

**示例：**
`https://www.youtube.com/watch?v=dQw4w9WgXcQ`"""

        notifier.send_message(help_text)

    except Exception as e:
        logger.error(f"发送帮助信息失败: {e}")


def _send_confirmation_message(url, config, download_id=None, auto_download=True):
    """发送确认消息"""
    try:
        from .notifier import get_telegram_notifier
        notifier = get_telegram_notifier()
        
        if auto_download and download_id:
            confirm_text = f"""✅ **下载已开始**

🔗 **链接**: {url}
📋 **任务ID**: `{download_id}`

⏳ 下载完成后会自动发送文件给您！"""
        else:
            confirm_text = f"""📥 **收到下载链接**

🔗 {url}

⚠️ 自动下载已禁用，请手动在网页端开始下载。"""
        
        notifier.send_message(confirm_text)
        
    except Exception as e:
        logger.error(f"发送确认消息失败: {e}")


def _is_valid_url(text):
    """验证URL格式"""
    try:
        # 基本URL格式检查
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(text))
        
    except Exception:
        return False


# ==================== API接口 ====================

@telegram_bp.route('/api/setup-webhook', methods=['POST'])
@auth_required
def setup_webhook():
    """设置Telegram Webhook"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 获取请求数据
        request_data = request.get_json() or {}
        custom_webhook_url = request_data.get('webhook_url')

        # 构建 Webhook URL
        if custom_webhook_url and custom_webhook_url.strip():
            webhook_url = custom_webhook_url.strip()
            logger.info(f'使用自定义 Webhook URL: {webhook_url}')
        else:
            # 使用默认URL，但检查是否为HTTPS
            base_url = request.url_root.rstrip('/')
            if base_url.startswith('http://'):
                # 如果是HTTP，给出警告但仍然尝试设置
                logger.warning("⚠️ 检测到HTTP协议，Telegram要求HTTPS，可能会失败")
            webhook_url = base_url + '/telegram/webhook'
            logger.info(f'使用默认 Webhook URL: {webhook_url}')

        # 验证URL格式
        if not webhook_url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'error': 'Webhook URL格式无效，必须以http://或https://开头'
            }), 400

        # 设置webhook
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

        webhook_data = {'url': webhook_url}

        logger.info(f"🔄 正在设置Webhook: {webhook_url}")
        response = requests.post(telegram_api_url, json=webhook_data, timeout=30)

        # 详细记录响应
        logger.info(f"📡 Telegram API响应状态: {response.status_code}")
        logger.info(f"📡 Telegram API响应内容: {response.text}")

        response.raise_for_status()
        result = response.json()

        if result.get('ok'):
            logger.info(f"✅ Webhook设置成功: {webhook_url}")
            return jsonify({
                'success': True,
                'message': 'Webhook设置成功',
                'webhook_url': webhook_url
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ Webhook设置失败: {error_msg}")

            # 提供更友好的错误信息
            if 'HTTPS' in error_msg.upper():
                error_msg += ' (提示: Telegram要求Webhook URL使用HTTPS协议)'
            elif 'URL' in error_msg.upper():
                error_msg += ' (提示: 请检查URL是否可以从外网访问)'

            return jsonify({
                'success': False,
                'error': f'Webhook设置失败: {error_msg}'
            }), 400

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 网络请求失败: {e}")
        return jsonify({
            'success': False,
            'error': f'网络请求失败: {str(e)}'
        }), 500
    except Exception as e:
        logger.error(f"❌ 设置Webhook失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/api/delete-webhook', methods=['POST'])
@auth_required
def delete_webhook():
    """删除Telegram Webhook"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 删除webhook
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

        response = requests.post(telegram_api_url, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get('ok'):
            logger.info("✅ Webhook删除成功")
            return jsonify({
                'success': True,
                'message': 'Webhook删除成功'
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ Webhook删除失败: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'Webhook删除失败: {error_msg}'
            }), 400

    except Exception as e:
        logger.error(f"❌ 删除Webhook失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/api/webhook-info', methods=['GET'])
@auth_required
def get_webhook_info():
    """获取Telegram Webhook信息"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 获取webhook信息
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

        response = requests.get(telegram_api_url, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get('ok'):
            logger.info("✅ 获取Webhook信息成功")
            return jsonify({
                'success': True,
                'webhook_info': result.get('result', {})
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ 获取Webhook信息失败: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'获取Webhook信息失败: {error_msg}'
            }), 400

    except Exception as e:
        logger.error(f"❌ 获取Webhook信息失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 异步上传接口 - 学习ytdlbot ====================

@telegram_bp.route('/api/upload/async', methods=['POST'])
@auth_required
def upload_file_async():
    """异步上传文件接口 - 学习ytdlbot的异步策略"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少请求数据'}), 400

        file_path = data.get('file_path')
        caption = data.get('caption', '')

        if not file_path:
            return jsonify({'error': '缺少文件路径'}), 400

        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return jsonify({'error': f'文件不存在: {file_path}'}), 404

        # 获取任务管理器
        try:
            from modules.telegram.tasks import get_task_manager
            task_manager = get_task_manager()

            if not task_manager.is_async_available():
                # SQLite队列总是可用，这种情况不应该发生
                logger.error("❌ SQLite任务队列不可用")
                return jsonify({'error': 'SQLite任务队列不可用'}), 500

            # 提交异步任务
            task_id = task_manager.submit_upload_task(file_path, caption)

            if task_id:
                file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'status': 'queued',
                    'file_path': file_path,
                    'file_size_mb': round(file_size_mb, 2),
                    'message': '上传任务已提交，请使用task_id查询进度'
                })
            else:
                return jsonify({'error': '提交异步任务失败'}), 500

        except ImportError:
            # SQLite队列总是可用，不需要回退
            logger.error("❌ 任务管理器导入失败")
            return jsonify({'error': '任务管理器不可用'}), 500

    except Exception as e:
        logger.error(f"❌ 异步上传接口错误: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/task/<task_id>/status', methods=['GET'])
@auth_required
def get_task_status(task_id):
    """获取任务状态"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        status = task_manager.get_task_status(task_id)
        return jsonify(status)

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取任务状态失败: {e}")
        return jsonify({'error': str(e)}), 500


def upload_file_sync_fallback(file_path: str, caption: str = ''):
    """同步上传回退方案"""
    try:
        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return jsonify({'error': f'文件不存在: {file_path}'}), 404

        # 创建上传器
        from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader
        from modules.telegram.services.config_service import get_telegram_config_service

        config_service = get_telegram_config_service()
        config = config_service.get_config()

        if not config:
            return jsonify({'error': 'Telegram配置未找到'}), 500

        uploader = ModernHybridUploader(config)

        if not uploader.is_available():
            return jsonify({'error': '没有可用的Telegram上传器'}), 500

        # 执行同步上传
        file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
        logger.info(f"📤 开始同步上传: {file_path_obj.name} ({file_size_mb:.1f}MB)")

        result = uploader.send_file(file_path, caption)

        if result:
            return jsonify({
                'success': True,
                'status': 'completed',
                'file_path': file_path,
                'file_size_mb': round(file_size_mb, 2),
                'message': '文件上传成功'
            })
        else:
            return jsonify({'error': '文件上传失败'}), 500

    except Exception as e:
        logger.error(f"❌ 同步上传失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 批量上传和队列管理接口 ====================

@telegram_bp.route('/api/upload/batch', methods=['POST'])
@auth_required
def batch_upload_async():
    """批量异步上传文件接口 - 支持多文件并发上传"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少请求数据'}), 400

        file_paths = data.get('file_paths', [])
        caption = data.get('caption', '')

        if not file_paths:
            return jsonify({'error': '缺少文件路径列表'}), 400

        if not isinstance(file_paths, list):
            return jsonify({'error': 'file_paths必须是数组'}), 400

        # 检查文件是否存在
        valid_files = []
        invalid_files = []

        for file_path in file_paths:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                valid_files.append(file_path)
            else:
                invalid_files.append(file_path)

        if not valid_files:
            return jsonify({'error': '没有有效的文件可以上传'}), 400

        # 获取任务管理器
        try:
            from modules.telegram.tasks import get_task_manager
            task_manager = get_task_manager()

            if not task_manager.is_async_available():
                # SQLite队列总是可用，这种情况不应该发生
                logger.error("❌ SQLite任务队列不可用")
                return jsonify({'error': 'SQLite任务队列不可用'}), 500

            # 提交异步批量任务
            task_id = task_manager.submit_batch_upload_task(valid_files, caption)

            if task_id:
                total_size_mb = sum(Path(f).stat().st_size for f in valid_files) / (1024 * 1024)
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'status': 'queued',
                    'total_files': len(file_paths),
                    'valid_files': len(valid_files),
                    'invalid_files': len(invalid_files),
                    'total_size_mb': round(total_size_mb, 2),
                    'message': '批量上传任务已提交，请使用task_id查询进度'
                })
            else:
                return jsonify({'error': '提交异步批量任务失败'}), 500

        except ImportError:
            # SQLite队列总是可用，不需要回退
            logger.error("❌ 任务管理器导入失败")
            return jsonify({'error': '任务管理器不可用'}), 500

    except Exception as e:
        logger.error(f"❌ 批量上传接口错误: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/status', methods=['GET'])
@auth_required
def get_queue_status():
    """获取上传队列状态"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        status = task_manager.get_queue_status()
        return jsonify(status)

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取队列状态失败: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/tasks', methods=['GET'])
@auth_required
def get_all_tasks():
    """获取所有跟踪的任务"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        tasks = task_manager.get_all_tasks()
        return jsonify({'tasks': tasks, 'total': len(tasks)})

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/cleanup', methods=['POST'])
@auth_required
def cleanup_completed_tasks():
    """清理已完成的任务"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        cleaned_count = task_manager.cleanup_completed_tasks()
        return jsonify({
            'success': True,
            'cleaned_count': cleaned_count,
            'message': f'已清理 {cleaned_count} 个已完成的任务'
        })

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 清理任务失败: {e}")
        return jsonify({'error': str(e)}), 500


def batch_upload_sync_fallback(file_paths: list, caption: str = ''):
    """同步批量上传回退方案"""
    try:
        from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader
        from modules.telegram.services.config_service import get_telegram_config_service

        config_service = get_telegram_config_service()
        config = config_service.get_config()

        if not config:
            return jsonify({'error': 'Telegram配置未找到'}), 500

        uploader = ModernHybridUploader(config)

        if not uploader.is_available():
            return jsonify({'error': '没有可用的Telegram上传器'}), 500

        # 执行同步批量上传
        successful_uploads = []
        failed_uploads = []

        for i, file_path in enumerate(file_paths):
            try:
                logger.info(f"📤 同步上传文件 {i+1}/{len(file_paths)}: {file_path}")
                result = uploader.send_file(file_path, caption)

                if result:
                    successful_uploads.append(file_path)
                else:
                    failed_uploads.append(file_path)

            except Exception as e:
                logger.error(f"❌ 文件上传异常: {file_path} - {e}")
                failed_uploads.append(file_path)

        success_rate = len(successful_uploads) / len(file_paths) * 100 if file_paths else 0

        return jsonify({
            'success': True,
            'status': 'completed',
            'total_files': len(file_paths),
            'successful_uploads': len(successful_uploads),
            'failed_uploads': len(failed_uploads),
            'success_rate': round(success_rate, 2),
            'successful_files': successful_uploads,
            'failed_files': failed_uploads,
            'message': f'同步批量上传完成: {len(successful_uploads)}/{len(file_paths)} 成功'
        })

    except Exception as e:
        logger.error(f"❌ 同步批量上传失败: {e}")
        return jsonify({'error': str(e)}), 500
