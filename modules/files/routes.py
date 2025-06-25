# -*- coding: utf-8 -*-
"""
文件管理路由 - 文件下载和管理
"""

import os
import logging
from pathlib import Path
from urllib.parse import quote
from flask import Blueprint, send_file, jsonify, abort
from core.auth import auth_required

logger = logging.getLogger(__name__)

files_bp = Blueprint('files', __name__)


def _is_safe_path(file_path: Path, base_dir: Path) -> bool:
    """基本路径检查，仅防止路径遍历攻击（私人项目简化版）"""
    try:
        # 解析绝对路径
        file_abs = file_path.resolve()
        base_abs = base_dir.resolve()

        # 基本的路径前缀检查（防止访问下载目录外的文件）
        if not str(file_abs).startswith(str(base_abs)):
            return False

        # 确保文件名不为空
        if not file_path.name:
            return False

        return True

    except Exception as e:
        logger.error(f"❌ 路径检查异常: {e}")
        return False


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

        # 增强的安全检查：防止路径遍历攻击
        if not _is_safe_path(file_path, download_dir):
            logger.warning(f"⚠️ 路径安全检查失败: {filename}")
            abort(403)

        # 检查文件是否存在
        if not file_path.exists():
            # 检查是否为播放器自动请求的附加文件
            if _is_auxiliary_file(filename):
                logger.debug(f"播放器附加文件不存在（正常）: {filename}")
                abort(404)  # 下载路由仍然返回404
            else:
                logger.warning(f"文件不存在: {filename}")
                abort(404)

        # 检查是否为在线播放请求
        is_streaming = request.args.get('stream') == '1'

        if is_streaming and _is_video_file(filename):
            # 流媒体播放
            logger.info(f"流媒体播放: {filename}")
            return send_file(file_path, as_attachment=False, mimetype=_get_video_mimetype(filename))
        else:
            # 普通下载 - 使用自定义响应避免send_file的文件名问题
            logger.info(f"下载文件: {filename}")

            # 获取文件信息
            file_size = file_path.stat().st_size
            mimetype = _get_media_mimetype(filename)

            # 安全的文件名处理
            safe_filename = filename.encode('utf-8').decode('utf-8')

            from flask import Response
            response = Response(
                _generate_file_chunks(file_path),
                mimetype=mimetype,
                headers={
                    'Content-Length': str(file_size),
                    'Content-Disposition': f'attachment; filename*=UTF-8\'\'{quote(safe_filename)}',
                    'Cache-Control': 'no-cache',
                    'Access-Control-Allow-Origin': '*'
                }
            )
            return response

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

        # 增强的安全检查
        if not _is_safe_path(file_path, download_dir):
            logger.warning(f"⚠️ 流媒体路径安全检查失败: {filename}")
            abort(403)

        if not file_path.exists():
            # 检查是否为播放器自动请求的附加文件（歌词、描述等）
            if _is_auxiliary_file(filename):
                logger.debug(f"播放器附加文件不存在（正常）: {filename}")
                # 返回204 No Content而不是404，避免播放器报错
                from flask import Response
                return Response(status=204)
            else:
                logger.warning(f"文件不存在: {filename}")
                abort(404)

        # 检查是否为支持的文件类型（媒体文件或歌词文件）
        if not (_is_video_file(filename) or _is_audio_file(filename) or _is_lyrics_file(filename)):
            logger.warning(f"不支持的文件类型: {filename}")
            abort(400)

        # 确定文件类型
        if _is_video_file(filename):
            file_type = "视频"
            icon = "🎥"
        elif _is_audio_file(filename):
            file_type = "音频"
            icon = "🎵"
        else:  # 歌词文件
            file_type = "歌词"
            icon = "📝"

        logger.info(f"{icon} 流媒体播放 ({file_type}): {filename}")

        # 获取文件信息
        file_size = file_path.stat().st_size
        mimetype = _get_media_mimetype(filename)

        # 大文件检测
        is_large_file = file_size > 100 * 1024 * 1024  # 100MB以上为大文件
        logger.info(f"文件大小: {file_size} bytes ({file_size/(1024*1024):.1f}MB), MIME类型: {mimetype}, 大文件: {is_large_file}")

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
        
        # 增强的安全检查
        if not _is_safe_path(file_path, download_dir):
            logger.warning(f"⚠️ 删除文件路径安全检查失败: {filename}")
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


def _is_audio_file(filename):
    """检查是否为音频文件"""
    audio_extensions = {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma',
        '.m4a', '.opus', '.aiff', '.ape', '.ac3', '.dts'
    }
    return Path(filename).suffix.lower() in audio_extensions


def _is_lyrics_file(filename):
    """检查是否为歌词文件"""
    lyrics_extensions = {'.lrc', '.txt'}
    return Path(filename).suffix.lower() in lyrics_extensions


def _is_auxiliary_file(filename):
    """检查是否为播放器自动请求的附加文件"""
    filename_lower = filename.lower()

    # 检查是否为临时文件
    if '.temp.' in filename_lower:
        return True

    # 常见的附加文件模式
    auxiliary_patterns = [
        '.txt',      # 歌词/描述文件
        '.lrc',      # LRC歌词文件
        '.srt',      # 字幕文件
        '.vtt',      # WebVTT字幕文件
        '.ass',      # ASS字幕文件
        '.ssa',      # SSA字幕文件
    ]

    # 检查是否为附加文件
    for pattern in auxiliary_patterns:
        if filename_lower.endswith(pattern):
            # 进一步检查是否为媒体文件的附加文件
            base_name = filename_lower.replace(pattern, '')

            # 检查是否存在对应的媒体文件
            media_extensions = [
                '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
                '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.opus'
            ]

            for media_ext in media_extensions:
                if (base_name + media_ext) != filename_lower:  # 不是自己
                    # 这可能是某个媒体文件的附加文件
                    return True

    return False


def _get_media_mimetype(filename):
    """获取媒体文件的MIME类型（视频、音频或歌词）"""
    ext = Path(filename).suffix.lower()

    # 视频MIME类型
    video_mime_types = {
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

    # 音频MIME类型
    audio_mime_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.aac': 'audio/aac',
        '.ogg': 'audio/ogg',
        '.wma': 'audio/x-ms-wma',
        '.m4a': 'audio/mp4',
        '.opus': 'audio/opus',
        '.aiff': 'audio/aiff',
        '.ape': 'audio/x-ape',
        '.ac3': 'audio/ac3',
        '.dts': 'audio/dts'
    }

    # 歌词文件MIME类型
    lyrics_mime_types = {
        '.lrc': 'text/plain; charset=utf-8',
        '.txt': 'text/plain; charset=utf-8'
    }

    # 按优先级检查文件类型
    if ext in video_mime_types:
        return video_mime_types[ext]
    elif ext in audio_mime_types:
        return audio_mime_types[ext]
    elif ext in lyrics_mime_types:
        return lyrics_mime_types[ext]
    else:
        # 默认返回通用类型
        return 'application/octet-stream'


def _get_video_mimetype(filename):
    """获取视频文件的MIME类型（保持向后兼容）"""
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
            'is_audio': _is_audio_file(filename),
            'is_lyrics': _is_lyrics_file(filename),
            'detected_mimetype': _get_media_mimetype(filename),
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
