# -*- coding: utf-8 -*-
"""
视频信息提取器

集成多种提取方法，提供统一的视频信息提取接口
"""

import logging
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class VideoExtractor:
    """视频信息提取器"""
    
    def __init__(self):
        self.extractors = []
        self._initialize_extractors()
    
    def _initialize_extractors(self):
        """初始化提取器（新策略：yt-dlp优先）"""
        try:
            # 1. yt-dlp作为主要引擎（使用无PO Token智能随机客户端策略）
            self.extractors.append(('ytdlp', None))  # 直接使用，不需要类
            logger.info("✅ yt-dlp引擎设为主要引擎（无PO Token智能随机客户端）")

            # 2. PyTubeFix作为备选引擎（使用PO Token策略）
            try:
                from .pytubefix_downloader import PyTubeFixDownloader
                self.extractors.append(('pytubefix', PyTubeFixDownloader))
                logger.info("✅ PyTubeFix下载器设为备选引擎（PO Token策略）")
            except ImportError:
                logger.debug("🔍 PyTubeFix下载器不可用")

            logger.info(f"📋 双引擎配置完成: {len(self.extractors)} 个引擎")
            logger.info(f"   🥇 主要引擎: yt-dlp（无PO Token + 智能随机客户端）")
            logger.info(f"   🥈 备选引擎: PyTubeFix（PO Token + 稳定配置）")

        except Exception as e:
            logger.error(f"❌ 初始化提取器失败: {e}")
    
    def extract_info(self, url: str, options: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """提取视频信息"""
        options = options or {}
        last_error = None
        
        for extractor_name, extractor_class in self.extractors:
            try:
                logger.info(f"🔄 尝试提取器: {extractor_name}")

                if extractor_name == 'pytubefix':
                    result = self._extract_with_pytubefix(url, extractor_class, options)
                elif extractor_name == 'ytdlp':
                    result = self._extract_with_ytdlp(url, options)
                else:
                    continue
                
                if result and not result.get('error'):
                    logger.info(f"✅ 提取成功: {extractor_name}")
                    result['extractor_used'] = extractor_name
                    return result
                else:
                    error_msg = result.get('message', '未知错误') if result else '无返回结果'
                    logger.warning(f"❌ 提取器失败 {extractor_name}: {error_msg}")
                    last_error = error_msg
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ 提取器异常 {extractor_name}: {error_msg}")
                last_error = error_msg
                continue
        
        # 所有提取器都失败
        logger.error(f"❌ 所有提取器都失败，最后错误: {last_error}")
        return {
            'error': 'all_extractors_failed',
            'message': f'所有提取器都失败: {last_error}',
            'url': url
        }
    
    def _extract_with_pytubefix(self, url: str, extractor_class, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用PyTubeFix提取"""
        try:
            import asyncio
            from urllib.parse import urlparse

            # 首先检查URL是否为YouTube - 避免无效尝试
            parsed_url = urlparse(url.lower())
            youtube_domains = ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'youtube-nocookie.com']

            if not any(domain in parsed_url.netloc for domain in youtube_domains):
                logger.info(f"🚫 PyTubeFix跳过非YouTube URL: {parsed_url.netloc}")
                return {'error': 'unsupported_site', 'message': 'PyTubeFix只支持YouTube网站'}

            # 获取PyTubeFix专用的代理配置
            proxy = self._get_pytubefix_proxy_config()

            # 创建PyTubeFix下载器实例
            downloader = extractor_class(proxy=proxy)

            async def async_extract():
                quality = options.get('quality', '720')
                return await downloader.extract_info(url, quality)

            # 在新的事件循环中运行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已有事件循环在运行，创建新的线程
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_extract())
                        return future.result(timeout=30)
                else:
                    return loop.run_until_complete(async_extract())
            except RuntimeError:
                # 没有事件循环，直接运行
                return asyncio.run(async_extract())

        except Exception as e:
            logger.error(f"❌ PyTubeFix提取失败: {e}")
            return {'error': 'pytubefix_failed', 'message': str(e)}
    
    def _extract_with_ytdlp(self, url: str, options: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """使用yt-dlp提取（集成智能格式选择器）"""
        try:
            import yt_dlp

            # 获取用户质量选择
            user_quality = options.get('quality', 'high')
            logger.info(f"🎯 用户选择质量: {user_quality}")

            # 使用智能格式选择器
            try:
                from core.smart_format_selector import select_format_for_user
                proxy = self._get_proxy_config()

                format_id, reason, info = select_format_for_user(user_quality, url, proxy)
                logger.info(f"🏆 智能选择格式: {format_id}")
                logger.info(f"   选择原因: {reason}")

                # 基础配置（使用智能选择的格式）
                ydl_opts = {
                    'format': format_id,        # 使用智能选择的格式ID
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'noprogress': True,         # 防止数据类型错误
                }

                if proxy:
                    ydl_opts['proxy'] = proxy
                    logger.info(f"✅ yt-dlp使用代理: {proxy}")

                # 自动获取cookies配置
                cookies_path = self._get_cookies_for_site(url)
                if cookies_path:
                    ydl_opts['cookiefile'] = cookies_path
                    logger.info(f"✅ yt-dlp使用cookies: {cookies_path}")
                elif options.get('cookies'):
                    ydl_opts['cookiefile'] = options['cookies']
                    logger.info(f"✅ yt-dlp使用选项cookies: {options['cookies']}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    video_info = ydl.extract_info(url, download=False)
                    if video_info:
                        # 添加智能选择器的信息
                        sanitized_info = ydl.sanitize_info(video_info)
                        sanitized_info['smart_format_selection'] = {
                            'selected_format': format_id,
                            'selection_reason': reason,
                            'total_formats_analyzed': info.get('total_formats', 0),
                            'available_qualities': info.get('available_qualities', [])
                        }
                        logger.info(f"✅ yt-dlp智能提取成功: {len(sanitized_info.get('formats', []))} 个格式")
                        return sanitized_info
                    else:
                        return {'error': 'no_info', 'message': 'yt-dlp未返回信息'}

            except Exception as smart_error:
                logger.warning(f"⚠️ 智能格式选择失败，使用传统方法: {smart_error}")

                # 降级到传统方法
                ydl_opts = {
                    'format': 'best',           # 使用简单格式选择
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'noprogress': True,         # 防止数据类型错误
                }

                proxy = self._get_proxy_config()
                if proxy:
                    ydl_opts['proxy'] = proxy

                # 应用PO Token配置 (传统方法的备选)
                from core.po_token_manager import apply_po_token_to_ytdlp
                ydl_opts = apply_po_token_to_ytdlp(ydl_opts, url, "VideoExtractor-Fallback")

                # 自动获取cookies配置
                cookies_path = self._get_cookies_for_site(url)
                if cookies_path:
                    ydl_opts['cookiefile'] = cookies_path
                elif options.get('cookies'):
                    ydl_opts['cookiefile'] = options['cookies']

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        sanitized_info = ydl.sanitize_info(info)
                        sanitized_info['smart_format_selection'] = {
                            'selected_format': 'best',
                            'selection_reason': f'智能选择失败，降级到传统方法: {str(smart_error)}',
                            'fallback_used': True
                        }
                        logger.info(f"✅ yt-dlp传统提取成功: {len(sanitized_info.get('formats', []))} 个格式")
                        return sanitized_info
                    else:
                        return {'error': 'no_info', 'message': 'yt-dlp未返回信息'}

        except Exception as e:
            logger.error(f"❌ yt-dlp提取失败: {e}")
            return {'error': 'ytdlp_failed', 'message': str(e)}

    def _get_cookies_for_site(self, url: str) -> Optional[str]:
        """获取网站对应的 Cookies 文件"""
        try:
            # 尝试导入 cookies 管理器
            from modules.cookies.manager import get_cookies_manager
            cookies_manager = get_cookies_manager()
            return cookies_manager.get_cookies_for_ytdlp(url)
        except Exception as e:
            logger.debug(f"🔍 获取Cookies失败: {e}")
            return None
    
    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置 - 使用统一的代理助手"""
        from core.proxy_converter import ProxyHelper
        return ProxyHelper.get_ytdlp_proxy("VideoExtractor")

    def _get_pytubefix_proxy_config(self) -> Optional[str]:
        """获取PyTubeFix专用的代理配置 - 使用统一的代理助手"""
        from core.proxy_converter import ProxyHelper
        return ProxyHelper.get_pytubefix_proxy("VideoExtractor-PyTubeFix")




    
    def get_available_extractors(self) -> List[str]:
        """获取可用的提取器列表"""
        return [name for name, _ in self.extractors]
    
    def test_extractor(self, extractor_name: str, test_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ") -> Dict[str, Any]:
        """测试特定提取器"""
        try:
            # 查找提取器
            extractor_class = None
            for name, cls in self.extractors:
                if name == extractor_name:
                    extractor_class = cls
                    break
            
            if extractor_class is None and extractor_name != 'ytdlp':
                return {
                    'success': False,
                    'error': f'未找到提取器: {extractor_name}'
                }
            
            # 测试提取
            start_time = time.time()
            
            if extractor_name == 'pytubefix':
                result = self._extract_with_pytubefix(test_url, extractor_class, {})
            elif extractor_name == 'ytdlp':
                result = self._extract_with_ytdlp(test_url, {})
            else:
                return {
                    'success': False,
                    'error': f'不支持的提取器: {extractor_name}'
                }
            
            end_time = time.time()
            response_time = end_time - start_time
            
            if result and not result.get('error'):
                return {
                    'success': True,
                    'response_time': round(response_time, 2),
                    'title': result.get('title', 'N/A'),
                    'duration': result.get('duration', 'N/A'),
                    'extractor': extractor_name
                }
            else:
                return {
                    'success': False,
                    'response_time': round(response_time, 2),
                    'error': result.get('message', '未知错误') if result else '无返回结果',
                    'extractor': extractor_name
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'extractor': extractor_name
            }
    
    def get_extractor_status(self) -> Dict[str, Any]:
        """获取所有提取器状态"""
        status = {
            'total_extractors': len(self.extractors),
            'available_extractors': [],
            'test_results': {}
        }
        
        for extractor_name, _ in self.extractors:
            status['available_extractors'].append(extractor_name)
            
            # 快速测试（使用较短的测试URL）
            test_result = self.test_extractor(extractor_name)
            status['test_results'][extractor_name] = test_result
        
        return status
