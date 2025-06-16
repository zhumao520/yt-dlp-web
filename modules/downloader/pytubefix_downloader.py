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
        self.proxy = proxy
        self.name = "PyTubeFix"
        self.version = self._get_version()
        
    def _get_version(self) -> str:
        """获取PyTubeFix版本"""
        try:
            import pytubefix
            return getattr(pytubefix, '__version__', 'unknown')
        except ImportError:
            return 'not_installed'
    
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
            yt_kwargs = {}
            if self.proxy:
                # PyTubeFix支持代理配置
                yt_kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
            
            yt = YouTube(url, **yt_kwargs)
            
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
                format_info = {
                    'format_id': f"pytubefix-{stream.itag}",
                    'url': stream.url,
                    'ext': stream.mime_type.split('/')[-1] if stream.mime_type else 'mp4',
                    'quality': stream.resolution or 'audio',
                    'qualityLabel': stream.resolution or 'audio only',
                    'height': int(stream.resolution.replace('p', '')) if stream.resolution else None,
                    'fps': stream.fps,
                    'vcodec': stream.video_codec,
                    'acodec': stream.audio_codec,
                    'filesize': stream.filesize,
                    'bitrate': stream.bitrate,
                    'mime_type': stream.mime_type,
                    'type': stream.type,
                    'progressive': stream.is_progressive,
                    'adaptive': stream.is_adaptive,
                    'itag': stream.itag
                }
                
                formats.append(format_info)
            
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
            
            # 创建YouTube对象
            yt_kwargs = {}
            if self.proxy:
                yt_kwargs['proxies'] = {'http': self.proxy, 'https': self.proxy}
            
            yt = YouTube(url, **yt_kwargs)
            
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
                'filepath': downloaded_file,
                'filesize': os.path.getsize(downloaded_file) if os.path.exists(downloaded_file) else 0,
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
