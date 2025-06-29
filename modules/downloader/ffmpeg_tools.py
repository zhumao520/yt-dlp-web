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
                encoding='utf-8',
                errors='ignore',
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
        """获取项目目录中的FFmpeg路径 - 跨平台智能检测"""
        project_paths = []

        if self._system_type == 'windows':
            # Windows平台路径
            project_paths.extend([
                Path("ffmpeg/bin/ffmpeg.exe"),           # 当前项目标准路径
                Path("ffmpeg/ffmpeg.exe"),               # 简化路径
                Path("bin/ffmpeg.exe"),                  # 根目录bin
                Path("./ffmpeg/bin/ffmpeg.exe"),         # 相对路径
                Path("../ffmpeg/bin/ffmpeg.exe"),        # 上级目录
                Path("tools/ffmpeg/bin/ffmpeg.exe"),     # 工具目录
                Path("external/ffmpeg/bin/ffmpeg.exe"),  # 外部工具
            ])
        elif self._system_type == 'darwin':  # macOS
            # macOS平台路径
            project_paths.extend([
                Path("ffmpeg/bin/ffmpeg"),               # 当前项目标准路径
                Path("ffmpeg/ffmpeg"),                   # 简化路径
                Path("bin/ffmpeg"),                      # 根目录bin
                Path("./ffmpeg/bin/ffmpeg"),             # 相对路径
                Path("../ffmpeg/bin/ffmpeg"),            # 上级目录
                Path("tools/ffmpeg/bin/ffmpeg"),         # 工具目录
                Path("external/ffmpeg/bin/ffmpeg"),      # 外部工具
                Path("/app/ffmpeg/bin/ffmpeg"),          # 容器环境
            ])
        else:  # Linux/容器
            # Linux平台路径
            project_paths.extend([
                Path("ffmpeg/bin/ffmpeg"),               # 当前项目标准路径
                Path("ffmpeg/ffmpeg"),                   # 简化路径
                Path("bin/ffmpeg"),                      # 根目录bin
                Path("./ffmpeg/bin/ffmpeg"),             # 相对路径
                Path("../ffmpeg/bin/ffmpeg"),            # 上级目录
                Path("tools/ffmpeg/bin/ffmpeg"),         # 工具目录
                Path("external/ffmpeg/bin/ffmpeg"),      # 外部工具
                Path("/app/ffmpeg/bin/ffmpeg"),          # 容器环境
                Path("/usr/local/ffmpeg/bin/ffmpeg"),    # 本地安装
                Path("/opt/ffmpeg/bin/ffmpeg"),          # 可选安装
            ])

        return project_paths
    
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
                encoding='utf-8',
                errors='ignore',
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
    
    def extract_audio(self, input_path: str, output_path: str, format: str = 'mp3', quality: str = 'medium') -> bool:
        """提取音频"""
        try:
            args = ['-i', input_path, '-vn']  # 不包含视频

            # 根据格式和质量设置编码器和参数
            if format.lower() == 'mp3':
                args.extend(['-acodec', 'libmp3lame'])
                # MP3 质量设置
                if quality == 'high':
                    args.extend(['-b:a', '320k'])  # 320kbps
                elif quality == 'medium':
                    args.extend(['-b:a', '192k'])  # 192kbps
                elif quality == 'low':
                    args.extend(['-b:a', '128k'])  # 128kbps
                else:
                    args.extend(['-b:a', '192k'])  # 默认

            elif format.lower() == 'aac':
                args.extend(['-acodec', 'aac'])
                # AAC 质量设置
                if quality == 'high':
                    args.extend(['-b:a', '256k'])  # 256kbps
                elif quality == 'medium':
                    args.extend(['-b:a', '128k'])  # 128kbps
                elif quality == 'low':
                    args.extend(['-b:a', '96k'])   # 96kbps
                else:
                    args.extend(['-b:a', '128k'])  # 默认

            elif format.lower() == 'flac':
                args.extend(['-acodec', 'flac'])
                # FLAC 无损，不需要比特率设置

            elif format.lower() == 'ogg':
                args.extend(['-acodec', 'libvorbis'])
                # OGG 质量设置
                if quality == 'high':
                    args.extend(['-q:a', '6'])     # 高质量
                elif quality == 'medium':
                    args.extend(['-q:a', '4'])     # 中等质量
                elif quality == 'low':
                    args.extend(['-q:a', '2'])     # 低质量
                else:
                    args.extend(['-q:a', '4'])     # 默认

            elif format.lower() == 'm4a':
                args.extend(['-acodec', 'aac'])
                # M4A (AAC) 质量设置
                if quality == 'high':
                    args.extend(['-b:a', '256k'])
                elif quality == 'medium':
                    args.extend(['-b:a', '128k'])
                elif quality == 'low':
                    args.extend(['-b:a', '96k'])
                else:
                    args.extend(['-b:a', '128k'])

            else:
                # 默认使用 MP3
                args.extend(['-acodec', 'libmp3lame', '-b:a', '192k'])

            # 添加通用音频设置
            args.extend(['-ar', '44100'])  # 采样率 44.1kHz
            args.extend(['-ac', '2'])      # 立体声
            args.extend(['-y', output_path])  # 覆盖输出文件

            result = self.run_ffmpeg_command(args)

            if result['success']:
                logger.info(f"✅ 音频提取成功: {output_path} (格式: {format.upper()}, 质量: {quality})")
                return True
            else:
                logger.error(f"❌ 音频提取失败: {result.get('error', result.get('stderr', '未知错误'))}")
                return False

        except Exception as e:
            logger.error(f"❌ 音频提取异常: {e}")
            return False

    def convert_audio(self, input_path: str, output_path: str, target_format: str = 'mp3', quality: str = 'medium') -> bool:
        """转换音频格式"""
        try:
            args = ['-i', input_path]

            # 根据目标格式设置编码器
            if target_format.lower() == 'mp3':
                args.extend(['-acodec', 'libmp3lame'])
                if quality == 'high':
                    args.extend(['-b:a', '320k'])
                elif quality == 'medium':
                    args.extend(['-b:a', '192k'])
                else:
                    args.extend(['-b:a', '128k'])

            elif target_format.lower() == 'aac':
                args.extend(['-acodec', 'aac'])
                if quality == 'high':
                    args.extend(['-b:a', '256k'])
                elif quality == 'medium':
                    args.extend(['-b:a', '128k'])
                else:
                    args.extend(['-b:a', '96k'])

            elif target_format.lower() == 'flac':
                args.extend(['-acodec', 'flac'])
                # FLAC 无损，不设置比特率

            elif target_format.lower() == 'ogg':
                args.extend(['-acodec', 'libvorbis'])
                if quality == 'high':
                    args.extend(['-q:a', '6'])
                elif quality == 'medium':
                    args.extend(['-q:a', '4'])
                else:
                    args.extend(['-q:a', '2'])

            # 通用设置
            args.extend(['-ar', '44100', '-ac', '2', '-y', output_path])

            result = self.run_ffmpeg_command(args)

            if result['success']:
                logger.info(f"✅ 音频转换成功: {output_path} ({target_format.upper()}, {quality})")
                return True
            else:
                logger.error(f"❌ 音频转换失败: {result.get('error', result.get('stderr', '未知错误'))}")
                return False

        except Exception as e:
            logger.error(f"❌ 音频转换异常: {e}")
            return False

    def get_supported_audio_formats(self) -> Dict[str, Dict[str, Any]]:
        """获取支持的音频格式"""
        return {
            'mp3': {
                'name': 'MP3',
                'description': '最常用的音频格式，兼容性好',
                'codec': 'libmp3lame',
                'extension': 'mp3',
                'qualities': {
                    'high': {'bitrate': '320k', 'description': '高质量 (320kbps)'},
                    'medium': {'bitrate': '192k', 'description': '中等质量 (192kbps)'},
                    'low': {'bitrate': '128k', 'description': '低质量 (128kbps)'}
                }
            },
            'aac': {
                'name': 'AAC',
                'description': '高效音频编码，质量好文件小',
                'codec': 'aac',
                'extension': 'm4a',
                'qualities': {
                    'high': {'bitrate': '256k', 'description': '高质量 (256kbps)'},
                    'medium': {'bitrate': '128k', 'description': '中等质量 (128kbps)'},
                    'low': {'bitrate': '96k', 'description': '低质量 (96kbps)'}
                }
            },
            'flac': {
                'name': 'FLAC',
                'description': '无损音频格式，文件较大',
                'codec': 'flac',
                'extension': 'flac',
                'qualities': {
                    'lossless': {'description': '无损压缩'}
                }
            },
            'ogg': {
                'name': 'OGG Vorbis',
                'description': '开源音频格式，质量好',
                'codec': 'libvorbis',
                'extension': 'ogg',
                'qualities': {
                    'high': {'quality': '6', 'description': '高质量'},
                    'medium': {'quality': '4', 'description': '中等质量'},
                    'low': {'quality': '2', 'description': '低质量'}
                }
            }
        }

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

    def merge_video_audio(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """合并视频和音频文件"""
        try:
            args = [
                '-i', video_path,  # 输入视频
                '-i', audio_path,  # 输入音频
                '-c:v', 'copy',    # 复制视频流，不重新编码
                '-c:a', 'aac',     # 音频编码为AAC
                '-strict', 'experimental',  # 允许实验性编码器
                '-y',              # 覆盖输出文件
                output_path        # 输出文件
            ]

            logger.info(f"🔧 合并视频和音频: {video_path} + {audio_path} -> {output_path}")

            result = self.run_ffmpeg_command(args, timeout=600)  # 10分钟超时

            if result['success']:
                logger.info(f"✅ 视频音频合并成功: {output_path}")
                return True
            else:
                logger.error(f"❌ 视频音频合并失败: {result.get('error', result.get('stderr', '未知错误'))}")
                return False

        except Exception as e:
            logger.error(f"❌ 视频音频合并异常: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取FFmpeg状态信息"""
        return {
            'available': self.is_available(),
            'path': self._ffmpeg_path,
            'version': self._ffmpeg_version,
            'system': self._system_type,
            'executable': self.get_ffmpeg_executable()
        }


# 全局实例和便捷函数
_ffmpeg_tools = None

def get_ffmpeg_tools() -> FFmpegTools:
    """获取FFmpeg工具实例"""
    global _ffmpeg_tools
    if _ffmpeg_tools is None:
        _ffmpeg_tools = FFmpegTools()
    return _ffmpeg_tools

def get_ffmpeg_path() -> Optional[str]:
    """获取FFmpeg路径的便捷函数"""
    tools = get_ffmpeg_tools()
    return tools.get_ffmpeg_path()

def get_ffmpeg_executable() -> str:
    """获取FFmpeg可执行文件的便捷函数"""
    tools = get_ffmpeg_tools()
    return tools.get_ffmpeg_executable()
