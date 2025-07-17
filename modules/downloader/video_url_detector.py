#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能视频URL检测器
用于判断URL是否为视频链接
"""

import re
import requests
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class VideoUrlDetector:
    """智能视频URL检测器"""
    
    def __init__(self):
        # 视频文件扩展名
        self.video_extensions = {
            'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v',
            '3gp', 'ogv', 'ts', 'mts', 'm2ts', 'vob', 'asf', 'rm',
            'rmvb', 'divx', 'xvid', 'f4v', 'm3u8', 'mpd'
        }
        
        # 音频文件扩展名
        self.audio_extensions = {
            'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a', 'opus',
            'aiff', 'au', 'ra', 'amr', 'ac3', 'dts'
        }
        
        # 已知视频平台域名
        self.video_platforms = {
            'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
            'twitch.tv', 'facebook.com', 'instagram.com', 'twitter.com',
            'x.com', 't.co',  # X平台（原Twitter）域名
            'tiktok.com', 'bilibili.com', 'iqiyi.com', 'youku.com',
            'qq.com', 'sohu.com', 'sina.com.cn', 'weibo.com',
            'pornhub.com', 'xvideos.com', 'xhamster.com', 'redtube.com'
        }
        
        # 视频相关的URL模式
        self.video_patterns = [
            r'/video[s]?/',
            r'/watch\?',
            r'/embed/',
            r'/player/',
            r'/stream[s]?/',
            r'/media/',
            r'/content/',
            r'/download/',
            r'/get_file',
            r'/file/',
            r'\.m3u8',
            r'\.mpd',
            r'/hls/',
            r'/dash/',
            r'/live/',
            r'/vod/',
            # X平台（Twitter）特有模式
            r'/status/',
            r'/i/status/',
            r'/tweet/',
        ]
        
        # 视频相关的参数名
        self.video_params = {
            'v', 'video', 'vid', 'id', 'watch', 'play', 'stream',
            'file', 'url', 'src', 'source', 'media', 'content'
        }
        
        # 可疑的非视频模式
        self.non_video_patterns = [
            r'/api/',
            r'/admin/',
            r'/login',
            r'/register',
            r'/search',
            r'/category',
            r'/tag[s]?/',
            r'/user[s]?/',
            r'/profile',
            r'/settings',
            r'/help',
            r'/about',
            r'/contact',
            r'\.html?$',
            r'\.php$',
            r'\.asp[x]?$',
            r'\.jsp$',
        ]
    
    def detect_video_url(self, url: str) -> Dict[str, Any]:
        """
        智能检测URL是否为视频链接
        
        Returns:
            {
                'is_video': bool,
                'confidence': float,  # 0.0-1.0
                'type': str,  # 'direct_file', 'platform', 'streaming', 'redirect', 'unknown'
                'reasons': List[str],
                'media_type': str,  # 'video', 'audio', 'unknown'
                'platform': Optional[str]
            }
        """
        try:
            result = {
                'is_video': False,
                'confidence': 0.0,
                'type': 'unknown',
                'reasons': [],
                'media_type': 'unknown',
                'platform': None
            }
            
            # 1. 解析URL
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace('www.', '')
            path = parsed.path
            params = parse_qs(parsed.query)
            
            # 2. 检查已知视频平台
            platform_score = self._check_video_platform(domain, result)
            
            # 3. 检查文件扩展名（包含master.txt特殊处理）
            extension_score = self._check_file_extension(path, result)
            
            # 4. 检查URL模式
            pattern_score = self._check_url_patterns(url, path, result)
            
            # 5. 检查参数
            param_score = self._check_url_parameters(params, result)
            
            # 6. 检查非视频模式
            non_video_penalty = self._check_non_video_patterns(url, path, result)
            
            # 7. 计算总分
            total_score = platform_score + extension_score + pattern_score + param_score - non_video_penalty
            
            # 8. 确定结果
            result['confidence'] = min(max(total_score / 4.0, 0.0), 1.0)
            result['is_video'] = result['confidence'] > 0.3
            
            # 9. 确定类型
            if extension_score > 0.8:
                result['type'] = 'direct_file'
            elif platform_score > 0.8:
                result['type'] = 'platform'
            elif 'm3u8' in url or 'mpd' in url:
                result['type'] = 'streaming'
            elif any(pattern in url for pattern in ['get_file', 'download', 'stream']):
                result['type'] = 'redirect'
            
            logger.debug(f"视频URL检测: {url[:50]}... → {result['is_video']} (置信度: {result['confidence']:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"视频URL检测失败: {e}")
            return {
                'is_video': False,
                'confidence': 0.0,
                'type': 'unknown',
                'reasons': [f'检测失败: {e}'],
                'media_type': 'unknown',
                'platform': None
            }
    
    def _check_video_platform(self, domain: str, result: Dict[str, Any]) -> float:
        """检查是否为已知视频平台"""
        for platform in self.video_platforms:
            if platform in domain:
                result['reasons'].append(f'已知视频平台: {platform}')
                result['platform'] = platform
                return 1.0
        return 0.0
    
    def _check_file_extension(self, path: str, result: Dict[str, Any]) -> float:
        """检查文件扩展名"""
        # 提取扩展名
        if '.' in path:
            ext = path.split('.')[-1].lower()

            if ext in self.video_extensions:
                result['reasons'].append(f'视频文件扩展名: .{ext}')
                result['media_type'] = 'video'
                return 1.0
            elif ext in self.audio_extensions:
                result['reasons'].append(f'音频文件扩展名: .{ext}')
                result['media_type'] = 'audio'
                return 0.8

        return 0.0
    
    def _check_url_patterns(self, url: str, path: str, result: Dict[str, Any]) -> float:
        """检查URL模式"""
        score = 0.0
        matched_patterns = []
        
        for pattern in self.video_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                matched_patterns.append(pattern)
                score += 0.3
        
        if matched_patterns:
            result['reasons'].append(f'匹配视频模式: {matched_patterns}')
        
        return min(score, 1.0)
    
    def _check_url_parameters(self, params: Dict[str, List[str]], result: Dict[str, Any]) -> float:
        """检查URL参数"""
        score = 0.0
        matched_params = []
        
        for param_name in params.keys():
            if param_name.lower() in self.video_params:
                matched_params.append(param_name)
                score += 0.2
        
        if matched_params:
            result['reasons'].append(f'视频相关参数: {matched_params}')
        
        return min(score, 0.6)
    
    def _check_non_video_patterns(self, url: str, path: str, result: Dict[str, Any]) -> float:
        """检查非视频模式（负分）"""
        penalty = 0.0
        matched_patterns = []
        
        for pattern in self.non_video_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                matched_patterns.append(pattern)
                penalty += 0.3
        
        if matched_patterns:
            result['reasons'].append(f'非视频模式: {matched_patterns}')
        
        return min(penalty, 0.8)
    
    def check_url_with_http_request(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """
        通过HTTP请求检查URL的实际内容类型
        """
        try:
            # 使用HEAD请求获取头部信息
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            
            content_type = response.headers.get('Content-Type', '').lower()
            content_length = response.headers.get('Content-Length')
            
            result = {
                'status_code': response.status_code,
                'content_type': content_type,
                'content_length': content_length,
                'final_url': response.url,
                'is_video_content': False,
                'is_audio_content': False,
                'file_size_mb': 0
            }
            
            # 检查Content-Type
            if any(video_type in content_type for video_type in ['video/', 'application/mp4', 'application/x-mpegURL']):
                result['is_video_content'] = True
            elif any(audio_type in content_type for audio_type in ['audio/', 'application/ogg']):
                result['is_audio_content'] = True
            
            # 计算文件大小
            if content_length:
                try:
                    result['file_size_mb'] = int(content_length) / (1024 * 1024)
                except:
                    pass
            
            return result
            
        except Exception as e:
            logger.debug(f"HTTP检查失败: {e}")
            return {
                'status_code': 0,
                'content_type': '',
                'content_length': None,
                'final_url': url,
                'is_video_content': False,
                'is_audio_content': False,
                'file_size_mb': 0,
                'error': str(e)
            }
    
    def comprehensive_video_detection(self, url: str, check_http: bool = True) -> Dict[str, Any]:
        """
        综合视频检测（URL分析 + HTTP检查）
        """
        # 1. URL模式检测
        url_result = self.detect_video_url(url)
        
        # 2. HTTP内容检测（可选）
        http_result = None
        if check_http and url_result['confidence'] > 0.2:
            http_result = self.check_url_with_http_request(url)
        
        # 3. 综合判断
        final_result = url_result.copy()
        
        if http_result:
            # 根据HTTP结果调整置信度
            if http_result['is_video_content']:
                final_result['confidence'] = max(final_result['confidence'], 0.9)
                final_result['is_video'] = True
                final_result['media_type'] = 'video'
                final_result['reasons'].append('HTTP Content-Type确认为视频')
            elif http_result['is_audio_content']:
                final_result['confidence'] = max(final_result['confidence'], 0.8)
                final_result['is_video'] = True
                final_result['media_type'] = 'audio'
                final_result['reasons'].append('HTTP Content-Type确认为音频')
            elif http_result['status_code'] == 404:
                final_result['confidence'] *= 0.1
                final_result['is_video'] = False
                final_result['reasons'].append('HTTP 404: 文件不存在')
            
            final_result['http_info'] = http_result
        
        return final_result


# 全局实例
_video_detector = None

def get_video_url_detector() -> VideoUrlDetector:
    """获取视频URL检测器实例"""
    global _video_detector
    if _video_detector is None:
        _video_detector = VideoUrlDetector()
    return _video_detector

def is_video_url(url: str, check_http: bool = False) -> bool:
    """便捷函数：判断URL是否为视频链接"""
    detector = get_video_url_detector()
    if check_http:
        result = detector.comprehensive_video_detection(url)
    else:
        result = detector.detect_video_url(url)
    return result['is_video']

def analyze_video_url(url: str, check_http: bool = True) -> Dict[str, Any]:
    """便捷函数：分析视频URL"""
    detector = get_video_url_detector()
    return detector.comprehensive_video_detection(url, check_http)
