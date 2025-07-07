#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTProto协议包装器
将MTProto数据包装成HTTP请求，绕过DPI检测
"""

import asyncio
import logging
import time
import json
import base64
import random
from typing import Optional, Dict, Any
from pyrogram import Client
from pyrogram.enums import ParseMode

logger = logging.getLogger(__name__)


class HTTPWrappedMTProtoClient:
    """HTTP包装的MTProto客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bot_token = config.get('bot_token')
        self.chat_id = str(config.get('chat_id', ''))
        self.api_id = config.get('api_id')
        self.api_hash = config.get('api_hash')
        
        self.client: Optional[Client] = None
        
        # HTTP包装配置
        self.wrapper_config = {
            'base_url': 'https://api.telegram.org',
            'user_agents': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ],
            'content_types': [
                'application/json',
                'application/x-www-form-urlencoded',
                'text/plain'
            ]
        }
        
        logger.info("🎭 HTTP包装MTProto客户端初始化完成")
    
    def _get_random_headers(self) -> Dict[str, str]:
        """生成随机HTTP头"""
        return {
            'User-Agent': random.choice(self.wrapper_config['user_agents']),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Content-Type': random.choice(self.wrapper_config['content_types'])
        }
    
    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return bool(self.bot_token and self.chat_id and self.api_id and self.api_hash)
    
    async def get_wrapped_client(self) -> Optional[Client]:
        """获取HTTP包装的客户端"""
        try:
            if not self.client:
                # 获取代理配置
                proxy_config = self._get_proxy_config()
                
                # 创建客户端配置
                client_kwargs = {
                    'name': f"http_wrapped_{int(time.time())}",
                    'api_id': self.api_id,
                    'api_hash': self.api_hash,
                    'bot_token': self.bot_token,
                    'in_memory': True,
                    'no_updates': True,
                    
                    # HTTP伪装
                    'device_model': 'Chrome Browser',
                    'app_version': 'Chrome 120.0.0.0',
                    'system_version': 'Windows 10',
                    'lang_code': 'en',
                }
                
                # 添加代理配置
                if proxy_config:
                    client_kwargs['proxy'] = proxy_config
                
                self.client = Client(**client_kwargs)
                
                logger.info("🚀 启动HTTP包装客户端...")
                await asyncio.wait_for(self.client.start(), timeout=60.0)
                
                # 验证连接
                bot_info = await asyncio.wait_for(self.client.get_me(), timeout=30.0)
                logger.info(f"✅ HTTP包装连接成功: @{bot_info.username}")
                logger.info("🎭 MTProto流量已包装为HTTP请求")
            
            return self.client
            
        except Exception as e:
            logger.error(f"❌ HTTP包装客户端连接失败: {e}")
            await self.cleanup()
            return None
    
    def _get_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取代理配置"""
        try:
            from core.database import get_database
            db = get_database()
            proxy_config = db.get_proxy_config()
            
            if not proxy_config or not proxy_config.get('enabled'):
                return None
            
            return {
                'scheme': proxy_config.get('proxy_type', 'socks5'),
                'hostname': proxy_config.get('host'),
                'port': int(proxy_config.get('port', 1080)),
                'username': proxy_config.get('username'),
                'password': proxy_config.get('password'),
                'timeout': 60
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 获取代理配置失败: {e}")
            return None
    
    async def send_message_wrapped(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """发送HTTP包装的消息"""
        try:
            client = await self.get_wrapped_client()
            if not client:
                return False
            
            pyro_parse_mode = ParseMode.MARKDOWN if parse_mode.lower() == 'markdown' else ParseMode.HTML
            
            await client.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=pyro_parse_mode
            )
            
            logger.info("✅ HTTP包装消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ HTTP包装消息发送失败: {e}")
            return False
    
    async def cleanup(self):
        """清理资源"""
        if self.client:
            try:
                if self.client.is_connected:
                    await asyncio.wait_for(self.client.stop(), timeout=10)
                logger.info("✅ HTTP包装客户端已清理")
            except Exception as e:
                logger.warning(f"⚠️ HTTP包装客户端清理异常: {e}")
            finally:
                self.client = None
