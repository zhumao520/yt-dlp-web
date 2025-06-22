# 配置说明

本文档详细说明YT-DLP Web的所有配置选项，包括应用配置、下载配置、Telegram集成等。

## 📁 配置文件结构

```
yt-dlp-web/
├── config.yml              # 主配置文件
├── yt-dlp.conf             # yt-dlp配置文件（自动生成）
└── data/
    ├── cookies/            # Cookies文件目录
    │   ├── youtube.json    # YouTube OAuth2 cookies
    │   ├── youtube_oauth2.json
    │   └── twitter_auth.txt
    ├── downloads/          # 下载文件目录
    ├── logs/              # 日志文件目录
    │   └── app.log
    └── app.db             # SQLite数据库文件
```

## ⚙️ 主配置文件 (config.yml)

### 应用基础配置
```yaml
app:
  name: "YT-DLP Web"              # 应用名称
  version: "2.0.0"                # 版本号（自动设置）
  host: "0.0.0.0"                 # 监听地址
  port: 8080                      # 监听端口
  debug: false                    # 调试模式
  secret_key: "your-secret-key"   # 会话密钥（必须修改）
```

**重要说明**:
- `secret_key`: 用于会话加密，生产环境必须设置为随机字符串
- `debug`: 生产环境必须设为 `false`
- `host`: 设为 `0.0.0.0` 允许外部访问，`127.0.0.1` 仅本地访问

### 数据库配置
```yaml
database:
  url: "sqlite:///data/app.db"    # 数据库连接URL
  echo: false                     # 是否输出SQL语句（调试用）
```

**支持的数据库**:
- SQLite: `sqlite:///path/to/database.db`
- MySQL: `mysql://user:password@host:port/database`
- PostgreSQL: `postgresql://user:password@host:port/database`

### 认证配置
```yaml
auth:
  session_timeout: 86400          # 会话超时时间（秒）
  default_username: "admin"       # 默认管理员用户名
  default_password: "admin123"    # 默认管理员密码（首次启动后请修改）
  password_min_length: 8         # 密码最小长度
  max_login_attempts: 5          # 最大登录尝试次数
  lockout_duration: 300          # 账户锁定时间（秒）
```

### 下载器配置
```yaml
downloader:
  # 基础设置
  output_dir: "/app/downloads"     # 下载目录
  temp_dir: "/app/temp"           # 临时目录
  max_concurrent: 3               # 最大并发下载数
  timeout: 300                    # 下载超时时间（秒）
  
  # 默认下载选项
  default_quality: "best"         # 默认质量
  default_format: "mp4"          # 默认格式
  extract_audio: false           # 是否默认提取音频
  
  # 自动清理设置
  auto_cleanup: true             # 启用自动清理
  cleanup_interval: 3600         # 清理检查间隔（秒）
  file_retention_hours: 168      # 文件保留时间（小时，7天）
  max_storage_mb: 5000          # 最大存储空间（MB）
  keep_recent_files: 20         # 始终保留的最近文件数
  
  # 重试设置
  max_retries: 3                # 最大重试次数
  retry_delay: 5                # 重试延迟（秒）
  
  # 代理设置
  proxy: ""                     # HTTP代理 (http://host:port)
  socks_proxy: ""              # SOCKS代理 (socks5://host:port)
```

**质量选项**:
- `best`: 最佳质量
- `worst`: 最低质量
- `720p`, `1080p`, `1440p`, `2160p`: 指定分辨率
- `bestaudio`: 最佳音频
- `worstaudio`: 最低音频

**格式选项**:
- `mp4`: MP4格式（推荐）
- `webm`: WebM格式
- `mkv`: MKV格式
- `mp3`: MP3音频
- `m4a`: M4A音频
- `wav`: WAV音频

### Telegram集成配置
```yaml
telegram:
  # Bot API配置
  bot_token: ""                  # Telegram Bot Token
  chat_id: ""                   # 目标聊天ID
  
  # Pyrogram配置（可选，用于大文件上传）
  api_id: ""                    # Telegram API ID
  api_hash: ""                  # Telegram API Hash
  session_name: "yt_dlp_web"   # 会话名称
  
  # 上传设置
  auto_upload: false            # 自动上传下载完成的文件
  upload_method: "bot_api"      # 上传方式: bot_api 或 pyrogram
  file_size_limit: 50          # Bot API文件大小限制（MB）
  
  # 通知设置
  notify_start: true           # 下载开始通知
  notify_complete: true        # 下载完成通知
  notify_error: true          # 下载错误通知
  
  # 消息模板
  templates:
    start: "🚀 开始下载: {title}"
    complete: "✅ 下载完成: {title}\n📁 大小: {size}\n⏱️ 用时: {duration}"
    error: "❌ 下载失败: {title}\n🔍 错误: {error}"
```

### 日志配置
```yaml
logging:
  level: "INFO"                 # 日志级别: DEBUG, INFO, WARNING, ERROR
  file: "data/logs/app.log"    # 日志文件路径
  max_size: 10485760           # 单个日志文件最大大小（字节）
  backup_count: 5              # 保留的日志文件数量
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 安全配置
```yaml
security:
  # CORS设置
  cors_origins: ["*"]          # 允许的跨域来源
  cors_methods: ["GET", "POST", "PUT", "DELETE"]
  
  # 文件上传限制
  max_file_size: 16777216000   # 最大文件大小（16GB）
  allowed_extensions: [".mp4", ".mp3", ".webm", ".mkv"]
  
  # API限制
  rate_limit: 100              # 每分钟API请求限制
  
  # 安全头部
  security_headers:
    x_frame_options: "DENY"
    x_content_type_options: "nosniff"
    x_xss_protection: "1; mode=block"
