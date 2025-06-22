"""
通用平台下载器配置

适用于所有其他网站的通用下载配置
"""

from typing import Dict, Any, List
from .base import BasePlatform


class GenericPlatform(BasePlatform):
    """通用平台配置"""
    
    def __init__(self):
        super().__init__()
        self.supported_domains = ['*']  # 支持所有域名
    
    def get_http_headers(self) -> Dict[str, str]:
        """通用请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """通用提取器参数"""
        return {}
    
    def get_retry_config(self) -> Dict[str, int]:
        """通用重试配置"""
        return {
            'retries': 3,
            'fragment_retries': 3,
            'extractor_retries': 2,
        }
    
    def get_sleep_config(self) -> Dict[str, int]:
        """通用睡眠配置"""
        return {
            'sleep_interval': 1,
            'max_sleep_interval': 2,
        }
    
    def supports_subtitles(self) -> bool:
        """通用字幕支持"""
        return True
    
    def get_subtitle_config(self) -> Dict[str, Any]:
        """通用字幕配置"""
        return {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-CN'],
        }
    
    def get_format_selector(self, quality: str = 'best', url: str = '') -> str:
        """通用格式选择器 - 支持HLS/m3u8"""
        # 检查是否为HLS/m3u8链接
        is_hls = url.lower().endswith('.m3u8') or 'm3u8' in url.lower()

        # 对于HLS流，使用最简单的格式选择器
        if is_hls:
            return '0'  # HLS流通常只有一个格式，ID为0

        # 对于其他格式，使用复杂的格式选择器
        if quality == 'best':
            return 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        elif quality == 'worst':
            return 'worst[ext=mp4]/worst[ext=webm]/worst'
        elif quality.isdigit():
            return f'best[height<={quality}][ext=mp4]/best[height<={quality}]/bestvideo[height<={quality}]+bestaudio/best'
        else:
            return 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
    
    def get_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """获取通用完整配置 - 支持HLS/m3u8"""
        config = self.get_base_config()

        # 添加格式选择器
        config['format'] = self.get_format_selector(quality, url)

        # 检查是否为HLS/m3u8链接
        is_hls = url.endswith('.m3u8') or 'm3u8' in url.lower()

        # 通用配置
        config.update({
            # 字幕配置
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-CN'],
            'writethumbnail': True,

            # 网络优化
            'socket_timeout': 30,
            'http_chunk_size': 10485760,  # 10MB chunks

            # 通用选项
            'extract_flat': False,
            'ignoreerrors': False,

            # 输出优化
            'no_warnings': False,
        })

        # HLS/m3u8 特殊配置
        if is_hls:
            config.update({
                'hls_prefer_native': True,
                'hls_use_mpegts': True,
                'fragment_retries': 10,
                'retry_sleep': 1,
                'concurrent_fragments': 4,
                'retries': 5,
                'file_access_retries': 3,
                # 对于HLS流，不指定格式让yt-dlp自动选择
                'format': None,
            })
            # 移除可能冲突的格式选择器
            if 'format' in config:
                del config['format']

        self.log_config(url)
        return config
    
    def get_quality_options(self) -> Dict[str, str]:
        """获取质量选项"""
        return {
            'best': 'best[ext=mp4]/best[ext=webm]/best',
            'high': 'best[height<=1080][ext=mp4]/best[height<=1080]/best',
            'medium': 'best[height<=720][ext=mp4]/best[height<=720]/best',
            'low': 'best[height<=480][ext=mp4]/best[height<=480]/best',
            'worst': 'worst[ext=mp4]/worst[ext=webm]/worst'
        }
    
    def get_supported_sites(self) -> List[str]:
        """获取支持的网站列表（部分）"""
        return [
            'YouTube', 'Vimeo', 'Dailymotion', 'Twitch',
            'Reddit', 'Imgur', 'SoundCloud', 'Bandcamp',
            'Archive.org', 'BBC iPlayer', 'CNN', 'ESPN',
            'Pornhub', 'Xvideos', 'YouPorn', 'RedTube',
            'Crunchyroll', 'Funimation', 'VRV', 'Rooster Teeth',
            'Udemy', 'Coursera', 'Khan Academy', 'TED',
            'Twitch', 'Mixer', 'DLive', 'Trovo',
            # ... 还有数百个网站
        ]
    
    def get_api_info(self) -> Dict[str, Any]:
        """获取 API 信息"""
        return {
            'type': 'generic',
            'supported_features': [
                'video_download',
                'audio_download',
                'subtitle_download',
                'thumbnail_download',
                'playlist_download'
            ],
            'limitations': [
                'site_specific_limitations',
                'rate_limiting_varies',
                'format_availability_varies'
            ]
        }
    
    def get_troubleshooting_tips(self) -> List[str]:
        """获取故障排除提示"""
        return [
            "如果下载失败，尝试更新 yt-dlp 到最新版本",
            "某些网站可能需要特定的 User-Agent",
            "使用代理可能有助于绕过地区限制",
            "某些内容可能需要登录或订阅",
            "检查网站是否支持直接下载",
            "尝试不同的质量选项",
            "某些网站可能有反爬虫机制"
        ]
    
    def is_supported(self, url: str) -> bool:
        """通用平台支持所有 URL"""
        return True
    
    def get_platform_specific_tips(self, url: str) -> List[str]:
        """根据 URL 获取平台特定提示"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.lower())
            domain = parsed.netloc
            
            # 根据域名提供特定提示
            if 'youtube.com' in domain or 'youtu.be' in domain:
                return ["建议使用专门的 YouTube 下载策略"]
            elif 'vimeo.com' in domain:
                return ["Vimeo 可能需要登录才能下载某些内容"]
            elif 'twitch.tv' in domain:
                return ["Twitch 直播需要特殊处理", "VOD 下载可能需要订阅"]
            else:
                return self.get_troubleshooting_tips()
                
        except Exception:
            return self.get_troubleshooting_tips()
