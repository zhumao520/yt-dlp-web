# -*- coding: utf-8 -*-
"""
FFmpeg工具模块

跨平台FFmpeg检测、管理和使用工具
"""

import logging
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class FFmpegTools:
    """FFmpeg工具类"""
    
    def __init__(self):
        self._ffmpeg_path = None
        self._ffmpeg_version = None
        self._system_type = platform.system().lower()
        
        # 初始化时检测FFmpeg
        self._detect_ffmpeg()
    
    def _detect_ffmpeg(self):
        """检测FFmpeg可执行文件"""
        try:
            logger.debug(f"🖥️ 检测到系统类型: {self._system_type}")
            
            # 1. 优先检查系统PATH中的FFmpeg
            system_ffmpeg = shutil.which('ffmpeg')
            if system_ffmpeg and self._verify_ffmpeg(system_ffmpeg):
                self._ffmpeg_path = str(Path(system_ffmpeg).parent.absolute())
                logger.info(f"✅ 找到系统FFmpeg: {system_ffmpeg}")
                return
            
            # 2. 检查项目目录中的FFmpeg
            project_paths = self._get_project_ffmpeg_paths()
            for project_ffmpeg in project_paths:
                if project_ffmpeg.exists() and self._verify_ffmpeg(str(project_ffmpeg)):
                    self._ffmpeg_path = str(project_ffmpeg.parent.absolute())
                    logger.info(f"✅ 找到项目FFmpeg: {project_ffmpeg.absolute()}")
                    return
            
            # 3. 检查常见安装位置
            common_paths = self._get_common_ffmpeg_paths()
            for common_ffmpeg in common_paths:
                if common_ffmpeg.exists() and self._verify_ffmpeg(str(common_ffmpeg)):
                    self._ffmpeg_path = str(common_ffmpeg.parent.absolute())
                    logger.info(f"✅ 找到常见位置FFmpeg: {common_ffmpeg}")
                    return
            
            logger.warning("⚠️ 未找到FFmpeg，某些功能可能不可用")
            
        except Exception as e:
            logger.error(f"❌ FFmpeg检测失败: {e}")
    
    def _verify_ffmpeg(self, ffmpeg_path: str) -> bool:
        """验证FFmpeg是否可用"""
        try:
            result = subprocess.run(
                [ffmpeg_path, '-version'],
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                # 提取版本信息
                version_line = result.stdout.split('\n')[0]
                if 'ffmpeg version' in version_line.lower():
                    self._ffmpeg_version = version_line
                    logger.debug(f"📋 FFmpeg版本: {version_line}")
                    return True
            
            return False
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            return False
        except Exception as e:
            logger.debug(f"🔍 FFmpeg验证异常: {e}")
            return False
    
    def _get_project_ffmpeg_paths(self) -> List[Path]:
        """获取项目目录中的FFmpeg路径"""
        if self._system_type == 'windows':
            return [
                Path("ffmpeg/bin/ffmpeg.exe"),
                Path("ffmpeg/ffmpeg.exe"),
                Path("bin/ffmpeg.exe"),
            ]
        else:
            return [
                Path("ffmpeg/bin/ffmpeg"),
                Path("ffmpeg/ffmpeg"),
                Path("bin/ffmpeg"),
            ]
    
    def _get_common_ffmpeg_paths(self) -> List[Path]:
        """获取常见安装位置的FFmpeg路径"""
        if self._system_type == 'windows':
            return [
                Path("C:/ffmpeg/bin/ffmpeg.exe"),
                Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
                Path("C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe"),
                Path.home() / "ffmpeg/bin/ffmpeg.exe",
                Path("C:/tools/ffmpeg/bin/ffmpeg.exe"),  # Chocolatey
            ]
        elif self._system_type == 'darwin':  # macOS
            return [
                Path("/usr/local/bin/ffmpeg"),  # Homebrew
                Path("/opt/homebrew/bin/ffmpeg"),  # Apple Silicon Homebrew
                Path("/usr/bin/ffmpeg"),
                Path("/opt/local/bin/ffmpeg"),  # MacPorts
                Path.home() / "ffmpeg/bin/ffmpeg",
            ]
        else:  # Linux/容器
            return [
                Path("/usr/bin/ffmpeg"),
                Path("/usr/local/bin/ffmpeg"),
                Path("/opt/ffmpeg/bin/ffmpeg"),
                Path("/snap/bin/ffmpeg"),  # Snap
                Path.home() / "ffmpeg/bin/ffmpeg",
                Path("/app/ffmpeg/bin/ffmpeg"),  # 容器环境
            ]
    
    def get_ffmpeg_path(self) -> Optional[str]:
        """获取FFmpeg路径"""
        return self._ffmpeg_path
    
    def get_ffmpeg_version(self) -> Optional[str]:
        """获取FFmpeg版本信息"""
        return self._ffmpeg_version
    
    def is_available(self) -> bool:
        """检查FFmpeg是否可用"""
        return self._ffmpeg_path is not None
    
    def get_ffmpeg_executable(self) -> Optional[str]:
        """获取FFmpeg可执行文件完整路径"""
        if not self._ffmpeg_path:
            return None
        
        if self._system_type == 'windows':
            return str(Path(self._ffmpeg_path) / "ffmpeg.exe")
        else:
            return str(Path(self._ffmpeg_path) / "ffmpeg")
    
    def run_ffmpeg_command(self, args: List[str], timeout: int = 300) -> Dict[str, Any]:
        """运行FFmpeg命令"""
        try:
            ffmpeg_exe = self.get_ffmpeg_executable()
            if not ffmpeg_exe:
                return {
                    'success': False,
                    'error': 'FFmpeg不可用',
                    'returncode': -1
                }
            
            cmd = [ffmpeg_exe] + args
            logger.debug(f"🔧 执行FFmpeg命令: {' '.join(cmd[:5])}...")  # 只显示前5个参数
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': cmd
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'FFmpeg命令超时 ({timeout}秒)',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'returncode': -1
            }
    
    def convert_video(self, input_path: str, output_path: str, options: Dict[str, Any] = None) -> bool:
        """转换视频格式"""
        try:
            args = ['-i', input_path]
            
            # 添加转换选项
            if options:
                if 'codec' in options:
                    args.extend(['-c:v', options['codec']])
                if 'bitrate' in options:
                    args.extend(['-b:v', options['bitrate']])
                if 'resolution' in options:
                    args.extend(['-s', options['resolution']])
                if 'fps' in options:
                    args.extend(['-r', str(options['fps'])])
            
            # 输出文件
            args.extend(['-y', output_path])  # -y 覆盖输出文件
            
            result = self.run_ffmpeg_command(args)
            
            if result['success']:
                logger.info(f"✅ 视频转换成功: {output_path}")
                return True
            else:
                logger.error(f"❌ 视频转换失败: {result.get('error', result.get('stderr', '未知错误'))}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 视频转换异常: {e}")
            return False
    
    def extract_audio(self, input_path: str, output_path: str, format: str = 'mp3') -> bool:
        """提取音频"""
        try:
            args = [
                '-i', input_path,
                '-vn',  # 不包含视频
                '-acodec', 'libmp3lame' if format == 'mp3' else 'copy',
                '-y', output_path
            ]
            
            result = self.run_ffmpeg_command(args)
            
            if result['success']:
                logger.info(f"✅ 音频提取成功: {output_path}")
                return True
            else:
                logger.error(f"❌ 音频提取失败: {result.get('error', result.get('stderr', '未知错误'))}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 音频提取异常: {e}")
            return False
    
    def get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """获取视频信息"""
        try:
            args = [
                '-i', video_path,
                '-hide_banner',
                '-f', 'null',
                '-'
            ]
            
            result = self.run_ffmpeg_command(args)
            
            # FFmpeg的视频信息通常在stderr中
            stderr = result.get('stderr', '')
            
            # 简单解析视频信息
            info = {}
            for line in stderr.split('\n'):
                line = line.strip()
                if 'Duration:' in line:
                    # 提取时长
                    duration_part = line.split('Duration:')[1].split(',')[0].strip()
                    info['duration'] = duration_part
                elif 'Video:' in line:
                    # 提取视频信息
                    info['video_codec'] = line
                elif 'Audio:' in line:
                    # 提取音频信息
                    info['audio_codec'] = line
            
            return info if info else None
            
        except Exception as e:
            logger.error(f"❌ 获取视频信息失败: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取FFmpeg状态信息"""
        return {
            'available': self.is_available(),
            'path': self._ffmpeg_path,
            'version': self._ffmpeg_version,
            'system': self._system_type,
            'executable': self.get_ffmpeg_executable()
        }
