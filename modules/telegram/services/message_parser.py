#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram消息解析服务
用于解析URL和自定义文件名
"""

import re
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class TelegramMessageParser:
    """Telegram消息解析器"""
    
    def __init__(self):
        # URL正则表达式 - 匹配常见的视频网站URL
        self.url_pattern = re.compile(
            r'https?://(?:www\.)?(?:'
            r'youtube\.com/watch\?v=[\w-]+|'
            r'youtu\.be/[\w-]+|'
            r'bilibili\.com/video/[\w-]+|'
            r'twitter\.com/\w+/status/\d+|'
            r'tiktok\.com/@[\w.-]+/video/\d+|'
            r'instagram\.com/(?:p|reel)/[\w-]+|'
            r'douyin\.com/video/\d+|'
            r'weibo\.com/\d+/[\w]+|'
            r'[^\s]+\.[a-z]{2,}[^\s]*'  # 通用URL模式
            r')[^\s]*',
            re.IGNORECASE
        )
    
    def parse_message(self, message: str) -> Dict[str, Optional[str]]:
        """
        解析Telegram消息，提取URL和自定义文件名
        
        Args:
            message: 用户发送的消息
            
        Returns:
            Dict包含:
            - url: 提取的URL
            - custom_filename: 自定义文件名
            - original_message: 原始消息
        """
        try:
            message = message.strip()
            
            # 查找URL
            url_match = self.url_pattern.search(message)
            
            if not url_match:
                return {
                    'url': None,
                    'custom_filename': None,
                    'original_message': message
                }
            
            url = url_match.group(0)
            
            # 提取自定义文件名（去掉URL后的剩余文本）
            custom_filename = message.replace(url, '').strip()
            
            # 验证自定义文件名
            if custom_filename:
                custom_filename = self._clean_filename(custom_filename)
                
                # 如果清理后为空，则不使用自定义文件名
                if not custom_filename:
                    custom_filename = None
            else:
                custom_filename = None
            
            result = {
                'url': url,
                'custom_filename': custom_filename,
                'original_message': message
            }
            
            logger.info(f"📝 消息解析结果: URL={url}, 自定义文件名={custom_filename}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 消息解析失败: {e}")
            return {
                'url': message.strip() if self._looks_like_url(message.strip()) else None,
                'custom_filename': None,
                'original_message': message
            }
    
    def _clean_filename(self, filename: str) -> Optional[str]:
        """清理文件名，确保有效性 - 复用统一的文件名清理器"""
        try:
            # 去除前后空格
            filename = filename.strip()

            if not filename:
                return None

            # 移除可能的引号
            filename = filename.strip('"\'')

            # 基本长度检查
            if len(filename) > 100:  # 限制文件名长度
                filename = filename[:100]

            # 🔧 复用统一的文件名清理器
            try:
                from modules.downloader.filename_processor import get_filename_processor
                processor = get_filename_processor()
                cleaned = processor.sanitize_filename(filename)
                return cleaned if cleaned else None
            except Exception as e:
                logger.debug(f"🔍 使用专业清理器失败，使用简单清理: {e}")

                # 降级到简单清理
                invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
                for char in invalid_chars:
                    filename = filename.replace(char, '')

                filename = filename.strip()
                return filename if filename else None

        except Exception as e:
            logger.error(f"❌ 清理文件名失败: {e}")
            return None
    
    def _looks_like_url(self, text: str) -> bool:
        """简单检查文本是否像URL"""
        try:
            parsed = urlparse(text)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False
    
    def validate_url(self, url: str) -> bool:
        """验证URL是否有效"""
        try:
            if not url:
                return False
                
            # 基本URL格式检查
            if not self._looks_like_url(url):
                return False
            
            # 检查是否匹配支持的模式
            return bool(self.url_pattern.match(url))
            
        except Exception as e:
            logger.error(f"❌ URL验证失败: {e}")
            return False


# 全局解析器实例
_message_parser = None

def get_message_parser() -> TelegramMessageParser:
    """获取消息解析器实例"""
    global _message_parser
    if _message_parser is None:
        _message_parser = TelegramMessageParser()
    return _message_parser
