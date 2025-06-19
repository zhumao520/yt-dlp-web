"""
平台特定下载器模块

支持的平台：
- Twitter/X
- Instagram  
- TikTok
- Bilibili
- Facebook
- YouTube (通过专门的策略处理)
- 通用平台
"""

from .base import BasePlatform
from .twitter import TwitterPlatform
from .instagram import InstagramPlatform
from .tiktok import TikTokPlatform
from .bilibili import BilibiliPlatform
from .facebook import FacebookPlatform
from .generic import GenericPlatform

# 平台映射
PLATFORM_MAPPING = {
    # Twitter/X
    'twitter.com': TwitterPlatform,
    'x.com': TwitterPlatform,
    
    # Instagram
    'instagram.com': InstagramPlatform,
    
    # TikTok
    'tiktok.com': TikTokPlatform,
    
    # Bilibili
    'bilibili.com': BilibiliPlatform,
    
    # Facebook
    'facebook.com': FacebookPlatform,
    'fb.com': FacebookPlatform,
    
    # 其他网站使用通用平台
}

def get_platform_for_url(url: str) -> BasePlatform:
    """根据 URL 获取对应的平台处理器"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        
        # 查找匹配的平台
        for platform_domain, platform_class in PLATFORM_MAPPING.items():
            if platform_domain in domain:
                return platform_class()
        
        # 默认使用通用平台
        return GenericPlatform()
        
    except Exception:
        return GenericPlatform()

__all__ = [
    'BasePlatform',
    'TwitterPlatform', 
    'InstagramPlatform',
    'TikTokPlatform',
    'BilibiliPlatform',
    'FacebookPlatform',
    'GenericPlatform',
    'get_platform_for_url',
    'PLATFORM_MAPPING'
]
