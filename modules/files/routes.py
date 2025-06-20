# -*- coding: utf-8 -*-
"""
文件管理路由 - 文件下载和管理
"""

import os
import logging
from pathlib import Path
from flask import Blueprint, send_file, jsonify, abort
from core.auth import auth_required

logger = logging.getLogger(__name__)

files_bp = Blueprint('files', __name__)


@files_bp.route('/download/<filename>')
@auth_required
def download_file(filename):
    """下载文件"""
    try:
        from core.config import get_config
        from flask import request

        # 获取下载目录
        download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        file_path = download_dir / filename

        # 安全检查：确保文件在下载目录内
        if not str(file_path.resolve()).startswith(str(download_dir.resolve())):
            logger.warning(f"尝试访问下载目录外的文件: {filename}")
            abort(403)

        # 检查文件是否存在
        if not file_path.exists():
            logger.warning(f"文件不存在: {filename}")
            abort(404)

        # 检查是否为在线播放请求
        is_streaming = request.args.get('stream') == '1'

        if is_streaming and _is_video_file(filename):
            # 流媒体播放
            logger.info(f"流媒体播放: {filename}")
            return send_file(file_path, as_attachment=False, mimetype=_get_video_mimetype(filename))
        else:
            # 普通下载
            logger.info(f"下载文件: {filename}")
            return send_file(file_path, as_attachment=True)

    except Exception as e:
        logger.error(f"文件访问失败: {e}")
        abort(500)


@files_bp.route('/stream/<filename>')
@auth_required
def stream_file(filename):
    """流媒体播放文件（支持Range请求）"""
    try:
        from core.config import get_config
        from flask import request, Response
        import os

        # 获取下载目录
        download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        file_path = download_dir / filename

        # 安全检查
        if not str(file_path.resolve()).startswith(str(download_dir.resolve())):
            logger.warning(f"安全检查失败: {filename}")
            abort(403)

        if not file_path.exists():
            logger.warning(f"文件不存在: {filename}")
            abort(404)

        # 只允许视频文件流媒体播放
        if not _is_video_file(filename):
            logger.warning(f"非视频文件: {filename}")
            abort(400)

        logger.info(f"🎥 流媒体播放: {filename}")

        # 获取文件信息
        file_size = file_path.stat().st_size
        mimetype = _get_video_mimetype(filename)

        # 大视频检测
        is_large_video = file_size > 100 * 1024 * 1024  # 100MB以上为大视频
        logger.info(f"文件大小: {file_size} bytes ({file_size/(1024*1024):.1f}MB), MIME类型: {mimetype}, 大视频: {is_large_video}")

        # 检查是否为Range请求
        range_header = request.headers.get('Range')

        if range_header:
            # 处理Range请求（视频播放必需）
            logger.info(f"处理Range请求: {range_header}")
            return _handle_range_request(file_path, file_size, mimetype, range_header)
        else:
            # 普通请求
            logger.info("处理普通请求")
            response = Response(
                _generate_file_chunks(file_path),
                mimetype=mimetype,
                headers={
                    'Content-Length': str(file_size),
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'public, max-age=3600',  # 缓存1小时，提高大视频播放性能
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                    'Access-Control-Allow-Headers': 'Range, Content-Range, Content-Length',
                    'Connection': 'keep-alive',  # 保持连接，提高流媒体性能
                    'Transfer-Encoding': 'chunked'  # 分块传输
                }
            )
            return response

    except Exception as e:
        logger.error(f"❌ 流媒体播放失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        abort(500)


@files_bp.route('/stream/<filename>', methods=['OPTIONS'])
def stream_file_options(filename):
    """处理CORS预检请求"""
    from flask import Response

    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Range, Content-Range, Content-Length, Authorization'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


@files_bp.route('/list')
@auth_required
def list_files():
    """获取文件列表"""
    try:
        from core.config import get_config
        
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
        logger.error(f"获取文件列表失败: {e}")
        return jsonify({'error': '获取文件列表失败'}), 500


@files_bp.route('/delete/<filename>', methods=['DELETE'])
@auth_required
def delete_file(filename):
    """删除文件"""
    try:
        from core.config import get_config
        
        download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        file_path = download_dir / filename
        
        # 安全检查
        if not str(file_path.resolve()).startswith(str(download_dir.resolve())):
            abort(403)
        
        if not file_path.exists():
            abort(404)
        
        file_path.unlink()
        logger.info(f"删除文件: {filename}")
        
        return jsonify({'success': True, 'message': '文件删除成功'})
        
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        return jsonify({'error': '删除文件失败'}), 500


def _is_video_file(filename):
    """检查是否为视频文件"""
    video_extensions = {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
        '.webm', '.m4v', '.3gp', '.ogv', '.ts', '.m2ts'
    }
    return Path(filename).suffix.lower() in video_extensions


def _get_video_mimetype(filename):
    """获取视频文件的MIME类型"""
    ext = Path(filename).suffix.lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.ogv': 'video/ogg',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mkv': 'video/x-matroska',
        '.flv': 'video/x-flv',
        '.wmv': 'video/x-ms-wmv',
        '.m4v': 'video/mp4',
        '.3gp': 'video/3gpp',
        '.ts': 'video/mp2t',
        '.m2ts': 'video/mp2t'
    }
    return mime_types.get(ext, 'video/mp4')


