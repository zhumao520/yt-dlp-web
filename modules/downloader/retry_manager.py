# -*- coding: utf-8 -*-
"""
智能重试管理器

提供智能的错误分析和重试策略
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryManager:
    """智能重试管理器"""
    
    def __init__(self):
        self.retry_data: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        
        # 错误分析模式
        self.error_patterns = {
            'permanent_errors': [
                'private', 'not available', 'removed', 'copyright',
                'age restricted', 'geo blocked', 'invalid url',
                'unsupported url', 'no video formats', 'video unavailable',
                'this video is not available', 'account has been terminated',
                'account suspended'
            ],
            'account_errors': [
                'sign in to confirm', 'confirm you\'re not a bot',
                'unusual traffic', 'authentication required'
            ],
            'retryable_errors': [
                'timeout', 'connection', 'network', 'temporary',
                'rate limit', 'server error', 'http error 5',
                'http error 429', 'http error 503', 'http error 502',
                'http error 504'
            ]
        }
        
        # 重试配置
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 2,
            'max_delay': 60,
            'exponential_base': 2
        }
    
    def should_retry(self, download_id: str, error_msg: str) -> bool:
        """判断是否应该重试"""
        try:
            with self.lock:
                # 获取或创建重试数据
                if download_id not in self.retry_data:
                    self.retry_data[download_id] = {
                        'retry_count': 0,
                        'first_error': error_msg,
                        'last_error': error_msg,
                        'error_history': [],
                        'created_at': datetime.now()
                    }
                
                retry_info = self.retry_data[download_id]
                retry_count = retry_info['retry_count']
                
                # 检查是否达到最大重试次数
                if retry_count >= self.retry_config['max_retries']:
                    logger.info(f"🚫 已达到最大重试次数: {download_id}")
                    return False
                
                # 分析错误类型
                error_type = self._analyze_error_type(error_msg)
                
                # 更新错误历史
                retry_info['error_history'].append({
                    'error': error_msg,
                    'type': error_type,
                    'timestamp': datetime.now(),
                    'retry_count': retry_count
                })
                retry_info['last_error'] = error_msg
                
                # 根据错误类型决定是否重试
                should_retry = self._should_retry_by_error_type(error_type, error_msg)
                
                if should_retry:
                    retry_info['retry_count'] += 1
                    logger.info(f"🔄 允许重试 ({retry_count + 1}/{self.retry_config['max_retries']}): {download_id}")
                    logger.info(f"🔄 错误类型: {error_type}")
                else:
                    logger.info(f"🚫 不允许重试，错误类型: {error_type}")
                
                return should_retry
                
        except Exception as e:
            logger.error(f"❌ 重试判断失败: {e}")
            return False
    
    def _analyze_error_type(self, error_msg: str) -> str:
        """分析错误类型"""
        error_lower = error_msg.lower()
        
        # 检查永久性错误
        for pattern in self.error_patterns['permanent_errors']:
            if pattern in error_lower:
                return 'permanent'
        
        # 检查账号相关错误
        for pattern in self.error_patterns['account_errors']:
            if pattern in error_lower:
                return 'account'
        
        # 检查可重试错误
        for pattern in self.error_patterns['retryable_errors']:
            if pattern in error_lower:
                return 'retryable'
        
        # 默认为未知错误（允许重试）
        return 'unknown'
    
    def _should_retry_by_error_type(self, error_type: str, error_msg: str) -> bool:
        """根据错误类型决定是否重试"""
        if error_type == 'permanent':
            return False
        
        if error_type == 'account':
            logger.warning(f"🚫 检测到账号问题: {error_msg}")
            logger.warning(f"💡 建议: 1) 清理现有cookies 2) 重新导出有效账号的cookies 3) 或使用无cookies模式")
            return False
        
        if error_type in ['retryable', 'unknown']:
            return True
        
        return False
    
    def calculate_retry_delay(self, download_id: str) -> int:
        """计算重试延迟（指数退避）"""
        try:
            with self.lock:
                retry_info = self.retry_data.get(download_id, {})
                retry_count = retry_info.get('retry_count', 0)
                
                # 指数退避算法
                delay = min(
                    self.retry_config['base_delay'] ** retry_count,
                    self.retry_config['max_delay']
                )
                
                return max(1, int(delay))  # 至少1秒
                
        except Exception as e:
            logger.error(f"❌ 计算重试延迟失败: {e}")
            return self.retry_config['base_delay']
    
    def schedule_retry(self, download_id: str, retry_func: Callable[[str], None]):
        """安排重试任务"""
        try:
            delay = self.calculate_retry_delay(download_id)
            
            logger.info(f"⏱️ 安排重试任务: {download_id}, 延迟 {delay} 秒")
            
            def delayed_retry():
                try:
                    time.sleep(delay)
                    
                    # 检查任务是否仍然需要重试
                    with self.lock:
                        if download_id in self.retry_data:
                            retry_func(download_id)
                        else:
                            logger.debug(f"🔍 重试任务已取消: {download_id}")
                            
                except Exception as e:
                    logger.error(f"❌ 延迟重试执行失败: {e}")
            
            # 在新线程中执行延迟重试
            retry_thread = threading.Thread(target=delayed_retry, daemon=True)
            retry_thread.start()
            
        except Exception as e:
            logger.error(f"❌ 安排重试任务失败: {e}")
    
    def get_retry_info(self, download_id: str) -> Optional[Dict[str, Any]]:
        """获取重试信息"""
        with self.lock:
            return self.retry_data.get(download_id)
    
    def clear_retry_data(self, download_id: str):
        """清理重试数据"""
        with self.lock:
            if download_id in self.retry_data:
                del self.retry_data[download_id]
                logger.debug(f"🧹 清理重试数据: {download_id}")
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        with self.lock:
            total_tasks = len(self.retry_data)
            
            if total_tasks == 0:
                return {
                    'total_tasks': 0,
                    'avg_retries': 0,
                    'error_types': {},
                    'success_rate': 0
                }
            
            total_retries = sum(data['retry_count'] for data in self.retry_data.values())
            avg_retries = total_retries / total_tasks
            
            # 统计错误类型
            error_types = {}
            for data in self.retry_data.values():
                for error_record in data.get('error_history', []):
                    error_type = error_record.get('type', 'unknown')
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return {
                'total_tasks': total_tasks,
                'total_retries': total_retries,
                'avg_retries': round(avg_retries, 2),
                'error_types': error_types,
                'max_retries_config': self.retry_config['max_retries']
            }
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """清理过期的重试数据"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            with self.lock:
                expired_ids = [
                    download_id for download_id, data in self.retry_data.items()
                    if data.get('created_at', datetime.now()) < cutoff_time
                ]
                
                for download_id in expired_ids:
                    del self.retry_data[download_id]
                
                if expired_ids:
                    logger.info(f"🧹 清理过期重试数据: {len(expired_ids)} 个任务")
                    
        except Exception as e:
            logger.error(f"❌ 清理过期数据失败: {e}")
    
    def update_config(self, config: Dict[str, Any]):
        """更新重试配置"""
        try:
            for key, value in config.items():
                if key in self.retry_config:
                    self.retry_config[key] = value
                    logger.info(f"🔧 更新重试配置: {key} = {value}")
                    
        except Exception as e:
            logger.error(f"❌ 更新重试配置失败: {e}")
    
    def add_error_pattern(self, category: str, pattern: str):
        """添加错误模式"""
        try:
            if category in self.error_patterns:
                if pattern not in self.error_patterns[category]:
                    self.error_patterns[category].append(pattern)
                    logger.info(f"➕ 添加错误模式: {category} -> {pattern}")
                    
        except Exception as e:
            logger.error(f"❌ 添加错误模式失败: {e}")
    
    def get_error_analysis_report(self) -> Dict[str, Any]:
        """获取错误分析报告"""
        with self.lock:
            report = {
                'total_errors': 0,
                'error_distribution': {},
                'common_errors': {},
                'retry_effectiveness': {}
            }
            
            for data in self.retry_data.values():
                error_history = data.get('error_history', [])
                report['total_errors'] += len(error_history)
                
                for error_record in error_history:
                    error_type = error_record.get('type', 'unknown')
                    error_msg = error_record.get('error', '')
                    
                    # 错误类型分布
                    report['error_distribution'][error_type] = report['error_distribution'].get(error_type, 0) + 1
                    
                    # 常见错误
                    error_key = error_msg[:50]  # 截取前50个字符作为key
                    report['common_errors'][error_key] = report['common_errors'].get(error_key, 0) + 1
            
            return report
