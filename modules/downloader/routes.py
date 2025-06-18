# -*- coding: utf-8 -*-
"""
下载路由 - 下载相关API接口
"""

import logging
from flask import Blueprint, request, jsonify
from core.auth import auth_required

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
        
        # 获取下载选项
        options = {
            'quality': data.get('quality', 'medium'),
            'audio_only': data.get('audio_only', False),
            'format': data.get('format'),
            'custom_filename': data.get('custom_filename', '').strip(),
            'source': 'web_interface'
        }
        
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
            response_data['file_info'] = {
                'path': download_info['file_path'],
                'size': download_info['file_size'],
                'filename': download_info['file_path'].split('/')[-1] if download_info['file_path'] else None
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
