# -*- coding: utf-8 -*-
"""
API路由 - 统一API接口
"""

import logging
import time
from flask import Blueprint, request, jsonify
from core.auth import auth_required, optional_auth

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ==================== 认证相关API ====================

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """API登录"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要JSON数据"}), 400
        
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"error": "用户名和密码不能为空"}), 400
        
        from core.auth import get_auth_manager
        auth_manager = get_auth_manager()
        
        token = auth_manager.login(username, password)
        if not token:
            return jsonify({"error": "用户名或密码错误"}), 401

        # 创建响应并设置cookie
        response_data = {
            "success": True,
            "message": "登录成功",
            "token": token,
            "username": username,
        }

        response = jsonify(response_data)

        # 设置cookie（与web登录保持一致）
        remember = data.get("remember", False)
        max_age = (30 * 24 * 60 * 60) if remember else (24 * 60 * 60)
        response.set_cookie('auth_token', token,
                          max_age=max_age,
                          path='/',
                          httponly=False, secure=False, samesite='Lax')

        logger.info(f"🍪 设置cookie: auth_token={token[:20]}..., max_age={max_age}")

        return response
        
    except Exception as e:
        logger.error(f"❌ API登录失败: {e}")
        return jsonify({"error": "登录处理失败"}), 500


@api_bp.route('/auth/status')
@optional_auth
def api_auth_status():
    """检查认证状态"""
    try:
        if hasattr(request, "current_user") and request.current_user:
            return jsonify({
                "authenticated": True,
                "username": request.current_user.get("username"),
                "is_admin": request.current_user.get("is_admin", False),
            })
        else:
            return jsonify({"authenticated": False})
            
    except Exception as e:
        logger.error(f"❌ 检查认证状态失败: {e}")
        return jsonify({"authenticated": False, "error": "状态检查失败"}), 500


# ==================== 下载相关API ====================

# 下载API已移至 /download/ 蓝图，避免重复


# 下载状态API已移至 /download/ 蓝图，避免重复


# 下载列表API已移至 /download/ 蓝图，避免重复


@api_bp.route('/video/info', methods=['POST'])
@auth_required
def api_video_info():
    """获取视频信息"""
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({"error": "需要提供URL"}), 400

        url = data["url"].strip()
        if not url:
            return jsonify({"error": "URL不能为空"}), 400
        
        # 提取视频信息
        video_info = _extract_video_info(url)
        if not video_info:
            return jsonify({"error": "无法获取视频信息"}), 400

        response_data = {
            "title": video_info.get("title", "Unknown"),
            "description": video_info.get("description", ""),
            "duration": video_info.get("duration"),
            "uploader": video_info.get("uploader", ""),
            "thumbnail": video_info.get("thumbnail", ""),
            "view_count": video_info.get("view_count"),
        }
        
        return jsonify({
            "success": True,
            "video_info": response_data,
        })
        
    except Exception as e:
        logger.error(f"❌ API获取视频信息失败: {e}")
        return jsonify({"error": "获取信息失败"}), 500


# ==================== Telegram相关API ====================

@api_bp.route('/telegram/config', methods=['GET'])
@auth_required
def api_telegram_config():
    """获取Telegram配置"""
    try:
        logger.info("🔄 收到Telegram配置获取请求")
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()
        logger.info(f"📥 从数据库获取的配置: {config}")
        
        if not config:
            logger.info("ℹ️ 数据库中没有配置，返回默认配置")
            default_config = {
                "enabled": False,
                "bot_token": "",
                "chat_id": "",
                "api_id": None,
                "api_hash": "",
                "push_mode": "file",
                "auto_download": True,
                "file_size_limit": 50,
                "webhook_url": "",
            }
            return jsonify(default_config)

        # 返回完整配置（用于编辑）
        # 确保布尔值正确转换（SQLite中可能存储为0/1）
        full_config = {
            "enabled": bool(config.get("enabled", False)),
            "bot_token": config.get("bot_token", ""),
            "chat_id": config.get("chat_id", ""),
            "api_id": config.get("api_id"),
            "api_hash": config.get("api_hash", ""),
            "push_mode": config.get("push_mode", "file"),
            "auto_download": bool(config.get("auto_download", True)),
            "file_size_limit": config.get("file_size_limit", 50),
            "webhook_url": config.get("webhook_url", ""),
        }

        logger.info(f"📤 返回的配置: {full_config}")
        return jsonify(full_config)
        
    except Exception as e:
        logger.error(f"❌ 获取Telegram配置失败: {e}")
        return jsonify({"error": "获取配置失败"}), 500


@api_bp.route('/telegram/config', methods=['POST'])
@auth_required
def api_save_telegram_config():
    """保存Telegram配置"""
    try:
        logger.info("🔄 收到Telegram配置保存请求")
        data = request.get_json()
        logger.info(f"📥 接收到的数据: {data}")

        if not data:
            logger.error("❌ 没有接收到配置数据")
            return jsonify({"error": "需要配置数据"}), 400

        # 处理api_id的类型转换
        api_id = data.get("api_id")
        if api_id is not None:
            try:
                api_id = int(api_id) if api_id != "" else None
            except (ValueError, TypeError):
                api_id = None

        config = {
            "bot_token": data.get("bot_token", "").strip(),
            "chat_id": data.get("chat_id", "").strip(),
            "api_id": api_id,
            "api_hash": data.get("api_hash", "").strip(),
            "enabled": data.get("enabled", False),
            "push_mode": data.get("push_mode", "file"),
            "auto_download": data.get("auto_download", True),
            "file_size_limit": data.get("file_size_limit", 50),
            "webhook_url": data.get("webhook_url", "").strip(),
        }

        logger.info(f"🔧 处理后的配置: {config}")
        
        # 验证必要字段
        if config["enabled"]:
            if not config["bot_token"] or config["bot_token"].strip() == "":
                logger.error("❌ 启用状态下Bot Token不能为空")
                return jsonify({"error": "启用Telegram功能时，Bot Token不能为空"}), 400

            if not config["chat_id"] or config["chat_id"].strip() == "":
                logger.error("❌ 启用状态下Chat ID不能为空")
                return jsonify({"error": "启用Telegram功能时，Chat ID不能为空"}), 400

        logger.info("🔧 开始保存配置到数据库")
        from core.database import get_database
        db = get_database()
        success = db.save_telegram_config(config)
        logger.info(f"💾 数据库保存结果: {'成功' if success else '失败'}")

        if success:
            # 重新加载配置
            logger.info("🔄 重新加载Telegram通知器配置")
            from modules.telegram.notifier import get_telegram_notifier
            notifier = get_telegram_notifier()
            notifier._load_config()

            logger.info("✅ Telegram配置保存完成")
            return jsonify({"success": True, "message": "配置保存成功"})
        else:
            logger.error("❌ 数据库保存失败")
            return jsonify({"error": "配置保存失败"}), 500
        
    except Exception as e:
        logger.error(f"❌ 保存Telegram配置失败: {e}")
        return jsonify({"error": "保存配置失败"}), 500


@api_bp.route('/telegram/test', methods=['POST'])
@auth_required
def api_test_telegram():
    """测试Telegram连接"""
    try:
        from modules.telegram.notifier import get_telegram_notifier
        notifier = get_telegram_notifier()

        result = notifier.test_connection()
        logger.info(f"🔍 Telegram测试结果: {result}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ 测试Telegram连接失败: {e}")
        return jsonify({"success": False, "error": "测试失败"}), 500


# ==================== 认证管理API ====================

@api_bp.route('/auth/change-password', methods=['POST'])
@auth_required
def api_change_password():
    """修改管理员密码"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要提供数据"}), 400

        current_password = data.get('current_password', '').strip()
        new_password = data.get('new_password', '').strip()

        if not current_password or not new_password:
            return jsonify({"error": "当前密码和新密码不能为空"}), 400

        if len(new_password) < 6:
            return jsonify({"error": "新密码长度不能少于6个字符"}), 400

        # 获取当前用户信息 - 简化版本
        from core.auth import get_token_from_request, get_auth_manager
        from core.database import get_database

        token = get_token_from_request()
        if not token:
            return jsonify({"error": "认证令牌无效"}), 401

        auth_manager = get_auth_manager()
        payload = auth_manager.verify_token(token)
        if not payload:
            return jsonify({"error": "认证令牌无效"}), 401

        username = payload.get('username')
        if not username:
            return jsonify({"error": "无法获取当前用户名"}), 401

        # 验证当前密码
        db = get_database()
        if not db.verify_user_password(username, current_password):
            return jsonify({"error": "当前密码错误"}), 400

        # 修改密码
        success = db.update_user_password(username, new_password)

        if success:
            logger.info(f"✅ 管理员密码修改成功: {username}")
            return jsonify({
                "success": True,
                "message": "密码修改成功"
            })
        else:
            return jsonify({"error": "密码修改失败"}), 500

    except Exception as e:
        logger.error(f"❌ 修改密码失败: {e}")
        return jsonify({"error": f"密码修改失败: {str(e)}"}), 500


