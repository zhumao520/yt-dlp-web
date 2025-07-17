#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YT-DLP Web - 应用入口点
轻量化可扩展架构
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 🔧 确保工作目录正确，以便相对路径能正常工作
os.chdir(current_dir)

from core import create_app, Config
from scripts.environment_detector import EnvironmentDetector
from scripts.ytdlp_installer import YtdlpInstaller

# 配置日志
from core.logging_config import setup_application_logging
setup_application_logging()
logger = logging.getLogger(__name__)


def setup_environment():
    """环境检测和初始化"""
    try:
        logger.info("🔍 检测运行环境...")
        
        # 环境检测
        detector = EnvironmentDetector()
        env_info = detector.detect()
        
        logger.info(f"📋 环境信息: {env_info['environment']}")
        logger.info(f"🐳 容器环境: {env_info['is_container']}")
        logger.info(f"🏗️ 构建环境: {env_info['is_build_environment']}")
        
        # yt-dlp 安装检查
        installer = YtdlpInstaller()
        
        if env_info['is_build_environment']:
            logger.info("🏗️ 构建环境检测到，跳过运行时yt-dlp安装")
        else:
            logger.info("🔽 检查并安装yt-dlp...")
            if installer.ensure_ytdlp():
                logger.info("✅ yt-dlp 准备就绪")
            else:
                logger.warning("⚠️ yt-dlp 安装失败，部分功能可能不可用")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 环境初始化失败: {e}")
        return False


def main():
    """主函数"""
    try:
        logger.info("🚀 启动 YT-DLP Web...")

        # 配置验证和修复
        logger.info("🔍 验证系统配置...")
        from core.config_validator import validate_and_fix_config
        success, issues, fixes = validate_and_fix_config()

        if not success:
            logger.warning("⚠️ 发现配置问题，但将继续启动")

        # 环境初始化
        if not setup_environment():
            logger.error("❌ 环境初始化失败，退出")
            sys.exit(1)

        # 初始化FFmpeg配置
        logger.info("🎬 初始化FFmpeg配置...")
        try:
            from modules.downloader.ffmpeg_config import update_ytdlp_config_file, get_ffmpeg_config_manager

            # 更新yt-dlp.conf文件
            if update_ytdlp_config_file():
                logger.info("✅ FFmpeg配置已自动更新到yt-dlp.conf")
            else:
                logger.warning("⚠️ FFmpeg配置更新失败，将使用默认配置")

            # 显示FFmpeg状态
            manager = get_ffmpeg_config_manager()
            status = manager.get_status()
            if status['ffmpeg_available']:
                logger.info(f"✅ FFmpeg可用: {status['ffmpeg_version']} @ {status['ffmpeg_path']}")
            else:
                logger.warning("⚠️ FFmpeg不可用，视频合并功能将受限")

        except Exception as e:
            logger.warning(f"⚠️ FFmpeg配置初始化失败: {e}")

        # 创建Flask应用
        logger.info("🔧 创建Flask应用...")
        app = create_app()

        # 初始化数据库
        logger.info("🗄️ 初始化数据库...")
        with app.app_context():
            from core.database import get_database
            db = get_database()
            # 数据库在get_database()时已自动初始化
            logger.info("✅ 数据库初始化完成")

        # 获取配置
        config = Config()
        host = config.get('app.host', '0.0.0.0')
        port = config.get('app.port', 8080)
        debug = config.get('app.debug', False)
        
        logger.info(f"🌐 启动Web服务器: http://{host}:{port}")
        
        # 启动应用
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("👋 用户中断，正在退出...")
    except Exception as e:
        logger.error(f"❌ 应用启动失败: {e}")
        sys.exit(1)


# 应用实例创建已移至 core/app.py，避免重复

if __name__ == '__main__':
    main()
