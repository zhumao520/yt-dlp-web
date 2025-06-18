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

            # 获取PyTubeFix专用的代理配置
            proxy = self._get_pytubefix_proxy_config()

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

            # 处理不同类型的输出模板
            if not output_template:
                logger.warning("⚠️ 未找到输出模板，无法定位下载文件")
                return None

            # 如果是字典类型，取默认值
            if isinstance(output_template, dict):
                output_template = output_template.get('default', '')
                if not output_template:
                    logger.warning("⚠️ 字典类型输出模板中未找到默认值")
                    return None

            # 确保是字符串类型
            if not isinstance(output_template, str):
                logger.error(f"❌ 输出模板类型错误: {type(output_template)}, 值: {output_template}")
                return None

            try:
                base_path = Path(output_template).parent
                # 更安全的文件名提取
                template_name = Path(output_template).name
                # 移除扩展名模板部分，如 .%(ext)s
                if '.%(ext)s' in template_name:
                    download_id = template_name.replace('.%(ext)s', '')
                else:
                    download_id = Path(output_template).stem.split('.')[0]

                # 查找匹配的文件
                found_files = list(base_path.glob(f'{download_id}.*'))
                if found_files:
                    # 返回第一个找到的文件
                    result_file = found_files[0]
                    if result_file.is_file():
                        logger.info(f"✅ 找到下载文件: {result_file}")
                        return str(result_file)

                logger.warning(f"⚠️ 未找到匹配的下载文件: {download_id}.*")
                return None

            except Exception as path_error:
                logger.error(f"❌ 文件路径处理失败: {path_error}")
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
            # 首先尝试从运行时配置获取
            from core.config import get_config
            proxy = get_config('downloader.proxy', None)
            if proxy:
                return proxy

            # 如果运行时配置没有，从数据库获取
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

            return None
        except ImportError:
            return None

    def _get_ffmpeg_path(self) -> Optional[str]:
        """获取FFmpeg路径"""
        try:
            # 尝试从FFmpeg工具模块获取
            try:
                from modules.downloader.ffmpeg_tools import get_ffmpeg_path
                ffmpeg_path = get_ffmpeg_path()
                if ffmpeg_path:
                    return ffmpeg_path
            except ImportError:
                pass

            # 尝试常见路径
            common_paths = [
                'ffmpeg/bin/ffmpeg.exe',  # Windows项目路径
                'ffmpeg/bin/ffmpeg',      # Linux项目路径
                '/usr/bin/ffmpeg',        # 系统路径
                '/usr/local/bin/ffmpeg',  # 本地安装
                'ffmpeg'                  # PATH中
            ]

            for path in common_paths:
                if Path(path).exists():
                    return str(Path(path).resolve())

            # 尝试which命令
            import shutil
            which_ffmpeg = shutil.which('ffmpeg')
            if which_ffmpeg:
                return which_ffmpeg

            return None

        except Exception as e:
            logger.debug(f"🔍 获取FFmpeg路径失败: {e}")
            return None

    def _get_pytubefix_proxy_config(self) -> Optional[str]:
        """获取PyTubeFix专用的代理配置（HTTP代理）"""
        try:
            # 尝试从数据库获取
            try:
                from core.database import get_database
                db = get_database()
                proxy_config = db.get_proxy_config()

                if proxy_config and proxy_config.get('enabled'):
                    host = proxy_config.get('host')

                    # 为PyTubeFix尝试HTTP代理端口
                    if host == '192.168.2.222':  # 用户的代理服务器
                        # 使用用户提到的HTTP代理端口
                        http_proxy = f"http://{host}:1190"
                        logger.info(f"✅ 为PyTubeFix使用HTTP代理: {http_proxy}")
                        return http_proxy

                    # 其他情况，尝试转换为HTTP代理
                    proxy_type = proxy_config.get('proxy_type', 'http')
                    if proxy_type == 'socks5':
                        # 尝试使用HTTP端口
                        http_proxy = f"http://{host}:1190"
                        return http_proxy
                    else:
                        # 已经是HTTP代理
                        proxy_url = f"http://"
                        if proxy_config.get('username'):
                            proxy_url += f"{proxy_config['username']}"
                            if proxy_config.get('password'):
                                proxy_url += f":{proxy_config['password']}"
                            proxy_url += "@"
                        proxy_url += f"{host}:{proxy_config.get('port')}"
                        return proxy_url
            except ImportError:
                pass

            return None

        except Exception as e:
            logger.debug(f"🔍 获取PyTubeFix代理配置失败: {e}")
            return None
    
    def _get_cookies_path(self) -> Optional[str]:
        """获取Cookies路径"""
        try:
            # 检查多个可能的cookies路径（包括JSON和TXT格式）
            possible_paths = [
                'data/cookies/youtube.txt',
                '/app/data/cookies/youtube.txt',
                'data/cookies/youtube_temp.txt',  # 临时转换文件
                '/app/data/cookies/youtube_temp.txt',
                'cookies.txt',
                'youtube.txt'
            ]

            for path_str in possible_paths:
                cookies_path = Path(path_str)
                if cookies_path.exists() and cookies_path.stat().st_size > 0:
                    logger.debug(f"✅ 找到cookies文件: {cookies_path}")
                    return str(cookies_path.resolve())

            # 如果没有找到TXT文件，尝试从JSON文件转换
            json_paths = [
                'data/cookies/youtube.json',
                '/app/data/cookies/youtube.json'
            ]

            for json_path_str in json_paths:
                json_path = Path(json_path_str)
                if json_path.exists() and json_path.stat().st_size > 0:
                    logger.info(f"🔄 发现JSON cookies文件，准备转换: {json_path}")
                    # 使用cookies管理器进行转换
                    try:
                        from modules.cookies.manager import get_cookies_manager
                        cookies_manager = get_cookies_manager()
                        temp_path = cookies_manager.get_cookies_for_ytdlp("https://www.youtube.com/")
                        if temp_path:
                            logger.info(f"✅ JSON转换为Netscape格式: {temp_path}")
                            return temp_path
                    except Exception as e:
                        logger.warning(f"⚠️ JSON转换失败: {e}")

            logger.debug("⚠️ 未找到有效的cookies文件")
            return None
        except Exception as e:
            logger.debug(f"🔍 获取cookies路径失败: {e}")
            return None

    def _get_po_token(self) -> Optional[str]:
        """获取YouTube PO Token"""
        try:
            # 尝试从数据库获取PO Token配置
            try:
                from core.database import get_database
                db = get_database()
                # 假设有一个获取PO Token的方法
                po_token_config = db.execute_query(
                    'SELECT value FROM settings WHERE key = ?',
                    ('youtube_po_token',)
                )
                if po_token_config and po_token_config[0]['value']:
                    return po_token_config[0]['value']
            except:
                pass

            # 尝试从环境变量获取
            import os
            po_token = os.getenv('YOUTUBE_PO_TOKEN')
            if po_token:
                return po_token

            # 尝试从配置文件获取
            try:
                from core.config import get_config
                po_token = get_config('youtube.po_token', None)
                if po_token:
                    return po_token
            except:
                pass

            return None

        except Exception as e:
            logger.debug(f"🔍 获取PO Token失败: {e}")
            return None

    def _convert_cookies_to_netscape(self, cookies_data: list) -> str:
        """将cookies数据转换为Netscape格式"""
        try:
            lines = ["# Netscape HTTP Cookie File"]
            lines.append("# This is a generated file! Do not edit.")
            lines.append("")

            for cookie in cookies_data:
                # 提取cookie信息
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                domain = cookie.get('domain', '.youtube.com')
                path = cookie.get('path', '/')
                expires = cookie.get('expiration', cookie.get('expires', 0))
                secure = cookie.get('secure', False)

                # 修复flag字段逻辑：根据domain是否以.开头来判断
                if domain.startswith('.'):
                    domain_specified = 'TRUE'
                else:
                    domain_specified = 'FALSE'
                    # 如果原来的flag字段存在，优先使用
                    if 'flag' in cookie:
                        domain_specified = 'TRUE' if cookie.get('flag', False) else 'FALSE'

                # 确保过期时间是整数
                try:
                    expires = int(float(expires))
                except (ValueError, TypeError):
                    expires = 0

                # 跳过无效的cookie
                if not name or not domain:
                    continue

                # 转换为Netscape格式
                # domain, domain_specified, path, secure, expires, name, value
                secure_str = 'TRUE' if secure else 'FALSE'
                line = f"{domain}\t{domain_specified}\t{path}\t{secure_str}\t{expires}\t{name}\t{value}"
                lines.append(line)

            return '\n'.join(lines)

        except Exception as e:
            logger.error(f"❌ 转换cookies格式失败: {e}")
            return ""

    def _get_default_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """默认下载选项"""
        # 智能格式选择，优先使用兼容性好的格式
        quality = options.get('quality', 'best')
        if quality == 'best':
            format_selector = 'best[height<=1080]/best[height<=720]/best'
        else:
            format_selector = f'best[height<={quality}]/best'

        opts = {
            'format': format_selector,
            'writesubtitles': options.get('subtitles', False),
            'writeautomaticsub': options.get('auto_subtitles', False),
            'writethumbnail': options.get('thumbnail', False),
            'writeinfojson': options.get('info_json', False),
        }

        # 添加代理
        proxy = self._get_proxy_config()
        if proxy:
            opts['proxy'] = proxy

        # 添加cookies支持以避免机器人检测
        cookies_path = self._get_cookies_path()
        if cookies_path:
            opts['cookiefile'] = cookies_path
            logger.info(f"✅ 使用cookies文件: {cookies_path}")
        else:
            # 尝试从cookies管理器获取YouTube cookies
            try:
                from modules.cookies.manager import get_cookies_manager
                cookies_manager = get_cookies_manager()

                # 先检查cookies文件是否存在
                cookies_file = cookies_manager.cookies_dir / 'youtube.json'
                logger.info(f"🔍 检查cookies文件: {cookies_file}")
                logger.info(f"🔍 文件存在: {cookies_file.exists()}")
                if cookies_file.exists():
                    logger.info(f"🔍 文件大小: {cookies_file.stat().st_size} 字节")

                youtube_cookies = cookies_manager.get_cookies('youtube')

                logger.info(f"🔍 Cookies管理器返回: success={youtube_cookies.get('success') if youtube_cookies else None}")

                # 添加详细的调试信息
                if youtube_cookies:
                    logger.info(f"🔍 Cookies管理器完整返回: {youtube_cookies}")
                else:
                    logger.warning("⚠️ Cookies管理器返回None")

                if youtube_cookies and youtube_cookies.get('success'):
                    # 获取cookies数据 - 根据Web代码分析数据结构
                    data = youtube_cookies.get('data', {})
                    logger.info(f"🔍 Cookies数据类型: {type(data)}")
                    logger.info(f"🔍 Cookies数据键: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

                    # 根据cookies管理器的实际返回结构解析
                    cookies_data = []
                    if isinstance(data, dict):
                        # 从cookies管理器的get_cookies方法看，应该直接有cookies字段
                        if 'cookies' in data:
                            cookies_data = data['cookies']
                            logger.info(f"✅ 从data.cookies获取到: {len(cookies_data)}个cookies")
                        else:
                            logger.warning(f"⚠️ data中没有cookies字段，可用字段: {list(data.keys())}")
                    elif isinstance(data, list):
                        cookies_data = data
                        logger.info(f"✅ data直接是列表: {len(cookies_data)}个cookies")
                    else:
                        logger.warning(f"⚠️ 未知的data类型: {type(data)}")

                    logger.info(f"🔍 最终解析到cookies数量: {len(cookies_data)}")

                    if cookies_data:
                        # 转换为Netscape格式
                        netscape_content = self._convert_cookies_to_netscape(cookies_data)

                        if netscape_content:
                            # 创建临时cookies文件
                            import tempfile
                            temp_cookies = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                            temp_cookies.write(netscape_content)
                            temp_cookies.close()
                            opts['cookiefile'] = temp_cookies.name
                            logger.info(f"✅ 使用YouTube cookies: {temp_cookies.name} ({len(cookies_data)}个)")
                        else:
                            logger.warning("⚠️ Cookies转换为Netscape格式失败")
                    else:
                        logger.warning("⚠️ YouTube cookies数据为空")
                else:
                    logger.warning("⚠️ 未找到YouTube cookies，可能被检测为机器人")
            except Exception as e:
                logger.error(f"❌ 获取cookies失败: {e}")
                import traceback
                logger.debug(f"详细错误: {traceback.format_exc()}")
                logger.warning("⚠️ 建议上传YouTube cookies以避免机器人检测")

        # 添加FFmpeg路径
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            opts['ffmpeg_location'] = ffmpeg_path
            logger.debug(f"✅ 使用FFmpeg: {ffmpeg_path}")
        else:
            logger.warning("⚠️ 未找到FFmpeg，高质量合并可能失败")

        return opts
    
    def _get_high_quality_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """高质量下载选项"""
        opts = self._get_default_opts(download_id, url, options)

        # 检查FFmpeg是否可用
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            # FFmpeg可用，使用高质量合并格式
            opts.update({
                'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
                'merge_output_format': 'mp4',
                'writesubtitles': True,
                'writethumbnail': True,
            })
            logger.info("✅ 使用FFmpeg进行高质量合并")
        else:
            # FFmpeg不可用，使用单一最佳格式
            opts.update({
                'format': 'best[height<=2160]/best',
                'writesubtitles': True,
                'writethumbnail': True,
            })
            logger.warning("⚠️ FFmpeg不可用，使用单一格式下载")

        # 添加PO Token支持以访问高质量格式
        po_token = self._get_po_token()
        if po_token:
            opts['extractor_args'] = {
                'youtube': {
                    'po_token': po_token
                }
            }
            logger.info("✅ 高质量下载使用PO Token")

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

        # 移动客户端配置 - 使用更兼容的格式
        opts.update({
            'format': 'best[height<=720]/worst',  # 降低质量要求，提高兼容性
        })

        # 移动客户端配置
        extractor_args = {
            'youtube': {
                'player_client': ['android', 'web'],  # 添加web作为备用
                'player_skip': ['webpage']
            }
        }

        # 添加PO Token支持
        po_token = self._get_po_token()
        if po_token:
            extractor_args['youtube']['po_token'] = po_token
            logger.info("✅ 移动客户端使用PO Token")
        else:
            # 如果没有PO Token，跳过需要认证的格式
            extractor_args['youtube']['formats'] = 'missing_pot'
            logger.warning("⚠️ 移动客户端缺少PO Token，跳过高级格式")

        opts.update({
            'extractor_args': extractor_args
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