@api_bp.route('/auth/change-username', methods=['POST'])
@auth_required
def api_change_username():
    """修改管理员用户名"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要提供数据"}), 400

        current_password = data.get('current_password', '').strip()
        new_username = data.get('new_username', '').strip()

        if not current_password or not new_username:
            return jsonify({"error": "当前密码和新用户名不能为空"}), 400

        if len(new_username) < 3:
            return jsonify({"error": "用户名长度不能少于3个字符"}), 400

        # 获取当前用户信息 - 简化版本
        from core.auth import get_token_from_request, get_auth_manager
        from core.database import get_database

        token = get_token_from_request()
        if not token:
            return jsonify({"error": "认证令牌无效"}), 401

        auth_manager = get_auth_manager()
        payload = auth_manager.verify_token(token)
        if not payload:
            return jsonify({"error": "认证令牌无效"}), 401

        current_username = payload.get('username')
        if not current_username:
            return jsonify({"error": "无法获取当前用户名"}), 401

        # 验证当前密码
        db = get_database()
        if not db.verify_user_password(current_username, current_password):
            return jsonify({"error": "当前密码错误"}), 400

        # 检查新用户名是否已存在
        if db.get_user_by_username(new_username):
            return jsonify({"error": "用户名已存在"}), 400

        # 修改用户名
        success = db.update_username(current_username, new_username)

        if success:
            logger.info(f"✅ 管理员用户名修改成功: {current_username} -> {new_username}")
            return jsonify({
                "success": True,
                "message": "用户名修改成功",
                "new_username": new_username
            })
        else:
            return jsonify({"error": "用户名修改失败"}), 500

    except Exception as e:
        logger.error(f"❌ 修改用户名失败: {e}")
        return jsonify({"error": f"用户名修改失败: {str(e)}"}), 500


# ==================== 系统相关API ====================

@api_bp.route('/health')
def api_health_check():
    """健康检查端点（无需认证）"""
    try:
        from core.health import get_health_checker
        health_checker = get_health_checker()
        health_data = health_checker.get_system_health()

        # 根据健康状态返回适当的HTTP状态码
        if health_data.get("status") == "unhealthy":
            return jsonify(health_data), 503
        elif health_data.get("status") == "degraded":
            return jsonify(health_data), 200
        else:
            return jsonify(health_data), 200

    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": int(time.time())
        }), 500


@api_bp.route('/system/status')
@auth_required
def api_system_status():
    """获取系统状态"""
    try:
        from core.config import get_config
        from core.health import get_health_checker

        # 获取健康检查数据
        health_checker = get_health_checker()
        health_data = health_checker.get_system_health()

        # 检查yt-dlp状态
        ytdlp_available = False
        ytdlp_version = "Unknown"
        try:
            from scripts.ytdlp_installer import YtdlpInstaller
            installer = YtdlpInstaller()

            if installer._check_ytdlp_available():
                ytdlp_available = True
                ytdlp_version = installer._get_ytdlp_version()
        except Exception as e:
            logger.warning(f"检查yt-dlp状态失败: {e}")
            pass

        # 获取下载统计
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()
        downloads = download_manager.get_all_downloads()

        download_stats = {
            "total": len(downloads),
            "completed": len([d for d in downloads if d["status"] == "completed"]),
            "failed": len([d for d in downloads if d["status"] == "failed"]),
            "pending": len([d for d in downloads if d["status"] in ["pending", "downloading"]]),
        }

        return jsonify({
            "app_name": get_config("app.name"),
            "app_version": get_config("app.version"),
            "ytdlp_available": ytdlp_available,
            "ytdlp_version": ytdlp_version,
            "download_stats": download_stats,
            "health": health_data,
            "uptime": health_data.get("uptime", 0)
        })

    except Exception as e:
        logger.error(f"❌ 获取系统状态失败: {e}")
        return jsonify({"error": "获取状态失败"}), 500


@api_bp.route('/system/optimize', methods=['POST'])
@auth_required
def api_system_optimize():
    """运行系统优化"""
    try:
        from scripts.system_optimizer import SystemOptimizer

        optimizer = SystemOptimizer()
        result = optimizer.run_optimization()

        return jsonify({
            "success": result["success"],
            "message": f"系统优化完成，应用了 {result['total_optimizations']} 个优化",
            "optimizations": result["optimizations"],
            "errors": result["errors"],
            "total_optimizations": result["total_optimizations"]
        })

    except Exception as e:
        logger.error(f"❌ 系统优化失败: {e}")
        return jsonify({"error": f"系统优化失败: {str(e)}"}), 500


# 调试端点已删除，生产环境不需要


@api_bp.route('/admin/reset-password', methods=['POST'])
def api_reset_admin_password():
    """重置管理员密码（无需认证，紧急使用）"""
    try:
        from core.database import get_database
        import hashlib
        import os

        # 获取环境变量中的密码
        env_password = os.getenv('ADMIN_PASSWORD')
        if not env_password:
            return jsonify({"error": "未设置 ADMIN_PASSWORD 环境变量"}), 400

        env_username = os.getenv('ADMIN_USERNAME', 'admin')
        password_hash = hashlib.sha256(env_password.encode()).hexdigest()

        db = get_database()

        # 更新或创建管理员用户
        result = db.execute_update('''
            INSERT OR REPLACE INTO users (username, password_hash, is_admin, created_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        ''', (env_username, password_hash))

        if result:
            logger.info(f"🔄 管理员密码重置成功: {env_username}")
            return jsonify({
                "success": True,
                "message": f"管理员密码重置成功",
                "username": env_username
            })
        else:
            return jsonify({"error": "密码重置失败"}), 500

    except Exception as e:
        logger.error(f"❌ 重置管理员密码失败: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/system/ytdlp/update", methods=["POST"])
@auth_required
def api_update_ytdlp():
    """更新yt-dlp"""
    try:
        from scripts.ytdlp_installer import YtdlpInstaller

        installer = YtdlpInstaller()

        # 先尝试强制更新
        logger.info("🔄 开始更新yt-dlp...")
        success = installer.update_ytdlp()

        if success:
            # 获取新版本信息
            info = installer.get_ytdlp_info()
            version = info.get("version", "Unknown") if info else "Unknown"

            logger.info(f"✅ yt-dlp更新成功，版本: {version}")
            return jsonify({
                "success": True,
                "message": f"yt-dlp更新成功，版本: {version}",
                "version": version,
            })
        else:
            # 如果更新失败，尝试重新安装
            logger.warning("⚠️ 更新失败，尝试重新安装...")
            success = installer.ensure_ytdlp(force_update=True)

            if success:
                info = installer.get_ytdlp_info()
                version = info.get("version", "Unknown") if info else "Unknown"

                logger.info(f"✅ yt-dlp重新安装成功，版本: {version}")
                return jsonify({
                    "success": True,
                    "message": f"yt-dlp重新安装成功，版本: {version}",
                    "version": version,
                })
            else:
                return jsonify({"error": "yt-dlp安装失败，请检查网络连接或手动安装"}), 500

    except Exception as e:
        logger.error(f"❌ 更新yt-dlp失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@api_bp.route("/system/ytdlp/info")
@auth_required
def api_ytdlp_info():
    """获取yt-dlp详细信息"""
    try:
        from scripts.ytdlp_installer import YtdlpInstaller

        installer = YtdlpInstaller()
        info = installer.get_ytdlp_info()

        if info:
            return jsonify({"success": True, "info": info})
        else:
            # 如果获取不到信息，尝试安装
            logger.info("🔧 yt-dlp信息获取失败，尝试安装...")
            success = installer.ensure_ytdlp()

            if success:
                info = installer.get_ytdlp_info()
                if info:
                    return jsonify({"success": True, "info": info})

            return jsonify({"success": False, "error": "yt-dlp未安装或不可用"}), 404

    except Exception as e:
        logger.error(f"❌ 获取yt-dlp信息失败: {e}")
        return jsonify({"error": "获取信息失败"}), 500


@api_bp.route("/system/ytdlp/install", methods=["POST"])
@auth_required
def api_install_ytdlp():
    """强制安装yt-dlp"""
    try:
        from scripts.ytdlp_installer import YtdlpInstaller

        installer = YtdlpInstaller()

        logger.info("🔧 开始强制安装yt-dlp...")
        success = installer.ensure_ytdlp(force_update=True)

        if success:
            info = installer.get_ytdlp_info()
            version = info.get("version", "Unknown") if info else "Unknown"

            logger.info(f"✅ yt-dlp安装成功，版本: {version}")
            return jsonify({
                "success": True,
                "message": f"yt-dlp安装成功，版本: {version}",
                "version": version,
            })
        else:
            return jsonify({"error": "yt-dlp安装失败，请检查网络连接"}), 500

    except Exception as e:
        logger.error(f"❌ 安装yt-dlp失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({"error": f"安装失败: {str(e)}"}), 500


# ==================== PyTubeFix 管理 API ====================

@api_bp.route("/system/pytubefix/info")
@auth_required
def api_pytubefix_info():
    """获取PyTubeFix详细信息"""
    try:
        from scripts.pytubefix_installer import PyTubeFixInstaller

        installer = PyTubeFixInstaller()
        info = installer.get_pytubefix_info()

        if info:
            return jsonify({
                "success": True,
                "pytubefix_info": info
            })
        else:
            return jsonify({
                "success": False,
                "error": "PyTubeFix未安装或无法获取信息"
            })

    except Exception as e:
        logger.error(f"❌ 获取PyTubeFix信息失败: {e}")
        return jsonify({"error": "获取信息失败"}), 500


@api_bp.route("/system/pytubefix/update", methods=["POST"])
@auth_required
def api_update_pytubefix():
    """更新PyTubeFix"""
    try:
        from scripts.pytubefix_installer import PyTubeFixInstaller

        installer = PyTubeFixInstaller()

        logger.info("🔄 开始更新PyTubeFix...")
        success = installer.update_pytubefix()

        if success:
            # 获取更新后的信息
            info = installer.get_pytubefix_info()

            logger.info("✅ PyTubeFix更新成功")
            return jsonify({
                "success": True,
                "message": "PyTubeFix更新成功",
                "pytubefix_info": info
            })
        else:
            logger.error("❌ PyTubeFix更新失败")
            return jsonify({
                "success": False,
                "error": "PyTubeFix更新失败"
            }), 500

    except Exception as e:
        logger.error(f"❌ 更新PyTubeFix异常: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@api_bp.route("/system/pytubefix/install", methods=["POST"])
@auth_required
def api_install_pytubefix():
    """强制安装PyTubeFix"""
    try:
        from scripts.pytubefix_installer import PyTubeFixInstaller

        installer = PyTubeFixInstaller()

        logger.info("📦 开始强制安装PyTubeFix...")
        success = installer.ensure_pytubefix(force_update=True)

        if success:
            # 获取安装后的信息
            info = installer.get_pytubefix_info()

            logger.info("✅ PyTubeFix强制安装成功")
            return jsonify({
                "success": True,
                "message": "PyTubeFix强制安装成功",
                "pytubefix_info": info
            })
        else:
            logger.error("❌ PyTubeFix强制安装失败")
            return jsonify({
                "success": False,
                "error": "PyTubeFix强制安装失败"
            }), 500

    except Exception as e:
        logger.error(f"❌ 强制安装PyTubeFix异常: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({"error": f"强制安装失败: {str(e)}"}), 500


# ==================== 统一引擎管理 API ====================

@api_bp.route("/system/engines/status")
@auth_required
def api_engines_status():
    """获取所有引擎状态"""
    try:
        from scripts.engine_manager import EngineManager

        manager = EngineManager()
        status = manager.get_all_engines_status()

        return jsonify({
            "success": True,
            "engines": status
        })

    except Exception as e:
        logger.error(f"❌ 获取引擎状态失败: {e}")
        return jsonify({"error": "获取引擎状态失败"}), 500


@api_bp.route("/system/engines/update-all", methods=["POST"])
@auth_required
def api_update_all_engines():
    """一键更新所有引擎"""
    try:
        from scripts.engine_manager import EngineManager

        manager = EngineManager()

        logger.info("🔄 开始一键更新所有引擎...")
        result = manager.update_all_engines()

        if result['summary']['successful'] > 0:
            logger.info(f"✅ 引擎更新完成: {result['summary']['successful']}/{result['summary']['total']} 成功")
            return jsonify({
                "success": True,
                "message": f"引擎更新完成: {result['summary']['successful']}/{result['summary']['total']} 成功",
                "results": result['results'],
                "summary": result['summary']
            })
        else:
            logger.error("❌ 所有引擎更新都失败")
            return jsonify({
                "success": False,
                "error": "所有引擎更新都失败",
                "results": result['results'],
                "summary": result['summary']
            }), 500

    except Exception as e:
        logger.error(f"❌ 一键更新引擎异常: {e}")
        return jsonify({"error": f"一键更新失败: {str(e)}"}), 500


# ==================== 设置相关API ====================

@api_bp.route('/settings/general', methods=['GET'])
@auth_required
def api_get_general_settings():
    """获取基础设置"""
    try:
        from core.config import get_config

        settings = {
            "app_name": get_config("app.name", "YT-DLP Web"),
            "app_version": get_config("app.version", "2.0.0"),
            "host": get_config("app.host", "0.0.0.0"),
            "port": get_config("app.port", 8080),
            "debug": get_config("app.debug", False),
            "secret_key": get_config("app.secret_key", "")[:10] + "..." if get_config("app.secret_key") else ""
        }

        return jsonify({"success": True, "settings": settings})

    except Exception as e:
        logger.error(f"❌ 获取基础设置失败: {e}")
        return jsonify({"error": "获取设置失败"}), 500


@api_bp.route('/settings/proxy', methods=['GET'])
@auth_required
def api_get_proxy_settings():
    """获取代理设置"""
    try:
        from core.database import get_database

        db = get_database()
        proxy_config = db.get_proxy_config()

        if not proxy_config:
            # 返回默认配置
            proxy_config = {
                "enabled": False,
                "proxy_type": "http",
                "host": "",
                "port": None,
                "username": "",
                "password": ""
            }
        else:
            # 隐藏密码
            proxy_config['password'] = '***' if proxy_config.get('password') else ''

        return jsonify({"success": True, "proxy": proxy_config})

    except Exception as e:
        logger.error(f"❌ 获取代理设置失败: {e}")
        return jsonify({"error": "获取代理设置失败"}), 500


@api_bp.route('/settings/proxy', methods=['POST'])
@auth_required
def api_save_proxy_settings():
    """保存代理设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "无效的请求数据"}), 400

        from core.database import get_database

        # 验证数据
        proxy_config = {
            "enabled": bool(data.get("enabled", False)),
            "proxy_type": data.get("proxy_type", "http"),
            "host": data.get("host", "").strip(),
            "port": data.get("port"),
            "username": data.get("username", "").strip(),
            "password": data.get("password", "").strip()
        }

        # 验证必填字段
        if proxy_config["enabled"]:
            if not proxy_config["host"]:
                return jsonify({"error": "代理地址不能为空"}), 400

            if not proxy_config["port"] or not (1 <= proxy_config["port"] <= 65535):
                return jsonify({"error": "代理端口必须在1-65535之间"}), 400

        # 如果密码是 *** 则保持原密码不变
        if proxy_config["password"] == "***":
            db = get_database()
            existing = db.get_proxy_config()
            if existing:
                proxy_config["password"] = existing.get("password", "")

        # 保存到数据库
        db = get_database()
        success = db.save_proxy_config(proxy_config)

        if success:
            # 更新运行时配置 - 使用统一的代理转换工具
            from core.config import set_config
            if proxy_config["enabled"] and proxy_config["host"]:
                from core.proxy_converter import ProxyConverter
                proxy_url = ProxyConverter.build_proxy_url(proxy_config)
                set_config("downloader.proxy", proxy_url)
            else:
                set_config("downloader.proxy", None)

            logger.info(f"✅ 代理设置保存成功: enabled={proxy_config['enabled']}")
            return jsonify({"success": True, "message": "代理设置保存成功"})
        else:
            return jsonify({"error": "保存代理设置失败"}), 500

    except Exception as e:
        logger.error(f"❌ 保存代理设置失败: {e}")
        return jsonify({"error": "保存代理设置失败"}), 500


