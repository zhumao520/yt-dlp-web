#!/bin/bash

# yt-dlp Web界面启动脚本
echo "🚀 启动 yt-dlp Web界面..."

# 处理环境变量文件
echo "🔧 处理环境变量配置..."
if [ -f "/app/.env" ]; then
    echo "✅ 发现 .env 文件"
    # 导出环境变量（过滤注释和空行）
    set -a
    source /app/.env 2>/dev/null || true
    set +a
elif [ -f "/app/.env.example" ]; then
    echo "⚠️ 未找到 .env 文件，使用 .env.example"
    cp /app/.env.example /app/.env
    set -a
    source /app/.env 2>/dev/null || true
    set +a
else
    echo "⚠️ 未找到环境变量文件，使用默认配置"
fi

# 设置默认环境变量（如果没有从 .env 文件中加载）
export ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
export ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
export SECRET_KEY=${SECRET_KEY:-dev-key-change-in-production}
export DOWNLOAD_FOLDER=${DOWNLOAD_FOLDER:-/app/downloads}
export YTDLP_NO_LAZY_EXTRACTORS=1
export YTDLP_IGNORE_EXTRACTOR_ERRORS=1

# 创建必要的目录并设置权限
echo "🔧 创建并设置目录权限..."
mkdir -p $DOWNLOAD_FOLDER
mkdir -p /app/config
mkdir -p /app/logs
mkdir -p /app/yt-dlp-cache

# 强制修复目录权限
echo "📁 下载目录: $DOWNLOAD_FOLDER"
echo "👤 当前用户: $(whoami)"
echo "🆔 用户ID: $(id)"

# 尝试多种方式修复权限
echo "🔧 修复目录权限..."
chmod 777 $DOWNLOAD_FOLDER 2>/dev/null || echo "⚠️ chmod 777 失败"
chmod 777 /app/config 2>/dev/null || echo "⚠️ chmod /app/config 失败"
chmod 777 /app/logs 2>/dev/null || echo "⚠️ chmod /app/logs 失败"
chmod 777 /app/yt-dlp-cache 2>/dev/null || echo "⚠️ chmod /app/yt-dlp-cache 失败"

# 以 root 用户运行，确保目录权限正确
if [ "$(id -u)" = "0" ]; then
    echo "🔧 以 root 身份确保目录权限..."
    # 现在以 root 用户运行，不需要 chown 到 ytdlp
    echo "✅ 以 root 用户运行，拥有完全权限"
else
    echo "⚠️ 非 root 用户运行，可能遇到权限问题"
fi

# 测试目录写入权限
echo "🧪 测试目录写入权限..."
if touch "$DOWNLOAD_FOLDER/test_write_permission" 2>/dev/null; then
    rm "$DOWNLOAD_FOLDER/test_write_permission" 2>/dev/null
    echo "✅ 下载目录权限验证成功: $DOWNLOAD_FOLDER"
else
    echo "⚠️ 下载目录写入权限测试失败"
    echo "📋 详细目录信息:"
    ls -la "$DOWNLOAD_FOLDER" 2>/dev/null || echo "无法列出目录内容"
    ls -la "$(dirname $DOWNLOAD_FOLDER)" 2>/dev/null || echo "无法列出父目录内容"

    # 尝试创建临时目录作为备用
    TEMP_DOWNLOAD_DIR="/tmp/downloads"
    echo "🔄 尝试使用临时下载目录: $TEMP_DOWNLOAD_DIR"
    mkdir -p "$TEMP_DOWNLOAD_DIR"
    chmod 777 "$TEMP_DOWNLOAD_DIR" 2>/dev/null
    if touch "$TEMP_DOWNLOAD_DIR/test_write_permission" 2>/dev/null; then
        rm "$TEMP_DOWNLOAD_DIR/test_write_permission" 2>/dev/null
        export DOWNLOAD_FOLDER="$TEMP_DOWNLOAD_DIR"
        echo "✅ 使用临时下载目录: $TEMP_DOWNLOAD_DIR"
    else
        echo "❌ 临时目录也无法写入，但继续启动..."
    fi
fi

# 设置Python路径
export PYTHONPATH="/app:$PYTHONPATH"

# 调试信息
echo "🔍 调试信息..."
echo "当前目录: $(pwd)"
echo "Python路径: $PYTHONPATH"
echo "目录内容:"
ls -la /app/
echo "yt_dlp目录内容:"
ls -la /app/yt_dlp/ | head -10

# 使用通用 yt-dlp 安装脚本
echo "🔧 安装和验证 yt-dlp..."
if [ -f "/app/scripts/ytdlp_installer.sh" ]; then
    source /app/scripts/ytdlp_installer.sh

    # 根据环境变量或文件存在情况选择模式
    if [ -d "/app/yt_dlp" ] && [ -f "/app/yt_dlp/__init__.py" ]; then
        # 本地模式：存在本地 yt_dlp 目录
        echo "🔍 检测到本地 yt_dlp 目录，使用本地模式"
        INSTALL_MODE="local"
    else
        # 构建时下载模式
        echo "🔍 使用构建时下载模式"
        INSTALL_MODE="build-time"
    fi

    if ! install_ytdlp "$INSTALL_MODE" "${YTDLP_VERSION:-latest}"; then
        echo "❌ yt-dlp 安装失败"
        exit 1
    fi

    if ! verify_installation; then
        echo "❌ yt-dlp 验证失败"
        exit 1
    fi
else
    echo "❌ yt-dlp 安装脚本不存在"
    exit 1
fi

# 启动Web应用
echo "🌐 启动Web服务器..."
cd /app

# 使用 gunicorn 启动（生产环境）
if command -v gunicorn &> /dev/null; then
    echo "使用 Gunicorn 启动..."
    gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 webapp.app:app
else
    echo "使用 Flask 开发服务器启动..."
    python3 -m webapp.server --host 0.0.0.0 --port 8080 --no-browser
fi
