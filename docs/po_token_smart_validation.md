# PO Token智能验证和自动更新逻辑（复用现有功能版）

## 问题解决

您提到的问题：**"每次下载都更新PO Token，而不是先验证现有PO Token有效性"** 已经修复。

### 🔧 修复前的问题
```
下载开始 → 直接更新PO Token → 下载
```

### ✅ 修复后的逻辑
```
下载开始 → 验证PO Token有效性 → 
  ├─ 有效：直接使用现有Token
  └─ 无效：自动更新Token → 使用新Token
```

## 核心改进

### 1. 复用现有功能 ✅
- **不重新实现**：复用项目中已有的自动生成功能
- **保持一致性**：使用相同的生成逻辑和代理配置
- **避免重复**：减少代码冗余，提高维护性

### 2. 智能验证机制
#### `verify_po_token(po_token, visitor_data, caller_name)`
- 使用yt-dlp测试PO Token的实际有效性
- **自动使用代理配置**：调用项目的代理转换器
- 通过YouTube视频提取判断Token是否工作
- 智能错误分析，区分Token问题和网络问题

#### `get_valid_po_token_config(caller_name, auto_update=True)`
- **核心智能逻辑**：
  1. 获取当前PO Token配置
  2. 验证Token有效性
  3. 如果有效，直接返回
  4. 如果无效且允许自动更新，调用现有生成功能
  5. 返回最新的有效配置

### 3. 复用现有自动生成功能
#### `_call_existing_auto_generator(caller_name)`
- **完全复用**项目中`modules/cookies/routes.py`的自动生成逻辑
- 包括：
  - 代理配置获取
  - Visitor Data提取
  - Node.js脚本生成
  - PO Token生成
  - 配置保存

### 4. 应用层优化
- `apply_to_ytdlp_opts()`: 使用`get_valid_po_token_config()`替代直接获取配置
- `apply_to_pytubefix_kwargs()`: 同样使用智能验证逻辑
- 所有下载器都自动受益于智能验证

## 技术实现

### 验证流程（带代理支持）
```python
def verify_po_token(self, po_token, visitor_data, caller_name):
    # 获取代理配置
    proxy_config = ProxyConverter.get_ytdlp_proxy(f"POTokenVerify-{caller_name}")

    test_opts = {
        'quiet': True,
        'extract_flat': True,
        'extractor_args': {
            'youtube': {
                'po_token': po_token,
                'visitor_data': visitor_data,
                'player_client': ['mweb']
            }
        }
    }

    # 添加代理配置
    if proxy_config:
        test_opts['proxy'] = proxy_config

    # 使用yt-dlp测试Token有效性
    with yt_dlp.YoutubeDL(test_opts) as ydl:
        info = ydl.extract_info(test_url, download=False)
        return info and 'title' in info

def get_valid_po_token_config(self, caller_name, auto_update=True):
    config = self.get_config(caller_name)

    if not config['po_token_available']:
        return config  # 没有Token，直接返回

    # 验证现有Token（使用代理）
    is_valid = self.verify_po_token(config['po_token'], config['visitor_data'], caller_name)

    if is_valid:
        return config  # 有效，直接使用

    if auto_update:
        # 无效，调用现有自动生成功能（也使用代理）
        success = self._call_existing_auto_generator(caller_name)
        if success:
            return self.get_config(caller_name)  # 返回新配置

    return config  # 降级处理
```

### 复用现有功能
```python
def _call_existing_auto_generator(self, caller_name):
    # 完全复用 modules/cookies/routes.py 中的逻辑
    # 1. 获取代理配置
    proxy_config = ProxyConverter.get_requests_proxy(f"AutoUpdate-{caller_name}")
    
    # 2. 生成visitor data（复用现有逻辑）
    visitor_data = self._generate_visitor_data(proxy_config)
    
    # 3. 使用Node.js生成PO Token（复用现有脚本）
    po_token = self._generate_po_token_with_nodejs(visitor_data)
    
    # 4. 保存配置（复用现有保存方法）
    return self.save_po_token_config(po_token, visitor_data, f"AutoUpdate-{caller_name}")
```

## 使用示例

### 自动验证和更新
```python
# 旧方式（每次都可能更新）
config = po_token_manager.get_config("Downloader")

# 新方式（智能验证，只在需要时更新）
config = po_token_manager.get_valid_po_token_config("Downloader", auto_update=True)
```

### 手动验证
```python
from core.po_token_manager import verify_current_po_token, update_po_token_if_needed

# 检查当前Token是否有效
is_valid = verify_current_po_token("ManualCheck")

# 如果需要则更新
if not is_valid:
    success = update_po_token_if_needed("ManualCheck")
```

## 日志示例

### Token有效时（使用代理验证）
```
🔍 Downloader 验证PO Token有效性...
🌐 Downloader PO Token验证使用代理: socks5://192.168.2.222:1186
✅ Downloader PO Token验证已配置代理
✅ Downloader PO Token验证成功
✅ Downloader 当前PO Token有效，直接使用
🔑 Downloader 使用PO Token配置 (mweb客户端，支持4K)
```

### Token无效时（使用代理更新）
```
🔍 Downloader 验证PO Token有效性...
🌐 Downloader PO Token验证使用代理: socks5://192.168.2.222:1186
✅ Downloader PO Token验证已配置代理
⚠️ Downloader PO Token已失效: Sign in to confirm your age
⚠️ Downloader 当前PO Token已失效
🔄 Downloader 尝试自动更新PO Token...
🚀 Downloader 调用现有自动生成功能
🌐 代理配置: {'http': 'http://192.168.2.222:1190', 'https': 'http://192.168.2.222:1190'}
✅ Downloader 成功获取visitor data: CgtaVzVOVGFXOXVkZz...
✅ Downloader Node.js PO Token生成成功: MmFhZGQyYWRkMmFkZD...
✅ PO Token配置已保存 (来源: AutoUpdate-Downloader)
🎉 Downloader 自动更新PO Token完成
✅ Downloader PO Token自动更新成功
```

## 优势

1. **智能化**：只在需要时更新，避免不必要的操作
2. **复用性**：完全复用现有功能，避免重复实现
3. **一致性**：使用相同的生成逻辑和配置
4. **可靠性**：验证机制确保Token有效性
5. **向后兼容**：保持现有API不变
6. **自动化**：无需手动干预，自动处理失效Token

## 配置要求

- **Node.js环境**：用于自动生成PO Token
- **代理配置**：复用项目现有的代理转换器
- **网络连接**：用于验证和生成Token

## 总结

通过这次修改，我们成功：
- ✅ **修复了逻辑问题**：先验证再更新，而不是每次都更新
- ✅ **复用了现有功能**：避免重复实现，保持代码一致性
- ✅ **提高了效率**：减少不必要的Token更新操作
- ✅ **增强了可靠性**：验证机制确保Token有效性
- ✅ **保持了兼容性**：现有代码无需修改即可受益

现在的PO Token管理逻辑更加智能和高效，完全符合您的需求！
