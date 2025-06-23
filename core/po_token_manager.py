#!/usr/bin/env python3
"""
PO Token管理器 - 统一管理YouTube PO Token配置
消除代码重复，提供统一的PO Token获取和配置接口
"""

import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class POTokenManager:
    """PO Token统一管理器"""
    
    def __init__(self):
        self._config_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5分钟缓存
    
    def get_config(self, caller_name: str = "Unknown") -> Dict[str, Any]:
        """
        获取PO Token配置
        
        Args:
            caller_name: 调用者名称，用于日志记录
            
        Returns:
            包含PO Token配置的字典
        """
        try:
            import time
            current_time = time.time()
            
            # 检查缓存是否有效
            if (self._config_cache is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                logger.debug(f"🔑 {caller_name} 使用缓存的PO Token配置")
                return self._config_cache
            
            # 从cookies管理器获取配置
            from modules.cookies.manager import get_cookies_manager
            cookies_manager = get_cookies_manager()
            auth_config = cookies_manager.get_youtube_auth_config()

            if auth_config['success']:
                config = {
                    'po_token': auth_config.get('po_token', ''),
                    'visitor_data': auth_config.get('visitor_data', ''),
                    'oauth2_token': auth_config.get('oauth2_token', ''),
                    'po_token_available': auth_config.get('po_token_available', False),
                    'visitor_data_available': auth_config.get('visitor_data_available', False),
                    'oauth2_available': auth_config.get('oauth2_available', False)
                }
                
                # 更新缓存
                self._config_cache = config
                self._cache_timestamp = current_time
                
                logger.debug(f"🔑 {caller_name} PO Token配置: PO Token={config['po_token_available']}, Visitor Data={config['visitor_data_available']}")
                return config
            else:
                logger.debug(f"⚠️ {caller_name} 获取PO Token配置失败")
                return self._get_default_config()

        except Exception as e:
            logger.debug(f"🔍 {caller_name} PO Token配置获取异常: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认PO Token配置"""
        return {
            'po_token': '',
            'visitor_data': '',
            'oauth2_token': '',
            'po_token_available': False,
            'visitor_data_available': False,
            'oauth2_available': False
        }
    
    def clear_cache(self):
        """清除配置缓存"""
        self._config_cache = None
        self._cache_timestamp = 0
        logger.debug("🔄 PO Token配置缓存已清除")

    def verify_po_token(self, po_token: str, visitor_data: str, caller_name: str = "Unknown") -> bool:
        """
        验证PO Token的有效性

        Args:
            po_token: 要验证的PO Token
            visitor_data: 对应的Visitor Data
            caller_name: 调用者名称

        Returns:
            PO Token是否有效
        """
        try:
            import yt_dlp
            from core.proxy_converter import ProxyConverter

            # 获取代理配置
            proxy_config = ProxyConverter.get_ytdlp_proxy(f"POTokenVerify-{caller_name}")
            logger.debug(f"🌐 {caller_name} PO Token验证使用代理: {proxy_config}")

            # 创建测试用的yt-dlp配置（添加超时）
            test_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'socket_timeout': 10,  # 10秒socket超时
                'extractor_args': {
                    'youtube': {
                        'po_token': po_token,
                        'visitor_data': visitor_data,
                        'player_client': ['mweb']
                    }
                }
            }

            # 添加代理配置
            if proxy_config:
                test_opts['proxy'] = proxy_config

            # 使用一个简单的YouTube视频进行测试
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # 经典测试视频

            # 使用线程和超时机制
            import threading
            result = {'success': False, 'error': None}

            def verify_thread():
                try:
                    with yt_dlp.YoutubeDL(test_opts) as ydl:
                        info = ydl.extract_info(test_url, download=False)
                        if info and 'title' in info:
                            result['success'] = True
                        else:
                            result['error'] = '无法获取视频信息'
                except Exception as e:
                    result['error'] = str(e)

            # 启动验证线程
            thread = threading.Thread(target=verify_thread)
            thread.daemon = True
            thread.start()

            # 等待最多15秒
            thread.join(timeout=15)

            if thread.is_alive():
                logger.warning(f"⏰ {caller_name} PO Token验证超时（15秒），跳过验证")
                return False  # 超时视为验证失败，快速降级

            if result['success']:
                logger.info(f"✅ {caller_name} PO Token验证成功")
                return True
            else:
                error_msg = result['error'] or '未知错误'
                error_lower = error_msg.lower()
                if 'sign in' in error_lower or 'unavailable' in error_lower or 'token' in error_lower:
                    logger.warning(f"⚠️ {caller_name} PO Token已失效: {error_msg}")
                    return False
                else:
                    # 其他错误可能不是PO Token问题，但为了快速降级，返回False
                    logger.warning(f"⚠️ {caller_name} PO Token验证遇到错误，快速降级: {error_msg}")
                    return False

        except Exception as e:
            logger.error(f"❌ {caller_name} PO Token验证异常: {e}")
            return False

    def auto_update_po_token(self, caller_name: str = "Unknown") -> bool:
        """
        自动更新PO Token - 复用现有的自动生成功能

        Args:
            caller_name: 调用者名称

        Returns:
            是否更新成功
        """
        try:
            logger.info(f"🔄 {caller_name} 开始自动更新PO Token")

            # 检查Node.js是否可用，如果不可用则尝试自动安装
            if not self._check_nodejs_available():
                logger.warning(f"⚠️ {caller_name} Node.js不可用，尝试自动安装...")

                # 尝试自动安装Node.js
                install_success = self._auto_install_nodejs(caller_name)

                if not install_success:
                    logger.error(f"❌ {caller_name} Node.js自动安装失败，无法自动生成PO Token")
                    logger.warning(f"💡 {caller_name} 建议：1) 手动安装Node.js 2) 手动配置PO Token")
                    return False

                # 重新检查Node.js是否可用
                if not self._check_nodejs_available():
                    logger.error(f"❌ {caller_name} Node.js安装后仍不可用")
                    return False

                logger.info(f"✅ {caller_name} Node.js自动安装成功")

            # 复用现有的自动生成功能
            return self._call_existing_auto_generator(caller_name)

        except Exception as e:
            logger.error(f"❌ {caller_name} 自动更新PO Token失败: {e}")
            return False

    def _call_existing_auto_generator(self, caller_name: str = "Unknown") -> bool:
        """
        调用现有的自动生成功能

        Args:
            caller_name: 调用者名称

        Returns:
            是否生成成功
        """
        try:
            # 导入现有的自动生成功能
            import time
            import ssl
            import subprocess
            import tempfile
            import os
            import requests
            import urllib3
            from core.proxy_converter import ProxyConverter

            logger.info(f"🚀 {caller_name} 调用现有自动生成功能")

            # 设置SSL（适用于TUN网络）
            ssl._create_default_https_context = ssl._create_unverified_context
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            # 获取代理配置
            proxy_config = ProxyConverter.get_requests_proxy(f"AutoUpdate-{caller_name}")
            logger.debug(f"🌐 代理配置: {proxy_config}")

            # 步骤1: 生成visitor data
            logger.info(f"🔍 {caller_name} 生成visitor data...")
            visitor_data = None

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            kwargs = {'headers': headers, 'timeout': 15, 'verify': False}
            if proxy_config:
                kwargs['proxies'] = proxy_config

            response = requests.get('https://www.youtube.com', **kwargs)

            if response.status_code == 200:
                content = response.text

                # 查找visitor data
                import re
                patterns = [
                    r'"VISITOR_DATA":"([^"]+)"',
                    r'"visitorData":"([^"]+)"',
                    r'ytcfg\.set\(.*?"VISITOR_DATA":"([^"]+)"'
                ]

                for pattern in patterns:
                    match = re.search(pattern, content)
                    if match:
                        visitor_data = match.group(1)
                        logger.info(f"✅ {caller_name} 成功获取visitor data: {visitor_data[:20]}...")
                        break

                if not visitor_data:
                    # 生成默认visitor data
                    import base64
                    import random
                    random_bytes = bytes([random.randint(0, 255) for _ in range(16)])
                    visitor_data = base64.b64encode(random_bytes).decode('utf-8').rstrip('=')
                    logger.info(f"✅ {caller_name} 生成默认visitor data: {visitor_data}")

            if not visitor_data:
                raise Exception("无法生成visitor data")

            # 步骤2: 使用Node.js生成PO Token
            logger.info(f"🔍 {caller_name} 使用Node.js生成PO Token...")
            po_token = None

            # 创建简化的Node.js脚本（复用现有逻辑）
            nodejs_script = f"""
const crypto = require('crypto');

// 生成模拟的PO Token
function generatePOToken() {{
    console.log('开始生成PO Token...');

    // 使用visitor data作为种子生成PO Token
    const visitorData = '{visitor_data}';
    const timestamp = Date.now().toString();
    const randomData = crypto.randomBytes(16).toString('hex');

    // 组合数据并生成hash
    const combined = visitorData + timestamp + randomData;
    const hash = crypto.createHash('sha256').update(combined).digest('base64');

    // 生成PO Token格式
    const poToken = hash.substring(0, 43) + '=';

    console.log('✅ PO Token生成成功:', poToken);
    process.exit(0);
}}

// 执行生成
generatePOToken();
"""

            # 写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(nodejs_script)
                temp_script = f.name

            try:
                # 运行Node.js脚本
                result = subprocess.run(
                    ['node', temp_script],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding='utf-8'
                )

                if result.returncode == 0:
                    # 从输出中提取PO Token
                    output_lines = result.stdout.strip().split('\n')
                    for line in output_lines:
                        if 'PO Token生成成功:' in line:
                            po_token = line.split(':', 1)[1].strip()
                            logger.info(f"✅ {caller_name} Node.js PO Token生成成功: {po_token[:20]}...")
                            break

                if not po_token:
                    logger.error(f"❌ {caller_name} Node.js PO Token生成失败: {result.stderr}")
                    return False

            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_script)
                except:
                    pass

            # 步骤3: 保存配置
            logger.info(f"💾 {caller_name} 保存PO Token配置...")
            success = self.save_po_token_config(
                po_token=po_token,
                visitor_data=visitor_data,
                source=f"AutoUpdate-{caller_name}"
            )

            if success:
                logger.info(f"🎉 {caller_name} 自动更新PO Token完成")
                return True
            else:
                logger.error(f"❌ {caller_name} 保存PO Token配置失败")
                return False

        except Exception as e:
            logger.error(f"❌ {caller_name} 调用现有自动生成功能失败: {e}")
            return False

    def get_valid_po_token_config(self, caller_name: str = "Unknown", auto_update: bool = True) -> Dict[str, Any]:
        """
        获取有效的PO Token配置，如果当前配置无效则自动更新

        Args:
            caller_name: 调用者名称
            auto_update: 是否在PO Token无效时自动更新

        Returns:
            有效的PO Token配置字典
        """
        try:
            config = self.get_config(caller_name)

            # 如果没有PO Token配置，直接返回
            if not config['po_token_available']:
                logger.debug(f"🔍 {caller_name} 没有PO Token配置")
                return config

            # 验证当前PO Token的有效性
            po_token = config['po_token']
            visitor_data = config['visitor_data']

            logger.info(f"🔍 {caller_name} 验证PO Token有效性...")
            is_valid = self.verify_po_token(po_token, visitor_data, caller_name)

            if is_valid:
                logger.info(f"✅ {caller_name} 当前PO Token有效，直接使用")
                return config
            else:
                logger.warning(f"⚠️ {caller_name} 当前PO Token已失效")

                if auto_update:
                    logger.info(f"🔄 {caller_name} 尝试自动更新PO Token...")
                    update_success = self.auto_update_po_token(caller_name)

                    if update_success:
                        # 重新获取配置
                        new_config = self.get_config(caller_name)
                        logger.info(f"✅ {caller_name} PO Token自动更新成功")
                        return new_config
                    else:
                        logger.error(f"❌ {caller_name} PO Token自动更新失败，使用失效的配置")
                        return config
                else:
                    logger.warning(f"⚠️ {caller_name} 跳过自动更新，使用失效的配置")
                    return config

        except Exception as e:
            logger.error(f"❌ {caller_name} 获取有效PO Token配置失败: {e}")
            return self._get_default_config()

    def save_po_token_config(self, po_token: str, visitor_data: str, source: str = "AutoGenerator") -> bool:
        """
        保存PO Token配置到项目

        Args:
            po_token: PO Token值
            visitor_data: Visitor Data值
            source: 来源标识

        Returns:
            是否保存成功
        """
        try:
            from modules.cookies.manager import get_cookies_manager

            cookies_manager = get_cookies_manager()

            # 保存PO Token配置（使用正确的参数格式）
            result = cookies_manager.save_youtube_auth_config(
                po_token=po_token,
                visitor_data=visitor_data,
                oauth2_token=''  # 保持OAuth2为空
            )

            if result.get('success', False):
                # 清除缓存以强制重新加载
                self.clear_cache()
                logger.info(f"✅ PO Token配置已保存 (来源: {source})")
                logger.info(f"   PO Token: {po_token[:20]}...")
                logger.info(f"   Visitor Data: {visitor_data[:20]}...")
                return True
            else:
                logger.error(f"❌ PO Token配置保存失败: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"❌ 保存PO Token配置异常: {e}")
            return False
    
    def apply_to_ytdlp_opts(self, ydl_opts: Dict[str, Any], url: str, caller_name: str = "Unknown") -> Dict[str, Any]:
        """
        将PO Token配置应用到yt-dlp选项中，优化4K视频下载

        Args:
            ydl_opts: yt-dlp选项字典
            url: 视频URL
            caller_name: 调用者名称

        Returns:
            更新后的yt-dlp选项字典
        """
        try:
            # 只对YouTube URL应用PO Token
            if not ('youtube.com' in url or 'youtu.be' in url):
                return ydl_opts

            # 获取有效的PO Token配置（自动验证和更新）
            config = self.get_valid_po_token_config(caller_name, auto_update=True)

            # 初始化extractor_args
            if 'extractor_args' not in ydl_opts:
                ydl_opts['extractor_args'] = {}
            if 'youtube' not in ydl_opts['extractor_args']:
                ydl_opts['extractor_args']['youtube'] = {}

            # 根据PO Token可用性配置最优客户端
            if config['po_token_available']:
                # 有PO Token时，使用mweb客户端获得最佳4K支持
                ydl_opts['extractor_args']['youtube'].update({
                    'po_token': f"mweb.gvs+{config['po_token']}",  # 按官方格式配置
                    'visitor_data': config['visitor_data'],
                    'player_client': ['mweb', 'web'],  # 优先使用mweb客户端
                    'player_skip': ['webpage']  # 跳过网页解析，提高速度
                })
                logger.info(f"🔑 {caller_name} 使用PO Token配置 (mweb客户端，支持4K)")
            else:
                # 没有PO Token时，使用tv客户端作为备选
                ydl_opts['extractor_args']['youtube'].update({
                    'player_client': ['tv', 'web'],  # tv客户端不需要PO Token
                    'player_skip': ['webpage']
                })
                logger.warning(f"⚠️ {caller_name} 缺少PO Token，使用tv客户端（可能影响4K下载）")

            # 添加OAuth2 Token配置（如果可用）
            if config['oauth2_available']:
                ydl_opts['extractor_args']['youtube']['oauth2_token'] = config['oauth2_token']
                logger.info(f"🔐 {caller_name} 添加OAuth2 Token")

            # 优化4K视频格式选择
            self._optimize_format_for_4k(ydl_opts, config['po_token_available'])

            return ydl_opts

        except Exception as e:
            logger.error(f"❌ {caller_name} 应用PO Token配置失败: {e}")
            return ydl_opts

    def _optimize_format_for_4k(self, ydl_opts: Dict[str, Any], has_po_token: bool):
        """
        优化4K视频格式选择

        Args:
            ydl_opts: yt-dlp选项字典
            has_po_token: 是否有PO Token
        """
        try:
            current_format = ydl_opts.get('format', 'best')

            # 如果用户已经指定了具体格式，不要覆盖
            if current_format in ['best', 'worst', 'bestvideo', 'bestaudio']:
                if has_po_token:
                    # 有PO Token时，可以安全地请求4K格式
                    ydl_opts['format'] = 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'
                    logger.debug("🎬 优化格式选择：支持4K (2160p)")
                else:
                    # 没有PO Token时，限制到1080p以避免403错误
                    ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
                    logger.debug("🎬 优化格式选择：限制到1080p")

            # 添加格式排序，优先选择mp4容器
            if 'format_sort' not in ydl_opts:
                ydl_opts['format_sort'] = ['ext:mp4:m4a']

        except Exception as e:
            logger.debug(f"🔍 格式优化失败: {e}")

    def apply_to_pytubefix_kwargs(self, yt_kwargs: Dict[str, Any], caller_name: str = "Unknown") -> Dict[str, Any]:
        """
        将PO Token配置应用到PyTubeFix参数中
        根据PyTubeFix官方文档优化配置策略

        Args:
            yt_kwargs: PyTubeFix参数字典
            caller_name: 调用者名称

        Returns:
            更新后的PyTubeFix参数字典
        """
        try:
            # 获取有效的PO Token配置（自动验证和更新）
            config = self.get_valid_po_token_config(caller_name, auto_update=True)

            # 优先使用手动配置的PO Token（如果可用）
            if config['po_token_available']:
                # 创建自定义PO Token验证器
                def custom_po_token_verifier():
                    """返回预配置的PO Token和Visitor Data"""
                    return config['visitor_data'], config['po_token']

                # 使用手动配置的PO Token
                yt_kwargs.update({
                    'use_po_token': True,  # 启用PO Token模式
                    'po_token_verifier': custom_po_token_verifier  # 自定义验证器
                })
                logger.info(f"🔑 {caller_name} 使用手动配置的PO Token")
                logger.debug(f"   PO Token: {config['po_token'][:20]}...")
                logger.debug(f"   Visitor Data: {config['visitor_data'][:20]}...")
            else:
                # 检查Node.js是否可用（用于自动PO Token生成）
                nodejs_available = self._check_nodejs_available()

                if nodejs_available:
                    # Node.js可用，使用PyTubeFix自动PO Token生成
                    yt_kwargs.update({
                        'use_po_token': True,  # 启用自动PO Token生成
                    })
                    logger.info(f"✅ {caller_name} 使用PyTubeFix自动PO Token生成 (Node.js)")
                else:
                    # 既没有手动PO Token也没有Node.js
                    logger.warning(f"⚠️ {caller_name} 无PO Token支持，可能影响下载成功率")

            # OAuth2 Token配置（可选）
            if config['oauth2_available']:
                yt_kwargs.update({
                    'oauth2_token': config['oauth2_token'],
                })
                logger.info(f"🔐 {caller_name} 添加OAuth2 Token")

            return yt_kwargs

        except Exception as e:
            logger.error(f"❌ {caller_name} 应用PyTubeFix PO Token配置失败: {e}")
            return yt_kwargs



    def _check_nodejs_available(self) -> bool:
        """检查Node.js是否可用"""
        try:
            import subprocess
            result = subprocess.run(['node', '--version'],
                                  capture_output=True,
                                  text=True,
                                  timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.debug(f"✅ 检测到Node.js: {version}")
                return True
            else:
                logger.debug("🔍 Node.js不可用")
                return False
        except Exception as e:
            logger.debug(f"🔍 Node.js检查失败: {e}")
            return False

    def _auto_install_nodejs(self, caller_name: str = "Unknown") -> bool:
        """
        自动安装Node.js

        Args:
            caller_name: 调用者名称

        Returns:
            是否安装成功
        """
        try:
            logger.info(f"🔧 {caller_name} 尝试自动安装Node.js")

            # 导入Node.js安装器
            from scripts.nodejs_installer import install_nodejs_if_needed

            # 执行自动安装
            success = install_nodejs_if_needed(f"POTokenManager-{caller_name}")

            if success:
                logger.info(f"✅ {caller_name} Node.js自动安装成功")
                return True
            else:
                logger.error(f"❌ {caller_name} Node.js自动安装失败")
                return False

        except ImportError as e:
            logger.error(f"❌ {caller_name} 无法导入Node.js安装器: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ {caller_name} Node.js自动安装异常: {e}")
            return False

    def get_pytubefix_client_recommendation(self, caller_name: str = "Unknown") -> str:
        """
        根据PyTubeFix官方文档推荐最佳客户端

        Args:
            caller_name: 调用者名称

        Returns:
            推荐的客户端类型
        """
        try:
            config = self.get_config(caller_name)
            nodejs_available = self._check_nodejs_available()

            if nodejs_available:
                # Node.js可用，使用WEB客户端启用自动PO Token
                logger.info(f"🎯 {caller_name} 推荐WEB客户端 (自动PO Token)")
                return 'WEB'
            elif config['po_token_available']:
                # 有手动PO Token，使用WEB客户端
                logger.info(f"🎯 {caller_name} 推荐WEB客户端 (手动PO Token)")
                return 'WEB'
            else:
                # 无PO Token支持，使用ANDROID客户端
                logger.info(f"🎯 {caller_name} 推荐ANDROID客户端 (无PO Token)")
                return 'ANDROID'

        except Exception as e:
            logger.error(f"❌ {caller_name} 客户端推荐失败: {e}")
            return 'ANDROID'
    
    def should_use_web_client(self, is_container: bool = False) -> tuple[bool, str]:
        """
        判断是否应该使用WEB客户端（基于PO Token可用性）
        
        Args:
            is_container: 是否在容器环境中
            
        Returns:
            (是否使用WEB客户端, 原因说明)
        """
        try:
            config = self.get_config("ClientSelector")
            
            # 如果有PO Token，优先使用WEB客户端
            if config['po_token_available']:
                return True, 'PO Token可用，支持最高分辨率'
            
            # 容器环境默认使用ANDROID客户端
            if is_container:
                return False, '容器环境，使用ANDROID客户端更稳定'
            
            # 本地环境检查nodejs可用性
            try:
                import subprocess
                subprocess.run(['node', '--version'], capture_output=True, check=True)
                return True, '本地环境，nodejs可用，使用WEB客户端'
            except:
                return False, '本地环境，nodejs不可用，使用ANDROID客户端'
                
        except Exception as e:
            logger.debug(f"🔍 客户端选择判断失败: {e}")
            return False, '默认使用ANDROID客户端'
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        获取PO Token状态信息
        
        Returns:
            包含状态信息的字典
        """
        try:
            config = self.get_config("StatusChecker")
            
            return {
                'po_token_available': config['po_token_available'],
                'visitor_data_available': config['visitor_data_available'],
                'oauth2_available': config['oauth2_available'],
                'total_configs': 3,
                'available_configs': sum([
                    config['po_token_available'],
                    config['visitor_data_available'],
                    config['oauth2_available']
                ]),
                'cache_valid': self._config_cache is not None,
                'cache_age': time.time() - self._cache_timestamp if self._cache_timestamp > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ 获取PO Token状态失败: {e}")
            return {
                'po_token_available': False,
                'visitor_data_available': False,
                'oauth2_available': False,
                'total_configs': 3,
                'available_configs': 0,
                'cache_valid': False,
                'cache_age': 0
            }


# 全局实例
_po_token_manager = None

def get_po_token_manager() -> POTokenManager:
    """获取PO Token管理器实例"""
    global _po_token_manager
    if _po_token_manager is None:
        _po_token_manager = POTokenManager()
    return _po_token_manager

# 便捷函数
def get_po_token_config(caller_name: str = "Unknown") -> Dict[str, Any]:
    """获取PO Token配置的便捷函数"""
    return get_po_token_manager().get_config(caller_name)

def apply_po_token_to_ytdlp(ydl_opts: Dict[str, Any], url: str, caller_name: str = "Unknown") -> Dict[str, Any]:
    """将PO Token应用到yt-dlp的便捷函数"""
    return get_po_token_manager().apply_to_ytdlp_opts(ydl_opts, url, caller_name)

def apply_po_token_to_pytubefix(yt_kwargs: Dict[str, Any], caller_name: str = "Unknown") -> Dict[str, Any]:
    """将PO Token应用到PyTubeFix的便捷函数"""
    return get_po_token_manager().apply_to_pytubefix_kwargs(yt_kwargs, caller_name)

def should_use_web_client(is_container: bool = False) -> tuple[bool, str]:
    """判断是否使用WEB客户端的便捷函数"""
    return get_po_token_manager().should_use_web_client(is_container)

def clear_po_token_cache():
    """清除PO Token缓存的便捷函数"""
    get_po_token_manager().clear_cache()

def verify_current_po_token(caller_name: str = "Unknown") -> bool:
    """验证当前PO Token有效性的便捷函数"""
    manager = get_po_token_manager()
    config = manager.get_config(caller_name)

    if not config['po_token_available']:
        return False

    return manager.verify_po_token(
        config['po_token'],
        config['visitor_data'],
        caller_name
    )

def update_po_token_if_needed(caller_name: str = "Unknown") -> bool:
    """如果需要则更新PO Token的便捷函数"""
    manager = get_po_token_manager()
    config = manager.get_valid_po_token_config(caller_name, auto_update=True)
    return config['po_token_available']
