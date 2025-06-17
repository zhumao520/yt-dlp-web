# -*- coding: utf-8 -*-
"""
会话管理器

管理YouTube会话token和访问者数据，
基于Cobalt项目的会话管理机制
"""

import logging
import asyncio
import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)


class SessionManager:
    """YouTube会话管理器"""
    
    def __init__(self, session_server_url: Optional[str] = None):
        self.session_server_url = session_server_url
        self.session_data = None
        self.last_updated = 0
        self.update_interval = 900  # 15分钟更新一次
        self.session_file = Path("youtube_session.json")
        
        logger.info("🔐 会话管理器初始化完成")
    
    async def get_session_tokens(self) -> Optional[Dict[str, Any]]:
        """获取会话token"""
        try:
            # 检查是否需要更新
            current_time = time.time()
            if (not self.session_data or 
                current_time - self.last_updated > self.update_interval):
                await self._update_session()
            
            return self.session_data
            
        except Exception as e:
            logger.error(f"❌ 获取会话token失败: {e}")
            return None
    
    async def _update_session(self):
        """更新会话数据"""
        try:
            # 优先从会话服务器获取
            if self.session_server_url:
                session_data = await self._fetch_from_server()
                if session_data:
                    self.session_data = session_data
                    self.last_updated = time.time()
                    await self._save_session_to_file()
                    logger.info("✅ 从服务器更新会话数据成功")
                    return
            
            # 从本地文件加载
            session_data = await self._load_session_from_file()
            if session_data and self._validate_session(session_data):
                self.session_data = session_data
                self.last_updated = time.time()
                logger.info("✅ 从本地文件加载会话数据成功")
                return
            
            # 生成新的会话数据
            session_data = await self._generate_session()
            if session_data:
                self.session_data = session_data
                self.last_updated = time.time()
                await self._save_session_to_file()
                logger.info("✅ 生成新会话数据成功")
            
        except Exception as e:
            logger.error(f"❌ 更新会话数据失败: {e}")
    
    async def _fetch_from_server(self) -> Optional[Dict[str, Any]]:
        """从会话服务器获取token"""
        try:
            if not self.session_server_url:
                return None
            
            # 构建请求URL
            if not self.session_server_url.endswith('/'):
                self.session_server_url += '/'
            token_url = f"{self.session_server_url}token"
            
            try:
                with urllib.request.urlopen(token_url, timeout=10) as response:
                    if response.status == 200:
                        response_data = response.read().decode('utf-8')
                        data = json.loads(response_data)
                        if self._validate_session(data):
                            logger.info("✅ 从服务器获取会话token成功")
                            return data
                        else:
                            logger.warning("⚠️ 服务器返回的会话数据无效")
                    else:
                        logger.warning(f"⚠️ 会话服务器响应错误: {response.status}")
            except urllib.error.HTTPError as e:
                logger.warning(f"⚠️ 会话服务器HTTP错误: {e.code}")
            except urllib.error.URLError as e:
                logger.warning(f"⚠️ 会话服务器网络错误: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 从服务器获取会话token失败: {e}")
            return None
    
    async def _load_session_from_file(self) -> Optional[Dict[str, Any]]:
        """从文件加载会话数据"""
        try:
            if not self.session_file.exists():
                return None
            
            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data
            
        except Exception as e:
            logger.error(f"❌ 从文件加载会话数据失败: {e}")
            return None
    
    async def _save_session_to_file(self):
        """保存会话数据到文件"""
        try:
            if not self.session_data:
                return
            
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2)
            
            logger.info("✅ 会话数据已保存到文件")
            
        except Exception as e:
            logger.error(f"❌ 保存会话数据到文件失败: {e}")
    
    async def _generate_session(self) -> Optional[Dict[str, Any]]:
        """生成新的会话数据"""
        try:
            # 首先尝试自动获取真实的Token
            logger.info("🔍 尝试自动获取YouTube Token...")
            real_tokens = await self._fetch_real_youtube_tokens()

            if real_tokens and real_tokens.get('visitor_data'):
                logger.info("✅ 获取到真实YouTube Token")
                session_data = {
                    "visitor_data": real_tokens['visitor_data'],
                    "po_token": real_tokens.get('po_token'),
                    "updated": int(time.time()),
                    "generated": True,
                    "source": "auto_fetch"
                }
                return session_data

            # 回退到生成基础数据
            logger.info("⚠️ 无法获取真实Token，生成基础数据")
            import uuid
            import base64

            # 生成基础的visitor_data
            visitor_data = base64.b64encode(
                f"CgtZdWVfVmlzaXRvcg%3D%3D{int(time.time())}".encode()
            ).decode()

            session_data = {
                "visitor_data": visitor_data,
                "updated": int(time.time()),
                "generated": True,
                "source": "fallback"
            }

            logger.info("✅ 生成基础会话数据")
            return session_data

        except Exception as e:
            logger.error(f"❌ 生成会话数据失败: {e}")
            return None

    async def _fetch_real_youtube_tokens(self) -> Optional[Dict[str, Any]]:
        """自动获取真实的YouTube Token"""
        try:
            import aiohttp
            import re
            import asyncio

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            timeout = aiohttp.ClientTimeout(total=30)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get('https://www.youtube.com', headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ YouTube访问失败: {response.status}")
                        return None

                    text = await response.text()

                    # 提取 visitor_data
                    visitor_data_patterns = [
                        r'"visitorData":"([^"]+)"',
                        r'"VISITOR_DATA":"([^"]+)"',
                        r'visitorData["\']:\s*["\']([^"\']+)["\']'
                    ]

                    visitor_data = None
                    for pattern in visitor_data_patterns:
                        match = re.search(pattern, text)
                        if match:
                            visitor_data = match.group(1)
                            break

                    # 提取 po_token
                    po_token_patterns = [
                        r'"poToken":"([^"]+)"',
                        r'"PO_TOKEN":"([^"]+)"',
                        r'poToken["\']:\s*["\']([^"\']+)["\']'
                    ]

                    po_token = None
                    for pattern in po_token_patterns:
                        match = re.search(pattern, text)
                        if match:
                            po_token = match.group(1)
                            break

                    if visitor_data:
                        logger.info(f"✅ 获取到visitor_data: {visitor_data[:20]}...")
                        if po_token:
                            logger.info(f"✅ 获取到po_token: {po_token[:20]}...")

                        return {
                            'visitor_data': visitor_data,
                            'po_token': po_token
                        }
                    else:
                        logger.warning("⚠️ 未找到visitor_data")
                        return None

        except ImportError:
            logger.warning("⚠️ aiohttp未安装，无法自动获取Token")
            return None
        except Exception as e:
            logger.warning(f"⚠️ 自动获取Token失败: {e}")
            return None
    
    def _validate_session(self, session_data: Dict[str, Any]) -> bool:
        """验证会话数据"""
        try:
            if not isinstance(session_data, dict):
                return False
            
            # 检查必要字段
            if 'updated' not in session_data:
                return False
            
            # 检查更新时间（不能太旧）
            updated = session_data.get('updated', 0)
            current_time = time.time()
            
            # 如果超过24小时，认为过期
            if current_time - updated > 86400:
                logger.warning("⚠️ 会话数据已过期")
                return False
            
            # 如果有potoken，检查长度
            potoken = session_data.get('potoken')
            if potoken and len(potoken) < 160:
                logger.warning("⚠️ poToken长度可能不足")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 验证会话数据失败: {e}")
            return False
    
    def get_visitor_data(self) -> Optional[str]:
        """获取访问者数据"""
        if self.session_data:
            return self.session_data.get('visitor_data')
        return None
    
    def get_po_token(self) -> Optional[str]:
        """获取PO Token"""
        if self.session_data:
            return self.session_data.get('potoken')
        return None
    
    def is_session_valid(self) -> bool:
        """检查会话是否有效"""
        if not self.session_data:
            return False
        
        return self._validate_session(self.session_data)
    
    async def refresh_session(self):
        """强制刷新会话"""
        self.last_updated = 0  # 重置更新时间
        await self._update_session()
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息"""
        if not self.session_data:
            return {
                'status': 'no_session',
                'message': '没有会话数据'
            }
        
        return {
            'status': 'active',
            'has_visitor_data': bool(self.session_data.get('visitor_data')),
            'has_po_token': bool(self.session_data.get('potoken')),
            'updated': self.session_data.get('updated', 0),
            'age_seconds': int(time.time() - self.session_data.get('updated', 0)),
            'generated': self.session_data.get('generated', False)
        }
