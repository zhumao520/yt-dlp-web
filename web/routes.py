# -*- coding: utf-8 -*-
"""
Web路由 - 页面路由
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, request
from ..core.auth import auth_required, optional_auth

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@optional_auth
def index():
    """首页 - 根据状态决定显示内容"""
    try:
        # 检查是否需要初始化
        if _needs_initialization():
            return redirect(url_for('main.setup'))

        # 检查是否已登录
        if not hasattr(request, 'current_user') or not request.current_user:
            return redirect(url_for('auth.login'))

        # 显示主界面
        return render_template('main/index.html')

    except Exception as e:
        logger.error(f"❌ 首页加载失败: {e}")
        return render_template('errors/500.html'), 500


@main_bp.route('/setup')
def setup():
    """初始化设置页面"""
    try:
        # 检查系统状态
        system_status = _get_system_status()
        return render_template('setup/index.html', status=system_status)
        
    except Exception as e:
        logger.error(f"❌ 初始化页面加载失败: {e}")
        return render_template('errors/500.html'), 500


@main_bp.route('/download')
@auth_required
def download():
    """下载页面 - 重定向到首页"""
    from flask import redirect, url_for
    return redirect(url_for('main.index'))


@main_bp.route('/files')
@auth_required
def files():
    """文件管理页面"""
    return render_template('main/files.html')


@main_bp.route('/history')
@auth_required
def history():
    """下载历史页面"""
    return render_template('main/history.html')


@main_bp.route('/cookies')
@auth_required
def cookies():
    """Cookies管理页面"""
    return render_template('main/cookies.html')


@main_bp.route('/telegram')
@auth_required
def telegram():
    """Telegram配置页面"""
    return render_template('main/telegram.html')


@main_bp.route('/settings')
@auth_required
def settings():
    """系统设置页面"""
    return render_template('main/settings.html')


def _needs_initialization():
    """检查是否需要初始化"""
    try:
        from ..core.database import get_database
        from ..core.config import get_config
        
        # 检查数据库是否有用户
        db = get_database()
        users = db.execute_query('SELECT COUNT(*) as count FROM users')
        if not users or users[0]['count'] == 0:
            return True
        
        # 检查基本配置是否完整
        required_configs = [
            'app.secret_key',
            'downloader.output_dir'
        ]
        
        for config_key in required_configs:
            if not get_config(config_key):
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"❌ 检查初始化状态失败: {e}")
        return True


def _get_system_status():
    """获取系统状态"""
    try:
        status = {
            'database': False,
            'ytdlp': False,
            'config': False,
            'admin_user': False
        }
        
        # 检查数据库
        try:
            from ..core.database import get_database
            db = get_database()
            db.execute_query('SELECT 1')
            status['database'] = True
        except:
            pass
        
        # 检查yt-dlp
        try:
            import yt_dlp
            status['ytdlp'] = True
        except ImportError:
            pass
        
        # 检查配置
        from ..core.config import get_config
        if get_config('app.secret_key') != 'change-this-secret-key-in-production':
            status['config'] = True
        
        # 检查管理员用户
        try:
            from ..core.database import get_database
            db = get_database()
            users = db.execute_query('SELECT COUNT(*) as count FROM users WHERE is_admin = 1')
            if users and users[0]['count'] > 0:
                status['admin_user'] = True
        except:
            pass
        
        return status

    except Exception as e:
        logger.error(f"❌ 获取系统状态失败: {e}")
        return {
            'database': False,
            'ytdlp': False,
            'config': False,
            'admin_user': False
        }



