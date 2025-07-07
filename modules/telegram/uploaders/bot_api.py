# -*- coding: utf-8 -*-
"""
Bot API上传器 - 参考ytdlbot的智能发送策略
"""

import logging
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
import time
import ssl
import urllib3

from ..base import BaseUploader

logger = logging.getLogger(__name__)


class BotAPIUploader(BaseUploader):
    """Bot API上传器 - 智能文件类型检测和发送"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._progress_message_id = None

        # 使用代理协议转换系统 - 支持用户开关控制
        self.proxies = self._get_proxy_config()

        if self.proxies:
            logger.info(f"✅ Bot API 使用转换后的代理: {self.proxies}")
        else:
            logger.info("ℹ️ Bot API 未配置代理或用户已禁用代理上传")

        # 备用代理配置（保持兼容性）
        self.fallback_proxies = self.proxies

        # 配置SSL和连接设置以解决SSL错误（在proxies设置之后）
        self._setup_ssl_config()

    def _setup_ssl_config(self):
        """配置SSL和会话设置"""
        try:
            # 创建requests会话以统一配置
            self.session = requests.Session()

            # 设置代理
            if self.proxies:
                self.session.proxies.update(self.proxies)

                # 检查是否是HTTP代理（转换后的）
                proxy_url = list(self.proxies.values())[0] if self.proxies else ""
                if proxy_url.startswith('http://'):
                    # HTTP代理，可以保持SSL验证
                    logger.info("✅ 使用HTTP代理，保持SSL验证")
                else:
                    # SOCKS5代理，禁用SSL验证避免兼容性问题
                    self.session.verify = False
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    logger.info("✅ 使用SOCKS5代理，禁用SSL验证")
            else:
                # 无代理，保持默认SSL设置
                logger.info("✅ 无代理，使用默认SSL设置")

        except Exception as e:
            logger.warning(f"⚠️ SSL配置失败，使用默认设置: {e}")
            self.session = requests

    def _get_proxy_config(self) -> Optional[Dict[str, str]]:
        """获取代理配置 - 支持用户开关控制"""
        try:
            # 首先检查用户是否启用了代理上传
            from modules.telegram.services.config_service import get_telegram_config_service
            config_service = get_telegram_config_service()

            if not config_service.use_proxy_for_upload():
                logger.info("🌐 Bot API 用户已禁用代理上传，使用直连模式")
                return None

            # 用户启用了代理上传，获取系统代理配置
            from core.proxy_converter import ProxyConverter
            proxies = ProxyConverter.get_requests_proxy("Bot API")

            if proxies:
                logger.info(f"✅ Bot API 使用用户启用的代理: {proxies}")
                return proxies
            else:
                logger.warning("⚠️ Bot API 用户启用了代理上传，但系统代理未配置或不可用")
                return None

        except Exception as e:
            logger.error(f"❌ Bot API 获取代理配置失败: {e}")
            return None



    def is_available(self) -> bool:
        """检查 Bot API 上传器是否可用"""
        return bool(self.bot_token and self.chat_id)

    def _send_with_retry(self, func, max_retries: int = 5, **kwargs):
        """带重试机制的发送方法"""
        last_exception = None
        original_proxies = self.proxies
        proxy_switched = False

        for attempt in range(max_retries):
            try:
                logger.debug(f"📤 Bot API 尝试 {attempt + 1}/{max_retries}")
                return func(**kwargs)

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                error_msg = str(e).lower()

                # 特殊处理 RemoteDisconnected 错误
                if 'remote end closed connection' in error_msg or 'remotedisconnected' in error_msg:
                    logger.warning(f"⚠️ 远程服务器断开连接 (尝试 {attempt + 1}/{max_retries}): {e}")
                else:
                    logger.warning(f"⚠️ 网络连接错误 (尝试 {attempt + 1}/{max_retries}): {e}")

                # 在第一次连接错误时尝试切换到备用代理
                if attempt == 0 and not proxy_switched and self.fallback_proxies:
                    logger.info("🔄 尝试切换到备用 SOCKS5 代理...")
                    self.proxies = self.fallback_proxies
                    proxy_switched = True
                    continue

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间：2s, 4s, 6s
                    logger.info(f"🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    # 恢复原始代理配置
                    self.proxies = original_proxies
                    if 'remote end closed connection' in error_msg:
                        logger.error("❌ 远程服务器持续断开连接，可能是代理或网络问题")
                    else:
                        logger.error("❌ 网络连接失败，已达到最大重试次数")
                    return False

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"⚠️ 请求超时 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3  # 递增等待时间：3s, 6s, 9s
                    logger.info(f"🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("❌ 请求超时，已达到最大重试次数")
                    return False

            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if e.response else 0

                # 某些HTTP错误不应该重试
                if status_code in [400, 401, 403, 404]:
                    logger.error(f"❌ HTTP错误 {status_code}，不重试: {e}")
                    return False

                logger.warning(f"⚠️ HTTP错误 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("❌ HTTP错误，已达到最大重试次数")
                    return False

            except Exception as e:
                last_exception = e
                logger.error(f"❌ 未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger.info(f"🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("❌ 未知错误，已达到最大重试次数")
                    return False

        # 如果所有重试都失败，返回 False
        logger.error(f"❌ 所有重试都失败，最后异常: {last_exception}")
        return False

    def send_message(self, message: str, parse_mode: str = None) -> bool:
        """发送文本消息 - 带重试机制"""
        return self._send_with_retry(self._send_message_impl, message=message, parse_mode=parse_mode)

    def _send_message_impl(self, message: str, parse_mode: str = None) -> bool:
        """发送文本消息的具体实现"""
        url = f"{self.base_url}/sendMessage"

        data = {
            'chat_id': self.chat_id,
            'text': message
        }

        if parse_mode:
            data['parse_mode'] = parse_mode

        # SSL验证已在session中配置

        response = self.session.post(url, data=data, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get('ok'):
            logger.info("✅ Bot API消息发送成功")
            return True
        else:
            logger.error(f"❌ Bot API消息发送失败: {result}")
            return False
    
    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """智能文件发送 - 根据文件类型选择最佳API"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.debug(f"🔍 文件不存在: {file_path}")
                return False
            
            # 获取文件元数据
            metadata = self.get_file_metadata(file_path)
            file_type = metadata.get('file_type', 'document')
            file_size_mb = metadata.get('size_mb', 0)
            
            # 检查文件大小限制（使用配置的限制）
            file_size_limit = self.config.get('file_size_limit', 50)
            if file_size_mb > file_size_limit:
                logger.info(f"📏 文件过大({file_size_mb:.1f}MB > {file_size_limit}MB)，Bot API无法处理，需要Pyrofork")
                return False
            
            logger.info(f"📤 使用Bot API发送{file_type}文件: {file_path_obj.name} ({file_size_mb:.1f}MB)")
            
            # 根据文件类型选择发送方法
            if file_type == 'video':
                return self._send_video(file_path, caption, metadata)
            elif file_type == 'audio':
                return self._send_audio(file_path, caption, metadata)
            elif file_type == 'photo':
                return self._send_photo(file_path, caption)
            else:
                return self._send_document(file_path, caption)
                
        except Exception as e:
            logger.debug(f"🔍 Bot API文件发送异常: {e}")
            return None
    
    def send_media_group(self, files: List[str], caption: str = None) -> bool:
        """发送媒体组"""
        try:
            if not files:
                return False
            
            # 检查文件数量限制
            if len(files) > 10:
                logger.warning(f"⚠️ 媒体组文件过多({len(files)})，限制为10个")
                files = files[:10]
            
            media = []
            total_size = 0
            
            for i, file_path in enumerate(files):
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    logger.warning(f"⚠️ 跳过不存在的文件: {file_path}")
                    continue
                
                metadata = self.get_file_metadata(file_path)
                file_type = metadata.get('file_type', 'document')
                file_size_mb = metadata.get('size_mb', 0)
                total_size += file_size_mb
                
                # 检查总大小限制（使用配置的限制）
                file_size_limit = self.config.get('file_size_limit', 50)
                if total_size > file_size_limit:
                    logger.warning(f"⚠️ 媒体组总大小超限({total_size:.1f}MB > {file_size_limit}MB)，截止到第{i}个文件")
                    break
                
                # 构建媒体项
                media_item = self._build_media_item(file_path, file_type, metadata)
                if i == 0 and caption:  # 第一个文件添加说明
                    media_item['caption'] = caption
                
                media.append(media_item)
            
            if not media:
                logger.error("❌ 没有有效的媒体文件")
                return False
            
            # 发送媒体组
            url = f"{self.base_url}/sendMediaGroup"
            
            # 准备文件数据
            files_data = {}
            for i, media_item in enumerate(media):
                file_key = f"file_{i}"
                files_data[file_key] = open(media_item['media'], 'rb')
                media_item['media'] = f"attach://{file_key}"
            
            try:
                data = {
                    'chat_id': self.chat_id,
                    'media': media
                }
                
                response = requests.post(url, data={'chat_id': self.chat_id, 'media': str(media)},
                                       files=files_data, timeout=300, proxies=self.proxies)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    logger.info(f"✅ 媒体组发送成功({len(media)}个文件)")
                    return True
                else:
                    logger.debug(f"🔍 媒体组发送失败: {result}")
                    return False
                    
            finally:
                # 关闭文件句柄
                for file_obj in files_data.values():
                    file_obj.close()
                
        except Exception as e:
            logger.debug(f"🔍 媒体组发送异常: {e}")
            return False
    
    def _send_video(self, file_path: str, caption: str, metadata: Dict[str, Any]) -> bool:
        """发送视频文件"""
        try:
            url = f"{self.base_url}/sendVideo"
            
            # 生成缩略图
            thumb_path = self._generate_thumbnail(file_path)
            
            with open(file_path, 'rb') as video_file:
                files = {'video': video_file}
                
                # 添加缩略图
                if thumb_path:
                    files['thumb'] = open(thumb_path, 'rb')
                
                try:
                    data = {
                        'chat_id': self.chat_id,
                        'caption': caption or '',
                        'supports_streaming': True,
                        'width': metadata.get('width', 1280),
                        'height': metadata.get('height', 720),
                        'duration': int(metadata.get('duration', 0))
                    }
                    
                    response = self.session.post(url, files=files, data=data, timeout=300)
                    response.raise_for_status()
                    
                    result = response.json()
                    if result.get('ok'):
                        logger.info("✅ 视频发送成功")
                        return True
                    else:
                        logger.debug(f"🔍 视频发送失败: {result}")
                        return False
                        
                finally:
                    if thumb_path and 'thumb' in files:
                        files['thumb'].close()
                        
        except Exception as e:
            logger.debug(f"🔍 视频发送异常: {e}")
            return None
    
    def _send_audio(self, file_path: str, caption: str, metadata: Dict[str, Any]) -> bool:
        """发送音频文件"""
        try:
            url = f"{self.base_url}/sendAudio"
            
            with open(file_path, 'rb') as audio_file:
                files = {'audio': audio_file}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption or '',
                    'duration': int(metadata.get('duration', 0))
                }
                
                response = self.session.post(url, files=files, data=data, timeout=300)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    logger.info("✅ 音频发送成功")
                    return True
                else:
                    logger.debug(f"🔍 音频发送失败: {result}")
                    return False
                    
        except Exception as e:
            logger.debug(f"🔍 音频发送异常: {e}")
            return None
    
    def _send_photo(self, file_path: str, caption: str) -> bool:
        """发送图片文件"""
        try:
            url = f"{self.base_url}/sendPhoto"
            
            with open(file_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption or ''
                }
                
                response = self.session.post(url, files=files, data=data, timeout=300)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    logger.info("✅ 图片发送成功")
                    return True
                else:
                    logger.debug(f"🔍 图片发送失败: {result}")
                    return False
                    
        except Exception as e:
            logger.debug(f"🔍 图片发送异常: {e}")
            return None
    
    def _send_document(self, file_path: str, caption: str) -> bool:
        """发送文档文件"""
        try:
            url = f"{self.base_url}/sendDocument"
            
            with open(file_path, 'rb') as document_file:
                files = {'document': document_file}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption or ''
                }
                
                response = self.session.post(url, files=files, data=data, timeout=300)
                response.raise_for_status()
                
                result = response.json()
                if result.get('ok'):
                    logger.info("✅ 文档发送成功")
                    return True
                else:
                    logger.debug(f"🔍 文档发送失败: {result}")
                    return False
                    
        except Exception as e:
            logger.debug(f"🔍 文档发送异常: {e}")
            return None
    
    def _build_media_item(self, file_path: str, file_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """构建媒体项"""
        if file_type == 'video':
            return {
                'type': 'video',
                'media': file_path,
                'width': metadata.get('width', 1280),
                'height': metadata.get('height', 720),
                'duration': int(metadata.get('duration', 0)),
                'supports_streaming': True
            }
        elif file_type == 'photo':
            return {
                'type': 'photo',
                'media': file_path
            }
        else:
            return {
                'type': 'document',
                'media': file_path
            }
    
    def _update_progress_display(self, text: str, file_id: str = None):
        """更新进度显示"""
        try:
            if self._progress_message_id:
                # 更新现有消息
                url = f"{self.base_url}/editMessageText"
                data = {
                    'chat_id': self.chat_id,
                    'message_id': self._progress_message_id,
                    'text': text
                }
                self.session.post(url, json=data, timeout=10)
            else:
                # 发送新的进度消息
                url = f"{self.base_url}/sendMessage"
                data = {
                    'chat_id': self.chat_id,
                    'text': text
                }
                response = self.session.post(url, json=data, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        self._progress_message_id = result['result']['message_id']
                        
        except Exception as e:
            logger.debug(f"更新进度显示失败: {e}")
            return None
    
    def cleanup(self):
        """清理资源"""
        super().cleanup()
        self._progress_message_id = None
