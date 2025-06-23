# -*- coding: utf-8 -*-
"""
PyTubeFix下载器 - 基于PyTubeFix的YouTube下载引擎
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class PyTubeFixDownloader:
    """PyTubeFix下载器"""
    
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

    def _get_version(self) -> str:
        """获取PyTubeFix版本"""
        try:
            import pytubefix
            return getattr(pytubefix, '__version__', 'unknown')
        except ImportError:
            return 'not_installed'



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

            # 本地环境检查nodejs
            nodejs_available = self._check_nodejs_available()
            if nodejs_available:
                return 'WEB', '本地环境+nodejs，支持PO Token'
            else:
                return 'ANDROID', '本地环境无nodejs，使用稳定模式'

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
        """同步提取视频信息（带超时机制）"""
        try:
            from pytubefix import YouTube
            import signal
            import threading

            # 创建YouTube对象，配置代理
            # PyTubeFix正确的反机器人配置
            yt_kwargs = {}

            # 代理配置 - 支持SOCKS5
            if self.proxy:
                proxy_config = self._configure_proxy_for_pytubefix(self.proxy)
                if proxy_config:
                    yt_kwargs.update(proxy_config)
                    logger.debug(f"✅ PyTubeFix使用代理: {self.proxy}")

            # 应用PO Token配置（快速降级）
            yt_kwargs = self.po_token_manager.apply_to_pytubefix_kwargs(yt_kwargs, "PyTubeFix-Extract")

            # 标准认证模式
            yt_kwargs.update({
                'use_oauth': False,
                'allow_oauth_cache': False,
            })
            logger.info("🤖 使用标准认证模式")

            # PyTubeFix反机器人检测配置
            import os

            # 检查是否在容器环境中
            is_container = (
                os.environ.get('CONTAINER_ENV') == '1' or
                os.environ.get('DOCKER_CONTAINER') == '1' or
                os.environ.get('VPS_ENV') == '1'
            )

            logger.info(f"🔍 环境检测: 容器环境={is_container}")

            # 智能客户端选择策略（优化版）
            client_type, client_reason = self._select_optimal_client(is_container)
            logger.info(f"🎯 选择客户端: {client_type} - {client_reason}")

            # 使用超时机制创建YouTube对象
            result = {'yt': None, 'error': None}

            def create_youtube():
                try:
                    result['yt'] = YouTube(url, client_type, **yt_kwargs)
                except Exception as e:
                    result['error'] = str(e)

            # 启动创建线程
            thread = threading.Thread(target=create_youtube)
            thread.daemon = True
            thread.start()

            # 等待最多20秒
            thread.join(timeout=20)

            if thread.is_alive():
                logger.warning(f"⏰ PyTubeFix YouTube对象创建超时（20秒），快速降级")
                return {
                    'error': 'creation_timeout',
                    'message': 'PyTubeFix YouTube对象创建超时，建议检查网络或PO Token配置'
                }

            if result['error']:
                logger.error(f"❌ PyTubeFix YouTube对象创建失败: {result['error']}")
                return {
                    'error': 'creation_failed',
                    'message': f'PyTubeFix YouTube对象创建失败: {result["error"]}'
                }

            yt = result['yt']
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
        """为PyTubeFix配置代理，支持SOCKS5"""
        try:
            if not proxy_url:
                return {}

            # 解析代理URL
            if '://' in proxy_url:
                protocol, rest = proxy_url.split('://', 1)
                protocol = protocol.lower()

                # 解析认证信息和地址
                if '@' in rest:
                    auth_part, addr_part = rest.rsplit('@', 1)
                    if ':' in auth_part:
                        username, password = auth_part.split(':', 1)
                    else:
                        username, password = auth_part, ''
                else:
                    username, password = '', ''
                    addr_part = rest

                # 解析主机和端口
                if ':' in addr_part:
                    host, port = addr_part.rsplit(':', 1)
                    port = int(port)
                else:
                    host = addr_part
                    port = 1080 if protocol == 'socks5' else 8080

                # 根据协议类型配置
                if protocol in ['http', 'https']:
                    # HTTP代理直接使用
                    return {'proxies': {'http': proxy_url, 'https': proxy_url}}

                elif protocol == 'socks5':
                    # SOCKS5代理需要特殊处理
                    try:
                        # 尝试使用requests[socks]支持
                        import socks
                        import socket

                        # 配置全局SOCKS5代理
                        socks.set_default_proxy(socks.SOCKS5, host, port, username=username or None, password=password or None)
                        socket.socket = socks.socksocket

                        logger.info(f"✅ PyTubeFix配置SOCKS5代理: {host}:{port}")
                        return {'_socks5_configured': True}

                    except ImportError:
                        logger.warning("⚠️ 未安装PySocks，尝试转换SOCKS5为HTTP代理")
                        # 回退到转换逻辑
                        from core.proxy_converter import ProxyConverter
                        http_proxy = ProxyConverter.get_pytubefix_proxy("PyTubeFix-SOCKS5")
                        if http_proxy:
                            return {'proxies': {'http': http_proxy, 'https': http_proxy}}
                        else:
                            logger.warning("⚠️ SOCKS5转HTTP失败，PyTubeFix将直连")
                            return {}

                    except Exception as e:
                        logger.error(f"❌ SOCKS5代理配置失败: {e}")
                        return {}

            # 如果不是标准格式，尝试作为HTTP代理使用
            return {'proxies': {'http': proxy_url, 'https': proxy_url}}

        except Exception as e:
            logger.error(f"❌ 代理配置解析失败: {e}")
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
    
    def _download_sync(self, url: str, output_path: str, quality: str) -> Dict[str, Any]:
        """同步下载视频"""
        try:
            from pytubefix import YouTube
            import os
            
            # 创建YouTube对象 - 使用正确的PyTubeFix配置
            yt_kwargs = {}

            # 代理配置 - 支持SOCKS5
            if self.proxy:
                proxy_config = self._configure_proxy_for_pytubefix(self.proxy)
                if proxy_config:
                    yt_kwargs.update(proxy_config)
                    logger.debug(f"✅ PyTubeFix下载使用代理: {self.proxy}")

            # 应用PO Token配置（与提取方法保持一致）
            yt_kwargs = self.po_token_manager.apply_to_pytubefix_kwargs(yt_kwargs, "PyTubeFix-Download")

            # 标准认证模式
            yt_kwargs.update({
                'use_oauth': False,
                'allow_oauth_cache': False,
            })
            logger.info("🤖 下载使用标准认证模式")

            # PyTubeFix反机器人检测配置（与提取方法保持一致）
            import os
            is_container = (
                os.environ.get('CONTAINER_ENV') == '1' or
                os.environ.get('DOCKER_CONTAINER') == '1' or
                os.environ.get('VPS_ENV') == '1'
            )

            logger.info(f"🔍 下载环境检测: 容器环境={is_container}")

            # 智能客户端选择策略（与提取方法保持一致）
            client_type, client_reason = self._select_optimal_client(is_container)
            logger.info(f"🎯 下载选择客户端: {client_type} - {client_reason}")

            yt = YouTube(url, client_type, **yt_kwargs)
            
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
            
            # 下载文件
            downloaded_file = stream.download(output_path=output_path)
            
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
        """智能流选择"""
        try:
            # 质量映射表
            quality_map = {
                'best': lambda: yt.streams.get_highest_resolution(),
                'worst': lambda: yt.streams.get_lowest_resolution(),
                '4k': lambda: yt.streams.filter(res='2160p').first(),
                '1440p': lambda: yt.streams.filter(res='1440p').first(),
                '1080p': lambda: yt.streams.filter(res='1080p').first(),
                '720p': lambda: yt.streams.filter(res='720p').first(),
                '480p': lambda: yt.streams.filter(res='480p').first(),
                '360p': lambda: yt.streams.filter(res='360p').first(),
                '240p': lambda: yt.streams.filter(res='240p').first(),
                '144p': lambda: yt.streams.filter(res='144p').first(),
                'audio': lambda: yt.streams.get_audio_only(),
            }

            # 尝试直接匹配
            if quality in quality_map:
                stream = quality_map[quality]()
                if stream:
                    logger.info(f"✅ 找到匹配流: {quality} - {getattr(stream, 'resolution', 'audio')}")
                    return stream

            # 尝试数字+p格式 (如 "1080p", "720p")
            if quality.endswith('p') and quality[:-1].isdigit():
                stream = yt.streams.filter(res=quality).first()
                if stream:
                    logger.info(f"✅ 找到分辨率流: {quality}")
                    return stream

            # 尝试纯数字格式 (如 "1080", "720")
            if quality.isdigit():
                stream = yt.streams.filter(res=f"{quality}p").first()
                if stream:
                    logger.info(f"✅ 找到数字分辨率流: {quality}p")
                    return stream

            return None

        except Exception as e:
            logger.error(f"❌ 流选择失败: {e}")
            return None

    def _fallback_stream_selection(self, yt, original_quality: str):
        """降级流选择策略"""
        try:
            # 降级策略：从高到低尝试
            fallback_order = ['1080p', '720p', '480p', '360p', '240p', '144p']

            logger.info(f"🔄 开始降级策略，原始质量: {original_quality}")

            for fallback_quality in fallback_order:
                stream = yt.streams.filter(res=fallback_quality).first()
                if stream:
                    logger.info(f"✅ 降级成功: {fallback_quality}")
                    return stream

            # 最后尝试获取任何可用的视频流
            stream = yt.streams.get_highest_resolution()
            if stream:
                logger.info(f"✅ 使用最高可用质量: {getattr(stream, 'resolution', 'unknown')}")
                return stream

            # 如果还是没有，尝试音频流
            stream = yt.streams.get_audio_only()
            if stream:
                logger.info("✅ 降级到音频流")
                return stream

            return None

        except Exception as e:
            logger.error(f"❌ 降级策略失败: {e}")
            return None

    def get_info(self) -> Dict[str, Any]:
        """获取下载器信息"""
        status_info = self.po_token_manager.get_status_info()

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
            'supported_qualities': ['4k', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p', 'audio', 'best', 'worst']
        }
