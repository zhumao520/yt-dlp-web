# -*- coding: utf-8 -*-
"""
Flask应用工厂 - 轻量化应用创建
"""

import logging
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)


def create_app(config_override=None):
    """创建Flask应用实例"""
    try:
        logger.info("🔧 创建Flask应用...")

        # 创建Flask实例，指定模板目录
        import os
        from pathlib import Path

        # 获取app目录的绝对路径
        app_dir = Path(__file__).parent.parent
        template_dir = app_dir / "web" / "templates"
        static_dir = app_dir / "web" / "static"

        app = Flask(
            __name__,
            template_folder=str(template_dir),
            static_folder=str(static_dir)
        )

        # 配置应用
        _configure_app(app, config_override)

        # 配置CORS
        CORS(app, supports_credentials=True)

        # 初始化核心组件
        _initialize_core_components(app)

        # 注册蓝图
        _register_blueprints(app)

        # 注册错误处理器
        _register_error_handlers(app)

        # 注册安全头部中间件
        _register_security_headers(app)

        # 发送应用启动事件
        with app.app_context():
            from .events import emit, Events

            emit(
                Events.APP_STARTED,
                {"app_name": app.config.get("APP_NAME", "YT-DLP Web")},
            )

            # 启动时检查并安装yt-dlp
            _ensure_ytdlp_available()

        logger.info("✅ Flask应用创建完成")
        return app

    except Exception as e:
        logger.error(f"❌ Flask应用创建失败: {e}")
        raise


def _ensure_ytdlp_available():
    """确保yt-dlp在启动时可用"""
    try:
        logger.info("🔧 检查yt-dlp可用性...")

        from scripts.ytdlp_installer import YtdlpInstaller
        installer = YtdlpInstaller()

        # 检查是否已经可用
        if installer._check_ytdlp_available():
            version = installer._get_ytdlp_version()
            logger.info(f"✅ yt-dlp已可用，版本: {version}")
            return True

        # 如果不可用，尝试安装
        logger.info("⚠️ yt-dlp不可用，尝试自动安装...")
        success = installer.ensure_ytdlp()

        if success:
            version = installer._get_ytdlp_version()
            logger.info(f"✅ yt-dlp自动安装成功，版本: {version}")
        else:
            logger.warning("⚠️ yt-dlp自动安装失败，请手动安装")

        return success

    except Exception as e:
        logger.error(f"❌ 检查yt-dlp可用性失败: {e}")
        return False


def _configure_app(app: Flask, config_override=None):
    """配置Flask应用"""
    from .config import get_config
    
    # 基础配置
    app.config.update(
        {
            "SECRET_KEY": get_config("app.secret_key"),
            "DEBUG": get_config("app.debug", False),
            "APP_NAME": get_config("app.name", "YT-DLP Web"),
            "APP_VERSION": get_config("app.version", "2.0.0"),
            # 文件上传配置
            "MAX_CONTENT_LENGTH": 16 * 1024 * 1024 * 1024,  # 16GB
            # JSON配置
            "JSON_AS_ASCII": False,
            "JSON_SORT_KEYS": False,
            # 会话配置
            "PERMANENT_SESSION_LIFETIME": get_config("auth.session_timeout", 86400),
        }
    )
    
    # 应用自定义配置覆盖
    if config_override:
        app.config.update(config_override)
        logger.info(f"✅ 应用自定义配置: {list(config_override.keys())}")
    
    logger.info("✅ Flask应用配置完成")


