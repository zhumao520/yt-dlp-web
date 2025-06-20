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
    
    # 常见的HTTP代理端口映射策略
    HTTP_PORT_MAPPING = [
        '1190',  # 用户提到的HTTP代理端口
        '8080',  # 常见HTTP代理端口
        '3128',  # Squid代理默认端口
        '1080',  # 有时SOCKS5和HTTP共用
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
    def get_requests_proxy(cls, module_name: str = "Unknown") -> Optional[Dict[str, str]]:
        """
        获取适用于requests库的代理配置
        
        Args:
            module_name: 调用模块名称，用于日志标识
            
        Returns:
            Dict[str, str]: requests库格式的代理配置 {'http': 'proxy_url', 'https': 'proxy_url'}
            None: 无代理或代理不可用
        """
        proxy_config = cls.get_proxy_config()
        if not proxy_config:
            return None
            
        try:
            proxy_type = proxy_config.get('proxy_type', 'http')
            host = proxy_config.get('host')
            port = proxy_config.get('port')
            username = proxy_config.get('username')
            password = proxy_config.get('password')
            
            if not host or not port:
                logger.warning(f"⚠️ {module_name}: 代理配置不完整")
                return None
            
            # 构建认证信息
            auth = ""
            if username and password:
                auth = f"{username}:{password}@"
            
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
                
                # 这里可以添加代理连通性测试（可选）
                # if cls._test_proxy_connectivity(http_proxy):
                #     return {'http': http_proxy, 'https': http_proxy}
                
                # 暂时直接返回，让调用方测试
                return {
                    'http': http_proxy,
                    'https': http_proxy
                }
            except Exception as e:
                logger.debug(f"🔍 {module_name}HTTP代理端口{http_port}转换失败: {e}")
                continue
        
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
    def get_ytdlp_proxy(cls, module_name: str = "yt-dlp") -> Optional[str]:
        """
        获取适用于yt-dlp的代理配置
        
        Args:
            module_name: 调用模块名称
            
        Returns:
            str: yt-dlp格式的代理URL
            None: 无代理或代理不可用
        """
        proxy_config = cls.get_proxy_config()
        if not proxy_config:
            return None
            
        try:
            proxy_type = proxy_config.get('proxy_type', 'http')
            host = proxy_config.get('host')
            port = proxy_config.get('port')
            username = proxy_config.get('username')
            password = proxy_config.get('password')
            
            if not host or not port:
                return None
            
            # 构建代理URL
            auth = ""
            if username and password:
                auth = f"{username}:{password}@"
            
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
        proxy_config = cls.get_proxy_config()
        if not proxy_config:
            return None
            
        try:
            proxy_type = proxy_config.get('proxy_type', 'http')
            host = proxy_config.get('host')
            port = proxy_config.get('port')
            username = proxy_config.get('username')
            password = proxy_config.get('password')
            
            if not host or not port:
                return None
            
            # 构建认证信息
            auth = ""
            if username and password:
                auth = f"{username}:{password}@"
            
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
        logger.info(f"🔄 {module_name}尝试转换SOCKS5代理为HTTP代理")
        
        http_ports_to_try = cls._generate_http_ports(port)
        
        # 返回第一个尝试的HTTP代理（PyTubeFix会自己测试连通性）
        for http_port in http_ports_to_try:
            try:
                http_proxy = f"http://{auth}{host}:{http_port}"
                logger.info(f"🔧 {module_name}尝试HTTP代理: {host}:{http_port}")
                return http_proxy
            except Exception:
                continue
        
        logger.warning(f"⚠️ {module_name}无法找到可用的HTTP代理，尝试直连")
        return None

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

            # 构建代理URL
            proxy_type = proxy_config.get('proxy_type', 'http')
            host = proxy_config.get('host', '').strip()
            port = proxy_config.get('port')
            username = proxy_config.get('username', '').strip()
            password = proxy_config.get('password', '').strip()

            # 验证端口
            try:
                port = int(port)
                if not (1 <= port <= 65535):
                    raise ValueError("端口超出范围")
            except (ValueError, TypeError):
                return {
                    'success': False,
                    'message': "端口号必须是1-65535之间的数字",
                    'ip': '',
                    'response_time': ''
                }

            # 构建代理URL
            proxy_url = f"{proxy_type}://"
            if username:
                proxy_url += username
                if password:
                    proxy_url += f":{password}"
                proxy_url += "@"
            proxy_url += f"{host}:{port}"

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

        proxy_url = f"{proxy_type}://"
        if username:
            proxy_url += username
            if password:
                proxy_url += f":{password}"
            proxy_url += "@"
        proxy_url += f"{host}:{port}"

        return proxy_url
