"""
FFmpeg配置管理器 - 跨平台智能配置

自动检测FFmpeg路径并生成适合的yt-dlp配置
"""

import logging
import platform
from pathlib import Path
from typing import Optional, Dict, Any
from .ffmpeg_tools import FFmpegTools

logger = logging.getLogger(__name__)


class FFmpegConfigManager:
    """FFmpeg配置管理器 - 跨平台智能配置"""
    
    def __init__(self):
        self.ffmpeg_tools = FFmpegTools()
        self.system_type = platform.system().lower()
        self._detected_path = None
        self._config_cache = None
        
    def detect_ffmpeg_path(self) -> Optional[str]:
        """检测FFmpeg路径"""
        if self._detected_path:
            return self._detected_path
            
        try:
            # 使用FFmpeg工具检测
            if self.ffmpeg_tools.is_available():
                self._detected_path = self.ffmpeg_tools.get_ffmpeg_path()
                logger.info(f"✅ 检测到FFmpeg路径: {self._detected_path}")
                return self._detected_path
            else:
                logger.warning("⚠️ 未检测到可用的FFmpeg")
                return None
                
        except Exception as e:
            logger.error(f"❌ FFmpeg路径检测失败: {e}")
            return None
    
    def get_ffmpeg_location_for_ytdlp(self) -> Optional[str]:
        """获取适用于yt-dlp的FFmpeg位置配置 - 优先使用相对路径避免中文编码问题"""
        ffmpeg_path = self.detect_ffmpeg_path()
        if not ffmpeg_path:
            return None

        try:
            # 转换为yt-dlp可用的路径格式
            path_obj = Path(ffmpeg_path)

            # 确保路径存在
            if not path_obj.exists():
                logger.warning(f"⚠️ FFmpeg路径不存在: {ffmpeg_path}")
                return None

            # 获取目录路径（yt-dlp需要目录，不是可执行文件）
            if path_obj.is_file():
                ffmpeg_dir = path_obj.parent
            else:
                ffmpeg_dir = path_obj

            # 尝试转换为相对路径，避免中文路径编码问题
            try:
                current_dir = Path.cwd()
                relative_path = ffmpeg_dir.relative_to(current_dir)

                # 跨平台路径处理：统一使用正斜杠
                relative_path_str = str(relative_path).replace('\\', '/')
                logger.info(f"✅ 使用跨平台相对路径: {relative_path_str}")
                return relative_path_str
            except ValueError:
                # 如果无法转换为相对路径，使用绝对路径
                abs_path_str = str(ffmpeg_dir).replace('\\', '/')
                logger.warning(f"⚠️ 无法转换为相对路径，使用跨平台绝对路径: {abs_path_str}")
                return abs_path_str

        except Exception as e:
            logger.error(f"❌ 转换FFmpeg路径失败: {e}")
            return None
    
    def generate_ytdlp_config(self) -> Dict[str, Any]:
        """生成yt-dlp配置"""
        if self._config_cache:
            return self._config_cache
            
        config = {}
        
        # 检测FFmpeg并添加配置
        ffmpeg_location = self.get_ffmpeg_location_for_ytdlp()
        if ffmpeg_location:
            config['ffmpeg_location'] = ffmpeg_location
            config['merge_output_format'] = 'mp4'
            logger.info(f"✅ 生成FFmpeg配置: {ffmpeg_location}")
        else:
            logger.warning("⚠️ 未找到FFmpeg，跳过合并配置")
        
        self._config_cache = config
        return config
    
    def update_ytdlp_conf_file(self, conf_path: str = "yt-dlp.conf") -> bool:
        """更新yt-dlp.conf文件"""
        try:
            ffmpeg_location = self.get_ffmpeg_location_for_ytdlp()
            if not ffmpeg_location:
                logger.warning("⚠️ 未找到FFmpeg，不更新配置文件")
                return False
            
            conf_file = Path(conf_path)
            
            # 读取现有配置
            lines = []
            if conf_file.exists():
                with open(conf_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            # 移除旧的FFmpeg配置
            lines = [line for line in lines if not line.strip().startswith('--ffmpeg-location')]
            lines = [line for line in lines if not line.strip().startswith('--merge-output-format')]

            # 确保移除了旧配置
            logger.debug(f"🔧 移除旧FFmpeg配置后剩余 {len(lines)} 行")
            
            # 添加新的FFmpeg配置
            # 找到合适的位置插入（在output之后）
            insert_index = 0
            for i, line in enumerate(lines):
                if line.strip().startswith('--output'):
                    insert_index = i + 1
                    break
            
            # 插入FFmpeg配置
            new_lines = [
                f'--ffmpeg-location "{ffmpeg_location}"\n',
                '--merge-output-format mp4\n'
            ]
            
            for i, new_line in enumerate(new_lines):
                lines.insert(insert_index + i, new_line)
            
            # 写回文件
            with open(conf_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            logger.info(f"✅ 更新yt-dlp.conf文件: {conf_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新yt-dlp.conf文件失败: {e}")
            return False
    
    def get_platform_specific_config(self) -> Dict[str, Any]:
        """获取平台特定的配置"""
        config = {}

        if self.system_type == 'windows':
            # Windows特定配置
            config.update({
                'prefer_ffmpeg': True,
                'ffmpeg_args': ['-hide_banner', '-loglevel', 'warning'],
                'path_separator': '/',  # 统一使用正斜杠
                'encoding_fix': True,   # 启用编码修复
            })
        elif self.system_type == 'darwin':  # macOS
            # macOS特定配置
            config.update({
                'prefer_ffmpeg': True,
                'ffmpeg_args': ['-hide_banner', '-loglevel', 'warning'],
                'path_separator': '/',
                'encoding_fix': False,  # macOS通常不需要编码修复
            })
        else:  # Linux/容器
            # Linux特定配置
            config.update({
                'prefer_ffmpeg': True,
                'ffmpeg_args': ['-hide_banner', '-loglevel', 'warning'],
                'path_separator': '/',
                'encoding_fix': False,  # Linux通常不需要编码修复
                'container_support': True,  # 容器环境支持
            })

        return config
    
    def get_status(self) -> Dict[str, Any]:
        """获取FFmpeg配置状态"""
        ffmpeg_path = self.detect_ffmpeg_path()
        ffmpeg_location = self.get_ffmpeg_location_for_ytdlp()
        
        return {
            'ffmpeg_available': ffmpeg_path is not None,
            'ffmpeg_path': ffmpeg_path,
            'ffmpeg_location_for_ytdlp': ffmpeg_location,
            'system_type': self.system_type,
            'config_ready': ffmpeg_location is not None,
            'ffmpeg_version': self.ffmpeg_tools.get_ffmpeg_version() if self.ffmpeg_tools.is_available() else None
        }
    
    def test_ffmpeg_integration(self) -> Dict[str, Any]:
        """测试FFmpeg集成 - 跨平台兼容性测试"""
        try:
            status = self.get_status()
            platform_config = self.get_platform_specific_config()

            if not status['ffmpeg_available']:
                return {
                    'success': False,
                    'error': 'FFmpeg不可用',
                    'status': status,
                    'platform': self.system_type,
                    'platform_config': platform_config
                }

            # 测试FFmpeg命令
            result = self.ffmpeg_tools.run_ffmpeg_command(['-version'])

            # 跨平台路径测试
            path_test = self._test_path_compatibility()

            return {
                'success': result['success'] and path_test['success'],
                'ffmpeg_version': self.ffmpeg_tools.get_ffmpeg_version(),
                'status': status,
                'platform': self.system_type,
                'platform_config': platform_config,
                'path_test': path_test,
                'test_result': result
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status': self.get_status(),
                'platform': self.system_type
            }

    def _test_path_compatibility(self) -> Dict[str, Any]:
        """测试路径兼容性"""
        try:
            ffmpeg_location = self.get_ffmpeg_location_for_ytdlp()
            if not ffmpeg_location:
                return {
                    'success': False,
                    'error': '无法获取FFmpeg路径'
                }

            # 测试路径是否存在
            path_obj = Path(ffmpeg_location)
            if not path_obj.exists():
                return {
                    'success': False,
                    'error': f'FFmpeg路径不存在: {ffmpeg_location}'
                }

            # 测试路径格式
            is_relative = not path_obj.is_absolute()
            has_backslash = '\\' in ffmpeg_location

            return {
                'success': True,
                'ffmpeg_location': ffmpeg_location,
                'is_relative': is_relative,
                'has_backslash': has_backslash,
                'platform_compatible': not has_backslash,  # 跨平台兼容应该没有反斜杠
                'path_exists': True
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# 全局实例
_ffmpeg_config_manager = None

def get_ffmpeg_config_manager() -> FFmpegConfigManager:
    """获取FFmpeg配置管理器实例"""
    global _ffmpeg_config_manager
    if _ffmpeg_config_manager is None:
        _ffmpeg_config_manager = FFmpegConfigManager()
    return _ffmpeg_config_manager

def get_ffmpeg_path_for_ytdlp() -> Optional[str]:
    """获取适用于yt-dlp的FFmpeg路径"""
    manager = get_ffmpeg_config_manager()
    return manager.get_ffmpeg_location_for_ytdlp()

def update_ytdlp_config_file() -> bool:
    """更新yt-dlp配置文件"""
    manager = get_ffmpeg_config_manager()
    return manager.update_ytdlp_conf_file()
