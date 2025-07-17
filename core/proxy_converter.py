"""
统一的代理管理工具
整合了代理转换和配置助手功能
统一处理各种代理类型的转换和配置
"""

import logging
import threading
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ProxyConverter:
    """代理转换工具类"""

    # 类级别的转换器缓存，避免重复创建
    _converter_cache = {}  # {socks5_url: http_proxy_url}
    _converter_lock = threading.Lock()
    

    
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
        # 使用协议转换器将 SOCKS5 转换为 HTTP 代理
        http_proxy = cls._try_socks5_to_http_conversion(host, port, auth, module_name)
        if http_proxy:
            return http_proxy

        # 转换失败，跳过代理
        logger.warning(f"⚠️ {module_name}SOCKS5 协议转换失败，跳过代理")
        return None
    
    @classmethod
    def _try_socks5_to_http_conversion(cls, host: str, port: str, auth: str, module_name: str) -> Optional[Dict[str, str]]:
        """将 SOCKS5 转换为 HTTP 代理 - 支持缓存复用"""
        socks5_url = f"socks5://{auth}{host}:{port}"

        # 检查缓存
        with cls._converter_lock:
            if socks5_url in cls._converter_cache:
                cached_proxy = cls._converter_cache[socks5_url]
                # 测试缓存的代理是否仍然可用
                if cls._test_http_proxy(cached_proxy):
                    logger.info(f"♻️ {module_name}复用现有转换器: {cached_proxy}")
                    return {
                        'http': cached_proxy,
                        'https': cached_proxy
                    }
                else:
                    # 缓存的代理不可用，移除
                    del cls._converter_cache[socks5_url]
                    logger.warning(f"⚠️ {module_name}缓存的转换器已失效，重新创建")

        logger.info(f"🔄 {module_name}尝试转换 SOCKS5 代理为 HTTP 代理")

        try:
            # 使用 Python 实现的协议转换器
            result = cls._start_python_socks_converter(host, port, auth, module_name)

            # 缓存成功的转换结果
            if result:
                with cls._converter_lock:
                    cls._converter_cache[socks5_url] = result['http']
                    logger.debug(f"💾 {module_name}缓存转换器: {result['http']}")

            return result

        except Exception as e:
            logger.warning(f"⚠️ {module_name}协议转换失败: {e}")
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
    def get_pyrogram_http_proxy(cls, module_name: str = "Pyrogram") -> Optional[Dict[str, Any]]:
        """
        获取适用于Pyrogram/Pyrofork的HTTP代理配置
        使用代理转换器将SOCKS5转换为HTTP代理

        Args:
            module_name: 调用模块名称

        Returns:
            Dict[str, Any]: Pyrogram格式的HTTP代理配置
            None: 无代理或代理不可用
        """
        try:
            # 获取转换后的HTTP代理
            http_proxy = cls.get_requests_proxy(module_name)
            if not http_proxy:
                logger.debug(f"🔍 {module_name}无HTTP代理可用")
                return None

            # 解析HTTP代理URL
            http_url = http_proxy.get('http', '')
            if not http_url:
                logger.debug(f"🔍 {module_name}HTTP代理URL为空")
                return None

            # 解析URL格式: http://host:port 或 http://username:password@host:port
            import re
            match = re.match(r'http://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)', http_url)
            if not match:
                logger.warning(f"⚠️ {module_name}无法解析HTTP代理URL: {http_url}")
                return None

            username, password, hostname, port = match.groups()

            # 构建Pyrogram格式的代理配置
            proxy_dict = {
                'scheme': 'http',
                'hostname': hostname,
                'port': int(port)
            }

            # 添加认证信息（如果有）
            if username and password:
                proxy_dict['username'] = username
                proxy_dict['password'] = password

            logger.info(f"✅ {module_name}使用HTTP代理转换器: {hostname}:{port}")
            return proxy_dict

        except Exception as e:
            logger.error(f"❌ {module_name}HTTP代理配置转换失败: {e}")
            return None

    @classmethod
    def _start_python_socks_converter(cls, host: str, port: str, auth: str, module_name: str) -> Optional[Dict[str, str]]:
        """使用 Python 实现 SOCKS5 到 HTTP 的协议转换"""
        import threading
        import socket
        import time

        try:
            # 寻找可用的本地端口
            local_port = cls._find_free_port()
            if not local_port:
                logger.error(f"❌ {module_name}无法找到可用的本地端口")
                return None

            logger.info(f"🚀 {module_name}启动 Python SOCKS5→HTTP 转换器: 127.0.0.1:{local_port} -> socks5://{host}:{port}")

            # 启动转换服务器
            converter = cls._create_socks_to_http_server(host, int(port), local_port, module_name)
            if not converter:
                return None

            # 等待服务器启动
            time.sleep(1)

            # 测试转换后的 HTTP 代理
            if cls._test_http_proxy(f"http://127.0.0.1:{local_port}"):
                logger.info(f"✅ {module_name}Python 转换器成功，HTTP 代理可用: 127.0.0.1:{local_port}")

                return {
                    'http': f"http://127.0.0.1:{local_port}",
                    'https': f"http://127.0.0.1:{local_port}"
                }
            else:
                logger.error(f"❌ {module_name}Python 转换器的 HTTP 代理不可用")
                return None

        except Exception as e:
            logger.error(f"❌ {module_name}Python 转换器启动异常: {e}")
            return None

    @classmethod
    def _create_socks_to_http_server(cls, socks_host: str, socks_port: int, local_port: int, module_name: str):
        """创建 SOCKS5 到 HTTP 的转换服务器"""
        import threading
        import socket
        import struct
        import select

        def handle_http_request(client_socket, socks_host, socks_port):
            """处理 HTTP 请求并通过 SOCKS5 转发"""
            try:
                # 接收 HTTP 请求
                request = client_socket.recv(4096).decode('utf-8', errors='ignore')
                if not request:
                    return

                # 解析 HTTP 请求
                lines = request.split('\r\n')
                if not lines:
                    return

                first_line = lines[0]
                method, url, version = first_line.split(' ', 2)

                # 解析目标地址
                if method == 'CONNECT':
                    # HTTPS 请求
                    host, port = url.split(':')
                    port = int(port)
                else:
                    # HTTP 请求，从 Host 头获取地址
                    host = None
                    port = 80
                    for line in lines[1:]:
                        if line.lower().startswith('host:'):
                            host_header = line.split(':', 1)[1].strip()
                            if ':' in host_header:
                                host, port_str = host_header.split(':', 1)
                                port = int(port_str)
                            else:
                                host = host_header
                            break

                    if not host:
                        client_socket.close()
                        return

                # 连接到 SOCKS5 代理
                socks_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socks_socket.settimeout(10)
                socks_socket.connect((socks_host, socks_port))

                # SOCKS5 握手
                # 发送认证方法
                socks_socket.send(b'\x05\x01\x00')  # SOCKS5, 1 method, no auth
                response = socks_socket.recv(2)
                if response != b'\x05\x00':
                    socks_socket.close()
                    client_socket.close()
                    return

                # 发送连接请求
                # SOCKS5 连接请求格式: VER CMD RSV ATYP DST.ADDR DST.PORT
                host_bytes = host.encode('utf-8')
                request_data = struct.pack('!BBBB', 0x05, 0x01, 0x00, 0x03)  # SOCKS5, CONNECT, RSV, DOMAINNAME
                request_data += struct.pack('!B', len(host_bytes)) + host_bytes
                request_data += struct.pack('!H', port)

                socks_socket.send(request_data)
                response = socks_socket.recv(10)

                if len(response) < 2 or response[1] != 0x00:
                    socks_socket.close()
                    client_socket.close()
                    return

                # 连接成功
                if method == 'CONNECT':
                    # HTTPS: 发送 200 Connection Established
                    client_socket.send(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                else:
                    # HTTP: 转发请求
                    socks_socket.send(request.encode('utf-8'))

                # 双向数据转发
                cls._relay_data(client_socket, socks_socket)

            except Exception as e:
                logger.debug(f"🔍 {module_name}HTTP 请求处理异常: {e}")
            finally:
                try:
                    client_socket.close()
                except:
                    pass
                try:
                    socks_socket.close()
                except:
                    pass

        def server_thread():
            """服务器线程"""
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('127.0.0.1', local_port))
                server_socket.listen(5)

                logger.debug(f"🔧 {module_name}转换服务器监听 127.0.0.1:{local_port}")

                while True:
                    try:
                        client_socket, addr = server_socket.accept()
                        # 为每个连接创建新线程
                        client_thread = threading.Thread(
                            target=handle_http_request,
                            args=(client_socket, socks_host, socks_port),
                            daemon=True
                        )
                        client_thread.start()
                    except Exception as e:
                        logger.debug(f"🔍 {module_name}接受连接异常: {e}")
                        break

            except Exception as e:
                logger.error(f"❌ {module_name}转换服务器异常: {e}")

        # 启动服务器线程
        thread = threading.Thread(target=server_thread, daemon=True)
        thread.start()

        return thread

    @classmethod
    def _relay_data(cls, socket1, socket2):
        """双向数据转发"""
        import select

        try:
            while True:
                ready, _, _ = select.select([socket1, socket2], [], [], 1.0)
                if not ready:
                    continue

                for sock in ready:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            return

                        if sock is socket1:
                            socket2.send(data)
                        else:
                            socket1.send(data)
                    except:
                        return
        except:
            pass

    @classmethod
    def _find_free_port(cls) -> Optional[int]:
        """寻找可用的本地端口"""
        import socket

        # 尝试一些常用的端口范围
        for port in range(18080, 18100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        return None

    @classmethod
    def _test_http_proxy(cls, proxy_url: str) -> bool:
        """测试 HTTP 代理是否可用"""
        try:
            import requests

            # 使用代理访问一个简单的测试 URL
            response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=10
            )
            return response.status_code == 200

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
    def get_telegram_proxy(cls, module_name: str = "Telegram") -> Optional[Dict[str, Any]]:
        """
        获取适用于Telegram的代理配置

        Args:
            module_name: 调用模块名称

        Returns:
            Dict: Telegram格式的代理配置
            None: 无代理或代理不可用
        """
        # 复用 Pyrogram 代理配置，因为 Telegram 使用相同的格式
        return cls.get_pyrogram_proxy(module_name)

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