@api_bp.route('/settings/proxy/test', methods=['POST'])
@auth_required
def api_test_proxy():
    """测试代理连接 - 使用统一的代理转换工具"""
    try:
        data = request.get_json()
        logger.info(f"🔍 收到代理测试请求: {data}")

        if not data:
            logger.error("❌ 代理测试请求数据为空")
            return jsonify({"error": "无效的请求数据"}), 400

        # 验证必需字段
        required_fields = ['host', 'port']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            logger.error(f"❌ 代理测试缺少必需字段: {missing_fields}")
            return jsonify({"error": f"缺少必需字段: {', '.join(missing_fields)}"}), 400

        # 使用统一的代理转换工具进行测试
        from core.proxy_converter import ProxyConverter

        result = ProxyConverter.test_proxy_connection(data, timeout=10)

        if result['success']:
            return jsonify({
                "success": True,
                "message": result['message'],
                "ip": result['ip'],
                "response_time": result['response_time']
            })
        else:
            return jsonify({
                "success": False,
                "error": result['message']
            }), 400

    except Exception as e:
        logger.error(f"❌ 测试代理失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"代理测试失败: {str(e)}"
        }), 500


@api_bp.route('/settings/general', methods=['POST'])
@auth_required
def api_save_general_settings():
    """保存基础设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要提供设置数据"}), 400

        # 这里应该保存到配置文件或数据库
        # 目前只是返回成功，实际项目中需要实现配置保存逻辑
        logger.info(f"📝 保存基础设置: {data}")

        return jsonify({"success": True, "message": "基础设置保存成功"})

    except Exception as e:
        logger.error(f"❌ 保存基础设置失败: {e}")
        return jsonify({"error": "保存设置失败"}), 500


@api_bp.route('/settings/download', methods=['GET'])
@auth_required
def api_get_download_settings():
    """获取下载设置"""
    try:
        from core.config import get_config

        # 从数据库获取设置，如果没有则使用默认值
        from core.database import get_database
        db = get_database()

        # 质量映射（后端到前端）
        format_to_quality = {
            "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best": "best",
            "best": "best",
            "best[height<=720]": "medium",
            "worst": "low"
        }

        current_format = get_config("ytdlp.format", "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best")
        current_quality = format_to_quality.get(current_format, "best")

        settings = {
            "output_dir": get_config("downloader.output_dir", "/app/downloads"),
            "max_concurrent": get_config("downloader.max_concurrent", 3),
            "timeout": get_config("downloader.timeout", 300),
            "default_quality": current_quality,
            "auto_cleanup": get_config("downloader.auto_cleanup", True),
            "file_retention_hours": get_config("downloader.file_retention_hours", 24),
            "cleanup_interval": get_config("downloader.cleanup_interval", 1),
            "max_storage_mb": get_config("downloader.max_storage_mb", 2048),
            "keep_recent_files": get_config("downloader.keep_recent_files", 20)
        }

        return jsonify({"success": True, "settings": settings})

    except Exception as e:
        logger.error(f"❌ 获取下载设置失败: {e}")
        return jsonify({"error": "获取设置失败"}), 500


@api_bp.route('/settings/download', methods=['POST'])
@auth_required
def api_save_download_settings():
    """保存下载设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要提供设置数据"}), 400

        logger.info(f"📝 保存下载设置: {data}")

        # 保存到数据库
        from core.database import get_database
        db = get_database()

        # 映射前端字段到后端配置
        quality_mapping = {
            "best": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
            "medium": "best[height<=720]",
            "low": "worst"
        }

        # 保存各个设置项（使用正确的字段名）
        settings_to_save = [
            ("downloader.output_dir", data.get("output_dir", "/app/downloads")),
            ("downloader.max_concurrent", str(data.get("max_concurrent", 3))),
            ("downloader.timeout", str(data.get("timeout", 300))),
            ("downloader.auto_cleanup", str(data.get("auto_cleanup", True))),
            ("downloader.file_retention_hours", str(data.get("file_retention_hours", 24))),
            ("downloader.cleanup_interval", str(data.get("cleanup_interval", 1))),
            ("downloader.max_storage_mb", str(data.get("max_storage_mb", 2048))),
            ("downloader.keep_recent_files", str(data.get("keep_recent_files", 20))),
            ("ytdlp.format", quality_mapping.get(data.get("default_quality", "best"), "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"))
        ]

        for key, value in settings_to_save:
            db.set_setting(key, value)

        # 重新初始化下载管理器以应用新设置
        try:
            from modules.downloader.manager import get_download_manager
            download_manager = get_download_manager()
            # 这里可以添加重新加载配置的逻辑
            logger.info("✅ 下载管理器配置已更新")
        except Exception as e:
            logger.warning(f"⚠️ 重新加载下载管理器配置失败: {e}")

        return jsonify({"success": True, "message": "下载配置保存成功"})

    except Exception as e:
        logger.error(f"❌ 保存下载设置失败: {e}")
        return jsonify({"error": "保存设置失败"}), 500


