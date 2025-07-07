# -*- coding: utf-8 -*-
"""
选择状态服务 - 管理用户交互状态
"""

import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SelectionStateService:
    """选择状态服务 - 管理用户的分辨率选择状态"""
    
    def __init__(self):
        self._states = {}
        self._state_ttl = 600  # 10分钟过期
    
    def store_state(self, chat_id: str, url: str, video_info: Dict[str, Any],
                   quality_options: list, custom_filename: Optional[str] = None) -> None:
        """存储用户选择状态"""
        try:
            state = {
                'url': url,
                'video_info': video_info,
                'quality_options': quality_options,
                'custom_filename': custom_filename,
                'timestamp': time.time()
            }

            self._states[str(chat_id)] = state
            logger.debug(f"📝 存储选择状态: chat_id={chat_id}, url={url}, custom_filename={custom_filename}")

            # 清理过期状态
            self._cleanup_expired_states()

        except Exception as e:
            logger.error(f"❌ 存储选择状态失败: {e}")
    
    def get_state(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """获取用户选择状态"""
        try:
            state = self._states.get(str(chat_id))
            if not state:
                return None
            
            # 检查是否过期
            if time.time() - state['timestamp'] > self._state_ttl:
                self.clear_state(chat_id)
                return None
            
            return state
            
        except Exception as e:
            logger.error(f"❌ 获取选择状态失败: {e}")
            return None
    
    def clear_state(self, chat_id: str) -> None:
        """清除用户选择状态"""
        try:
            chat_id_str = str(chat_id)
            if chat_id_str in self._states:
                del self._states[chat_id_str]
                logger.debug(f"🗑️ 清除选择状态: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"❌ 清除选择状态失败: {e}")
    
    def _cleanup_expired_states(self) -> None:
        """清理过期状态"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for chat_id, state in self._states.items():
                if current_time - state['timestamp'] > self._state_ttl:
                    expired_keys.append(chat_id)
            
            for key in expired_keys:
                del self._states[key]
            
            if expired_keys:
                logger.debug(f"🧹 清理了{len(expired_keys)}个过期状态")
                
        except Exception as e:
            logger.error(f"❌ 清理过期状态失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取状态统计信息"""
        try:
            current_time = time.time()
            active_count = 0
            expired_count = 0
            
            for state in self._states.values():
                if current_time - state['timestamp'] <= self._state_ttl:
                    active_count += 1
                else:
                    expired_count += 1
            
            return {
                'total_states': len(self._states),
                'active_states': active_count,
                'expired_states': expired_count,
                'state_ttl': self._state_ttl
            }
            
        except Exception as e:
            logger.error(f"❌ 获取状态统计失败: {e}")
            return {}
    
    def clear_all_states(self) -> None:
        """清除所有状态"""
        try:
            count = len(self._states)
            self._states.clear()
            logger.info(f"🗑️ 清除了所有选择状态({count}个)")
        except Exception as e:
            logger.error(f"❌ 清除所有状态失败: {e}")


# 全局状态服务实例
_state_service = None

def get_selection_state_service() -> SelectionStateService:
    """获取选择状态服务实例"""
    global _state_service
    if _state_service is None:
        _state_service = SelectionStateService()
    return _state_service
