#!/usr/bin/env python3
"""
代理配置助手 - 统一的代理获取接口
消除各下载器中重复的代理获取方法
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ProxyHelper:
    """代理配置助手 - 提供统一的代理获取接口"""
    
    @staticmethod
    def get_ytdlp_proxy(module_name: str = "Unknown") -> Optional[str]:
        """
        获取适用于yt-dlp的代理配置
        
        Args:
            module_name: 调用模块名称，用于日志标识
            
        Returns:
            str: yt-dlp格式的代理URL
            None: 无代理或代理不可用
        """
        try:
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_ytdlp_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取yt-dlp代理配置失败: {e}")
            return None
    
    @staticmethod
    def get_pytubefix_proxy(module_name: str = "Unknown") -> Optional[str]:
        """
        获取适用于PyTubeFix的代理配置
        
        Args:
            module_name: 调用模块名称，用于日志标识
            
        Returns:
            str: PyTubeFix格式的代理URL
            None: 无代理或代理不可用
        """
        try:
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_pytubefix_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取PyTubeFix代理配置失败: {e}")
            return None
    
    @staticmethod
    def get_requests_proxy(module_name: str = "Unknown") -> Optional[Dict[str, str]]:
        """
        获取适用于requests库的代理配置
        
        Args:
            module_name: 调用模块名称，用于日志标识
            
        Returns:
            dict: requests格式的代理配置 {'http': 'proxy_url', 'https': 'proxy_url'}
            None: 无代理或代理不可用
        """
        try:
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_requests_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取requests代理配置失败: {e}")
            return None
    
    @staticmethod
    def get_pyrogram_proxy(module_name: str = "Unknown") -> Optional[Dict[str, Any]]:
        """
        获取适用于Pyrogram的代理配置
        
        Args:
            module_name: 调用模块名称，用于日志标识
            
        Returns:
            dict: Pyrogram格式的代理配置
            None: 无代理或代理不可用
        """
        try:
            from core.proxy_converter import ProxyConverter
            return ProxyConverter.get_pyrogram_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取Pyrogram代理配置失败: {e}")
            return None


# 便捷函数 - 向后兼容
def get_proxy_config(module_name: str = "Unknown") -> Optional[str]:
    """
    获取代理配置的便捷函数 - 默认返回yt-dlp格式
    
    Args:
        module_name: 调用模块名称
        
    Returns:
        str: yt-dlp格式的代理URL
        None: 无代理或代理不可用
    """
    return ProxyHelper.get_ytdlp_proxy(module_name)


def get_pytubefix_proxy_config(module_name: str = "Unknown") -> Optional[str]:
    """
    获取PyTubeFix代理配置的便捷函数
    
    Args:
        module_name: 调用模块名称
        
    Returns:
        str: PyTubeFix格式的代理URL
        None: 无代理或代理不可用
    """
    return ProxyHelper.get_pytubefix_proxy(module_name)