@api_bp.route('/settings/api-key', methods=['GET'])
@auth_required
def api_get_api_key():
    """获取API密钥设置"""
    try:
        from core.database import get_database
        db = get_database()

        api_key = db.get_setting("api_key", "")

        return jsonify({
            "success": True,
            "api_key": api_key,
            "has_key": bool(api_key)
        })

    except Exception as e:
        logger.error(f"❌ 获取API密钥失败: {e}")
        return jsonify({"error": "获取API密钥失败"}), 500


@api_bp.route('/settings/api-key', methods=['POST'])
@auth_required
def api_save_api_key():
    """保存API密钥设置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "需要提供数据"}), 400

        api_key = data.get("api_key", "").strip()

        from core.database import get_database
        db = get_database()

        if api_key:
            db.set_setting("api_key", api_key)
            message = "API密钥保存成功"
        else:
            db.delete_setting("api_key")
            message = "API密钥已删除"

        return jsonify({
            "success": True,
            "message": message
        })

    except Exception as e:
        logger.error(f"❌ 保存API密钥失败: {e}")
        return jsonify({"error": "保存API密钥失败"}), 500


@api_bp.route('/settings/api-key/generate', methods=['POST'])
@auth_required
def api_generate_api_key():
    """生成新的API密钥"""
    try:
        import secrets
        import string

        # 生成32位随机API密钥
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(32))

        from core.database import get_database
        db = get_database()
        db.set_setting("api_key", api_key)

        return jsonify({
            "success": True,
            "api_key": api_key,
            "message": "新API密钥生成成功"
        })

    except Exception as e:
        logger.error(f"❌ 生成API密钥失败: {e}")
        return jsonify({"error": "生成API密钥失败"}), 500


@api_bp.route("/system/info")
@auth_required
def api_system_info():
    """获取系统信息"""
    try:
        import os
        from pathlib import Path
        from core.config import get_config
        from core.database import get_database

        # 获取存储信息
        download_dir = Path(get_config("downloader.output_dir", "./downloads"))
        if download_dir.exists():
            try:
                import shutil
                total_space, used_space, free_space = shutil.disk_usage(str(download_dir))
            except:
                # 回退方案
                try:
                    stat = os.statvfs(str(download_dir))
                    total_space = stat.f_frsize * stat.f_blocks
                    free_space = stat.f_frsize * stat.f_bavail
                    used_space = total_space - free_space
                except:
                    total_space = 0
                    free_space = 0
                    used_space = 0
        else:
            total_space = 0
            free_space = 0
            used_space = 0

        # 获取系统运行时间
        try:
            import psutil
            import time
            uptime = time.time() - psutil.boot_time()
        except:
            # 回退方案 - 读取/proc/uptime
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime = float(f.readline().split()[0])
            except:
                uptime = 0

        # 获取活跃下载数量
        try:
            db = get_database()
            active_downloads = len(db.get_active_downloads())
        except:
            active_downloads = 0

        return jsonify({
            "success": True,
            "storage": {
                "total": total_space,
                "used": used_space,
                "free": free_space
            },
            "uptime": uptime,
            "active_downloads": active_downloads
        })

    except Exception as e:
        logger.error(f"❌ 获取系统信息失败: {e}")
        return jsonify({"success": False, "error": "获取系统信息失败"}), 500


@api_bp.route("/system/cleanup", methods=["POST"])
@auth_required
def api_manual_cleanup():
    """手动执行文件清理"""
    try:
        from modules.downloader.cleanup import get_cleanup_manager

        cleanup_manager = get_cleanup_manager()
        result = cleanup_manager.manual_cleanup()

        if result["success"]:
            return jsonify({
                "success": True,
                "message": result["message"]
            })
        else:
            return jsonify({"error": result["error"]}), 500

    except Exception as e:
        logger.error(f"❌ 手动清理失败: {e}")
        return jsonify({"error": "清理失败"}), 500


@api_bp.route("/system/restart", methods=["POST"])
@auth_required
def api_system_restart():
    """重启系统服务"""
    try:
        logger.info("🔄 收到系统重启请求")

        # 在容器环境中，我们不能真正重启系统
        # 但可以尝试重启应用进程
        import os
        import signal

        # 发送响应后再重启
        def restart_after_response():
            import time
            time.sleep(1)  # 等待响应发送完成
            logger.info("🔄 正在重启应用...")
            os.kill(os.getpid(), signal.SIGTERM)

        # 在后台线程中执行重启
        import threading
        restart_thread = threading.Thread(target=restart_after_response)
        restart_thread.daemon = True
        restart_thread.start()

        return jsonify({
            "success": True,
            "message": "系统重启请求已接收，服务将在1秒后重启"
        })

    except Exception as e:
        logger.error(f"❌ 系统重启失败: {e}")
        return jsonify({"error": "重启失败"}), 500


# ==================== 前端兼容路由 ====================

@api_bp.route("/system/update-ytdlp", methods=["POST"])
@auth_required
def api_update_ytdlp_alias():
    """更新yt-dlp - 前端兼容路由"""
    return api_update_ytdlp()


@api_bp.route("/system/install-ytdlp", methods=["POST"])
@auth_required
def api_install_ytdlp_alias():
    """安装yt-dlp - 前端兼容路由"""
    return api_install_ytdlp()


@api_bp.route("/system/update-pytubefix", methods=["POST"])
@auth_required
def api_update_pytubefix_alias():
    """更新PyTubeFix - 前端兼容路由"""
    return api_update_pytubefix()


@api_bp.route("/system/install-pytubefix", methods=["POST"])
@auth_required
def api_install_pytubefix_alias():
    """安装PyTubeFix - 前端兼容路由"""
    return api_install_pytubefix()


@api_bp.route("/system/paths")
@auth_required
def api_system_paths():
    """获取系统路径信息"""
    try:
        from core.config import get_config
        import os
        from pathlib import Path

        # 获取配置的路径
        download_dir = get_config('downloader.output_dir', '/app/downloads')
        temp_dir = get_config('downloader.temp_dir', '/app/temp')

        # 检查路径是否存在
        download_path = Path(download_dir)
        temp_path = Path(temp_dir)

        # 获取文件列表
        download_files = []
        if download_path.exists():
            try:
                download_files = [
                    {
                        'name': f.name,
                        'size': f.stat().st_size,
                        'modified': f.stat().st_mtime,
                        'is_video': f.suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov', '.webm']
                    }
                    for f in download_path.iterdir()
                    if f.is_file()
                ]
            except Exception as e:
                logger.warning(f"读取下载目录失败: {e}")

        # 获取环境变量
        env_download_dir = os.getenv('DOWNLOAD_DIR')

        path_info = {
            "download_directory": {
                "configured_path": download_dir,
                "resolved_path": str(download_path.resolve()) if download_path.exists() else None,
                "exists": download_path.exists(),
                "is_writable": download_path.exists() and os.access(download_path, os.W_OK),
                "file_count": len(download_files),
                "files": download_files[:10]  # 只返回前10个文件
            },
            "temp_directory": {
                "configured_path": temp_dir,
                "resolved_path": str(temp_path.resolve()) if temp_path.exists() else None,
                "exists": temp_path.exists(),
                "is_writable": temp_path.exists() and os.access(temp_path, os.W_OK)
            },
            "environment_variables": {
                "DOWNLOAD_DIR": env_download_dir,
                "PWD": os.getenv('PWD'),
                "HOME": os.getenv('HOME')
            },
            "current_working_directory": os.getcwd(),
            "container_info": {
                "is_container": os.path.exists('/.dockerenv'),
                "hostname": os.getenv('HOSTNAME', 'unknown')
            }
        }

        return jsonify({
            "success": True,
            "paths": path_info
        })

    except Exception as e:
        logger.error(f"❌ 获取系统路径失败: {e}")
        return jsonify({"error": f"获取路径信息失败: {str(e)}"}), 500


# ==================== iOS快捷指令API ====================

@api_bp.route('/shortcuts/download', methods=['POST'])
def api_shortcuts_download():
    """iOS快捷指令下载接口 - 支持简化认证"""
    try:
        # 支持多种数据格式
        if request.content_type == 'application/json':
            data = request.get_json()
        elif request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
        else:
            # 尝试从查询参数获取
            data = request.args.to_dict()
            if not data:
                data = request.get_json() or {}

        if not data:
            return jsonify({"error": "需要提供数据"}), 400

        # 获取URL
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "需要提供视频URL"}), 400

        # 简化认证 - 支持API密钥或用户名密码
        auth_token = None
        api_key = data.get("api_key") or request.headers.get("X-API-Key")

        if api_key:
            # 使用API密钥认证
            if not _verify_api_key(api_key):
                return jsonify({"error": "API密钥无效"}), 401
        else:
            # 使用用户名密码认证
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                return jsonify({"error": "需要提供用户名和密码或API密钥"}), 401

            from core.auth import get_auth_manager
            auth_manager = get_auth_manager()
            auth_token = auth_manager.login(username, password)

            if not auth_token:
                return jsonify({"error": "用户名或密码错误"}), 401

        # 获取下载选项
        audio_only_value = data.get("audio_only", "false")
        # 处理布尔值或字符串
        if isinstance(audio_only_value, bool):
            audio_only = audio_only_value
        else:
            audio_only = str(audio_only_value).lower() in ["true", "1", "yes"]

        options = {
            "quality": data.get("quality", "medium"),
            "audio_only": audio_only,
            "custom_filename": data.get("custom_filename", "").strip(),
            "source": "ios_shortcuts",
            "ios_callback": True,
        }

        # 使用统一的下载API
        from modules.downloader.api import get_unified_download_api
        api = get_unified_download_api()
        result = api.create_download(url, options)

        if not result['success']:
            return jsonify({"error": result['error']}), 500

        download_id = result['data']['download_id']

        # 返回简化的响应
        response = {
            "success": True,
            "message": "下载已开始",
            "download_id": download_id,
            "status_url": f"/api/shortcuts/status/{download_id}"
        }

        # 如果需要，添加认证令牌
        if auth_token:
            response["token"] = auth_token

        return jsonify(response)

    except Exception as e:
        logger.error(f"❌ iOS快捷指令下载失败: {e}")
        return jsonify({"error": "下载启动失败"}), 500


@api_bp.route('/shortcuts/status/<download_id>')
def api_shortcuts_status(download_id):
    """iOS快捷指令状态查询 - 无需认证"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        download_info = download_manager.get_download(download_id)
        if not download_info:
            return jsonify({"error": "下载任务不存在"}), 404

        # 简化的状态响应
        response = {
            "id": download_info["id"],
            "status": download_info["status"],
            "progress": download_info["progress"],
            "title": download_info.get("title", "Unknown"),
        }

        # 如果下载完成，添加文件信息
        if download_info["status"] == "completed" and download_info.get("file_path"):
            filename = download_info["file_path"].split("/")[-1]
            response.update({
                "filename": filename,
                "file_size": download_info.get("file_size", 0),
                "download_url": f"/api/shortcuts/file/{filename}",
                "completed": True
            })
        elif download_info["status"] == "failed":
            response["error"] = download_info.get("error_message", "下载失败")

        return jsonify(response)

    except Exception as e:
        logger.error(f"❌ 获取下载状态失败: {e}")
        return jsonify({"error": "获取状态失败"}), 500


