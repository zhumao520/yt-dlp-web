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
from .core_manager import CoreDownloadManager
from .retry_manager import RetryManager
from .ffmpeg_tools import FFmpegTools
from .filename_processor import FilenameProcessor
from .youtube_strategies import YouTubeStrategies
from .video_extractor import VideoExtractor

logger = logging.getLogger(__name__)


class DownloadManagerV2:
    """下载管理器 V2 - 模块化版本"""
    
    def __init__(self):
        self.downloads: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.executor = None
        
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
    
    def _initialize(self):
        """初始化下载管理器"""
        try:
            # 灵活的配置导入
            try:
                from core.config import get_config
            except ImportError:
                try:
                    from app.core.config import get_config
                except ImportError:
                    def get_config(key, default=None):
                        logger.warning(f"⚠️ 无法导入配置模块，使用默认值: {key} = {default}")
                        return default

            # 获取配置
            max_concurrent = get_config('downloader.max_concurrent', 3)
            self.output_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
            self.temp_dir = Path(get_config('downloader.temp_dir', '/app/temp'))

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
            # 灵活的数据库导入
            try:
                from core.database import get_database
            except ImportError:
                try:
                    from app.core.database import get_database
                except ImportError:
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
                    logger.info(f"🔄 复用数据库中的失败任务: {existing_download['id']}")
                    return existing_download['id']
                else:
                    # 内存中的失败任务，复用ID
                    logger.info(f"🔄 复用内存中的失败任务: {existing_download['id']}")
                    # 重置状态为pending
                    with self.lock:
                        if existing_download['id'] in self.downloads:
                            self.downloads[existing_download['id']]['status'] = 'pending'
                            self.downloads[existing_download['id']]['error_message'] = None
                            self.downloads[existing_download['id']]['retry_count'] = 0
                    return existing_download['id']

            # 创建下载记录
            download_info = {
                'id': download_id,
                'url': url,
                'status': 'pending',
                'progress': 0,
                'title': None,
                'file_path': None,
                'file_size': None,
                'error_message': None,
                'created_at': datetime.now(),
                'completed_at': None,
                'options': options or {},
                'retry_count': 0,
                'max_retries': options.get('max_retries', 3) if options else 3,
                'url_hash': self._generate_url_hash(url)  # 添加URL哈希用于续传
            }

            with self.lock:
                self.downloads[download_id] = download_info

            # 保存到数据库
            self._save_to_database(download_id, url)

            # 发送事件
            self._emit_event('DOWNLOAD_STARTED', {
                'download_id': download_id,
                'url': url,
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

            # 1. 检查内存中的下载任务
            with self.lock:
                for download_id, download_info in self.downloads.items():
                    if (download_info['url'] == url and
                        download_info['status'] in ['failed', 'cancelled']):
                        logger.info(f"🔍 找到可续传的内存任务: {download_id}")
                        return download_info

            # 2. 检查是否有部分下载的文件
            url_hash_files = list(self.output_dir.glob(f"{url_hash}.*"))
            if url_hash_files:
                logger.info(f"🔍 找到部分下载文件: {[f.name for f in url_hash_files]}")
                # 创建一个虚拟的下载信息用于续传
                return {
                    'url': url,
                    'url_hash': url_hash,
                    'partial_files': url_hash_files,
                    'resumable': True
                }

            # 3. 检查数据库中的失败任务（如果可用）
            try:
                from core.database import get_database
                db = get_database()
                if db:
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
            from core.database import get_database
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
                    'options': {},  # 数据库中没有存储options
                    'retry_count': 0,
                    'max_retries': 3
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

            # 更新标题
            title = video_info.get('title', 'Unknown')
            with self.lock:
                self.downloads[download_id]['title'] = title

            # 最后一次检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（开始下载前）: {download_id}")
                return

            # 执行下载
            file_path = self._download_video(download_id, url, video_info, options)

            if file_path and Path(file_path).exists():
                # 处理音频转换
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
                    file_path = final_path or file_path

                # 下载成功
                file_size = Path(file_path).stat().st_size if Path(file_path).exists() else None
                self._update_download_status(download_id, 'completed', 100,
                                           file_path=file_path, file_size=file_size)

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

    def _handle_download_failure(self, download_id: str, error_msg: str):
        """处理下载失败"""
        try:
            # 使用重试管理器判断是否重试
            should_retry = self.retry_manager.should_retry(download_id, error_msg)
            
            if should_retry:
                # 安排重试
                self.retry_manager.schedule_retry(download_id, self._execute_download)
                
                # 更新状态
                retry_info = self.retry_manager.get_retry_info(download_id)
                retry_count = retry_info.get('retry_count', 0) if retry_info else 0
                max_retries = 3  # 默认值
                
                self._update_download_status(download_id, 'retrying', 
                                           error_message=f"重试中 ({retry_count}/{max_retries}): {error_msg}")
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

            if 'youtube.com' in url or 'youtu.be' in url:
                # 使用YouTube策略
                return self.youtube_strategies.download(download_id, url, video_info, options)
            else:
                # 使用通用下载
                return self._generic_download(download_id, url, video_info, options)

        except Exception as e:
            logger.error(f"❌ 视频下载失败: {e}")
            return None
    
    def _generic_download(self, download_id: str, url: str, video_info: Dict[str, Any], options: Dict[str, Any]) -> Optional[str]:
        """通用下载方法"""
        try:
            # 检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（通用下载开始）: {download_id}")
                return None

            import yt_dlp

            # 生成URL哈希用于续传
            url_hash = self._generate_url_hash(url)

            # 基础配置 - 优化续传支持
            ydl_opts = {
                'outtmpl': str(self.output_dir / f'{url_hash}.%(ext)s'),  # 使用URL哈希作为文件名
                'continue_dl': True,  # 明确启用续传
                'nooverwrites': True,  # 不覆盖已存在的文件
                'retries': 5,  # 增加重试次数
                'fragment_retries': 10,  # 分片重试次数
                'skip_unavailable_fragments': False,  # 不跳过不可用的分片
            }

            logger.info(f"🔄 使用续传文件名: {url_hash} (来自URL: {url[:50]}...)")

            # 处理音频下载 - 只下载最佳音频，后续用FFmpeg转换
            quality = options.get('quality', 'best')
            audio_only = options.get('audio_only', False)

            if audio_only or quality.startswith('audio_'):
                # 下载最佳音频质量，后续转换
                ydl_opts['format'] = 'bestaudio/best'
            else:
                # 使用平台配置系统获取格式选择器
                from .platforms import get_platform_for_url
                platform = get_platform_for_url(url)
                ydl_opts['format'] = platform.get_format_selector(quality, url)

            # 添加代理
            proxy = self._get_proxy_config()
            if proxy:
                ydl_opts['proxy'] = proxy

            # 应用PO Token配置 (只对YouTube有效)
            from core.po_token_manager import apply_po_token_to_ytdlp
            ydl_opts = apply_po_token_to_ytdlp(ydl_opts, url, "DownloadManager")

            # 添加进度钩子来检查取消状态
            def progress_hook(d):
                if self._is_cancelled(download_id):
                    logger.info(f"🚫 下载已被取消（下载进行中）: {download_id}")
                    raise yt_dlp.DownloadError("Download cancelled by user")

                if d['status'] == 'downloading':
                    # 更新进度
                    try:
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        downloaded = d.get('downloaded_bytes', 0)
                        if total > 0:
                            progress = int((downloaded / total) * 100)
                            self._update_download_status(download_id, 'downloading', progress)
                    except:
                        pass

            ydl_opts['progress_hooks'] = [progress_hook]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 最后检查是否已被取消
            if self._is_cancelled(download_id):
                logger.info(f"🚫 下载已被取消（下载完成后）: {download_id}")
                return None

            # 查找下载的文件（使用URL哈希）
            for file_path in self.output_dir.glob(f'{url_hash}.*'):
                if file_path.is_file() and not file_path.name.endswith('.part'):
                    logger.info(f"✅ 找到下载文件: {file_path.name}")
                    return str(file_path)

            return None

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

            # 生成输出文件路径
            input_file = Path(input_path)
            output_path = str(input_file.parent / f"{input_file.stem}.{audio_format}")

            # 使用FFmpeg工具转换
            success = self.ffmpeg_tools.extract_audio(
                input_path=input_path,
                output_path=output_path,
                format=audio_format,
                quality=audio_quality
            )

            if success and Path(output_path).exists():
                logger.info(f"✅ 音频转换成功: {audio_format} ({audio_quality})")
                return output_path
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
                return self.filename_processor.apply_smart_filename_to_all(download_id, title, Path(file_path).parent)
        except Exception as e:
            logger.error(f"❌ 应用智能文件名失败: {e}")
            return None

    def _get_proxy_config(self) -> Optional[str]:
        """获取代理配置 - 使用统一的代理转换器"""
        try:
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_ytdlp_proxy("DownloadManager")
        except Exception as e:
            logger.debug(f"🔍 获取代理配置失败: {e}")
            return None



    def _save_to_database(self, download_id: str, url: str):
        """保存到数据库"""
        try:
            from core.database import get_database
            db = get_database()
            db.save_download_record(download_id, url)
        except Exception as e:
            logger.warning(f"⚠️ 保存到数据库失败: {e}")

    def _update_database_status(self, download_id: str, status: str, **kwargs):
        """更新数据库状态"""
        try:
            from core.database import get_database
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
                emit(event, data)
        except Exception as e:
            logger.debug(f"🔍 发送事件失败: {e}")

    def _update_download_status(self, download_id: str, status: str, progress: int = None, **kwargs):
        """更新下载状态"""
        try:
            with self.lock:
                if download_id in self.downloads:
                    self.downloads[download_id]['status'] = status
                    if progress is not None:
                        self.downloads[download_id]['progress'] = progress
                    for key, value in kwargs.items():
                        self.downloads[download_id][key] = value

            # 更新数据库
            self._update_database_status(download_id, status, **kwargs)

            # 发送状态变更事件
            if status == 'completed':
                # 发送下载完成事件
                with self.lock:
                    download_info = self.downloads.get(download_id, {})

                self._emit_event('DOWNLOAD_COMPLETED', {
                    'download_id': download_id,
                    'file_path': kwargs.get('file_path'),
                    'title': download_info.get('title', 'Unknown'),
                    'file_size': kwargs.get('file_size')
                })
                logger.info(f"📡 发送下载完成事件: {download_id}")
            elif status in ['downloading', 'retrying']:
                # 发送进度事件
                self._emit_event('DOWNLOAD_PROGRESS', {
                    'download_id': download_id,
                    'status': status,
                    'progress': progress or 0
                })

        except Exception as e:
            logger.error(f"❌ 更新下载状态失败: {e}")

    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            return {
                'download_manager': {
                    'active_downloads': len([d for d in self.downloads.values() if d['status'] in ['pending', 'downloading']]),
                    'total_downloads': len(self.downloads),
                    'version': 'V2 (Modular)'
                },
                'ffmpeg': self.ffmpeg_tools.get_status(),
                'video_extractor': self.video_extractor.get_extractor_status(),
                'youtube_strategies': self.youtube_strategies.get_strategy_status(),
                'retry_manager': self.retry_manager.get_retry_statistics()
            }
        except Exception as e:
            logger.error(f"❌ 获取系统状态失败: {e}")
            return {'error': str(e)}

    def cleanup(self):
        """清理资源"""
        try:
            if self.executor:
                self.executor.shutdown(wait=True)

            # 清理重试管理器的过期数据
            self.retry_manager.cleanup_old_data()

            logger.info("✅ 下载管理器V2清理完成")
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")


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
