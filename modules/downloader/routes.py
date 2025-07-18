# -*- coding: utf-8 -*-
"""
下载路由 - 下载相关API接口
"""

import logging
from flask import Blueprint, request, jsonify
from core.auth import auth_required
from core.filename_extractor import apply_url_filename_to_options

logger = logging.getLogger(__name__)

downloader_bp = Blueprint('downloader', __name__)


@downloader_bp.route('/start', methods=['POST'])
@auth_required
def start_download():
    """开始下载"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': '需要提供URL'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL不能为空'}), 400
        
        # 验证URL格式
        if not _validate_url(url):
            return jsonify({'error': 'URL格式无效'}), 400
        
        # 🔍 调试接收到的数据
        logger.info(f"📥 接收到下载请求数据:")
        logger.info(f"   URL: {url}")
        logger.info(f"   custom_filename: '{data.get('custom_filename', '')}' (长度: {len(data.get('custom_filename', ''))})")
        logger.info(f"   quality: {data.get('quality', 'high')}")
        logger.info(f"   audio_only: {data.get('audio_only', False)}")
        logger.info(f"   完整data: {data}")

        # 获取下载选项
        options = {
            'quality': data.get('quality', 'high'),
            'audio_only': data.get('audio_only', False),
            'format': data.get('format'),
            'custom_filename': data.get('custom_filename', '').strip(),
            'source': 'web_interface',
            'client_id': data.get('client_id')  # 🔧 传递客户端ID用于精准推送
        }

        logger.info(f"🔧 处理后的options: {options}")

        # 🔧 应用URL中的自定义文件名（如果没有手动输入）
        options = apply_url_filename_to_options(url, options)
        
        # 创建下载任务
        from .manager import get_download_manager
        download_manager = get_download_manager()
        download_id = download_manager.create_download(url, options)
        
        return jsonify({
            'success': True,
            'message': '下载已开始',
            'download_id': download_id
        })
        
    except Exception as e:
        logger.error(f"❌ 开始下载失败: {e}")
        return jsonify({'error': '下载启动失败'}), 500

@downloader_bp.route('/active', methods=['GET'])
def get_active_downloads():
    """获取活跃下载任务 - 用于页面刷新后恢复进度跟踪"""
    try:
        from .manager import get_download_manager
        download_manager = get_download_manager()

        # 获取所有正在进行的下载任务
        active_downloads = []
        for download_id, download_info in download_manager.downloads.items():
            status = download_info.get('status', 'unknown')
            if status in ['pending', 'downloading']:
                download_data = {
                    'download_id': download_id,
                    'status': status,
                    'progress': download_info.get('progress', 0),
                    'title': download_info.get('title', 'Unknown'),
                    'url': download_info.get('url', ''),
                    'created_at': download_info.get('created_at', ''),
                    'client_id': download_info.get('client_id', '')
                }
                active_downloads.append(download_data)

        logger.info(f"📊 返回 {len(active_downloads)} 个活跃下载任务")
        return jsonify({
            'success': True,
            'active_downloads': active_downloads,
            'count': len(active_downloads)
        })

    except Exception as e:
        logger.error(f"获取活跃下载失败: {e}")
        return jsonify({'error': str(e)}), 500


@downloader_bp.route('/status/<download_id>')
@auth_required
def get_download_status(download_id):
    """获取下载状态"""
    try:
        from .manager import get_download_manager
        download_manager = get_download_manager()
        
        download_info = download_manager.get_download(download_id)
        if not download_info:
            return jsonify({'error': '下载任务不存在'}), 404
        
        # 格式化返回数据
        response_data = {
            'id': download_info['id'],
            'url': download_info['url'],
            'status': download_info['status'],
            'progress': download_info['progress'],
            'title': download_info['title'],
            'created_at': download_info['created_at'].isoformat() if download_info['created_at'] else None,
            'completed_at': download_info['completed_at'].isoformat() if download_info['completed_at'] else None
        }
        
        # 添加文件信息（如果已完成）
        if download_info['status'] == 'completed' and download_info['file_path']:
            from pathlib import Path
            file_path = Path(download_info['file_path'])
            file_size = download_info.get('file_size', 0) or 0

            response_data.update({
                'filename': file_path.name,
                'file_path': download_info['file_path'],
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2) if file_size > 0 else 0.0,
                'download_url': f"/files/download/{file_path.name}"
            })

            # 保持向后兼容的file_info结构
            response_data['file_info'] = {
                'path': download_info['file_path'],
                'size': file_size,
                'filename': file_path.name
            }
        
        # 添加错误信息（如果失败）
        if download_info['status'] == 'failed' and download_info['error_message']:
            response_data['error_message'] = download_info['error_message']
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ 获取下载状态失败: {e}")
        return jsonify({'error': '获取状态失败'}), 500


@downloader_bp.route('/list')
@auth_required
def list_downloads():
    """获取下载列表"""
    try:
        from .manager import get_download_manager
        download_manager = get_download_manager()
        
        downloads = download_manager.get_all_downloads()
        
        # 格式化返回数据
        response_data = []
        for download in downloads:
            # 处理created_at字段，可能是datetime对象或字符串
            created_at = download['created_at']
            if created_at:
                if hasattr(created_at, 'isoformat'):
                    # 是datetime对象
                    created_at_str = created_at.isoformat()
                else:
                    # 是字符串，直接使用
                    created_at_str = str(created_at)
            else:
                created_at_str = None

            item = {
                'id': download['id'],
                'url': download['url'],
                'status': download['status'],
                'progress': download['progress'],
                'title': download['title'],
                'created_at': created_at_str
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


@downloader_bp.route('/cancel/<download_id>', methods=['POST'])
@auth_required
def cancel_download(download_id):
    """取消下载"""
    try:
        from .manager import get_download_manager
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


@downloader_bp.route('/info', methods=['POST'])
@auth_required
def get_video_info():
    """获取视频信息（不下载）"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': '需要提供URL'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL不能为空'}), 400
        
        # 验证URL格式
        if not _validate_url(url):
            return jsonify({'error': 'URL格式无效'}), 400
        
        # 提取视频信息
        video_info = _extract_video_info(url)
        if not video_info:
            return jsonify({'error': '无法获取视频信息'}), 400
        
        # 格式化返回数据
        response_data = {
            'title': video_info.get('title', 'Unknown'),
            'description': video_info.get('description', ''),
            'duration': video_info.get('duration'),
            'uploader': video_info.get('uploader', ''),
            'upload_date': video_info.get('upload_date', ''),
            'view_count': video_info.get('view_count'),
            'thumbnail': video_info.get('thumbnail', ''),
            'formats': []
        }
        
        # 添加可用格式信息
        if 'formats' in video_info:
            for fmt in video_info['formats'][:10]:  # 限制返回前10个格式
                format_info = {
                    'format_id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': fmt.get('resolution', 'audio only' if fmt.get('vcodec') == 'none' else 'unknown'),
                    'filesize': fmt.get('filesize'),
                    'quality': fmt.get('quality')
                }
                response_data['formats'].append(format_info)
        
        return jsonify({
            'success': True,
            'video_info': response_data
        })
        
    except Exception as e:
        logger.error(f"❌ 获取视频信息失败: {e}")
        return jsonify({'error': '获取信息失败'}), 500


def _validate_url(url: str) -> bool:
    """验证URL格式"""
    try:
        import re

        # 基本URL格式检查
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(url):
            return False

        # 检查URL长度
        if len(url) > 2048:
            return False

        # 检查是否包含危险字符（移除&，因为URL查询参数需要它）
        dangerous_chars = ['<', '>', '"', "'", '\n', '\r', '\t']
        if any(char in url for char in dangerous_chars):
            return False

        return True

    except Exception:
        return False


def _extract_video_info(url: str):
    """提取视频信息"""
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,   # 防止播放列表展开
            'noplaylist': True      # 只处理单个视频，忽略播放列表
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
            
    except Exception as e:
        logger.error(f"❌ 提取视频信息失败: {e}")
        return None