def _handle_range_request(file_path, file_size, mimetype, range_header):
    """处理HTTP Range请求（视频播放必需）"""
    from flask import Response
    import re

    # 解析Range头
    range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if not range_match:
        abort(400)

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

    # 验证范围
    if start >= file_size or end >= file_size or start > end:
        abort(416)  # Range Not Satisfiable

    content_length = end - start + 1

    def generate_range_data():
        try:
            with open(file_path, 'rb') as f:
                f.seek(start)
                remaining = content_length
                while remaining:
                    # 动态chunk_size：大视频使用更大的块
                    if file_size > 500 * 1024 * 1024:  # 500MB+
                        chunk_size = min(2 * 1024 * 1024, remaining)  # 2MB chunks
                    elif file_size > 100 * 1024 * 1024:  # 100MB+
                        chunk_size = min(1024 * 1024, remaining)  # 1MB chunks
                    else:
                        chunk_size = min(512 * 1024, remaining)  # 512KB chunks

                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        except Exception as e:
            logger.error(f"Range数据生成失败: {e}")
            raise

    response = Response(
        generate_range_data(),
        206,  # Partial Content
        headers={
            'Content-Type': mimetype,
            'Content-Length': str(content_length),
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Range, Content-Length'
        }
    )

    return response


def _generate_file_chunks(file_path, chunk_size=None):
    """生成文件数据块 - 智能大视频优化，内存安全"""
    import gc
    import psutil
    import os

    file_size = file_path.stat().st_size

    # 根据文件大小动态调整chunk_size
    if chunk_size is None:
        if file_size > 500 * 1024 * 1024:  # 500MB+
            chunk_size = 2 * 1024 * 1024  # 2MB chunks
        elif file_size > 100 * 1024 * 1024:  # 100MB+
            chunk_size = 1024 * 1024  # 1MB chunks
        else:
            chunk_size = 512 * 1024  # 512KB chunks

    # 获取当前进程内存使用情况
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        logger.info(f"开始流媒体传输 - 文件: {file_size/(1024*1024):.1f}MB, Chunk: {chunk_size/1024:.0f}KB, 进程内存: {memory_mb:.1f}MB")
    except:
        logger.info(f"使用chunk_size: {chunk_size/1024:.0f}KB 用于 {file_size/(1024*1024):.1f}MB 文件")

    chunks_sent = 0
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                chunks_sent += 1

                # 每100个chunk检查一次内存（避免频繁检查影响性能）
                if chunks_sent % 100 == 0:
                    try:
                        current_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                        if current_memory > memory_mb + 100:  # 内存增长超过100MB时警告
                            logger.warning(f"内存使用增长: {current_memory:.1f}MB (+{current_memory-memory_mb:.1f}MB)")
                            gc.collect()  # 强制垃圾回收
                    except:
                        pass

                yield chunk

    except Exception as e:
        logger.error(f"文件流传输失败: {e}")
        raise
    finally:
        # 传输完成后的内存检查
        try:
            final_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            logger.info(f"流媒体传输完成 - 发送chunks: {chunks_sent}, 最终内存: {final_memory:.1f}MB")
        except:
            logger.info(f"流媒体传输完成 - 发送chunks: {chunks_sent}")

        # 强制垃圾回收
        gc.collect()


@files_bp.route('/debug/<filename>')
@auth_required
def debug_file(filename):
    """调试文件信息"""
    try:
        from core.config import get_config
        import mimetypes

        download_dir = Path(get_config('downloader.output_dir', '/app/downloads'))
        file_path = download_dir / filename

        if not file_path.exists():
            return jsonify({'error': '文件不存在'}), 404

        stat = file_path.stat()

        debug_info = {
            'filename': filename,
            'path': str(file_path),
            'exists': file_path.exists(),
            'size': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': stat.st_mtime,
            'is_video': _is_video_file(filename),
            'detected_mimetype': _get_video_mimetype(filename),
            'system_mimetype': mimetypes.guess_type(filename)[0],
            'extension': file_path.suffix.lower(),
            'stream_url': f'/files/stream/{filename}',
            'download_url': f'/files/download/{filename}',
            'permissions': oct(stat.st_mode)[-3:]
        }

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"文件调试失败: {e}")
        return jsonify({'error': str(e)}), 500
