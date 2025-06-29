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
    
    def get_format_selector(self, quality: str = 'best', url: str = '') -> str:
        """Bilibili 格式选择器 - 优化非会员格式选择"""
        # Bilibili格式选择策略：优先选择可用的非会员格式
        base_selectors = [
            # 优先选择合并格式（视频+音频）
            'best[ext=mp4]',
            'best[ext=flv]',
            # 备选：分离格式，自动合并
            'best[height<=720]+bestaudio/best[height<=720]',
            'best[height<=480]+bestaudio/best[height<=480]',
            # 最后备选：任何可用格式
            'best/worst'
        ]

        if quality == 'high':
            quality_selectors = [
                'best[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
                'best[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
            ]
        elif quality == 'medium':
            quality_selectors = [
                'best[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
                'best[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
            ]
        elif quality == 'low':
            quality_selectors = [
                'best[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
                'best[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]',
            ]
        else:
            quality_selectors = []

        # 组合所有选择器
        all_selectors = quality_selectors + base_selectors

        # 返回用斜杠分隔的格式选择器字符串
        return '/'.join(all_selectors)

    def get_enhanced_format_selector(self, quality: str) -> str:
        """增强的格式选择器 - 遵循yt-dlp最佳实践，提供更多回退选项"""
        # Bilibili增强格式选择策略：更宽松的选择，确保能下载到内容
        base_selectors = [
            'best',  # 最优先：任何最佳格式
            'worst',  # 最终回退：任何最差格式
            'best[ext=mp4]',  # MP4格式
            'best[ext=flv]',  # FLV格式
            'best[ext=webm]',  # WebM格式
            'best[protocol=https]',  # HTTPS协议
            'best[protocol=http]',  # HTTP协议
            'best[height<=720]+bestaudio/best[height<=720]',  # 合并格式回退
            'best[height<=480]+bestaudio/best[height<=480]',  # 更低质量合并
        ]

        if quality == 'high':
            quality_selectors = [
                'best[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
                'best[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
                'best[height<=1080]',
                'best[height<=720]',
                'best[width<=1920]',
                'best[width<=1280]',
            ]
        elif quality == 'medium':
            quality_selectors = [
                'best[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
                'best[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
                'best[height<=720]',
                'best[height<=480]',
                'best[width<=1280]',
                'best[width<=854]',
            ]
        elif quality == 'low':
            quality_selectors = [
                'best[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
                'best[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]',
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
        """获取 Bilibili 完整配置 - 包含FFmpeg自动合并"""
        config = self.get_base_config()

        # 添加格式选择器
        config['format'] = self.get_format_selector(quality)

        # 添加FFmpeg路径配置，确保自动合并
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            config['ffmpeg_location'] = ffmpeg_path
            config['merge_output_format'] = 'mp4'  # 强制合并为MP4格式
            logger.info(f"✅ Bilibili配置FFmpeg自动合并: {ffmpeg_path}")
        else:
            logger.warning("⚠️ 未找到FFmpeg，Bilibili视频可能无法自动合并")

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

    def _get_ffmpeg_path(self) -> str:
        """获取FFmpeg路径"""
        try:
            # 尝试从FFmpeg工具模块获取
            try:
                from modules.downloader.ffmpeg_tools import get_ffmpeg_path
                ffmpeg_path = get_ffmpeg_path()
                if ffmpeg_path:
                    return ffmpeg_path
            except ImportError:
                pass

            # 尝试项目路径
            from pathlib import Path
            project_ffmpeg = Path('ffmpeg/bin')
            if project_ffmpeg.exists():
                return str(project_ffmpeg.resolve())

            # 尝试系统路径
            import shutil
            which_ffmpeg = shutil.which('ffmpeg')
            if which_ffmpeg:
                return str(Path(which_ffmpeg).parent)

            return None

        except Exception as e:
            logger.debug(f"🔍 获取FFmpeg路径失败: {e}")
            return None
    
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
