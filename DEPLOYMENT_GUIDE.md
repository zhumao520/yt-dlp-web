# YT-DLP Web 部署指南

## 📋 部署前准备

### 系统要求
- **操作系统**: Linux/Windows/macOS
- **Docker**: 版本 20.10+
- **Docker Compose**: 版本 2.0+
- **内存**: 最少 512MB，推荐 1GB+
- **存储**: 最少 2GB 可用空间

### 检查系统环境
```bash
# 检查 Docker 版本
docker --version

# 检查 Docker Compose 版本
docker compose version
```

## 🚀 快速部署

### 方法一：使用部署脚本（推荐）

1. **下载部署文件**
```bash
# 下载必要文件到部署目录
mkdir yt-dlp-web-deploy && cd yt-dlp-web-deploy
# 将 docker-compose.yml, .env.example, deploy.sh 复制到此目录
```

2. **配置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

3. **运行部署脚本**
```bash
# 给脚本执行权限
chmod +x deploy.sh

# 启动服务
./deploy.sh start
```

### 方法二：手动部署

1. **创建目录结构**
```bash
mkdir -p data/{downloads,database,logs,temp,cookies}
mkdir -p config
```

2. **配置环境变量**
```bash
# 创建 .env 文件
cat > .env << EOF
SECRET_KEY=your-secret-key-change-in-production-environment
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
MAX_CONCURRENT=3
TZ=Asia/Shanghai
EOF
```

3. **启动服务**
```bash
docker compose up -d
```

## ⚙️ 配置说明

### 必需配置
| 环境变量 | 说明 | 默认值 | 示例 |
|---------|------|--------|------|
| `SECRET_KEY` | 应用密钥（必须修改） | - | `your-secret-key-here` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` | `your-secure-password` |

### 可选配置
| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `MAX_CONCURRENT` | 最大并发下载数 | `3` |
| `TZ` | 时区设置 | `Asia/Shanghai` |
| `TELEGRAM_BOT_TOKEN` | Telegram机器人Token | - |
| `TELEGRAM_CHAT_ID` | Telegram聊天ID | - |

### 端口配置
- **Web界面**: `http://localhost:8090`
- **API接口**: `http://localhost:8090/api`
- **健康检查**: `http://localhost:8090/api/health`

## 📁 目录结构

```
yt-dlp-web-deploy/
├── docker-compose.yml      # Docker Compose 配置
├── .env                   # 环境变量配置
├── deploy.sh              # 部署脚本
├── data/                  # 数据目录
│   ├── downloads/         # 下载文件存储
│   ├── database/          # 数据库文件
│   ├── logs/             # 日志文件
│   ├── temp/             # 临时文件
│   └── cookies/          # Cookie文件
└── config/               # 配置文件目录
```

## 🔧 管理命令

### 使用部署脚本
```bash
./deploy.sh start      # 启动服务
./deploy.sh stop       # 停止服务
./deploy.sh restart    # 重启服务
./deploy.sh update     # 更新服务
./deploy.sh logs       # 查看日志
./deploy.sh status     # 查看状态
./deploy.sh backup     # 备份数据
```

### 使用 Docker Compose
```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 查看日志
docker compose logs -f

# 查看状态
docker compose ps

# 更新镜像
docker compose pull && docker compose up -d
```

## 🔍 故障排除

### 常见问题

1. **端口被占用**
```bash
# 检查端口占用
netstat -tlnp | grep 8090

# 修改端口映射
# 在 docker-compose.yml 中修改 ports: "8091:8080"
```

2. **权限问题**
```bash
# 修复目录权限
sudo chown -R $USER:$USER data/
chmod -R 755 data/
```

3. **服务无法启动**
```bash
# 查看详细日志
docker compose logs yt-dlp-web

# 检查配置文件
docker compose config
```

4. **内存不足**
```bash
# 检查系统资源
free -h
df -h

# 调整资源限制（在 docker-compose.yml 中）
```

### 健康检查
```bash
# 检查服务健康状态
curl http://localhost:8090/api/health

# 预期返回
{"status": "healthy", "timestamp": "..."}
```

## 🔒 安全建议

1. **修改默认密码**
   - 必须修改 `SECRET_KEY`
   - 修改管理员密码

2. **网络安全**
   - 使用反向代理（Nginx/Traefik）
   - 启用 HTTPS
   - 限制访问IP

3. **数据备份**
   - 定期备份 `data` 目录
   - 使用 `./deploy.sh backup` 命令

## 📊 监控和维护

### 日志管理
```bash
# 查看实时日志
./deploy.sh logs

# 查看特定时间的日志
docker compose logs --since="2024-01-01T00:00:00" yt-dlp-web
```

### 资源监控
```bash
# 查看资源使用
./deploy.sh status

# 详细监控
docker stats yt-dlp-web
```

### 定期维护
```bash
# 清理无用镜像
docker image prune -f

# 清理无用容器
docker container prune -f

# 更新服务
./deploy.sh update
```

## 🆙 升级指南

1. **备份数据**
```bash
./deploy.sh backup
```

2. **更新服务**
```bash
./deploy.sh update
```

3. **验证服务**
```bash
./deploy.sh status
curl http://localhost:8090/api/health
```

## 📞 技术支持

如果遇到问题，请：
1. 查看日志文件
2. 检查配置文件
3. 参考故障排除部分
4. 提交 GitHub Issue