class ProxyHelper:
    """代理配置助手 - 提供统一的代理获取接口（整合自原 proxy_helper.py）"""

    @staticmethod
    def get_ytdlp_proxy(module_name: str = "Unknown") -> Optional[str]:
        """
        获取适用于yt-dlp的代理配置

        Args:
            module_name: 调用模块名称，用于日志标识

        Returns:
            str: yt-dlp格式的代理URL
            None: 无代理或代理不可用
        """
        try:
            return ProxyConverter.get_ytdlp_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取yt-dlp代理配置失败: {e}")
            return None

    @staticmethod
    def get_pytubefix_proxy(module_name: str = "Unknown") -> Optional[str]:
        """
        获取适用于PyTubeFix的代理配置

        Args:
            module_name: 调用模块名称，用于日志标识

        Returns:
            str: PyTubeFix格式的代理URL
            None: 无代理或代理不可用
        """
        try:
            return ProxyConverter.get_pytubefix_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取PyTubeFix代理配置失败: {e}")
            return None

    @staticmethod
    def get_telegram_proxy(module_name: str = "Unknown") -> Optional[Dict[str, Any]]:
        """
        获取适用于Telegram的代理配置

        Args:
            module_name: 调用模块名称，用于日志标识

        Returns:
            Dict: Telegram格式的代理配置
            None: 无代理或代理不可用
        """
        try:
            return ProxyConverter.get_telegram_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取Telegram代理配置失败: {e}")
            return None

    @staticmethod
    def get_requests_proxy(module_name: str = "Unknown") -> Optional[Dict[str, str]]:
        """
        获取适用于requests库的代理配置

        Args:
            module_name: 调用模块名称，用于日志标识

        Returns:
            Dict: requests格式的代理配置
            None: 无代理或代理不可用
        """
        try:
            return ProxyConverter.get_requests_proxy(module_name)
        except Exception as e:
            logger.debug(f"🔍 {module_name}获取requests代理配置失败: {e}")
            return None

    @staticmethod
    def is_proxy_enabled() -> bool:
        """检查代理是否启用"""
        try:
            proxy_config = ProxyConverter.get_proxy_config()
            return proxy_config is not None
        except Exception as e:
            logger.debug(f"🔍 检查代理状态失败: {e}")
            return False

    @staticmethod
    def get_proxy_status() -> Dict[str, Any]:
        """获取代理状态信息"""
        try:
            proxy_config = ProxyConverter.get_proxy_config()
            if not proxy_config:
                return {
                    'enabled': False,
                    'type': None,
                    'host': None,
                    'port': None,
                    'status': 'disabled'
                }

            return {
                'enabled': True,
                'type': proxy_config.get('proxy_type', 'unknown'),
                'host': proxy_config.get('host', 'unknown'),
                'port': proxy_config.get('port', 'unknown'),
                'status': 'enabled'
            }
        except Exception as e:
            logger.debug(f"🔍 获取代理状态失败: {e}")
            return {
                'enabled': False,
                'type': None,
                'host': None,
                'port': None,
                'status': 'error'
            }


