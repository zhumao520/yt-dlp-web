"""
基础平台类

定义所有平台下载器的通用接口和基础功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class BasePlatform(ABC):
    """基础平台类"""
    
    def __init__(self):
        self.name = self.__class__.__name__.replace('Platform', '')
        self.supported_domains = []
        
    @abstractmethod
    def get_config(self, url: str, quality: str = 'best', user_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取平台特定的 yt-dlp 配置"""
        pass
    
    @abstractmethod
    def get_format_selector(self, quality: str = 'best') -> str:
        """获取格式选择器"""
        pass
    
    def get_http_headers(self) -> Dict[str, str]:
        """获取 HTTP 请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }
    
    def get_extractor_args(self) -> Dict[str, Any]:
        """获取提取器参数"""
        return {}
    
    def get_retry_config(self) -> Dict[str, int]:
        """获取重试配置 - 已弃用，配置已合并到 get_config() 中"""
        # 保留此方法以维持向后兼容性，但实际配置在 get_config() 中
        return {
            'retries': 3,
            'fragment_retries': 3,
            'extractor_retries': 2,
        }

    def _merge_retry_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """合并重试配置到主配置中 - 代码复用方法"""
        retry_config = self.get_retry_config()
        config.update(retry_config)
        return config

    def _build_enhanced_config(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """构建增强配置 - 统一应用重试、睡眠等配置的代码复用方法"""
        # 1. 应用重试配置
        enhanced_config = self._merge_retry_config(base_config.copy())

        # 2. 应用睡眠配置
        sleep_config = self.get_sleep_config()
        enhanced_config.update(sleep_config)

        # 3. 应用字幕配置
        subtitle_config = self.get_subtitle_config()
        enhanced_config.update(subtitle_config)

        return enhanced_config
    
    def get_sleep_config(self) -> Dict[str, int]:
        """获取睡眠配置"""
        return {
            'sleep_interval': 1,
            'max_sleep_interval': 3,
        }
    
    def supports_subtitles(self) -> bool:
        """是否支持字幕"""
        return False
    
    def get_subtitle_config(self, user_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取字幕配置 - 支持用户自定义选择"""
        # 🔧 检查用户是否选择下载字幕
        user_wants_subtitles = user_options and user_options.get('download_subtitles', False)

        if self.supports_subtitles() and user_wants_subtitles:
            return {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'zh-CN'],
            }
        return {
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
    
    def get_base_config(self, user_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取基础配置 - 支持用户自定义选择"""
        config = {}
        
        # HTTP 请求头
        config['http_headers'] = self.get_http_headers()
        
        # 提取器参数
        extractor_args = self.get_extractor_args()
        if extractor_args:
            config['extractor_args'] = extractor_args
        
        # 重试配置
        config.update(self.get_retry_config())
        
        # 睡眠配置
        config.update(self.get_sleep_config())
        
        # 字幕配置 - 传递用户选项
        config.update(self.get_subtitle_config(user_options))

        # 🔧 额外文件下载配置 - 根据用户选择（仅支持缩略图）
        if user_options:
            config.update({
                'writethumbnail': user_options.get('download_thumbnail', False),
            })
        else:
            # 默认不下载缩略图
            config.update({
                'writethumbnail': False,
            })

        return config
    
    def is_supported(self, url: str) -> bool:
        """检查是否支持该 URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.lower())
            domain = parsed.netloc
            
            return any(supported_domain in domain for supported_domain in self.supported_domains)
        except Exception:
            return False
    
    def log_config(self, url: str):
        """记录配置信息"""
        logger.info(f"🎯 使用 {self.name} 平台配置: {url}")
    
    def __str__(self):
        return f"{self.name}Platform"
    
    def __repr__(self):
        return f"<{self.__class__.__name__} domains={self.supported_domains}>"
