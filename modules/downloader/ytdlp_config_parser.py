"""
yt-dlp 配置文件解析器
将 yt-dlp.conf 文件的内容转换为 yt-dlp 可用的选项字典
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _parse_size_string(size_str: str) -> int:
    """解析大小字符串为字节数

    支持的格式：
    - "10M" -> 10 * 1024 * 1024
    - "1G" -> 1 * 1024 * 1024 * 1024
    - "512K" -> 512 * 1024
    - "1024" -> 1024 (纯数字)
    """
    try:
        size_str = size_str.strip().upper()

        # 如果是纯数字，直接返回
        if size_str.isdigit():
            return int(size_str)

        # 解析带单位的大小
        if size_str.endswith('K'):
            return int(float(size_str[:-1]) * 1024)
        elif size_str.endswith('M'):
            return int(float(size_str[:-1]) * 1024 * 1024)
        elif size_str.endswith('G'):
            return int(float(size_str[:-1]) * 1024 * 1024 * 1024)
        else:
            # 尝试作为纯数字解析
            return int(float(size_str))

    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ 无法解析大小字符串 '{size_str}': {e}，使用默认值 10MB")
        return 10 * 1024 * 1024  # 默认 10MB


class YtdlpConfigParser:
    """yt-dlp 配置文件解析器"""
    
    def __init__(self, config_path: str = "yt-dlp.conf"):
        self.config_path = Path(config_path)
        self._config_cache = None
    
    def parse_config_file(self) -> Dict[str, Any]:
        """解析配置文件并返回 yt-dlp 选项字典"""
        if self._config_cache is not None:
            return self._config_cache
        
        if not self.config_path.exists():
            logger.warning(f"⚠️ 配置文件不存在: {self.config_path}")
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            options = {}
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 解析选项
                try:
                    self._parse_option_line(line, options)
                except Exception as e:
                    logger.warning(f"⚠️ 解析配置行失败 (第{line_num}行): {line} - {e}")
            
            self._config_cache = options
            logger.info(f"✅ 解析配置文件成功: {len(options)} 个选项")
            
            return options
            
        except Exception as e:
            logger.error(f"❌ 解析配置文件失败: {e}")
            return {}
    
    def _parse_option_line(self, line: str, options: Dict[str, Any]) -> None:
        """解析单行配置选项"""
        
        # 移除前导的 --
        if line.startswith('--'):
            line = line[2:]
        
        # 分割选项名和值
        if ' ' in line:
            parts = line.split(' ', 1)
            option_name = parts[0]
            option_value = parts[1].strip()
            
            # 移除引号
            if option_value.startswith('"') and option_value.endswith('"'):
                option_value = option_value[1:-1]
            elif option_value.startswith("'") and option_value.endswith("'"):
                option_value = option_value[1:-1]
        else:
            option_name = line
            option_value = True  # 布尔选项
        
        # 转换选项名（将连字符转换为下划线）
        python_option_name = option_name.replace('-', '_')
        
        # 特殊处理某些选项
        if python_option_name == 'no_keep_video':
            options['keepvideo'] = False
        elif python_option_name == 'keep_video':
            options['keepvideo'] = True
        elif python_option_name == 'no_warnings':
            options['no_warnings'] = True
        elif python_option_name == 'ignore_errors':
            options['ignoreerrors'] = True
        elif python_option_name == 'no_overwrites':
            options['nooverwrites'] = True
        elif python_option_name == 'continue':
            options['continue_dl'] = True
        elif python_option_name == 'no_part':
            options['nopart'] = True
        elif python_option_name == 'keep_fragments':
            options['keep_fragments'] = True
        elif python_option_name == 'no_keep_fragments':
            options['keep_fragments'] = False
        elif python_option_name == 'output':
            options['outtmpl'] = option_value
        elif python_option_name == 'format':
            options['format'] = option_value
        elif python_option_name == 'merge_output_format':
            options['merge_output_format'] = option_value
        elif python_option_name == 'ffmpeg_location':
            options['ffmpeg_location'] = option_value
        elif python_option_name == 'retries':
            options['retries'] = int(option_value)
        elif python_option_name == 'fragment_retries':
            options['fragment_retries'] = int(option_value)
        elif python_option_name == 'file_access_retries':
            options['file_access_retries'] = int(option_value)
        elif python_option_name == 'socket_timeout':
            options['socket_timeout'] = int(option_value)
        elif python_option_name == 'retry_sleep':
            options['retry_sleep'] = int(option_value)
        elif python_option_name == 'http_chunk_size':
            # 解析大小字符串（如 "10M", "1G", "512K"）为字节数
            options['http_chunk_size'] = _parse_size_string(option_value)
        elif python_option_name == 'concurrent_fragments':
            options['concurrent_fragments'] = int(option_value)
        elif python_option_name == 'hls_prefer_native':
            options['hls_prefer_native'] = True
        elif python_option_name == 'hls_use_mpegts':
            options['hls_use_mpegts'] = True
        else:
            # 其他选项直接使用转换后的名称
            if isinstance(option_value, str) and option_value.isdigit():
                options[python_option_name] = int(option_value)
            else:
                options[python_option_name] = option_value
    
    def get_config_for_ytdlp(self, base_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取适用于 yt-dlp 的配置选项"""
        config_options = self.parse_config_file()
        
        if base_options:
            # 合并基础选项和配置文件选项（配置文件优先级更低）
            merged_options = config_options.copy()
            merged_options.update(base_options)
            return merged_options
        else:
            return config_options
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache = None
    
    def reload_config(self) -> Dict[str, Any]:
        """重新加载配置"""
        self.clear_cache()
        return self.parse_config_file()


# 全局实例
_config_parser = None

def get_ytdlp_config_parser() -> YtdlpConfigParser:
    """获取全局配置解析器实例"""
    global _config_parser
    if _config_parser is None:
        _config_parser = YtdlpConfigParser()
    return _config_parser

def get_ytdlp_config_options(base_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """便捷函数：获取 yt-dlp 配置选项"""
    parser = get_ytdlp_config_parser()
    return parser.get_config_for_ytdlp(base_options)

def reload_ytdlp_config() -> Dict[str, Any]:
    """便捷函数：重新加载配置"""
    parser = get_ytdlp_config_parser()
    return parser.reload_config()