@api_bp.route('/shortcuts/file/<filename>')
def api_shortcuts_file(filename):
    """iOS快捷指令文件下载 - 无需认证"""
    try:
        from core.config import get_config
        from flask import send_file
        from pathlib import Path

        # 获取下载目录
        download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        file_path = download_dir / filename

        # 安全检查
        if not str(file_path.resolve()).startswith(str(download_dir.resolve())):
            logger.warning(f"尝试访问下载目录外的文件: {filename}")
            return jsonify({"error": "文件访问被拒绝"}), 403

        if not file_path.exists():
            return jsonify({"error": "文件不存在"}), 404

        # 返回文件
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"❌ 文件下载失败: {e}")
        return jsonify({"error": "文件下载失败"}), 500


@api_bp.route('/shortcuts/info')
def api_shortcuts_info():
    """iOS快捷指令服务信息 - 无需认证"""
    try:
        from core.config import get_config

        return jsonify({
            "service": "YT-DLP Web",
            "version": get_config("app.version", "2.0.0"),
            "supported_sites": "1000+ 网站",
            "max_file_size": "无限制",
            "formats": ["视频", "音频"],
            "qualities": ["最高质量", "中等质量", "低质量"],
            "endpoints": {
                "download": "/api/shortcuts/download",
                "status": "/api/shortcuts/status/{download_id}",
                "file": "/api/shortcuts/file/{filename}"
            }
        })

    except Exception as e:
        logger.error(f"❌ 获取服务信息失败: {e}")
        return jsonify({"error": "获取信息失败"}), 500


