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
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

# 导入模块化组件
from .retry_manager import RetryManager
from .ffmpeg_tools import FFmpegTools
from .filename_processor import FilenameProcessor
from .youtube_strategies import YouTubeStrategies
from .video_extractor import VideoExtractor

logger = logging.getLogger(__name__)


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

    # 进度日志间隔（百分比）- 降低到5%以便更好地观察进度
    PROGRESS_LOG_INTERVAL = 5

    # 默认重试次数
    DEFAULT_RETRIES = 5
    DEFAULT_FRAGMENT_RETRIES = 10


class ImportHelper:
    """统一的导入助手，消除重复的导入逻辑"""

    @staticmethod
    def safe_import(module_paths: List[str], fallback_func=None):
        """安全导入模块，支持多个路径尝试"""
        for module_path in module_paths:
            try:
                parts = module_path.split('.')
                # 修复导入逻辑：导入模块，然后获取属性
                if len(parts) > 1:
                    module_name = '.'.join(parts[:-1])  # 模块名
                    attr_name = parts[-1]  # 属性名
                    module = __import__(module_name, fromlist=[attr_name])
                    return getattr(module, attr_name)
                else:
                    # 如果只有一个部分，直接导入
                    return __import__(module_path)
            except (ImportError, AttributeError):
                continue

        if fallback_func:
            return fallback_func

        raise ImportError(f"无法导入任何模块: {module_paths}")

    @staticmethod
    def get_config():
        """获取配置函数"""
        def fallback_get_config(key, default=None):
            return os.getenv(key.upper().replace('.', '_'), default)

        return ImportHelper.safe_import([
            'core.config.get_config',
            'app.core.config.get_config'
        ], fallback_get_config)

    @staticmethod
    def get_database():
        """获取数据库函数"""
        try:
            # 直接导入数据库模块
            from core.database import get_database
            return get_database
        except ImportError:
            try:
                # 备用路径
                from app.core.database import get_database
                return get_database
            except ImportError:
                # 如果都失败，返回None
                logger.warning("⚠️ 无法导入数据库模块")
                return None


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
            # 使用统一的配置导入
            get_config = ImportHelper.get_config()

            # 获取并验证配置（带日志记录）
            max_concurrent_raw = self._get_config_with_log(get_config, 'downloader.max_concurrent', 3)
            output_dir_raw = self._get_config_with_log(get_config, 'downloader.output_dir', '/app/downloads')
            temp_dir_raw = self._get_config_with_log(get_config, 'downloader.temp_dir', '/app/temp')

            max_concurrent = self._validate_config_int(max_concurrent_raw, 'max_concurrent', 1, 10)
            self.output_dir = self._validate_config_path(output_dir_raw, 'output_dir')
            self.temp_dir = self._validate_config_path(temp_dir_raw, 'temp_dir')

            # 创建目录
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)

            # 清理遗留任务
            self._cleanup_orphaned_downloads()

            # 创建线程池
            self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

            # 启动自动清理
            self._start_cleanup()

            logger.info(f"✅ 下载管理器V2初始化完成 - 最大并发: {max_concurrent}")
            logger.info(f"🔧 FFmpeg状态: {'可用' if self.ffmpeg_tools.is_available() else '不可用'}")
            logger.info(f"📋 可用提取器: {len(self.video_extractor.get_available_extractors())} 个")
            logger.info(f"🎯 YouTube策略: {len(self.youtube_strategies.get_strategy_list())} 个")

        except Exception as e:
            logger.error(f"❌ 下载管理器V2初始化失败: {e}")
            raise
    
    def _cleanup_orphaned_downloads(self):
        """清理遗留的下载任务"""
        try:
            # 使用统一的数据库导入
            get_database = ImportHelper.get_database()
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
                        'url_hash': self._generate_url_hash(url)
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
                'url_hash': self._generate_url_hash(url)  # 添加URL哈希用于续传
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



    def _generate_url_hash(self, url: str) -> str:
        """生成URL哈希，用于续传功能"""
        try:
            # 标准化URL（移除查询参数中的时间戳等）
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
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

    def _find_resumable_download(self, url: str) -> Optional[Dict[str, Any]]:
        """查找可续传的下载任务"""
        try:
            url_hash = self._generate_url_hash(url)

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
                get_database = ImportHelper.get_database()
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
            get_database = ImportHelper.get_database()
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

                # 🔧 检测并修复 TS 容器格式问题（特别是 Pornhub 等 HLS 网站）
                fixed_file_path = self._fix_ts_container_if_needed(str(final_file_path), url)
                if fixed_file_path != str(final_file_path):
                    final_file_path = Path(fixed_file_path)
                    logger.info(f"✅ TS容器格式已修复: {final_file_path.name}")

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
        """处理下载失败 - 统一使用RetryManager（带PHP重定向回退）"""
        try:
            # 🔧 首先检查是否是PHP重定向问题，尝试直接下载回退
            with self.lock:
                download_info = self.downloads.get(download_id)
                if download_info:
                    url = download_info['url']
                    options = download_info['options']

                    # 检查是否是PHP重定向错误且还没有尝试过回退
                    if (("unusual and will be skipped" in error_msg or
                         "extracted extension" in error_msg or
                         "下载文件不存在" in error_msg) and
                        self._is_php_redirect_url(url) and
                        not download_info.get('_fallback_attempted', False)):

                        logger.info(f"🔧 检测到PHP重定向问题，尝试直接下载回退: {download_id}")

                        # 标记已尝试回退，避免无限循环
                        self.downloads[download_id]['_fallback_attempted'] = True

                        # 尝试直接下载
                        fallback_result = self._try_direct_download_fallback(download_id, url, options)

                        if fallback_result:
                            logger.info(f"✅ 直接下载回退成功: {download_id}")
                            return  # 成功了就直接返回
                        else:
                            logger.warning(f"❌ 直接下载回退也失败: {download_id}")
                            error_msg = f"yt-dlp和直接下载都失败: {error_msg}"

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
                failed_data = {
                    'download_id': download_id,
                    'error': error_msg
                }

                # 🔧 包含客户端ID用于精准推送
                download_info = self.downloads.get(download_id, {})
                if download_info and 'client_id' in download_info:
                    failed_data['client_id'] = download_info['client_id']

                self._emit_event('DOWNLOAD_FAILED', failed_data)

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
            import yt_dlp  # 在使用前导入

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

                # 🔧 检查是否是PHP重定向问题，尝试直接下载
                if "unusual and will be skipped" in str(e) and self._is_php_redirect_url(url):
                    logger.info(f"🔧 检测到PHP重定向问题，尝试直接下载")
                    return self._try_direct_download_fallback(download_id, url, options)

                return None
        except Exception as e:
            logger.error(f"❌ 通用下载失败: {e}")

            # 🔧 检查是否是PHP重定向问题，尝试直接下载
            if self._is_php_redirect_url(url):
                logger.info(f"🔧 通用下载失败，尝试PHP重定向直接下载")
                return self._try_direct_download_fallback(download_id, url, options)

            return None

    def _prepare_download_options(self, url: str, options: Dict[str, Any], download_id: str) -> Dict[str, Any]:
        """准备下载选项配置（集成平台配置）"""
        import yt_dlp

        # 🎯 获取平台特定配置
        try:
            from modules.downloader.platforms import get_platform_for_url
            platform = get_platform_for_url(url)
            logger.info(f"🎯 使用平台配置: {platform.name} for {url[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ 无法获取平台配置，使用默认配置: {e}")
            platform = None

        # 生成URL哈希用于续传
        url_hash = self._generate_url_hash(url)

        # 智能路径选择：需要转换的文件使用临时目录
        if self._needs_audio_conversion(options):
            # 需要转换，使用临时目录
            output_template = str(self.temp_dir / f'{url_hash}.%(ext)s')
            logger.info(f"🔄 需要音频转换，使用临时目录: {self.temp_dir}")
        else:
            # 不需要转换，直接使用最终目录
            output_template = str(self.output_dir / f'{url_hash}.%(ext)s')
            logger.info(f"📁 无需转换，直接下载到最终目录: {self.output_dir}")

        # 🎯 基础配置 - 集成平台特定配置
        if platform:
            # 使用平台特定配置作为基础
            quality = options.get('quality', 'high')
            ydl_opts = platform.get_config(url, quality)
            logger.info(f"✅ 已应用 {platform.name} 平台配置")

            # 🎯 关键：应用平台提取器参数（这是Twitter成功的关键！）
            if hasattr(platform, 'get_extractor_args'):
                extractor_args = platform.get_extractor_args()
                if extractor_args:
                    ydl_opts['extractor_args'] = extractor_args
                    logger.info(f"✅ 应用平台提取器参数: {extractor_args}")
        else:
            # 使用默认配置
            ydl_opts = {}
            logger.info("📋 使用默认配置")

        # 覆盖/添加必要的基础设置
        ydl_opts.update({
            'outtmpl': output_template,  # 智能选择输出路径
            'continue_dl': True,  # 明确启用续传
            'nooverwrites': True,  # 不覆盖已存在的文件
            'retries': ydl_opts.get('retries', DownloadConstants.DEFAULT_RETRIES),  # 保留平台重试设置
            'fragment_retries': ydl_opts.get('fragment_retries', DownloadConstants.DEFAULT_FRAGMENT_RETRIES),
            'skip_unavailable_fragments': False,  # 不跳过不可用的分片
            'allow_unplayable_formats': True,  # 允许不可播放的格式
            'ignore_no_formats_error': False,  # 不忽略无格式错误
            'no_check_certificates': True,  # 不检查SSL证书
            'prefer_insecure': False,  # 不优先使用不安全连接

            # 🔧 处理异常扩展名问题（如PHP重定向）
            # 'allowed_extractors': ['generic'],  # 注释掉：允许所有提取器自动识别
            'force_write_download_archive': False,  # 不强制写入下载档案
        })

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

        # 添加进度钩子 - 使用安全包装器
        ydl_opts['progress_hooks'] = [self._create_safe_progress_hook(download_id)]

        # 🔧 智能处理异常扩展名问题（通用解决方案）
        unusual_extension_detected = self._detect_unusual_extension_url(url)
        if unusual_extension_detected:
            logger.info(f"🔧 检测到异常扩展名URL: {unusual_extension_detected['type']}")
            ydl_opts = self._apply_unusual_extension_fix(ydl_opts, unusual_extension_detected, options)

        # 🔧 特殊处理：PHP重定向文件下载
        if self._is_php_redirect_url(url):
            logger.info(f"🔧 检测到PHP重定向URL，应用特殊处理")
            ydl_opts = self._apply_php_redirect_fix(ydl_opts, url, options)

        # 🔧 进度控制选项：明确启用进度回调
        ydl_opts['noprogress'] = False  # 明确启用进度，避免下载问题

        logger.info(f"🔄 使用续传文件名: {url_hash} (来自URL: {url[:50]}...)")

        return ydl_opts

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
                # 移除 noprogress = True，让HLS流也能显示进度
                logger.info(f"🔄 HLS流使用平台格式选择器: {ydl_opts['format']}")
            else:
                # 优先使用平台特定的格式选择器
                try:
                    platform_format = platform.get_format_selector(quality, url)
                    ydl_opts['format'] = platform_format
                    # 移除 noprogress = True，让平台格式选择器也能显示进度

                    logger.info(f"🎯 使用{platform.name}平台格式选择器: {platform_format}")

                except Exception as platform_error:
                    logger.warning(f"⚠️ 平台格式选择器失败，使用智能选择器: {platform_error}")

                    # 降级到智能格式选择器
                    try:
                        from core.smart_format_selector import select_format_for_user
                        format_selector, reason, info = select_format_for_user(quality, url, proxy)
                        ydl_opts['format'] = format_selector
                        # 移除 noprogress = True，让智能格式选择器也能显示进度

                        logger.info(f"🏆 降级使用智能格式选择器: {format_selector}")
                        logger.info(f"   选择原因: {reason}")

                    except Exception as smart_error:
                        logger.error(f"❌ 智能格式选择器也失败，使用默认格式: {smart_error}")
                        ydl_opts['format'] = 'best/worst'
                        logger.info(f"🔄 使用默认格式选择器: best/worst")

        return ydl_opts

    def _create_safe_progress_hook(self, download_id: str):
        """创建安全的进度钩子函数 - 增强错误处理"""
        def safe_progress_hook(d):
            try:
                # 调试：记录所有进度钩子调用
                logger.info(f"🔍 进度钩子被调用: {download_id} - 状态: {d.get('status')}")

                # 取消检查
                if self._is_cancelled(download_id):
                    logger.info(f"🚫 下载已被取消（下载进行中）: {download_id}")
                    import yt_dlp
                    raise yt_dlp.DownloadError("Download cancelled by user")

                # 只处理下载状态
                if d.get('status') != 'downloading':
                    logger.info(f"🔍 跳过非下载状态: {d.get('status')}")
                    return

                # 安全的进度数据提取 - 支持HLS分片下载
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes')

                # HLS分片下载的特殊处理
                fragment_index = d.get('fragment_index')
                fragment_count = d.get('fragment_count')

                # 如果是HLS分片下载且没有字节数据，使用分片进度
                if fragment_index is not None and fragment_count is not None and fragment_count > 0:
                    if total is None or downloaded is None:
                        # 基于分片计算进度
                        progress_percent = int((fragment_index / fragment_count) * 100)
                        logger.info(f"📊 HLS分片进度: {download_id} - {fragment_index}/{fragment_count} = {progress_percent}%")

                        # 直接更新进度状态
                        self._update_download_status(download_id, 'downloading', progress_percent)

                        # 减少日志噪音
                        if progress_percent % DownloadConstants.PROGRESS_LOG_INTERVAL == 0:
                            logger.info(f"📊 HLS下载进度: {download_id} - {progress_percent}% (片段 {fragment_index}/{fragment_count})")
                        return

                # 多层安全检查（普通下载）
                if not self._is_valid_progress_data(total, downloaded):
                    return

                # 安全的类型转换
                try:
                    total_float = self._safe_float_convert(total)
                    downloaded_float = self._safe_float_convert(downloaded)

                    if total_float > 0 and downloaded_float >= 0:
                        # 使用统一的进度计算工具
                        from core.file_utils import ProgressUtils
                        progress = ProgressUtils.calculate_smooth_progress(
                            int(downloaded_float), int(total_float), download_id
                        )

                        # 更新进度状态
                        self._update_download_status(download_id, 'downloading', progress)

                        # 减少日志噪音 - 只在进度有显著变化时记录
                        if progress % DownloadConstants.PROGRESS_LOG_INTERVAL == 0:
                            logger.info(f"📊 下载进度: {download_id} - {progress}%")

                except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
                    # 详细记录类型转换错误，但不中断下载
                    logger.debug(f"⚠️ 进度计算类型错误 {download_id}: {e}")
                    logger.debug(f"   原始数据: total={total}, downloaded={downloaded}")

            except Exception as e:
                # 最外层异常捕获 - 确保进度钩子异常不会中断下载
                logger.debug(f"⚠️ 进度钩子异常 {download_id}: {e}")

        return safe_progress_hook

    def _is_valid_progress_data(self, total, downloaded):
        """验证进度数据的有效性"""
        try:
            # 检查数据是否存在
            if total is None or downloaded is None:
                return False

            # 检查数据类型是否可转换
            if isinstance(total, (str, bytes)) and not str(total).replace('.', '').isdigit():
                return False
            if isinstance(downloaded, (str, bytes)) and not str(downloaded).replace('.', '').isdigit():
                return False

            return True
        except Exception:
            return False

    def _safe_float_convert(self, value):
        """安全的浮点数转换"""
        try:
            if value is None:
                return 0.0

            # 处理字符串类型
            if isinstance(value, (str, bytes)):
                value = str(value).strip()
                if not value:
                    return 0.0

            # 转换为浮点数
            result = float(value)

            # 检查是否为有效数字
            if not (0 <= result <= float('inf')):
                return 0.0

            return result
        except (ValueError, TypeError, OverflowError):
            return 0.0

    def _create_progress_hook(self, download_id: str):
        """创建进度钩子函数 - 保留原方法以兼容性"""
        return self._create_safe_progress_hook(download_id)

    def _execute_generic_download(self, download_id: str, url: str, ydl_opts: Dict[str, Any], options: Dict[str, Any] = None) -> Optional[str]:
        """执行通用下载（带PHP重定向回退）"""
        import yt_dlp

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 最后检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（下载完成后）: {download_id}")
                return None

            # 查找下载的文件（使用URL哈希）
            url_hash = self._generate_url_hash(url)
            result = self._find_downloaded_file(url_hash, options)

            # 🔧 如果下载失败且是PHP重定向URL，尝试直接下载回退
            if result is None and self._is_php_redirect_url(url):
                logger.info(f"🔧 yt-dlp下载失败，检测到PHP重定向URL，启动直接下载回退")

                # 标记已尝试回退，避免重复
                with self.lock:
                    if download_id in self.downloads:
                        self.downloads[download_id]['_fallback_attempted'] = True

                fallback_result = self._try_direct_download_fallback(download_id, url, options or {})

                if fallback_result:
                    logger.info(f"✅ 直接下载回退成功: {download_id}")
                    return fallback_result
                else:
                    logger.error(f"❌ 直接下载回退也失败: {download_id}")

            return result

        except Exception as e:
            logger.error(f"❌ yt-dlp执行失败: {e}")

            # 🔧 检查是否是PHP重定向问题，尝试直接下载
            error_str = str(e)
            is_extension_error = ("unusual and will be skipped" in error_str or
                                "extracted extension" in error_str)
            is_php_redirect = self._is_php_redirect_url(url)

            if is_extension_error and is_php_redirect:
                logger.info(f"🔧 检测到PHP重定向问题，启动直接下载回退")

                # 标记已尝试回退，避免重复
                with self.lock:
                    if download_id in self.downloads:
                        self.downloads[download_id]['_fallback_attempted'] = True

                fallback_result = self._try_direct_download_fallback(download_id, url, options or {})

                if fallback_result:
                    logger.info(f"✅ 直接下载回退成功: {download_id}")
                    return fallback_result
                else:
                    logger.error(f"❌ 直接下载回退也失败: {download_id}")
                    # 回退也失败了，抛出包含原始错误信息的异常
                    raise Exception(f"yt-dlp和直接下载都失败: {error_str}")

            # 重新抛出异常让上层处理
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
        """获取代理配置 - 使用统一的代理助手"""
        from core.proxy_converter import ProxyHelper
        return ProxyHelper.get_ytdlp_proxy("DownloadManager")



    def _save_to_database(self, download_id: str, url: str):
        """保存到数据库"""
        try:
            get_database = ImportHelper.get_database()
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
            get_database = ImportHelper.get_database()
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

                # 构建完成事件数据
                completed_data = {
                    'download_id': download_id,
                    'file_path': kwargs.get('file_path'),
                    'title': download_info.get('title', 'Unknown'),
                    'file_size': kwargs.get('file_size')
                }

                # 🔧 包含客户端ID用于精准推送
                if download_info and 'client_id' in download_info:
                    completed_data['client_id'] = download_info['client_id']

                self._emit_event('DOWNLOAD_COMPLETED', completed_data)
                logger.info(f"📡 发送下载完成事件: {download_id}")
            elif status == 'failed':
                # 更新统计
                self._update_stats('download_failed')
            elif status == 'cancelled':
                # 更新统计
                self._update_stats('download_cancelled')
            elif status in ['downloading', 'retrying']:
                # 发送进度事件
                progress_data = {
                    'download_id': download_id,
                    'status': status,
                    'progress': progress or 0
                }

                # 🔧 包含客户端ID用于精准推送
                if download_info and 'client_id' in download_info:
                    progress_data['client_id'] = download_info['client_id']

                # 如果有下载字节数信息，添加到事件中
                if 'downloaded_bytes' in kwargs:
                    progress_data['downloaded_bytes'] = kwargs['downloaded_bytes']
                    progress_data['downloaded_mb'] = kwargs['downloaded_bytes'] / (1024 * 1024)

                if 'total_bytes' in kwargs:
                    progress_data['total_bytes'] = kwargs['total_bytes']
                    if kwargs['total_bytes']:
                        progress_data['total_mb'] = kwargs['total_bytes'] / (1024 * 1024)

                self._emit_event('DOWNLOAD_PROGRESS', progress_data)

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

    def _detect_unusual_extension_url(self, url: str) -> Optional[Dict[str, Any]]:
        """智能检测异常扩展名URL（通用检测器）"""
        try:
            url_lower = url.lower()

            # 白名单：已知的正常平台，不需要特殊处理
            normal_platforms = [
                'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com',
                'twitch.tv', 'facebook.com', 'instagram.com', 'twitter.com',
                'tiktok.com', 'bilibili.com', 'iqiyi.com', 'youku.com'
            ]

            # 如果是已知正常平台，跳过检测
            for platform in normal_platforms:
                if platform in url_lower:
                    return None

            # 定义异常扩展名模式（可扩展）
            unusual_patterns = {
                # 服务器脚本扩展名（更精确的检测）
                'server_script': ['.php', '.jsp', '.asp', '.aspx', '.cgi'],
                # 重定向控制文件
                'redirect_control': ['remote_control', 'proxy_redirect', 'file_redirect'],
                # 动态生成文件
                'dynamic_file': ['get_file', 'download_file', 'stream_file'],
            }

            detected_type = None
            detected_patterns = []

            # 检测各种模式
            for pattern_type, patterns in unusual_patterns.items():
                for pattern in patterns:
                    if pattern in url_lower:
                        detected_type = pattern_type
                        detected_patterns.append(pattern)

            # 特殊检测：URL中包含大量参数且有可疑的文件扩展名
            if (url.count('?') > 0 and url.count('&') > 5 and
                any(ext in url_lower for ext in ['.php', '.jsp', '.asp', '.cgi'])):
                detected_type = 'param_heavy_script'
                detected_patterns.append('multiple_params_with_script')

            if detected_type:
                logger.info(f"🔍 检测到异常URL模式: {detected_type} - {detected_patterns}")
                return {
                    'type': detected_type,
                    'patterns': detected_patterns,
                    'url': url
                }

            return None

        except Exception as e:
            logger.debug(f"异常扩展名检测失败: {e}")
            return None

    def _apply_unusual_extension_fix(self, ydl_opts: Dict[str, Any], detection_info: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """应用异常扩展名修复策略（智能策略选择）"""
        try:
            detection_type = detection_info.get('type')
            patterns = detection_info.get('patterns', [])

            logger.info(f"🔧 应用修复策略: {detection_type}")

            # 策略1: 强制扩展名修复
            target_format = self._determine_target_format(options)
            base_template = ydl_opts['outtmpl'].replace('.%(ext)s', f'.{target_format}')
            ydl_opts['outtmpl'] = base_template

            # 策略2: 添加后处理器
            postprocessors = ydl_opts.get('postprocessors', [])

            if options.get('audio_only'):
                # 音频下载
                postprocessors.append({
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': options.get('audio_format', 'mp3'),
                    'preferredquality': '192',
                })
            else:
                # 视频下载
                postprocessors.append({
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': target_format,
                })

            ydl_opts['postprocessors'] = postprocessors

            # 策略3: 增强容错配置
            ydl_opts.update({
                'ignore_errors': False,  # 不忽略错误，但用后处理器处理
                'extract_flat': False,   # 完整提取信息
                'force_generic_extractor': False,  # 不强制使用通用提取器
            })

            logger.info(f"✅ 异常扩展名修复策略已应用: 目标格式={target_format}")
            return ydl_opts

        except Exception as e:
            logger.error(f"❌ 应用异常扩展名修复失败: {e}")
            return ydl_opts

    def _determine_target_format(self, options: Dict[str, Any]) -> str:
        """智能确定目标格式"""
        if options.get('audio_only'):
            return options.get('audio_format', 'mp3')
        else:
            # 根据质量选择视频格式
            quality = options.get('quality', 'high')
            if quality in ['4k', 'high']:
                return 'mp4'  # 高质量使用mp4
            elif quality in ['medium', 'low']:
                return 'mp4'  # 中低质量也使用mp4（兼容性最好）
            else:
                return 'mp4'  # 默认mp4

    def _is_php_redirect_url(self, url: str) -> bool:
        """检测是否为PHP重定向URL"""
        try:
            import re
            # 检测可能导致PHP重定向的URL模式
            php_redirect_patterns = [
                r'/get_file/',
                r'/download\.php',
                r'/stream\.php',
                r'/video\.php',
                r'/media\.php',
                r'/remote_control\.php',  # 远程控制PHP文件
                r'\.php\?',  # 任何带参数的PHP文件
                r'\.mp4$',  # 直接指向mp4但可能重定向到PHP
            ]

            for pattern in php_redirect_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.debug(f"🔍 匹配PHP重定向模式: {pattern}")
                    return True

            return False

        except Exception as e:
            logger.debug(f"PHP重定向检测失败: {e}")
            return False

    def _apply_php_redirect_fix(self, ydl_opts: Dict[str, Any], url: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """应用PHP重定向修复策略"""
        try:
            logger.info(f"🔧 应用PHP重定向修复策略")

            # 1. 强制使用通用提取器
            ydl_opts['force_generic_extractor'] = True

            # 2. 允许异常扩展名
            ydl_opts['allow_unplayable_formats'] = True

            # 3. 修改输出模板，强制使用正确的扩展名
            target_format = self._determine_target_format(options)
            if '.%(ext)s' in ydl_opts['outtmpl']:
                # 替换为固定扩展名
                ydl_opts['outtmpl'] = ydl_opts['outtmpl'].replace('.%(ext)s', f'.{target_format}')
                logger.info(f"🔧 强制输出格式: {target_format}")

            # 4. 添加后处理器确保格式正确
            postprocessors = ydl_opts.get('postprocessors', [])

            if not options.get('audio_only'):
                # 视频文件：确保转换为mp4
                postprocessors.append({
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': target_format,
                })

            ydl_opts['postprocessors'] = postprocessors

            # 5. 绕过yt-dlp的扩展名安全检查
            ydl_opts.update({
                'ignoreerrors': True,  # 忽略错误继续下载
                'no_warnings': True,   # 不显示警告
                'extract_flat': False,  # 完整提取
                'writeinfojson': False,  # 不写入info.json
                'writethumbnail': False,  # 不下载缩略图
                'writesubtitles': False,  # 不下载字幕
            })

            # 6. 增强网络配置
            ydl_opts.update({
                'socket_timeout': 60,  # 增加超时时间
                'retries': 5,  # 增加重试次数
                'fragment_retries': 10,  # 增加分片重试
                'http_chunk_size': 1048576,  # 1MB chunks
            })

            # 7. 如果yt-dlp仍然失败，准备直接下载方案
            ydl_opts['_php_redirect_fallback'] = {
                'url': url,
                'target_format': target_format,
                'options': options
            }

            logger.info(f"✅ PHP重定向修复策略已应用")
            return ydl_opts

        except Exception as e:
            logger.error(f"❌ PHP重定向修复失败: {e}")
            return ydl_opts

    def _direct_download_php_redirect(self, url: str, output_path: str, options: Dict[str, Any], download_id: str = None) -> bool:
        """直接下载PHP重定向文件（绕过yt-dlp）"""
        try:
            import requests
            from core.proxy_converter import ProxyConverter

            logger.info(f"🔧 尝试直接下载PHP重定向文件")

            # 获取代理配置
            proxy_config = ProxyConverter.get_requests_proxy("DirectDownload")
            proxies = proxy_config if proxy_config else None

            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'video/mp4,video/*,*/*;q=0.9',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'identity',  # 不压缩，直接下载
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            # 发送请求
            logger.info(f"📥 开始直接下载: {url}")
            response = requests.get(url, headers=headers, proxies=proxies, stream=True, timeout=60)
            response.raise_for_status()

            # 检查内容类型
            content_type = response.headers.get('content-type', '').lower()
            content_length = response.headers.get('content-length', 'Unknown')
            logger.info(f"📄 内容类型: {content_type}")
            logger.info(f"📏 内容长度: {content_length}")
            logger.info(f"🆔 下载ID: {download_id}")

            if 'video' in content_type or 'octet-stream' in content_type:
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # 下载文件
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_progress = 0
                chunk_count = 0

                logger.info(f"📏 文件总大小: {total_size:,} bytes ({total_size/(1024*1024):.1f}MB)")

                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            chunk_count += 1

                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)

                                # 每1%更新一次进度
                                if progress > last_progress or progress == 100:
                                    logger.info(f"📈 直接下载进度: {progress}% ({downloaded:,}/{total_size:,}) - {downloaded/(1024*1024):.1f}MB")

                                    # 更新下载状态和发送SSE事件，包含字节数信息
                                    if download_id:
                                        self._update_download_status(download_id, 'downloading', progress,
                                                                   downloaded_bytes=downloaded,
                                                                   total_bytes=total_size)

                                    last_progress = progress
                            else:
                                # 如果没有总大小信息，每5MB显示一次进度
                                mb_downloaded = downloaded / (1024 * 1024)
                                if int(mb_downloaded) % 5 == 0 and int(mb_downloaded) > int((downloaded - len(chunk)) / (1024 * 1024)):
                                    logger.info(f"📈 直接下载进度: {downloaded:,} bytes ({mb_downloaded:.1f}MB) - 总大小未知")

                                    if download_id:
                                        # 没有总大小时，传递实际下载的字节数，前端可以显示为MB
                                        self._update_download_status(download_id, 'downloading', -1,
                                                                   downloaded_bytes=downloaded,
                                                                   total_bytes=None)

                logger.info(f"✅ 直接下载完成: {output_path}")
                logger.info(f"📏 文件大小: {downloaded / (1024*1024):.1f}MB")

                return True
            else:
                logger.warning(f"⚠️ 内容类型不是视频: {content_type}")
                return False

        except Exception as e:
            logger.error(f"❌ 直接下载失败: {e}")
            return False

    def _try_direct_download_fallback(self, download_id: str, url: str, options: Dict[str, Any]) -> Optional[str]:
        """尝试直接下载回退方案"""
        try:
            logger.info(f"🔧 启动直接下载回退方案: {download_id}")

            # 生成输出文件路径
            target_format = self._determine_target_format(options)
            filename = f"{download_id}.{target_format}"
            output_path = os.path.join(self.output_dir, filename)

            # 尝试直接下载
            success = self._direct_download_php_redirect(url, output_path, options, download_id)

            if success and os.path.exists(output_path):
                logger.info(f"✅ 直接下载成功: {output_path}")

                # 更新下载状态
                file_size = os.path.getsize(output_path)
                self._update_download_status(download_id, 'completed', 100,
                                           file_path=output_path, file_size=file_size)

                return output_path
            else:
                logger.error(f"❌ 直接下载失败或文件不存在")
                return None

        except Exception as e:
            logger.error(f"❌ 直接下载回退失败: {e}")
            return None

    def _fix_ts_container_if_needed(self, file_path: str, url: str) -> str:
        """检测并修复TS容器格式问题（特别是Pornhub等HLS网站）

        Args:
            file_path: 文件路径
            url: 原始URL，用于判断是否为特定网站

        Returns:
            str: 修复后的文件路径（如果没有修复，返回原路径）
        """
        try:
            # 检查是否为MP4文件
            path_obj = Path(file_path)
            if not path_obj.suffix.lower() == '.mp4':
                return file_path  # 不是MP4文件，不需要处理

            # 检查是否为特定网站（Pornhub等）
            is_pornhub = 'pornhub.com' in url.lower()
            is_xvideos = 'xvideos.com' in url.lower()
            is_xhamster = 'xhamster.com' in url.lower()
            is_adult_site = is_pornhub or is_xvideos or is_xhamster

            # 如果不是特定网站，使用更通用的检测方法
            if not is_adult_site:
                # 检查URL是否包含HLS相关关键词
                is_hls = '.m3u8' in url.lower() or 'hls' in url.lower()
                if not is_hls:
                    return file_path  # 不是HLS流，不需要处理

            logger.info(f"🔍 检测到可能的TS容器问题，开始检查: {path_obj.name}")

            # 简单检测：使用FFmpeg获取文件信息
            from modules.downloader.ffmpeg_tools import get_ffmpeg_tools
            ffmpeg_tools = get_ffmpeg_tools()

            if not ffmpeg_tools.is_available():
                logger.warning(f"⚠️ FFmpeg不可用，跳过TS容器检测")
                return file_path

            # 使用FFmpeg检测容器格式（快速检测，只读取文件头）
            import subprocess
            try:
                ffmpeg_exe = ffmpeg_tools.get_ffmpeg_executable()
                result = subprocess.run([
                    ffmpeg_exe, '-i', file_path, '-t', '0.1', '-f', 'null', '-'
                ], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=15)

                # 检查输出中是否包含MPEG-TS相关信息
                output = result.stderr.lower()
                is_ts_container = 'mpegts' in output or 'mpeg-ts' in output

                logger.debug(f"🔍 FFmpeg容器检测结果: {is_ts_container} (输出包含: {'mpegts' if 'mpegts' in output else 'other'})")

                if not is_ts_container:
                    logger.info(f"✅ 文件容器格式正常: {path_obj.name}")
                    return file_path

                logger.info(f"🔧 检测到TS容器格式，开始修复: {path_obj.name}")

                # 创建临时文件路径
                temp_file = path_obj.parent / f"{path_obj.stem}_fixed{path_obj.suffix}"

                # 使用FFmpeg重新封装为MP4容器（仅复制流，不重新编码）
                convert_result = subprocess.run([
                    ffmpeg_exe, '-i', file_path,
                    '-c', 'copy',  # 复制所有流，不重新编码
                    '-y', str(temp_file)  # 覆盖输出文件
                ], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=300)

                if convert_result.returncode == 0 and temp_file.exists():
                    # 转换成功，替换原文件
                    try:
                        # 删除原文件
                        path_obj.unlink()
                        # 重命名新文件
                        temp_file.rename(path_obj)
                        logger.info(f"✅ TS容器格式修复成功: {path_obj.name}")
                        return file_path
                    except Exception as e:
                        logger.error(f"❌ 替换文件失败: {e}")
                        # 如果替换失败，返回临时文件路径
                        return str(temp_file)
                else:
                    logger.error(f"❌ TS容器格式修复失败: {convert_result.stderr}")
                    # 清理临时文件
                    if temp_file.exists():
                        temp_file.unlink()
                    return file_path

            except subprocess.TimeoutExpired:
                logger.error(f"❌ TS容器检测超时")
                return file_path
            except Exception as e:
                logger.error(f"❌ TS容器检测失败: {e}")
                return file_path

        except Exception as e:
            logger.error(f"❌ TS容器格式修复异常: {e}")
            return file_path




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
