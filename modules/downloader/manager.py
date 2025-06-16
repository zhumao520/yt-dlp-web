# -*- coding: utf-8 -*-
"""
下载管理器 V2 - 模块化重构版

使用模块化架构，提高代码可维护性和可扩展性
"""

import os
import uuid
import logging
import threading
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
                'max_retries': options.get('max_retries', 3) if options else 3
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
    
    def get_download(self, download_id: str) -> Optional[Dict[str, Any]]:
        """获取下载信息"""
        with self.lock:
            return self.downloads.get(download_id)
    
    def get_all_downloads(self) -> List[Dict[str, Any]]:
        """获取所有下载"""
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

            # 更新状态为下载中
            self._update_download_status(download_id, 'downloading', 0)

            # 提取视频信息
            video_info = self.video_extractor.extract_info(url, options)
            
            if not video_info or video_info.get('error'):
                error_msg = video_info.get('message', '无法获取视频信息') if video_info else '无法获取视频信息'
                self._handle_download_failure(download_id, error_msg)
                return

            # 更新标题
            title = video_info.get('title', 'Unknown')
            with self.lock:
                self.downloads[download_id]['title'] = title

            # 执行下载
            file_path = self._download_video(download_id, url, video_info, options)

            if file_path and Path(file_path).exists():
                # 应用智能文件名
                if options.get('smart_filename', True):
                    final_path = self._apply_smart_filename(file_path, video_info, options)
                    file_path = final_path or file_path
                
                # 下载成功
                self._update_download_status(download_id, 'completed', 100, 
                                           file_path=file_path, completed_at=datetime.now())
                
                # 清理重试数据
                self.retry_manager.clear_retry_data(download_id)
                
                logger.info(f"✅ 下载完成: {download_id} - {title}")
            else:
                self._handle_download_failure(download_id, '下载文件不存在')

        except Exception as e:
            logger.error(f"❌ 下载执行失败 {download_id}: {e}")
            self._handle_download_failure(download_id, str(e))
    
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
            import yt_dlp
            
            ydl_opts = {
                'outtmpl': str(self.output_dir / f'{download_id}.%(ext)s'),
                'format': options.get('quality', 'best'),
            }
            
            # 添加代理
            proxy = self._get_proxy_config()
            if proxy:
                ydl_opts['proxy'] = proxy
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # 查找下载的文件
            for file_path in self.output_dir.glob(f'{download_id}.*'):
                if file_path.is_file():
                    return str(file_path)
            
            return None

        except Exception as e:
            logger.error(f"❌ 通用下载失败: {e}")
            return None

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
        """获取代理配置"""
        try:
            from core.config import get_config
            return get_config('downloader.proxy', None)
        except ImportError:
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
