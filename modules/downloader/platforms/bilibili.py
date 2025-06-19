"""
Bilibili 平台下载器配置

专门针对 Bilibili 平台的下载优化
"""

from typing import Dict, Any, List
from .base import BasePlatform


class BilibiliPlatform(BasePlatform):
    """Bilibili 平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['bilibili.com']
    
    def get_http_headers(self) -> Dict[str, str]:
        """Bilibili 专用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.bilibili.com',
            'Cache-Control': 'max-age=0',
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """Bilibili 提取器参数"""
        return {
            'bilibili': {
                'api': ['web', 'app'],  # 使用多种 API
                'download_archive': True,  # 支持合集下载
            }
        }
    
    def get_retry_config(self) -> Dict[str, int]:
        """Bilibili 重试配置"""
        return {
            'retries': 4,
            'fragment_retries': 4,
            'extractor_retries': 3,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """Bilibili 睡眠配置"""
        return {
            'sleep_interval': 1,
            'max_sleep_interval': 2,
        }
    
    def supports_subtitles(self) -> bool:
        """Bilibili 支持字幕"""
        return True
    
    def get_subtitle_config(self) -> Dict[str, Any]:
        """Bilibili 字幕配置"""
        return {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-CN', 'zh-TW', 'en'],  # 支持多语言字幕
            'subtitlesformat': 'srt',  # 首选 SRT 格式
        }
    
    def get_format_selector(self, quality: str = 'best') -> str:
        """Bilibili 格式选择器"""
        if quality == 'best':
            return 'best[ext=mp4][height<=1080]/best[ext=flv][height<=1080]/best[height<=1080]/best/worst'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=flv]/worst/best[height<=480]/best'
        elif quality.isdigit():
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best/worst'
        else:
            return 'best[ext=mp4][height<=1080]/best[height<=1080]/best/worst'
    
    def get_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """获取 Bilibili 完整配置"""
        config = self.get_base_config()
        
        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)
        
        # Bilibili 特殊配置
        config.update({
            # 字幕配置
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-CN', 'zh-TW', 'en'],
            'writethumbnail': True,   # Bilibili 缩略图很重要
            
            # 网络优化
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks
            
            # Bilibili 特殊选项
            'extract_flat': False,
            'ignoreerrors': False,
            
            # 输出优化
            'no_warnings': False,
            
            # 分P视频支持
            'playlist_items': '1-50',  # 限制播放列表项目数量
        })
        
        self.log_config(url)
        return config
    
    def get_quality_options(self) -> Dict[str, str]:
        """获取质量选项"""
        return {
            'best': 'best[ext=mp4][height<=1080]/best[ext=flv][height<=1080]/best[height<=1080]/best/worst',
            'high': 'best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best',
            'medium': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            'low': 'best[height<=480][ext=mp4]/best[height<=480]/worst[ext=mp4]/worst',
            'worst': 'worst[ext=mp4]/worst[ext=flv]/worst/best[height<=480]/best'
        }
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取 API 信息"""
        return {
            'primary_api': 'web',
            'fallback_api': 'app',
            'supported_features': [
                'video_download',
                'subtitle_download',
                'thumbnail_download',
                'playlist_download',
                'series_download'
            ],
            'limitations': [
                'vip_content_limited',
                'region_restricted',
                'rate_limited'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "某些VIP内容需要会员账户",
            "港澳台地区内容可能需要特殊处理",
            "分P视频会自动下载多个文件",
            "使用中文环境可以提高兼容性",
            "某些直播内容可能无法下载",
            "番剧内容可能有版权限制"
        ]
    
    def get_content_types(self) -> List[str]:
        """支持的内容类型"""
        return [
            'video',      # 普通视频
            'bangumi',    # 番剧
            'live',       # 直播
            'audio',      # 音频
            'article',    # 专栏
            'space',      # 用户空间
        ]
    
    def is_bangumi_url(self, url: str) -> bool:
        """检查是否为番剧 URL"""
        return '/bangumi/' in url or '/anime/' in url
    
    def is_live_url(self, url: str) -> bool:
        """检查是否为直播 URL"""
        return '/live/' in url
    
    def is_audio_url(self, url: str) -> bool:
        """检查是否为音频 URL"""
        return '/audio/' in url
    
    def is_playlist_url(self, url: str) -> bool:
        """检查是否为播放列表 URL"""
        return '/playlist/' in url or 'p=' in url
