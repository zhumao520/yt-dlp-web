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
        self.proxy = self._convert_proxy_format(proxy)
        self.name = "PyTubeFix"
        self.version = self._get_version()
        
    def _convert_proxy_format(self, proxy: Optional[str]) -> Optional[str]:
        """转换代理格式，PyTubeFix只支持HTTP代理"""
        if not proxy:
            return None

        try:
            # 如果是SOCKS5代理，尝试转换为HTTP代理
            if proxy.startswith('socks5://'):
                # 提取主机和端口
                import re
                match = re.match(r'socks5://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)', proxy)
                if match:
                    username, password, host, port = match.groups()

                    # 尝试多种HTTP代理端口策略
                    http_ports_to_try = [
                        '1190',  # 用户提到的HTTP代理端口
                        str(int(port) + 4),  # SOCKS5端口+4的常见映射
                        '8080',  # 常见HTTP代理端口
                        '3128',  # 另一个常见HTTP代理端口
                    ]

                    logger.info(f"🔄 PyTubeFix尝试转换SOCKS5代理为HTTP代理")

                    # 首先尝试用户配置的HTTP代理端口
                    for http_port in http_ports_to_try:
                        try:
                            if username and password:
                                http_proxy = f"http://{username}:{password}@{host}:{http_port}"
                            else:
                                http_proxy = f"http://{host}:{http_port}"

                            logger.info(f"🔧 PyTubeFix尝试HTTP代理: {host}:{http_port}")
                            return http_proxy
                        except:
                            continue

                    # 如果都失败，尝试无代理模式
                    logger.warning(f"⚠️ PyTubeFix无法找到可用的HTTP代理，尝试直连")
                    return None

            # 如果是HTTP代理，直接使用
            elif proxy.startswith('http://') or proxy.startswith('https://'):
                logger.info(f"✅ PyTubeFix使用HTTP代理: {proxy}")
                return proxy

            # 其他格式，尝试添加http://前缀
            else:
                http_proxy = f"http://{proxy}"
                logger.info(f"✅ PyTubeFix使用HTTP代理: {http_proxy}")
                return http_proxy

        except Exception as e:
            logger.error(f"❌ 代理格式转换失败: {e}")
            return None

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
    
    async def extract_info(self, url: str, quality: str = "720") -> Optional[Dict[str, Any]]:
        """提取视频信息"""
        try:
            logger.info(f"🔧 PyTubeFix开始提取: {url}")
            
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
        """同步提取视频信息"""
        try:
            from pytubefix import YouTube
            
            # 创建YouTube对象，配置代理
            # PyTubeFix正确的反机器人配置
            yt_kwargs = {}

            # 代理配置
            if self.proxy:
                yt_kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
                logger.debug(f"✅ PyTubeFix使用代理: {self.proxy}")

            # 智能反机器人配置 - 使用PyTubeFix推荐的默认客户端
            yt_kwargs.update({
                # 不指定client，使用PyTubeFix默认的ANDROID_VR
                'use_oauth': False,            # 禁用OAuth（避免账号风险）
                'allow_oauth_cache': False,    # 禁用OAuth缓存
            })

            # PyTubeFix反机器人检测配置
            import os

            # 检查是否在容器环境中
            is_container = (
                os.environ.get('CONTAINER_ENV') == '1' or
                os.environ.get('DOCKER_CONTAINER') == '1' or
                os.environ.get('VPS_ENV') == '1'
            )

            logger.info(f"🔍 环境检测: 容器环境={is_container}")

            # 智能反机器人策略
            if is_container:
                # 容器环境：使用ANDROID客户端（最稳定，无需JavaScript）
                logger.info("🤖 容器环境使用PyTubeFix ANDROID客户端（无JS依赖）")
                yt = YouTube(url, 'ANDROID', **yt_kwargs)
            else:
                # 本地环境：检查nodejs并选择策略
                nodejs_available = self._check_nodejs_available()
                logger.info(f"🔍 本地环境nodejs可用: {nodejs_available}")

                if nodejs_available:
                    # 策略1: 使用WEB客户端 + 自动PO Token生成
                    logger.info("🚀 本地环境使用PyTubeFix WEB客户端 + 自动PO Token生成")
                    yt = YouTube(url, 'WEB', **yt_kwargs)
                else:
                    # 策略2: 使用ANDROID客户端（最稳定）
                    logger.info("🤖 本地环境使用PyTubeFix ANDROID客户端")
                    yt = YouTube(url, 'ANDROID', **yt_kwargs)
            
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

            # 代理配置
            if self.proxy:
                yt_kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
                logger.debug(f"✅ PyTubeFix下载使用代理: {self.proxy}")

            # 智能反机器人配置
            yt_kwargs.update({
                'use_oauth': False,            # 禁用OAuth（避免账号风险）
                'allow_oauth_cache': False,    # 禁用OAuth缓存
            })

            # PyTubeFix反机器人检测配置（与提取方法保持一致）
            import os
            is_container = (
                os.environ.get('CONTAINER_ENV') == '1' or
                os.environ.get('DOCKER_CONTAINER') == '1' or
                os.environ.get('VPS_ENV') == '1'
            )

            logger.info(f"🔍 下载环境检测: 容器环境={is_container}")

            # 智能反机器人策略
            if is_container:
                # 容器环境：使用ANDROID客户端（最稳定，无需JavaScript）
                logger.info("🤖 容器环境下载使用PyTubeFix ANDROID客户端（无JS依赖）")
                yt = YouTube(url, 'ANDROID', **yt_kwargs)
            else:
                # 本地环境：检查nodejs并选择策略
                nodejs_available = self._check_nodejs_available()
                logger.info(f"🔍 本地环境nodejs可用: {nodejs_available}")

                if nodejs_available:
                    # 策略1: 使用WEB客户端 + 自动PO Token生成
                    logger.info("🚀 本地环境下载使用PyTubeFix WEB客户端 + 自动PO Token生成")
                    yt = YouTube(url, 'WEB', **yt_kwargs)
                else:
                    # 策略2: 使用WEB客户端（避免交互式PO Token输入）
                    logger.info("🤖 本地环境下载使用PyTubeFix WEB客户端（无交互模式）")
                    yt = YouTube(url, 'WEB', **yt_kwargs)
            
            # 选择最佳流
            if quality == "best":
                stream = yt.streams.get_highest_resolution()
            elif quality == "worst":
                stream = yt.streams.get_lowest_resolution()
            else:
                # 尝试获取指定质量
                stream = yt.streams.filter(res=f"{quality}p").first()
                if not stream:
                    # 如果没有指定质量，获取最高质量
                    stream = yt.streams.get_highest_resolution()
            
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
    
    def get_info(self) -> Dict[str, Any]:
        """获取下载器信息"""
        return {
            'name': self.name,
            'version': self.version,
            'proxy': self.proxy,
            'available': self.version != 'not_installed',
            'supports_youtube': True,
            'supports_other_sites': False,
            'technical_route': 'web_parsing'
        }
