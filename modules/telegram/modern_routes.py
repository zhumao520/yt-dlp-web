# -*- coding: utf-8 -*-
"""
现代化 Telegram 路由处理器
优化的命令处理和消息路由，支持依赖注入
"""

import logging
import re
import time
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify

from .services.modern_command_service import ModernTelegramCommandService
from .services.state_service import SelectionStateService
from .notifier import get_telegram_notifier

logger = logging.getLogger(__name__)

# 创建Telegram Blueprint
telegram_bp = Blueprint('telegram', __name__, url_prefix='/telegram')


class ModernTelegramRouter:
    """现代化 Telegram 路由处理器"""
    
    def __init__(self):
        self.command_service = ModernTelegramCommandService()
        self.state_service = SelectionStateService()
        self.notifier = None
    
    def get_notifier(self):
        """获取通知器实例（延迟加载）"""
        if not self.notifier:
            self.notifier = get_telegram_notifier()
        return self.notifier
    
    def process_telegram_message(self, update: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """处理 Telegram 消息 - 现代化路由"""
        try:
            # 提取消息
            message = update.get('message')
            if not message:
                return {'action': 'ignored', 'reason': '非消息更新'}

            # 验证授权
            auth_result = self._verify_authorization(message, config)
            if not auth_result['authorized']:
                return auth_result

            # 获取消息内容
            text = message.get('text', '').strip()
            user_info = self._extract_user_info(message)
            
            logger.info(f"📨 收到消息: '{text}' 来自 {user_info['username']}")

            if not text:
                return {'action': 'ignored', 'reason': '空消息'}

            # 路由消息到相应处理器
            return self._route_message(text, user_info, config)
            
        except Exception as e:
            logger.error(f'❌ 处理 Telegram 消息失败: {e}')
            return {'action': 'error', 'error': str(e)}

    def _verify_authorization(self, message: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """验证用户授权"""
        chat_id = str(message.get('chat', {}).get('id', ''))
        expected_chat_id = str(config.get('chat_id', ''))
        
        if chat_id != expected_chat_id:
            logger.warning(f"⚠️ 未授权的 chat_id: {chat_id}, 期望: {expected_chat_id}")
            return {'action': 'ignored', 'reason': '未授权的聊天', 'authorized': False}
        
        return {'authorized': True}

    def _extract_user_info(self, message: Dict[str, Any]) -> Dict[str, str]:
        """提取用户信息"""
        user = message.get('from', {})
        return {
            'id': str(user.get('id', '')),
            'username': user.get('username', user.get('first_name', '未知用户')),
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', '')
        }

    def _route_message(self, text: str, user_info: Dict[str, str], config: Dict[str, Any]) -> Dict[str, Any]:
        """路由消息到相应处理器"""
        chat_id = config.get('chat_id')
        
        # 1. 处理命令
        if text.startswith('/'):
            return self._handle_command(text, user_info)
        
        # 2. 处理数字选择（分辨率选择）
        if text.isdigit():
            return self._handle_quality_selection(int(text), chat_id, user_info)
        
        # 3. 处理 URL
        if self._is_valid_url(text):
            return self._handle_url_with_quality_selection(text, config, user_info)
        
        # 4. 处理其他文本（发送帮助）
        return self._handle_unknown_text(text, user_info)

    def _handle_command(self, command: str, user_info: Dict[str, str]) -> Dict[str, Any]:
        """处理命令 - 现代化命令路由"""
        try:
            notifier = self.get_notifier()
            
            # 解析命令和参数
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            logger.info(f"🎮 处理命令: {cmd} 参数: '{args}' 用户: {user_info['username']}")
            
            # 命令路由表
            command_handlers = {
                '/start': lambda: self.command_service.handle_start_command(),
                '/status': lambda: self.command_service.handle_status_command(),
                '/downloads': lambda: self.command_service.handle_downloads_command(),
                '/files': lambda: self.command_service.handle_files_command(),
                '/send': lambda: self.command_service.handle_send_command(args),
                '/delete': lambda: self.command_service.handle_delete_command(args),
                '/cancel': lambda: self.command_service.handle_cancel_command(args),
                '/cleanup': lambda: self.command_service.handle_cleanup_command(),
            }
            
            # 执行命令
            if cmd in command_handlers:
                response = command_handlers[cmd]()
                notifier.send_message(response)
                return {'action': 'command_processed', 'command': cmd.replace('/', '')}
            else:
                # 未知命令
                response = f"❌ **未知命令**: {cmd}\n\n💡 发送 `/start` 查看可用命令"
                notifier.send_message(response)
                return {'action': 'command_error', 'error': 'unknown_command', 'command': cmd}
            
        except Exception as e:
            logger.error(f"❌ 命令处理失败: {e}")
            notifier = self.get_notifier()
            notifier.send_message(f"❌ **命令执行失败**\n\n错误: {str(e)}")
            return {'action': 'command_error', 'error': str(e)}

    def _handle_quality_selection(self, selection: int, chat_id: str, user_info: Dict[str, str]) -> Dict[str, Any]:
        """处理分辨率选择"""
        try:
            # 获取用户的选择状态
            state = self.state_service.get_selection_state(chat_id)
            
            if not state:
                notifier = self.get_notifier()
                notifier.send_message("❌ **选择已过期**\n\n请重新发送视频链接")
                return {'action': 'selection_expired'}
            
            url = state.get('url')
            qualities = state.get('qualities', [])
            
            if not (1 <= selection <= len(qualities)):
                notifier = self.get_notifier()
                notifier.send_message(f"❌ **选择无效**\n\n请选择 1-{len(qualities)} 之间的数字")
                return {'action': 'invalid_selection'}
            
            # 获取选择的质量
            selected_quality = qualities[selection - 1]
            
            # 清除选择状态
            self.state_service.clear_selection_state(chat_id)
            
            # 开始下载
            return self._start_download_with_quality(url, selected_quality, user_info)
            
        except Exception as e:
            logger.error(f"❌ 处理分辨率选择失败: {e}")
            return {'action': 'error', 'error': str(e)}

    def _handle_url_with_quality_selection(self, url: str, config: Dict[str, Any], user_info: Dict[str, str]) -> Dict[str, Any]:
        """处理 URL 并显示分辨率选择"""
        try:
            logger.info(f"🔗 处理 URL: {url}")
            
            # 分析可用质量
            qualities = self._analyze_available_qualities(url)
            
            if not qualities:
                # 如果无法获取质量信息，直接下载
                return self._start_download_direct(url, user_info)
            
            # 存储选择状态
            chat_id = config.get('chat_id')
            self.state_service.store_selection_state(chat_id, {
                'url': url,
                'qualities': qualities,
                'timestamp': time.time()
            })
            
            # 发送质量选择菜单
            self._send_quality_selection_menu(url, qualities)
            
            return {'action': 'quality_selection_sent', 'url': url, 'qualities_count': len(qualities)}
            
        except Exception as e:
            logger.error(f"❌ 处理 URL 失败: {e}")
            # 出错时直接下载
            return self._start_download_direct(url, user_info)

    def _handle_unknown_text(self, text: str, user_info: Dict[str, str]) -> Dict[str, Any]:
        """处理未知文本"""
        notifier = self.get_notifier()
        
        help_message = """❓ **不理解您的消息**

请发送：
• **视频链接** - 开始下载
• **命令** - 如 `/start`, `/files`, `/status`
• **数字** - 选择视频质量（如果正在选择）

💡 发送 `/start` 查看完整帮助"""
        
        notifier.send_message(help_message)
        return {'action': 'help_sent', 'message': '已发送帮助信息'}

    def _is_valid_url(self, text: str) -> bool:
        """检查是否为有效 URL"""
        url_pattern = re.compile(
            r'^https?://'  # http:// 或 https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # 可选端口
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(text))

    def _analyze_available_qualities(self, url: str) -> list:
        """分析可用的视频质量"""
        try:
            # 这里应该调用 yt-dlp 来获取可用格式
            # 为了简化，返回常见的质量选项
            return [
                {'format_id': 'best', 'quality': '最佳质量', 'note': '自动选择最高质量'},
                {'format_id': '720p', 'quality': '720p', 'note': '高清'},
                {'format_id': '480p', 'quality': '480p', 'note': '标清'},
                {'format_id': 'worst', 'quality': '最小文件', 'note': '最小文件大小'}
            ]
        except Exception as e:
            logger.error(f"❌ 分析视频质量失败: {e}")
            return []

    def _send_quality_selection_menu(self, url: str, qualities: list):
        """发送质量选择菜单"""
        try:
            notifier = self.get_notifier()
            
            # 提取视频标题（简化版）
            title = self._extract_video_title(url)
            
            message = f"""🎬 **视频质量选择**

📹 **{title}**
🔗 {url[:50]}...

请选择下载质量：

"""
            
            for i, quality in enumerate(qualities, 1):
                message += f"{i}. **{quality['quality']}** - {quality['note']}\n"
            
            message += f"""
💡 **提示**: 发送数字 1-{len(qualities)} 进行选择
⏰ **有效期**: 5分钟"""
            
            notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"❌ 发送质量选择菜单失败: {e}")

    def _extract_video_title(self, url: str) -> str:
        """提取视频标题（简化版）"""
        try:
            # 这里应该调用 yt-dlp 来获取视频信息
            # 为了简化，从 URL 中提取
            if 'youtube.com' in url or 'youtu.be' in url:
                return "YouTube 视频"
            elif 'bilibili.com' in url:
                return "Bilibili 视频"
            elif 'twitter.com' in url or 'x.com' in url:
                return "Twitter 视频"
            else:
                return "未知视频"
        except:
            return "视频"

    def _start_download_with_quality(self, url: str, quality: Dict[str, Any], user_info: Dict[str, str]) -> Dict[str, Any]:
        """开始指定质量的下载"""
        try:
            from modules.downloader.manager import get_download_manager
            
            download_manager = get_download_manager()
            
            # 构建下载选项
            options = {
                'format': quality['format_id'],
                'source': 'telegram_webhook',
                'user': user_info['username'],
                'quality_selected': quality['quality']
            }
            
            # 开始下载
            download_id = download_manager.add_download(url, options)
            
            notifier = self.get_notifier()
            notifier.send_message(f"""✅ **下载已开始**

📹 **质量**: {quality['quality']}
🆔 **ID**: `{download_id[:8]}`

📊 下载进度将实时更新
🚫 发送 `/cancel {download_id[:8]}` 可取消下载""")
            
            return {'action': 'download_started', 'download_id': download_id, 'quality': quality['quality']}
            
        except Exception as e:
            logger.error(f"❌ 开始下载失败: {e}")
            notifier = self.get_notifier()
            notifier.send_message(f"❌ **下载启动失败**\n\n错误: {str(e)}")
            return {'action': 'download_failed', 'error': str(e)}

    def _start_download_direct(self, url: str, user_info: Dict[str, str]) -> Dict[str, Any]:
        """直接开始下载（不选择质量）"""
        try:
            from modules.downloader.manager import get_download_manager
            
            download_manager = get_download_manager()
            
            # 构建下载选项
            options = {
                'source': 'telegram_webhook',
                'user': user_info['username']
            }
            
            # 开始下载
            download_id = download_manager.add_download(url, options)
            
            notifier = self.get_notifier()
            notifier.send_message(f"""✅ **下载已开始**

🔗 **链接**: {url[:50]}...
🆔 **ID**: `{download_id[:8]}`

📊 下载进度将实时更新
🚫 发送 `/cancel {download_id[:8]}` 可取消下载""")
            
            return {'action': 'download_started', 'download_id': download_id}
            
        except Exception as e:
            logger.error(f"❌ 开始下载失败: {e}")
            notifier = self.get_notifier()
            notifier.send_message(f"❌ **下载启动失败**\n\n错误: {str(e)}")
            return {'action': 'download_failed', 'error': str(e)}


# 全局路由器实例
_modern_router_instance = None

def get_modern_telegram_router() -> ModernTelegramRouter:
    """获取现代化路由器实例（单例）"""
    global _modern_router_instance

    if _modern_router_instance is None:
        _modern_router_instance = ModernTelegramRouter()

    return _modern_router_instance


@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Telegram Webhook处理"""
    try:
        from core.database import get_database

        # 获取请求数据
        update = request.get_json()
        if not update:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        # 获取Telegram配置
        db = get_database()
        telegram_config = db.get_telegram_config()

        if not telegram_config or not telegram_config.get('enabled'):
            return jsonify({'status': 'disabled', 'message': 'Telegram not enabled'}), 200

        # 处理消息
        router = get_modern_telegram_router()
        result = router.process_telegram_message(update, telegram_config)

        return jsonify({'status': 'success', 'result': result}), 200

    except Exception as e:
        logger.error(f"❌ Telegram webhook处理失败: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
