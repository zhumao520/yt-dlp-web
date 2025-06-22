# 故障排除指南

本文档提供常见问题的解决方案和调试方法，帮助您快速解决使用过程中遇到的问题。

## 🔍 快速诊断

### 系统健康检查
```bash
# 检查服务状态
curl http://localhost:8080/api/health

# 预期响应
{
  "status": "healthy",
  "version": "2.0.0",
  "components": {
    "database": "ok",
    "downloader": "ok",
    "telegram": "ok"
  }
}
```

### 查看日志
```bash
# Docker部署
docker-compose logs -f yt-dlp-web

# 本地部署
tail -f data/logs/app.log

# 查看特定时间段的日志
grep "2024-01-01 10:" data/logs/app.log
```

## 🚨 常见问题

### 1. 服务无法启动

#### 问题：端口被占用
```bash
# 检查端口占用
sudo netstat -tlnp | grep :8080
# 或
sudo lsof -i :8080
```

**解决方案**:
```bash
# 方案1：杀死占用进程
sudo kill -9 <PID>

# 方案2：修改端口
nano config.yml
# 修改 app.port: 8081

# 方案3：Docker修改端口映射
nano docker-compose.yml
# 修改 ports: "8081:8080"
```

#### 问题：权限不足
```bash
# 错误信息
Permission denied: '/app/data'
```

**解决方案**:
```bash
# 修复目录权限
sudo chown -R $USER:$USER ./data ./downloads ./logs

# Docker权限问题
sudo usermod -aG docker $USER
newgrp docker

# 检查SELinux（CentOS/RHEL）
sudo setsebool -P container_manage_cgroup on
```

#### 问题：依赖缺失
```bash
# 错误信息
ModuleNotFoundError: No module named 'xxx'
```

**解决方案**:
```bash
# 重新安装依赖
pip install -r requirements.txt

# Docker重新构建
docker-compose down
docker-compose up -d --build
```

### 2. 下载问题

#### 问题：下载失败 - 网络错误
```bash
# 错误信息
ERROR: Unable to download webpage: HTTP Error 403: Forbidden
```

**解决方案**:
```bash
# 1. 检查网络连接
curl -I https://www.youtube.com

# 2. 使用代理
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080

# 3. 使用WARP版本
docker-compose -f docker-compose-warp.yml up -d

# 4. 更新yt-dlp
pip install --upgrade yt-dlp
```

#### 问题：下载失败 - 地区限制
```bash
# 错误信息
ERROR: Video unavailable in your country
```

**解决方案**:
```bash
# 1. 使用WARP版本
docker run -d --name yt-dlp-web-warp \
  --cap-add=NET_ADMIN \
  -p 8080:8080 \
  -e ENABLE_WARP=true \
  your-image:warp

# 2. 配置代理
nano config.yml
# downloader:
#   proxy: "socks5://proxy:1080"

# 3. 使用VPN
```

#### 问题：FFmpeg错误
```bash
# 错误信息
ERROR: ffmpeg not found
```

**解决方案**:
```bash
# 检查FFmpeg安装
ffmpeg -version

# Ubuntu/Debian安装
sudo apt update && sudo apt install ffmpeg

# CentOS/RHEL安装
sudo yum install epel-release
sudo yum install ffmpeg

# Docker检查
docker exec yt-dlp-web ffmpeg -version

# 如果缺失，重新构建镜像
docker-compose down
docker-compose up -d --build
```

#### 问题：YouTube特定错误
```bash
# 错误信息
ERROR: Sign in to confirm your age
```

**解决方案**:
```bash
# 1. 使用Cookies
# 导出浏览器Cookies到 data/cookies/youtube.txt

# 2. 使用PyTubeFix引擎
# 在下载选项中选择PyTubeFix

# 3. 更新PO Token
# 系统会自动尝试生成新的PO Token
```

### 3. Telegram集成问题

#### 问题：Bot无法发送消息
```bash
# 错误信息
Telegram API error: Unauthorized
```

**解决方案**:
```bash
# 1. 检查Bot Token
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"

# 2. 检查Chat ID
# 发送消息给Bot，然后访问：
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates"

# 3. 检查Bot权限
# 确保Bot在群组中有发送消息权限
```

#### 问题：文件上传失败
```bash
# 错误信息
File too large for Bot API
```

**解决方案**:
```bash
# 1. 使用Pyrogram上传大文件
nano config.yml
# telegram:
#   upload_method: "pyrogram"
#   api_id: "your_api_id"
#   api_hash: "your_api_hash"

# 2. 压缩文件
# 系统会自动尝试压缩大文件

# 3. 分割上传
# 对于超大文件，系统会自动分割
```

### 4. 存储问题

#### 问题：磁盘空间不足
```bash
# 错误信息
No space left on device
```

