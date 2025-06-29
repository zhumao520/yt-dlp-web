# -*- coding: utf-8 -*-
"""
PyTubeFix下载器 - 基于PyTubeFix的YouTube下载引擎
"""

import logging
import asyncio
import threading
import time
import os
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class PyTubeFixDownloader:
    """PyTubeFix下载器 - 优化版，支持YouTube对象缓存"""

    def __init__(self, proxy: Optional[str] = None):
        # 使用统一的代理转换器
        from core.proxy_converter import ProxyConverter
        if proxy:
            # 如果传入了具体的代理URL，直接使用
            self.proxy = proxy
        else:
            # 从数据库获取代理配置并转换为PyTubeFix格式
            self.proxy = ProxyConverter.get_pytubefix_proxy("PyTubeFix")

        self.name = "PyTubeFix"
        self.version = self._get_version()

        # 使用统一的PO Token管理器
        from core.po_token_manager import get_po_token_manager
        self.po_token_manager = get_po_token_manager()

        # YouTube对象缓存 - 避免重复创建
        self._youtube_cache = {}  # URL -> (YouTube对象, 创建时间)
        self._cache_timeout = 300  # 缓存5分钟

        # 进度回调函数
        self._progress_callback = None
        self._download_id = None

    def _get_version(self) -> str:
        """获取PyTubeFix版本"""
        try:
            import pytubefix
            return getattr(pytubefix, '__version__', 'unknown')
        except ImportError:
            return 'not_installed'

    def _get_or_create_youtube(self, url: str, force_refresh: bool = False) -> Optional[object]:
        """获取或创建YouTube对象，支持缓存"""
        try:
            import time
            from pytubefix import YouTube

            current_time = time.time()

            # 检查缓存
            if not force_refresh and url in self._youtube_cache:
                yt_obj, created_time = self._youtube_cache[url]

                # 检查缓存是否过期
                if current_time - created_time < self._cache_timeout:
                    logger.debug(f"🔄 使用缓存的YouTube对象: {url[:50]}...")
                    return yt_obj
                else:
                    logger.debug(f"⏰ YouTube对象缓存已过期，重新创建")
                    del self._youtube_cache[url]

            # 创建新的YouTube对象
            logger.info(f"🆕 创建新的YouTube对象: {url[:50]}...")

            # 构建配置参数
            yt_kwargs = {}

            # 代理配置
            if self.proxy:
                proxy_config = self._configure_proxy_for_pytubefix(self.proxy)
                if proxy_config:
                    yt_kwargs.update(proxy_config)
                    logger.debug(f"✅ 使用代理: {self.proxy}")

            # 应用PO Token配置
            yt_kwargs = self.po_token_manager.apply_to_pytubefix_kwargs(yt_kwargs, "PyTubeFix-Cached")

            # 标准认证模式
            yt_kwargs.update({
                'use_oauth': False,
                'allow_oauth_cache': False,
            })

            # 智能客户端选择
            import os
            is_container = (
                os.environ.get('CONTAINER_ENV') == '1' or
                os.environ.get('DOCKER_CONTAINER') == '1' or
                os.environ.get('VPS_ENV') == '1'
            )

            client_type, client_reason = self._select_optimal_client(is_container)
            logger.debug(f"🎯 选择客户端: {client_type} - {client_reason}")

            # 创建YouTube对象
            yt = YouTube(url, client_type, **yt_kwargs)

            # 缓存对象
            self._youtube_cache[url] = (yt, current_time)
            logger.info(f"✅ YouTube对象创建并缓存成功")

            return yt

        except Exception as e:
            logger.error(f"❌ 创建YouTube对象失败: {e}")
            return None

    def _clear_cache(self):
        """清理缓存"""
        self._youtube_cache.clear()
        logger.debug("🧹 YouTube对象缓存已清理")

    def _get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        import time
        current_time = time.time()

        cache_info = {
            'total_cached': len(self._youtube_cache),
            'cache_timeout': self._cache_timeout,
            'cached_urls': []
        }

        for url, (yt_obj, created_time) in self._youtube_cache.items():
            age = current_time - created_time
            cache_info['cached_urls'].append({
                'url': url[:50] + '...' if len(url) > 50 else url,
                'age_seconds': int(age),
                'expired': age > self._cache_timeout
            })

        return cache_info



    def _check_nodejs_available(self) -> bool:
        """检查nodejs是否可用"""
        try:
            import subprocess
            result = subprocess.run(['node', '--version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.debug(f"✅ 检测到nodejs: {version}")
                return True
            else:
                logger.debug("❌ nodejs不可用")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.debug(f"❌ nodejs检测失败: {e}")
            return False

    def _select_optimal_client(self, is_container: bool) -> tuple[str, str]:
        """智能选择最优客户端"""
        try:
            # 使用统一的客户端选择逻辑
            use_web, reason = self.po_token_manager.should_use_web_client(is_container)

            if use_web:
                return 'WEB', reason
            else:
                return 'ANDROID', reason

        except Exception as e:
            logger.warning(f"⚠️ 客户端选择失败，使用默认: {e}")
            return 'ANDROID', '默认稳定模式'
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """从URL中提取视频ID"""
        try:
            parsed_url = urlparse(url)
            
            if 'youtube.com' in parsed_url.netloc:
                if '/watch' in parsed_url.path:
                    query_params = parse_qs(parsed_url.query)
                    return query_params.get('v', [None])[0]
                elif '/embed/' in parsed_url.path:
                    return parsed_url.path.split('/embed/')[-1].split('?')[0]
                elif '/v/' in parsed_url.path:
                    return parsed_url.path.split('/v/')[-1].split('?')[0]
            elif 'youtu.be' in parsed_url.netloc:
                return parsed_url.path.lstrip('/')
                
            return None
        except Exception as e:
            logger.error(f"❌ 提取视频ID失败: {e}")
            return None

    def _is_youtube_url(self, url: str) -> bool:
        """检查是否为YouTube URL"""
        try:
            parsed_url = urlparse(url.lower())

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

            is_youtube = parsed_url.netloc in youtube_domains

            if is_youtube:
                logger.debug(f"✅ PyTubeFix检测到YouTube URL: {parsed_url.netloc}")
            else:
                logger.debug(f"🌐 PyTubeFix检测到非YouTube URL: {parsed_url.netloc}")

            return is_youtube

        except Exception as e:
            logger.error(f"❌ PyTubeFix URL检测失败: {e}")
            # 如果检测失败，保守地假设不是YouTube
            return False
    
    async def extract_info(self, url: str, quality: str = "720") -> Optional[Dict[str, Any]]:
        """提取视频信息"""
        try:
            logger.info(f"🔧 PyTubeFix开始提取: {url}")

            # 首先检查是否为YouTube URL
            if not self._is_youtube_url(url):
                logger.warning(f"⚠️ PyTubeFix只支持YouTube，跳过: {url}")
                return {
                    'error': 'unsupported_site',
                    'message': 'PyTubeFix只支持YouTube网站'
                }

            # 检查PyTubeFix是否可用
            try:
                from pytubefix import YouTube
            except ImportError:
                logger.error("❌ PyTubeFix未安装")
                return {
                    'error': 'pytubefix_not_installed',
                    'message': 'PyTubeFix未安装，请先安装PyTubeFix'
                }

            # 提取视频ID
            video_id = self._extract_video_id(url)
            if not video_id:
                logger.error(f"❌ 无法提取视频ID: {url}")
                return {
                    'error': 'invalid_url',
                    'message': '无效的YouTube URL'
                }
            
            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._extract_sync, url, quality)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ PyTubeFix提取异常: {e}")
            return {
                'error': 'extraction_failed',
                'message': f'PyTubeFix提取失败: {str(e)}'
            }
    
    def _extract_sync(self, url: str, quality: str) -> Dict[str, Any]:
        """同步提取视频信息（优化版，使用缓存）"""
        try:
            # 使用缓存的YouTube对象
            yt = self._get_or_create_youtube(url)

            if not yt:
                return {
                    'error': 'creation_failed',
                    'message': 'PyTubeFix YouTube对象创建失败'
                }
            
            # 获取基本信息
            basic_info = {
                'title': yt.title,
                'duration': yt.length,
                'description': yt.description,
                'uploader': yt.author,
                'upload_date': yt.publish_date.strftime('%Y%m%d') if yt.publish_date else None,
                'view_count': yt.views,
                'thumbnail': yt.thumbnail_url,
                'video_id': yt.video_id,
                'extractor': 'pytubefix',
                'webpage_url': url
            }
            
            # 获取格式信息
            formats = self._extract_formats(yt)
            
            result = {
                **basic_info,
                'formats': formats,
                'format_count': len(formats)
            }
            
            logger.info(f"✅ PyTubeFix提取成功: {basic_info['title']} ({len(formats)}个格式)")
            return result
            
        except Exception as e:
            logger.error(f"❌ PyTubeFix同步提取失败: {e}")
            return {
                'error': 'sync_extraction_failed',
                'message': f'PyTubeFix同步提取失败: {str(e)}'
            }

    def _configure_proxy_for_pytubefix(self, proxy_url: str) -> Dict[str, Any]:
        """为PyTubeFix配置代理 - 使用统一的代理转换器"""
        try:
            if not proxy_url:
                return {}

            # 使用统一的代理转换器处理SOCKS5
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_pytubefix_socks5_config(proxy_url, "PyTubeFix")

        except Exception as e:
            logger.error(f"❌ PyTubeFix代理配置失败: {e}")
            return {}
    
    def _extract_formats(self, yt) -> List[Dict[str, Any]]:
        """提取格式信息"""
        formats = []
        
        try:
            # 获取所有流
            streams = yt.streams
            
            for stream in streams:
                try:
                    format_info = {
                        'format_id': f"pytubefix-{stream.itag}",
                        'url': stream.url,
                        'ext': stream.mime_type.split('/')[-1] if stream.mime_type else 'mp4',
                        'quality': stream.resolution or 'audio',
                        'qualityLabel': stream.resolution or 'audio only',
                        'height': int(stream.resolution.replace('p', '')) if stream.resolution else None,
                        'fps': getattr(stream, 'fps', None),  # 安全获取fps属性
                        'vcodec': getattr(stream, 'video_codec', None),  # 安全获取视频编码
                        'acodec': getattr(stream, 'audio_codec', None),  # 安全获取音频编码
                        'filesize': getattr(stream, 'filesize', None),  # 安全获取文件大小
                        'bitrate': getattr(stream, 'bitrate', None),  # 安全获取比特率
                        'mime_type': getattr(stream, 'mime_type', None),  # 安全获取MIME类型
                        'type': getattr(stream, 'type', 'unknown'),  # 安全获取类型
                        'progressive': getattr(stream, 'is_progressive', False),  # 安全获取progressive状态
                        'adaptive': getattr(stream, 'is_adaptive', False),  # 安全获取adaptive状态
                        'itag': getattr(stream, 'itag', None)  # 安全获取itag
                    }

                    formats.append(format_info)

                except Exception as stream_error:
                    # 单个流处理失败时，记录错误但继续处理其他流
                    logger.warning(f"⚠️ 跳过有问题的流 {getattr(stream, 'itag', 'unknown')}: {stream_error}")
                    continue
            
            # 按质量排序
            formats.sort(key=lambda x: (
                x.get('height', 0) if x.get('height') else 0,
                x.get('bitrate', 0) if x.get('bitrate') else 0
            ), reverse=True)
            
            logger.debug(f"📊 提取到 {len(formats)} 个格式")
            return formats
            
        except Exception as e:
            logger.error(f"❌ 格式提取失败: {e}")
            return []
    
    async def download(self, url: str, output_path: str, quality: str = "720") -> Dict[str, Any]:
        """下载视频"""
        try:
            logger.info(f"📥 PyTubeFix开始下载: {url}")

            # 首先检查是否为YouTube URL
            if not self._is_youtube_url(url):
                logger.warning(f"⚠️ PyTubeFix只支持YouTube，跳过下载: {url}")
                return {
                    'error': 'unsupported_site',
                    'message': 'PyTubeFix只支持YouTube网站'
                }

            # 先提取信息
            info = await self.extract_info(url, quality)
            if not info or info.get('error'):
                return info or {'error': 'extraction_failed', 'message': '信息提取失败'}
            
            # 在线程池中执行下载
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._download_sync, url, output_path, quality)
            
            return result

        except Exception as e:
            logger.error(f"❌ PyTubeFix下载异常: {e}")
            return {
                'error': 'download_failed',
                'message': f'PyTubeFix下载失败: {str(e)}'
            }

    async def download_with_cached_info(self, url: str, output_path: str, quality: str = "720", video_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """使用已缓存信息进行下载，避免重复提取"""
        try:
            logger.info(f"📥 PyTubeFix开始缓存下载: {url}")

            # 首先检查是否为YouTube URL
            if not self._is_youtube_url(url):
                logger.warning(f"⚠️ PyTubeFix只支持YouTube，跳过下载: {url}")
                return {
                    'error': 'unsupported_site',
                    'message': 'PyTubeFix只支持YouTube网站'
                }

            # 如果没有传入video_info，先提取信息
            if not video_info:
                logger.info("📋 未提供视频信息，先进行提取")
                info = await self.extract_info(url, quality)
                if not info or info.get('error'):
                    return info or {'error': 'extraction_failed', 'message': '信息提取失败'}
                video_info = info
            else:
                logger.info("✅ 使用已提供的视频信息，跳过重复提取")

            # 在线程池中执行下载（复用缓存的YouTube对象）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._download_sync, url, output_path, quality)

            # 合并视频信息到结果中
            if result.get('success') and video_info:
                result.update({
                    'video_info': video_info,
                    'cached_download': True
                })

            return result

        except Exception as e:
            logger.error(f"❌ PyTubeFix缓存下载异常: {e}")
            return {
                'error': 'cached_download_failed',
                'message': f'PyTubeFix缓存下载失败: {str(e)}'
            }
    
    def _download_sync(self, url: str, output_path: str, quality: str) -> Dict[str, Any]:
        """同步下载视频（优化版，复用缓存的YouTube对象）"""
        try:
            import os

            # 复用缓存的YouTube对象，避免重复创建
            yt = self._get_or_create_youtube(url)

            if not yt:
                return {
                    'error': 'youtube_object_failed',
                    'message': '无法获取YouTube对象'
                }

            logger.info(f"🔄 复用YouTube对象进行下载")
            
            # 智能流选择（优化版）
            stream = self._select_optimal_stream(yt, quality)

            if not stream:
                # 如果没有找到流，尝试降级策略
                logger.warning(f"⚠️ 未找到质量 {quality} 的流，尝试降级策略")
                stream = self._fallback_stream_selection(yt, quality)
            
            if not stream:
                return {
                    'error': 'no_stream_found',
                    'message': '未找到可用的视频流'
                }
            
            # 确保输出目录存在
            os.makedirs(output_path, exist_ok=True)

            # 检查是否需要合并Adaptive streams
            if hasattr(stream, '_needs_merge') and stream._needs_merge:
                # 下载Adaptive格式（需要合并）
                downloaded_file = self._download_adaptive_stream(yt, stream, output_path)
            else:
                # 下载Progressive格式（单一文件）- 带进度监控
                downloaded_file = self._download_with_progress(stream, output_path)

            if not downloaded_file:
                return {
                    'error': 'download_failed',
                    'message': '文件下载失败'
                }

            result = {
                'success': True,
                'title': yt.title,
                'filename': os.path.basename(downloaded_file),
                'file_path': downloaded_file,  # 修复：使用统一的字段名
                'filepath': downloaded_file,   # 保留向后兼容
                'file_size': os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0,  # 修复：使用统一的字段名
                'filesize': os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0,   # 保留向后兼容
                'quality': stream.resolution or 'audio',
                'format': stream.mime_type,
                'extractor': 'pytubefix'
            }
            
            logger.info(f"✅ PyTubeFix下载成功: {result['filename']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ PyTubeFix同步下载失败: {e}")
            return {
                'error': 'sync_download_failed',
                'message': f'PyTubeFix同步下载失败: {str(e)}'
            }
    
    def _select_optimal_stream(self, yt, quality: str):
        """智能流选择 - 支持4K和自动降级"""
        try:
            # 首先尝试获取指定质量的流（包括adaptive streams）
            stream = self._get_stream_by_quality(yt, quality)
            if stream:
                return stream

            # 如果没有找到，使用降级策略
            logger.warning(f"⚠️ 未找到质量 {quality} 的流，开始降级策略")
            return self._fallback_stream_selection(yt, quality)

        except Exception as e:
            logger.error(f"❌ 流选择失败: {e}")
            return None

    def _get_stream_by_quality(self, yt, quality: str):
        """根据质量获取最佳流"""
        try:
            # 定义质量到分辨率的映射
            quality_resolution_map = {
                '4k': '2160p',
                '2k': '1440p',
                'high': '1080p',
                'medium': '720p',
                'low': '480p'
            }

            # 获取目标分辨率
            target_res = quality_resolution_map.get(quality, quality)

            # 如果是数字格式，添加p
            if target_res.isdigit():
                target_res = f"{target_res}p"

            logger.info(f"🎯 寻找质量: {quality} -> {target_res}")

            # 特殊处理
            if quality == 'best':
                return yt.streams.get_highest_resolution()
            elif quality == 'worst':
                return yt.streams.get_lowest_resolution()
            elif quality == 'audio':
                return yt.streams.get_audio_only()

            # 对于高分辨率（1080p+），直接降级到Progressive格式以避免网络问题
            if target_res in ['2160p', '1440p', '1080p']:
                logger.info(f"🔄 高分辨率{target_res}降级到Progressive格式以提高稳定性")
                fallback_progressive = self._get_progressive_fallback(yt, target_res)
                if fallback_progressive:
                    logger.info(f"✅ 找到Progressive降级流: {fallback_progressive.resolution}")
                    return fallback_progressive

            # 优先尝试Progressive格式（预合并，更稳定）
            progressive_stream = yt.streams.filter(progressive=True, res=target_res).first()
            if progressive_stream:
                logger.info(f"✅ 找到Progressive流: {target_res}")
                return progressive_stream

            # 如果没有Progressive格式，尝试稍低分辨率的Progressive格式
            if target_res in ['720p', '480p', '360p']:
                fallback_progressive = self._get_progressive_fallback(yt, target_res)
                if fallback_progressive:
                    logger.info(f"✅ 找到Progressive降级流: {fallback_progressive.resolution}")
                    return fallback_progressive

            # 最后才考虑Adaptive格式（网络要求高，容易失败）
            adaptive_video = yt.streams.filter(adaptive=True, type='video', res=target_res).first()
            if adaptive_video:
                logger.warning(f"⚠️ 使用Adaptive视频流: {target_res}，网络要求较高")
                # 标记这是一个需要合并的流
                adaptive_video._needs_merge = True
                return adaptive_video

            # 尝试不指定分辨率的匹配
            if target_res.endswith('p'):
                fallback_stream = yt.streams.filter(res=target_res).first()
                if fallback_stream:
                    logger.info(f"✅ 找到备选流: {target_res}")
                    return fallback_stream

            return None

        except Exception as e:
            logger.error(f"❌ 获取质量流失败: {e}")
            return None

    def _get_progressive_fallback(self, yt, target_res: str):
        """获取Progressive格式的降级流（优化版，更多降级选项）"""
        try:
            # Progressive降级顺序（包含更多选项，优先稳定性）
            progressive_fallback = {
                '2160p': ['720p', '480p', '360p'],  # 4K直接降到720p
                '1440p': ['720p', '480p', '360p'],  # 2K直接降到720p
                '1080p': ['720p', '480p', '360p'],  # 1080p直接降到720p
                '720p': ['480p', '360p'],
                '480p': ['360p'],
                '360p': []
            }

            fallback_list = progressive_fallback.get(target_res, ['720p', '480p', '360p'])

            for fallback_res in fallback_list:
                progressive_stream = yt.streams.filter(progressive=True, res=fallback_res).first()
                if progressive_stream:
                    logger.info(f"✅ Progressive降级: {target_res} -> {fallback_res}")
                    return progressive_stream

            # 如果还是没有找到，尝试获取任何可用的Progressive流
            any_progressive = yt.streams.filter(progressive=True).order_by('resolution').desc().first()
            if any_progressive:
                logger.info(f"✅ 使用最高可用Progressive流: {any_progressive.resolution}")
                return any_progressive

            return None

        except Exception as e:
            logger.error(f"❌ Progressive降级失败: {e}")
            return None

    def _fallback_stream_selection(self, yt, original_quality: str):
        """降级流选择策略 - 支持4K降级"""
        try:
            # 根据原始质量确定降级顺序（优化：减少降级级别）
            if original_quality in ['4k', '2160p']:
                fallback_order = ['2160p', '1080p', '720p']  # 减少到3个级别
            elif original_quality in ['2k', '1440p']:
                fallback_order = ['1440p', '1080p', '720p']  # 减少到3个级别
            elif original_quality in ['high', '1080p']:
                fallback_order = ['1080p', '720p', '480p']   # 减少到3个级别
            elif original_quality in ['medium', '720p']:
                fallback_order = ['720p', '480p', '360p']    # 保持3个级别
            elif original_quality in ['low', '480p']:
                fallback_order = ['480p', '360p']            # 减少到2个级别
            else:
                # 默认降级顺序（减少级别）
                fallback_order = ['1080p', '720p', '480p']   # 减少到3个级别

            logger.info(f"🔄 开始降级策略，原始质量: {original_quality}")
            logger.info(f"🔄 降级顺序: {' -> '.join(fallback_order)}")

            for fallback_quality in fallback_order:
                # 尝试获取该质量的流
                stream = self._get_stream_by_quality(yt, fallback_quality)
                if stream:
                    logger.info(f"✅ 降级成功: {original_quality} -> {fallback_quality}")
                    return stream

            # 最后尝试获取任何可用的最高质量视频流
            stream = yt.streams.get_highest_resolution()
            if stream:
                logger.info(f"✅ 使用最高可用质量: {getattr(stream, 'resolution', 'unknown')}")
                return stream

            # 如果还是没有，尝试音频流
            stream = yt.streams.get_audio_only()
            if stream:
                logger.info("✅ 最终降级到音频流")
                return stream

            return None

        except Exception as e:
            logger.error(f"❌ 降级策略失败: {e}")
            return None

    def _download_adaptive_stream(self, yt, video_stream, output_path: str) -> str:
        """下载Adaptive格式并合并"""
        try:
            import tempfile
            import uuid
            import os
            from pathlib import Path

            logger.info(f"🔧 开始下载Adaptive格式: {video_stream.resolution}")

            # 获取最佳音频流
            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
            if not audio_stream:
                # 如果没有mp4音频，尝试其他格式
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()

            if not audio_stream:
                logger.error("❌ 未找到音频流")
                return None

            logger.info(f"🎵 选择音频流: {audio_stream.abr} {audio_stream.mime_type}")

            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix='pytubefix_')
            temp_video_path = None
            temp_audio_path = None

            try:
                # 下载视频流
                logger.info("📹 下载视频流...")
                temp_video_path = video_stream.download(output_path=temp_dir, filename_prefix='video_')

                # 下载音频流
                logger.info("🎵 下载音频流...")
                temp_audio_path = audio_stream.download(output_path=temp_dir, filename_prefix='audio_')

                # 生成输出文件名
                safe_title = self._sanitize_filename(yt.title)
                output_filename = f"{safe_title}.mp4"
                final_output_path = os.path.join(output_path, output_filename)

                # 使用FFmpeg合并
                logger.info("🔧 使用FFmpeg合并视频和音频...")
                success = self._merge_video_audio(temp_video_path, temp_audio_path, final_output_path)

                if success and os.path.exists(final_output_path):
                    logger.info(f"✅ Adaptive格式合并成功: {output_filename}")
                    return final_output_path
                else:
                    logger.error("❌ FFmpeg合并失败")
                    return None

            finally:
                # 增强的临时文件清理
                self._cleanup_temp_files(temp_dir, temp_video_path, temp_audio_path)

        except Exception as e:
            logger.error(f"❌ Adaptive下载失败: {e}")
            return None

    def _download_stream_with_retry(self, stream, output_dir: str, filename_prefix: str, max_retries: int = 3) -> Optional[str]:
        """带重试机制的流下载"""
        import time

        for attempt in range(max_retries):
            try:
                logger.info(f"🔄 尝试下载流 (第 {attempt + 1}/{max_retries} 次): {filename_prefix}")

                # 尝试下载
                result = stream.download(output_path=output_dir, filename_prefix=filename_prefix)

                if result:
                    logger.info(f"✅ 流下载成功: {filename_prefix}")
                    return result
                else:
                    logger.warning(f"⚠️ 流下载返回空结果: {filename_prefix}")

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"⚠️ 流下载失败 (第 {attempt + 1}/{max_retries} 次): {error_msg}")

                # 检查是否是网络相关错误
                if "Maximum reload attempts" in error_msg or "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 递增等待时间
                        logger.info(f"⏱️ 等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                        continue

                # 如果是最后一次尝试或非网络错误，直接抛出
                if attempt == max_retries - 1:
                    logger.error(f"❌ 流下载最终失败: {error_msg}")
                    raise e

        return None

    def _merge_video_audio(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """使用FFmpeg合并视频和音频"""
        try:
            from modules.downloader.ffmpeg_tools import FFmpegTools

            ffmpeg_tools = FFmpegTools()
            if not ffmpeg_tools.is_available():
                logger.error("❌ FFmpeg不可用，无法合并Adaptive格式")
                return False

            # 使用FFmpeg合并
            success = ffmpeg_tools.merge_video_audio(
                video_path=video_path,
                audio_path=audio_path,
                output_path=output_path
            )

            return success

        except Exception as e:
            logger.error(f"❌ FFmpeg合并异常: {e}")
            return False

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename.strip()

    def _cleanup_temp_files(self, temp_dir: str = None, *temp_files) -> None:
        """增强的临时文件清理，确保资源释放"""
        import shutil
        import time
        import os

        cleanup_errors = []

        # 清理临时文件
        for temp_file in temp_files:
            if temp_file and os.path.exists(temp_file):
                try:
                    # 尝试多次删除（Windows文件锁定问题）
                    for attempt in range(3):
                        try:
                            os.remove(temp_file)
                            logger.debug(f"✅ 清理临时文件: {temp_file}")
                            break
                        except PermissionError:
                            if attempt < 2:
                                time.sleep(0.1)  # 等待文件句柄释放
                                continue
                            raise
                except Exception as e:
                    cleanup_errors.append(f"文件 {temp_file}: {e}")
                    logger.warning(f"⚠️ 清理临时文件失败: {temp_file} - {e}")

        # 清理临时目录
        if temp_dir and os.path.exists(temp_dir):
            try:
                # 尝试删除目录中的所有文件
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except Exception as e:
                            cleanup_errors.append(f"目录文件 {file}: {e}")
                    for dir in dirs:
                        try:
                            os.rmdir(os.path.join(root, dir))
                        except Exception as e:
                            cleanup_errors.append(f"子目录 {dir}: {e}")

                # 删除主目录
                os.rmdir(temp_dir)
                logger.debug(f"✅ 清理临时目录: {temp_dir}")

            except Exception as e:
                cleanup_errors.append(f"目录 {temp_dir}: {e}")
                logger.warning(f"⚠️ 清理临时目录失败: {temp_dir} - {e}")

                # 如果常规删除失败，尝试强制删除（仅限Windows）
                if os.name == 'nt':
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        logger.info(f"🔧 强制清理临时目录: {temp_dir}")
                    except Exception as e2:
                        cleanup_errors.append(f"强制删除 {temp_dir}: {e2}")

        # 记录清理结果
        if cleanup_errors:
            logger.warning(f"⚠️ 部分临时文件清理失败: {'; '.join(cleanup_errors)}")
        else:
            logger.debug("✅ 所有临时文件清理完成")

    def set_progress_callback(self, callback, download_id: str = None):
        """设置进度回调函数"""
        self._progress_callback = callback
        self._download_id = download_id
        logger.debug(f"✅ PyTubeFix设置进度回调: {download_id}")

    def _download_with_progress(self, stream, output_path: str) -> str:
        """带进度监控的下载方法"""
        try:

            # 获取文件大小
            file_size = getattr(stream, 'filesize', 0)
            if file_size == 0:
                # 如果无法获取文件大小，直接下载
                logger.debug("⚠️ 无法获取文件大小，使用普通下载")
                return stream.download(output_path=output_path)

            # 启动进度监控线程
            progress_stop_event = threading.Event()

            # 预测下载文件路径（PyTubeFix的默认命名规则）
            safe_title = self._sanitize_filename(stream.default_filename)
            predicted_file_path = os.path.join(output_path, safe_title)

            progress_thread = threading.Thread(
                target=self._monitor_download_progress,
                args=(predicted_file_path, file_size, progress_stop_event),
                daemon=True
            )
            progress_thread.start()

            try:
                # 执行下载
                downloaded_file = stream.download(output_path=output_path)

                # 停止进度监控
                progress_stop_event.set()

                # 等待监控线程结束（最多等待2秒）
                progress_thread.join(timeout=2.0)

                # 发送100%进度
                self._update_progress(file_size, file_size)

                return downloaded_file

            except Exception as e:
                # 确保停止进度监控
                progress_stop_event.set()
                # 不等待线程结束，让它自然退出
                raise e

        except Exception as e:
            logger.error(f"❌ PyTubeFix进度下载失败: {e}")
            # 降级到普通下载
            return stream.download(output_path=output_path)

    def _monitor_download_progress(self, file_path: str, total_size: int, stop_event: threading.Event):
        """监控下载进度"""
        try:
            last_size = 0
            file_found = False
            wait_count = 0
            max_wait = 20  # 最多等待10秒（20 * 0.5秒）

            while not stop_event.is_set():
                try:
                    if os.path.exists(file_path):
                        file_found = True
                        current_size = os.path.getsize(file_path)
                        if current_size != last_size:
                            self._update_progress(current_size, total_size)
                            last_size = current_size
                    else:
                        # 文件还不存在，可能下载还没开始
                        if not file_found:
                            wait_count += 1
                            if wait_count > max_wait:
                                logger.debug("⚠️ 等待下载文件创建超时，停止监控")
                                break
                        else:
                            # 文件曾经存在但现在不存在了，可能被移动或重命名
                            logger.debug("⚠️ 下载文件消失，可能已完成并被重命名")
                            break

                    # 每0.5秒检查一次
                    time.sleep(0.5)

                except Exception as e:
                    logger.debug(f"⚠️ 进度监控异常: {e}")
                    break

        except Exception as e:
            logger.debug(f"⚠️ 进度监控线程异常: {e}")

    def _update_progress(self, current: int, total: int):
        """更新下载进度"""
        if self._progress_callback:
            try:
                # 使用统一的进度处理工具
                from core.file_utils import ProgressUtils

                # 格式化进度数据
                progress_data = ProgressUtils.format_progress_data(
                    max(0, current), max(0, total), 'downloading'
                )

                # 安全的进度回调
                ProgressUtils.safe_progress_callback(self._progress_callback, progress_data)

                progress = progress_data['progress_percent']
                logger.debug(f"📊 PyTubeFix进度: {progress}% ({current}/{total})")
            except Exception as e:
                logger.debug(f"⚠️ PyTubeFix进度回调失败: {e}")

    def get_info(self) -> Dict[str, Any]:
        """获取下载器信息（包含缓存状态）"""
        status_info = self.po_token_manager.get_status_info()
        cache_info = self._get_cache_info()

        return {
            'name': self.name,
            'version': self.version,
            'proxy': self.proxy,
            'po_token_available': status_info['po_token_available'],
            'visitor_data_available': status_info['visitor_data_available'],
            'oauth2_available': status_info['oauth2_available'],
            'available': self.version != 'not_installed',
            'supports_youtube': True,
            'supports_other_sites': False,
            'technical_route': 'web_parsing',
            'supported_qualities': ['4k', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p', 'audio', 'best', 'worst'],
            'cache_enabled': True,
            'cache_info': cache_info,
            'optimizations': ['youtube_object_caching', 'duplicate_extraction_prevention', '4k_adaptive_support']
        }
