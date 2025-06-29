"""
Facebook 平台下载器配置

专门针对 Facebook 平台的下载优化
"""

from typing import Dict, Any, List
from .base import BasePlatform


class FacebookPlatform(BasePlatform):
    """Facebook 平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['facebook.com', 'fb.com']
    
    def get_http_headers(self) -> Dict[str, str]:
        """Facebook 专用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """Facebook 提取器参数"""
        return {
            'facebook': {
                'api': ['web', 'mobile'],  # 使用多种 API
            }
        }
    
    def get_retry_config(self) -> Dict[str, int]:
        """Facebook 重试配置"""
        return {
            'retries': 4,
            'fragment_retries': 4,
            'extractor_retries': 3,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """Facebook 睡眠配置"""
        return {
            'sleep_interval': 2,
            'max_sleep_interval': 4,
        }
    
    def supports_subtitles(self) -> bool:
        """Facebook 可能有字幕"""
        return True
    
    def get_subtitle_config(self) -> Dict[str, Any]:
        """Facebook 字幕配置"""
        return {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'es', 'fr', 'de', 'zh-CN'],
        }
    
    def get_format_selector(self, quality: str = 'best', url: str = '') -> str:
        """Facebook 格式选择器"""
        if quality == 'best':
            return 'best[ext=mp4][height<=1080]/best[ext=webm][height<=1080]/best[height<=1080]/best/worst'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=webm]/worst/best[height<=480]/best'
        elif quality.isdigit():
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best/worst'
        else:
            return 'best[ext=mp4][height<=1080]/best[height<=1080]/best/worst'

    def get_enhanced_format_selector(self, quality: str) -> str:
        """增强的格式选择器 - 遵循yt-dlp最佳实践"""
        # Facebook增强格式选择策略：更多回退选项
        base_selectors = [
            'best',  # 最优先：任何最佳格式
            'worst',  # 最终回退：任何最差格式
            'best[ext=mp4]',  # MP4格式
            'best[ext=webm]',  # WebM格式
            'best[ext=m4v]',  # M4V格式
            'best[protocol=https]',  # HTTPS协议
            'best[protocol=http]',  # HTTP协议
        ]

        if quality == 'high':
            quality_selectors = [
                'best[height<=1080][ext=mp4]',
                'best[height<=720][ext=mp4]',
                'best[height<=1080]',
                'best[height<=720]',
                'best[width<=1920]',
                'best[width<=1280]',
            ]
        elif quality == 'medium':
            quality_selectors = [
                'best[height<=720][ext=mp4]',
                'best[height<=480][ext=mp4]',
                'best[height<=720]',
                'best[height<=480]',
                'best[width<=1280]',
                'best[width<=854]',
            ]
        elif quality == 'low':
            quality_selectors = [
                'best[height<=480][ext=mp4]',
                'best[height<=360][ext=mp4]',
                'best[height<=480]',
                'best[height<=360]',
                'best[width<=854]',
                'best[width<=640]',
            ]
        else:
            quality_selectors = []

        # 组合所有选择器，确保有足够的备选方案
        all_selectors = quality_selectors + base_selectors
        return '/'.join(all_selectors)
    
    def get_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """获取 Facebook 完整配置"""
        config = self.get_base_config()
        
        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)
        
        # Facebook 特殊配置
        config.update({
            # 字幕配置
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'es', 'fr', 'de', 'zh-CN'],
            'writethumbnail': True,   # Facebook 缩略图有用
            
            # 网络优化
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks
            
            # Facebook 特殊选项
            'extract_flat': False,
            'ignoreerrors': False,
            
            # 输出优化
            'no_warnings': False,
        })
        
        self.log_config(url)
        return config
    
    def get_quality_options(self) -> Dict[str, str]:
        """获取质量选项"""
        return {
            'best': 'best[ext=mp4][height<=1080]/best[ext=webm][height<=1080]/best[height<=1080]/best/worst',
            'high': 'best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best',
            'medium': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            'low': 'best[height<=480][ext=mp4]/best[height<=480]/worst[ext=mp4]/worst',
            'worst': 'worst[ext=mp4]/worst[ext=webm]/worst/best[height<=480]/best'
        }
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取 API 信息"""
        return {
            'primary_api': 'web',
            'fallback_api': 'mobile',
            'supported_features': [
                'video_download',
                'subtitle_download',
                'thumbnail_download',
                'live_stream_download'
            ],
            'limitations': [
                'private_content_limited',
                'login_required',
                'rate_limited'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "私人内容需要登录 Facebook 账户",
            "某些内容可能需要特定的访问权限",
            "使用 Cookies 可以提高成功率",
            "频繁请求可能触发 Facebook 限制",
            "直播内容可能需要特殊处理",
            "某些地区的内容可能被限制"
        ]
    
    def get_content_types(self) -> List[str]:
        """支持的内容类型"""
        return [
            'video',      # 普通视频
            'live',       # 直播
            'story',      # 故事
            'reel',       # 短视频
            'watch',      # Facebook Watch
        ]
    
    def is_live_url(self, url: str) -> bool:
        """检查是否为直播 URL"""
        return '/live/' in url or 'live_video' in url
    
    def is_story_url(self, url: str) -> bool:
        """检查是否为故事 URL"""
        return '/stories/' in url
    
    def is_reel_url(self, url: str) -> bool:
        """检查是否为 Reel URL"""
        return '/reel/' in url or '/reels/' in url
    
    def is_watch_url(self, url: str) -> bool:
        """检查是否为 Facebook Watch URL"""
        return '/watch/' in url or 'watch.facebook.com' in url
