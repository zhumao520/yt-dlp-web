# YT-DLP Web - 轻量化Docker镜像
FROM python:3.11-slim

# 构建参数 - 决定是否安装 WARP
ARG INSTALL_WARP=false

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_ENV=production

# 安装系统依赖 (包含 TgCrypto 编译所需的依赖)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    ffmpeg \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 设置容器环境标识
ENV DOCKER_CONTAINER=1

# 复制依赖文件
COPY requirements.txt .

# 升级pip和安装构建工具
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 设置pip配置以提高兼容性
ENV PIP_USE_PEP517=1
ENV PIP_NO_BUILD_ISOLATION=0

# 安装依赖包
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 根据构建参数决定是否安装 WARP
RUN if [ "$INSTALL_WARP" = "true" ]; then \
        echo "🌐 构建时安装 WARP..." && \
        # 安装 WARP 相关依赖 \
        apt-get update && apt-get install -y \
            gnupg \
            lsb-release \
            iptables \
            iproute2 \
            procps \
            net-tools && \
        # 安装 Cloudflare WARP \
        curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg && \
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflare-main $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-main.list && \
        apt-get update && \
        apt-get install -y cloudflare-warp && \
        # 安装 GOST 代理 \
        curl -L https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz | gunzip > /usr/local/bin/gost && \
        chmod +x /usr/local/bin/gost && \
        # 复制启动脚本 \
        cp modules/warp/start-with-warp.sh /start-app.sh && \
        chmod +x /start-app.sh && \
        # 设置 WARP 可用标识 \
        echo "true" > /warp-available && \
        # 清理 \
        rm -rf /var/lib/apt/lists/* && \
        echo "✅ WARP 安装完成"; \
    else \
        echo "ℹ️ 跳过 WARP 安装" && \
        # 复制标准启动脚本 \
        cp scripts/start-standard.sh /start-app.sh && \
        chmod +x /start-app.sh && \
        # 设置 WARP 不可用标识 \
        echo "false" > /warp-available; \
    fi

# 创建必要目录
RUN mkdir -p /app/downloads /app/data/downloads /app/data/logs /app/data/cookies

# 设置权限
RUN chmod +x main.py

# 暴露端口
EXPOSE 8080

# 健康检查（WARP版需要更长的启动时间）
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动应用
CMD ["/start-app.sh"]
