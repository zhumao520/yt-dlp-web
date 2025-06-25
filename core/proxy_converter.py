"""
代理转换工具类
统一处理各种代理类型的转换和配置
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class ProxyConverter:
    """代理转换工具类"""
    
    # 常见的HTTP代理端口映射策略（不包含硬编码的特定端口）
    HTTP_PORT_MAPPING = [
        '1080',  # 尝试原SOCKS5端口作为HTTP
        '8080',  # 常见HTTP代理端口
        '3128',  # Squid代理默认端口
        '8888',  # 另一个常见HTTP代理端口
    ]
    
    @staticmethod
    def get_proxy_config() -> Optional[Dict[str, Any]]:
        """从数据库获取代理配置"""
        try:
            from core.database import get_database
            db = get_database()
            proxy_config = db.get_proxy_config()

            if proxy_config and proxy_config.get('enabled'):
                return proxy_config
            return None
        except Exception as e:
            logger.debug(f"🔍 获取代理配置失败: {e}")
            return None

    @classmethod
    def _parse_proxy_config(cls, module_name: str = "Unknown") -> Optional[Tuple[str, str, str, str, str]]:
        """解析代理配置，返回通用的代理参数

        Returns:
            Tuple[proxy_type, host, port, username, password] 或 None
        """
        proxy_config = cls.get_proxy_config()
        if not proxy_config:
            return None

        proxy_type = proxy_config.get('proxy_type', 'http')
        host = proxy_config.get('host')
        port = proxy_config.get('port')
        username = proxy_config.get('username', '')
        password = proxy_config.get('password', '')

        if not host or not port:
            logger.warning(f"⚠️ {module_name}: 代理配置不完整")
            return None

        return proxy_type, host, str(port), username, password

    @classmethod
    def _build_auth_string(cls, username: str, password: str) -> str:
        """构建认证字符串"""
        if username and password:
            return f"{username}:{password}@"
        return ""
    
    @classmethod
    def get_requests_proxy(cls, module_name: str = "Unknown") -> Optional[Dict[str, str]]:
        """
        获取适用于requests库的代理配置

        Args:
            module_name: 调用模块名称，用于日志标识

        Returns:
            Dict[str, str]: requests库格式的代理配置 {'http': 'proxy_url', 'https': 'proxy_url'}
            None: 无代理或代理不可用
        """
        parsed = cls._parse_proxy_config(module_name)
        if not parsed:
            return None

        try:
            proxy_type, host, port, username, password = parsed
            auth = cls._build_auth_string(username, password)

            # 根据代理类型处理
            if proxy_type == 'socks5':
                return cls._handle_socks5_proxy(host, port, auth, module_name)
            else:
                # HTTP/HTTPS代理直接使用
                proxy_url = f"{proxy_type}://{auth}{host}:{port}"
                logger.info(f"✅ {module_name}使用{proxy_type.upper()}代理: {host}:{port}")
                return {
                    'http': proxy_url,
                    'https': proxy_url
                }

        except Exception as e:
            logger.error(f"❌ {module_name}代理配置处理失败: {e}")
            return None
    
    @classmethod
    def _handle_socks5_proxy(cls, host: str, port: str, auth: str, module_name: str) -> Optional[Dict[str, str]]:
        """处理SOCKS5代理"""
        # 策略1: 尝试转换为HTTP代理
        http_proxy = cls._try_socks5_to_http_conversion(host, port, auth, module_name)
        if http_proxy:
            return http_proxy
        
        # 策略2: 检查是否支持直接SOCKS5
        socks5_proxy = cls._try_direct_socks5(host, port, auth, module_name)
        if socks5_proxy:
            return socks5_proxy
        
        # 策略3: 都失败，跳过代理
        logger.warning(f"⚠️ {module_name}无法使用SOCKS5代理，跳过代理")
        return None
    
    @classmethod
    def _try_socks5_to_http_conversion(cls, host: str, port: str, auth: str, module_name: str) -> Optional[Dict[str, str]]:
        """尝试将SOCKS5转换为HTTP代理"""
        logger.info(f"🔄 {module_name}尝试转换SOCKS5代理为HTTP代理")

        # 生成要尝试的HTTP端口列表
        http_ports_to_try = cls._generate_http_ports(port)

        for http_port in http_ports_to_try:
            try:
                http_proxy = f"http://{auth}{host}:{http_port}"
                logger.info(f"🔧 {module_name}尝试HTTP代理: {host}:{http_port}")

                # 进行快速连通性测试
                if cls._test_proxy_connectivity(http_proxy, timeout=5):
                    logger.info(f"✅ {module_name}HTTP代理连通性测试成功: {host}:{http_port}")
                    return {
                        'http': http_proxy,
                        'https': http_proxy
                    }
                else:
                    logger.debug(f"🔍 {module_name}HTTP代理端口{http_port}连通性测试失败")
                    continue

            except Exception as e:
                logger.debug(f"🔍 {module_name}HTTP代理端口{http_port}转换失败: {e}")
                continue

        logger.warning(f"⚠️ {module_name}所有HTTP代理端口转换尝试都失败")
        return None

    @classmethod
    def get_pyrogram_proxy(cls, module_name: str = "Pyrogram") -> Optional[Dict[str, Any]]:
        """
        获取适用于Pyrogram/Pyrofork的代理配置

        Args:
            module_name: 调用模块名称

        Returns:
            Dict[str, Any]: Pyrogram格式的代理配置
            None: 无代理或代理不可用
        """
        parsed = cls._parse_proxy_config(module_name)
        if not parsed:
            return None

        try:
            proxy_type, host, port, username, password = parsed

            # 转换为Pyrogram需要的格式
            if proxy_type == 'socks5':
                proxy_dict = {
                    'scheme': 'socks5',
                    'hostname': host,
                    'port': int(port)
                }
                # 只有在有用户名密码时才添加认证信息
                if username and password:
                    proxy_dict['username'] = username
                    proxy_dict['password'] = password
                logger.info(f"✅ {module_name}使用SOCKS5代理: {host}:{port}")
                return proxy_dict
            elif proxy_type in ['http', 'https']:
                proxy_dict = {
                    'scheme': 'http',
                    'hostname': host,
                    'port': int(port)
                }
                # 只有在有用户名密码时才添加认证信息
                if username and password:
                    proxy_dict['username'] = username
                    proxy_dict['password'] = password
                logger.info(f"✅ {module_name}使用HTTP代理: {host}:{port}")
                return proxy_dict
            else:
                logger.warning(f"⚠️ {module_name}不支持的代理协议: {proxy_type}")
                return None

        except Exception as e:
            logger.error(f"❌ {module_name}代理配置处理失败: {e}")
            return None
    
    @classmethod
    def _try_direct_socks5(cls, host: str, port: str, auth: str, module_name: str) -> Optional[Dict[str, str]]:
        """尝试直接使用SOCKS5代理"""
        try:
            # 检查是否安装了requests[socks]
            import socks
            proxy_url = f"socks5://{auth}{host}:{port}"
            logger.info(f"✅ {module_name}使用SOCKS5代理: {host}:{port}")
            return {
                'http': proxy_url,
                'https': proxy_url
            }
        except ImportError:
            logger.debug(f"🔍 {module_name}未安装requests[socks]，无法直接使用SOCKS5")
            return None
    
    @classmethod
    def _generate_http_ports(cls, socks5_port: str) -> List[str]:
        """生成要尝试的HTTP代理端口列表"""
        ports = cls.HTTP_PORT_MAPPING.copy()
        
        # 添加SOCKS5端口+4的映射（常见映射规则）
        try:
            mapped_port = str(int(socks5_port) + 4)
            if mapped_port not in ports:
                ports.insert(1, mapped_port)  # 插入到第二位，优先级较高
        except ValueError:
            pass
        
        return ports

    @classmethod
    def _test_proxy_connectivity(cls, proxy_url: str, timeout: int = 5) -> bool:
        """快速测试代理连通性"""
        try:
            import requests
            import socket

            # 解析代理URL获取host和port
            if '://' in proxy_url:
                parts = proxy_url.split('://', 1)[1]
                if '@' in parts:
                    parts = parts.split('@', 1)[1]
                host_port = parts.split(':', 1)
                if len(host_port) == 2:
                    host = host_port[0]
                    port = int(host_port[1])

                    # 快速TCP连接测试
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, port))
                    sock.close()

                    return result == 0
            return False
        except Exception:
            return False

    @classmethod
    def get_ytdlp_proxy(cls, module_name: str = "yt-dlp") -> Optional[str]:
        """
        获取适用于yt-dlp的代理配置

        Args:
            module_name: 调用模块名称

        Returns:
            str: yt-dlp格式的代理URL
            None: 无代理或代理不可用
        """
        parsed = cls._parse_proxy_config(module_name)
        if not parsed:
            return None

        try:
            proxy_type, host, port, username, password = parsed
            auth = cls._build_auth_string(username, password)

            proxy_url = f"{proxy_type}://{auth}{host}:{port}"
            logger.info(f"✅ {module_name}使用代理: {proxy_type}://{host}:{port}")
            return proxy_url

        except Exception as e:
            logger.error(f"❌ {module_name}代理配置处理失败: {e}")
            return None
    
    @classmethod
    def get_pytubefix_proxy(cls, module_name: str = "PyTubeFix") -> Optional[str]:
        """
        获取适用于PyTubeFix的代理配置
        PyTubeFix不直接支持SOCKS5，需要转换为HTTP

        Args:
            module_name: 调用模块名称

        Returns:
            str: PyTubeFix格式的代理URL (HTTP)
            None: 无代理或代理不可用
        """
        parsed = cls._parse_proxy_config(module_name)
        if not parsed:
            return None

        try:
            proxy_type, host, port, username, password = parsed
            auth = cls._build_auth_string(username, password)

            # PyTubeFix只支持HTTP代理
            if proxy_type == 'socks5':
                # 尝试转换为HTTP代理
                return cls._convert_socks5_to_http_for_pytubefix(host, port, auth, module_name)
            else:
                # 已经是HTTP代理，直接使用
                proxy_url = f"http://{auth}{host}:{port}"
                logger.info(f"✅ {module_name}使用HTTP代理: {host}:{port}")
                return proxy_url

        except Exception as e:
            logger.error(f"❌ {module_name}代理配置处理失败: {e}")
            return None
    
    @classmethod
    def _convert_socks5_to_http_for_pytubefix(cls, host: str, port: str, auth: str, module_name: str) -> Optional[str]:
        """为PyTubeFix转换SOCKS5为HTTP代理"""
        # 复用通用的SOCKS5转换逻辑
        result = cls._try_socks5_to_http_conversion(host, port, auth, module_name)
        if result:
            # 返回单个URL而不是字典
            return result['http']

        logger.warning(f"⚠️ {module_name}无法找到可用的HTTP代理，尝试直连")
        return None

    @classmethod
    def get_pytubefix_socks5_config(cls, proxy_url: str, module_name: str = "PyTubeFix") -> Dict[str, Any]:
        """
        为PyTubeFix配置SOCKS5代理 - 统一的SOCKS5处理

        Args:
            proxy_url: 代理URL
            module_name: 调用模块名称

        Returns:
            Dict: PyTubeFix格式的代理配置
        """
        try:
            if not proxy_url:
                return {}

            logger.info(f"🔧 {module_name}配置SOCKS5代理: {proxy_url}")

            # 检查是否为SOCKS5代理
            if proxy_url.startswith('socks5://'):
                # SOCKS5代理需要特殊处理
                try:
                    # 尝试使用requests[socks]支持
                    import socks
                    import socket
                    from urllib.parse import urlparse

                    parsed = urlparse(proxy_url)
                    host = parsed.hostname
                    port = parsed.port or 1080
                    username = parsed.username
                    password = parsed.password

                    # 配置全局SOCKS5代理
                    socks.set_default_proxy(socks.SOCKS5, host, port, username=username or None, password=password or None)
                    socket.socket = socks.socksocket

                    logger.info(f"✅ {module_name}配置SOCKS5代理: {host}:{port}")
                    return {'_socks5_configured': True}

                except ImportError:
                    logger.warning(f"⚠️ {module_name}未安装PySocks，将使用直连模式")
                    return {}
                except Exception as e:
                    logger.error(f"❌ {module_name}SOCKS5代理配置失败: {e}")
                    return {}
            else:
                # HTTP代理直接使用
                return {'proxies': {'http': proxy_url, 'https': proxy_url}}

        except Exception as e:
            logger.error(f"❌ {module_name}代理配置解析失败: {e}")
            return {}

    @classmethod
    def test_proxy_connection(cls, proxy_config: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        """
        测试代理连接

        Args:
            proxy_config: 代理配置字典
            timeout: 超时时间（秒）

        Returns:
            Dict: 测试结果 {'success': bool, 'message': str, 'ip': str, 'response_time': str}
        """
        try:
            import requests
            import time

            # 使用统一的URL构建方法
            proxy_url = cls.build_proxy_url(proxy_config)

            # 验证端口
            try:
                port = int(proxy_config.get('port', 0))
                if not (1 <= port <= 65535):
                    raise ValueError("端口超出范围")
            except (ValueError, TypeError):
                return {
                    'success': False,
                    'message': "端口号必须是1-65535之间的数字",
                    'ip': '',
                    'response_time': ''
                }

            proxy_type = proxy_config.get('proxy_type', 'http')
            host = proxy_config.get('host', '').strip()

            logger.info(f"🔗 测试代理: {proxy_type}://{host}:{port}")

            # 测试代理连接
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }

            test_url = "http://httpbin.org/ip"
            start_time = time.time()

            response = requests.get(test_url, proxies=proxies, timeout=timeout)
            response_time = round((time.time() - start_time) * 1000)

            if response.status_code == 200:
                result = response.json()
                ip = result.get('origin', '未知')
                logger.info(f"✅ 代理测试成功: IP={ip}, 响应时间={response_time}ms")
                return {
                    'success': True,
                    'message': "代理连接测试成功",
                    'ip': ip,
                    'response_time': f"{response_time}ms"
                }
            else:
                logger.error(f"❌ 代理测试失败: 状态码={response.status_code}")
                return {
                    'success': False,
                    'message': f"代理测试失败，状态码: {response.status_code}",
                    'ip': '',
                    'response_time': ''
                }

        except requests.exceptions.Timeout:
            logger.error("❌ 代理连接超时")
            return {
                'success': False,
                'message': f"代理连接超时（{timeout}秒）",
                'ip': '',
                'response_time': ''
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ 代理连接错误: {e}")
            return {
                'success': False,
                'message': f"无法连接到代理服务器: {str(e)}",
                'ip': '',
                'response_time': ''
            }
        except requests.exceptions.ProxyError as e:
            logger.error(f"❌ 代理错误: {e}")
            return {
                'success': False,
                'message': f"代理服务器错误: {str(e)}",
                'ip': '',
                'response_time': ''
            }
        except Exception as e:
            logger.error(f"❌ 测试代理失败: {e}")
            return {
                'success': False,
                'message': f"代理测试失败: {str(e)}",
                'ip': '',
                'response_time': ''
            }

    @classmethod
    def build_proxy_url(cls, proxy_config: Dict[str, Any]) -> str:
        """
        构建代理URL

        Args:
            proxy_config: 代理配置字典

        Returns:
            str: 代理URL
        """
        proxy_type = proxy_config.get('proxy_type', 'http')
        host = proxy_config.get('host', '')
        port = proxy_config.get('port', '')
        username = proxy_config.get('username', '')
        password = proxy_config.get('password', '')

        # 使用统一的认证字符串构建方法
        auth = cls._build_auth_string(username, password)

        if auth:
            return f"{proxy_type}://{auth}{host}:{port}"
        else:
            return f"{proxy_type}://{host}:{port}"
