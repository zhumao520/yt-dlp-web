"""
Twitter/X 平台下载器配置

专门针对 Twitter/X 平台的下载优化
"""

from typing import Dict, Any
from .base import BasePlatform


class TwitterPlatform(BasePlatform):
    """Twitter/X 平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['twitter.com', 'x.com']
    
    def get_http_headers(self) -> Dict[str, str]:
        """Twitter 专用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',  # Do Not Track - Twitter 特有
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """Twitter 提取器参数"""
        return {
            'twitter': {
                'api': ['syndication', 'legacy'],  # 使用多种 API
            }
        }
    
    def get_retry_config(self) -> Dict[str, int]:
        """Twitter 重试配置 - 更激进的重试"""
        return {
            'retries': 5,
            'fragment_retries': 5,
            'extractor_retries': 3,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """Twitter 睡眠配置"""
        return {
            'sleep_interval': 1,
            'max_sleep_interval': 3,
        }
    
    def supports_subtitles(self) -> bool:
        """Twitter 通常没有字幕"""
        return False
    
    def get_format_selector(self, quality: str = 'best') -> str:
        """Twitter 格式选择器 - 多重备用策略"""
        if quality == 'best':
            return 'best[ext=mp4]/best[ext=m4v]/best[height<=720]/best/worst'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=m4v]/worst/best[height<=480]/best'
        elif quality.isdigit():
            # 数字质量 (如 720, 480)
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best[ext=mp4]/best/worst'
        else:
            # 其他情况
            return f'best[ext=mp4]/best[ext=m4v]/best/worst'
    
    def get_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """获取 Twitter 完整配置"""
        config = self.get_base_config()
        
        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)
        
        # Twitter 特殊配置
        config.update({
            # 禁用不必要的功能
            'writesubtitles': False,
            'writeautomaticsub': False,
            'writethumbnail': False,  # Twitter 缩略图通常不重要
            
            # 网络优化
            'socket_timeout': 30,
            'fragment_retries': 5,
            
            # 输出优化
            'no_warnings': False,  # 保留警告以便调试
        })
        
        self.log_config(url)
        return config
    
    def get_quality_options(self) -> Dict[str, str]:
        """获取质量选项"""
        return {
            'best': 'best[ext=mp4]/best[ext=m4v]/best[height<=720]/best/worst',
            'high': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
            'medium': 'best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best',
            'low': 'best[height<=360][ext=mp4]/best[height<=360]/worst[ext=mp4]/worst',
            'worst': 'worst[ext=mp4]/worst[ext=m4v]/worst/best[height<=480]/best'
        }
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取 API 信息"""
        return {
            'primary_api': 'syndication',
            'fallback_api': 'legacy',
            'supported_features': [
                'video_download',
                'image_download', 
                'thread_support',
                'guest_access'
            ],
            'limitations': [
                'no_subtitles',
                'quality_limited',
                'rate_limited'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "如果下载失败，尝试使用代理",
            "某些私人账户的内容可能需要登录",
            "视频质量可能受到 Twitter 限制",
            "使用 Cookies 可以提高成功率",
            "频繁请求可能触发速率限制"
        ]
