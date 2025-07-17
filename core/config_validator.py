# -*- coding: utf-8 -*-
"""
配置验证和修复模块
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
    
    def validate_and_fix(self) -> Tuple[bool, List[str], List[str]]:
        """验证配置并尝试修复问题"""
        self.issues = []
        self.fixes_applied = []
        
        logger.info("🔍 开始配置验证...")
        
        # 验证必要目录
        self._check_directories()
        
        # 验证配置文件
        self._check_config_files()
        
        # 验证数据库
        self._check_database()
        
        # 验证密钥
        self._check_secret_key()
        
        # 验证下载目录权限
        self._check_download_permissions()
        
        success = len(self.issues) == 0
        
        if success:
            logger.info("✅ 配置验证通过")
        else:
            logger.warning(f"⚠️ 发现 {len(self.issues)} 个配置问题")
            for issue in self.issues:
                logger.warning(f"   - {issue}")
        
        if self.fixes_applied:
            logger.info(f"🔧 应用了 {len(self.fixes_applied)} 个修复")
            for fix in self.fixes_applied:
                logger.info(f"   + {fix}")
        
        return success, self.issues, self.fixes_applied
    
    def _check_directories(self):
        """检查必要目录"""
        required_dirs = [
            "data",
            "data/downloads", 
            "data/logs",
            "data/cookies"
        ]
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    self.fixes_applied.append(f"创建目录: {dir_path}")
                except Exception as e:
                    self.issues.append(f"无法创建目录 {dir_path}: {e}")
    
    def _check_config_files(self):
        """检查配置文件"""
        config_file = Path("config.yml")
        example_file = Path("config.example.yml")
        
        if not config_file.exists():
            if example_file.exists():
                try:
                    import shutil
                    shutil.copy2(example_file, config_file)
                    self.fixes_applied.append("从示例文件创建配置文件")
                except Exception as e:
                    self.issues.append(f"无法创建配置文件: {e}")
            else:
                self.issues.append("配置文件和示例文件都不存在")
    
    def _check_database(self):
        """检查数据库"""
        try:
            from .database import get_database
            db = get_database()
            
            # 测试数据库连接
            db.execute_query('SELECT 1')
            
            # 检查管理员用户
            users = db.execute_query('SELECT COUNT(*) as count FROM users WHERE is_admin = 1')
            if not users or users[0]['count'] == 0:
                # 尝试创建管理员用户
                if db.ensure_admin_user_exists():
                    self.fixes_applied.append("创建默认管理员用户")
                else:
                    self.issues.append("无法创建管理员用户")
                    
        except Exception as e:
            self.issues.append(f"数据库检查失败: {e}")
    
    def _check_secret_key(self):
        """检查密钥配置"""
        try:
            from .config import get_config
            secret_key = get_config('app.secret_key')
            
            if not secret_key or secret_key == 'change-this-secret-key-in-production':
                # 生成新的密钥
                import secrets
                import string
                new_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
                
                # 更新配置
                from .config import set_config
                set_config('app.secret_key', new_key)
                self.fixes_applied.append("生成新的安全密钥")
                
        except Exception as e:
            self.issues.append(f"密钥检查失败: {e}")
    
    def _check_download_permissions(self):
        """检查下载目录权限"""
        try:
            from .config import get_config
            download_dir = Path(get_config('downloader.output_dir', 'data/downloads'))
            
            if not download_dir.exists():
                download_dir.mkdir(parents=True, exist_ok=True)
                self.fixes_applied.append(f"创建下载目录: {download_dir}")
            
            # 测试写入权限
            test_file = download_dir / '.permission_test'
            try:
                test_file.write_text('test')
                test_file.unlink()
            except Exception as e:
                self.issues.append(f"下载目录无写入权限: {e}")
                
        except Exception as e:
            self.issues.append(f"下载目录检查失败: {e}")





# 便捷函数
def validate_and_fix_config() -> Tuple[bool, List[str], List[str]]:
    """验证并修复配置"""
    validator = ConfigValidator()
    return validator.validate_and_fix()

def optimize_system() -> List[str]:
    """优化系统 - 使用统一的系统优化器"""
    try:
        from scripts.system_optimizer import SystemOptimizer
        optimizer = SystemOptimizer()
        result = optimizer.run_optimization()
        return result.get('optimizations', [])
    except Exception as e:
        logger.error(f"❌ 系统优化失败: {e}")
        return []
