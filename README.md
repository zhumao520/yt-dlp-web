# YT-DLP Web

🚀 **现代化轻量级YouTube下载器Web界面** - 基于Flask的双引擎下载系统

[![Docker Build](https://github.com/your-username/yt-dlp-web/actions/workflows/docker-build.yml/badge.svg)](https://github.com/your-username/yt-dlp-web/actions/workflows/docker-build.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)

## 📋 项目简介

YT-DLP Web 是一个现代化的YouTube视频下载器Web界面，采用轻量化架构设计，支持1000+网站的视频下载。项目基于Flask框架，集成了双引擎下载系统、智能Telegram推送、现代化Web界面等功能。

## ✨ 核心功能

### 🎬 双引擎下载系统
- **yt-dlp引擎**: 支持1000+网站，功能强大
- **PyTubeFix引擎**: YouTube专用，速度优化
- **智能切换**: 自动选择最佳下载引擎
- **格式选择**: 支持多种视频/音频格式
- **质量控制**: 自定义分辨率和码率

### 🌐 现代化Web界面
- **响应式设计**: 支持桌面和移动设备
- **实时进度**: WebSocket实时下载进度
- **暗色主题**: 支持明暗主题切换
- **多语言**: 中文界面，易于使用
- **文件管理**: 在线预览和管理下载文件

### 📱 Telegram集成
- **智能推送**: 下载完成自动推送到Telegram
- **文件上传**: 支持大文件分片上传
- **命令控制**: 通过Telegram Bot远程下载
- **状态通知**: 实时下载状态推送
- **Webhook支持**: 支持Telegram Webhook模式

### 🔐 安全认证
- **JWT认证**: 现代化令牌认证系统
- **用户管理**: 支持多用户和权限控制
- **会话管理**: 安全的会话超时机制
- **API密钥**: 支持API密钥访问

### 🛠️ 系统管理
- **健康监控**: 实时系统健康状态
- **自动更新**: yt-dlp自动更新机制
- **日志管理**: 详细的操作日志
- **配置管理**: 灵活的配置系统

## 🏗️ 技术架构

### 后端技术栈
- **Flask 3.1+**: 轻量级Web框架
- **SQLite**: 嵌入式数据库
- **PyJWT**: JWT令牌认证
- **PyroFork**: 现代化Telegram客户端
- **aiohttp**: 异步HTTP客户端

### 前端技术栈
- **Bootstrap 5**: 现代化UI框架
- **JavaScript ES6+**: 原生JavaScript
- **WebSocket**: 实时通信
- **Plyr**: 视频播放器

### 下载引擎
- **yt-dlp**: 主要下载引擎
- **PyTubeFix**: YouTube专用引擎
- **FFmpeg**: 视频处理工具

## 🚀 快速开始

### Docker部署（推荐）

```bash
# 拉取镜像
docker pull ghcr.io/your-username/yt-dlp-web:latest

# 运行容器
docker run -d \
  --name yt-dlp-web \
  -p 8080:8080 \
  -v /path/to/downloads:/app/downloads \
  -v /path/to/data:/app/data \
  -e SECRET_KEY=your-secret-key \
  ghcr.io/your-username/yt-dlp-web:latest
```

### 手动部署

```bash
# 克隆项目
git clone https://github.com/your-username/yt-dlp-web.git
cd yt-dlp-web

# 安装依赖
pip install -r requirements.txt

# 启动应用
python main.py
```

## 📖 使用指南

### 基础使用
1. 访问 `http://localhost:8080`
2. 使用默认账号登录: `admin/admin123`
3. 在下载页面输入视频URL
4. 选择下载格式和质量
5. 点击下载按钮

### Telegram配置
1. 创建Telegram Bot并获取Token
2. 在设置页面配置Bot Token和Chat ID
3. 启用Telegram推送功能
4. 下载完成后自动推送到Telegram

### API使用
```bash
# 获取系统状态
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8080/api/health

# 创建下载任务
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=VIDEO_ID"}' \
  http://localhost:8080/api/download/create
```

## 🔧 配置说明

### 环境变量
```bash
SECRET_KEY=your-secret-key-here
APP_HOST=0.0.0.0
APP_PORT=8080
DATABASE_URL=sqlite:///data/app.db
DOWNLOAD_DIR=/app/downloads
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

### 配置文件
创建 `config.yml` 文件进行详细配置：

```yaml
app:
  name: "YT-DLP Web"
  host: "0.0.0.0"
  port: 8080
  debug: false

downloader:
  output_dir: "/app/downloads"
  max_concurrent: 3
  timeout: 300

telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  push_mode: "file"
```

## 📁 项目结构

```
yt-dlp-web/
├── api/                    # API接口
├── core/                   # 核心功能
├── modules/                # 功能模块
│   ├── auth/              # 认证模块
│   ├── downloader/        # 下载模块
│   ├── telegram/          # Telegram模块
│   ├── files/             # 文件管理
│   └── cookies/           # Cookie管理
├── web/                    # Web界面
│   ├── static/            # 静态文件
│   └── templates/         # 模板文件
├── scripts/                # 维护脚本
├── data/                   # 数据目录
├── main.py                 # 主程序
├── requirements.txt        # 依赖配置
└── Dockerfile             # Docker配置
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
- [PyTubeFix](https://github.com/JuanBindez/pytubefix) - YouTube专用下载库
- [PyroFork](https://github.com/Mayuri-Chan/pyrofork) - Telegram客户端库
- [Flask](https://flask.palletsprojects.com/) - 轻量级Web框架


⭐ 如果这个项目对您有帮助，请给个Star支持一下！
