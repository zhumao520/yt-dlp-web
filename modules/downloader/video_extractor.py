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
        """初始化提取器"""
        try:
            # 1. 尝试导入PyTubeFix下载器
            try:
                from .pytubefix_downloader import PyTubeFixDownloader
                self.extractors.append(('pytubefix', PyTubeFixDownloader))
                logger.info("✅ PyTubeFix下载器可用")
            except ImportError:
                logger.debug("🔍 PyTubeFix下载器不可用")

            # 2. yt-dlp作为主要引擎
            self.extractors.append(('ytdlp', None))  # 直接使用，不需要类

            logger.info(f"📋 可用提取器: {len(self.extractors)} 个")

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

            # 获取代理配置
            proxy = self._get_proxy_config()

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
        """使用yt-dlp提取"""
        try:
            import yt_dlp
            
            # 构建yt-dlp选项
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            # 添加代理配置
            proxy = self._get_proxy_config()
            if proxy:
                ydl_opts['proxy'] = proxy
            
            # 添加其他选项
            if options.get('cookies'):
                ydl_opts['cookiefile'] = options['cookies']
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return ydl.sanitize_info(info)
                else:
                    return {'error': 'no_info', 'message': 'yt-dlp未返回信息'}
                    
        except Exception as e:
            logger.error(f"❌ yt-dlp提取失败: {e}")
            return {'error': 'ytdlp_failed', 'message': str(e)}
    
    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置"""
        try:
            # 尝试从配置获取代理
            try:
                from core.config import get_config
                return get_config('downloader.proxy', None)
            except ImportError:
                pass
            
            # 尝试从数据库获取代理
            try:
                from core.database import get_database
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
                    return proxy_url
            except ImportError:
                pass
            
            return None
            
        except Exception as e:
            logger.debug(f"🔍 获取代理配置失败: {e}")
            return None
    
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
