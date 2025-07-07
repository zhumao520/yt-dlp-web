#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram异步任务模块 - 基于SQLite的轻量级异步上传

使用SQLite数据库实现异步任务队列，无需外部依赖
"""

import os
import sys
import time
import json
import uuid
import sqlite3
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 添加项目根目录到Python路径
current_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(current_dir))

logger = logging.getLogger(__name__)


class SQLiteTaskQueue:
    """基于SQLite的轻量级任务队列"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 使用项目数据库路径
            self.db_path = "data/app.db"
        else:
            self.db_path = db_path
        
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._init_tables()
        self._running = False
        self._worker_thread = None
    
    def _init_tables(self):
        """初始化任务表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS upload_tasks (
                        id TEXT PRIMARY KEY,
                        task_type TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        file_path TEXT,
                        file_paths TEXT,  -- JSON格式存储多文件路径
                        caption TEXT,
                        config TEXT,  -- JSON格式存储配置
                        progress INTEGER DEFAULT 0,
                        current_file TEXT,
                        completed_files INTEGER DEFAULT 0,
                        total_files INTEGER DEFAULT 1,
                        result TEXT,  -- JSON格式存储结果
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                conn.execute('CREATE INDEX IF NOT EXISTS idx_upload_tasks_status ON upload_tasks(status)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_upload_tasks_created ON upload_tasks(created_at)')
                
                logger.info("✅ SQLite任务队列表初始化成功")
                
        except Exception as e:
            logger.error(f"❌ 初始化任务队列表失败: {e}")
            raise
    
    def submit_task(self, task_type: str, **kwargs) -> str:
        """提交任务到队列"""
        task_id = str(uuid.uuid4())
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 处理不同类型的任务参数
                file_path = kwargs.get('file_path')
                file_paths = kwargs.get('file_paths')
                caption = kwargs.get('caption', '')
                config = kwargs.get('config', {})
                
                # 计算总文件数
                if file_paths:
                    total_files = len(file_paths)
                    file_paths_json = json.dumps(file_paths)
                else:
                    total_files = 1
                    file_paths_json = None
                
                conn.execute('''
                    INSERT INTO upload_tasks 
                    (id, task_type, file_path, file_paths, caption, config, total_files)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_id, task_type, file_path, file_paths_json, 
                    caption, json.dumps(config), total_files
                ))
                
                logger.info(f"✅ 任务已提交到队列: {task_id} ({task_type})")
                
                # 启动工作线程（如果还没启动）
                self._ensure_worker_running()
                
                return task_id
                
        except Exception as e:
            logger.error(f"❌ 提交任务失败: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM upload_tasks WHERE id = ?
                ''', (task_id,))
                
                row = cursor.fetchone()
                if not row:
                    return {'status': 'not_found', 'error': '任务不存在'}
                
                # 构建状态响应
                status_data = {
                    'status': row['status'],
                    'progress': row['progress'],
                    'current_file': row['current_file'],
                    'completed_files': row['completed_files'],
                    'total_files': row['total_files'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                # 添加结果或错误信息
                if row['status'] == 'completed' and row['result']:
                    status_data['result'] = json.loads(row['result'])
                elif row['status'] == 'failed' and row['error_message']:
                    status_data['error'] = row['error_message']
                
                return status_data
                
        except Exception as e:
            logger.error(f"❌ 获取任务状态失败: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def update_task_progress(self, task_id: str, progress: int, current_file: str = None, completed_files: int = None):
        """更新任务进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                update_fields = ['progress = ?', 'updated_at = CURRENT_TIMESTAMP']
                params = [progress]
                
                if current_file:
                    update_fields.append('current_file = ?')
                    params.append(current_file)
                
                if completed_files is not None:
                    update_fields.append('completed_files = ?')
                    params.append(completed_files)
                
                params.append(task_id)
                
                conn.execute(f'''
                    UPDATE upload_tasks 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', params)
                
        except Exception as e:
            logger.error(f"❌ 更新任务进度失败: {e}")
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """标记任务完成"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE upload_tasks 
                    SET status = 'completed', result = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (json.dumps(result), task_id))
                
                logger.info(f"✅ 任务完成: {task_id}")
                
        except Exception as e:
            logger.error(f"❌ 标记任务完成失败: {e}")
    
    def fail_task(self, task_id: str, error_message: str):
        """标记任务失败"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    UPDATE upload_tasks 
                    SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (error_message, task_id))
                
                logger.error(f"❌ 任务失败: {task_id} - {error_message}")
                
        except Exception as e:
            logger.error(f"❌ 标记任务失败失败: {e}")
    
    def _ensure_worker_running(self):
        """确保工作线程正在运行"""
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker_thread.start()
            logger.info("🚀 SQLite任务队列工作线程已启动")
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self._running:
            try:
                # 获取待处理任务
                pending_tasks = self._get_pending_tasks()
                
                if not pending_tasks:
                    time.sleep(1)  # 没有任务时休眠1秒
                    continue
                
                # 处理任务（使用线程池）
                for task in pending_tasks:
                    self.executor.submit(self._process_task, task)
                
                time.sleep(0.5)  # 短暂休眠避免过度轮询
                
            except Exception as e:
                logger.error(f"❌ 工作线程错误: {e}")
                time.sleep(5)  # 出错时休眠5秒
    
    def _get_pending_tasks(self, limit: int = 4) -> List[Dict]:
        """获取待处理任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM upload_tasks 
                    WHERE status = 'pending' 
                    ORDER BY created_at ASC 
                    LIMIT ?
                ''', (limit,))
                
                tasks = []
                for row in cursor.fetchall():
                    # 标记为处理中
                    conn.execute('''
                        UPDATE upload_tasks 
                        SET status = 'processing', updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (row['id'],))
                    
                    tasks.append(dict(row))
                
                return tasks
                
        except Exception as e:
            logger.error(f"❌ 获取待处理任务失败: {e}")
            return []

    def _process_task(self, task: Dict):
        """处理单个任务"""
        task_id = task['id']
        task_type = task['task_type']

        try:
            logger.info(f"🚀 开始处理任务: {task_id} ({task_type})")

            if task_type == 'upload_file':
                self._process_upload_file(task)
            elif task_type == 'batch_upload':
                self._process_batch_upload(task)
            elif task_type == 'send_message':
                self._process_send_message(task)
            else:
                raise ValueError(f"未知任务类型: {task_type}")

        except Exception as e:
            logger.error(f"❌ 处理任务失败: {task_id} - {e}")
            self.fail_task(task_id, str(e))

    def _process_upload_file(self, task: Dict):
        """处理单文件上传任务"""
        task_id = task['id']
        file_path = task['file_path']
        caption = task['caption'] or ''
        config = json.loads(task['config']) if task['config'] else {}

        try:
            # 检查文件是否存在
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")

            # 更新进度
            self.update_task_progress(task_id, 10, file_path)

            # 创建上传器
            from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader

            if not config:
                from modules.telegram.services.config_service import get_telegram_config_service
                config_service = get_telegram_config_service()
                config = config_service.get_config()

            uploader = ModernHybridUploader(config)

            if not uploader.is_available():
                raise RuntimeError("没有可用的Telegram上传器")

            # 更新进度
            self.update_task_progress(task_id, 20)

            # 执行上传
            result = uploader.send_file(file_path, caption)

            if result:
                file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
                self.complete_task(task_id, {
                    'status': 'success',
                    'file_path': file_path,
                    'file_size_mb': round(file_size_mb, 2),
                    'upload_time': time.time()
                })
                logger.info(f"✅ 文件上传成功: {file_path}")
            else:
                raise RuntimeError("上传失败")

        except Exception as e:
            self.fail_task(task_id, str(e))
            raise

    def _process_batch_upload(self, task: Dict):
        """处理批量上传任务"""
        task_id = task['id']
        file_paths = json.loads(task['file_paths']) if task['file_paths'] else []
        caption = task['caption'] or ''
        config = json.loads(task['config']) if task['config'] else {}

        try:
            # 验证文件
            valid_files = []
            invalid_files = []

            for file_path in file_paths:
                if Path(file_path).exists():
                    valid_files.append(file_path)
                else:
                    invalid_files.append(file_path)

            if not valid_files:
                raise FileNotFoundError("没有有效的文件可以上传")

            # 更新进度
            self.update_task_progress(task_id, 10, completed_files=0)

            # 创建上传器
            from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader

            if not config:
                from modules.telegram.services.config_service import get_telegram_config_service
                config_service = get_telegram_config_service()
                config = config_service.get_config()

            uploader = ModernHybridUploader(config)

            if not uploader.is_available():
                raise RuntimeError("没有可用的Telegram上传器")

            # 批量上传
            successful_uploads = []
            failed_uploads = []

            for i, file_path in enumerate(valid_files):
                try:
                    # 更新进度
                    progress = 10 + (i / len(valid_files)) * 80
                    self.update_task_progress(task_id, int(progress), file_path, i)

                    logger.info(f"📤 上传文件 {i+1}/{len(valid_files)}: {file_path}")

                    result = uploader.send_file(file_path, caption)

                    if result:
                        successful_uploads.append(file_path)
                    else:
                        failed_uploads.append(file_path)

                except Exception as e:
                    logger.error(f"❌ 文件上传异常: {file_path} - {e}")
                    failed_uploads.append(file_path)

            # 完成任务
            success_rate = len(successful_uploads) / len(valid_files) * 100 if valid_files else 0

            self.complete_task(task_id, {
                'status': 'completed',
                'total_files': len(file_paths),
                'valid_files': len(valid_files),
                'invalid_files': len(invalid_files),
                'successful_uploads': len(successful_uploads),
                'failed_uploads': len(failed_uploads),
                'success_rate': round(success_rate, 2),
                'successful_files': successful_uploads,
                'failed_files': failed_uploads,
                'invalid_files': invalid_files
            })

            logger.info(f"✅ 批量上传完成: {len(successful_uploads)}/{len(valid_files)} 成功")

        except Exception as e:
            self.fail_task(task_id, str(e))
            raise

    def _process_send_message(self, task: Dict):
        """处理消息发送任务"""
        task_id = task['id']
        message = task['caption']  # 复用caption字段存储消息内容
        config = json.loads(task['config']) if task['config'] else {}

        try:
            # 创建上传器
            from modules.telegram.uploaders.modern_hybrid import ModernHybridUploader

            if not config:
                from modules.telegram.services.config_service import get_telegram_config_service
                config_service = get_telegram_config_service()
                config = config_service.get_config()

            uploader = ModernHybridUploader(config)

            if not uploader.is_available():
                raise RuntimeError("没有可用的Telegram上传器")

            # 发送消息
            result = uploader.send_message(message)

            if result:
                self.complete_task(task_id, {
                    'status': 'success',
                    'message_length': len(message)
                })
                logger.info(f"✅ 消息发送成功")
            else:
                raise RuntimeError("消息发送失败")

        except Exception as e:
            self.fail_task(task_id, str(e))
            raise

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT status, COUNT(*) as count
                    FROM upload_tasks
                    GROUP BY status
                ''')

                status_counts = {}
                for row in cursor.fetchall():
                    status_counts[row[0]] = row[1]

                return {
                    'pending': status_counts.get('pending', 0),
                    'processing': status_counts.get('processing', 0),
                    'completed': status_counts.get('completed', 0),
                    'failed': status_counts.get('failed', 0),
                    'total': sum(status_counts.values())
                }

        except Exception as e:
            logger.error(f"❌ 获取队列状态失败: {e}")
            return {'error': str(e)}

    def cleanup_completed_tasks(self, days: int = 7) -> int:
        """清理已完成的任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    DELETE FROM upload_tasks
                    WHERE status IN ('completed', 'failed')
                    AND created_at < datetime('now', '-{} days')
                '''.format(days))

                cleaned_count = cursor.rowcount
                logger.info(f"🧹 清理了 {cleaned_count} 个过期任务")
                return cleaned_count

        except Exception as e:
            logger.error(f"❌ 清理任务失败: {e}")
            return 0

    def stop(self):
        """停止工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        logger.info("🛑 SQLite任务队列已停止")


