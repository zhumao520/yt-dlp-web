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
        # 移除全局进度回调，改为每个下载任务独立设置
        self._initialize_strategies()

    def _create_progress_callback(self, download_id: str):
        """为特定下载任务创建进度回调函数"""
        def progress_callback(progress_data):
            """任务专用进度回调"""
            try:
                # 使用统一的进度处理工具
                from core.file_utils import ProgressUtils
                from .manager import get_download_manager
                manager = get_download_manager()

                # 转换进度数据格式
                if progress_data.get('status') == 'downloading':
                    total = progress_data.get('total_bytes') or progress_data.get('total_bytes_estimate')
                    downloaded = progress_data.get('downloaded_bytes')

                    if total and downloaded:
                        try:
                            total = float(total)
                            downloaded = float(downloaded)
                            if total > 0:
                                # 使用统一的进度计算
                                progress = ProgressUtils.calculate_progress(int(downloaded), int(total))
                                manager._update_download_status(download_id, 'downloading', progress)
                        except (ValueError, TypeError, ZeroDivisionError):
                            pass
            except Exception as e:
                logger.debug(f"⚠️ 进度回调失败 {download_id}: {e}")

        return progress_callback
    
    def _initialize_strategies(self):
        """初始化下载策略"""
        try:
            # 基础策略
            self.strategies = [
                {
                    'name': 'audio_only',
                    'description': '仅音频策略',
                    'priority': 1,
                    'options': self._get_audio_only_opts,
                    'condition': lambda options: self._is_audio_only_request(options)
                },
                {
                    'name': 'default',
                    'description': '默认策略',
                    'priority': 2,
                    'options': self._get_default_opts
                },
                {
                    'name': 'high_quality',
                    'description': '高质量策略',
                    'priority': 3,
                    'options': self._get_high_quality_opts
                },
                {
                    'name': 'with_cookies',
                    'description': '使用Cookies策略',
                    'priority': 4,
                    'options': self._get_cookies_opts
                },
                {
                    'name': 'mobile_client',
                    'description': '移动客户端策略',
                    'priority': 5,
                    'options': self._get_mobile_opts
                }
            ]
            
            logger.info(f"✅ 初始化 {len(self.strategies)} 个YouTube策略")
            
        except Exception as e:
            logger.error(f"❌ 初始化YouTube策略失败: {e}")
    
    def download(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """执行YouTube下载 - 双引擎策略"""
        try:
            logger.info(f"🚀 YouTube策略开始下载: {download_id} - {url}")

            # 智能选择输出目录：需要转换的使用临时目录
            output_dir = self._get_smart_output_dir(options)

            # 双引擎策略：先尝试yt-dlp，失败后尝试PyTubeFix
            engines = [
                ('ytdlp', self._download_with_ytdlp),
                ('pytubefix', self._download_with_pytubefix)
            ]

            logger.info(f"🔧 准备尝试 {len(engines)} 个下载引擎")

            for engine_name, download_func in engines:
                try:
                    logger.info(f"🔄 尝试引擎: {engine_name}")

                    result = download_func(download_id, url, video_info, options, output_dir)

                    if result:
                        logger.info(f"✅ 引擎成功: {engine_name}")

                        # 检查是否需要音频转换
                        if self._needs_audio_conversion(options):
                            converted_path = self._convert_to_audio(result, options)
                            if converted_path:
                                # 删除原始文件
                                try:
                                    Path(result).unlink()
                                except:
                                    pass
                                result = converted_path

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
            logger.info(f"🔧 yt-dlp引擎开始下载: {download_id}")

            # 筛选适用的策略
            applicable_strategies = []
            for strategy in self.strategies:
                # 检查策略条件
                if 'condition' in strategy:
                    if strategy['condition'](options):
                        applicable_strategies.append(strategy)
                        logger.info(f"✅ 策略条件匹配: {strategy['name']}")
                    else:
                        logger.debug(f"⏭️ 策略条件不匹配: {strategy['name']}")
                        continue
                else:
                    # 没有条件的策略总是适用
                    applicable_strategies.append(strategy)

            # 如果没有适用的策略，使用所有策略
            if not applicable_strategies:
                applicable_strategies = [s for s in self.strategies if 'condition' not in s]
                logger.warning("⚠️ 没有匹配的策略，使用默认策略")

            # 尝试适用的yt-dlp策略
            for strategy in applicable_strategies:
                try:
                    logger.info(f"🔄 yt-dlp策略: {strategy['name']}")

                    # 构建下载选项
                    ydl_opts = strategy['options'](download_id, url, options)
                    ydl_opts['outtmpl'] = str(output_dir / f'{download_id}.%(ext)s')

                    # 执行下载
                    result = self._execute_ytdlp_download(download_id, url, ydl_opts)

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
        """使用PyTubeFix下载（优化版，复用已提取的信息）"""
        try:
            logger.info(f"🔧 PyTubeFix引擎开始下载: {download_id}")

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

            # 设置任务专用进度回调
            task_progress_callback = self._create_progress_callback(download_id)

            def pytubefix_progress_callback(progress_data):
                """PyTubeFix进度回调"""
                try:
                    # 使用统一的进度数据格式化
                    from core.file_utils import ProgressUtils
                    formatted_data = ProgressUtils.format_progress_data(
                        progress_data.get('downloaded_bytes', 0),
                        progress_data.get('total_bytes', 0),
                        progress_data.get('status', 'downloading')
                    )
                    task_progress_callback(formatted_data)
                except Exception as e:
                    logger.debug(f"⚠️ PyTubeFix进度回调转发失败: {e}")

            downloader.set_progress_callback(pytubefix_progress_callback, download_id)

            # 执行下载 - 使用优化的缓存下载方法
            import asyncio

            async def async_download():
                quality = options.get('quality', '720')
                # 使用新的缓存下载方法，传入已提取的视频信息
                result = await downloader.download_with_cached_info(url, str(output_dir), quality, video_info)

                # 如果下载成功且需要音频转换，进行后处理
                if result and result.get('success') and self._needs_audio_conversion(options):
                    file_path = result.get('filepath')
                    if file_path:
                        converted_path = self._convert_to_audio(file_path, options)
                        if converted_path:
                            # 更新结果中的文件路径
                            result['filepath'] = converted_path
                            result['file_path'] = converted_path
                            result['filename'] = Path(converted_path).name

                return result

            # 安全的异步处理，避免死锁
            try:
                # 检查是否在异步上下文中
                try:
                    loop = asyncio.get_running_loop()
                    # 在运行的事件循环中，使用线程池避免死锁
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(asyncio.run, async_download())
                        result = future.result(timeout=120)  # 增加超时时间

                except RuntimeError:
                    # 没有运行的事件循环，直接运行
                    result = asyncio.run(async_download())

            except concurrent.futures.TimeoutError:
                logger.error("❌ PyTubeFix下载超时（120秒）")
                return None
            except Exception as e:
                logger.error(f"❌ PyTubeFix异步处理异常: {e}")
                return None

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

    def _execute_ytdlp_download(self, download_id: str, url: str, ydl_opts: Dict[str, Any]) -> Optional[str]:
        """执行yt-dlp下载"""
        try:
            import yt_dlp

            # 创建任务专用进度回调
            task_progress_callback = self._create_progress_callback(download_id)

            # 添加安全的进度回调，避免类型错误
            def safe_progress_hook(d):
                """安全的进度回调，避免类型转换错误"""
                try:
                    if d.get('status') == 'downloading':
                        # 安全地处理进度数据，避免类型错误
                        total = d.get('total_bytes') or d.get('total_bytes_estimate')
                        downloaded = d.get('downloaded_bytes')

                        # 确保数据类型正确
                        if total is not None and downloaded is not None:
                            try:
                                total = float(total) if total else 0.0
                                downloaded = float(downloaded) if downloaded else 0.0

                                if total > 0:
                                    # 使用统一的进度处理工具，带平滑化处理
                                    from core.file_utils import ProgressUtils
                                    formatted_data = ProgressUtils.format_progress_data(
                                        int(downloaded), int(total), 'downloading', download_id
                                    )
                                    task_progress_callback(formatted_data)
                            except (ValueError, TypeError, ZeroDivisionError) as e:
                                # 忽略类型转换错误，避免中断下载
                                pass
                except Exception as e:
                    # 进度回调失败不应该影响下载
                    pass

            # 添加进度回调到选项中
            if 'progress_hooks' not in ydl_opts:
                ydl_opts['progress_hooks'] = []
            ydl_opts['progress_hooks'].append(safe_progress_hook)

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

            # 初始化download_id变量，避免作用域问题
            download_id = "unknown"

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
        """获取最终输出目录"""
        try:
            from core.config import get_config
            output_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
        except ImportError:
            output_dir = Path('data/downloads')

        # 确保路径是绝对路径
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _get_temp_dir(self) -> Path:
        """获取临时目录并记录配置来源"""
        try:
            # 检查数据库设置
            from core.database import get_database
            db = get_database()
            db_value = db.get_setting('downloader.temp_dir')
            if db_value is not None:
                temp_dir = Path(db_value)
                logger.debug(f"🔧 YouTube策略临时目录: {temp_dir} (来源: 数据库)")
            else:
                # 检查配置文件
                from core.config import get_config
                config_value = get_config('downloader.temp_dir', None)
                if config_value is not None:
                    temp_dir = Path(config_value)
                    logger.debug(f"🔧 YouTube策略临时目录: {temp_dir} (来源: 配置文件)")
                else:
                    temp_dir = Path('data/temp')
                    logger.debug(f"🔧 YouTube策略临时目录: {temp_dir} (来源: 默认值)")
        except ImportError:
            temp_dir = Path('data/temp')
            logger.debug(f"🔧 YouTube策略临时目录: {temp_dir} (来源: 默认值-导入失败)")

        # 确保路径是绝对路径
        if not temp_dir.is_absolute():
            temp_dir = Path.cwd() / temp_dir

        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    def _get_smart_output_dir(self, options: Dict[str, Any]) -> Path:
        """智能选择输出目录：需要转换的使用临时目录"""
        if self._needs_audio_conversion(options):
            temp_dir = self._get_temp_dir()
            logger.info(f"🔄 需要音频转换，使用临时目录: {temp_dir}")
            return temp_dir
        else:
            output_dir = self._get_output_dir()
            logger.info(f"📁 无需转换，直接使用最终目录: {output_dir}")
            return output_dir
    
    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置 - 使用统一的代理助手"""
        from core.proxy_converter import ProxyHelper
        return ProxyHelper.get_ytdlp_proxy("YouTubeStrategies")

    def _get_ffmpeg_path(self) -> Optional[str]:
        """获取FFmpeg路径 - 使用统一工具"""
        try:
            from modules.downloader.ffmpeg_tools import get_ffmpeg_path
            return get_ffmpeg_path()
        except Exception as e:
            logger.debug(f"🔍 获取FFmpeg路径失败: {e}")
            return None

    def _get_pytubefix_proxy_config(self) -> Optional[str]:
        """获取PyTubeFix专用的代理配置 - 使用统一的代理助手"""
        from core.proxy_converter import ProxyHelper
        return ProxyHelper.get_pytubefix_proxy("YouTubeStrategies-PyTubeFix")
    
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
            # 使用统一的PO Token管理器
            from core.po_token_manager import get_po_token_config
            config = get_po_token_config("YouTubeStrategy")

            if config['po_token_available']:
                return config['po_token']

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
        if quality == '4k':
            # 4K优先，使用最佳编码
            format_selector = 'bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best'
        elif quality == 'best':
            format_selector = 'bestvideo[height<=2160]+bestaudio/bestvideo[height<=1440]+bestaudio/bestvideo[height<=1080]+bestaudio/best'
        elif quality == 'high':
            format_selector = 'bestvideo[height<=1080]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=1080]/best'
        elif quality == 'medium':
            format_selector = 'bestvideo[height<=720]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=720]/best'
        elif quality == 'low':
            format_selector = 'bestvideo[height<=480]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=480]/best'
        elif quality.isdigit():
            format_selector = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'
        else:
            # 对于未知质量参数，使用高质量的默认值
            format_selector = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'

        opts = {
            'format': format_selector,
            'writesubtitles': options.get('subtitles', False),
            'writeautomaticsub': options.get('auto_subtitles', False),
            'writethumbnail': options.get('thumbnail', False),
            'writeinfojson': options.get('info_json', False),
        }

        # 应用 yt-dlp.conf 配置文件
        try:
            from .ytdlp_config_parser import get_ytdlp_config_options
            config_file_opts = get_ytdlp_config_options()
            if config_file_opts:
                # 配置文件选项优先级较低，基础选项会覆盖它们
                merged_opts = config_file_opts.copy()
                merged_opts.update(opts)
                opts = merged_opts
                logger.debug(f"✅ YouTube策略应用yt-dlp.conf配置: {len(config_file_opts)} 个选项")
        except Exception as e:
            logger.warning(f"⚠️ 应用yt-dlp.conf配置失败: {e}")

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

        # 添加FFmpeg路径和音频兼容性修复
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            opts['ffmpeg_location'] = ffmpeg_path
            logger.debug(f"✅ 使用FFmpeg: {ffmpeg_path}")

            # 添加音频兼容性修复
            if 'postprocessors' not in opts:
                opts['postprocessors'] = []

            # 确保MP4音频兼容性
            opts['postprocessors'].extend([
                {
                    'key': 'FFmpegFixupM4a',  # 修复M4A音频兼容性问题
                },
                {
                    'key': 'FFmpegVideoConvertor',  # 确保视频格式兼容性
                    'preferedformat': 'mp4',
                }
            ])

            # 音频编码优化 - 确保使用兼容的AAC编码
            opts['postprocessor_args'] = {
                'ffmpeg': ['-c:a', 'aac', '-avoid_negative_ts', 'make_zero']
            }

            logger.debug("✅ 添加MP4音频兼容性修复")
        else:
            logger.warning("⚠️ 未找到FFmpeg，高质量合并和音频修复可能失败")

        return opts
    
    def _get_high_quality_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """高质量下载选项"""
        opts = self._get_default_opts(download_id, url, options)

        # 检查FFmpeg是否可用
        ffmpeg_path = self._get_ffmpeg_path()
        if ffmpeg_path:
            # FFmpeg可用，使用高质量合并格式，确保音频兼容性
            opts.update({
                'format': 'bestvideo[height<=2160]+bestaudio[acodec^=mp4a]/bestvideo[height<=2160]+bestaudio/best[height<=2160]/best',
                'merge_output_format': 'mp4',
                'writesubtitles': True,
                'writethumbnail': True,
                # 确保音频编码兼容性
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }, {
                    'key': 'FFmpegFixupM4a',  # 修复M4A音频兼容性
                }],
                # 强制使用兼容的音频编码
                'postprocessor_args': {
                    'ffmpeg': ['-c:a', 'aac', '-b:a', '128k']  # 强制使用AAC音频编码
                }
            })
            logger.info("✅ 使用FFmpeg进行高质量合并（兼容音频编码）")
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

    def _get_audio_only_opts(self, download_id: str, url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """仅音频下载选项"""
        opts = self._get_default_opts(download_id, url, options)

        # 检查是否指定了音频格式
        quality = options.get('quality', 'audio_mp3_medium')

        if quality.startswith('audio_'):
            # 解析音频格式和质量
            parts = quality.split('_')
            if len(parts) >= 3:
                audio_format = parts[1]  # mp3, aac, flac
                audio_quality = parts[2]  # high, medium, low

                # 设置音频格式选择器
                if audio_format == 'flac':
                    format_selector = 'bestaudio[ext=flac]/bestaudio'
                elif audio_format == 'aac':
                    format_selector = 'bestaudio[ext=m4a]/bestaudio[ext=aac]/bestaudio'
                elif audio_format == 'ogg':
                    format_selector = 'bestaudio[ext=ogg]/bestaudio'
                else:  # mp3 或其他
                    format_selector = 'bestaudio[ext=mp3]/bestaudio'

                # 只下载音频，不进行转换（后续用FFmpeg处理）
                opts.update({
                    'format': format_selector,
                    'merge_output_format': None,  # 禁用合并为MP4
                    'writesubtitles': False,      # 禁用字幕下载
                    'writeautomaticsub': False,   # 禁用自动字幕
                })
            else:
                # 默认音频设置 - 只下载音频，不转换
                opts.update({
                    'format': 'bestaudio/best',
                    'merge_output_format': None,  # 禁用合并为MP4
                    'writesubtitles': False,      # 禁用字幕下载
                    'writeautomaticsub': False,   # 禁用自动字幕
                })
        else:
            # 传统的仅音频下载 - 只下载音频，不转换
            opts.update({
                'format': 'bestaudio/best',
                'merge_output_format': None,  # 禁用合并为MP4
                'writesubtitles': False,      # 禁用字幕下载
                'writeautomaticsub': False,   # 禁用自动字幕
            })

        # 添加代理
        proxy = self._get_proxy_config()
        if proxy:
            opts['proxy'] = proxy

        return opts

    def _get_audio_bitrate(self, format: str, quality: str) -> str:
        """获取音频比特率"""
        bitrate_map = {
            'mp3': {
                'high': '320',
                'medium': '192',
                'low': '128'
            },
            'aac': {
                'high': '256',
                'medium': '128',
                'low': '96'
            },
            'flac': {
                'lossless': '0'  # FLAC 无损
            },
            'ogg': {
                'high': '6',
                'medium': '4',
                'low': '2'
            }
        }

        return bitrate_map.get(format, {}).get(quality, '192')

    def _is_audio_only_request(self, options: Dict[str, Any]) -> bool:
        """判断是否为仅音频下载请求"""
        quality = options.get('quality', '')
        audio_only = options.get('audio_only', False)

        # 检查是否明确指定了仅音频
        if audio_only:
            return True

        # 检查质量参数是否包含音频标识
        if isinstance(quality, str) and quality.startswith('audio_'):
            return True

        return False

    def _needs_audio_conversion(self, options: Dict[str, Any]) -> bool:
        """判断是否需要音频转换"""
        quality = options.get('quality', 'best')
        audio_only = options.get('audio_only', False)
        return audio_only or quality.startswith('audio_')

    def _convert_to_audio(self, input_path: str, options: Dict[str, Any]) -> Optional[str]:
        """转换为音频格式"""
        try:
            quality = options.get('quality', 'best')

            # 解析音频格式和质量
            if quality.startswith('audio_'):
                parts = quality.split('_')
                if len(parts) >= 3:
                    audio_format = parts[1]  # mp3, aac, flac
                    audio_quality = parts[2]  # high, medium, low
                else:
                    audio_format = 'mp3'
                    audio_quality = 'medium'
            else:
                # 默认音频格式
                audio_format = 'mp3'
                audio_quality = 'medium'

            input_file = Path(input_path)

            # 检查输入文件是否已经是目标格式
            current_extension = input_file.suffix.lower().lstrip('.')
            target_extension = audio_format.lower()

            # 判断是否需要实际转换
            if current_extension == target_extension:
                logger.info(f"✅ 文件已经是目标格式 {audio_format.upper()}，无需转换: {input_file.name}")
                # 如果文件在临时目录，需要移动到最终目录
                temp_dir = self._get_temp_dir()
                if str(input_file.parent) == str(temp_dir):
                    final_dir = self._get_output_dir()
                    final_path = final_dir / input_file.name
                    try:
                        input_file.rename(final_path)
                        logger.info(f"📁 文件已移动到最终目录: {final_path.name}")
                        return str(final_path)
                    except Exception as e:
                        logger.error(f"❌ 移动文件失败: {e}")
                        return input_path
                else:
                    return input_path

            # 需要转换：在临时目录进行转换，然后移动到最终目录
            temp_output_path = str(input_file.parent / f"{input_file.stem}.{audio_format}")

            # 双重检查：如果路径相同，添加后缀避免冲突
            if temp_output_path == input_path:
                temp_output_path = str(input_file.parent / f"{input_file.stem}_converted.{audio_format}")
                logger.warning(f"⚠️ 输入输出路径相同，使用临时文件名: {Path(temp_output_path).name}")

            # 使用FFmpeg工具转换
            from modules.downloader.ffmpeg_tools import FFmpegTools
            ffmpeg_tools = FFmpegTools()

            logger.info(f"🔄 开始音频转换: {input_file.name} -> {Path(temp_output_path).name}")
            success = ffmpeg_tools.extract_audio(
                input_path=input_path,
                output_path=temp_output_path,
                format=audio_format,
                quality=audio_quality
            )

            if success and Path(temp_output_path).exists():
                logger.info(f"✅ 音频转换成功: {audio_format} ({audio_quality})")

                # 移动转换后的文件到最终目录
                temp_file = Path(temp_output_path)
                final_dir = self._get_output_dir()
                final_path = final_dir / temp_file.name

                try:
                    # 检查目标文件是否已经存在，如果存在则删除
                    if final_path.exists():
                        logger.warning(f"⚠️ 目标文件已存在，将覆盖: {final_path.name}")
                        final_path.unlink()

                    # 使用shutil.move代替rename，更可靠
                    import shutil
                    shutil.move(str(temp_file), str(final_path))
                    logger.info(f"📁 转换后文件已移动到最终目录: {final_path.name}")

                    # 验证文件移动成功
                    if final_path.exists():
                        file_size = final_path.stat().st_size
                        logger.info(f"✅ 文件移动验证成功: {final_path.name} ({file_size} 字节)")
                    else:
                        logger.error(f"❌ 文件移动验证失败: {final_path.name}")
                        return None

                    # 清理原始文件
                    try:
                        if Path(input_path).exists():
                            Path(input_path).unlink()
                            logger.debug(f"🗑️ 清理原始文件: {Path(input_path).name}")
                    except:
                        pass

                    return str(final_path)
                except Exception as e:
                    logger.error(f"❌ 移动转换后文件失败: {e}")
                    logger.error(f"❌ 源文件: {temp_file}")
                    logger.error(f"❌ 目标文件: {final_path}")
                    return temp_output_path
            else:
                logger.error(f"❌ 音频转换失败")
                return None

        except Exception as e:
            logger.error(f"❌ 音频转换异常: {e}")
            return None

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
