"""
yt-dlp 默认配置
如果不使用配置文件，这里定义所有默认的 yt-dlp 选项
"""

from typing import Dict, Any

# 默认的 yt-dlp 配置选项
DEFAULT_YTDLP_OPTIONS = {
    # 文件清理配置 - 解决多余文件问题
    'keepvideo': False,  # 相当于 --no-keep-video
    
    # 网络优化配置
    'fragment_retries': 3,
    'retry_sleep': 2,
    'socket_timeout': 30,
    'file_access_retries': 2,
    'http_chunk_size': '10M',
    'concurrent_fragments': 4,
    
    # HLS/m3u8 优化
    'hls_prefer_native': True,
    'hls_use_mpegts': True,
    
    # 输出配置
    'no_warnings': True,
    'ignoreerrors': True,
    'continue_dl': True,
    'nooverwrites': True,
    'nopart': True,
}

def get_default_ytdlp_options(base_options: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    获取默认的 yt-dlp 选项
    
    Args:
        base_options: 基础选项，会覆盖默认选项
        
    Returns:
        合并后的选项字典
    """
    options = DEFAULT_YTDLP_OPTIONS.copy()
    
    if base_options:
        options.update(base_options)
    
    return options
