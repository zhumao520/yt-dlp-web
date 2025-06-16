# YT-DLP Web V2 - 轻量化Docker镜像
FROM python:3.11-slim

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

# 创建必要目录
RUN mkdir -p /app/downloads /app/data/downloads /app/data/logs /app/data/cookies

# 设置权限
RUN chmod +x main.py

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# 启动应用
CMD ["python", "main.py"]
