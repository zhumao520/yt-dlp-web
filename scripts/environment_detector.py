# -*- coding: utf-8 -*-
"""
环境检测器 - 自动检测运行环境
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class EnvironmentDetector:
    """环境检测器"""
    
    def __init__(self):
        self.env_info = {}
    
    def detect(self) -> Dict[str, Any]:
        """检测运行环境"""
        try:
            self.env_info = {
                'environment': self._detect_environment(),
                'is_container': self._is_container(),
                'is_build_environment': self._is_build_environment(),
                'python_version': sys.version,
                'platform': sys.platform,
                'working_directory': str(Path.cwd()),
                'script_directory': str(Path(__file__).parent),
                'project_root': str(Path(__file__).parent.parent.parent),
                'has_ytdlp': self._check_ytdlp_availability(),
                'environment_variables': self._get_relevant_env_vars()
            }
            
            logger.info("✅ 环境检测完成")
            return self.env_info
            
        except Exception as e:
            logger.error(f"❌ 环境检测失败: {e}")
            return {}
    
    def _detect_environment(self) -> str:
        """检测环境类型"""
        # GitHub Actions
        if os.environ.get('GITHUB_ACTIONS'):
            return 'github_actions'
        
        # Docker容器
        if self._is_container():
            return 'docker'
        
        # 本地开发
        if os.environ.get('FLASK_ENV') == 'development':
            return 'development'
        
        # 生产环境
        if os.environ.get('FLASK_ENV') == 'production':
            return 'production'
        
        # 默认本地环境
        return 'local'
    
    def _is_container(self) -> bool:
        """检测是否在容器中运行"""
        # 检查Docker环境标识
        if os.path.exists('/.dockerenv'):
            return True
        
        # 检查cgroup信息
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content or 'containerd' in content:
                    return True
        except (FileNotFoundError, PermissionError):
            pass
        
        # 检查环境变量
        if os.environ.get('CONTAINER') or os.environ.get('DOCKER_CONTAINER'):
            return True
        
        return False
    
    def _is_build_environment(self) -> bool:
        """检测是否在构建环境中"""
        # GitHub Actions构建
        if os.environ.get('GITHUB_ACTIONS'):
            return True
        
        # Docker构建阶段
        if os.environ.get('DOCKER_BUILDKIT') or os.environ.get('BUILDKIT_HOST'):
            return True
        
        # 检查是否存在预构建的yt-dlp
        ytdlp_prepared_paths = [
            '/ytdlp-prepared',
            '/app/yt-dlp',
            './yt-dlp'
        ]
        
        for path in ytdlp_prepared_paths:
            if Path(path).exists():
                return True
        
        return False
    
    def _check_ytdlp_availability(self) -> bool:
        """检查yt-dlp是否可用"""
        try:
            import yt_dlp
            return True
        except ImportError:
            pass
        
        # 检查预构建路径
        ytdlp_paths = [
            '/ytdlp-prepared',
            '/app/yt-dlp',
            './yt-dlp',
            './yt_dlp'
        ]
        
        for path in ytdlp_paths:
            if Path(path).exists():
                return True
        
        return False
    
    def _get_relevant_env_vars(self) -> Dict[str, str]:
        """获取相关环境变量"""
        relevant_vars = [
            'GITHUB_ACTIONS',
            'GITHUB_WORKFLOW',
            'DOCKER_BUILDKIT',
            'CONTAINER',
            'FLASK_ENV',
            'YTDLP_SOURCE',
            'YTDLP_VERSION',
            'APP_HOST',
            'APP_PORT',
            'SECRET_KEY',
            'DATABASE_URL',
            'DOWNLOAD_DIR',
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_CHAT_ID'
        ]
        
        env_vars = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value:
                # 敏感信息脱敏
                if 'TOKEN' in var or 'SECRET' in var or 'PASSWORD' in var:
                    env_vars[var] = f"{value[:8]}..." if len(value) > 8 else "***"
                else:
                    env_vars[var] = value
        
        return env_vars
    
    def get_ytdlp_paths(self) -> list:
        """获取可能的yt-dlp路径"""
        paths = []
        
        # 预构建路径
        if self.env_info.get('is_build_environment'):
            paths.extend([
                '/ytdlp-prepared',
                '/app/yt-dlp'
            ])
        
        # 标准路径
        paths.extend([
            './yt-dlp',
            './yt_dlp',
            '/usr/local/lib/python*/site-packages/yt_dlp',
            str(Path.home() / '.local/lib/python*/site-packages/yt_dlp')
        ])
        
        return [p for p in paths if Path(p).exists()]
    
    def should_install_ytdlp(self) -> bool:
        """判断是否需要安装yt-dlp"""
        # 构建环境中已预安装，不需要再安装
        if self.env_info.get('is_build_environment'):
            return False
        
        # 已经可用，不需要安装
        if self.env_info.get('has_ytdlp'):
            return False
        
        # 其他情况需要安装
        return True
    
    def get_install_strategy(self) -> str:
        """获取安装策略"""
        if self.env_info.get('is_build_environment'):
            return 'use_prebuilt'
        
        if self.env_info.get('environment') == 'github_actions':
            return 'github_release'
        
        if self.env_info.get('is_container'):
            return 'pip_install'
        
        return 'auto_detect'
    
    def print_summary(self):
        """打印环境信息摘要"""
        print("\n" + "="*50)
        print("🔍 环境检测结果")
        print("="*50)
        print(f"环境类型: {self.env_info.get('environment', 'unknown')}")
        print(f"容器环境: {'是' if self.env_info.get('is_container') else '否'}")
        print(f"构建环境: {'是' if self.env_info.get('is_build_environment') else '否'}")
        print(f"yt-dlp可用: {'是' if self.env_info.get('has_ytdlp') else '否'}")
        print(f"Python版本: {sys.version.split()[0]}")
        print(f"工作目录: {self.env_info.get('working_directory', 'unknown')}")
        
        if self.env_info.get('environment_variables'):
            print("\n环境变量:")
            for key, value in self.env_info['environment_variables'].items():
                print(f"  {key}: {value}")
        
        print("="*50)


if __name__ == '__main__':
    # 测试环境检测
    detector = EnvironmentDetector()
    env_info = detector.detect()
    detector.print_summary()
    
    print(f"\n需要安装yt-dlp: {'是' if detector.should_install_ytdlp() else '否'}")
    print(f"安装策略: {detector.get_install_strategy()}")
    
    ytdlp_paths = detector.get_ytdlp_paths()
    if ytdlp_paths:
        print(f"yt-dlp路径: {ytdlp_paths}")
