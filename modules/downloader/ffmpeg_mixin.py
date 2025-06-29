"""
FFmpeg智能检测混入类 - 为所有下载器提供统一的FFmpeg完成检测
"""

import logging
from typing import Dict, Any, Optional, List
from .ffmpeg_tools import FFmpegTools

logger = logging.getLogger(__name__)


class FFmpegSmartDetectionMixin:
    """FFmpeg智能检测混入类 - 统一的FFmpeg完成检测机制"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ffmpeg_tools = FFmpegTools()
    
    def setup_ffmpeg_detection_for_ytdlp(self, ydl_opts: Dict[str, Any]) -> Dict[str, Any]:
        """为yt-dlp设置FFmpeg智能检测"""
        try:
            # 记录开始时的FFmpeg进程
            initial_ffmpeg_pids = self._ffmpeg_tools.get_ffmpeg_processes()
            
            # 创建后处理钩子事件
            hook_events = self._ffmpeg_tools.create_postprocessor_hooks()
            postprocessor_hook = self._ffmpeg_tools.create_postprocessor_hook_callback(hook_events)
            
            # 添加钩子到yt-dlp选项
            if 'postprocessor_hooks' not in ydl_opts:
                ydl_opts['postprocessor_hooks'] = []
            ydl_opts['postprocessor_hooks'].append(postprocessor_hook)
            
            # 存储检测信息供后续使用
            detection_info = {
                'hook_events': hook_events,
                'initial_ffmpeg_pids': initial_ffmpeg_pids
            }
            
            return detection_info
            
        except Exception as e:
            logger.error(f"❌ 设置FFmpeg检测失败: {e}")
            return {}
    
    def wait_for_ffmpeg_completion(self, detection_info: Dict[str, Any]) -> None:
        """等待FFmpeg完成 - 使用检测信息"""
        try:
            if not detection_info:
                # 降级到固定等待
                logger.warning("⚠️ 无FFmpeg检测信息，使用固定等待")
                import time
                time.sleep(2.0)
                return
            
            hook_events = detection_info.get('hook_events')
            initial_ffmpeg_pids = detection_info.get('initial_ffmpeg_pids')
            
            # 使用FFmpeg工具的智能等待
            self._ffmpeg_tools.wait_for_ffmpeg_completion(
                postprocessing_started=hook_events.get('started') if hook_events else None,
                postprocessing_completed=hook_events.get('completed') if hook_events else None,
                initial_ffmpeg_pids=initial_ffmpeg_pids
            )
            
        except Exception as e:
            logger.error(f"❌ 等待FFmpeg完成失败: {e}")
            # 降级到固定等待
            import time
            time.sleep(2.0)
    
    def setup_ffmpeg_detection_for_generic(self) -> Dict[str, Any]:
        """为通用下载器设置FFmpeg检测（不使用yt-dlp钩子）"""
        try:
            # 记录开始时的FFmpeg进程
            initial_ffmpeg_pids = self._ffmpeg_tools.get_ffmpeg_processes()
            
            return {
                'initial_ffmpeg_pids': initial_ffmpeg_pids,
                'start_time': __import__('time').time()
            }
            
        except Exception as e:
            logger.error(f"❌ 设置通用FFmpeg检测失败: {e}")
            return {}
    
    def wait_for_ffmpeg_completion_generic(self, detection_info: Dict[str, Any], 
                                         expected_output_file: Optional[str] = None) -> None:
        """等待FFmpeg完成 - 通用方法（不依赖yt-dlp钩子）"""
        try:
            import time
            from pathlib import Path
            
            if not detection_info:
                logger.warning("⚠️ 无FFmpeg检测信息，使用固定等待")
                time.sleep(2.0)
                return
            
            initial_ffmpeg_pids = detection_info.get('initial_ffmpeg_pids', [])
            start_time = detection_info.get('start_time', time.time())
            
            logger.info("⏳ 开始通用FFmpeg完成检测...")
            
            # 方法1：进程监控
            if initial_ffmpeg_pids is not None:
                self._ffmpeg_tools.wait_for_ffmpeg_processes(initial_ffmpeg_pids)
            
            # 方法2：文件监控（如果提供了输出文件路径）
            if expected_output_file:
                self._wait_for_file_completion(expected_output_file, start_time)
            
            # 方法3：最小等待时间
            logger.info("⏳ 额外等待1秒确保文件系统同步...")
            time.sleep(1.0)
            
        except Exception as e:
            logger.error(f"❌ 通用FFmpeg等待失败: {e}")
            time.sleep(2.0)
    
    def _wait_for_file_completion(self, file_path: str, start_time: float, 
                                max_wait: int = 300) -> None:
        """等待文件完成写入"""
        try:
            import time
            from pathlib import Path
            
            file_obj = Path(file_path)
            last_size = 0
            stable_count = 0
            check_interval = 1.0
            
            logger.info(f"🔍 监控文件完成: {file_obj.name}")
            
            while time.time() - start_time < max_wait:
                if file_obj.exists():
                    current_size = file_obj.stat().st_size
                    
                    if current_size == last_size and current_size > 0:
                        stable_count += 1
                        if stable_count >= 3:  # 文件大小稳定3秒
                            logger.info(f"✅ 文件写入完成: {file_obj.name} ({current_size} bytes)")
                            break
                    else:
                        stable_count = 0
                        last_size = current_size
                
                time.sleep(check_interval)
            
        except Exception as e:
            logger.debug(f"⚠️ 文件监控失败: {e}")
    
    def is_ffmpeg_required(self, options: Dict[str, Any]) -> bool:
        """判断是否需要FFmpeg处理"""
        try:
            # 检查是否需要音频转换
            if options.get('audio_only', False):
                return True
            
            # 检查是否需要格式转换
            if options.get('format_conversion', False):
                return True
            
            # 检查是否需要合并视频音频
            quality = options.get('quality', '')
            if 'best' in quality and '+' in quality:  # 如 bestvideo+bestaudio
                return True
            
            # 检查是否有后处理器配置
            if options.get('postprocessors'):
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"⚠️ 判断FFmpeg需求失败: {e}")
            return True  # 保守估计，假设需要FFmpeg
    
    def get_ffmpeg_status(self) -> Dict[str, Any]:
        """获取FFmpeg状态"""
        return self._ffmpeg_tools.get_status()


# 便捷函数
def create_ffmpeg_detection_mixin():
    """创建FFmpeg检测混入实例"""
    return FFmpegSmartDetectionMixin()


def apply_ffmpeg_smart_detection(downloader_class):
    """装饰器：为下载器类添加FFmpeg智能检测功能"""
    
    class SmartFFmpegDownloader(FFmpegSmartDetectionMixin, downloader_class):
        """带FFmpeg智能检测的下载器"""
        pass
    
    # 保持原类名和模块信息
    SmartFFmpegDownloader.__name__ = downloader_class.__name__
    SmartFFmpegDownloader.__module__ = downloader_class.__module__
    SmartFFmpegDownloader.__qualname__ = downloader_class.__qualname__
    
    return SmartFFmpegDownloader