```

## 🌐 环境变量配置

环境变量会覆盖配置文件中的对应设置：

### 基础环境变量
```bash
# 应用配置
SECRET_KEY=your-random-secret-key
FLASK_ENV=production
FLASK_DEBUG=0

# 服务器配置
HOST=0.0.0.0
PORT=8080

# 管理员账号
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password

# 数据库
DATABASE_URL=sqlite:///data/app.db
```

### 下载器环境变量
```bash
# 下载设置
DOWNLOAD_DIR=/app/downloads
MAX_CONCURRENT=3
DEFAULT_QUALITY=best

# 清理设置
AUTO_CLEANUP=true
FILE_RETENTION_HOURS=168
MAX_STORAGE_MB=5000

# 代理设置
HTTP_PROXY=http://proxy:8080
HTTPS_PROXY=http://proxy:8080
SOCKS_PROXY=socks5://proxy:1080
```

### Telegram环境变量
```bash
# Bot配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# API配置
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# 上传设置
TELEGRAM_AUTO_UPLOAD=true
TELEGRAM_UPLOAD_METHOD=bot_api
```

### WARP环境变量（WARP版）
```bash
# WARP配置
ENABLE_WARP=true
WARP_PROXY_PORT=1080
WARP_LICENSE_KEY=your_warp_plus_key

# 网络配置
WARP_ENDPOINT=auto
WARP_MTU=1280
```

## 🔧 高级配置

### yt-dlp配置文件
系统会自动生成 `yt-dlp.conf` 文件，您也可以手动编辑：

```conf
# 输出模板
-o "/app/downloads/%(title)s.%(ext)s"

# 质量选择
-f "best[height<=1080]"

# 字幕下载
--write-subs
--write-auto-subs
--sub-langs "zh,en"

# 元数据
--write-info-json
--write-thumbnail

# 代理设置（如果需要）
--proxy "socks5://127.0.0.1:1080"

# FFmpeg路径
--ffmpeg-location "/usr/bin/ffmpeg"
```

### Cookies配置
为了访问需要登录的内容，可以配置Cookies：

1. **导出Cookies**:
   - 使用浏览器插件导出Cookies
   - 保存为Netscape格式

2. **放置Cookies文件**:
   ```
   data/cookies/
   ├── youtube.json         # YouTube OAuth2 cookies (JSON格式)
   ├── youtube_oauth2.json  # YouTube OAuth2 备用
   ├── twitter_auth.txt     # Twitter认证信息
   └── bilibili.txt         # Bilibili Cookies (如需要)
   ```

3. **配置使用**:
   ```yaml
   downloader:
     use_cookies: true
     cookies_dir: "data/cookies"
     # 系统会自动检测和使用cookies文件
   ```

### 代理配置
支持多种代理方式：

#### HTTP代理
```yaml
downloader:
  proxy: "http://username:password@proxy.example.com:8080"
```

#### SOCKS代理
```yaml
downloader:
  socks_proxy: "socks5://username:password@proxy.example.com:1080"
```

#### 代理链
```yaml
downloader:
  proxy_chain:
    - "http://proxy1:8080"
    - "socks5://proxy2:1080"
```

### 性能优化配置
```yaml
downloader:
  # 并发设置
  max_concurrent: 3              # 根据CPU核心数调整
  max_connections_per_download: 4 # 每个下载的最大连接数
  
  # 缓冲设置
  buffer_size: 8192             # 缓冲区大小（字节）
  chunk_size: 1048576          # 分块大小（字节）
  
  # 超时设置
  connect_timeout: 30          # 连接超时
  read_timeout: 300           # 读取超时
  
  # 重试设置
  max_retries: 3
  retry_delay: 5
  exponential_backoff: true   # 指数退避
```

## 📊 监控配置
```yaml
monitoring:
  # 健康检查
  health_check_interval: 30    # 健康检查间隔（秒）
  
  # 性能监控
  enable_metrics: true         # 启用性能指标
  metrics_retention: 86400     # 指标保留时间（秒）
  
  # 告警设置
  alerts:
    disk_usage_threshold: 90   # 磁盘使用率告警阈值（%）
    memory_usage_threshold: 85 # 内存使用率告警阈值（%）
    failed_downloads_threshold: 10 # 失败下载数告警阈值
```

## 🔍 配置验证

### 验证配置文件
```bash
# 检查配置语法
python -c "import yaml; yaml.safe_load(open('config.yml'))"

# 验证配置完整性
python main.py --validate-config
```

### 测试配置
```bash
# 测试数据库连接
python -c "from core.database import get_database; db = get_database(); print('数据库连接成功')"

# 测试Telegram配置
python -c "from modules.telegram import test_connection; test_connection()"

# 测试下载功能
curl -X POST http://localhost:8080/api/download/test
```

## 🚨 配置安全建议

1. **密钥安全**:
   - 使用强随机密钥
   - 定期更换密钥
   - 不要在代码中硬编码密钥

2. **权限控制**:
   - 限制配置文件访问权限
   - 使用专用用户运行服务
   - 定期审查访问日志

3. **网络安全**:
   - 使用HTTPS
   - 配置防火墙
   - 限制API访问频率

4. **数据保护**:
   - 定期备份配置
   - 加密敏感数据
   - 监控异常访问

---

📝 **注意**: 修改配置后需要重启服务才能生效。建议在测试环境中验证配置后再应用到生产环境。
