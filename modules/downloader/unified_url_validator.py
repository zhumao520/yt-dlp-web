#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一URL验证器
整合项目中所有的URL检测方法
"""

import re
import logging
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Tuple
from .video_url_detector import get_video_url_detector, analyze_video_url

logger = logging.getLogger(__name__)

class UnifiedUrlValidator:
    """统一URL验证器"""
    
    def __init__(self):
        self.video_detector = get_video_url_detector()
        
        # YouTube域名列表（从pytubefix_downloader.py复制）
        self.youtube_domains = [
            'youtube.com', 'www.youtube.com', 'm.youtube.com',
            'music.youtube.com', 'youtu.be', 'youtube-nocookie.com',
            'www.youtube-nocookie.com'
        ]
    
    def validate_url(self, url: str, check_video: bool = True) -> Dict[str, Any]:
        """
        统一URL验证入口
        
        Args:
            url: 要验证的URL
            check_video: 是否进行视频检测
            
        Returns:
            {
                'is_valid': bool,           # URL格式是否有效
                'is_safe': bool,            # URL是否安全
                'is_video': bool,           # 是否为视频链接
                'confidence': float,        # 视频检测置信度
                'platform': Optional[str],  # 检测到的平台
                'type': str,               # URL类型
                'reasons': List[str],      # 检测原因
                'errors': List[str]        # 错误信息
            }
        """
        result = {
            'is_valid': False,
            'is_safe': False,
            'is_video': False,
            'confidence': 0.0,
            'platform': None,
            'type': 'unknown',
            'reasons': [],
            'errors': []
        }
        
        try:
            # 第1步：基础URL格式验证
            format_check = self._validate_url_format(url)
            if not format_check['valid']:
                result['errors'].extend(format_check['errors'])
                return result
            
            result['is_valid'] = True
            result['reasons'].append('URL格式正确')
            
            # 第2步：安全性检查
            safety_check = self._validate_url_safety(url)
            if not safety_check['safe']:
                result['errors'].extend(safety_check['errors'])
                return result
            
            result['is_safe'] = True
            result['reasons'].append('URL安全检查通过')
            
            # 第3步：平台特定检测
            platform_check = self._detect_platform(url)
            if platform_check['platform']:
                result['platform'] = platform_check['platform']
                result['reasons'].append(f'检测到平台: {platform_check["platform"]}')
            
            # 第4步：视频检测（可选）
            if check_video:
                video_check = self._detect_video(url)
                result.update({
                    'is_video': video_check['is_video'],
                    'confidence': video_check['confidence'],
                    'type': video_check['type']
                })
                result['reasons'].extend(video_check['reasons'])
            
            return result
            
        except Exception as e:
            logger.error(f"URL验证失败: {e}")
            result['errors'].append(f'验证过程出错: {e}')
            return result
    
    def _validate_url_format(self, url: str) -> Dict[str, Any]:
        """基础URL格式验证（从routes.py复制并改进）"""
        try:
            # 基本URL格式检查
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            errors = []
            
            if not url_pattern.match(url):
                errors.append('URL格式不正确')
            
            # 检查URL长度
            if len(url) > 2048:
                errors.append('URL长度超过限制（2048字符）')
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'valid': False,
                'errors': [f'URL格式检查失败: {e}']
            }
    
    def _validate_url_safety(self, url: str) -> Dict[str, Any]:
        """URL安全性检查"""
        try:
            errors = []
            
            # 检查是否包含危险字符
            dangerous_chars = ['<', '>', '"', "'", '\n', '\r', '\t']
            found_dangerous = [char for char in dangerous_chars if char in url]
            if found_dangerous:
                errors.append(f'URL包含危险字符: {found_dangerous}')
            
            # 检查协议安全性
            if not url.lower().startswith(('http://', 'https://')):
                errors.append('只支持HTTP/HTTPS协议')
            
            return {
                'safe': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'safe': False,
                'errors': [f'安全检查失败: {e}']
            }
    
    def _detect_platform(self, url: str) -> Dict[str, Any]:
        """平台检测（整合现有的平台检测逻辑）"""
        try:
            parsed_url = urlparse(url.lower())
            domain = parsed_url.netloc.replace('www.', '')
            
            # YouTube检测（从pytubefix_downloader.py）
            if parsed_url.netloc in [d.lower() for d in self.youtube_domains]:
                return {'platform': 'youtube'}
            
            # TikTok检测（从tiktok.py）
            if 'tiktok.com' in domain:
                if '/video/' in url or url.count('/') >= 5:
                    return {'platform': 'tiktok'}

            # X平台（Twitter）检测
            if any(x_domain in domain for x_domain in ['twitter.com', 'x.com', 't.co']):
                if '/status/' in url or '/i/status/' in url or '/tweet/' in url:
                    return {'platform': 'x'}  # 使用'x'作为统一平台名
            
            # 其他平台检测（从video_url_detector.py）
            video_platforms = {
                'vimeo.com': 'vimeo',
                'dailymotion.com': 'dailymotion',
                'twitch.tv': 'twitch',
                'bilibili.com': 'bilibili',
                'iqiyi.com': 'iqiyi',
                'youku.com': 'youku'
            }
            
            for platform_domain, platform_name in video_platforms.items():
                if platform_domain in domain:
                    return {'platform': platform_name}
            
            return {'platform': None}
            
        except Exception as e:
            logger.debug(f"平台检测失败: {e}")
            return {'platform': None}
    
    def _detect_video(self, url: str) -> Dict[str, Any]:
        """视频检测（使用智能检测器）"""
        try:
            # 使用智能视频检测器
            result = analyze_video_url(url, check_http=False)  # 先不进行HTTP检查，提高速度
            
            return {
                'is_video': result['is_video'],
                'confidence': result['confidence'],
                'type': result['type'],
                'reasons': result['reasons']
            }
            
        except Exception as e:
            logger.debug(f"视频检测失败: {e}")
            return {
                'is_video': False,
                'confidence': 0.0,
                'type': 'unknown',
                'reasons': [f'视频检测失败: {e}']
            }
    
    def quick_validate(self, url: str) -> bool:
        """快速验证（只检查格式和安全性）"""
        try:
            format_check = self._validate_url_format(url)
            if not format_check['valid']:
                return False
            
            safety_check = self._validate_url_safety(url)
            return safety_check['safe']
            
        except Exception:
            return False
    
    def is_video_url(self, url: str, min_confidence: float = 0.3) -> bool:
        """判断是否为视频URL"""
        try:
            result = self.validate_url(url, check_video=True)
            return result['is_video'] and result['confidence'] >= min_confidence
        except Exception:
            return False
    
    def get_platform(self, url: str) -> Optional[str]:
        """获取URL对应的平台"""
        try:
            result = self.validate_url(url, check_video=False)
            return result['platform']
        except Exception:
            return None


# 全局实例
_unified_validator = None

def get_unified_validator() -> UnifiedUrlValidator:
    """获取统一URL验证器实例"""
    global _unified_validator
    if _unified_validator is None:
        _unified_validator = UnifiedUrlValidator()
    return _unified_validator

# 便捷函数
def validate_url(url: str, check_video: bool = True) -> Dict[str, Any]:
    """便捷函数：统一URL验证"""
    validator = get_unified_validator()
    return validator.validate_url(url, check_video)

def quick_validate_url(url: str) -> bool:
    """便捷函数：快速URL验证"""
    validator = get_unified_validator()
    return validator.quick_validate(url)

def is_video_url(url: str, min_confidence: float = 0.3) -> bool:
    """便捷函数：判断是否为视频URL"""
    validator = get_unified_validator()
    return validator.is_video_url(url, min_confidence)

def get_url_platform(url: str) -> Optional[str]:
    """便捷函数：获取URL平台"""
    validator = get_unified_validator()
    return validator.get_platform(url)
