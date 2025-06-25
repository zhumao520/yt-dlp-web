#!/usr/bin/env python3
"""
Server-Sent Events (SSE) 实现
用于实时推送下载进度和状态更新
"""

import json
import logging
import threading
import time
from typing import Dict, Any, Set
from flask import Response
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class SSEManager:
    """SSE连接管理器"""
    
    def __init__(self):
        self._clients: Dict[str, Queue] = {}  # client_id -> message_queue
        self._lock = threading.Lock()
        
    def add_client(self, client_id: str) -> Queue:
        """添加客户端连接"""
        with self._lock:
            if client_id in self._clients:
                # 如果客户端已存在，清空旧队列
                try:
                    while not self._clients[client_id].empty():
                        self._clients[client_id].get_nowait()
                except Empty:
                    pass
            else:
                self._clients[client_id] = Queue(maxsize=100)  # 限制队列大小
            
            logger.info(f"📡 SSE客户端连接: {client_id}")
            return self._clients[client_id]
    
    def remove_client(self, client_id: str):
        """移除客户端连接"""
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"📡 SSE客户端断开: {client_id}")
    
    def broadcast(self, event_type: str, data: Any):
        """广播消息给所有客户端"""
        message = self._format_sse_message(event_type, data)
        
        with self._lock:
            disconnected_clients = []
            
            for client_id, queue in self._clients.items():
                try:
                    if queue.full():
                        # 队列满了，移除最老的消息
                        try:
                            queue.get_nowait()
                        except Empty:
                            pass
                    
                    queue.put_nowait(message)
                    
                except Exception as e:
                    logger.debug(f"⚠️ 向客户端 {client_id} 发送消息失败: {e}")
                    disconnected_clients.append(client_id)
            
            # 清理断开的客户端
            for client_id in disconnected_clients:
                if client_id in self._clients:
                    del self._clients[client_id]
        
        if self._clients:
            logger.debug(f"📡 SSE广播: {event_type} -> {len(self._clients)} 个客户端")
    
    def send_to_client(self, client_id: str, event_type: str, data: Any):
        """发送消息给特定客户端"""
        message = self._format_sse_message(event_type, data)
        
        with self._lock:
            if client_id in self._clients:
                try:
                    queue = self._clients[client_id]
                    if queue.full():
                        # 队列满了，移除最老的消息
                        try:
                            queue.get_nowait()
                        except Empty:
                            pass
                    
                    queue.put_nowait(message)
                    logger.debug(f"📡 SSE发送: {event_type} -> {client_id}")
                    
                except Exception as e:
                    logger.debug(f"⚠️ 向客户端 {client_id} 发送消息失败: {e}")
                    del self._clients[client_id]
    
    def _format_sse_message(self, event_type: str, data: Any) -> str:
        """格式化SSE消息"""
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {json_data}\n\n"
        except Exception as e:
            logger.error(f"❌ SSE消息格式化失败: {e}")
            return f"event: error\ndata: {{\"error\": \"消息格式化失败\"}}\n\n"
    
    def get_client_count(self) -> int:
        """获取连接的客户端数量"""
        with self._lock:
            return len(self._clients)


# 全局SSE管理器实例
_sse_manager = None
_sse_lock = threading.Lock()


def get_sse_manager() -> SSEManager:
    """获取SSE管理器实例（单例）"""
    global _sse_manager
    
    if _sse_manager is None:
        with _sse_lock:
            if _sse_manager is None:
                _sse_manager = SSEManager()
                logger.info("✅ SSE管理器初始化完成")
    
    return _sse_manager


def create_sse_response(client_id: str) -> Response:
    """创建SSE响应流"""
    sse_manager = get_sse_manager()
    message_queue = sse_manager.add_client(client_id)
    
    def event_stream():
        """事件流生成器"""
        try:
            # 发送连接确认消息
            yield f"event: connected\ndata: {{\"client_id\": \"{client_id}\", \"timestamp\": {int(time.time())}}}\n\n"
            
            # 发送心跳和处理消息
            last_heartbeat = time.time()
            
            while True:
                try:
                    # 检查是否需要发送心跳
                    current_time = time.time()
                    if current_time - last_heartbeat > 30:  # 30秒心跳
                        yield f"event: heartbeat\ndata: {{\"timestamp\": {int(current_time)}}}\n\n"
                        last_heartbeat = current_time
                    
                    # 获取消息（非阻塞，超时1秒）
                    try:
                        message = message_queue.get(timeout=1.0)
                        yield message
                    except Empty:
                        continue  # 超时继续循环
                        
                except Exception as e:
                    logger.error(f"❌ SSE事件流异常: {e}")
                    break
                    
        except GeneratorExit:
            # 客户端断开连接
            logger.debug(f"📡 SSE客户端断开: {client_id}")
        finally:
            # 清理客户端
            sse_manager.remove_client(client_id)
    
    # 创建SSE响应
    response = Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control',
            'X-Accel-Buffering': 'no',  # 禁用Nginx缓冲
        }
    )
    
    return response


def setup_sse_events():
    """设置SSE事件监听器"""
    try:
        from .events import on, Events
        sse_manager = get_sse_manager()
        
        @on(Events.DOWNLOAD_PROGRESS)
        def handle_download_progress(data):
            """处理下载进度事件"""
            if data:
                sse_manager.broadcast('download_progress', {
                    'download_id': data.get('download_id'),
                    'status': data.get('status'),
                    'progress': data.get('progress', 0),
                    'timestamp': int(time.time())
                })
        
        @on(Events.DOWNLOAD_COMPLETED)
        def handle_download_completed(data):
            """处理下载完成事件"""
            if data:
                sse_manager.broadcast('download_completed', {
                    'download_id': data.get('download_id'),
                    'title': data.get('title'),
                    'file_path': data.get('file_path'),
                    'file_size': data.get('file_size'),
                    'timestamp': int(time.time())
                })

                # 检查是否还有活跃下载，如果没有则建议客户端关闭连接
                try:
                    from modules.downloader.manager import get_download_manager
                    download_manager = get_download_manager()
                    active_downloads = download_manager.get_active_downloads()

                    if len(active_downloads) == 0:
                        logger.info("📡 所有下载已完成，建议客户端关闭SSE连接")
                        # 发送特殊事件建议客户端关闭连接
                        sse_manager.broadcast('all_downloads_completed', {
                            'message': '所有下载已完成',
                            'timestamp': int(time.time())
                        })
                except Exception as e:
                    logger.debug(f"检查活跃下载失败: {e}")
        
        @on(Events.DOWNLOAD_FAILED)
        def handle_download_failed(data):
            """处理下载失败事件"""
            if data:
                sse_manager.broadcast('download_failed', {
                    'download_id': data.get('download_id'),
                    'error': data.get('error'),
                    'timestamp': int(time.time())
                })
        
        @on(Events.DOWNLOAD_STARTED)
        def handle_download_started(data):
            """处理下载开始事件"""
            if data:
                sse_manager.broadcast('download_started', {
                    'download_id': data.get('download_id'),
                    'url': data.get('url'),
                    'title': data.get('title'),
                    'timestamp': int(time.time())
                })
        
        logger.info("✅ SSE事件监听器设置完成")
        
    except Exception as e:
        logger.error(f"❌ 设置SSE事件监听器失败: {e}")


# 在模块导入时自动设置事件监听器
try:
    setup_sse_events()
except Exception as e:
    logger.warning(f"⚠️ SSE事件监听器设置延迟: {e}")
