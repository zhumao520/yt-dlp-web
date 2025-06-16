# 部署指南

本文档详细说明了YT-DLP Web的各种部署方式和配置选项。

## 🐳 Docker部署（推荐）

### 快速启动

```bash
docker run -d \
  --name yt-dlp-web \
  -p 8080:8080 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/data:/app/data \
  -e SECRET_KEY=your-secret-key-here \
  ghcr.io/your-username/yt-dlp-web:latest
```

### Docker Compose部署

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  yt-dlp-web:
    image: ghcr.io/your-username/yt-dlp-web:latest
    container_name: yt-dlp-web
    ports:
      - "8080:8080"
    volumes:
      - ./downloads:/app/downloads
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - SECRET_KEY=your-secret-key-here
      - APP_HOST=0.0.0.0
      - APP_PORT=8080
      - DOWNLOAD_DIR=/app/downloads
      - TELEGRAM_BOT_TOKEN=your-bot-token
      - TELEGRAM_CHAT_ID=your-chat-id
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

启动服务：

```bash
docker-compose up -d
```

### 环境变量配置

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `SECRET_KEY` | Flask密钥 | - | ✅ |
| `APP_HOST` | 监听地址 | `0.0.0.0` | ❌ |
| `APP_PORT` | 监听端口 | `8080` | ❌ |
| `DATABASE_URL` | 数据库URL | `sqlite:///data/app.db` | ❌ |
| `DOWNLOAD_DIR` | 下载目录 | `/app/downloads` | ❌ |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - | ❌ |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | - | ❌ |

## 🖥️ 手动部署

### 系统要求

- Python 3.11+
- FFmpeg
- 2GB+ RAM
- 10GB+ 存储空间

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-username/yt-dlp-web.git
cd yt-dlp-web
```

2. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **安装FFmpeg**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# macOS
brew install ffmpeg

# Windows
# 下载FFmpeg并添加到PATH
```

5. **配置应用**
```bash
# 复制配置文件
cp config.example.yml config.yml

# 编辑配置
nano config.yml
```

6. **启动应用**
```bash
python main.py
```

### 生产部署

使用Gunicorn作为WSGI服务器：

```bash
# 安装Gunicorn
pip install gunicorn

# 启动服务
gunicorn -w 4 -b 0.0.0.0:8080 main:app
```

使用systemd管理服务：

```ini
# /etc/systemd/system/yt-dlp-web.service
[Unit]
Description=YT-DLP Web
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/yt-dlp-web
Environment=PATH=/path/to/yt-dlp-web/venv/bin
ExecStart=/path/to/yt-dlp-web/venv/bin/gunicorn -w 4 -b 0.0.0.0:8080 main:app
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl enable yt-dlp-web
sudo systemctl start yt-dlp-web
```

## 🌐 反向代理配置

### Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 静态文件直接服务
    location /static/ {
        alias /path/to/yt-dlp-web/web/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 下载文件服务
    location /downloads/ {
        alias /path/to/downloads/;
        add_header Content-Disposition "attachment";
    }
}
```

### Apache配置

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    
    ProxyPreserveHost On
    ProxyRequests Off
    
    ProxyPass /static/ !
    ProxyPass /downloads/ !
    ProxyPass / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/
    
    Alias /static/ /path/to/yt-dlp-web/web/static/
    Alias /downloads/ /path/to/downloads/

    <Directory "/path/to/yt-dlp-web/web/static/">
        Require all granted
    </Directory>
    
    <Directory "/path/to/downloads/">
        Require all granted
    </Directory>
</VirtualHost>
```

## 🔒 HTTPS配置

### 使用Let's Encrypt

```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo crontab -e
# 添加: 0 12 * * * /usr/bin/certbot renew --quiet
```

### 自签名证书

```bash
# 生成证书
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Nginx HTTPS配置
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # 其他配置...
}
```

## 📊 监控和日志

### 日志配置

应用日志位置：
- 应用日志: `/app/data/logs/app.log`
- 访问日志: 由反向代理记录
- 错误日志: 由反向代理记录

### 健康检查

```bash
# 检查应用状态
curl http://localhost:8080/api/health

# 检查系统资源
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/system/info
```

### 监控脚本

```bash
#!/bin/bash
# monitor.sh - 简单监控脚本

URL="http://localhost:8080/api/health"
TIMEOUT=10

if curl -f -s --max-time $TIMEOUT $URL > /dev/null; then
    echo "$(date): Service is healthy"
else
    echo "$(date): Service is down, restarting..."
    systemctl restart yt-dlp-web
fi
```

## 🔧 故障排除

### 常见问题

1. **端口被占用**
```bash
# 查看端口占用
sudo netstat -tlnp | grep :8080
# 或
sudo lsof -i :8080
```

2. **权限问题**
```bash
# 确保目录权限正确
sudo chown -R www-data:www-data /path/to/yt-dlp-web
sudo chmod -R 755 /path/to/yt-dlp-web
```

3. **FFmpeg未找到**
```bash
# 检查FFmpeg安装
which ffmpeg
ffmpeg -version
```

4. **Python依赖问题**
```bash
# 重新安装依赖
pip install --upgrade -r requirements.txt
```

### 日志分析

```bash
# 查看应用日志
tail -f /app/data/logs/app.log

# 查看Docker日志
docker logs -f yt-dlp-web

# 查看系统日志
journalctl -u yt-dlp-web -f
```

## 🚀 性能优化

### 系统优化

1. **增加文件描述符限制**
```bash
# /etc/security/limits.conf
* soft nofile 65536
* hard nofile 65536
```

2. **优化内核参数**
```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
```

3. **使用SSD存储**
- 将下载目录放在SSD上
- 使用高速网络存储

### 应用优化

1. **增加Worker数量**
```bash
# Gunicorn配置
gunicorn -w 8 -b 0.0.0.0:8080 main:app
```

2. **启用缓存**
```yaml
# config.yml
cache:
  enabled: true
  type: "redis"
  url: "redis://localhost:6379"
```

3. **数据库优化**
```bash
# 定期优化数据库
sqlite3 /app/data/app.db "VACUUM; ANALYZE;"
```

---

如需更多帮助，请查看项目Wiki或创建Issue。
