# -*- coding: utf-8 -*-
"""
下载管理器 V2 - 模块化重构版

使用模块化架构，提高代码可维护性和可扩展性
"""

import os
import uuid
import logging
import threading
import hashlib
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, unquote

# 预导入常用模块，避免重复导入
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    yt_dlp = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

# 导入模块化组件
from .retry_manager import RetryManager
from .ffmpeg_tools import FFmpegTools
from .filename_processor import FilenameProcessor
from .youtube_strategies import YouTubeStrategies
from .video_extractor import VideoExtractor

logger = logging.getLogger(__name__)


def safe_execute(default_return=None, log_error=True):
    """统一的错误处理装饰器，减少重复的try-except代码"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"❌ {func.__name__} 执行失败: {e}")
                return default_return
        return wrapper
    return decorator


class URLUtils:
    """URL处理工具类，避免重复的URL操作逻辑"""

    @staticmethod
    def extract_filename_from_url(url: str) -> Optional[str]:
        """从URL中提取真实的文件名"""
        # 尝试从URL参数中提取文件名
        if 'file=' in url:
            # 提取file参数
            match = re.search(r'file=([^&]+)', url)
            if match:
                file_param = unquote(match.group(1))
                # 提取文件名部分
                filename = file_param.split('/')[-1]
                if filename and '.' in filename:
                    logger.info(f"🔍 从URL参数提取文件名: {filename}")
                    return filename
        return None

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """生成URL哈希，用于续传功能"""
        try:
            # 标准化URL（移除查询参数中的时间戳等）
            from urllib.parse import parse_qs, urlencode, urlunparse
            parsed = urlparse(url)

            # 对于某些平台，移除时间戳参数
            if parsed.query:
                query_params = parse_qs(parsed.query)
                # 移除常见的时间戳参数
                timestamp_params = ['t', 'timestamp', '_t', 'time', 'ts']
                for param in timestamp_params:
                    query_params.pop(param, None)

                # 重建查询字符串
                clean_query = urlencode(query_params, doseq=True)
                parsed = parsed._replace(query=clean_query)

            clean_url = urlunparse(parsed)
            return hashlib.md5(clean_url.encode('utf-8')).hexdigest()[:12]
        except Exception as e:
            logger.warning(f"⚠️ 生成URL哈希失败，使用原URL: {e}")
            return hashlib.md5(url.encode('utf-8')).hexdigest()[:12]

    @staticmethod
    def should_fix_extension(url: str) -> bool:
        """判断是否需要修复扩展名"""
        # 检查URL是否包含可能导致扩展名问题的模式
        problematic_patterns = [
            'remote_control.php',
            '.php?',
            'file=%2F',  # URL编码的文件路径
        ]

        for pattern in problematic_patterns:
            if pattern in url:
                # 进一步检查是否实际指向视频文件
                if any(video_ext in url for video_ext in ['.mp4', '.avi', '.mkv', '.mov', '.flv']):
                    logger.info(f"🔧 检测到需要修复扩展名的URL: {pattern}")
                    return True

        return False


# 常量定义
class DownloadConstants:
    """下载相关常量"""

    # YouTube 域名列表
    YOUTUBE_DOMAINS = [
        'youtube.com',
        'youtu.be',
        'www.youtube.com',
        'm.youtube.com',
        'music.youtube.com',
        'youtube-nocookie.com'
    ]

    # 进度日志间隔（百分比）
    PROGRESS_LOG_INTERVAL = 10

    # 默认重试次数
    DEFAULT_RETRIES = 5
    DEFAULT_FRAGMENT_RETRIES = 10


class ConfigManager:
    """统一的配置管理器，缓存配置函数避免重复导入"""

    _config_func = None
    _database_func = None
    _proxy_helper = None

    @classmethod
    def get_config_func(cls):
        """获取配置函数（缓存）"""
        if cls._config_func is None:
            def fallback_get_config(key, default=None):
                return os.getenv(key.upper().replace('.', '_'), default)

            try:
                from core.config import get_config
                cls._config_func = get_config
            except ImportError:
                try:
                    from app.core.config import get_config
                    cls._config_func = get_config
                except ImportError:
                    cls._config_func = fallback_get_config
                    logger.warning("⚠️ 使用环境变量作为配置源")

        return cls._config_func

    @classmethod
    def get_database_func(cls):
        """获取数据库函数（缓存）"""
        if cls._database_func is None:
            try:
                from core.database import get_database
                cls._database_func = get_database
            except ImportError:
                try:
                    from app.core.database import get_database
                    cls._database_func = get_database
                except ImportError:
                    logger.warning("⚠️ 无法导入数据库模块")
                    cls._database_func = None

        return cls._database_func

    @classmethod
    def get_proxy_config(cls) -> Optional[str]:
        """获取代理配置（缓存）"""
        if cls._proxy_helper is None:
            try:
                from core.proxy_converter import ProxyHelper
                cls._proxy_helper = ProxyHelper
            except ImportError:
                logger.warning("⚠️ 无法导入代理助手")
                return None

        return cls._proxy_helper.get_ytdlp_proxy("DownloadManager") if cls._proxy_helper else None


class DownloadManagerV2:
    """下载管理器 V2 - 模块化版本"""
    
    def __init__(self):
        self.downloads: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.executor = None

        # 性能统计
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'cancelled_downloads': 0,
            'total_bytes_downloaded': 0,
            'start_time': datetime.now()
        }

        # 初始化模块化组件
        self._initialize_components()
        self._initialize()
    
    def _initialize_components(self):
        """初始化模块化组件"""
        try:
            self.retry_manager = RetryManager()
            self.ffmpeg_tools = FFmpegTools()
            self.filename_processor = FilenameProcessor()
            self.youtube_strategies = YouTubeStrategies()
            self.video_extractor = VideoExtractor()
            
            logger.info("✅ 模块化组件初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 模块化组件初始化失败: {e}")
            raise
    
    def _get_config_with_log(self, get_config_func, key: str, default, config_type: str = "下载管理器"):
        """获取配置并记录来源"""
        try:
            # 检查数据库设置
            from core.database import get_database
            db = get_database()
            db_value = db.get_setting(key)
            if db_value is not None:
                logger.info(f"🔧 {config_type}配置: {key} = {db_value} (来源: 数据库)")
                return db_value

            # 检查配置文件
            config_value = get_config_func(key, None)
            if config_value is not None and config_value != default:
                logger.info(f"🔧 {config_type}配置: {key} = {config_value} (来源: 配置文件)")
                return config_value

            # 使用默认值
            logger.info(f"🔧 {config_type}配置: {key} = {default} (来源: 默认值)")
            return default

        except Exception as e:
            logger.warning(f"⚠️ {config_type}配置获取失败 {key}: {e}")
            return get_config_func(key, default)

    def _initialize(self):
        """初始化下载管理器"""
        try:
            # 使用统一的配置管理器
            get_config = ConfigManager.get_config_func()

            # 获取并验证配置（带日志记录）
            max_concurrent_raw = self._get_config_with_log(get_config, 'downloader.max_concurrent', 3)
            output_dir_raw = self._get_config_with_log(get_config, 'downloader.output_dir', '/app/downloads')
            temp_dir_raw = self._get_config_with_log(get_config, 'downloader.temp_dir', '/app/temp')

            self.max_concurrent = self._validate_config_int(max_concurrent_raw, 'max_concurrent', 1, 10)
            self.output_dir = self._validate_config_path(output_dir_raw, 'output_dir')
            self.temp_dir = self._validate_config_path(temp_dir_raw, 'temp_dir')

            # 创建目录
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # 清理遗留任务
            self._cleanup_orphaned_downloads()

            # 创建线程池
            self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent)

            # 启动自动清理
            self._start_cleanup()

            logger.info(f"✅ 下载管理器V2初始化完成 - 最大并发: {self.max_concurrent}")
            logger.info(f"🔧 FFmpeg状态: {'可用' if self.ffmpeg_tools.is_available() else '不可用'}")
            logger.info(f"📋 可用提取器: {len(self.video_extractor.get_available_extractors())} 个")
            logger.info(f"🎯 YouTube策略: {len(self.youtube_strategies.get_strategy_list())} 个")

        except Exception as e:
            logger.error(f"❌ 下载管理器V2初始化失败: {e}")
            raise
    
    def _cleanup_orphaned_downloads(self):
        """清理遗留的下载任务"""
        try:
            # 使用统一的配置管理器
            get_database = ConfigManager.get_database_func()
            if not get_database:
                logger.warning("⚠️ 无法导入数据库模块，跳过清理遗留任务")
                return

            db = get_database()
            orphaned_downloads = db.execute_query('''
                SELECT id, url FROM downloads
                WHERE status IN ('pending', 'downloading')
            ''')

            if orphaned_downloads:
                logger.info(f"🧹 发现 {len(orphaned_downloads)} 个遗留下载任务，正在清理...")
                
                for download in orphaned_downloads:
                    db.execute_update('''
                        UPDATE downloads
                        SET status = 'failed',
                            error_message = '应用重启，任务已取消',
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (download['id'],))
                
                logger.info(f"✅ 已清理 {len(orphaned_downloads)} 个遗留下载任务")

        except Exception as e:
            logger.error(f"❌ 清理遗留下载任务失败: {e}")
    
    def _start_cleanup(self):
        """启动自动清理"""
        try:
            from .cleanup import get_cleanup_manager
            cleanup_manager = get_cleanup_manager()
            cleanup_manager.start()
        except Exception as e:
            logger.warning(f"⚠️ 启动自动清理失败: {e}")
    
    def create_download(self, url: str, options: Dict[str, Any] = None) -> str:
        """创建下载任务"""
        try:
            download_id = str(uuid.uuid4())

            # 检查是否有相同URL的未完成下载，支持续传
            existing_download = self._find_resumable_download(url)
            if existing_download:
                if existing_download.get('resumable'):
                    # 有部分文件，创建新任务但使用续传
                    logger.info(f"🔄 发现部分下载文件，将续传: {url}")
                elif existing_download.get('from_database'):
                    # 数据库中的失败任务，复用ID
                    reused_id = existing_download['id']
                    logger.info(f"🔄 复用数据库中的失败任务: {reused_id}")

                    # 重新创建内存中的下载记录
                    initial_title = None
                    if options and options.get('custom_filename'):
                        initial_title = options['custom_filename']

                    download_info = {
                        'id': reused_id,
                        'url': url,
                        'status': 'pending',
                        'progress': 0,
                        'title': initial_title,
                        'file_path': None,
                        'file_size': None,
                        'error_message': None,
                        'created_at': datetime.now(),
                        'completed_at': None,
                        'options': options or {},
                        'url_hash': URLUtils.generate_url_hash(url)
                    }

                    with self.lock:
                        self.downloads[reused_id] = download_info

                    # 🔧 重要：清理重试数据，重新开始重试计数
                    logger.info(f"🧹 清理数据库复用任务的重试数据: {reused_id}")
                    self.retry_manager.clear_retry_data(reused_id)

                    # 🔧 重要：重新提交执行任务
                    logger.info(f"🚀 重新提交数据库失败任务执行: {reused_id}")
                    self.executor.submit(self._execute_download, reused_id)

                    return reused_id
                else:
                    # 内存中的失败任务，不复用，创建新任务
                    logger.info(f"🆕 内存中存在失败任务，但创建新任务: {existing_download['id']}")
                    # 继续执行后面的新任务创建逻辑

            # 创建下载记录
            # 如果有自定义文件名，优先使用作为显示标题
            initial_title = None
            if options and options.get('custom_filename'):
                initial_title = options['custom_filename']
                logger.info(f"🎯 使用自定义文件名作为初始标题: {initial_title}")

            download_info = {
                'id': download_id,
                'url': url,
                'status': 'pending',
                'progress': 0,
                'title': initial_title,
                'file_path': None,
                'file_size': None,
                'error_message': None,
                'created_at': datetime.now(),
                'completed_at': None,
                'options': options or {},
                'url_hash': URLUtils.generate_url_hash(url)  # 添加URL哈希用于续传
            }

            with self.lock:
                self.downloads[download_id] = download_info

            # 保存到数据库
            self._save_to_database(download_id, url)

            # 更新统计
            self._update_stats('download_started')

            # 发送事件
            self._emit_event('DOWNLOAD_STARTED', {
                'download_id': download_id,
                'url': url,
                'title': initial_title,
                'options': options
            })

            # 提交下载任务
            self.executor.submit(self._execute_download, download_id)

            logger.info(f"📥 创建下载任务: {download_id} - {url}")
            return download_id

        except Exception as e:
            logger.error(f"❌ 创建下载任务失败: {e}")
            raise



    def _find_resumable_download(self, url: str) -> Optional[Dict[str, Any]]:
        """查找可续传的下载任务"""
        try:
            url_hash = URLUtils.generate_url_hash(url)

            # 1. 检查是否有部分下载的文件
            url_hash_files = self._find_partial_files(url_hash)
            if url_hash_files:
                logger.info(f"🔍 找到部分下载文件: {[f.name for f in url_hash_files]}")
                # 创建一个虚拟的下载信息用于续传
                return {
                    'url': url,
                    'url_hash': url_hash,
                    'partial_files': url_hash_files,
                    'resumable': True
                }

            # 2. 检查数据库中的失败任务（如果可用）
            try:
                get_database = ConfigManager.get_database_func()
                if get_database:
                    db = get_database()
                    cursor = db.execute(
                        "SELECT id, url, status FROM downloads WHERE url = ? AND status IN ('failed', 'cancelled') ORDER BY created_at DESC LIMIT 1",
                        (url,)
                    )
                    row = cursor.fetchone()
                    if row:
                        logger.info(f"🔍 找到数据库中的可续传任务: {row[0]}")
                        return {
                            'id': row[0],
                            'url': row[1],
                            'status': row[2],
                            'from_database': True
                        }
            except Exception as e:
                logger.debug(f"数据库查询失败: {e}")

            return None

        except Exception as e:
            logger.error(f"❌ 查找续传任务失败: {e}")
            return None

    def add_download(self, url: str, options: Dict[str, Any] = None) -> str:
        """添加下载任务（向后兼容别名）"""
        return self.create_download(url, options)
    
    def get_download(self, download_id: str) -> Optional[Dict[str, Any]]:
        """获取下载信息"""
        with self.lock:
            return self.downloads.get(download_id)

    def get_download_status(self, download_id: str) -> Optional[Dict[str, Any]]:
        """获取下载状态（向后兼容别名）"""
        return self.get_download(download_id)
    
    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """获取所有下载（包括内存中的和数据库中的历史记录）"""
        try:
            # 获取内存中的下载记录
            with self.lock:
                memory_downloads = list(self.downloads.values())

            # 获取数据库中的历史记录
            database_downloads = self._load_from_database()

            # 合并记录，避免重复
            all_downloads = {}

            # 先添加数据库记录
            for download in database_downloads:
                all_downloads[download['id']] = download

            # 再添加内存记录（会覆盖数据库中的同ID记录，确保最新状态）
            for download in memory_downloads:
                all_downloads[download['id']] = download

            # 转换为列表并按创建时间排序
            result = list(all_downloads.values())

            # 安全的排序函数，处理datetime和字符串混合的情况
            def safe_sort_key(download):
                created_at = download.get('created_at')
                if not created_at:
                    return ''

                # 如果是datetime对象，转换为字符串
                if hasattr(created_at, 'isoformat'):
                    return created_at.isoformat()

                # 如果已经是字符串，直接返回
                return str(created_at)

            result.sort(key=safe_sort_key, reverse=True)

            logger.debug(f"📋 返回下载记录: 内存 {len(memory_downloads)} 条, 数据库 {len(database_downloads)} 条, 合并后 {len(result)} 条")
            return result

        except Exception as e:
            logger.error(f"❌ 获取所有下载记录失败: {e}")
            # 如果出错，至少返回内存中的记录
            with self.lock:
                return list(self.downloads.values())
    
    def cancel_download(self, download_id: str) -> bool:
        """取消下载"""
        try:
            with self.lock:
                download_info = self.downloads.get(download_id)
                if not download_info:
                    return False
                
                if download_info['status'] in ['completed', 'failed', 'cancelled']:
                    return False
                
                download_info['status'] = 'cancelled'
                download_info['error_message'] = '用户取消'
            
            # 更新数据库
            self._update_database_status(download_id, 'cancelled', error_message='用户取消')
            
            # 清理重试数据
            self.retry_manager.clear_retry_data(download_id)
            
            logger.info(f"🚫 取消下载: {download_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 取消下载失败: {e}")
            return False

    def _load_from_database(self) -> List[Dict[str, Any]]:
        """从数据库加载历史下载记录"""
        try:
            get_database = ConfigManager.get_database_func()
            if not get_database:
                logger.debug("数据库模块不可用，返回空列表")
                return []

            db = get_database()

            # 获取数据库中的下载记录
            records = db.get_download_records(limit=100)  # 限制返回最近100条记录

            downloads = []
            for record in records:
                # 转换数据库记录为下载管理器格式
                download_info = {
                    'id': record['id'],
                    'url': record['url'],
                    'title': record['title'],
                    'status': record['status'],
                    'progress': record['progress'] or 0,
                    'file_path': record['file_path'],
                    'file_size': record['file_size'],
                    'error_message': record['error_message'],
                    'created_at': record['created_at'],
                    'completed_at': record['completed_at'],
                    'options': {}  # 数据库中没有存储options
                }
                downloads.append(download_info)

            logger.debug(f"📋 从数据库加载了 {len(downloads)} 条历史记录")
            return downloads

        except Exception as e:
            logger.warning(f"⚠️ 从数据库加载历史记录失败: {e}")
            return []

    def _execute_download(self, download_id: str):
        """执行下载任务"""
        try:
            with self.lock:
                download_info = self.downloads.get(download_id)
                if not download_info:
                    return

                url = download_info['url']
                options = download_info['options']

            logger.info(f"🔄 开始执行下载: {download_id} - {url}")

            # 🔧 重置进度记录，防止上次下载的进度影响
            from core.file_utils import ProgressUtils
            ProgressUtils.reset_progress(download_id)

            # 检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消: {download_id}")
                return

            # 更新状态为下载中
            self._update_download_status(download_id, 'downloading', 0)

            # 提取视频信息
            video_info = self.video_extractor.extract_info(url, options)

            # 再次检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（提取信息后）: {download_id}")
                return

            if not video_info or video_info.get('error'):
                error_msg = video_info.get('message', '无法获取视频信息') if video_info else '无法获取视频信息'
                self._handle_download_failure(download_id, error_msg)
                return

            # 更新标题 - 优先保留自定义文件名
            title = video_info.get('title', 'Unknown')
            with self.lock:
                current_title = self.downloads[download_id].get('title')
                # 如果已经有自定义标题（来自自定义文件名），不要覆盖它
                if not current_title:
                    self.downloads[download_id]['title'] = title
                    logger.info(f"📝 设置视频标题: {title}")
                else:
                    logger.info(f"📝 保留自定义标题: {current_title} (原始标题: {title})")
                    title = current_title  # 使用自定义标题作为后续处理的标题

            # 检测并记录文件大小信息（仅提供信息，不限制下载）
            self._detect_and_log_file_size(video_info, title)

            # 最后一次检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（开始下载前）: {download_id}")
                return

            # 执行下载
            file_path = self._download_video(download_id, url, video_info, options)

            if file_path and Path(file_path).exists():
                # 🔧 修复：检查是否是YouTube平台，避免重复音频转换
                is_youtube = 'youtube.com' in url or 'youtu.be' in url

                if is_youtube:
                    # YouTube策略已经处理了音频转换，下载管理器不需要重复处理
                    logger.info(f"✅ YouTube文件已经是目标格式 {Path(file_path).suffix.upper().lstrip('.')}，无需转换: {Path(file_path).name}")
                else:
                    # 其他平台需要下载管理器的音频转换逻辑
                    if self._needs_audio_conversion(options):
                        converted_path = self._convert_to_audio(file_path, options)
                        if converted_path:
                            # 删除原始文件
                            try:
                                Path(file_path).unlink()
                            except:
                                pass
                            file_path = converted_path

                # 应用智能文件名
                if options.get('smart_filename', True):
                    final_path = self._apply_smart_filename(file_path, video_info, options)
                    if final_path:
                        file_path = final_path
                        logger.info(f"✅ 智能文件名应用成功: {Path(file_path).name}")

                        # 更新显示标题为自定义文件名（如果使用了自定义文件名）
                        if options.get('custom_filename'):
                            display_title = options['custom_filename']
                            with self.lock:
                                if download_id in self.downloads:
                                    self.downloads[download_id]['title'] = display_title
                            logger.info(f"✅ 更新显示标题为自定义文件名: {display_title}")

                            # 发送标题更新事件给前端
                            self._emit_event('DOWNLOAD_TITLE_UPDATED', {
                                'download_id': download_id,
                                'title': display_title
                            })
                    else:
                        # 如果智能重命名失败，记录警告但继续使用当前路径
                        logger.warning(f"⚠️ 智能文件名应用失败，保持原文件名: {Path(file_path).name}")

                # 确保文件存在并获取最终信息（延迟检查以避免文件系统延迟）
                final_file_path = Path(file_path)

                # 简化的延迟检查机制：给文件系统一些时间完成操作
                max_check_attempts = 3  # 减少到3次
                check_delay = 0.5  # 固定0.5秒延迟

                for attempt in range(max_check_attempts):
                    # 每次检查前都先等待，给重命名操作时间完成
                    if attempt == 0:
                        logger.info(f"🔍 等待{check_delay}秒后开始文件检查...")
                    else:
                        logger.info(f"🔍 文件检查第{attempt}次未找到，等待{check_delay}秒后重试...")

                    time.sleep(check_delay)

                    if final_file_path.exists():
                        if attempt == 0:
                            logger.info(f"✅ 文件检查成功")
                        else:
                            logger.info(f"✅ 文件检查成功，第{attempt + 1}次尝试后找到文件")
                        break

                    # 如果是最后一次尝试失败
                    if attempt == max_check_attempts - 1:
                        # 最后一次尝试失败，记录详细信息
                        logger.error(f"❌ 最终文件不存在: {file_path}")
                        logger.error(f"❌ 检查路径: {final_file_path.absolute()}")
                        logger.error(f"❌ 父目录存在: {final_file_path.parent.exists()}")
                        if final_file_path.parent.exists():
                            logger.error(f"❌ 父目录内容: {list(final_file_path.parent.glob('*'))}")
                        self._handle_download_failure(download_id, '最终文件不存在')
                        return

                file_size = final_file_path.stat().st_size
                logger.info(f"📁 最终文件: {final_file_path.name} ({file_size / (1024*1024):.1f}MB)")

                # 下载和后处理完全完成，发送完成事件
                self._update_download_status(download_id, 'completed', 100,
                                           file_path=str(final_file_path), file_size=file_size)

                # 清理重试数据
                self.retry_manager.clear_retry_data(download_id)

                logger.info(f"✅ 下载完成: {download_id} - {title}")
            else:
                self._handle_download_failure(download_id, '下载文件不存在')

        except Exception as e:
            logger.error(f"❌ 下载执行失败 {download_id}: {e}")
            self._handle_download_failure(download_id, str(e))

    def _is_cancelled(self, download_id: str) -> bool:
        """检查下载是否已被取消"""
        try:
            with self.lock:
                download_info = self.downloads.get(download_id)
                if not download_info:
                    return True  # 如果记录不存在，视为已取消
                return download_info.get('status') == 'cancelled'
        except Exception as e:
            logger.error(f"❌ 检查取消状态失败: {e}")
            return False

    def _detect_and_log_file_size(self, video_info: Dict[str, Any], title: str):
        """检测并记录文件大小信息（仅提供信息，不限制下载）"""
        try:
            # 尝试获取文件大小信息
            filesize = video_info.get('filesize')
            filesize_approx = video_info.get('filesize_approx')
            duration = video_info.get('duration')

            # 确定最佳的大小估算
            estimated_size = None
            size_source = "未知"

            if filesize and filesize > 0:
                estimated_size = filesize
                size_source = "精确"
            elif filesize_approx and filesize_approx > 0:
                estimated_size = filesize_approx
                size_source = "估算"

            if estimated_size:
                # 使用统一的文件大小格式化工具
                try:
                    from core.file_utils import FileUtils
                    size_str = FileUtils.format_file_size(estimated_size)
                except ImportError:
                    # 备用格式化方案
                    size_mb = estimated_size / (1024 * 1024)
                    size_gb = size_mb / 1024
                    if size_gb >= 1:
                        size_str = f"{size_gb:.2f} GB"
                    else:
                        size_str = f"{size_mb:.1f} MB"

                # 记录文件大小信息
                logger.info(f"📊 文件大小检测: {title}")
                logger.info(f"   📏 预估大小: {size_str} ({size_source})")

                # 提供下载时间估算（基于常见网速）
                if duration:
                    duration_str = f"{duration // 60}:{duration % 60:02d}"
                    logger.info(f"   ⏱️ 视频时长: {duration_str}")

                # 根据文件大小提供友好提示
                size_mb = estimated_size / (1024 * 1024)
                if size_mb >= 5120:  # 5GB
                    logger.warning(f"⚠️ 大文件提醒: 文件较大 ({size_str})，请确保有足够的存储空间和网络带宽")
                elif size_mb >= 2048:  # 2GB
                    logger.info(f"ℹ️ 文件提醒: 中等大小文件 ({size_str})，预计需要一些时间下载")
                elif size_mb >= 100:
                    logger.info(f"ℹ️ 文件提醒: 标准大小文件 ({size_str})")

                # 检查可用磁盘空间
                self._check_available_disk_space(estimated_size, size_str)

            else:
                logger.info(f"📊 文件大小检测: {title}")
                logger.info(f"   📏 预估大小: 无法获取大小信息")
                if duration:
                    duration_str = f"{duration // 60}:{duration % 60:02d}"
                    logger.info(f"   ⏱️ 视频时长: {duration_str}")

        except Exception as e:
            logger.debug(f"文件大小检测失败: {e}")

    def _check_available_disk_space(self, estimated_size: int, size_str: str):
        """检查可用磁盘空间"""
        try:
            import shutil

            # 获取下载目录的磁盘使用情况
            total, used, free = shutil.disk_usage(str(self.output_dir))

            # 使用统一的文件大小格式化工具
            try:
                from core.file_utils import FileUtils
                free_str = FileUtils.format_file_size(free)
            except ImportError:
                # 备用格式化方案
                free_gb = free / (1024**3)
                free_str = f"{free_gb:.2f} GB"

            logger.info(f"   💾 可用空间: {free_str}")

            # 检查空间是否足够（预留20%缓冲）
            required_space = estimated_size * 1.2  # 预留20%空间

            if free < required_space:
                logger.warning(f"⚠️ 磁盘空间警告: 可用空间可能不足")
                logger.warning(f"   需要: {size_str} (+ 20%缓冲)")
                logger.warning(f"   可用: {free_str}")
            elif free < estimated_size * 2:  # 如果可用空间少于文件大小的2倍
                logger.info(f"ℹ️ 磁盘空间提醒: 建议清理一些旧文件以释放更多空间")

        except Exception as e:
            logger.debug(f"磁盘空间检查失败: {e}")

    def _handle_download_failure(self, download_id: str, error_msg: str):
        """处理下载失败 - 统一使用RetryManager"""
        try:
            # 使用重试管理器判断是否重试
            should_retry = self.retry_manager.should_retry(download_id, error_msg)

            if should_retry:
                # 安排重试
                self.retry_manager.schedule_retry(download_id, self._execute_download)

                # 获取重试信息用于状态显示
                retry_info = self.retry_manager.get_retry_info(download_id)
                if retry_info:
                    retry_count = retry_info.get('retry_count', 0)
                    max_retries = self.retry_manager.retry_config.get('max_retries', 3)
                    self._update_download_status(download_id, 'retrying',
                                               error_message=f"重试中 ({retry_count}/{max_retries}): {error_msg}")
                else:
                    self._update_download_status(download_id, 'retrying', error_message=f"准备重试: {error_msg}")
            else:
                # 标记为最终失败
                self._update_download_status(download_id, 'failed', error_message=error_msg)

                # 发送失败事件
                self._emit_event('DOWNLOAD_FAILED', {
                    'download_id': download_id,
                    'error': error_msg
                })

                logger.error(f"❌ 下载最终失败: {download_id} - {error_msg}")

        except Exception as e:
            logger.error(f"❌ 处理下载失败时出错: {e}")
            self._update_download_status(download_id, 'failed', error_message=f"处理失败: {str(e)}")
    
    def _download_video(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """下载视频"""
        try:
            # 检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（开始下载视频）: {download_id}")
                return None

            if any(domain in url.lower() for domain in DownloadConstants.YOUTUBE_DOMAINS):
                # 使用YouTube策略
                logger.info(f"🎯 调用YouTube策略下载: {download_id}")
                return self.youtube_strategies.download(download_id, url, video_info, options)
            else:
                # 使用通用下载
                logger.info(f"🌐 使用通用下载: {download_id}")
                return self._generic_download(download_id, url, video_info, options)

        except Exception as e:
            logger.error(f"❌ 视频下载失败: {e}")
            return None
    
    def _generic_download(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """通用下载方法"""
        try:
            if not YT_DLP_AVAILABLE:
                raise ImportError("yt-dlp 模块不可用")

            # 检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（通用下载开始）: {download_id}")
                return None

            # 准备下载配置
            ydl_opts = self._prepare_download_options(url, options, download_id)

            # 执行下载
            return self._execute_generic_download(download_id, url, ydl_opts, options)

        except yt_dlp.DownloadError as e:
            if "cancelled by user" in str(e):
                logger.info(f"🚫 用户取消下载: {download_id}")
                return None
            else:
                logger.error(f"❌ yt-dlp下载失败: {e}")
                return None
        except Exception as e:
            logger.error(f"❌ 通用下载失败: {e}")
            return None

    def _prepare_download_options(self, url: str, options: Dict[str, Any], download_id: str) -> Dict[str, Any]:
        """准备下载选项配置"""
        if not YT_DLP_AVAILABLE:
            raise ImportError("yt-dlp 模块不可用")

        # 生成URL哈希用于续传
        url_hash = URLUtils.generate_url_hash(url)

        # 智能路径选择：需要转换的文件使用临时目录
        if self._needs_audio_conversion(options):
            # 需要转换，使用临时目录
            output_template = str(self.temp_dir / f'{url_hash}.%(ext)s')
            logger.info(f"🔄 需要音频转换，使用临时目录: {self.temp_dir}")
        else:
            # 不需要转换，直接使用最终目录
            output_template = str(self.output_dir / f'{url_hash}.%(ext)s')
            logger.info(f"📁 无需转换，直接下载到最终目录: {self.output_dir}")

        # 基础配置 - 优化续传支持
        ydl_opts = {
            'outtmpl': output_template,  # 智能选择输出路径
            'continue_dl': True,  # 明确启用续传
            'nooverwrites': True,  # 不覆盖已存在的文件
            'retries': DownloadConstants.DEFAULT_RETRIES,  # 增加重试次数
            'fragment_retries': DownloadConstants.DEFAULT_FRAGMENT_RETRIES,  # 分片重试次数
            'skip_unavailable_fragments': False,  # 不跳过不可用的分片
            'allow_unplayable_formats': True,  # 允许不可播放的格式
            'check_formats': False,  # 跳过格式检查，允许不常见扩展名
            'force_generic_extractor': True,  # 强制使用通用提取器
            'prefer_free_formats': False,  # 不偏好免费格式
        }

        # 应用配置文件选项
        ydl_opts = self._apply_config_file_options(ydl_opts)

        # 设置格式选择器
        ydl_opts = self._setup_format_selector(ydl_opts, url, options)

        # 添加代理配置
        proxy = self._get_proxy_config()
        if proxy:
            ydl_opts['proxy'] = proxy

        # 应用PO Token配置 (只对YouTube有效)
        from core.po_token_manager import apply_po_token_to_ytdlp
        ydl_opts = apply_po_token_to_ytdlp(ydl_opts, url, "DownloadManager")

        # 添加进度钩子
        ydl_opts['progress_hooks'] = [self._create_progress_hook(download_id)]

        # 对于有问题的URL，尝试直接下载而不是使用yt-dlp的安全检查
        if URLUtils.should_fix_extension(url):
            logger.info("🔧 检测到问题URL，将尝试直接下载方式")
            # 移除可能导致问题的选项
            ydl_opts.pop('check_formats', None)
            # 添加强制下载选项
            ydl_opts['force_json'] = False
            ydl_opts['simulate'] = False

        logger.info(f"🔄 使用续传文件名: {url_hash} (来自URL: {url[:50]}...)")

        return ydl_opts



    def _check_resume_support(self, url: str, proxies: Dict[str, str] = None) -> bool:
        """检测服务器是否支持断点续传"""
        if not REQUESTS_AVAILABLE:
            logger.warning("⚠️ requests 模块不可用，假设不支持断点续传")
            return False

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
            }

            # 方法1: 检查HEAD请求的Accept-Ranges头部
            logger.debug("🔍 检测断点续传支持 - HEAD请求")
            response = requests.head(url, headers=headers, proxies=proxies, timeout=10)

            accept_ranges = response.headers.get('Accept-Ranges', '').lower()
            if accept_ranges == 'bytes':
                logger.debug("✅ HEAD请求显示支持Range: bytes")

                # 方法2: 实际测试小范围Range请求
                logger.debug("🔍 验证Range请求 - 测试前1KB")
                test_headers = headers.copy()
                test_headers['Range'] = 'bytes=0-1023'

                test_response = requests.get(url, headers=test_headers, proxies=proxies, timeout=10)

                if test_response.status_code == 206:
                    logger.debug("✅ Range请求测试成功 - 返回206")
                    return True
                elif test_response.status_code == 200:
                    logger.debug("❌ Range请求被忽略 - 返回完整文件")
                    return False
                else:
                    logger.debug(f"⚠️ Range请求异常 - 状态码: {test_response.status_code}")
                    return False
            elif accept_ranges == 'none':
                logger.debug("❌ HEAD请求明确不支持Range")
                return False
            else:
                logger.debug("⚠️ HEAD请求未明确Range支持，尝试测试")

                # 没有明确的Accept-Ranges，直接测试Range请求
                test_headers = headers.copy()
                test_headers['Range'] = 'bytes=0-1023'

                test_response = requests.get(url, headers=test_headers, proxies=proxies, timeout=10)
                return test_response.status_code == 206

        except Exception as e:
            logger.warning(f"⚠️ 断点续传检测失败，假设不支持: {e}")
            return False

    def _apply_config_file_options(self, base_opts: Dict[str, Any]) -> Dict[str, Any]:
        """应用配置文件选项"""
        from .ytdlp_config_parser import get_ytdlp_config_options
        config_file_opts = get_ytdlp_config_options()
        if config_file_opts:
            # 配置文件选项优先级较高，基础选项作为默认值
            merged_opts = base_opts.copy()  # 基础选项作为默认值
            merged_opts.update(config_file_opts)  # 配置文件选项覆盖基础选项
            logger.debug(f"✅ 应用yt-dlp.conf配置: {len(config_file_opts)} 个选项（配置文件优先）")
            return merged_opts
        return base_opts

    def _setup_format_selector(self, ydl_opts: Dict[str, Any], url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """设置格式选择器"""
        quality = options.get('quality', 'best')
        audio_only = options.get('audio_only', False)

        # 获取代理配置（一次性获取，避免重复调用）
        proxy = self._get_proxy_config()

        # 获取平台配置（一次性获取，避免重复导入）
        from .platforms import get_platform_for_url
        platform = get_platform_for_url(url)

        if audio_only or quality.startswith('audio_'):
            # 下载最佳音频质量，后续转换
            ydl_opts['format'] = 'bestaudio/best'
            logger.info(f"🎵 音频下载模式: bestaudio/best")
        else:
            # 检查是否为HLS/m3u8流，直接使用平台配置
            if url.lower().endswith('.m3u8') or 'm3u8' in url.lower():
                logger.info(f"🎯 检测到HLS/m3u8流，使用平台配置")
                ydl_opts['format'] = platform.get_format_selector(quality, url)
                ydl_opts['noprogress'] = True
                logger.info(f"🔄 HLS流使用平台格式选择器: {ydl_opts['format']}")
            else:
                # 优先使用平台特定的格式选择器
                try:
                    platform_format = platform.get_format_selector(quality, url)
                    ydl_opts['format'] = platform_format
                    ydl_opts['noprogress'] = True  # 防止数据类型错误

                    logger.info(f"🎯 使用{platform.name}平台格式选择器: {platform_format}")

                except Exception as platform_error:
                    logger.warning(f"⚠️ 平台格式选择器失败，使用智能选择器: {platform_error}")

                    # 降级到智能格式选择器
                    try:
                        from core.smart_format_selector import select_format_for_user
                        format_selector, reason, info = select_format_for_user(quality, url, proxy)
                        ydl_opts['format'] = format_selector
                        ydl_opts['noprogress'] = True  # 防止数据类型错误

                        logger.info(f"🏆 降级使用智能格式选择器: {format_selector}")
                        logger.info(f"   选择原因: {reason}")

                    except Exception as smart_error:
                        logger.error(f"❌ 智能格式选择器也失败，使用默认格式: {smart_error}")
                        ydl_opts['format'] = 'best/worst'
                        logger.info(f"🔄 使用默认格式选择器: best/worst")

        return ydl_opts

    def _create_progress_hook(self, download_id: str):
        """创建进度钩子函数"""
        def progress_hook(d):
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（下载进行中）: {download_id}")
                if YT_DLP_AVAILABLE:
                    raise yt_dlp.DownloadError("Download cancelled by user")
                else:
                    raise Exception("Download cancelled by user")

            if d.get('status') == 'downloading':
                # 更新进度 - 安全的类型处理
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate')
                    downloaded = d.get('downloaded_bytes')

                    # 确保数据类型正确，避免 "can't multiply sequence by non-int" 错误
                    if total is not None and downloaded is not None:
                        try:
                            total = float(total) if total else 0.0
                            downloaded = float(downloaded) if downloaded else 0.0

                            if total > 0:
                                # 使用统一的进度计算工具，带平滑化处理
                                from core.file_utils import ProgressUtils
                                progress = ProgressUtils.calculate_smooth_progress(int(downloaded), int(total), download_id)

                                # 🔧 总是更新进度状态（Web界面需要实时进度）
                                self._update_download_status(download_id, 'downloading', progress)

                                # 只在进度有显著变化时记录日志（减少日志噪音）
                                if progress % DownloadConstants.PROGRESS_LOG_INTERVAL == 0:
                                    logger.info(f"📊 下载进度: {download_id} - {progress}%")
                        except (ValueError, TypeError, ZeroDivisionError) as e:
                            # 记录具体的类型转换错误，便于调试
                            logger.debug(f"进度计算类型转换错误: {e}")
                except Exception as e:
                    # 记录进度钩子的其他异常，便于调试
                    logger.debug(f"进度钩子异常: {e}")

        return progress_hook

    def _execute_generic_download(self, download_id: str, url: str, ydl_opts: Dict[str, Any], options: Dict[str, Any] = None) -> Optional[str]:
        """执行通用下载"""
        if not YT_DLP_AVAILABLE:
            raise ImportError("yt-dlp 模块不可用")

        # 对于有问题的URL，尝试直接下载
        if URLUtils.should_fix_extension(url):
            logger.info("🔧 尝试直接下载方式绕过扩展名检查")
            try:
                return self._direct_download_fallback(download_id, url, ydl_opts, options)
            except Exception as e:
                logger.warning(f"⚠️ 直接下载失败，回退到标准方式: {e}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 最后检查是否已被取消
        if self._is_cancelled(download_id):
            logger.info(f"🚫 下载已被取消（下载完成后）: {download_id}")
            return None

        # 查找下载的文件（使用URL哈希）
        url_hash = URLUtils.generate_url_hash(url)
        return self._find_downloaded_file(url_hash, options)

    def _direct_download_fallback(self, download_id: str, url: str, ydl_opts: Dict[str, Any], options: Dict[str, Any] = None) -> Optional[str]:
        """直接下载备用方案，绕过yt-dlp的扩展名检查"""
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests 模块不可用")

        try:
            # 从URL中提取真实的文件名
            real_filename = URLUtils.extract_filename_from_url(url)
            if not real_filename:
                # 备用方案：使用URL哈希 + 推测的扩展名
                url_hash = URLUtils.generate_url_hash(url)
                if '.mp4' in url:
                    real_filename = f"{url_hash}.mp4"
                elif '.avi' in url:
                    real_filename = f"{url_hash}.avi"
                else:
                    real_filename = f"{url_hash}.mp4"  # 默认使用mp4

            logger.info(f"🔧 直接下载文件: {real_filename}")

            # 准备下载路径
            url_hash = URLUtils.generate_url_hash(url)
            if self._needs_audio_conversion(options):
                output_path = self.temp_dir / real_filename
            else:
                output_path = self.output_dir / real_filename

            # 获取代理配置
            proxy = self._get_proxy_config()
            proxies = {'http': proxy, 'https': proxy} if proxy else None

            # 检测服务器是否支持断点续传
            resume_support = self._check_resume_support(url, proxies)
            logger.info(f"🔍 服务器断点续传支持: {'✅ 支持' if resume_support else '❌ 不支持'}")

            # 检查是否存在部分下载的文件（断点续传）
            resume_pos = 0
            if output_path.exists() and resume_support:
                resume_pos = output_path.stat().st_size
                logger.info(f"🔄 检测到部分文件，从 {resume_pos / (1024*1024):.1f}MB 处续传")
            elif output_path.exists() and not resume_support:
                # 服务器不支持断点续传，删除部分文件重新开始
                logger.info("🗑️ 服务器不支持断点续传，删除部分文件重新下载")
                output_path.unlink()
                resume_pos = 0

            # 直接下载文件（支持断点续传）
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
            }

            # 如果有部分文件且服务器支持，添加Range头部进行断点续传
            if resume_pos > 0 and resume_support:
                headers['Range'] = f'bytes={resume_pos}-'
                logger.info(f"📡 发送Range请求: bytes={resume_pos}-")

            # 使用更长的超时时间和重试配置
            session = requests.Session()
            session.proxies = proxies

            # 配置重试适配器
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )

            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            response = session.get(url, headers=headers, stream=True, timeout=(30, 300))  # 连接30s，读取300s
            response.raise_for_status()

            # 获取文件总大小（处理断点续传）
            if response.status_code == 206:  # 部分内容响应
                # 从Content-Range头部获取总大小
                content_range = response.headers.get('content-range', '')
                if content_range:
                    # 格式: bytes 200-1023/1024
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = int(response.headers.get('content-length', 0)) + resume_pos
            else:
                total_size = int(response.headers.get('content-length', 0))

            downloaded_size = resume_pos  # 从已下载的位置开始计算
            last_progress = int((downloaded_size / total_size) * 100) if total_size > 0 else 0

            logger.info(f"📏 文件总大小: {total_size / (1024*1024):.1f}MB" if total_size > 0 else "📏 文件大小未知")
            if resume_pos > 0:
                logger.info(f"🔄 断点续传: 已下载 {resume_pos / (1024*1024):.1f}MB，继续下载")

            # 保存文件并显示进度（断点续传模式）
            file_mode = 'ab' if resume_pos > 0 else 'wb'
            with open(output_path, file_mode) as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 计算并发送进度（只在进度变化时更新）
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            # 只在进度变化超过1%时更新，减少频繁更新
                            if progress != last_progress and (progress - last_progress >= 1 or progress == 100):
                                self._update_download_status(download_id, "downloading", progress)
                                last_progress = progress

                        # 每下载1MB记录一次日志
                        if downloaded_size % (1024 * 1024) == 0 or downloaded_size == total_size:
                            mb_downloaded = downloaded_size / (1024 * 1024)
                            if total_size > 0:
                                total_mb = total_size / (1024 * 1024)
                                progress = int((downloaded_size / total_size) * 100)
                                logger.info(f"📥 直接下载进度: {mb_downloaded:.1f}MB / {total_mb:.1f}MB ({progress}%)")
                            else:
                                logger.info(f"📥 直接下载进度: {mb_downloaded:.1f}MB")

                        # 检查是否被取消
                        if self._is_cancelled(download_id):
                            logger.info(f"🚫 直接下载已被取消: {download_id}")
                            output_path.unlink(missing_ok=True)
                            return None

            # 发送完成进度
            self._update_download_status(download_id, "downloading", 100)
            logger.info(f"✅ 直接下载完成: {output_path} ({downloaded_size / (1024*1024):.1f}MB)")
            return str(output_path)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 直接下载失败: {error_msg}")

            # 检查是否是网络连接问题
            if any(keyword in error_msg.lower() for keyword in ['connection', 'timeout', 'incomplete', 'broken']):
                # 根据服务器支持情况决定是否保留部分文件
                if output_path.exists():
                    current_size = output_path.stat().st_size
                    if resume_support:
                        logger.info(f"💾 保留部分文件用于续传: {current_size / (1024*1024):.1f}MB")
                        # 抛出特定的网络错误，让重试机制处理
                        raise ConnectionError(f"网络连接中断，已保存 {current_size / (1024*1024):.1f}MB，支持续传")
                    else:
                        logger.info(f"🗑️ 服务器不支持续传，删除部分文件: {current_size / (1024*1024):.1f}MB")
                        output_path.unlink(missing_ok=True)
                        # 抛出网络错误，但不提及续传
                        raise ConnectionError("网络连接中断，服务器不支持断点续传，需要重新下载")
                else:
                    raise ConnectionError("网络连接中断")
            else:
                # 其他错误，删除部分文件
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                    logger.info("🗑️ 删除损坏的部分文件")
                raise



    def _find_downloaded_file(self, url_hash: str, options: Dict[str, Any] = None) -> Optional[str]:
        """安全地查找下载的文件 - 支持临时目录和最终目录"""
        try:
            # 使用更安全的文件匹配逻辑
            matched_files = []

            # 确定搜索目录：明确的单一目录搜索
            if options and self._needs_audio_conversion(options):
                search_dir = self.temp_dir
                logger.debug(f"🔍 搜索需要转换的文件: {search_dir}")
            else:
                search_dir = self.output_dir
                logger.debug(f"🔍 搜索无需转换的文件: {search_dir}")

            # 在指定目录搜索文件
            if search_dir.exists():
                for file_path in search_dir.iterdir():
                    if (file_path.is_file() and
                        file_path.name.startswith(url_hash + '.') and
                        not file_path.name.endswith('.part') and
                        not file_path.name.endswith('.tmp')):
                        matched_files.append(file_path)

            if matched_files:
                # 如果有多个匹配文件，选择最新的
                latest_file = max(matched_files, key=lambda f: f.stat().st_mtime)
                logger.info(f"✅ 找到下载文件: {latest_file} (目录: {latest_file.parent.name})")
                return str(latest_file)

            logger.debug(f"🔍 未找到匹配的下载文件: {url_hash}")
            return None

        except Exception as e:
            logger.error(f"❌ 查找下载文件失败: {e}")
            return None

    def _find_partial_files(self, url_hash: str) -> List[Path]:
        """安全地查找部分下载的文件"""
        try:
            partial_files = []

            # 遍历输出目录，查找部分文件
            for file_path in self.output_dir.iterdir():
                if (file_path.is_file() and
                    file_path.name.startswith(url_hash + '.') and
                    (file_path.name.endswith('.part') or
                     file_path.name.endswith('.tmp') or
                     file_path.stat().st_size > 0)):  # 有内容的文件
                    partial_files.append(file_path)

            return partial_files

        except Exception as e:
            logger.error(f"❌ 查找部分文件失败: {e}")
            return []

    def _validate_config_int(self, value: Any, name: str, min_val: int, max_val: int) -> int:
        """验证整数配置值"""
        try:
            int_value = int(value)
            if min_val <= int_value <= max_val:
                return int_value
            else:
                logger.warning(f"⚠️ 配置 {name} 值 {int_value} 超出范围 [{min_val}, {max_val}]，使用默认值")
                return min(max(int_value, min_val), max_val)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ 配置 {name} 值 {value} 无效，使用默认值 {min_val}")
            return min_val

    def _validate_config_path(self, value: Any, name: str) -> Path:
        """验证路径配置值"""
        try:
            path = Path(str(value))
            # 确保路径是绝对路径
            if not path.is_absolute():
                # 相对于当前工作目录
                path = Path.cwd() / path
            return path
        except Exception as e:
            logger.warning(f"⚠️ 配置 {name} 路径 {value} 无效: {e}，使用默认路径")
            return Path.cwd() / 'downloads' if name == 'output_dir' else Path.cwd() / 'temp'

    def _update_stats(self, event_type: str, **kwargs):
        """更新性能统计"""
        try:
            with self.lock:
                if event_type == 'download_started':
                    self.stats['total_downloads'] += 1
                elif event_type == 'download_completed':
                    self.stats['successful_downloads'] += 1
                    # 更新下载字节数
                    file_size = kwargs.get('file_size', 0)
                    if file_size:
                        self.stats['total_bytes_downloaded'] += file_size
                elif event_type == 'download_failed':
                    self.stats['failed_downloads'] += 1
                elif event_type == 'download_cancelled':
                    self.stats['cancelled_downloads'] += 1
        except Exception as e:
            logger.debug(f"统计更新失败: {e}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取简化的性能统计 - 只返回关键指标"""
        try:
            with self.lock:
                total = max(self.stats['total_downloads'], 1)
                success_rate = (self.stats['successful_downloads'] / total) * 100
                total_mb = self.stats['total_bytes_downloaded'] / 1024 / 1024

                return {
                    'total_downloads': self.stats['total_downloads'],
                    'success_rate': round(success_rate, 1),
                    'total_mb': round(total_mb, 1),
                    'failed_downloads': self.stats['failed_downloads']
                }
        except Exception as e:
            logger.error(f"❌ 获取性能统计失败: {e}")
            return {
                'total_downloads': 0,
                'success_rate': 0.0,
                'total_mb': 0.0,
                'failed_downloads': 0
            }

    def _needs_audio_conversion(self, options: Dict[str, Any]) -> bool:
        """判断是否需要音频转换"""
        quality = options.get('quality', 'best')
        audio_only = options.get('audio_only', False)
        return audio_only or quality.startswith('audio_')

    def _convert_to_audio(self, input_path: str, options: Dict[str, Any]) -> Optional[str]:
        """转换为音频格式 - 支持临时目录到最终目录的流程"""
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
                if str(input_file.parent) == str(self.temp_dir):
                    final_path = self.output_dir / input_file.name
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
            logger.info(f"🔄 开始音频转换: {input_file.name} -> {Path(temp_output_path).name}")
            success = self.ffmpeg_tools.extract_audio(
                input_path=input_path,
                output_path=temp_output_path,
                format=audio_format,
                quality=audio_quality
            )

            if success and Path(temp_output_path).exists():
                logger.info(f"✅ 音频转换成功: {audio_format} ({audio_quality})")

                # 移动转换后的文件到最终目录
                temp_file = Path(temp_output_path)
                final_path = self.output_dir / temp_file.name

                try:
                    temp_file.rename(final_path)
                    logger.info(f"📁 转换后文件已移动到最终目录: {final_path.name}")

                    # 清理原始文件
                    try:
                        Path(input_path).unlink()
                        logger.debug(f"🗑️ 清理原始文件: {Path(input_path).name}")
                    except:
                        pass

                    return str(final_path)
                except Exception as e:
                    logger.error(f"❌ 移动转换后文件失败: {e}")
                    return temp_output_path
            else:
                logger.error(f"❌ 音频转换失败")
                return None

        except Exception as e:
            logger.error(f"❌ 音频转换异常: {e}")
            return None

    def _get_audio_bitrate(self, audio_format: str, audio_quality: str) -> str:
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
                'high': '0',  # 无损
                'medium': '0',
                'low': '0'
            },
            'ogg': {
                'high': '256',
                'medium': '128',
                'low': '96'
            }
        }

        return bitrate_map.get(audio_format, {}).get(audio_quality, '192')

    def _apply_smart_filename(self, file_path: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """应用智能文件名"""
        try:
            if options.get('custom_filename'):
                return self.filename_processor.apply_custom_filename(file_path, options['custom_filename'])
            else:
                title = video_info.get('title', 'Unknown')
                download_id = Path(file_path).stem.split('.')[0]
                file_parent = Path(file_path).parent

                # 添加调试日志
                logger.info(f"🔧 智能文件名处理调试:")
                logger.info(f"   file_path: {file_path}")
                logger.info(f"   download_id: {download_id}")
                logger.info(f"   file_parent: {file_parent}")
                logger.info(f"   file_parent.exists(): {file_parent.exists()}")

                # 检查文件是否真的存在
                actual_file = Path(file_path)
                logger.info(f"   actual_file.exists(): {actual_file.exists()}")

                return self.filename_processor.apply_smart_filename_to_all(download_id, title, file_parent)
        except Exception as e:
            logger.error(f"❌ 应用智能文件名失败: {e}")
            return None

    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置 - 使用统一的配置管理器"""
        return ConfigManager.get_proxy_config()



    def _save_to_database(self, download_id: str, url: str):
        """保存到数据库"""
        try:
            get_database = ConfigManager.get_database_func()
            if not get_database:
                logger.debug("数据库模块不可用，跳过保存")
                return
            db = get_database()
            db.save_download_record(download_id, url)
        except Exception as e:
            logger.warning(f"⚠️ 保存到数据库失败: {e}")

    def _update_database_status(self, download_id: str, status: str, **kwargs):
        """更新数据库状态"""
        try:
            get_database = ConfigManager.get_database_func()
            if not get_database:
                logger.debug("数据库模块不可用，跳过状态更新")
                return
            db = get_database()
            db.update_download_status(download_id, status, **kwargs)
        except Exception as e:
            logger.warning(f"⚠️ 更新数据库状态失败: {e}")

    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        """发送事件"""
        try:
            from core.events import emit, Events
            event = getattr(Events, event_name, None)
            if event:
                logger.info(f"📡 发送事件: {event_name} - {data.get('download_id', 'N/A')}")
                emit(event, data)
            else:
                logger.warning(f"⚠️ 未知事件类型: {event_name}")
        except Exception as e:
            logger.error(f"❌ 发送事件失败: {event_name} - {e}")
            import traceback
            traceback.print_exc()

    def _update_download_status(self, download_id: str, status: str, progress: int = None, **kwargs):
        """更新下载状态"""
        try:
            # 先获取需要的数据，减少锁的持有时间
            download_info = None
            with self.lock:
                if download_id in self.downloads:
                    self.downloads[download_id]['status'] = status
                    if progress is not None:
                        self.downloads[download_id]['progress'] = progress
                    for key, value in kwargs.items():
                        self.downloads[download_id][key] = value
                    # 获取下载信息的副本，用于事件发送
                    download_info = self.downloads[download_id].copy()

            # 在锁外执行耗时操作
            # 更新数据库
            self._update_database_status(download_id, status, **kwargs)

            # 发送状态变更事件
            if status == 'completed' and download_info:
                # 更新统计
                self._update_stats('download_completed', file_size=kwargs.get('file_size', 0))

                self._emit_event('DOWNLOAD_COMPLETED', {
                    'download_id': download_id,
                    'file_path': kwargs.get('file_path'),
                    'title': download_info.get('title', 'Unknown'),
                    'file_size': kwargs.get('file_size')
                })
                logger.info(f"📡 发送下载完成事件: {download_id}")
            elif status == 'failed':
                # 更新统计
                self._update_stats('download_failed')
            elif status == 'cancelled':
                # 更新统计
                self._update_stats('download_cancelled')
            elif status in ['downloading', 'retrying']:
                # 发送进度事件
                self._emit_event('DOWNLOAD_PROGRESS', {
                    'download_id': download_id,
                    'status': status,
                    'progress': progress or 0
                })

        except Exception as e:
            logger.error(f"❌ 更新下载状态失败: {e}")

    def get_active_downloads(self) -> List[Dict]:
        """获取活跃的下载任务（正在进行中的）"""
        try:
            with self.lock:
                active_downloads = []
                for download_id, download_info in self.downloads.items():
                    if download_info.get('status') in ['pending', 'downloading']:
                        active_downloads.append({
                            'id': download_id,
                            'status': download_info.get('status'),
                            'title': download_info.get('title'),
                            'url': download_info.get('url'),
                            'progress': download_info.get('progress', 0),
                            'created_at': download_info.get('created_at')
                        })
                return active_downloads
        except Exception as e:
            logger.error(f"❌ 获取活跃下载失败: {e}")
            return []

    def get_system_status(self) -> Dict[str, Any]:
        """获取简化的系统状态 - 只返回关键信息"""
        try:
            # 获取基础状态
            active_downloads = len([d for d in self.downloads.values() if d['status'] in ['pending', 'downloading']])

            # 获取健康检查
            health = self.health_check()

            # 获取性能统计
            stats = self.get_performance_stats()

            return {
                'status': health['status'],
                'active_downloads': active_downloads,
                'total_downloads': len(self.downloads),
                'disk_writable': health.get('disk_writable', False),
                'memory_mb': health.get('memory_mb', 0),
                'download_stats': stats,
                'version': 'V2 (Optimized)'
            }
        except Exception as e:
            logger.error(f"❌ 获取系统状态失败: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'active_downloads': 0,
                'total_downloads': 0
            }

    def cleanup(self):
        """清理资源"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)

            # 清理重试管理器的过期数据
            self.retry_manager.cleanup_old_data()

            # 清理过期的下载记录（保留最近100个）
            self._cleanup_old_downloads()

            # 清理临时文件
            self._cleanup_temp_files()

            logger.info("✅ 下载管理器V2清理完成")
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")

    def _cleanup_old_downloads(self):
        """清理过期的下载记录"""
        try:
            with self.lock:
                # 保留最近的100个下载记录
                if len(self.downloads) > 100:
                    # 按时间排序，保留最新的100个
                    sorted_downloads = sorted(
                        self.downloads.items(),
                        key=lambda x: x[1].get('created_at', datetime.min),
                        reverse=True
                    )

                    # 保留前100个，删除其余的
                    keep_downloads = dict(sorted_downloads[:100])
                    removed_count = len(self.downloads) - len(keep_downloads)
                    self.downloads = keep_downloads

                    if removed_count > 0:
                        logger.info(f"🧹 清理了 {removed_count} 个过期下载记录")
        except Exception as e:
            logger.error(f"❌ 清理下载记录失败: {e}")

    def _cleanup_temp_files(self):
        """清理临时文件"""
        try:
            temp_files_removed = 0

            # 清理输出目录中的临时文件
            for temp_dir in [self.output_dir, self.temp_dir]:
                if temp_dir.exists():
                    for file_path in temp_dir.iterdir():
                        if (file_path.is_file() and
                            (file_path.name.endswith('.part') or
                             file_path.name.endswith('.tmp') or
                             file_path.name.startswith('tmp'))):
                            try:
                                # 检查文件是否超过1小时未修改
                                if (datetime.now().timestamp() - file_path.stat().st_mtime) > 3600:
                                    file_path.unlink()
                                    temp_files_removed += 1
                            except Exception as e:
                                logger.debug(f"删除临时文件失败: {file_path} - {e}")

            if temp_files_removed > 0:
                logger.info(f"🧹 清理了 {temp_files_removed} 个临时文件")

        except Exception as e:
            logger.error(f"❌ 清理临时文件失败: {e}")

    def health_check(self) -> Dict[str, Any]:
        """简化的系统健康检查 - 只检查关键项目"""
        try:
            # 检查目录状态
            dir_check = self._check_directories()

            # 检查内存使用
            memory_check = self._check_memory_usage()

            # 检查下载状态
            download_check = self._check_downloads_health()

            # 计算总体健康状态
            all_healthy = (dir_check.get('healthy', True) and
                          memory_check.get('healthy', True) and
                          download_check.get('healthy', True))

            return {
                'status': 'healthy' if all_healthy else 'degraded',
                'timestamp': datetime.now().isoformat(),
                'disk_writable': dir_check.get('output_dir_writable', False),
                'memory_mb': memory_check.get('rss_mb', 0),
                'stuck_downloads': download_check.get('stuck_downloads', 0),
                'active_downloads': download_check.get('active_downloads', 0)
            }

        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _check_directories(self) -> Dict[str, Any]:
        """检查目录状态 - 简化版本"""
        try:
            output_writable = (self.output_dir.exists() and
                             os.access(self.output_dir, os.W_OK))

            return {
                'healthy': output_writable,
                'output_dir_writable': output_writable
            }
        except Exception as e:
            return {'healthy': False, 'output_dir_writable': False}



    def _check_memory_usage(self) -> Dict[str, Any]:
        """检查内存使用情况 - 简化版本"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            rss_mb = memory_info.rss / 1024 / 1024

            return {
                'healthy': rss_mb < 512,  # 512MB 限制
                'rss_mb': round(rss_mb, 1)
            }
        except ImportError:
            return {'healthy': True, 'rss_mb': 0}
        except Exception as e:
            return {'healthy': True, 'rss_mb': 0}

    def _check_downloads_health(self) -> Dict[str, Any]:
        """检查下载状态健康 - 简化版本"""
        try:
            with self.lock:
                active = len([d for d in self.downloads.values() if d['status'] in ['pending', 'downloading']])
                stuck = len([d for d in self.downloads.values()
                           if d['status'] == 'downloading' and
                           (datetime.now() - d.get('updated_at', datetime.now())).total_seconds() > 300])  # 5分钟无更新

                return {
                    'healthy': stuck == 0,
                    'active_downloads': active,
                    'stuck_downloads': stuck
                }
        except Exception as e:
            return {'healthy': True, 'active_downloads': 0, 'stuck_downloads': 0}




# 全局实例
_manager_v2 = None


def get_download_manager_v2() -> DownloadManagerV2:
    """获取下载管理器V2实例"""
    global _manager_v2
    if _manager_v2 is None:
        _manager_v2 = DownloadManagerV2()
    return _manager_v2


# 向后兼容的别名
def get_download_manager() -> DownloadManagerV2:
    """向后兼容的获取下载管理器方法"""
    return get_download_manager_v2()