# 全局任务队列实例
_task_queue = None

def get_task_queue() -> SQLiteTaskQueue:
    """获取全局任务队列实例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = SQLiteTaskQueue()
    return _task_queue


class TelegramTaskManager:
    """Telegram任务管理器 - 基于SQLite的轻量级实现"""

    def __init__(self):
        self.task_queue = get_task_queue()

    def is_async_available(self) -> bool:
        """检查异步功能是否可用"""
        return True  # SQLite队列总是可用

    def submit_upload_task(self, file_path: str, caption: str = None, config: Dict[str, Any] = None, **kwargs) -> Optional[str]:
        """提交上传任务"""
        try:
            task_id = self.task_queue.submit_task(
                'upload_file',
                file_path=file_path,
                caption=caption,
                config=config or {}
            )

            if task_id:
                logger.info(f"✅ 上传任务已提交: {task_id}")
                return task_id
            else:
                logger.error("❌ 提交上传任务失败")
                return None

        except Exception as e:
            logger.error(f"❌ 提交上传任务失败: {e}")
            return None

    def submit_batch_upload_task(self, file_paths: list, caption: str = None, config: Dict[str, Any] = None, **kwargs) -> Optional[str]:
        """提交批量上传任务"""
        try:
            task_id = self.task_queue.submit_task(
                'batch_upload',
                file_paths=file_paths,
                caption=caption,
                config=config or {}
            )

            if task_id:
                logger.info(f"✅ 批量上传任务已提交: {task_id} ({len(file_paths)} 个文件)")
                return task_id
            else:
                logger.error("❌ 提交批量上传任务失败")
                return None

        except Exception as e:
            logger.error(f"❌ 提交批量上传任务失败: {e}")
            return None

    def submit_message_task(self, message: str, config: Dict[str, Any] = None, **kwargs) -> Optional[str]:
        """提交消息任务"""
        try:
            task_id = self.task_queue.submit_task(
                'send_message',
                caption=message,  # 复用caption字段
                config=config or {}
            )

            if task_id:
                logger.info(f"✅ 消息任务已提交: {task_id}")
                return task_id
            else:
                logger.error("❌ 提交消息任务失败")
                return None

        except Exception as e:
            logger.error(f"❌ 提交消息任务失败: {e}")
            return None

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        return self.task_queue.get_task_status(task_id)

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return self.task_queue.get_queue_status()

    def cleanup_completed_tasks(self) -> int:
        """清理已完成的任务"""
        return self.task_queue.cleanup_completed_tasks()

    def get_all_tasks(self) -> Dict[str, Any]:
        """获取所有任务（最近的100个）"""
        try:
            with sqlite3.connect(self.task_queue.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT id, task_type, status, progress, created_at, updated_at
                    FROM upload_tasks
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                tasks = {}
                for row in cursor.fetchall():
                    tasks[row['id']] = {
                        'type': row['task_type'],
                        'status': row['status'],
                        'progress': row['progress'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }

                return tasks

        except Exception as e:
            logger.error(f"❌ 获取任务列表失败: {e}")
            return {}

    def cancel_task(self, task_id: str) -> bool:
        """取消任务（标记为失败）"""
        try:
            self.task_queue.fail_task(task_id, "用户取消")
            logger.info(f"✅ 任务已取消: {task_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 取消任务失败: {e}")
            return False


# 全局任务管理器实例
_task_manager = None

def get_task_manager() -> TelegramTaskManager:
    """获取任务管理器实例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TelegramTaskManager()
    return _task_manager


# 兼容性函数（保持API一致性）
def upload_file_async(*args, **kwargs):
    """兼容性函数 - 异步上传文件"""
    task_manager = get_task_manager()
    return task_manager.submit_upload_task(*args, **kwargs)

def send_message_async(*args, **kwargs):
    """兼容性函数 - 异步发送消息"""
    task_manager = get_task_manager()
    return task_manager.submit_message_task(*args, **kwargs)

def batch_upload_async(*args, **kwargs):
    """兼容性函数 - 批量异步上传"""
    task_manager = get_task_manager()
    return task_manager.submit_batch_upload_task(*args, **kwargs)


if __name__ == "__main__":
    # 测试SQLite任务队列
    print("🧪 测试SQLite任务队列")

    task_queue = SQLiteTaskQueue()

    # 提交测试任务
    task_id = task_queue.submit_task('send_message', caption='测试消息')
    print(f"任务ID: {task_id}")

    # 查询状态
    status = task_queue.get_task_status(task_id)
    print(f"任务状态: {status}")

    # 等待处理
    time.sleep(2)

    # 再次查询状态
    status = task_queue.get_task_status(task_id)
    print(f"最终状态: {status}")

    # 停止队列
    task_queue.stop()
