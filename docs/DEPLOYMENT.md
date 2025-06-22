# 部署指南

本文档详细介绍如何部署YT-DLP Web项目，包括Docker部署和本地部署两种方式。

## 🐳 Docker部署（推荐）

### 标准版部署

适用于大多数使用场景，轻量快速。

#### 1. 准备环境
```bash
# 创建项目目录
mkdir -p yt-dlp-web
cd yt-dlp-web

# 创建必要的子目录
mkdir -p {data,downloads,logs}
mkdir -p data/{cookies,downloads,logs}
```

#### 2. 下载配置文件
```bash
# 下载Docker Compose配置
wget https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/docker-compose.example.yml -O docker-compose.yml

# 下载应用配置文件
wget https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/config.yml -O config.yml
```

#### 3. 修改配置
```bash
# 编辑Docker Compose配置
nano docker-compose.yml
```

关键配置项：
```yaml
services:
  yt-dlp-web:
    image: ghcr.io/your-username/yt-dlp-web:latest
    container_name: yt-dlp-web
    restart: always
    ports:
      - "8080:8080"  # 修改外部端口
    environment:
      - SECRET_KEY=your-random-secret-key  # 修改密钥
      - ADMIN_USERNAME=admin               # 修改用户名
      - ADMIN_PASSWORD=your-password       # 修改密码
    volumes:
      - ./config.yml:/app/config.yml
      - ./data:/app/data
      - ./downloads:/app/downloads
      - ./logs:/app/logs
```

#### 4. 启动服务
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 检查状态
docker-compose ps
```

### WARP版部署

适用于需要突破地区限制的场景。

#### 1. 下载WARP版配置
```bash
wget https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/docker-compose-warp-template.yml -O docker-compose.yml
```

#### 2. 修改配置
```yaml
services:
  yt-dlp-web:
    image: ghcr.io/your-username/yt-dlp-web-warp:latest
    container_name: yt-dlp-web-warp
    restart: unless-stopped
    
    # WARP需要的特殊权限
    cap_add:
      - NET_ADMIN
    sysctls:
      - net.ipv4.ip_forward=1
      - net.ipv4.conf.all.src_valid_mark=1
      - net.ipv6.conf.all.disable_ipv6=0
      - net.ipv6.conf.all.forwarding=1
    
    ports:
      - "8090:8080"  # 修改外部端口
    
    environment:
      # 基础配置
      - SECRET_KEY=your-random-secret-key
      - ADMIN_USERNAME=admin
      - ADMIN_PASSWORD=your-password
      
      # WARP配置
      - ENABLE_WARP=true
      - WARP_PROXY_PORT=1080
      - WARP_LICENSE_KEY=  # 可选：WARP+许可证
    
    volumes:
      - ./config.yml:/app/config.yml
      - ./data:/app/data
      - ./downloads:/app/downloads
      - ./logs:/app/logs
      - ./warp:/var/lib/cloudflare-warp  # WARP数据持久化
```

#### 3. 启动WARP版
```bash
# 启动服务（需要特殊权限）
docker-compose up -d

# 等待WARP连接建立（约30-60秒）
docker-compose logs -f

# 验证WARP状态
docker exec yt-dlp-web-warp warp-cli status
```

## 💻 本地部署

### 系统要求
- Python 3.11+
- Node.js 18+ (用于PO Token生成)
- FFmpeg
- Git

### 1. 安装依赖

#### Ubuntu/Debian
```bash
# 更新包列表
sudo apt update

# 安装系统依赖
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm ffmpeg git

# 安装构建工具
sudo apt install -y build-essential python3-dev libssl-dev libffi-dev
```

#### CentOS/RHEL
```bash
# 安装EPEL仓库
sudo yum install -y epel-release

# 安装依赖
sudo yum install -y python3.11 python3-pip nodejs npm ffmpeg git gcc python3-devel openssl-devel libffi-devel
```

#### macOS
```bash
# 使用Homebrew安装
brew install python@3.11 node ffmpeg git
```

### 2. 克隆项目
```bash
# 克隆代码
git clone https://github.com/your-repo/yt-dlp-web.git
cd yt-dlp-web

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows
```

### 3. 安装Python依赖
```bash
# 升级pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

### 4. 配置应用
```bash
# 复制配置文件
cp config.yml.example config.yml

# 编辑配置
nano config.yml
```

### 5. 初始化数据库
```bash
# 创建数据目录
mkdir -p data/downloads data/logs data/cookies

# 运行应用（首次运行会自动初始化数据库）
python main.py
```

### 6. 启动服务
```bash
# 开发模式
python main.py

# 生产模式（使用Gunicorn）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 main:app
```

## 🔧 高级配置

### 反向代理配置

#### Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

#### Caddy
```caddy
your-domain.com {
    reverse_proxy localhost:8080
}
```

### SSL证书配置

#### 使用Let's Encrypt
```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo crontab -e
# 添加：0 12 * * * /usr/bin/certbot renew --quiet
```

### 系统服务配置

#### Systemd服务
```bash
# 创建服务文件
sudo nano /etc/systemd/system/yt-dlp-web.service
```

```ini
[Unit]
Description=YT-DLP Web Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/yt-dlp-web
Environment=PATH=/path/to/yt-dlp-web/venv/bin
ExecStart=/path/to/yt-dlp-web/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable yt-dlp-web
sudo systemctl start yt-dlp-web

# 查看状态
sudo systemctl status yt-dlp-web
```

## 🔍 验证部署

### 健康检查
```bash
# 检查服务状态
curl http://localhost:8080/api/health

# 预期响应
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### 功能测试
```bash
# 测试下载功能
curl -X POST http://localhost:8080/api/download \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### 日志检查
```bash
# Docker部署
docker-compose logs -f

# 本地部署
tail -f data/logs/app.log
```

## 🚨 故障排除

### 常见问题

1. **端口占用**
```bash
# 检查端口占用
sudo netstat -tlnp | grep :8080

# 修改端口配置
nano docker-compose.yml  # 或 config.yml
```

2. **权限问题**
```bash
# 修复目录权限
sudo chown -R $USER:$USER ./data ./downloads ./logs

# Docker权限问题
sudo usermod -aG docker $USER
```

3. **内存不足**
```bash
# 检查内存使用
free -h

# 调整并发数
nano config.yml
# downloader.max_concurrent: 1  # 降低并发数
```

4. **网络问题**
```bash
# 测试网络连接
curl -I https://www.youtube.com

# 配置代理
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
```

### 性能优化

1. **调整并发数**
```yaml
downloader:
  max_concurrent: 3  # 根据服务器性能调整
```

2. **配置清理策略**
```yaml
downloader:
  auto_cleanup: true
  file_retention_hours: 168  # 7天
  max_storage_mb: 5000      # 5GB
```

3. **使用SSD存储**
```bash
# 将下载目录挂载到SSD
mount /dev/sdb1 /path/to/downloads
```

---

📝 **注意**: 部署完成后，请立即修改默认密码并配置防火墙规则。
