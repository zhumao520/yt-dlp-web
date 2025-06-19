# -*- coding: utf-8 -*-
"""
Telegram推送基础类 - 参考ytdlbot架构
"""

import hashlib
import json
import logging
import tempfile
import uuid
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Any, List, Optional, Union
import threading
import time

logger = logging.getLogger(__name__)


class BaseUploader(ABC):
    """基础上传器抽象类 - 参考ytdlbot的BaseDownloader设计"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._tempdir = tempfile.TemporaryDirectory(prefix="telegram-upload-")
        self._cache = {}
        self._lock = threading.RLock()
        self._upload_progress = {}
        
    def __del__(self):
        """清理临时目录"""
        try:
            self._tempdir.cleanup()
        except:
            pass
    
    @abstractmethod
    def send_message(self, message: str, parse_mode: str = None) -> bool:
        """发送文本消息"""
        pass
    
    @abstractmethod
    def send_file(self, file_path: str, caption: str = None, **kwargs) -> bool:
        """发送文件"""
        pass
    
    @abstractmethod
    def send_media_group(self, files: List[str], caption: str = None) -> bool:
        """发送媒体组"""
        pass
    
    def upload_hook(self, current: int, total: int, file_id: str = None):
        """上传进度回调"""
        if file_id:
            with self._lock:
                self._upload_progress[file_id] = {
                    'current': current,
                    'total': total,
                    'percent': (current / total) * 100 if total > 0 else 0,
                    'timestamp': time.time()
                }
        
        # 生成进度条文本
        text = self._generate_progress_text("上传中...", total, current)
        self._update_progress_display(text, file_id)
    
    def _generate_progress_text(self, desc: str, total: int, current: int, 
                               speed: str = "", eta: str = "") -> str:
        """生成进度条文本 - 参考ytdlbot的tqdm样式"""
        if total <= 0:
            return f"{desc} 准备中..."
        
        percent = (current / total) * 100
        bar_length = 20
        filled_length = int(bar_length * current // total)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # 格式化文件大小
        def format_bytes(bytes_val):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f}{unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f}TB"
        
        current_str = format_bytes(current)
        total_str = format_bytes(total)
        
        text = f"""
{desc}
[{bar}] {percent:.1f}%
{current_str}/{total_str}
{f"速度: {speed}" if speed else ""}
{f"剩余: {eta}" if eta else ""}
        """.strip()
        
        return text
    
    @abstractmethod
    def _update_progress_display(self, text: str, file_id: str = None):
        """更新进度显示"""
        pass
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                return {}
            
            metadata = {
                'filename': file_path_obj.name,
                'size': file_path_obj.stat().st_size,
                'size_mb': file_path_obj.stat().st_size / (1024 * 1024),
                'extension': file_path_obj.suffix.lower(),
                'mime_type': self._get_mime_type(file_path_obj),
                'file_type': self._detect_file_type(file_path_obj)
            }
            
            # 如果是视频文件，获取视频信息
            if metadata['file_type'] == 'video':
                video_info = self._get_video_metadata(file_path)
                metadata.update(video_info)
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ 获取文件元数据失败: {e}")
            return {}
    
    def _get_mime_type(self, file_path: Path) -> str:
        """获取MIME类型"""
        try:
            import filetype
            mime = filetype.guess_mime(str(file_path))
            return mime or 'application/octet-stream'
        except:
            return 'application/octet-stream'
    
    def _detect_file_type(self, file_path: Path) -> str:
        """检测文件类型"""
        mime_type = self._get_mime_type(file_path)
        extension = file_path.suffix.lower()
        
        # 视频文件
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', 
                           '.webm', '.m4v', '.3gp', '.ogv', '.ts', '.m2ts'}
        if 'video' in mime_type or extension in video_extensions:
            return 'video'
        
        # 音频文件
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
        if 'audio' in mime_type or extension in audio_extensions:
            return 'audio'
        
        # 图片文件
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if 'image' in mime_type or extension in image_extensions:
            return 'photo'
        
        # 默认为文档
        return 'document'
    
    def _get_video_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取视频元数据"""
        try:
            import subprocess
            import json
            
            # 使用ffprobe获取视频信息
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # 提取视频流信息
                video_stream = None
                audio_stream = None
                
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video' and not video_stream:
                        video_stream = stream
                    elif stream.get('codec_type') == 'audio' and not audio_stream:
                        audio_stream = stream
                
                metadata = {}
                
                if video_stream:
                    metadata.update({
                        'width': video_stream.get('width', 0),
                        'height': video_stream.get('height', 0),
                        'duration': float(video_stream.get('duration', 0)),
                        'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                        'video_codec': video_stream.get('codec_name', 'unknown')
                    })
                
                if audio_stream:
                    metadata.update({
                        'audio_codec': audio_stream.get('codec_name', 'unknown'),
                        'sample_rate': audio_stream.get('sample_rate', 0)
                    })
                
                # 格式信息
                format_info = data.get('format', {})
                if 'duration' in format_info and 'duration' not in metadata:
                    metadata['duration'] = float(format_info['duration'])
                
                return metadata
            
        except Exception as e:
            logger.warning(f"⚠️ 获取视频元数据失败: {e}")
        
        return {'width': 0, 'height': 0, 'duration': 0}
    
    def _generate_thumbnail(self, video_path: str) -> Optional[str]:
        """生成视频缩略图"""
        try:
            import subprocess
            
            video_path_obj = Path(video_path)
            thumb_path = Path(self._tempdir.name) / f"{uuid.uuid4().hex}_thumb.jpg"
            
            # 使用ffmpeg生成缩略图
            cmd = [
                'ffmpeg', '-i', str(video_path_obj), '-ss', '00:00:01.000',
                '-vframes', '1', '-vf', 'scale=320:240:force_original_aspect_ratio=decrease',
                str(thumb_path), '-y'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and thumb_path.exists():
                return str(thumb_path)
            
        except Exception as e:
            logger.warning(f"⚠️ 生成缩略图失败: {e}")
        
        return None
    
    def _calc_file_key(self, file_path: str, options: Dict[str, Any] = None) -> str:
        """计算文件缓存键"""
        h = hashlib.md5()
        h.update(file_path.encode())
        if options:
            h.update(json.dumps(options, sort_keys=True).encode())
        return h.hexdigest()
    
    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """获取缓存"""
        with self._lock:
            return self._cache.get(key)
    
    def _set_cache(self, key: str, value: Dict[str, Any]):
        """设置缓存"""
        with self._lock:
            self._cache[key] = value
            
            # 限制缓存大小
            if len(self._cache) > 1000:
                # 删除最旧的一半缓存
                keys = list(self._cache.keys())
                for old_key in keys[:500]:
                    del self._cache[old_key]
    
    def should_use_pyrogram(self, file_size_mb: float) -> bool:
        """判断是否应该使用Pyrogram"""
        # 大文件优先使用Pyrogram
        if file_size_mb > self.config.get('file_size_limit', 50):
            return True
        
        # 如果Bot API不可用，使用Pyrogram
        if not self.config.get('bot_token'):
            return True
        
        return False
    
    def cleanup(self):
        """清理资源"""
        try:
            self._tempdir.cleanup()
            with self._lock:
                self._cache.clear()
                self._upload_progress.clear()
        except Exception as e:
            logger.error(f"❌ 清理资源失败: {e}")


class TelegramUploadResult:
    """上传结果类"""
    
    def __init__(self, success: bool = False, message_id: int = None, 
                 file_id: str = None, error: str = None):
        self.success = success
        self.message_id = message_id
        self.file_id = file_id
        self.error = error
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message_id': self.message_id,
            'file_id': self.file_id,
            'error': self.error,
            'timestamp': self.timestamp
        }