# 向后兼容的便捷函数
def get_ytdlp_proxy(module_name: str = "Unknown") -> Optional[str]:
    """便捷函数：获取yt-dlp代理配置"""
    return ProxyHelper.get_ytdlp_proxy(module_name)

def get_pytubefix_proxy(module_name: str = "Unknown") -> Optional[str]:
    """便捷函数：获取PyTubeFix代理配置"""
    return ProxyHelper.get_pytubefix_proxy(module_name)

def get_telegram_proxy(module_name: str = "Unknown") -> Optional[Dict[str, Any]]:
    """便捷函数：获取Telegram代理配置"""
    return ProxyHelper.get_telegram_proxy(module_name)

def get_requests_proxy(module_name: str = "Unknown") -> Optional[Dict[str, str]]:
    """便捷函数：获取requests代理配置"""
    return ProxyHelper.get_requests_proxy(module_name)

def is_proxy_enabled() -> bool:
    """便捷函数：检查代理是否启用"""
    return ProxyHelper.is_proxy_enabled()

def get_proxy_status() -> Dict[str, Any]:
    """便捷函数：获取代理状态"""
    return ProxyHelper.get_proxy_status()

def get_proxy_converter() -> ProxyConverter:
    """便捷函数：获取代理转换器实例"""
    return ProxyConverter()
