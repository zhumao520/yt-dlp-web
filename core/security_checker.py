#!/usr/bin/env python3
"""
安全检查器 - 启动时检查安全配置
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple
from .config import get_config

logger = logging.getLogger(__name__)

class SecurityChecker:
    """安全配置检查器"""
    
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.is_production = os.environ.get('FLASK_ENV') == 'production'
    
    def check_all(self) -> Tuple[bool, List[str], List[str]]:
        """执行所有安全检查"""
        logger.info("🔍 开始安全配置检查...")
        
        # 检查密钥安全性
        self._check_secret_key()
        
        # 检查默认密码
        self._check_default_passwords()
        
        # 检查调试模式
        self._check_debug_mode()
        
        # 检查文件权限
        self._check_file_permissions()
        
        # 检查路径配置
        self._check_path_configuration()
        
        # 检查会话配置
        self._check_session_configuration()
        
        # 检查日志配置
        self._check_logging_configuration()
        
        # 检查资源限制
        self._check_resource_limits()
        
        # 汇总结果
        has_errors = len(self.errors) > 0
        
        if has_errors:
            logger.error(f"❌ 发现 {len(self.errors)} 个安全错误")
            for error in self.errors:
                logger.error(f"   - {error}")
        
        if self.warnings:
            logger.warning(f"⚠️ 发现 {len(self.warnings)} 个安全警告")
            for warning in self.warnings:
                logger.warning(f"   - {warning}")
        
        if not has_errors and not self.warnings:
            logger.info("✅ 安全配置检查通过")
        
        return not has_errors, self.errors, self.warnings
    
    def _check_secret_key(self):
        """检查密钥安全性"""
        secret_key = get_config('app.secret_key')
        
        if not secret_key:
            self.errors.append("SECRET_KEY 未设置")
            return
        
        # 检查是否为默认值
        default_keys = [
            'change-this-secret-key-in-production',
            'dev-secret-key',
            'secret-key',
            'your-secret-key'
        ]
        
        if secret_key in default_keys:
            if self.is_production:
                self.errors.append("生产环境使用默认 SECRET_KEY")
            else:
                self.warnings.append("使用默认 SECRET_KEY")
        
        # 检查密钥强度
        if len(secret_key) < 32:
            self.warnings.append("SECRET_KEY 长度不足32位")
        
        # 检查密钥复杂度
        if secret_key.isalnum():
            self.warnings.append("SECRET_KEY 缺少特殊字符")
    
    def _check_default_passwords(self):
        """检查默认密码"""
        default_password = get_config('auth.default_password')
        
        weak_passwords = [
            'admin', 'admin123', 'password', '123456',
            'admin@123', 'root', 'test', 'demo'
        ]
        
        if default_password in weak_passwords:
            if self.is_production:
                self.errors.append("生产环境使用弱默认密码")
            else:
                self.warnings.append("使用弱默认密码")
    
    def _check_debug_mode(self):
        """检查调试模式"""
        debug_mode = get_config('app.debug', False)
        flask_debug = os.environ.get('FLASK_DEBUG', '0') != '0'
        
        if self.is_production and (debug_mode or flask_debug):
            self.errors.append("生产环境启用了调试模式")
        elif debug_mode or flask_debug:
            self.warnings.append("调试模式已启用")
    
    def _check_file_permissions(self):
        """检查文件权限"""
        sensitive_files = [
            'config.yml',
            '.env',
            '.env.production',
            'data/app.db'
        ]
        
        for file_path in sensitive_files:
            path = Path(file_path)
            if path.exists():
                # 检查文件权限（Unix系统）
                if hasattr(os, 'stat'):
                    try:
                        stat_info = path.stat()
                        mode = stat_info.st_mode
                        
                        # 检查是否对其他用户可读
                        if mode & 0o044:  # 其他用户可读
                            self.warnings.append(f"文件 {file_path} 对其他用户可读")
                        
                        # 检查是否对其他用户可写
                        if mode & 0o022:  # 其他用户可写
                            self.errors.append(f"文件 {file_path} 对其他用户可写")
                    except Exception:
                        pass
    
    def _check_path_configuration(self):
        """检查路径配置"""
        # 检查是否使用绝对路径
        paths_to_check = [
            ('downloader.output_dir', get_config('downloader.output_dir')),
            ('downloader.temp_dir', get_config('downloader.temp_dir')),
            ('logging.file', get_config('logging.file'))
        ]
        
        for config_key, path_value in paths_to_check:
            if path_value and os.path.isabs(path_value):
                # 检查是否为硬编码的系统路径
                system_paths = ['/tmp', '/var/tmp', '/app']
                if any(path_value.startswith(sp) for sp in system_paths):
                    self.warnings.append(f"{config_key} 使用硬编码系统路径: {path_value}")
    
    def _check_session_configuration(self):
        """检查会话配置"""
        session_timeout = get_config('auth.session_timeout', 86400)
        
        # 生产环境会话超时不应超过4小时
        if self.is_production and session_timeout > 14400:
            self.warnings.append(f"生产环境会话超时过长: {session_timeout}秒")
        
        # 会话超时不应超过24小时
        if session_timeout > 86400:
            self.warnings.append(f"会话超时过长: {session_timeout}秒")
    
    def _check_logging_configuration(self):
        """检查日志配置"""
        log_level = get_config('logging.level', 'INFO')
        
        # 生产环境不应使用DEBUG级别
        if self.is_production and log_level == 'DEBUG':
            self.warnings.append("生产环境使用DEBUG日志级别")
        
        # 检查日志文件路径
        log_file = get_config('logging.file')
        if log_file:
            log_path = Path(log_file)
            if not log_path.parent.exists():
                self.warnings.append(f"日志目录不存在: {log_path.parent}")
    
    def _check_resource_limits(self):
        """检查资源限制"""
        max_concurrent = get_config('downloader.max_concurrent', 3)
        
        # 检查并发数是否合理
        if max_concurrent > 10:
            self.warnings.append(f"并发下载数过高: {max_concurrent}")
        
        # 检查存储限制
        max_storage = get_config('downloader.max_storage_mb', 5000)
        if max_storage > 10000:  # 10GB
            self.warnings.append(f"存储限制过高: {max_storage}MB")
    
    def get_security_recommendations(self) -> List[str]:
        """获取安全建议"""
        recommendations = []
        
        if self.is_production:
            recommendations.extend([
                "使用HTTPS（建议配置反向代理）",
                "配置防火墙限制访问端口",
                "定期更新密钥和密码",
                "启用访问日志监控",
                "配置自动备份",
                "使用专用数据库用户",
                "启用速率限制",
                "配置监控和告警"
            ])
        else:
            recommendations.extend([
                "开发环境也应使用强密码",
                "不要在版本控制中提交敏感配置",
                "定期检查依赖包安全更新"
            ])
        
        return recommendations

def check_security_on_startup() -> bool:
    """启动时执行安全检查"""
    try:
        checker = SecurityChecker()
        is_secure, errors, warnings = checker.check_all()
        
        if not is_secure:
            logger.error("❌ 安全检查失败，应用可能存在安全风险")
            
            # 在生产环境中，安全错误应该阻止启动
            if checker.is_production:
                logger.error("🚨 生产环境安全检查失败，拒绝启动")
                return False
        
        # 显示安全建议
        recommendations = checker.get_security_recommendations()
        if recommendations:
            logger.info("💡 安全建议:")
            for rec in recommendations:
                logger.info(f"   - {rec}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 安全检查异常: {e}")
        return False
