"""
TikTok 平台下载器配置

专门针对 TikTok 平台的下载优化
"""

from typing import Dict, Any, List
from .base import BasePlatform


class TikTokPlatform(BasePlatform):
    """TikTok 平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['tiktok.com']
    
    def get_http_headers(self) -> Dict[str, str]:
        """TikTok 专用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tiktok.com/',
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
        """TikTok 提取器参数"""
        return {
            'tiktok': {
                'api': ['web', 'mobile'],  # 使用多种 API
                'webpage_download': True,   # 下载网页
            }
        }
    
    def get_retry_config(self) -> Dict[str, int]:
        """TikTok 重试配置"""
        return {
            'retries': 4,
            'fragment_retries': 4,
            'extractor_retries': 3,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """TikTok 睡眠配置"""
        return {
            'sleep_interval': 1,
            'max_sleep_interval': 3,
        }
    
    def supports_subtitles(self) -> bool:
        """TikTok 通常没有字幕"""
        return False
    
    def get_format_selector(self, quality: str = 'best', url: str = '') -> str:
        """TikTok 格式选择器"""
        if quality == 'best':
            return 'best[ext=mp4][height<=1080]/best[ext=webm][height<=1080]/best[height<=1080]/best/worst'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=webm]/worst/best[height<=480]/best'
        elif quality.isdigit():
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best/worst'
        else:
            return 'best[ext=mp4][height<=1080]/best[height<=1080]/best/worst'
    
    def get_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """获取 TikTok 完整配置"""
        config = self.get_base_config()
        
        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)
        
        # TikTok 特殊配置
        config.update({
            # 禁用不必要的功能
            'writesubtitles': False,
            'writeautomaticsub': False,
            'writethumbnail': True,   # TikTok 缩略图有用
            
            # 网络优化
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks
            
            # TikTok 特殊选项
            'extract_flat': False,
            'ignoreerrors': False,
            
            # 地区相关
            'geo_bypass': True,
            'geo_bypass_country': 'US',  # 绕过地区限制
            
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
                'thumbnail_download',
                'metadata_extraction',
                'geo_bypass'
            ],
            'limitations': [
                'no_subtitles',
                'geo_restricted',
                'rate_limited',
                'watermark_present'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "某些地区的内容可能被限制访问",
            "使用代理可以绕过地区限制",
            "下载的视频可能包含 TikTok 水印",
            "频繁请求可能触发速率限制",
            "某些私人账户内容需要登录",
            "使用最新的 yt-dlp 版本以获得最佳兼容性"
        ]
    
    def get_region_info(self) -> Dict[str, Any]:
        """获取地区信息"""
        return {
            'supported_regions': ['US', 'EU', 'ASIA'],
            'restricted_regions': ['CN', 'IN'],  # 可能受限的地区
            'bypass_methods': ['proxy', 'vpn', 'geo_bypass'],
            'recommended_countries': ['US', 'UK', 'CA', 'AU']
        }
    
    def is_user_profile(self, url: str) -> bool:
        """检查是否为用户主页 URL"""
        return '/@' in url and '/video/' not in url
    
    def is_video_url(self, url: str) -> bool:
        """检查是否为单个视频 URL"""
        return '/video/' in url or url.count('/') >= 5
