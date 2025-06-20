# -*- coding: utf-8 -*-
"""
核心下载管理器 - 精简版

专注于核心下载管理功能，移除复杂的辅助功能
"""

import os
import uuid
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class CoreDownloadManager:
    """核心下载管理器 - 精简版"""
    
    def __init__(self):
        self.downloads: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.executor = None
        
        # 导入辅助模块
        self._import_helpers()
        self._initialize()
    
    def _import_helpers(self):
        """导入辅助模块"""
        try:
            from .retry_manager import RetryManager
            from .ffmpeg_tools import FFmpegTools
            from .filename_processor import FilenameProcessor
            from .youtube_strategies import YouTubeStrategies
            from .video_extractor import VideoExtractor
            
            self.retry_manager = RetryManager()
            self.ffmpeg_tools = FFmpegTools()
            self.filename_processor = FilenameProcessor()
            self.youtube_strategies = YouTubeStrategies()
            self.video_extractor = VideoExtractor()
            
            logger.info("✅ 辅助模块导入完成")
            
        except ImportError as e:
            logger.warning(f"⚠️ 部分辅助模块导入失败: {e}")
            # 创建空的占位符
            self.retry_manager = None
            self.ffmpeg_tools = None
            self.filename_processor = None
            self.youtube_strategies = None
            self.video_extractor = None
    
    def _initialize(self):
        """初始化下载管理器"""
        try:
            # 灵活的配置导入
            try:
                from core.config import get_config
            except ImportError:
                try:
                    from app.core.config import get_config
                except ImportError:
                    def get_config(key, default=None):
                        logger.warning(f"⚠️ 无法导入配置模块，使用默认值: {key} = {default}")
                        return default

            # 获取配置
            max_concurrent = get_config('downloader.max_concurrent', 3)
            self.output_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
            self.temp_dir = Path(get_config('downloader.temp_dir', '/app/temp'))

            # 创建目录
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # 清理遗留任务
            self._cleanup_orphaned_downloads()

            # 创建线程池
            self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

            # 启动自动清理
            self._start_cleanup()

            logger.info(f"✅ 核心下载管理器初始化完成 - 最大并发: {max_concurrent}")

        except Exception as e:
            logger.error(f"❌ 核心下载管理器初始化失败: {e}")
            raise
    
    def _cleanup_orphaned_downloads(self):
        """清理遗留的下载任务"""
        try:
            # 灵活的数据库导入
            try:
                from core.database import get_database
            except ImportError:
                try:
                    from app.core.database import get_database
                except ImportError:
                    logger.warning("⚠️ 无法导入数据库模块，跳过清理遗留任务")
                    return
            
            db = get_database()
            orphaned_downloads = db.execute_query('''
                SELECT id, url FROM downloads
                WHERE status IN ('pending', 'downloading')
            ''')

            if orphaned_downloads:
                logger.info(f"🧹 发现 {len(orphaned_downloads)} 个遗留下载任务，正在清理...")
                
                for download in orphaned_downloads:
                    db.execute_update('''
                        UPDATE downloads
                        SET status = 'failed',
                            error_message = '应用重启，任务已取消',
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (download['id'],))
                
                logger.info(f"✅ 已清理 {len(orphaned_downloads)} 个遗留下载任务")

        except Exception as e:
            logger.error(f"❌ 清理遗留下载任务失败: {e}")
    
    def _start_cleanup(self):
        """启动自动清理"""
        try:
            from .cleanup import get_cleanup_manager
            cleanup_manager = get_cleanup_manager()
            cleanup_manager.start()
        except Exception as e:
            logger.warning(f"⚠️ 启动自动清理失败: {e}")
    
    def create_download(self, url: str, options: Dict[str, Any] = None) -> str:
        """创建下载任务"""
        try:
            download_id = str(uuid.uuid4())
            
            # 创建下载记录
            download_info = {
                'id': download_id,
                'url': url,
                'status': 'pending',
                'progress': 0,
                'title': None,
                'file_path': None,
                'file_size': None,
                'error_message': None,
                'created_at': datetime.now(),
                'completed_at': None,
                'options': options or {},
                'retry_count': 0,
                'max_retries': self._get_max_retries(options)
            }
            
            with self.lock:
                self.downloads[download_id] = download_info
            
            # 保存到数据库
            self._save_to_database(download_id, url)
            
            # 发送事件
            self._emit_event('DOWNLOAD_STARTED', {
                'download_id': download_id,
                'url': url,
                'options': options
            })
            
            # 提交下载任务
            self.executor.submit(self._execute_download, download_id)
            
            logger.info(f"📥 创建下载任务: {download_id} - {url}")
            return download_id
            
        except Exception as e:
            logger.error(f"❌ 创建下载任务失败: {e}")
            raise
    
    def get_download(self, download_id: str) -> Optional[Dict[str, Any]]:
        """获取下载信息"""
        with self.lock:
            return self.downloads.get(download_id)
    
    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """获取所有下载"""
        with self.lock:
            return list(self.downloads.values())
    
    def cancel_download(self, download_id: str) -> bool:
        """取消下载"""
        try:
            with self.lock:
                download_info = self.downloads.get(download_id)
                if not download_info:
                    return False
                
                if download_info['status'] in ['completed', 'failed', 'cancelled']:
                    return False
                
                download_info['status'] = 'cancelled'
                download_info['error_message'] = '用户取消'
            
            # 更新数据库
            self._update_database_status(download_id, 'cancelled', error_message='用户取消')
            
            logger.info(f"🚫 取消下载: {download_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 取消下载失败: {e}")
            return False
    
    def _execute_download(self, download_id: str):
        """执行下载任务"""
        try:
            with self.lock:
                download_info = self.downloads.get(download_id)
                if not download_info:
                    return

                url = download_info['url']
                options = download_info['options']

            logger.info(f"🔄 开始执行下载: {download_id} - {url}")

            # 更新状态为下载中
            self._update_download_status(download_id, 'downloading', 0)

            # 提取视频信息
            if self.video_extractor:
                video_info = self.video_extractor.extract_info(url)
            else:
                video_info = self._fallback_extract_info(url)
            
            if not video_info:
                self._handle_download_failure(download_id, '无法获取视频信息')
                return

            # 更新标题
            title = video_info.get('title', 'Unknown')
            with self.lock:
                self.downloads[download_id]['title'] = title

            # 执行下载
            file_path = self._download_video(download_id, url, video_info, options)

            if file_path and Path(file_path).exists():
                logger.info(f"✅ 下载完成: {download_id} - {title}")
            else:
                self._handle_download_failure(download_id, '下载文件不存在')

        except Exception as e:
            logger.error(f"❌ 下载执行失败 {download_id}: {e}")
            self._handle_download_failure(download_id, str(e))
    
    def _handle_download_failure(self, download_id: str, error_msg: str):
        """处理下载失败"""
        try:
            if self.retry_manager:
                # 使用重试管理器
                should_retry = self.retry_manager.should_retry(download_id, error_msg)
                if should_retry:
                    self.retry_manager.schedule_retry(download_id, self._execute_download)
                    return
            
            # 标记为最终失败
            self._update_download_status(download_id, 'failed', error_message=error_msg)
            
            # 发送失败事件
            self._emit_event('DOWNLOAD_FAILED', {
                'download_id': download_id,
                'error': error_msg
            })
            
            logger.error(f"❌ 下载最终失败: {download_id} - {error_msg}")
            
        except Exception as e:
            logger.error(f"❌ 处理下载失败时出错: {e}")
    
    def _download_video(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """下载视频 - 委托给策略模块"""
        try:
            if self.youtube_strategies and self._is_youtube_url(url):
                logger.info(f"🎬 使用YouTube专用策略下载: {url}")
                return self.youtube_strategies.download(download_id, url, video_info, options)
            else:
                logger.info(f"🌐 使用通用yt-dlp下载非YouTube网站: {url}")
                return self._fallback_download(download_id, url, video_info, options)
        except Exception as e:
            logger.error(f"❌ 视频下载失败: {e}")
            return None

    def _is_youtube_url(self, url: str) -> bool:
        """检查是否为YouTube URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.lower())

            # YouTube 官方域名列表
            youtube_domains = [
                'youtube.com',
                'www.youtube.com',
                'm.youtube.com',
                'music.youtube.com',
                'youtu.be',
                'youtube-nocookie.com',
                'www.youtube-nocookie.com'
            ]

            is_youtube = parsed.netloc in youtube_domains

            if is_youtube:
                logger.debug(f"✅ 检测到YouTube URL: {parsed.netloc}")
            else:
                logger.debug(f"🌐 检测到非YouTube URL: {parsed.netloc}")

            return is_youtube

        except Exception as e:
            logger.error(f"❌ URL检测失败: {e}")
            # 如果检测失败，保守地假设不是YouTube
            return False
    
    def _fallback_extract_info(self, url: str) -> Optional[Dict[str, Any]]:
        """备用信息提取 - 针对不同网站优化"""
        try:
            import yt_dlp

            # 构建基本选项
            ydl_opts = {
                'quiet': True,
                'no_warnings': False,
                'extract_flat': False,
            }

            # 使用新的平台配置系统
            platform_config = self._get_platform_config(url, 'best')
            ydl_opts.update(platform_config)

            # 添加代理配置
            proxy = self._get_proxy_config()
            if proxy:
                ydl_opts['proxy'] = proxy
                logger.debug(f"✅ 信息提取使用代理: {proxy}")

            # 添加 Cookies 支持
            cookies_path = self._get_cookies_for_site(url)
            if cookies_path:
                ydl_opts['cookiefile'] = cookies_path
                logger.debug(f"✅ 信息提取使用Cookies: {cookies_path}")

            logger.info(f"🔍 信息提取配置: {self._get_site_name(url)}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    logger.info(f"✅ 信息提取成功: {info.get('title', 'Unknown')}")
                    return info
                else:
                    logger.warning("⚠️ 信息提取返回空结果")
                    return None

        except Exception as e:
            logger.error(f"❌ 备用信息提取失败: {e}")
            return None
    
    def _fallback_download(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """备用下载方法 - 针对不同网站优化，包含FFmpeg自动合并"""
        try:
            import yt_dlp

            # 构建基本选项
            ydl_opts = {
                'outtmpl': str(self.output_dir / f'{download_id}.%(ext)s'),
                'retries': 3,
                'fragment_retries': 3,
                'extractor_retries': 3,
                'no_warnings': False,
                'ignoreerrors': False,
            }

            # 添加FFmpeg配置，确保自动合并
            ffmpeg_path = self._get_ffmpeg_path()
            if ffmpeg_path:
                ydl_opts['ffmpeg_location'] = ffmpeg_path
                ydl_opts['merge_output_format'] = 'mp4'  # 强制合并为MP4格式
                logger.info(f"✅ 配置FFmpeg自动合并: {ffmpeg_path}")
            else:
                logger.warning("⚠️ 未找到FFmpeg，视频可能无法自动合并")

            # 使用新的平台配置系统（包含格式选择）
            platform_config = self._get_platform_config(url, options.get('quality', 'best'))
            ydl_opts.update(platform_config)

            # 添加代理配置
            proxy = self._get_proxy_config()
            if proxy:
                ydl_opts['proxy'] = proxy
                logger.info(f"✅ 备用下载使用代理: {proxy}")

            # 添加 Cookies 支持
            cookies_path = self._get_cookies_for_site(url)
            if cookies_path:
                ydl_opts['cookiefile'] = cookies_path
                logger.info(f"✅ 备用下载使用Cookies: {cookies_path}")

            logger.info(f"🌐 备用下载配置: {self._get_site_name(url)}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 查找下载的文件
            for file_path in self.output_dir.glob(f'{download_id}.*'):
                if file_path.is_file():
                    logger.info(f"✅ 备用下载成功: {file_path}")
                    return str(file_path)

            logger.warning("⚠️ 备用下载完成但未找到文件")
            return None

        except Exception as e:
            logger.error(f"❌ 备用下载失败: {e}")
            return None

    def _get_platform_config(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """使用新的平台配置系统"""
        try:
            from .platforms import get_platform_for_url

            # 获取对应的平台处理器
            platform = get_platform_for_url(url)

            # 获取平台特定配置
            config = platform.get_config(url, quality)

            logger.info(f"🎯 使用平台配置: {platform.name} for {url}")
            return config

        except Exception as e:
            logger.error(f"❌ 获取平台配置失败: {e}")
            # 回退到旧的配置方法
            return self._get_site_specific_config(url)

    def _get_site_specific_config(self, url: str) -> Dict[str, Any]:
        """获取网站特定配置"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.lower())
            domain = parsed.netloc

            # X 平台（Twitter）特殊配置 - 增强版
            if any(x in domain for x in ['twitter.com', 'x.com']):
                return {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Referer': 'https://twitter.com/',
                        'Origin': 'https://twitter.com',
                    },
                    'sleep_interval': 2,  # 增加延迟避免限制
                    'max_sleep_interval': 5,
                    'writesubtitles': False,
                    'writeautomaticsub': False,
                    'writethumbnail': True,  # 保留缩略图
                    # 更宽松的格式选择策略
                    'format': 'best[ext=mp4]/best[ext=m4v]/best[height<=1080]/best[height<=720]/best[height<=480]/best/worst',
                    # 增强的 X 平台选项
                    'extractor_args': {
                        'twitter': {
                            'api': ['syndication', 'legacy', 'graphql'],  # 使用所有可用 API
                            'legacy_api': True,
                            'guest_token': True,
                            'syndication_api': True,
                        }
                    },
                    # 网络优化
                    'socket_timeout': 60,
                    'fragment_retries': 8,
                    'http_chunk_size': 10485760,  # 10MB chunks
                    # 增强重试策略
                    'retries': 8,
                    'extractor_retries': 5,
                    # 错误处理
                    'ignoreerrors': False,
                    'no_warnings': False,
                    # 地区绕过
                    'geo_bypass': True,
                    'geo_bypass_country': 'US',
                    # 认证设置
                    'username': None,
                    'password': None,
                    'netrc': False,
                }

            # Instagram 特殊配置
            elif 'instagram.com' in domain:
                return {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                    },
                    'sleep_interval': 2,
                    'max_sleep_interval': 5,
                    'format': 'best[height<=1080]/best',
                }

            # TikTok 特殊配置
            elif 'tiktok.com' in domain:
                return {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.tiktok.com/',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                    },
                    'sleep_interval': 1,
                    'max_sleep_interval': 3,
                    # TikTok 专用格式选择
                    'format': 'best[ext=mp4][height<=1080]/best[ext=webm][height<=1080]/best[height<=1080]/best/worst',
                    # TikTok 特殊选项
                    'extractor_args': {
                        'tiktok': {
                            'api': ['web', 'mobile'],  # 使用多种 API
                        }
                    },
                    # 增加重试和容错
                    'retries': 4,
                    'fragment_retries': 4,
                    'extractor_retries': 3,
                    'writesubtitles': False,  # TikTok 通常没有字幕
                    'writeautomaticsub': False,
                }

            # Bilibili 特殊配置
            elif 'bilibili.com' in domain:
                return {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.bilibili.com/',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Origin': 'https://www.bilibili.com',
                    },
                    'sleep_interval': 1,
                    'max_sleep_interval': 2,
                    # Bilibili 专用格式选择
                    'format': 'best[ext=mp4][height<=1080]/best[ext=flv][height<=1080]/best[height<=1080]/best/worst',
                    # Bilibili 特殊选项
                    'extractor_args': {
                        'bilibili': {
                            'api': ['web', 'app'],  # 使用多种 API
                        }
                    },
                    # 增加重试和容错
                    'retries': 4,
                    'fragment_retries': 4,
                    'extractor_retries': 3,
                    'writesubtitles': True,   # Bilibili 支持字幕
                    'writeautomaticsub': True,
                    'subtitleslangs': ['zh-CN', 'zh-TW', 'en'],  # 支持多语言字幕
                }

            # 默认配置
            else:
                return {
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    },
                    'sleep_interval': 1,
                    'max_sleep_interval': 2,
                }

        except Exception as e:
            logger.error(f"❌ 获取网站配置失败: {e}")
            return {}



    def _get_max_retries(self, options: Dict[str, Any] = None) -> int:
        """获取最大重试次数"""
        if options and 'max_retries' in options:
            return max(0, int(options['max_retries']))
        return 3  # 默认值

    def _get_ffmpeg_path(self) -> str:
        """获取FFmpeg路径 - 使用智能配置管理器"""
        try:
            from .ffmpeg_config import get_ffmpeg_path_for_ytdlp
            ffmpeg_path = get_ffmpeg_path_for_ytdlp()
            if ffmpeg_path:
                logger.debug(f"✅ 智能检测FFmpeg路径: {ffmpeg_path}")
                return ffmpeg_path
            else:
                logger.warning("⚠️ 智能检测未找到FFmpeg路径")
                return None

        except Exception as e:
            logger.debug(f"🔍 智能FFmpeg路径检测失败: {e}")
            # 备用方案：传统检测
            return self._get_ffmpeg_path_fallback()

    def _get_ffmpeg_path_fallback(self) -> str:
        """FFmpeg路径检测备用方案"""
        try:
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
            logger.debug(f"🔍 备用FFmpeg路径检测失败: {e}")
            return None

    def _get_site_name(self, url: str) -> str:
        """获取网站名称"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url.lower())
            domain = parsed.netloc

            site_names = {
                'twitter.com': 'Twitter/X',
                'x.com': 'Twitter/X',
                'instagram.com': 'Instagram',
                'tiktok.com': 'TikTok',
                'bilibili.com': 'Bilibili',
                'youtube.com': 'YouTube',
                'youtu.be': 'YouTube',
                'facebook.com': 'Facebook',
                'vimeo.com': 'Vimeo',
                'dailymotion.com': 'Dailymotion'
            }

            for site_domain, site_name in site_names.items():
                if site_domain in domain:
                    return site_name

            return domain

        except Exception:
            return "未知网站"

    def _get_cookies_for_site(self, url: str) -> Optional[str]:
        """获取网站对应的 Cookies 文件"""
        try:
            # 尝试导入 cookies 管理器
            from modules.cookies.manager import CookiesManager
            cookies_manager = CookiesManager()
            return cookies_manager.get_cookies_for_ytdlp(url)
        except Exception as e:
            logger.debug(f"🔍 获取Cookies失败: {e}")
            return None

    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置 - 增强版，支持代理健康检查"""
        try:
            # 首先尝试从数据库获取代理配置
            from core.database import get_database
            db = get_database()
            proxy_config = db.get_proxy_config()

            if proxy_config and proxy_config.get('enabled'):
                # 使用统一的代理转换工具
                from core.proxy_converter import ProxyConverter
                proxy_url = ProxyConverter.build_proxy_url(proxy_config)

                # 测试代理连接
                test_result = ProxyConverter.test_proxy_connection(proxy_config, timeout=3)
                if test_result['success']:
                    logger.info(f"✅ 使用数据库代理配置: {proxy_config.get('proxy_type')}://{proxy_config.get('host')}:{proxy_config.get('port')}")
                    return proxy_url
                else:
                    logger.warning(f"⚠️ 代理连接失败，跳过代理: {proxy_config.get('host')}:{proxy_config.get('port')} - {test_result['message']}")
                    return None

            # 其次尝试从配置文件获取
            from core.config import get_config
            config = get_config()
            proxy_config = config.get('proxy', {})

            if proxy_config.get('enabled', False):
                proxy_type = proxy_config.get('type', 'http')
                proxy_host = proxy_config.get('host', '')
                proxy_port = proxy_config.get('port', '')

                if proxy_host and proxy_port:
                    proxy_url = f"{proxy_type}://{proxy_host}:{proxy_port}"
                    if self._test_proxy_connection(proxy_url):
                        logger.info(f"✅ 使用配置文件代理: {proxy_url}")
                        return proxy_url
                    else:
                        logger.warning(f"⚠️ 配置文件代理连接失败，跳过代理: {proxy_host}:{proxy_port}")

            return None
        except Exception as e:
            logger.debug(f"🔍 获取代理配置失败: {e}")
            return None



    def _save_to_database(self, download_id: str, url: str):
        """保存到数据库"""
        try:
            from core.database import get_database
            db = get_database()
            db.save_download_record(download_id, url)
        except Exception as e:
            logger.warning(f"⚠️ 保存到数据库失败: {e}")

    def _update_database_status(self, download_id: str, status: str, **kwargs):
        """更新数据库状态"""
        try:
            from core.database import get_database
            db = get_database()
            db.update_download_status(download_id, status, **kwargs)
        except Exception as e:
            logger.warning(f"⚠️ 更新数据库状态失败: {e}")

    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        """发送事件"""
        try:
            from core.events import emit, Events
            event = getattr(Events, event_name, None)
            if event:
                emit(event, data)
        except Exception as e:
            logger.debug(f"🔍 发送事件失败: {e}")

    def _update_download_status(self, download_id: str, status: str, progress: int = None, **kwargs):
        """更新下载状态"""
        try:
            with self.lock:
                if download_id in self.downloads:
                    self.downloads[download_id]['status'] = status
                    if progress is not None:
                        self.downloads[download_id]['progress'] = progress
                    for key, value in kwargs.items():
                        self.downloads[download_id][key] = value

            # 更新数据库
            self._update_database_status(download_id, status, **kwargs)

            # 发送状态变更事件
            if status == 'completed':
                # 发送下载完成事件
                with self.lock:
                    download_info = self.downloads.get(download_id, {})

                self._emit_event('DOWNLOAD_COMPLETED', {
                    'download_id': download_id,
                    'file_path': kwargs.get('file_path'),
                    'title': download_info.get('title', 'Unknown'),
                    'file_size': kwargs.get('file_size')
                })
                logger.info(f"📡 发送下载完成事件: {download_id}")
            elif status in ['downloading', 'retrying']:
                # 发送进度事件
                self._emit_event('DOWNLOAD_PROGRESS', {
                    'download_id': download_id,
                    'status': status,
                    'progress': progress or 0
                })

        except Exception as e:
            logger.error(f"❌ 更新下载状态失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)
            logger.info("✅ 核心下载管理器清理完成")
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")


# 全局实例
_core_manager = None


def get_core_download_manager() -> CoreDownloadManager:
    """获取核心下载管理器实例"""
    global _core_manager
    if _core_manager is None:
        _core_manager = CoreDownloadManager()
    return _core_manager
