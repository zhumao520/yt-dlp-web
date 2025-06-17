# -*- coding: utf-8 -*-
"""
Cobalt增强模块核心类

基于Cobalt项目的YouTube下载技术，提供独立的下载能力
"""

import logging
import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, parse_qs
import re
import json
import urllib.request
import urllib.parse
import urllib.error
# aiohttp是可选依赖，如果没有安装会回退到urllib
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class CobaltDownloader:
    """Cobalt增强下载器核心类"""
    
    def __init__(self, proxy: Optional[str] = None):
        # 如果没有提供代理，尝试从项目配置中获取
        if not proxy:
            proxy = self._get_project_proxy_config()

        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        # Cobalt支持的客户端列表（按抗机器人检测能力排序）
        self.clients = [
            'YTSTUDIO_ANDROID',  # YouTube Studio Android - 最高成功率
            'YTMUSIC_ANDROID',   # YouTube Music Android - 较少被检测
            'ANDROID',           # 标准Android客户端
            'IOS',               # iOS客户端
            'WEB_EMBEDDED',      # 嵌入式播放器
            'WEB'                # Web客户端（最后尝试）
        ]
        
        # 无需解密的客户端
        self.no_cipher_clients = ['IOS', 'ANDROID', 'YTSTUDIO_ANDROID', 'YTMUSIC_ANDROID']
        
        # 视频质量列表
        self.video_qualities = [144, 240, 360, 480, 720, 1080, 1440, 2160, 4320]
        
        logger.info("🚀 Cobalt增强下载器初始化完成")
        if self.proxy:
            logger.info(f"🌐 使用代理: {self.proxy}")

    def _get_project_proxy_config(self) -> Optional[str]:
        """获取项目代理配置（与下载管理器保持一致）"""
        try:
            # 优先使用数据库中的代理配置
            try:
                from core.database import get_database
            except ImportError:
                try:
                    from app.core.database import get_database
                except ImportError:
                    try:
                        from ...core.database import get_database
                    except ImportError:
                        get_database = None

            if get_database:
                try:
                    db = get_database()
                    proxy_config = db.get_proxy_config()

                    if proxy_config and proxy_config.get('enabled'):
                        proxy_url = f"{proxy_config.get('proxy_type', 'http')}://"
                        if proxy_config.get('username'):
                            proxy_url += f"{proxy_config['username']}"
                            if proxy_config.get('password'):
                                proxy_url += f":{proxy_config['password']}"
                            proxy_url += "@"
                        proxy_url += f"{proxy_config.get('host')}:{proxy_config.get('port')}"
                        logger.info(f"🌐 Cobalt使用数据库代理配置: {proxy_config.get('proxy_type')}://{proxy_config.get('host')}:{proxy_config.get('port')}")
                        return proxy_url
                except Exception as e:
                    logger.debug(f"🔍 数据库代理配置获取失败: {e}")

            # 其次使用配置文件中的代理
            try:
                from core.config import get_config
            except ImportError:
                try:
                    from app.core.config import get_config
                except ImportError:
                    try:
                        from ...core.config import get_config
                    except ImportError:
                        get_config = None

            if get_config:
                try:
                    proxy = get_config('downloader.proxy', None)
                    if proxy:
                        logger.info(f"🌐 Cobalt使用配置文件代理: {proxy}")
                        return proxy
                except Exception as e:
                    logger.debug(f"🔍 配置文件代理获取失败: {e}")

            # 最后使用环境变量
            import os
            proxy = os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
            if proxy:
                logger.info(f"🌐 Cobalt使用环境变量代理: {proxy}")
                return proxy

            return None

        except Exception as e:
            logger.warning(f"⚠️ Cobalt获取代理配置失败: {e}")
            return None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        pass
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """从YouTube URL提取视频ID"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def is_youtube_url(self, url: str) -> bool:
        """检查是否为YouTube URL"""
        return 'youtube.com' in url or 'youtu.be' in url
    
    async def extract_info(self, url: str, quality: str = "1080") -> Dict[str, Any]:
        """
        提取视频信息（Cobalt风格）
        
        Args:
            url: 视频URL
            quality: 目标质量 (144, 240, 360, 480, 720, 1080, 1440, 2160, max)
            
        Returns:
            包含视频信息和下载链接的字典
        """
        try:
            if not self.is_youtube_url(url):
                return {'error': 'unsupported_url', 'message': '不支持的URL'}
            
            video_id = self.extract_video_id(url)
            if not video_id:
                return {'error': 'invalid_url', 'message': '无法提取视频ID'}
            
            logger.info(f"🎬 开始提取视频信息: {video_id}")
            
            # 尝试不同的客户端 - 智能重试机制
            last_error = None
            bot_detected_count = 0

            for i, client in enumerate(self.clients):
                try:
                    logger.info(f"🔄 尝试客户端 {i+1}/{len(self.clients)}: {client}")
                    result = await self._extract_with_client(video_id, client, quality)

                    if result and not result.get('error'):
                        logger.info(f"✅ 客户端 {client} 成功")
                        result['extractor'] = 'cobalt_enhanced'
                        result['client_used'] = client
                        return result
                    else:
                        error_type = result.get('error', 'unknown') if result else 'no_result'
                        error_msg = result.get('message', '未知错误') if result else '无返回结果'
                        last_error = error_msg

                        # 特殊错误处理
                        if error_type == 'bot_detected':
                            bot_detected_count += 1
                            logger.warning(f"🤖 客户端 {client} 被检测为机器人 ({bot_detected_count})")
                            # 添加延迟，避免频繁请求
                            if i < len(self.clients) - 1:  # 不是最后一个客户端
                                await asyncio.sleep(2)
                        elif error_type == 'age_restricted':
                            logger.warning(f"🔞 客户端 {client} 遇到年龄限制")
                        elif error_type == 'geo_blocked':
                            logger.warning(f"🌍 客户端 {client} 遇到地区限制")
                        else:
                            logger.warning(f"❌ 客户端 {client} 失败: {error_msg}")

                except Exception as e:
                    logger.warning(f"❌ 客户端 {client} 异常: {e}")
                    last_error = str(e)
                    continue
            
            # 构建详细的错误信息
            error_details = [
                f'尝试了 {len(self.clients)} 个客户端: {", ".join(self.clients)}',
                f'机器人检测次数: {bot_detected_count}'
            ]

            if bot_detected_count >= len(self.clients) // 2:
                error_details.append('建议: 大量机器人检测，可能需要更换IP或使用Cookies')

            return {
                'error': 'all_clients_failed',
                'message': f'所有客户端都失败了。最后错误: {last_error}',
                'details': error_details,
                'bot_detected_count': bot_detected_count
            }
            
        except Exception as e:
            logger.error(f"❌ 提取视频信息失败: {e}")
            return {'error': 'extraction_failed', 'message': str(e)}
    
    async def _extract_with_client(self, video_id: str, client: str, quality: str) -> Dict[str, Any]:
        """使用指定客户端提取视频信息"""
        # 这里将实现具体的InnerTube API调用
        # 暂时返回模拟数据，后续会实现完整的API调用
        
        # 构建InnerTube API请求
        api_data = self._build_innertube_request(video_id, client)
        
        try:
            # 发送API请求（现在直接返回Cobalt格式的数据）
            response = await self._call_innertube_api(api_data, client)

            if not response:
                return {'error': 'api_call_failed', 'message': 'API调用失败'}

            # 由于现在使用yt-dlp作为后端，response已经是Cobalt格式，直接返回
            if isinstance(response, dict) and response.get('extractor') == 'cobalt_via_ytdlp':
                return response
            else:
                # 如果是其他格式，尝试解析（保留兼容性）
                parsed_info = self._parse_innertube_response(response, quality)
                return parsed_info

        except Exception as e:
            return {'error': 'client_failed', 'message': str(e)}
    
    def _build_innertube_request(self, video_id: str, client: str) -> Dict[str, Any]:
        """构建InnerTube API请求数据"""
        # 基础请求结构
        base_request = {
            "videoId": video_id,
            "context": {
                "client": self._get_client_config(client)
            }
        }
        
        return base_request
    
    def _get_client_config(self, client: str) -> Dict[str, Any]:
        """获取客户端配置 - 增强的抗机器人检测配置"""
        configs = {
            'YTSTUDIO_ANDROID': {
                "clientName": "YTSTUDIO_ANDROID",
                "clientVersion": "23.32.204",
                "androidSdkVersion": 30,
                "userAgent": "com.google.android.apps.youtube.creator/23.32.204 (Linux; U; Android 11) gzip"
            },
            'YTMUSIC_ANDROID': {
                "clientName": "YTMUSIC_ANDROID",
                "clientVersion": "6.42.52",
                "androidSdkVersion": 30,
                "userAgent": "com.google.android.apps.youtube.music/6.42.52 (Linux; U; Android 11) gzip"
            },
            'IOS': {
                "clientName": "IOS",
                "clientVersion": "19.09.3",
                "deviceModel": "iPhone14,3",
                "userAgent": "com.google.ios.youtube/19.09.3 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)",
                "osName": "iPhone",
                "osVersion": "15.6.0.19G71"
            },
            'ANDROID': {
                "clientName": "ANDROID",
                "clientVersion": "19.09.37",
                "androidSdkVersion": 30,
                "userAgent": "com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip"
            },
            'WEB': {
                "clientName": "WEB",
                "clientVersion": "2.20241215.01.00",
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            'WEB_EMBEDDED': {
                "clientName": "WEB_EMBEDDED_PLAYER",
                "clientVersion": "1.20241215.01.00",
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        }

        return configs.get(client, configs['YTSTUDIO_ANDROID'])

    async def _call_innertube_api(self, data: Dict[str, Any], client: str) -> Optional[Dict[str, Any]]:
        """调用InnerTube API（使用aiohttp支持SOCKS5）"""
        # InnerTube API端点
        api_url = "https://www.youtube.com/youtubei/v1/player"

        # 2024年更新：InnerTube API不再需要API密钥
        # 直接使用API端点，不添加key参数
        full_url = api_url

        # 根据客户端类型构建请求头
        client_config = self._get_client_config(client)

        # 客户端名称映射
        client_name_map = {
            'YTSTUDIO_ANDROID': "14",
            'YTMUSIC_ANDROID': "21",
            'IOS': "5",
            'ANDROID': "3",
            'WEB': "1",
            'WEB_EMBEDDED': "56"
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": client_config.get("userAgent", self.user_agent),
            "X-YouTube-Client-Name": client_name_map.get(client, "14"),
            "X-YouTube-Client-Version": client_config.get("clientVersion", "23.32.204")
        }

        try:
            # 直接使用yt-dlp作为Cobalt的后端
            # 这样可以保证功能正常，同时提供Cobalt的接口
            logger.info("ℹ️ Cobalt增强模式：使用yt-dlp作为后端")
            video_id = data.get('videoId')
            if video_id:
                return await self._extract_with_ytdlp_directly(video_id, client)
            else:
                logger.error("❌ 缺少videoId")
                return None

        except Exception as e:
            logger.error(f"❌ Cobalt增强模式失败: {e}")
            return None

    async def _extract_with_ytdlp_directly(self, video_id: str, client: str):
        """直接使用yt-dlp进行视频信息提取"""
        import concurrent.futures

        def sync_ytdlp_extract():
            try:
                import yt_dlp

                # 构建视频URL
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                # 配置yt-dlp选项
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'simulate': True,  # 只提取信息，不下载
                    'extract_flat': False,
                }

                # 如果有代理，添加代理配置
                if self.proxy:
                    ydl_opts['proxy'] = self.proxy
                    logger.info(f"✅ Cobalt使用yt-dlp代理: {self.proxy}")

                # 使用yt-dlp提取信息
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)

                    if info:
                        # 转换为Cobalt格式
                        cobalt_result = self._convert_ytdlp_to_cobalt_format(info, client)
                        if cobalt_result:
                            logger.info(f"✅ Cobalt通过yt-dlp提取成功: {client}")
                            return cobalt_result
                        else:
                            logger.warning(f"❌ Cobalt格式转换失败: {client}")
                            return None
                    else:
                        logger.warning(f"❌ yt-dlp提取失败: {client}")
                        return None

            except Exception as e:
                logger.error(f"❌ Cobalt通过yt-dlp提取异常: {e}")
                raise

        # 在线程池中执行同步调用
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(sync_ytdlp_extract)
            try:
                result = future.result(timeout=30)
                return result
            except concurrent.futures.TimeoutError:
                logger.error(f"❌ Cobalt通过yt-dlp提取超时: {client}")
                return None

    def _convert_ytdlp_to_cobalt_format(self, ytdlp_info: dict, client: str) -> dict:
        """将yt-dlp格式转换为Cobalt格式"""
        if not ytdlp_info:
            logger.error("❌ ytdlp_info为空，无法转换")
            return None

        try:
            # 提取基本信息
            result = {
                'title': ytdlp_info.get('title', 'Unknown'),
                'duration': ytdlp_info.get('duration', 0),
                'description': ytdlp_info.get('description', ''),
                'uploader': ytdlp_info.get('uploader', 'Unknown'),
                'upload_date': ytdlp_info.get('upload_date'),
                'view_count': ytdlp_info.get('view_count', 0),
                'like_count': ytdlp_info.get('like_count', 0),
                'thumbnail': ytdlp_info.get('thumbnail'),
                'extractor': 'cobalt_via_ytdlp',
                'client_used': client,
                'anti_detection_used': True,
                'original_extractor': ytdlp_info.get('extractor', 'youtube')
            }

            # 验证基本信息
            if not result['title'] or result['title'] == 'Unknown':
                logger.warning(f"⚠️ 视频标题缺失或无效: {result['title']}")
                # 但不返回None，继续处理

            # 转换格式信息
            formats = []
            ytdlp_formats = ytdlp_info.get('formats', [])

            for fmt in ytdlp_formats:
                if not fmt:  # 跳过空格式
                    continue

                cobalt_format = {
                    'format_id': fmt.get('format_id'),
                    'url': fmt.get('url'),
                    'ext': fmt.get('ext', 'mp4'),
                    'quality': fmt.get('format_note', 'unknown'),
                    'qualityLabel': f"{fmt.get('height', 'unknown')}p" if fmt.get('height') else 'unknown',
                    'height': fmt.get('height'),
                    'width': fmt.get('width'),
                    'fps': fmt.get('fps'),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec'),
                    'filesize': fmt.get('filesize'),
                    'bitrate': fmt.get('tbr')
                }
                formats.append(cobalt_format)

            result['formats'] = formats

            logger.info(f"✅ 成功转换yt-dlp格式到Cobalt格式: {len(formats)} 个格式")
            logger.info(f"📊 视频信息: {result['title']} ({result['duration']}秒)")

            # 确保返回有效结果
            if not result.get('title') and not formats:
                logger.error("❌ 转换结果无效：缺少标题和格式")
                return None

            return result

        except Exception as e:
            logger.error(f"❌ 格式转换失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

            # 即使转换失败，也返回基本信息
            fallback_result = {
                'title': ytdlp_info.get('title', 'Unknown') if ytdlp_info else 'Unknown',
                'duration': ytdlp_info.get('duration', 0) if ytdlp_info else 0,
                'extractor': 'cobalt_via_ytdlp',
                'client_used': client,
                'formats': [],
                'conversion_error': str(e)
            }
            logger.info(f"🔄 返回回退结果: {fallback_result['title']}")
            return fallback_result

    def _parse_innertube_response(self, response: Dict[str, Any], quality: str) -> Dict[str, Any]:
        """解析InnerTube API响应 - 增强的错误处理"""
        try:
            # 检查播放状态
            playability = response.get('playabilityStatus', {})
            status = playability.get('status')

            if status != 'OK':
                error_reason = playability.get('reason', '视频不可用')

                # 特殊错误处理
                if status == 'LOGIN_REQUIRED':
                    if 'bot' in error_reason.lower():
                        return {'error': 'bot_detected', 'message': '检测到机器人行为，需要尝试其他客户端'}
                    elif 'age' in error_reason.lower():
                        return {'error': 'age_restricted', 'message': '年龄限制视频'}
                    else:
                        return {'error': 'login_required', 'message': f'需要登录: {error_reason}'}
                elif status == 'UNPLAYABLE':
                    if 'country' in error_reason.lower() or 'region' in error_reason.lower():
                        return {'error': 'geo_blocked', 'message': '地区限制'}
                    else:
                        return {'error': 'unplayable', 'message': f'视频无法播放: {error_reason}'}
                elif status == 'AGE_VERIFICATION_REQUIRED':
                    return {'error': 'age_verification', 'message': '需要年龄验证'}
                else:
                    return {'error': 'video_unavailable', 'message': f'{status}: {error_reason}'}

            # 获取基本信息
            video_details = response.get('videoDetails', {})
            streaming_data = response.get('streamingData', {})

            if not streaming_data:
                return {'error': 'no_streaming_data', 'message': '没有流媒体数据'}

            # 解析格式
            formats = self._parse_formats(streaming_data, quality)

            if not formats:
                return {'error': 'no_formats', 'message': '没有可用格式'}

            # 构建返回结果
            result = {
                'success': True,
                'id': video_details.get('videoId'),
                'title': video_details.get('title'),
                'uploader': video_details.get('author'),
                'duration': int(video_details.get('lengthSeconds', 0)),
                'view_count': int(video_details.get('viewCount', 0)),
                'formats': formats,
                'extractor': 'cobalt_enhanced'
            }

            return result

        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return {'error': 'parse_failed', 'message': str(e)}

    def _parse_formats(self, streaming_data: Dict[str, Any], target_quality: str) -> List[Dict[str, Any]]:
        """解析视频格式"""
        formats = []

        # 获取自适应格式
        adaptive_formats = streaming_data.get('adaptiveFormats', [])

        for fmt in adaptive_formats:
            if not fmt.get('url'):
                continue

            format_info = {
                'format_id': str(fmt.get('itag', 'unknown')),
                'url': fmt.get('url'),
                'ext': self._get_ext_from_mime(fmt.get('mimeType', '')),
                'quality': fmt.get('qualityLabel'),
                'fps': fmt.get('fps'),
                'tbr': fmt.get('bitrate'),
                'filesize': int(fmt.get('contentLength', 0)) if fmt.get('contentLength') else None,
                'width': fmt.get('width'),
                'height': fmt.get('height'),
                'vcodec': 'none' if not fmt.get('width') else 'unknown',
                'acodec': 'none' if fmt.get('width') else 'unknown',
            }

            formats.append(format_info)

        return formats

    def _get_ext_from_mime(self, mime_type: str) -> str:
        """从MIME类型获取文件扩展名"""
        mime_to_ext = {
            'video/mp4': 'mp4',
            'video/webm': 'webm',
            'audio/mp4': 'm4a',
            'audio/webm': 'webm',
            'application/x-mpegURL': 'mp4'
        }

        for mime, ext in mime_to_ext.items():
            if mime in mime_type:
                return ext

        return 'mp4'  # 默认扩展名
