# -*- coding: utf-8 -*-
"""
YouTube下载策略模块

提供多种YouTube下载策略和配置
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class YouTubeStrategies:
    """YouTube下载策略管理器"""
    
    def __init__(self):
        self.strategies = []
        self._initialize_strategies()
    
    def _initialize_strategies(self):
        """初始化下载策略"""
        try:
            # 基础策略
            self.strategies = [
                {
                    'name': 'default',
                    'description': '默认策略',
                    'priority': 1,
                    'options': self._get_default_opts
                },
                {
                    'name': 'high_quality',
                    'description': '高质量策略',
                    'priority': 2,
                    'options': self._get_high_quality_opts
                },
                {
                    'name': 'with_cookies',
                    'description': '使用Cookies策略',
                    'priority': 3,
                    'options': self._get_cookies_opts
                },
                {
                    'name': 'mobile_client',
                    'description': '移动客户端策略',
                    'priority': 4,
                    'options': self._get_mobile_opts
                }
            ]
            
            logger.info(f"✅ 初始化 {len(self.strategies)} 个YouTube策略")
            
        except Exception as e:
            logger.error(f"❌ 初始化YouTube策略失败: {e}")
    
    def download(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """执行YouTube下载 - 双引擎策略"""
        try:
            # 获取输出目录
            output_dir = self._get_output_dir()

            # 双引擎策略：先尝试yt-dlp，失败后尝试PyTubeFix
            engines = [
                ('ytdlp', self._download_with_ytdlp),
                ('pytubefix', self._download_with_pytubefix)
            ]

            for engine_name, download_func in engines:
                try:
                    logger.info(f"🔄 尝试引擎: {engine_name}")

                    result = download_func(download_id, url, video_info, options, output_dir)

                    if result:
                        logger.info(f"✅ 引擎成功: {engine_name}")
                        return result
                    else:
                        logger.warning(f"❌ 引擎失败: {engine_name}")

                except Exception as e:
                    logger.error(f"❌ 引擎异常 {engine_name}: {e}")
                    continue

            logger.error(f"❌ 所有下载引擎都失败: {url}")
            return None

        except Exception as e:
            logger.error(f"❌ YouTube下载失败: {e}")
            return None
    
    def _download_with_ytdlp(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any], output_dir: Path) -> Optional[str]:
        """使用yt-dlp下载"""
        try:
            # 尝试不同的yt-dlp策略
            for strategy in self.strategies:
                try:
                    logger.info(f"🔄 yt-dlp策略: {strategy['name']}")

                    # 构建下载选项
                    ydl_opts = strategy['options'](download_id, url, options)
                    ydl_opts['outtmpl'] = str(output_dir / f'{download_id}.%(ext)s')

                    # 执行下载
                    result = self._execute_ytdlp_download(url, ydl_opts)

                    if result:
                        logger.info(f"✅ yt-dlp策略成功: {strategy['name']}")
                        return result
                    else:
                        logger.warning(f"❌ yt-dlp策略失败: {strategy['name']}")

                except Exception as e:
                    logger.error(f"❌ yt-dlp策略异常 {strategy['name']}: {e}")
                    continue

            return None

        except Exception as e:
            logger.error(f"❌ yt-dlp下载失败: {e}")
            return None

    def _download_with_pytubefix(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any], output_dir: Path) -> Optional[str]:
        """使用PyTubeFix下载"""
        try:
            # 检查PyTubeFix是否可用
            try:
                from .pytubefix_downloader import PyTubeFixDownloader
            except ImportError:
                logger.warning("⚠️ PyTubeFix不可用")
                return None

            # 获取代理配置
            proxy = self._get_proxy_config()

            # 创建PyTubeFix下载器
            downloader = PyTubeFixDownloader(proxy=proxy)

            # 执行下载
            import asyncio

            async def async_download():
                quality = options.get('quality', '720')
                return await downloader.download(url, str(output_dir), quality)

            # 在新的事件循环中运行
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已有事件循环在运行，创建新的线程
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, async_download())
                        result = future.result(timeout=60)
                else:
                    result = loop.run_until_complete(async_download())
            except RuntimeError:
                # 没有事件循环，直接运行
                result = asyncio.run(async_download())

            if result and result.get('success'):
                logger.info(f"✅ PyTubeFix下载成功: {result.get('filename')}")
                return result.get('filepath')
            else:
                error_msg = result.get('message', '未知错误') if result else '无返回结果'
                logger.error(f"❌ PyTubeFix下载失败: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"❌ PyTubeFix下载异常: {e}")
            return None

    def _execute_ytdlp_download(self, url: str, ydl_opts: Dict[str, Any]) -> Optional[str]:
        """执行yt-dlp下载"""
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 查找下载的文件
            output_template = ydl_opts.get('outtmpl', '')
            if output_template:
                base_path = Path(output_template).parent
                download_id = Path(output_template).stem.split('.')[0]

                for file_path in base_path.glob(f'{download_id}.*'):
                    if file_path.is_file():
                        return str(file_path)

            return None

        except Exception as e:
            logger.error(f"❌ yt-dlp执行失败: {e}")
            return None
    
    def _get_output_dir(self) -> Path:
        """获取输出目录"""
        try:
            from core.config import get_config
            output_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        except ImportError:
            output_dir = Path('/app/downloads')
        
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置"""
        try:
            from core.config import get_config
            return get_config('downloader.proxy', None)
        except ImportError:
            return None
    
    def _get_cookies_path(self) -> Optional[str]:
        """获取Cookies路径"""
        try:
            cookies_path = Path('cookies.txt')
            if cookies_path.exists():
                return str(cookies_path)
            return None
        except Exception:
            return None
    
    def _get_default_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """默认下载选项"""
        opts = {
            'format': options.get('quality', 'best'),
            'writesubtitles': options.get('subtitles', False),
            'writeautomaticsub': options.get('auto_subtitles', False),
            'writethumbnail': options.get('thumbnail', False),
            'writeinfojson': options.get('info_json', False),
        }
        
        # 添加代理
        proxy = self._get_proxy_config()
        if proxy:
            opts['proxy'] = proxy
        
        return opts
    
    def _get_high_quality_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """高质量下载选项"""
        opts = self._get_default_opts(download_id, url, options)
        
        # 高质量格式选择
        opts.update({
            'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
            'merge_output_format': 'mp4',
            'writesubtitles': True,
            'writethumbnail': True,
        })
        
        return opts
    
    def _get_cookies_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """使用Cookies的下载选项"""
        opts = self._get_default_opts(download_id, url, options)
        
        # 添加Cookies
        cookies_path = self._get_cookies_path()
        if cookies_path:
            opts['cookiefile'] = cookies_path
        
        return opts
    
    def _get_mobile_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """移动客户端下载选项"""
        opts = self._get_default_opts(download_id, url, options)
        
        # 移动客户端配置
        opts.update({
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage']
                }
            }
        })
        
        return opts
    
    def get_strategy_list(self) -> List[Dict[str, Any]]:
        """获取策略列表"""
        return [
            {
                'name': strategy['name'],
                'description': strategy['description'],
                'priority': strategy['priority']
            }
            for strategy in self.strategies
        ]
    
    def test_strategy(self, strategy_name: str, test_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ") -> Dict[str, Any]:
        """测试特定策略"""
        try:
            # 查找策略
            strategy = None
            for s in self.strategies:
                if s['name'] == strategy_name:
                    strategy = s
                    break
            
            if not strategy:
                return {
                    'success': False,
                    'error': f'未找到策略: {strategy_name}'
                }
            
            # 构建测试选项
            test_opts = strategy['options']('test', test_url, {})
            test_opts['quiet'] = True
            test_opts['no_warnings'] = True
            test_opts['simulate'] = True  # 只模拟，不实际下载
            
            # 测试执行
            import yt_dlp
            import time
            
            start_time = time.time()
            
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
            
            end_time = time.time()
            
            if info:
                return {
                    'success': True,
                    'strategy': strategy_name,
                    'response_time': round(end_time - start_time, 2),
                    'title': info.get('title', 'N/A'),
                    'duration': info.get('duration', 'N/A'),
                    'formats_count': len(info.get('formats', []))
                }
            else:
                return {
                    'success': False,
                    'strategy': strategy_name,
                    'error': '未获取到视频信息'
                }
                
        except Exception as e:
            return {
                'success': False,
                'strategy': strategy_name,
                'error': str(e)
            }
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """获取所有策略状态"""
        status = {
            'total_strategies': len(self.strategies),
            'available_strategies': [s['name'] for s in self.strategies],
            'test_results': {}
        }
        
        # 测试所有策略
        for strategy in self.strategies:
            test_result = self.test_strategy(strategy['name'])
            status['test_results'][strategy['name']] = test_result
        
        return status
    
    def add_custom_strategy(self, name: str, description: str, options_func: callable, priority: int = 10):
        """添加自定义策略"""
        try:
            custom_strategy = {
                'name': name,
                'description': description,
                'priority': priority,
                'options': options_func
            }
            
            self.strategies.append(custom_strategy)
            
            # 按优先级排序
            self.strategies.sort(key=lambda x: x['priority'])
            
            logger.info(f"✅ 添加自定义策略: {name}")
            
        except Exception as e:
            logger.error(f"❌ 添加自定义策略失败: {e}")
    
    def remove_strategy(self, name: str) -> bool:
        """移除策略"""
        try:
            original_count = len(self.strategies)
            self.strategies = [s for s in self.strategies if s['name'] != name]
            
            if len(self.strategies) < original_count:
                logger.info(f"✅ 移除策略: {name}")
                return True
            else:
                logger.warning(f"⚠️ 未找到策略: {name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 移除策略失败: {e}")
            return False
