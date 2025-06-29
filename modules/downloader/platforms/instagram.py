"""
Instagram 平台下载器配置

专门针对 Instagram 平台的下载优化
"""

from typing import Dict, Any, List
from .base import BasePlatform


class InstagramPlatform(BasePlatform):
    """Instagram 平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['instagram.com']
    
    def get_http_headers(self) -> Dict[str, str]:
        """Instagram 专用请求头 - 移动端模拟"""
        return {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'X-Requested-With': 'XMLHttpRequest',  # Instagram 特有
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """Instagram 提取器参数"""
        return {
            'instagram': {
                'api': ['graphql', 'web'],  # 使用多种 API
                'include_stories': True,    # 包含故事
                'include_highlights': True, # 包含精选
            }
        }
    
    def get_retry_config(self) -> Dict[str, int]:
        """Instagram 重试配置"""
        return {
            'retries': 4,
            'fragment_retries': 4,
            'extractor_retries': 3,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """Instagram 睡眠配置 - 更保守的间隔"""
        return {
            'sleep_interval': 2,
            'max_sleep_interval': 5,
        }
    
    def supports_subtitles(self) -> bool:
        """Instagram 通常没有字幕"""
        return False
    
    def get_format_selector(self, quality: str = 'best', url: str = '') -> str:
        """Instagram 格式选择器"""
        if quality == 'best':
            return 'best[ext=mp4][height<=1080]/best[ext=m4v][height<=1080]/best[height<=1080]/best/worst'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=m4v]/worst/best[height<=480]/best'
        elif quality.isdigit():
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best/worst'
        else:
            return 'best[ext=mp4][height<=1080]/best[height<=1080]/best/worst'

    def get_enhanced_format_selector(self, quality: str) -> str:
        """增强的格式选择器 - 遵循yt-dlp最佳实践"""
        # Instagram增强格式选择策略：更多回退选项
        base_selectors = [
            'best',  # 最优先：任何最佳格式
            'worst',  # 最终回退：任何最差格式
            'best[ext=mp4]',  # MP4格式
            'best[ext=m4v]',  # M4V格式
            'best[ext=webm]',  # WebM格式
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
        """获取 Instagram 完整配置"""
        config = self.get_base_config()
        
        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)
        
        # Instagram 特殊配置
        config.update({
            # 禁用不必要的功能
            'writesubtitles': False,
            'writeautomaticsub': False,
            'writethumbnail': True,   # Instagram 缩略图很重要
            
            # 网络优化
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks
            
            # Instagram 特殊选项
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
            'best': 'best[ext=mp4][height<=1080]/best[ext=m4v][height<=1080]/best[height<=1080]/best/worst',
            'high': 'best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best',
            'medium': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            'low': 'best[height<=480][ext=mp4]/best[height<=480]/worst[ext=mp4]/worst',
            'worst': 'worst[ext=mp4]/worst[ext=m4v]/worst/best[height<=480]/best'
        }
    
    def get_content_types(self) -> List[str]:
        """支持的内容类型"""
        return [
            'posts',      # 普通帖子
            'stories',    # 故事
            'reels',      # 短视频
            'igtv',       # IGTV
            'highlights', # 精选故事
        ]
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取 API 信息"""
        return {
            'primary_api': 'graphql',
            'fallback_api': 'web',
            'supported_features': [
                'video_download',
                'image_download',
                'story_download',
                'reel_download',
                'igtv_download'
            ],
            'limitations': [
                'no_subtitles',
                'private_account_limited',
                'story_time_limited',
                'rate_limited'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "私人账户内容需要登录后才能下载",
            "故事内容有时间限制（24小时）",
            "使用移动端 User-Agent 提高成功率",
            "频繁请求可能触发 Instagram 限制",
            "某些内容可能需要特定的 Cookies",
            "Reels 和 IGTV 可能有不同的下载策略"
        ]
    
    def is_story_url(self, url: str) -> bool:
        """检查是否为故事 URL"""
        return '/stories/' in url.lower()
    
    def is_reel_url(self, url: str) -> bool:
        """检查是否为 Reel URL"""
        return '/reel/' in url.lower() or '/reels/' in url.lower()
    
    def is_igtv_url(self, url: str) -> bool:
        """检查是否为 IGTV URL"""
        return '/tv/' in url.lower() or '/igtv/' in url.lower()
