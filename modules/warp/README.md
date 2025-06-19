# WARP 模块

## 📋 模块说明

这个模块包含了 Cloudflare WARP 集成的相关脚本和配置。

## 📁 文件结构

```
modules/warp/
├── __init__.py              # 模块初始化文件
├── start-with-warp.sh       # WARP版启动脚本
└── README.md               # 本说明文件
```

## 🚀 启动脚本说明

### start-with-warp.sh
- **用途**: WARP版容器的启动脚本
- **功能**: 
  - 启动 Cloudflare WARP 服务
  - 配置 SOCKS5 代理
  - 验证连接状态
  - 启动主应用
- **环境变量**:
  - `ENABLE_WARP`: 是否启用 WARP (默认: true)
  - `WARP_PROXY_PORT`: 代理端口 (默认: 1080)
  - `WARP_LICENSE_KEY`: WARP+ 许可证 (可选)

### scripts/start-standard.sh
- **位置**: `scripts/start-standard.sh` (不在此模块中)
- **用途**: 标准版容器的启动脚本
- **功能**:
  - 创建必要目录
  - 直接启动主应用
- **特点**: 轻量级，快速启动

## 🔧 在 Dockerfile 中的使用

```dockerfile
# 根据构建参数复制对应的启动脚本
RUN if [ "$INSTALL_WARP" = "true" ]; then \
        cp modules/warp/start-with-warp.sh /start-app.sh; \
    else \
        cp scripts/start-standard.sh /start-app.sh; \
    fi && \
    chmod +x /start-app.sh
```

## 🎯 设计理念

1. **模块化**: 将 WARP 相关功能集中在一个模块中
2. **简洁性**: 避免复杂的管理类，使用简单的脚本
3. **可靠性**: 包含完整的错误处理和故障恢复
4. **用户友好**: 提供详细的状态信息和配置指导

## 🔍 故障排除

### 常见问题
1. **权限不足**: 确保容器有 NET_ADMIN 权限
2. **网络问题**: 检查是否能访问 Cloudflare 服务
3. **端口冲突**: 确保代理端口没有被占用

### 调试方法
```bash
# 查看容器日志
docker logs container-name

# 进入容器检查
docker exec -it container-name bash

# 检查 WARP 状态
docker exec container-name warp-cli status

# 检查代理端口
docker exec container-name netstat -ln | grep 1080
```

## 📊 版本历史

- **v1.0.0**: 初始版本，包含基本的 WARP 集成功能
