# YT-DLP Web

🎬 **现代化的视频下载Web界面** - 基于yt-dlp的强大视频下载工具，提供简洁易用的Web界面

[![Docker](https://img.shields.io/badge/Docker-支持-blue?logo=docker)](https://hub.docker.com)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## ✨ 核心特色

### 🚀 **双引擎下载系统**
- **yt-dlp**: 主力引擎，支持1000+网站
- **PyTubeFix**: YouTube专用引擎，突破限制
- **智能切换**: 自动选择最佳下载策略
- **高成功率**: 多重备用方案确保下载成功

### 🎯 **强大功能**
- **多平台支持**: YouTube、Bilibili、Twitter等主流平台
- **质量选择**: 4K/1080p/720p/音频等多种格式
- **批量下载**: 支持播放列表和多URL同时下载
- **断点续传**: 网络中断自动恢复下载
- **实时进度**: Web界面实时显示下载状态

### 🤖 **Telegram集成**
- **即时通知**: 下载完成自动推送消息
- **文件上传**: 自动上传到Telegram频道
- **远程控制**: 通过Telegram机器人远程下载
- **双API支持**: Bot API + Pyrogram，适应不同需求

### 🌐 **WARP代理支持**
- **突破限制**: 绕过地区封锁和IP限制
- **提升成功率**: 解决YouTube等平台的访问问题
- **一键启用**: Docker镜像内置WARP支持
- **智能路由**: 自动选择最优代理路径

### 🧹 **智能管理**
- **自动清理**: 可配置的文件清理策略
- **存储监控**: 实时监控磁盘使用情况
- **历史记录**: 完整的下载历史和状态追踪
- **文件管理**: Web界面直接管理下载文件

## 🚀 快速开始

### 一键部署（推荐）

#### 标准版 - 适合大多数用户
```bash
# 创建项目目录
mkdir -p yt-dlp-web && cd yt-dlp-web

# 下载并启动
curl -fsSL https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/scripts/quick-start.sh | bash
```

#### WARP版 - 突破地区限制
```bash
# 创建项目目录
mkdir -p yt-dlp-web && cd yt-dlp-web

# 下载WARP版配置
curl -fsSL https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/docker-compose-warp-template.yml -o docker-compose.yml

# 修改配置（重要！）
nano docker-compose.yml
# 修改：密码、路径、端口等

# 启动服务
docker-compose up -d
```

#### 手动部署
```bash
# 1. 创建目录结构
mkdir -p yt-dlp-web/{config,data,downloads,logs}
cd yt-dlp-web

# 2. 下载配置文件
wget https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/docker-compose.example.yml -O docker-compose.yml
wget https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/config.yml -O config.yml

# 3. 修改配置
nano docker-compose.yml  # 修改端口、密码等
nano config.yml          # 修改应用配置

# 4. 启动服务
docker-compose up -d
```

### 🌐 访问应用
- **Web界面**: http://localhost:8080
- **默认账号**: admin / admin123
- **⚠️ 重要**: 首次登录后立即修改默认密码！

### 📊 验证部署
```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 健康检查
curl http://localhost:8080/api/health
```

## 📋 功能详解

### 下载功能
- **支持格式**: MP4、MP3、WEBM等多种格式
- **质量选择**: 自动检测可用质量，支持最高4K下载
- **字幕下载**: 自动下载字幕文件（如果可用）
- **元数据保存**: 保留视频标题、描述等信息

### Web界面
- **响应式设计**: 支持桌面和移动设备
- **实时更新**: 下载进度实时刷新
- **批量操作**: 支持多文件同时管理
- **设置面板**: 完整的配置管理界面

### API接口
```bash
# 创建下载任务
curl -X POST http://localhost:8080/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# 查询下载状态
curl http://localhost:8080/api/download/TASK_ID/status
```

## ⚙️ 配置说明

### 基础配置 (config.yml)
```yaml
app:
  host: "0.0.0.0"
  port: 8080
  debug: false

downloader:
  max_concurrent: 3          # 最大并发下载数
  auto_cleanup: true         # 自动清理
  file_retention_hours: 168  # 文件保留时间（小时）
  max_storage_mb: 5000      # 最大存储空间（MB）

telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```

### 环境变量
```bash
# 基础配置
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-password

# Telegram配置
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# WARP配置（WARP版）
ENABLE_WARP=true
WARP_PROXY_PORT=1080
```

## 🔧 故障排除

### 常见问题

**1. 下载失败**
```bash
# 检查日志
docker logs yt-dlp-web

# 常见原因：网络问题、地区限制、视频不可用
# 解决方案：使用WARP版本或配置代理
```

**2. FFmpeg错误**
```bash
# 确认FFmpeg已安装
docker exec yt-dlp-web ffmpeg -version

# 重新构建镜像（如果需要）
docker-compose down
docker-compose up -d --build
```

**3. 权限问题**
```bash
# 检查目录权限
ls -la ./data ./downloads

# 修复权限
sudo chown -R 1000:1000 ./data ./downloads
```

### 性能优化
- **并发数**: 根据服务器性能调整 `max_concurrent`
- **存储清理**: 合理设置 `file_retention_hours`
- **代理配置**: 使用WARP或自定义代理提升下载速度

## 🏗️ 项目架构

```
yt-dlp-web/
├── core/              # 核心模块
│   ├── app.py        # Flask应用
│   ├── config.py     # 配置管理
│   └── database.py   # 数据库操作
├── modules/          # 功能模块
│   ├── downloader/   # 下载引擎
│   ├── telegram/     # Telegram集成
│   └── warp/         # WARP代理
├── web/              # Web界面
│   ├── templates/    # HTML模板
│   └── static/       # 静态资源
└── api/              # API接口
```

## 📊 系统要求

### 最低要求
- **CPU**: 1核心
- **内存**: 512MB
- **存储**: 1GB可用空间
- **网络**: 稳定的互联网连接

### 推荐配置
- **CPU**: 2核心以上
- **内存**: 2GB以上
- **存储**: 10GB以上SSD
- **网络**: 100Mbps以上带宽

## 📚 完整文档

- 📖 [文档中心](docs/README.md) - 完整文档导航
- 🚀 [部署指南](docs/DEPLOYMENT.md) - 详细部署说明
- ⚙️ [配置说明](docs/CONFIGURATION.md) - 完整配置选项
- 🔌 [API文档](docs/API.md) - RESTful API接口
- 🔧 [故障排除](docs/TROUBLESHOOTING.md) - 问题解决方案

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

### 参与方式
- 🐛 **报告Bug**: [提交Issue](https://github.com/your-repo/yt-dlp-web/issues)
- 💡 **功能建议**: [参与讨论](https://github.com/your-repo/yt-dlp-web/discussions)
- 📝 **改进文档**: 编辑docs目录下的文档
- 🔧 **代码贡献**: 提交Pull Request

### 开发流程
1. 🍴 Fork本项目
2. 🌿 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 📝 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 📤 推送到分支 (`git push origin feature/AmazingFeature`)
5. 🔄 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

### 核心依赖
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [PyTubeFix](https://github.com/JuanBindez/pytubefix) - YouTube专用下载库
- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架
- [Cloudflare WARP](https://developers.cloudflare.com/warp-client/) - 网络加速服务

### 社区贡献
感谢所有为项目贡献代码、文档和建议的开发者和用户！

## 🔗 相关链接

- 🏠 [项目主页](https://github.com/your-repo/yt-dlp-web)
- 📦 [Docker镜像](https://hub.docker.com/r/your-username/yt-dlp-web)
- 📚 [完整文档](docs/README.md)
- 💬 [讨论区](https://github.com/your-repo/yt-dlp-web/discussions)
- 🐛 [问题报告](https://github.com/your-repo/yt-dlp-web/issues)

---

⭐ **如果这个项目对您有帮助，请给个Star支持一下！**

🚀 **立即开始**: `curl -fsSL https://raw.githubusercontent.com/your-repo/yt-dlp-web/main/scripts/quick-start.sh | bash`
