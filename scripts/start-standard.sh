#!/bin/bash
# 标准版启动脚本

set -e

echo "🚀 启动 YT-DLP Web 标准版..."
echo "📋 版本: 标准版（无 WARP 支持）"
echo "🔧 功能: 标准下载 + 外部代理支持"

# 创建必要目录
mkdir -p /app/data/{downloads,logs,cookies}

# 启动应用
echo "🚀 启动主应用..."
exec python main.py