def _initialize_core_components(app: Flask):
    """初始化核心组件"""
    with app.app_context():
        try:
            # 初始化数据库
            from .database import get_database
            db = get_database()

            # 确保管理员用户存在
            if not db.ensure_admin_user_exists():
                logger.error("❌ 管理员用户创建失败")
                raise Exception("管理员用户创建失败")

            logger.info("✅ 数据库初始化完成")
            
            # 初始化认证管理器
            from .auth import get_auth_manager
            auth_manager = get_auth_manager()
            logger.info("✅ 认证管理器初始化完成")
            
            # 初始化事件总线
            from .events import event_bus
            logger.info("✅ 事件总线初始化完成")

            # 初始化Telegram模块（注册事件监听器）
            try:
                # 修复容器环境中的导入问题
                import sys
                from pathlib import Path

                # 确保modules目录在Python路径中
                app_root = Path(__file__).parent.parent
                modules_path = str(app_root / "modules")
                if modules_path not in sys.path:
                    sys.path.insert(0, modules_path)

                # 使用绝对导入
                import modules.telegram as telegram
                logger.info("✅ Telegram事件监听器注册完成")
            except ImportError as e:
                logger.warning(f"⚠️ Telegram模块导入失败: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Telegram模块初始化失败: {e}")
            
        except Exception as e:
            logger.error(f"❌ 核心组件初始化失败: {e}")
            raise


def _register_blueprints(app: Flask):
    """注册蓝图"""
    try:
        # 主页蓝图
        from web.routes import main_bp
        app.register_blueprint(main_bp)

        # API蓝图
        from api.routes import api_bp
        app.register_blueprint(api_bp, url_prefix="/api")

        # 认证蓝图
        from modules.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix="/auth")

        # 下载模块蓝图
        from modules.downloader.routes import downloader_bp
        app.register_blueprint(downloader_bp, url_prefix="/download")

        # Telegram模块蓝图
        try:
            from modules.telegram.routes import telegram_bp
            app.register_blueprint(telegram_bp, url_prefix="/telegram")
        except ImportError as e:
            logger.warning(f"⚠️ Telegram模块导入失败: {e}")

        # Cookies管理蓝图
        from modules.cookies.routes import cookies_bp
        app.register_blueprint(cookies_bp, url_prefix="/cookies")

        # 文件管理蓝图
        from modules.files.routes import files_bp
        app.register_blueprint(files_bp, url_prefix="/files")



        logger.info("✅ 蓝图注册完成")

    except Exception as e:
        logger.error(f"❌ 蓝图注册失败: {e}")
        raise


def _register_error_handlers(app: Flask):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import request, jsonify, render_template

        if request.is_json:
            return jsonify({"error": "页面未找到"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import request, jsonify, render_template

        logger.error(f"内部服务器错误: {error}")
        if request.is_json:
            return jsonify({"error": "内部服务器错误"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(401)
    def unauthorized_error(error):
        from flask import request, jsonify, render_template

        if request.is_json:
            return jsonify({"error": "未授权访问"}), 401
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        from flask import request, jsonify, render_template

        if request.is_json:
            return jsonify({"error": "禁止访问"}), 403
        return render_template("errors/403.html"), 403
    
    logger.info("✅ 错误处理器注册完成")


def _register_security_headers(app: Flask):
    """注册安全头部中间件"""

    @app.after_request
    def add_security_headers(response):
        """添加安全头部"""
        # 内容类型选项
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # 现代化内容安全策略（替代X-Frame-Options）
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net https://cdn.plyr.io https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net https://cdn.plyr.io https://unpkg.com https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:; "
            "connect-src 'self' https:; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"  # 替代X-Frame-Options
        )
        response.headers['Content-Security-Policy'] = csp

        # 引用者策略
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # 权限策略
        response.headers['Permissions-Policy'] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # 缓存控制（使用Cache-Control而不是Expires）
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        elif response.mimetype.startswith('text/css') or response.mimetype.startswith('application/javascript'):
            response.headers['Cache-Control'] = 'public, max-age=31536000'  # 静态资源缓存1年

        # 设置正确的字符集
        if response.mimetype == 'text/html':
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

        return response

    logger.info("✅ 安全头部中间件注册完成")


# WSGI应用入口点
def create_wsgi_app():
    """创建WSGI应用（用于生产部署）"""
    return create_app()


# 为了兼容性，提供应用实例
app = None

def get_app():
    """获取应用实例（延迟初始化）"""
    global app
    if app is None:
        app = create_app()
    return app
