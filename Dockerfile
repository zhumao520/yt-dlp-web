# YT-DLP Web - 轻量化Docker镜像
FROM python:3.11-slim

# 构建参数 - 决定是否安装 WARP
ARG INSTALL_WARP=false
ARG TARGETPLATFORM
ARG GOST_VERSION=2.11.5
ARG WARP_VERSION=none

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
    gnupg \
    lsb-release \
    ca-certificates \
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

# 安装 WARP 相关依赖（如果需要）
RUN if [ "$INSTALL_WARP" = "true" ]; then \
        echo "🌐 安装 WARP 运行时依赖..." && \
        apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
            iptables \
            iproute2 \
            procps \
            net-tools && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# 安装 Cloudflare WARP（如果需要）
RUN if [ "$INSTALL_WARP" = "true" ] && [ "$WARP_VERSION" != "none" ]; then \
        echo "🔑 安装 Cloudflare WARP v${WARP_VERSION}..." && \
        echo "🏗️ 构建平台: ${TARGETPLATFORM}" && \
        # 检测架构 \
        case ${TARGETPLATFORM} in \
            "linux/amd64") export ARCH="amd64" ;; \
            "linux/arm64") export ARCH="arm64" ;; \
            *) echo "❌ 不支持的平台: ${TARGETPLATFORM}" && exit 1 ;; \
        esac && \
        echo "🔍 使用架构: ${ARCH}" && \
        # 使用预先验证的版本信息安装 \
        curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
        echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ bullseye main" > /etc/apt/sources.list.d/cloudflare-client.list && \
        apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends cloudflare-warp=${WARP_VERSION}* && \
        rm -rf /var/lib/apt/lists/* && \
        echo "✅ WARP v${WARP_VERSION} 安装完成"; \
    elif [ "$INSTALL_WARP" = "true" ]; then \
        echo "⚠️ WARP 版本信息不可用，跳过安装"; \
    fi

# 安装 GOST 代理（如果需要）
RUN if [ "$INSTALL_WARP" = "true" ] && [ "$GOST_VERSION" != "none" ]; then \
        echo "📡 安装 GOST 代理 v${GOST_VERSION}..." && \
        # 使用 TARGETPLATFORM 进行架构检测 \
        case ${TARGETPLATFORM} in \
            "linux/amd64") export ARCH="amd64" ;; \
            "linux/arm64") export ARCH="arm64" ;; \
            *) echo "❌ 不支持的平台: ${TARGETPLATFORM}" && exit 1 ;; \
        esac && \
        echo "🔍 构建平台: ${TARGETPLATFORM}，使用 GOST ${ARCH} v${GOST_VERSION}" && \
        # 简单下载 GOST，失败则使用备用版本 \
        curl -fsSL -o /tmp/gost.tar.gz "https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost_${GOST_VERSION}_linux_${ARCH}.tar.gz" || \
        curl -fsSL -o /tmp/gost.tar.gz "https://github.com/ginuerzh/gost/releases/download/v2.12.0/gost_2.12.0_linux_${ARCH}.tar.gz" && \
        echo "✅ GOST 下载成功" && \
        cd /tmp && \
        tar -xzf gost.tar.gz && \
        GOST_BINARY=$(find . -name "gost" -type f -executable | head -1) && \
        if [ -n "$GOST_BINARY" ]; then \
            mv "$GOST_BINARY" /usr/local/bin/gost && \
            chmod +x /usr/local/bin/gost && \
            echo "✅ GOST 安装到 /usr/local/bin/gost"; \
        else \
            echo "❌ 未找到 gost 可执行文件" && exit 1; \
        fi && \
        rm -rf /tmp/gost* && \
        echo "✅ GOST v${GOST_VERSION} 代理安装完成"; \
    elif [ "$INSTALL_WARP" = "true" ]; then \
        echo "⚠️ GOST 版本信息不可用，跳过安装"; \
    fi

# 配置启动脚本
RUN if [ "$INSTALL_WARP" = "true" ]; then \
        echo "🚀 配置 WARP 启动脚本..." && \
        cp modules/warp/start-with-warp.sh /start-app.sh && \
        chmod +x /start-app.sh && \
        echo "true" > /warp-available && \
        echo "✅ WARP 版本配置完成"; \
    else \
        echo "ℹ️ 配置标准启动脚本..." && \
        cp scripts/start-standard.sh /start-app.sh && \
        chmod +x /start-app.sh && \
        echo "false" > /warp-available && \
        echo "✅ 标准版配置完成"; \
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
