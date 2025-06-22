# API 文档

YT-DLP Web 提供完整的 RESTful API，支持所有核心功能的程序化访问。

## 🔐 认证

### 获取访问令牌
```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "your_password"
}
```

**响应**:
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expires_in": 86400,
  "user": {
    "username": "admin",
    "role": "admin"
  }
}
```

### 使用令牌
在所有API请求中包含Authorization头：
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## 📥 下载管理

### 创建下载任务
```http
POST /api/download
Content-Type: application/json
Authorization: Bearer <token>

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "quality": "best",
  "format": "mp4",
  "extract_audio": false,
  "custom_filename": "my_video"
}
```

**参数说明**:
- `url` (必需): 视频URL
- `quality`: 视频质量 (`best`, `worst`, `720p`, `1080p`, `4k`)
- `format`: 输出格式 (`mp4`, `webm`, `mkv`)
- `extract_audio`: 是否仅提取音频
- `custom_filename`: 自定义文件名

**响应**:
```json
{
  "success": true,
  "download_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "下载任务已创建"
}
```

### 查询下载状态
```http
GET /api/download/{download_id}/status
Authorization: Bearer <token>
```

**响应**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "status": "downloading",
  "progress": 45.6,
  "title": "Video Title",
  "file_size": 1048576,
  "downloaded_size": 478150,
  "speed": "1.2MB/s",
  "eta": "00:02:30",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:02:30Z"
}
```

**状态值**:
- `pending`: 等待中
- `downloading`: 下载中
- `completed`: 已完成
- `failed`: 失败
- `cancelled`: 已取消

### 获取下载列表
```http
GET /api/downloads?page=1&limit=20&status=all
Authorization: Bearer <token>
```

**查询参数**:
- `page`: 页码 (默认: 1)
- `limit`: 每页数量 (默认: 20, 最大: 100)
- `status`: 状态过滤 (`all`, `pending`, `downloading`, `completed`, `failed`)

**响应**:
```json
{
  "downloads": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "url": "https://www.youtube.com/watch?v=VIDEO_ID",
      "status": "completed",
      "title": "Video Title",
      "file_path": "/app/downloads/video.mp4",
      "file_size": 1048576,
      "created_at": "2024-01-01T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "pages": 5
  }
}
```

### 取消下载
```http
DELETE /api/download/{download_id}
Authorization: Bearer <token>
```

**响应**:
```json
{
  "success": true,
  "message": "下载任务已取消"
}
```

### 重试下载
```http
POST /api/download/{download_id}/retry
Authorization: Bearer <token>
```

## 📁 文件管理

### 获取文件列表
```http
GET /api/files?path=/&page=1&limit=50
Authorization: Bearer <token>
```

**响应**:
```json
{
  "files": [
    {
      "name": "video.mp4",
      "path": "/app/downloads/video.mp4",
      "size": 1048576,
      "size_human": "1.0 MB",
      "type": "video",
      "mime_type": "video/mp4",
      "created_at": "2024-01-01T10:00:00Z",
      "modified_at": "2024-01-01T10:05:00Z"
    }
  ],
  "current_path": "/",
  "parent_path": null,
  "total_files": 25,
  "total_size": 52428800
}
```

### 下载文件
```http
GET /api/files/download?path=/app/downloads/video.mp4
Authorization: Bearer <token>
```

### 删除文件
```http
DELETE /api/files
Content-Type: application/json
Authorization: Bearer <token>

{
  "paths": ["/app/downloads/video1.mp4", "/app/downloads/video2.mp4"]
}
```

### 获取文件信息
```http
GET /api/files/info?path=/app/downloads/video.mp4
Authorization: Bearer <token>
```

**响应**:
```json
{
  "name": "video.mp4",
  "path": "/app/downloads/video.mp4",
  "size": 1048576,
  "size_human": "1.0 MB",
  "type": "video",
  "mime_type": "video/mp4",
  "duration": "00:03:45",
  "resolution": "1920x1080",
  "bitrate": "2000 kbps",
  "created_at": "2024-01-01T10:00:00Z",
  "modified_at": "2024-01-01T10:05:00Z"
}
```

## ⚙️ 系统管理

### 获取系统状态
```http
GET /api/system/status
Authorization: Bearer <token>
```

**响应**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime": 86400,
  "downloads": {
    "active": 2,
    "pending": 5,
    "completed": 150,
    "failed": 3
  },
  "storage": {
    "total": 107374182400,
    "used": 21474836480,
    "free": 85899345920,
    "usage_percent": 20.0
  },
  "system": {
    "cpu_percent": 15.5,
    "memory_percent": 45.2,
    "disk_io": {
      "read_mb": 1024,
      "write_mb": 2048
    }
  }
}
```

### 获取系统配置
```http
GET /api/system/config
Authorization: Bearer <token>
```

### 更新系统配置
```http
PUT /api/system/config
Content-Type: application/json
Authorization: Bearer <token>

