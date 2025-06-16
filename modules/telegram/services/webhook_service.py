# -*- coding: utf-8 -*-
"""
Telegram Webhook服务 - 处理webhook相关逻辑
"""

import logging
import requests
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class TelegramWebhookService:
    """Telegram Webhook服务 - 管理webhook设置"""
    
    def __init__(self):
        pass
    
    def setup_webhook(self, bot_token: str, webhook_url: str) -> Tuple[bool, str]:
        """设置Telegram Webhook"""
        try:
            # 验证URL格式
            if not webhook_url.startswith(('http://', 'https://')):
                return False, 'Webhook URL格式无效，必须以http://或https://开头'
            
            # 检查HTTPS要求
            if webhook_url.startswith('http://'):
                logger.warning("⚠️ 检测到HTTP协议，Telegram要求HTTPS，可能会失败")
            
            # 设置webhook
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
                return True, 'Webhook设置成功'
            else:
                error_msg = result.get('description', '未知错误')
                logger.error(f"❌ Webhook设置失败: {error_msg}")
                
                # 提供更友好的错误信息
                if 'HTTPS' in error_msg.upper():
                    error_msg += ' (提示: Telegram要求Webhook URL使用HTTPS协议)'
                elif 'URL' in error_msg.upper():
                    error_msg += ' (提示: 请检查URL是否可以从外网访问)'
                
                return False, f'Webhook设置失败: {error_msg}'
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 网络请求失败: {e}")
            return False, f'网络请求失败: {str(e)}'
        except Exception as e:
            logger.error(f"❌ 设置Webhook失败: {e}")
            return False, str(e)
    
    def delete_webhook(self, bot_token: str) -> Tuple[bool, str]:
        """删除Telegram Webhook"""
        try:
            telegram_api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
            
            response = requests.post(telegram_api_url, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                logger.info("✅ Webhook删除成功")
                return True, 'Webhook删除成功'
            else:
                error_msg = result.get('description', '未知错误')
                logger.error(f"❌ Webhook删除失败: {error_msg}")
                return False, f'Webhook删除失败: {error_msg}'
                
        except Exception as e:
            logger.error(f"❌ 删除Webhook失败: {e}")
            return False, str(e)
    
    def get_webhook_info(self, bot_token: str) -> Tuple[bool, Dict[str, Any]]:
        """获取Telegram Webhook信息"""
        try:
            telegram_api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
            
            response = requests.get(telegram_api_url, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('ok'):
                logger.info("✅ 获取Webhook信息成功")
                return True, result.get('result', {})
            else:
                error_msg = result.get('description', '未知错误')
                logger.error(f"❌ 获取Webhook信息失败: {error_msg}")
                return False, {'error': f'获取Webhook信息失败: {error_msg}'}
                
        except Exception as e:
            logger.error(f"❌ 获取Webhook信息失败: {e}")
            return False, {'error': str(e)}
    
    def validate_webhook_url(self, webhook_url: str) -> Tuple[bool, str]:
        """验证Webhook URL"""
        if not webhook_url:
            return False, 'Webhook URL不能为空'
        
        if not webhook_url.startswith(('http://', 'https://')):
            return False, 'Webhook URL必须以http://或https://开头'
        
        if webhook_url.startswith('http://'):
            return True, '警告: Telegram要求使用HTTPS，HTTP可能无法正常工作'
        
        return True, 'URL格式正确'
    
    def build_webhook_url(self, base_url: str, custom_path: str = None) -> str:
        """构建Webhook URL"""
        base_url = base_url.rstrip('/')
        
        if custom_path:
            return f"{base_url}{custom_path}"
        else:
            return f"{base_url}/telegram/webhook"
    
    def test_webhook_connectivity(self, webhook_url: str) -> Tuple[bool, str]:
        """测试Webhook连通性"""
        try:
            # 发送测试请求
            response = requests.get(webhook_url, timeout=10)
            
            if response.status_code == 200:
                return True, 'Webhook URL可访问'
            elif response.status_code == 404:
                return True, 'Webhook端点存在（404是正常的，因为GET请求不被支持）'
            else:
                return False, f'Webhook URL返回状态码: {response.status_code}'
                
        except requests.exceptions.ConnectionError:
            return False, 'Webhook URL无法连接'
        except requests.exceptions.Timeout:
            return False, 'Webhook URL连接超时'
        except Exception as e:
            return False, f'测试连接失败: {str(e)}'


# 全局webhook服务实例
_webhook_service = None

def get_telegram_webhook_service() -> TelegramWebhookService:
    """获取Telegram Webhook服务实例"""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = TelegramWebhookService()
    return _webhook_service