**解决方案**:
```bash
# 1. 检查磁盘使用
df -h

# 2. 清理下载文件
rm -rf downloads/*

# 3. 启用自动清理
nano config.yml
# downloader:
#   auto_cleanup: true
#   file_retention_hours: 72

# 4. 手动清理
curl -X POST http://localhost:8080/api/system/cleanup \
  -H "Authorization: Bearer <token>" \
  -d '{"clean_downloads": true}'
```

#### 问题：文件权限错误
```bash
# 错误信息
Permission denied: '/app/downloads/video.mp4'
```

**解决方案**:
```bash
# 检查文件权限
ls -la downloads/

# 修复权限
sudo chown -R www-data:www-data downloads/
sudo chmod -R 755 downloads/

# Docker权限修复
docker exec yt-dlp-web chown -R app:app /app/downloads
```

### 5. 性能问题

#### 问题：下载速度慢
**解决方案**:
```bash
# 1. 增加并发数
nano config.yml
# downloader:
#   max_concurrent: 5

# 2. 使用代理
# 配置高速代理服务器

# 3. 优化网络
# 检查网络带宽和延迟
ping google.com
speedtest-cli

# 4. 使用SSD存储
# 将下载目录挂载到SSD
```

#### 问题：内存使用过高
```bash
# 检查内存使用
free -h
docker stats yt-dlp-web
```

**解决方案**:
```bash
# 1. 降低并发数
nano config.yml
# downloader:
#   max_concurrent: 2

# 2. 限制容器内存
nano docker-compose.yml
# services:
#   yt-dlp-web:
#     mem_limit: 1g

# 3. 清理缓存
docker system prune -f
```

## 🔧 调试方法

### 启用调试模式
```bash
# 修改配置
nano config.yml
# app:
#   debug: true
# logging:
#   level: "DEBUG"

# 或使用环境变量
export FLASK_DEBUG=1
export LOG_LEVEL=DEBUG
```

### 详细日志分析
```bash
# 查看错误日志
grep "ERROR" data/logs/app.log

# 查看特定模块日志
grep "downloader" data/logs/app.log

# 实时监控日志
tail -f data/logs/app.log | grep -E "(ERROR|WARNING)"
```

### 网络调试
```bash
# 测试网络连接
curl -v https://www.youtube.com

# 测试代理连接
curl -v --proxy socks5://127.0.0.1:1080 https://www.youtube.com

# 检查DNS解析
nslookup youtube.com
dig youtube.com
```

### 数据库调试
```bash
# 检查数据库文件
ls -la data/app.db

# 连接数据库
sqlite3 data/app.db
.tables
.schema downloads

# 查询下载记录
SELECT * FROM downloads ORDER BY created_at DESC LIMIT 10;
```

## 📊 性能监控

### 系统监控命令
```bash
# CPU和内存使用
top
htop

# 磁盘IO
iotop

# 网络连接
netstat -an | grep :8080

# Docker容器状态
docker stats
```

### 应用监控
```bash
# 检查下载状态
curl http://localhost:8080/api/system/status

# 查看活跃下载
curl http://localhost:8080/api/downloads?status=downloading

# 监控存储使用
curl http://localhost:8080/api/system/storage
```

## 🆘 获取帮助

### 收集诊断信息
```bash
#!/bin/bash
# 诊断信息收集脚本

echo "=== 系统信息 ==="
uname -a
cat /etc/os-release

echo "=== Docker信息 ==="
docker version
docker-compose version

echo "=== 服务状态 ==="
docker-compose ps

echo "=== 最近日志 ==="
docker-compose logs --tail=50

echo "=== 配置信息 ==="
cat config.yml | grep -v password | grep -v token

echo "=== 磁盘使用 ==="
df -h

echo "=== 内存使用 ==="
free -h
```

### 提交问题报告
在GitHub提交Issue时，请包含：

1. **环境信息**:
   - 操作系统版本
   - Docker版本
   - 应用版本

2. **问题描述**:
   - 具体错误信息
   - 重现步骤
   - 预期行为

3. **日志信息**:
   - 相关错误日志
   - 系统状态信息

4. **配置信息**:
   - 相关配置（隐藏敏感信息）

### 社区支持
- GitHub Issues: 报告Bug和功能请求
- 讨论区: 使用问题和经验分享
- Wiki: 详细文档和教程

## 🔄 恢复操作

### 重置配置
```bash
# 备份当前配置
cp config.yml config.yml.backup

# 恢复默认配置
cp config.yml.example config.yml

# 重启服务
docker-compose restart
```

### 重置数据库
```bash
# 备份数据库
cp data/app.db data/app.db.backup

# 删除数据库（将重新初始化）
rm data/app.db

# 重启服务
docker-compose restart
```

### 完全重置
```bash
# 停止服务
docker-compose down

# 清理所有数据
rm -rf data/* downloads/* logs/*

# 重新启动
docker-compose up -d
```

---

📝 **注意**: 在执行重置操作前，请务必备份重要数据。如果问题仍然存在，请查看GitHub Issues或提交新的问题报告。
