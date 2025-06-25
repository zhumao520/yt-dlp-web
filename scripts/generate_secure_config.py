#!/usr/bin/env python3
"""
安全配置生成器 - 为生产环境生成安全的配置
"""

import secrets
import string
import hashlib
import os
import yaml
from pathlib import Path

def generate_secret_key(length=64):
    """生成安全的密钥"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_password(length=16):
    """生成安全的密码"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    # 确保包含各种字符类型
    if not any(c.islower() for c in password):
        password = password[:-1] + secrets.choice(string.ascii_lowercase)
    if not any(c.isupper() for c in password):
        password = password[:-1] + secrets.choice(string.ascii_uppercase)
    if not any(c.isdigit() for c in password):
        password = password[:-1] + secrets.choice(string.digits)
    if not any(c in "!@#$%^&*" for c in password):
        password = password[:-1] + secrets.choice("!@#$%^&*")
    
    return password

def hash_password(password):
    """使用PBKDF2哈希密码"""
    salt = secrets.token_hex(32)
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}:{password_hash}"

def create_production_config():
    """创建生产环境配置"""
    
    print("🔐 生成安全的生产环境配置...")
    
    # 生成安全密钥和密码
    secret_key = generate_secret_key()
    admin_password = generate_password()
    
    # 生产环境配置
    config = {
        "app": {
            "name": "YT-DLP Web",
            "version": "2.0.0",
            "host": "0.0.0.0",
            "port": 8080,
            "debug": False,  # 生产环境必须为False
            "secret_key": secret_key
        },
        "database": {
            "url": "sqlite:///data/app.db",
            "echo": False  # 生产环境不输出SQL
        },
        "auth": {
            "session_timeout": 3600,  # 1小时，更安全
            "default_username": "admin",
            "default_password": admin_password,
            "require_password_change": True  # 强制首次登录修改密码
        },
        "downloader": {
            "output_dir": "data/downloads",
            "temp_dir": "data/temp",  # 使用相对路径
            "max_concurrent": 2,  # 保守设置
            "timeout": 300,
            "auto_cleanup": True,  # 生产环境启用清理
            "cleanup_interval": 1800,  # 30分钟
            "max_file_age": 43200,  # 12小时
            "file_retention_hours": 72,  # 3天
            "max_storage_mb": 2000,  # 2GB限制
            "keep_recent_files": 10
        },
        "security": {
            "max_upload_size": 100,  # 100MB限制
            "rate_limit": {
                "enabled": True,
                "requests_per_minute": 30,
                "requests_per_hour": 500
            },
            "allowed_domains": [
                "youtube.com", "youtu.be", "twitter.com", "x.com",
                "bilibili.com", "tiktok.com", "instagram.com"
            ]
        },
        "logging": {
            "level": "WARNING",  # 生产环境只记录警告和错误
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "data/logs/app.log",
            "max_size": 50485760,  # 50MB
            "backup_count": 10,
            "enable_access_log": False  # 减少日志量
        },
        "features": {
            "ai_analysis": False,
            "cloud_storage": False,
            "multi_user": False,
            "monitoring": True,  # 生产环境启用监控
            "plugins": False
        }
    }
    
    return config, admin_password

def create_docker_env():
    """创建Docker环境变量文件"""
    secret_key = generate_secret_key()
    admin_password = generate_password()
    
    env_content = f"""# 生产环境配置 - 请妥善保管此文件
# 生成时间: {os.popen('date').read().strip()}

# 基础配置
FLASK_ENV=production
SECRET_KEY={secret_key}

# 管理员账号 - 请在首次登录后修改
ADMIN_USERNAME=admin
ADMIN_PASSWORD={admin_password}

# 数据库配置
DATABASE_URL=sqlite:///data/app.db

# 下载配置
DOWNLOAD_DIR=data/downloads
MAX_CONCURRENT=2
CLEANUP_ENABLED=true

# 安全配置
SESSION_TIMEOUT=3600
MAX_UPLOAD_SIZE=104857600
RATE_LIMIT_ENABLED=true

# 日志配置
LOG_LEVEL=WARNING
LOG_FILE=data/logs/app.log

# 时区设置
TZ=Asia/Shanghai

# 调试配置（生产环境必须为0）
FLASK_DEBUG=0
PYTHONPATH=/app
"""
    
    return env_content, admin_password

def main():
    """主函数"""
    print("🚀 YT-DLP Web 生产环境配置生成器")
    print("=" * 50)
    
    # 创建配置目录
    config_dir = Path("production")
    config_dir.mkdir(exist_ok=True)
    
    # 生成配置文件
    config, config_password = create_production_config()
    
    # 保存配置文件
    config_file = config_dir / "config.yml"
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"✅ 生产环境配置已生成: {config_file}")
    
    # 生成Docker环境变量
    env_content, env_password = create_docker_env()
    
    env_file = config_dir / ".env.production"
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"✅ Docker环境变量已生成: {env_file}")
    
    # 生成安全说明
    security_notes = f"""
🔐 安全配置说明
================

📋 生成的配置文件:
- {config_file}: 主配置文件
- {env_file}: Docker环境变量

🔑 管理员账号信息:
- 用户名: admin
- 密码: {config_password}

⚠️ 重要安全提醒:
1. 请立即修改默认管理员密码
2. 妥善保管配置文件，不要提交到版本控制
3. 定期更新密钥和密码
4. 启用HTTPS（建议使用反向代理）
5. 配置防火墙限制访问

🚀 部署步骤:
1. 复制配置文件到生产环境
2. 设置正确的文件权限 (chmod 600)
3. 启动应用并测试
4. 首次登录后立即修改密码

📊 生产环境优化:
- 会话超时: 1小时
- 并发限制: 2个
- 文件保留: 3天
- 存储限制: 2GB
- 日志级别: WARNING
"""
    
    readme_file = config_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(security_notes)
    
    print(f"✅ 安全说明已生成: {readme_file}")
    
    print("\n" + "=" * 50)
    print("🎉 配置生成完成！")
    print(f"📁 配置文件位置: {config_dir.absolute()}")
    print(f"🔑 管理员密码: {config_password}")
    print("\n⚠️  请立即查看 README.md 了解安全配置说明")

if __name__ == "__main__":
    main()
