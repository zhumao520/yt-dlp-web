# -*- coding: utf-8 -*-
"""
Telegram路由 - 机器人webhook和API接口
"""

import logging
import re
import os
import time
from pathlib import Path
from flask import Blueprint, request, jsonify
from core.auth import auth_required
from core.config import get_config
from core.filename_extractor import extract_filename_from_url

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)


# ==================== 现代化 API 端点 ====================

@telegram_bp.route('/api/test-message', methods=['POST'])
@auth_required
def send_test_message_modern():
    """发送测试消息 - 现代化版本"""
    try:
        from .notifier import get_telegram_notifier

        data = request.get_json() or {}
        message = data.get('message', '🤖 这是一条测试消息')

        notifier = get_telegram_notifier()

        if not notifier.is_enabled():
            return jsonify({
                'success': False,
                'error': 'Telegram 未启用'
            }), 400

        success = notifier.send_message(message)

        if success:
            return jsonify({
                'success': True,
                'message': '测试消息发送成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '消息发送失败'
            }), 400

    except Exception as e:
        logger.error(f'发送测试消息失败: {e}')
        return jsonify({'error': '发送失败'}), 500


# ==================== Webhook 接收端点 ====================

@telegram_bp.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Telegram Webhook接收端点"""
    try:
        logger.info("=== 收到 Telegram Webhook 请求 ===")
        logger.info(f"请求头: {dict(request.headers)}")
        logger.info(f"请求来源: {request.remote_addr}")

        # 获取配置
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()
        
        if not config or not config.get('enabled'):
            logger.warning("Telegram未启用，拒绝请求")
            return jsonify({'error': 'Telegram未启用'}), 403

        # 解析消息
        update = request.get_json()
        logger.info(f"收到的更新数据: {update}")

        if not update:
            logger.error("无效的消息格式")
            return jsonify({'error': '无效的消息格式'}), 400

        # 使用现代化路由处理器
        from modules.telegram.modern_routes import get_modern_telegram_router
        router = get_modern_telegram_router()
        result = router.process_telegram_message(update, config)
        logger.info(f"消息处理结果: {result}")

        return jsonify({'success': True, 'result': result})

    except Exception as e:
        logger.error(f'Telegram webhook处理失败: {e}')
        return jsonify({'error': '处理失败'}), 500


def setup_webhook():
    """设置Telegram Webhook"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 获取请求数据
        request_data = request.get_json() or {}
        custom_webhook_url = request_data.get('webhook_url')

        # 构建 Webhook URL
        if custom_webhook_url and custom_webhook_url.strip():
            webhook_url = custom_webhook_url.strip()
            logger.info(f'使用自定义 Webhook URL: {webhook_url}')
        else:
            # 使用默认URL，但检查是否为HTTPS
            base_url = request.url_root.rstrip('/')
            if base_url.startswith('http://'):
                # 如果是HTTP，给出警告但仍然尝试设置
                logger.warning("⚠️ 检测到HTTP协议，Telegram要求HTTPS，可能会失败")
            webhook_url = base_url + '/telegram/webhook'
            logger.info(f'使用默认 Webhook URL: {webhook_url}')

        # 验证URL格式
        if not webhook_url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'error': 'Webhook URL格式无效，必须以http://或https://开头'
            }), 400

        # 设置webhook
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

        webhook_data = {'url': webhook_url}

        logger.info(f"🔄 正在设置Webhook: {webhook_url}")
        response = requests.post(telegram_api_url, json=webhook_data, timeout=30)

        # 详细记录响应
        logger.info(f"📡 Telegram API响应状态: {response.status_code}")
        logger.info(f"📡 Telegram API响应内容: {response.text}")

        response.raise_for_status()
        result = response.json()

        if result.get('ok'):
            logger.info(f"✅ Webhook设置成功: {webhook_url}")
            return jsonify({
                'success': True,
                'message': 'Webhook设置成功',
                'webhook_url': webhook_url
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ Webhook设置失败: {error_msg}")

            # 提供更友好的错误信息
            if 'HTTPS' in error_msg.upper():
                error_msg += ' (提示: Telegram要求Webhook URL使用HTTPS协议)'
            elif 'URL' in error_msg.upper():
                error_msg += ' (提示: 请检查URL是否可以从外网访问)'

            return jsonify({
                'success': False,
                'error': f'Webhook设置失败: {error_msg}'
            }), 400

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 网络请求失败: {e}")
        return jsonify({
            'success': False,
            'error': f'网络请求失败: {str(e)}'
        }), 500
    except Exception as e:
        logger.error(f"❌ 设置Webhook失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/api/delete-webhook', methods=['POST'])
@auth_required
def delete_webhook():
    """删除Telegram Webhook"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 删除webhook
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

        response = requests.post(telegram_api_url, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get('ok'):
            logger.info("✅ Webhook删除成功")
            return jsonify({
                'success': True,
                'message': 'Webhook删除成功'
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ Webhook删除失败: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'Webhook删除失败: {error_msg}'
            }), 400

    except Exception as e:
        logger.error(f"❌ 删除Webhook失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@telegram_bp.route('/api/webhook-info', methods=['GET'])
@auth_required
def get_webhook_info():
    """获取Telegram Webhook信息"""
    try:
        from core.database import get_database
        db = get_database()
        config = db.get_telegram_config()

        if not config or not config.get('bot_token'):
            return jsonify({
                'success': False,
                'error': '请先配置 Bot Token'
            }), 400

        # 获取webhook信息
        import requests
        bot_token = config['bot_token']
        telegram_api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

        response = requests.get(telegram_api_url, timeout=30)
        response.raise_for_status()

        result = response.json()

        if result.get('ok'):
            logger.info("✅ 获取Webhook信息成功")
            return jsonify({
                'success': True,
                'webhook_info': result.get('result', {})
            })
        else:
            error_msg = result.get('description', '未知错误')
            logger.error(f"❌ 获取Webhook信息失败: {error_msg}")
            return jsonify({
                'success': False,
                'error': f'获取Webhook信息失败: {error_msg}'
            }), 400

    except Exception as e:
        logger.error(f"❌ 获取Webhook信息失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 异步上传接口 - 学习ytdlbot ====================

@telegram_bp.route('/api/upload/async', methods=['POST'])
@auth_required
def upload_file_async():
    """异步上传文件接口 - 学习ytdlbot的异步策略"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少请求数据'}), 400

        file_path = data.get('file_path')
        caption = data.get('caption', '')

        if not file_path:
            return jsonify({'error': '缺少文件路径'}), 400

        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return jsonify({'error': f'文件不存在: {file_path}'}), 404

        # 获取任务管理器
        try:
            from modules.telegram.tasks import get_task_manager
            task_manager = get_task_manager()

            if not task_manager.is_async_available():
                # SQLite队列总是可用，这种情况不应该发生
                logger.error("❌ SQLite任务队列不可用")
                return jsonify({'error': 'SQLite任务队列不可用'}), 500

            # 提交异步任务
            task_id = task_manager.submit_upload_task(file_path, caption)

            if task_id:
                file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'status': 'queued',
                    'file_path': file_path,
                    'file_size_mb': round(file_size_mb, 2),
                    'message': '上传任务已提交，请使用task_id查询进度'
                })
            else:
                return jsonify({'error': '提交异步任务失败'}), 500

        except ImportError:
            # SQLite队列总是可用，不需要回退
            logger.error("❌ 任务管理器导入失败")
            return jsonify({'error': '任务管理器不可用'}), 500

    except Exception as e:
        logger.error(f"❌ 异步上传接口错误: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/task/<task_id>/status', methods=['GET'])
@auth_required
def get_task_status(task_id):
    """获取任务状态"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        status = task_manager.get_task_status(task_id)
        return jsonify(status)

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取任务状态失败: {e}")
        return jsonify({'error': str(e)}), 500


def upload_file_sync_fallback(file_path: str, caption: str = ''):
    """同步上传回退方案"""
    try:
        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return jsonify({'error': f'文件不存在: {file_path}'}), 404

        # 创建上传器
        from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader
        from modules.telegram.services.config_service import get_telegram_config_service

        config_service = get_telegram_config_service()
        config = config_service.get_config()

        if not config:
            return jsonify({'error': 'Telegram配置未找到'}), 500

        uploader = ModernHybridUploader(config)

        if not uploader.is_available():
            return jsonify({'error': '没有可用的Telegram上传器'}), 500

        # 执行同步上传
        file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
        logger.info(f"📤 开始同步上传: {file_path_obj.name} ({file_size_mb:.1f}MB)")

        result = uploader.send_file(file_path, caption)

        if result:
            return jsonify({
                'success': True,
                'status': 'completed',
                'file_path': file_path,
                'file_size_mb': round(file_size_mb, 2),
                'message': '文件上传成功'
            })
        else:
            return jsonify({'error': '文件上传失败'}), 500

    except Exception as e:
        logger.error(f"❌ 同步上传失败: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== 批量上传和队列管理接口 ====================

@telegram_bp.route('/api/upload/batch', methods=['POST'])
@auth_required
def batch_upload_async():
    """批量异步上传文件接口 - 支持多文件并发上传"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少请求数据'}), 400

        file_paths = data.get('file_paths', [])
        caption = data.get('caption', '')

        if not file_paths:
            return jsonify({'error': '缺少文件路径列表'}), 400

        if not isinstance(file_paths, list):
            return jsonify({'error': 'file_paths必须是数组'}), 400

        # 检查文件是否存在
        valid_files = []
        invalid_files = []

        for file_path in file_paths:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                valid_files.append(file_path)
            else:
                invalid_files.append(file_path)

        if not valid_files:
            return jsonify({'error': '没有有效的文件可以上传'}), 400

        # 获取任务管理器
        try:
            from modules.telegram.tasks import get_task_manager
            task_manager = get_task_manager()

            if not task_manager.is_async_available():
                # SQLite队列总是可用，这种情况不应该发生
                logger.error("❌ SQLite任务队列不可用")
                return jsonify({'error': 'SQLite任务队列不可用'}), 500

            # 提交异步批量任务
            task_id = task_manager.submit_batch_upload_task(valid_files, caption)

            if task_id:
                total_size_mb = sum(Path(f).stat().st_size for f in valid_files) / (1024 * 1024)
                return jsonify({
                    'success': True,
                    'task_id': task_id,
                    'status': 'queued',
                    'total_files': len(file_paths),
                    'valid_files': len(valid_files),
                    'invalid_files': len(invalid_files),
                    'total_size_mb': round(total_size_mb, 2),
                    'message': '批量上传任务已提交，请使用task_id查询进度'
                })
            else:
                return jsonify({'error': '提交异步批量任务失败'}), 500

        except ImportError:
            # SQLite队列总是可用，不需要回退
            logger.error("❌ 任务管理器导入失败")
            return jsonify({'error': '任务管理器不可用'}), 500

    except Exception as e:
        logger.error(f"❌ 批量上传接口错误: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/status', methods=['GET'])
@auth_required
def get_queue_status():
    """获取上传队列状态"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        status = task_manager.get_queue_status()
        return jsonify(status)

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取队列状态失败: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/tasks', methods=['GET'])
@auth_required
def get_all_tasks():
    """获取所有跟踪的任务"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        tasks = task_manager.get_all_tasks()
        return jsonify({'tasks': tasks, 'total': len(tasks)})

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 获取任务列表失败: {e}")
        return jsonify({'error': str(e)}), 500


@telegram_bp.route('/api/queue/cleanup', methods=['POST'])
@auth_required
def cleanup_completed_tasks():
    """清理已完成的任务"""
    try:
        from modules.telegram.tasks import get_task_manager
        task_manager = get_task_manager()

        if not task_manager.is_async_available():
            return jsonify({'error': 'SQLite任务队列不可用'}), 503

        cleaned_count = task_manager.cleanup_completed_tasks()
        return jsonify({
            'success': True,
            'cleaned_count': cleaned_count,
            'message': f'已清理 {cleaned_count} 个已完成的任务'
        })

    except ImportError:
        return jsonify({'error': '任务管理器不可用'}), 503
    except Exception as e:
        logger.error(f"❌ 清理任务失败: {e}")
        return jsonify({'error': str(e)}), 500


def batch_upload_sync_fallback(file_paths: list, caption: str = ''):
    """同步批量上传回退方案"""
    try:
        from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader
        from modules.telegram.services.config_service import get_telegram_config_service

        config_service = get_telegram_config_service()
        config = config_service.get_config()

        if not config:
            return jsonify({'error': 'Telegram配置未找到'}), 500

        uploader = ModernHybridUploader(config)

        if not uploader.is_available():
            return jsonify({'error': '没有可用的Telegram上传器'}), 500

        # 执行同步批量上传
        successful_uploads = []
        failed_uploads = []

        for i, file_path in enumerate(file_paths):
            try:
                logger.info(f"📤 同步上传文件 {i+1}/{len(file_paths)}: {file_path}")
                result = uploader.send_file(file_path, caption)

                if result:
                    successful_uploads.append(file_path)
                else:
                    failed_uploads.append(file_path)

            except Exception as e:
                logger.error(f"❌ 文件上传异常: {file_path} - {e}")
                failed_uploads.append(file_path)

        success_rate = len(successful_uploads) / len(file_paths) * 100 if file_paths else 0

        return jsonify({
            'success': True,
            'status': 'completed',
            'total_files': len(file_paths),
            'successful_uploads': len(successful_uploads),
            'failed_uploads': len(failed_uploads),
            'success_rate': round(success_rate, 2),
            'successful_files': successful_uploads,
            'failed_files': failed_uploads,
            'message': f'同步批量上传完成: {len(successful_uploads)}/{len(file_paths)} 成功'
        })

    except Exception as e:
        logger.error(f"❌ 同步批量上传失败: {e}")
        return jsonify({'error': str(e)}), 500