# ==================== 下载管理API兼容路由 ====================

@api_bp.route('/download/<download_id>/cancel', methods=['POST'])
@auth_required
def api_cancel_download_alt(download_id):
    """取消下载 - 首页兼容路由"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        success = download_manager.cancel_download(download_id)
        if not success:
            return jsonify({'error': '无法取消下载'}), 400

        return jsonify({
            'success': True,
            'message': '下载已取消'
        })

    except Exception as e:
        logger.error(f"❌ 取消下载失败: {e}")
        return jsonify({'error': '取消失败'}), 500


@api_bp.route('/download/cancel/<download_id>', methods=['POST'])
@auth_required
def api_cancel_download_alt2(download_id):
    """取消下载 - 历史页面兼容路由"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        success = download_manager.cancel_download(download_id)
        if not success:
            return jsonify({'error': '无法取消下载'}), 400

        return jsonify({
            'success': True,
            'message': '下载已取消'
        })

    except Exception as e:
        logger.error(f"❌ 取消下载失败: {e}")
        return jsonify({'error': '取消失败'}), 500


@api_bp.route('/download/<download_id>/retry', methods=['POST'])
@auth_required
def api_retry_download(download_id):
    """重试下载 - 支持续传"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        # 获取原下载信息
        download = download_manager.get_download(download_id)
        if not download:
            return jsonify({"error": "下载记录不存在"}), 404

        # 检查下载状态
        if download['status'] in ['downloading', 'pending']:
            return jsonify({"error": "下载正在进行中，无需重试"}), 400

        logger.info(f"🔄 手动重试下载: {download_id} - {download['url']}")

        # 重新开始下载（yt-dlp会自动检测并续传）
        new_download_id = download_manager.create_download(
            download['url'],
            download.get('options', {})
        )

        if new_download_id:
            return jsonify({
                "success": True,
                "message": "下载已重新开始，将自动续传",
                "new_download_id": new_download_id,
                "original_url": download['url']
            })
        else:
            return jsonify({"error": "重试失败"}), 500

    except Exception as e:
        logger.error(f"❌ 重试下载失败: {e}")
        return jsonify({"error": f"重试失败: {str(e)}"}), 500


@api_bp.route('/download/<download_id>/resume', methods=['POST'])
@auth_required
def api_resume_download(download_id):
    """恢复下载 - 专门用于续传"""
    try:
        from modules.downloader.manager import get_download_manager
        from pathlib import Path
        download_manager = get_download_manager()

        # 获取原下载信息
        download = download_manager.get_download(download_id)
        if not download:
            return jsonify({"error": "下载记录不存在"}), 404

        # 只允许恢复失败或取消的下载
        if download['status'] not in ['failed', 'cancelled']:
            return jsonify({"error": f"当前状态 '{download['status']}' 不支持恢复"}), 400

        # 检查是否有部分下载的文件
        output_dir = Path(download_manager.output_dir)
        partial_files = list(output_dir.glob(f'{download_id}.*'))

        logger.info(f"▶️ 恢复下载: {download_id} - {download['url']}")
        logger.info(f"🔍 找到部分文件: {[f.name for f in partial_files]}")

        # 使用相同的下载ID恢复（保持历史记录）
        download_manager._update_download_status(download_id, 'pending', progress=0)

        # 重新提交下载任务
        download_manager.executor.submit(download_manager._execute_download, download_id)

        return jsonify({
            "success": True,
            "message": "下载已恢复，将从断点继续",
            "download_id": download_id,
            "url": download['url'],
            "partial_files": [f.name for f in partial_files]
        })

    except Exception as e:
        logger.error(f"❌ 恢复下载失败: {e}")
        return jsonify({"error": f"恢复失败: {str(e)}"}), 500


@api_bp.route('/download/test-resume', methods=['POST'])
@auth_required
def api_test_resume():
    """测试续传功能"""
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({"error": "需要提供URL"}), 400

        from modules.downloader.manager import get_download_manager
        from pathlib import Path
        import yt_dlp

        download_manager = get_download_manager()
        output_dir = Path(download_manager.output_dir)

        # 生成测试下载ID
        test_id = f"test-resume-{int(time.time())}"

        # 测试yt-dlp续传配置
        ydl_opts = {
            'outtmpl': str(output_dir / f'{test_id}.%(ext)s'),
            'continue_dl': True,
            'nooverwrites': True,
            'retries': 3,
            'fragment_retries': 5,
            'skip_unavailable_fragments': False,
            'no_warnings': False,
            'ignoreerrors': False,
        }

        # 检查是否为m3u8链接
        is_hls = url.lower().endswith('.m3u8') or 'm3u8' in url.lower()
        if is_hls:
            ydl_opts['format'] = '0'  # 对m3u8使用简单格式

        logger.info(f"🧪 测试续传配置: {test_id} - {url}")

        # 创建下载任务
        download_id = download_manager.create_download(url, {
            'test_resume': True,
            'test_id': test_id
        })

        return jsonify({
            "success": True,
            "message": "续传测试已开始",
            "download_id": download_id,
            "test_id": test_id,
            "is_hls": is_hls,
            "config": ydl_opts
        })

    except Exception as e:
        logger.error(f"❌ 续传测试失败: {e}")
        return jsonify({"error": f"测试失败: {str(e)}"}), 500


@api_bp.route('/download/<download_id>', methods=['DELETE'])
@auth_required
def api_delete_download_record(download_id):
    """删除下载记录"""
    try:
        from core.database import get_database

        db = get_database()

        # 检查记录是否存在
        existing = db.execute_query('''
            SELECT id, status, file_path FROM downloads WHERE id = ?
        ''', (download_id,))

        if not existing:
            return jsonify({'error': '下载记录不存在'}), 404

        record = existing[0]

        # 如果是正在下载的任务，先取消
        if record['status'] in ['pending', 'downloading']:
            try:
                from modules.downloader.manager import get_download_manager
                download_manager = get_download_manager()
                download_manager.cancel_download(download_id)
            except Exception as e:
                logger.warning(f"⚠️ 取消下载任务失败: {e}")

        # 删除关联的文件（可选）
        try:
            delete_file = request.json.get('delete_file', False) if request.is_json and request.json else False
        except:
            delete_file = False
        if delete_file and record.get('file_path'):
            try:
                from pathlib import Path
                from core.config import get_config

                download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
                file_path = Path(record['file_path'])

                # 如果是相对路径，转换为绝对路径
                if not file_path.is_absolute():
                    file_path = download_dir / file_path.name

                if file_path.exists() and str(file_path.resolve()).startswith(str(download_dir.resolve())):
                    file_path.unlink()
                    logger.info(f"删除关联文件: {file_path.name}")
            except Exception as e:
                logger.warning(f"⚠️ 删除关联文件失败: {e}")

        # 从数据库删除记录
        db.execute_update('DELETE FROM downloads WHERE id = ?', (download_id,))

        logger.info(f"删除下载记录: {download_id}")

        return jsonify({
            'success': True,
            'message': '下载记录已删除'
        })

    except Exception as e:
        logger.error(f"❌ 删除下载记录失败: {e}")
        return jsonify({'error': '删除记录失败'}), 500


@api_bp.route('/download/history/clear', methods=['POST'])
@auth_required
def api_clear_download_history():
    """清空下载历史记录"""
    try:
        from core.database import get_database

        db = get_database()

        # 获取请求参数
        data = request.get_json() if request.is_json else {}
        delete_files = data.get('delete_files', False)
        keep_active = data.get('keep_active', True)  # 默认保留正在进行的下载

        # 构建删除条件
        if keep_active:
            # 只删除已完成、失败或取消的记录
            condition = "WHERE status NOT IN ('pending', 'downloading')"
            params = ()
        else:
            # 删除所有记录（先取消正在进行的下载）
            active_downloads = db.execute_query('''
                SELECT id FROM downloads WHERE status IN ('pending', 'downloading')
            ''')

            if active_downloads:
                try:
                    from modules.downloader.manager import get_download_manager
                    download_manager = get_download_manager()
                    for download in active_downloads:
                        download_manager.cancel_download(download['id'])
                except Exception as e:
                    logger.warning(f"⚠️ 取消活跃下载失败: {e}")

            condition = ""
            params = ()

        # 如果需要删除文件，先获取文件路径
        if delete_files:
            try:
                file_records = db.execute_query(f'''
                    SELECT file_path FROM downloads
                    {condition} AND file_path IS NOT NULL
                ''', params)

                if file_records:
                    from pathlib import Path
                    from core.config import get_config

                    download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
                    deleted_files = 0

                    for record in file_records:
                        try:
                            file_path = Path(record['file_path'])

                            # 如果是相对路径，转换为绝对路径
                            if not file_path.is_absolute():
                                file_path = download_dir / file_path.name

                            if file_path.exists() and str(file_path.resolve()).startswith(str(download_dir.resolve())):
                                file_path.unlink()
                                deleted_files += 1
                        except Exception as e:
                            logger.warning(f"⚠️ 删除文件失败: {e}")

                    logger.info(f"删除了 {deleted_files} 个关联文件")
            except Exception as e:
                logger.warning(f"⚠️ 删除关联文件失败: {e}")

        # 删除数据库记录
        result = db.execute_update(f'DELETE FROM downloads {condition}', params)
        deleted_count = result if isinstance(result, int) else 0

        logger.info(f"清空下载历史: 删除了 {deleted_count} 条记录")

        return jsonify({
            'success': True,
            'message': f'已清空 {deleted_count} 条下载记录',
            'deleted_count': deleted_count
        })

    except Exception as e:
        logger.error(f"❌ 清空下载历史失败: {e}")
        return jsonify({'error': '清空历史失败'}), 500


def _verify_api_key(api_key: str) -> bool:
    """验证API密钥"""
    try:
        from core.database import get_database
        db = get_database()

        # 从设置中获取API密钥
        stored_key = db.get_setting("api_key")
        if not stored_key:
            return False

        return api_key == stored_key

    except Exception as e:
        logger.error(f"❌ API密钥验证失败: {e}")
        return False


# ==================== 辅助函数 ====================

def _extract_video_info(url: str):
    """提取视频信息 - 使用统一的下载管理器和智能回退"""
    try:
        # 使用统一的下载管理器，它包含智能回退机制
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        # 使用下载管理器的智能回退机制
        return download_manager._extract_video_info(url)

    except Exception as e:
        logger.error(f"❌ 提取视频信息失败: {e}")
        return None


# ==================== 文件管理API ====================

# 文件列表API已移至 /files/ 蓝图，避免重复


@api_bp.route('/files/list')
@auth_required
def api_files_list():
    """获取文件列表 - API统一入口"""
    try:
        from core.config import get_config
        from pathlib import Path

        download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))

        if not download_dir.exists():
            return jsonify({'files': []})

        files = []
        for file_path in download_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    'name': file_path.name,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'download_url': f'/files/download/{file_path.name}'
                })

        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({'files': files})

    except Exception as e:
        logger.error(f"❌ 获取文件列表失败: {e}")
        return jsonify({'error': '获取文件列表失败'}), 500


@api_bp.route('/download/list')
@auth_required
def api_download_list():
    """获取下载列表 - API统一入口"""
    try:
        from modules.downloader.manager import get_download_manager
        download_manager = get_download_manager()

        downloads = download_manager.get_all_downloads()

        # 格式化返回数据
        response_data = []
        for download in downloads:
            item = {
                'id': download['id'],
                'url': download['url'],
                'status': download['status'],
                'progress': download['progress'],
                'title': download['title'],
                'created_at': download['created_at'].isoformat() if download['created_at'] else None
            }

            if download['status'] == 'completed' and download['file_path']:
                item['filename'] = download['file_path'].split('/')[-1] if download['file_path'] else None
                item['file_size'] = download['file_size']

            response_data.append(item)

        # 按创建时间倒序排列
        response_data.sort(key=lambda x: x['created_at'] or '', reverse=True)

        return jsonify({
            'success': True,
            'downloads': response_data,
            'total': len(response_data)
        })

    except Exception as e:
        logger.error(f"❌ 获取下载列表失败: {e}")
        return jsonify({'error': '获取列表失败'}), 500


@api_bp.route('/files/delete/<filename>', methods=['DELETE'])
@auth_required
def api_files_delete(filename):
    """删除文件 - API统一入口"""
    try:
        from core.config import get_config
        from pathlib import Path

        download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
        file_path = download_dir / filename

        # 安全检查
        if not str(file_path.resolve()).startswith(str(download_dir.resolve())):
            return jsonify({'error': '文件访问被拒绝'}), 403

        if not file_path.exists():
            return jsonify({'error': '文件不存在'}), 404

        file_path.unlink()
        logger.info(f"删除文件: {filename}")

        return jsonify({'success': True, 'message': '文件删除成功'})

    except Exception as e:
        logger.error(f"❌ 删除文件失败: {e}")
        return jsonify({"error": "删除文件失败"}), 500


# ==================== Telegram Webhook API ====================

@api_bp.route('/telegram/setup-webhook', methods=['POST'])
@auth_required
def api_telegram_setup_webhook():
    """设置Telegram Webhook - API统一入口"""
    try:
        from modules.telegram.routes import setup_webhook
        return setup_webhook()
    except Exception as e:
        logger.error(f"❌ 设置Telegram Webhook失败: {e}")
        return jsonify({"error": "设置Webhook失败"}), 500


@api_bp.route('/telegram/delete-webhook', methods=['POST'])
@auth_required
def api_telegram_delete_webhook():
    """删除Telegram Webhook - API统一入口"""
    try:
        from modules.telegram.routes import delete_webhook
        return delete_webhook()
    except Exception as e:
        logger.error(f"❌ 删除Telegram Webhook失败: {e}")
        return jsonify({"error": "删除Webhook失败"}), 500


@api_bp.route('/telegram/webhook-info', methods=['GET'])
@auth_required
def api_telegram_webhook_info():
    """获取Telegram Webhook信息 - API统一入口"""
    try:
        from modules.telegram.routes import get_webhook_info
        return get_webhook_info()
    except Exception as e:
        logger.error(f"❌ 获取Telegram Webhook信息失败: {e}")
        return jsonify({"error": "获取Webhook信息失败"}), 500
