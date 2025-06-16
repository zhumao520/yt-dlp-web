# -*- coding: utf-8 -*-
"""
统一下载API - 供所有平台调用
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class UnifiedDownloadAPI:
    """统一下载API - 供Telegram、Web、iOS快捷指令等所有平台使用"""
    
    def __init__(self):
        self.download_manager = None
        self._initialize()
    
    def _initialize(self):
        """初始化API"""
        try:
            from .manager import get_download_manager
            self.download_manager = get_download_manager()
            logger.info("✅ 统一下载API初始化完成")
        except Exception as e:
            logger.error(f"❌ 统一下载API初始化失败: {e}")
            raise
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """获取视频信息 - 使用智能回退机制"""
        try:
            logger.info(f"🔍 获取视频信息: {url}")
            
            # 使用下载管理器的智能回退机制
            video_info = self.download_manager._extract_video_info(url)
            
            if not video_info:
                raise Exception("无法获取视频信息")
            
            # 标准化返回格式
            result = {
                'success': True,
                'data': {
                    'title': video_info.get('title', 'Unknown'),
                    'duration': video_info.get('duration', 0),
                    'uploader': video_info.get('uploader', 'Unknown'),
                    'thumbnail': video_info.get('thumbnail'),
                    'description': video_info.get('description', ''),
                    'formats': self._analyze_formats(video_info.get('formats', [])),
                    'url': url
                }
            }
            
            logger.info(f"✅ 成功获取视频信息: {result['data']['title']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取视频信息失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def create_download(self, url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建下载任务"""
        try:
            logger.info(f"📥 创建下载任务: {url}")
            
            # 标准化选项
            download_options = self._standardize_options(options or {})
            
            # 创建下载任务
            download_id = self.download_manager.create_download(url, download_options)
            
            result = {
                'success': True,
                'data': {
                    'download_id': download_id,
                    'url': url,
                    'status': 'pending',
                    'options': download_options
                }
            }
            
            logger.info(f"✅ 下载任务创建成功: {download_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 创建下载任务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_download_status(self, download_id: str) -> Dict[str, Any]:
        """获取下载状态"""
        try:
            download_info = self.download_manager.get_download(download_id)
            
            if not download_info:
                return {
                    'success': False,
                    'error': '下载任务不存在',
                    'data': None
                }
            
            return {
                'success': True,
                'data': {
                    'download_id': download_id,
                    'status': download_info.get('status'),
                    'progress': download_info.get('progress', 0),
                    'title': download_info.get('title'),
                    'file_path': download_info.get('file_path'),
                    'file_size': download_info.get('file_size'),
                    'error_message': download_info.get('error_message'),
                    'created_at': download_info.get('created_at'),
                    'completed_at': download_info.get('completed_at')
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 获取下载状态失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_all_downloads(self) -> Dict[str, Any]:
        """获取所有下载任务"""
        try:
            downloads = self.download_manager.get_all_downloads()
            
            return {
                'success': True,
                'data': {
                    'downloads': downloads,
                    'total': len(downloads),
                    'active': len([d for d in downloads if d['status'] in ['pending', 'downloading']]),
                    'completed': len([d for d in downloads if d['status'] == 'completed']),
                    'failed': len([d for d in downloads if d['status'] == 'failed'])
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 获取下载列表失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def cancel_download(self, download_id: str) -> Dict[str, Any]:
        """取消下载任务"""
        try:
            success = self.download_manager.cancel_download(download_id)
            
            return {
                'success': success,
                'data': {
                    'download_id': download_id,
                    'cancelled': success
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 取消下载失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def _analyze_formats(self, formats: List[Dict]) -> List[Dict]:
        """分析可用格式"""
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
                        'quality': quality_key,
                        'display': quality_display,
                        'size_info': size_info,
                        'format_id': fmt.get('format_id'),
                        'height': height,
                        'width': fmt.get('width'),
                        'fps': fmt.get('fps'),
                        'tbr': fmt.get('tbr'),
                        'ext': fmt.get('ext')
                    }
            
            # 按分辨率排序（从高到低）
            sorted_qualities = sorted(quality_map.values(), key=lambda x: x['height'], reverse=True)
            
            # 添加音频选项
            sorted_qualities.append({
                'quality': 'audio',
                'display': '仅音频 (MP3)',
                'size_info': '音频文件',
                'format_id': 'audio_only',
                'height': 0,
                'width': 0,
                'fps': 0,
                'tbr': 0,
                'ext': 'mp3'
            })
            
            return sorted_qualities[:6]  # 最多6个选项
            
        except Exception as e:
            logger.error(f"❌ 分析格式失败: {e}")
            return [
                {'quality': 'high', 'display': '最高质量', 'size_info': '自动选择'},
                {'quality': 'medium', 'display': '中等质量 (720p)', 'size_info': '推荐'},
                {'quality': 'low', 'display': '低质量 (360p)', 'size_info': '节省流量'}
            ]
    
    def _standardize_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """标准化下载选项"""
        # 处理audio_only参数，支持布尔值和字符串
        audio_only_value = options.get('audio_only', False)
        if isinstance(audio_only_value, bool):
            audio_only = audio_only_value
        else:
            audio_only = str(audio_only_value).lower() in ["true", "1", "yes"]

        # 处理telegram_push参数
        telegram_push_value = options.get('telegram_push', False)
        if isinstance(telegram_push_value, bool):
            telegram_push = telegram_push_value
        else:
            telegram_push = str(telegram_push_value).lower() in ["true", "1", "yes"]

        # 处理web_callback参数
        web_callback_value = options.get('web_callback', False)
        if isinstance(web_callback_value, bool):
            web_callback = web_callback_value
        else:
            web_callback = str(web_callback_value).lower() in ["true", "1", "yes"]

        # 处理ios_callback参数
        ios_callback_value = options.get('ios_callback', False)
        if isinstance(ios_callback_value, bool):
            ios_callback = ios_callback_value
        else:
            ios_callback = str(ios_callback_value).lower() in ["true", "1", "yes"]

        standardized = {
            'source': options.get('source', 'api'),
            'quality': options.get('quality', 'medium'),
            'audio_only': audio_only,
            'format': options.get('format'),
            'telegram_push': telegram_push,
            'telegram_push_mode': options.get('telegram_push_mode', 'file'),
            'web_callback': web_callback,
            'ios_callback': ios_callback
        }

        return standardized


# 全局实例
_unified_api = None

def get_unified_download_api() -> UnifiedDownloadAPI:
    """获取统一下载API实例"""
    global _unified_api
    if _unified_api is None:
        _unified_api = UnifiedDownloadAPI()
    return _unified_api
