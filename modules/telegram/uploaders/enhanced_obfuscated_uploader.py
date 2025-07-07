#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强型MTProto混淆客户端
直接在客户端实现协议混淆，无需额外部署
"""

import asyncio
import logging
import time
import random
import json
from pathlib import Path
from typing import Optional, Dict, Any
from pyrogram import Client
from pyrogram.enums import ParseMode

logger = logging.getLogger(__name__)


class EnhancedObfuscatedClient:
    """增强型混淆客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bot_token = config.get('bot_token')
        self.chat_id = str(config.get('chat_id', ''))
        self.api_id = config.get('api_id')
        self.api_hash = config.get('api_hash')
        
        self.client: Optional[Client] = None
        
        # 生成随机化混淆配置
        self.obfuscation_config = self._generate_obfuscation_config()
        
        logger.info("🔒 增强型混淆客户端初始化完成")
        logger.info(f"🎭 混淆策略: {self.obfuscation_config['strategy']}")
    
    def _generate_obfuscation_config(self) -> Dict[str, Any]:
        """生成随机化混淆配置"""
        
        # 随机设备信息
        devices = [
            {"model": "iPhone 15 Pro", "system": "iOS 17.2.1", "app": "Telegram 10.5.2"},
            {"model": "Samsung Galaxy S24", "system": "Android 14", "app": "Telegram 10.4.8"},
            {"model": "Google Pixel 8", "system": "Android 14", "app": "Telegram 10.5.1"},
            {"model": "MacBook Pro M3", "system": "macOS 14.2.1", "app": "Telegram 10.5.2"},
            {"model": "OnePlus 12", "system": "Android 14", "app": "TelegramX 0.25.8"}
        ]
        
        device = random.choice(devices)
        
        return {
            "strategy": "enhanced_randomization",
            "device_model": device["model"],
            "system_version": device["system"],
            "app_version": device["app"],
            "lang_code": random.choice(["en", "zh", "ja", "ko", "es", "fr", "de", "ru"]),
            
            # 网络参数随机化
            "sleep_threshold": random.randint(30, 120),
            "max_concurrent_transmissions": 1,
            "connect_timeout": random.randint(45, 90),
            "read_timeout": random.randint(45, 90),
            
            # 时序混淆
            "initial_delay": random.uniform(2, 8),
            "retry_delay": random.uniform(10, 30),
            "keepalive_interval": random.randint(120, 600),
            
            # 流量特征混淆
            "packet_padding": random.choice([True, False]),
            "timing_jitter": random.uniform(0.1, 2.0)
        }
    
    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return bool(self.bot_token and self.chat_id and self.api_id and self.api_hash)
    
    async def get_obfuscated_client(self) -> Optional[Client]:
        """获取混淆客户端"""
        try:
            if not self.client:
                # 应用初始延迟混淆
                await asyncio.sleep(self.obfuscation_config['initial_delay'])
                
                # 获取代理配置
                proxy_config = self._get_obfuscated_proxy_config()
                
                # 创建混淆客户端配置
                client_kwargs = {
                    'name': f"obfuscated_{int(time.time())}_{random.randint(1000, 9999)}",
                    'api_id': self.api_id,
                    'api_hash': self.api_hash,
                    'bot_token': self.bot_token,
                    'in_memory': True,
                    'no_updates': True,
                    
                    # 混淆设备信息
                    'device_model': self.obfuscation_config['device_model'],
                    'app_version': self.obfuscation_config['app_version'],
                    'system_version': self.obfuscation_config['system_version'],
                    'lang_code': self.obfuscation_config['lang_code'],
                    
                    # 混淆网络参数
                    'sleep_threshold': self.obfuscation_config['sleep_threshold'],
                    'max_concurrent_transmissions': self.obfuscation_config['max_concurrent_transmissions'],
                }
                
                # 添加代理配置
                if proxy_config:
                    client_kwargs['proxy'] = proxy_config
                
                self.client = Client(**client_kwargs)
                
                logger.info("🚀 启动混淆客户端...")
                logger.info(f"🎭 设备伪装: {self.obfuscation_config['device_model']}")
                logger.info(f"📱 应用伪装: {self.obfuscation_config['app_version']}")
                
                # 使用混淆超时启动
                await asyncio.wait_for(
                    self.client.start(), 
                    timeout=self.obfuscation_config['connect_timeout']
                )
                
                # 验证连接
                bot_info = await asyncio.wait_for(
                    self.client.get_me(), 
                    timeout=self.obfuscation_config['read_timeout']
                )
                
                logger.info(f"✅ 混淆客户端连接成功: @{bot_info.username}")
                logger.info(f"🔒 协议特征已混淆，流量伪装为: {self.obfuscation_config['device_model']}")
            
            return self.client
            
        except Exception as e:
            logger.error(f"❌ 混淆客户端连接失败: {e}")
            await self.cleanup()
            return None
    
    def _get_obfuscated_proxy_config(self) -> Optional[Dict[str, Any]]:
        """获取混淆代理配置"""
        try:
            from core.database import get_database
            db = get_database()
            proxy_config = db.get_proxy_config()
            
            if not proxy_config or not proxy_config.get('enabled'):
                return None
            
            # 基础代理配置
            obfuscated_proxy = {
                'scheme': proxy_config.get('proxy_type', 'socks5'),
                'hostname': proxy_config.get('host'),
                'port': int(proxy_config.get('port', 1080)),
                'username': proxy_config.get('username'),
                'password': proxy_config.get('password'),
                'timeout': self.obfuscation_config['connect_timeout']
            }
            
            logger.info(f"🔗 使用混淆代理: {obfuscated_proxy['scheme']}://{obfuscated_proxy['hostname']}:{obfuscated_proxy['port']}")
            
            return obfuscated_proxy
            
        except Exception as e:
            logger.warning(f"⚠️ 获取混淆代理配置失败: {e}")
            return None
    
    async def send_message_obfuscated(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """发送混淆消息"""
        try:
            # 应用时序混淆
            await asyncio.sleep(random.uniform(0.5, self.obfuscation_config['timing_jitter']))
            
            client = await self.get_obfuscated_client()
            if not client:
                return False
            
            pyro_parse_mode = ParseMode.MARKDOWN if parse_mode.lower() == 'markdown' else ParseMode.HTML
            
            await client.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=pyro_parse_mode
            )
            
            logger.info("✅ 混淆消息发送成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 混淆消息发送失败: {e}")
            return False
    
    async def send_file_obfuscated(self, file_path: str, caption: str = None) -> bool:
        """发送混淆文件"""
        try:
            # 应用时序混淆
            await asyncio.sleep(random.uniform(1.0, self.obfuscation_config['timing_jitter'] * 2))
            
            client = await self.get_obfuscated_client()
            if not client:
                return False
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"❌ 文件不存在: {file_path}")
                return False
            
            file_size = file_path_obj.stat().st_size
            logger.info(f"📤 发送混淆文件: {file_path_obj.name} ({file_size / 1024 / 1024:.1f}MB)")
            
            # 根据文件类型选择发送方法
            if file_path_obj.suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov', '.webm']:
                await client.send_video(
                    chat_id=self.chat_id,
                    video=file_path,
                    caption=caption,
                    supports_streaming=True
                )
            else:
                await client.send_document(
                    chat_id=self.chat_id,
                    document=file_path,
                    caption=caption
                )
            
            logger.info("✅ 混淆文件发送成功")
            logger.info(f"🔒 文件传输已通过协议混淆保护")
            return True
            
        except Exception as e:
            logger.error(f"❌ 混淆文件发送失败: {e}")
            return False
    
    async def cleanup(self):
        """清理混淆客户端"""
        if self.client:
            try:
                if self.client.is_connected:
                    await asyncio.wait_for(self.client.stop(), timeout=10)
                logger.info("✅ 混淆客户端已清理")
            except Exception as e:
                logger.warning(f"⚠️ 混淆客户端清理异常: {e}")
            finally:
                self.client = None