{
  "downloader": {
    "max_concurrent": 3,
    "auto_cleanup": true,
    "file_retention_hours": 168
  }
}
```

### 清理系统
```http
POST /api/system/cleanup
Content-Type: application/json
Authorization: Bearer <token>

{
  "clean_downloads": true,
  "clean_logs": false,
  "clean_temp": true
}
```

## 🤖 Telegram集成

### 获取Telegram配置
```http
GET /api/telegram/config
Authorization: Bearer <token>
```

### 更新Telegram配置
```http
PUT /api/telegram/config
Content-Type: application/json
Authorization: Bearer <token>

{
  "bot_token": "YOUR_BOT_TOKEN",
  "chat_id": "YOUR_CHAT_ID",
  "api_id": "YOUR_API_ID",
  "api_hash": "YOUR_API_HASH",
  "auto_upload": true,
  "upload_method": "bot_api"
}
```

### 测试Telegram连接
```http
POST /api/telegram/test
Authorization: Bearer <token>
```

### 手动上传文件
```http
POST /api/telegram/upload
Content-Type: application/json
Authorization: Bearer <token>

{
  "file_path": "/app/downloads/video.mp4",
  "caption": "Downloaded video",
  "method": "bot_api"
}
```

## 📊 统计信息

### 获取下载统计
```http
GET /api/stats/downloads?period=7d
Authorization: Bearer <token>
```

**响应**:
```json
{
  "period": "7d",
  "total_downloads": 150,
  "successful_downloads": 145,
  "failed_downloads": 5,
  "success_rate": 96.7,
  "total_size": 5368709120,
  "average_size": 35791394,
  "daily_stats": [
    {
      "date": "2024-01-01",
      "downloads": 25,
      "size": 1073741824
    }
  ]
}
```

## 🔍 搜索和过滤

### 搜索下载记录
```http
GET /api/search/downloads?q=keyword&status=completed&date_from=2024-01-01
Authorization: Bearer <token>
```

### 搜索文件
```http
GET /api/search/files?q=video&type=mp4&size_min=1048576
Authorization: Bearer <token>
```

## 📝 错误处理

### 错误响应格式
```json
{
  "success": false,
  "error": {
    "code": "INVALID_URL",
    "message": "提供的URL无效",
    "details": "URL格式不正确或不受支持"
  },
  "timestamp": "2024-01-01T10:00:00Z"
}
```

### 常见错误码
- `UNAUTHORIZED`: 未授权访问
- `FORBIDDEN`: 权限不足
- `NOT_FOUND`: 资源不存在
- `INVALID_URL`: URL无效
- `DOWNLOAD_FAILED`: 下载失败
- `STORAGE_FULL`: 存储空间不足
- `RATE_LIMITED`: 请求频率过高

## 📋 使用示例

### Python示例
```python
import requests

# 登录获取令牌
response = requests.post('http://localhost:8080/auth/login', json={
    'username': 'admin',
    'password': 'your_password'
})
token = response.json()['token']

# 创建下载任务
headers = {'Authorization': f'Bearer {token}'}
response = requests.post('http://localhost:8080/api/download', 
    headers=headers,
    json={
        'url': 'https://www.youtube.com/watch?v=VIDEO_ID',
        'quality': 'best'
    }
)
download_id = response.json()['download_id']

# 查询下载状态
response = requests.get(f'http://localhost:8080/api/download/{download_id}/status',
    headers=headers
)
status = response.json()
print(f"下载进度: {status['progress']}%")
```

### JavaScript示例
```javascript
// 登录
const loginResponse = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        username: 'admin',
        password: 'your_password'
    })
});
const { token } = await loginResponse.json();

// 创建下载
const downloadResponse = await fetch('/api/download', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
        url: 'https://www.youtube.com/watch?v=VIDEO_ID',
        quality: 'best'
    })
});
const { download_id } = await downloadResponse.json();

// 轮询状态
const checkStatus = async () => {
    const response = await fetch(`/api/download/${download_id}/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const status = await response.json();
    console.log(`进度: ${status.progress}%`);
    
    if (status.status === 'completed') {
        console.log('下载完成!');
    } else if (status.status === 'failed') {
        console.log('下载失败:', status.error_message);
    } else {
        setTimeout(checkStatus, 1000);
    }
};
checkStatus();
```

---

📝 **注意**: 所有API都需要有效的认证令牌，请妥善保管您的访问凭据。
