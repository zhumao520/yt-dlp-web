# -*- coding: utf-8 -*-
"""
通用文件名提取工具
用于从URL中提取自定义文件名参数，供所有下载渠道复用
"""

import logging
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def extract_filename_from_url(url: str) -> Optional[str]:
    """
    从URL中提取自定义文件名参数

    Args:
        url: 要解析的URL

    Returns:
        提取到的文件名（不含扩展名），如果没有找到则返回None
    """
    try:
        # 解析URL参数
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 支持的文件名参数（按优先级排序）
        filename_params = [
            'download_filename',  # 最高优先级
            'filename', 
            'name', 
            'title',
            'custom_filename',
            'file_name',
            'video_name'
        ]
        
        for param in filename_params:
            if param in query_params and query_params[param]:
                custom_filename = query_params[param][0]  # 取第一个值
                if custom_filename.strip():
                    # 清理文件名
                    clean_filename = _clean_filename(custom_filename.strip())
                    
                    if clean_filename:
                        logger.info(f"🔧 从URL提取自定义文件名: '{custom_filename}' -> '{clean_filename}'")
                        return clean_filename
        
        return None
        
    except Exception as e:
        logger.debug(f"🔍 URL文件名提取失败: {e}")
        return None


def _clean_filename(filename: str) -> str:
    """
    清理文件名 - 复用现有的专业文件名处理器

    Args:
        filename: 原始文件名

    Returns:
        清理后的文件名
    """
    if not filename:
        return ""

    try:
        # 复用现有的专业文件名处理器
        from modules.downloader.filename_processor import get_filename_processor
        processor = get_filename_processor()

        # 移除常见的视频扩展名（系统会自动添加）
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
        clean_name = filename.strip()

        for ext in video_extensions:
            if clean_name.lower().endswith(ext):
                clean_name = clean_name[:-len(ext)]
                break

        # 使用专业的文件名清理器
        return processor.sanitize_filename(clean_name)

    except Exception as e:
        logger.debug(f"🔍 使用专业清理器失败，使用简单清理: {e}")

        # 降级到简单清理
        clean_name = filename.strip()

        # 移除常见的视频扩展名
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
        for ext in video_extensions:
            if clean_name.lower().endswith(ext):
                clean_name = clean_name[:-len(ext)]
                break

        # 移除不安全的字符
        unsafe_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in unsafe_chars:
            clean_name = clean_name.replace(char, '_')

        # 移除多余的空格和下划线
        clean_name = ' '.join(clean_name.split())
        clean_name = clean_name.replace('__', '_')

        return clean_name.strip()


def apply_url_filename_to_options(url: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """
    将URL中的文件名应用到下载选项中
    
    Args:
        url: 下载URL
        options: 现有的下载选项
        
    Returns:
        更新后的下载选项
    """
    try:
        # 如果已经有自定义文件名，不覆盖（手动输入优先）
        if options.get('custom_filename'):
            logger.debug("🔍 已有自定义文件名，跳过URL提取")
            return options
        
        # 从URL提取文件名
        extracted_filename = extract_filename_from_url(url)
        
        if extracted_filename:
            # 复制选项字典，避免修改原始对象
            updated_options = options.copy()
            updated_options['custom_filename'] = extracted_filename
            
            logger.info(f"🔧 应用URL提取的文件名: '{extracted_filename}'")
            return updated_options
        
        return options
        
    except Exception as e:
        logger.debug(f"🔍 应用URL文件名失败: {e}")
        return options


def get_filename_info(url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    获取文件名信息（用于调试和日志）
    
    Args:
        url: 下载URL
        options: 下载选项
        
    Returns:
        文件名信息字典
    """
    if options is None:
        options = {}
    
    info = {
        'url_has_filename_param': False,
        'extracted_filename': None,
        'manual_filename': options.get('custom_filename', ''),
        'final_filename': options.get('custom_filename', ''),
        'filename_source': 'default'
    }
    
    try:
        # 检查URL是否包含文件名参数
        extracted = extract_filename_from_url(url)
        if extracted:
            info['url_has_filename_param'] = True
            info['extracted_filename'] = extracted
        
        # 确定最终文件名来源
        if info['manual_filename']:
            info['filename_source'] = 'manual'
        elif info['extracted_filename']:
            info['filename_source'] = 'url_extracted'
            info['final_filename'] = info['extracted_filename']
        else:
            info['filename_source'] = 'default'
        
    except Exception as e:
        logger.debug(f"🔍 获取文件名信息失败: {e}")
    
    return info


# 向后兼容的别名
def _extract_filename_from_url(url: str) -> str:
    """向后兼容的函数名"""
    result = extract_filename_from_url(url)
    return result if result else ""
