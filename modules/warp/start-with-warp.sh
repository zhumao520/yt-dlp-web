#!/bin/bash
# WARP 版启动脚本

set -e

echo "🚀 启动 YT-DLP Web WARP 版..."
echo "📋 版本: WARP 版（支持机器人检测规避）"

# 环境变量
ENABLE_WARP=${ENABLE_WARP:-true}
WARP_PROXY_PORT=${WARP_PROXY_PORT:-1080}
WARP_LICENSE_KEY=${WARP_LICENSE_KEY:-}

# 创建必要目录
mkdir -p /app/data/{downloads,logs,cookies,warp}

if [ "$ENABLE_WARP" = "true" ]; then
    echo "🌐 启动 WARP 服务（后台模式）..."

    # 创建日志目录
    mkdir -p /app/data/logs/warp
    WARP_LOG="/app/data/logs/warp/warp.log"

    # 静默模式函数
    log_error() {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$WARP_LOG"
    }

    log_info() {
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1" >> "$WARP_LOG"
    }

    # 检查权限（静默）
    if [ ! -w /dev ]; then
        log_error "缺少必要权限，WARP 可能无法正常工作"
        log_error "请使用 --cap-add NET_ADMIN 启动容器"
        echo "⚠️ WARP 权限检查失败，详情查看日志: $WARP_LOG"
    fi
    
    # 创建 TUN 设备（静默）
    mkdir -p /dev/net
    if [ ! -c /dev/net/tun ]; then
        if ! mknod /dev/net/tun c 10 200 2>>"$WARP_LOG"; then
            log_error "无法创建 TUN 设备，WARP 可能无法工作"
        else
            chmod 600 /dev/net/tun 2>/dev/null || true
            log_info "TUN 设备创建成功"
        fi
    fi
    
    # 启动 WARP 守护进程（后台静默）
    log_info "启动 WARP 守护进程..."
    warp-svc >>"$WARP_LOG" 2>&1 &
    WARP_PID=$!
    sleep 3

    # 检查守护进程是否启动成功
    if ! kill -0 $WARP_PID 2>/dev/null; then
        log_error "WARP 守护进程启动失败"
        echo "⚠️ WARP 守护进程启动失败，应用将以直连模式运行"
        echo "📋 错误详情查看: $WARP_LOG"
    else
        log_info "WARP 守护进程启动成功 (PID: $WARP_PID)"
        # 注册和连接 WARP（静默）
        if [ ! -f /var/lib/cloudflare-warp/reg.json ]; then
            log_info "注册 WARP 客户端..."
            if ! timeout 30 warp-cli register >>"$WARP_LOG" 2>&1; then
                log_error "WARP 注册失败"
                echo "⚠️ WARP 注册失败，应用将以直连模式运行"
            else
                log_info "WARP 注册成功"

                # 设置许可证（如果提供）
                if [ -n "$WARP_LICENSE_KEY" ]; then
                    log_info "设置 WARP+ 许可证..."
                    if ! timeout 10 warp-cli set-license "$WARP_LICENSE_KEY" >>"$WARP_LOG" 2>&1; then
                        log_error "许可证设置失败"
                    else
                        log_info "许可证设置成功"
                    fi
                fi
            fi
        fi

        # 连接 WARP（静默）
        log_info "连接到 WARP..."
        if ! timeout 30 warp-cli connect >>"$WARP_LOG" 2>&1; then
            log_error "WARP 连接失败"
            echo "⚠️ WARP 连接失败，应用将以直连模式运行"
        else
            log_info "WARP 连接成功"
            sleep 5
        fi
    fi
    
    # 启动 GOST 代理（后台静默）
    log_info "启动 SOCKS5 代理（端口 $WARP_PROXY_PORT）..."
    if ! gost -L :$WARP_PROXY_PORT >>"$WARP_LOG" 2>&1 &; then
        log_error "GOST 代理启动失败"
        echo "⚠️ SOCKS5 代理启动失败"
    else
        GOST_PID=$!
        sleep 2

        # 验证代理服务（静默）
        log_info "验证代理服务状态..."
        if command -v netstat >/dev/null && netstat -ln 2>/dev/null | grep -q ":$WARP_PROXY_PORT "; then
            log_info "SOCKS5 代理启动成功 (PID: $GOST_PID)"
            PROXY_RUNNING=true
        elif command -v ss >/dev/null && ss -ln 2>/dev/null | grep -q ":$WARP_PROXY_PORT "; then
            log_info "SOCKS5 代理启动成功 (PID: $GOST_PID)"
            PROXY_RUNNING=true
        else
            log_info "无法验证代理状态，但可能正在运行"
            PROXY_RUNNING=true
        fi
    fi
    
    # 验证 WARP 连接（静默）
    log_info "验证 WARP 连接状态..."
    if timeout 10 curl -s https://cloudflare.com/cdn-cgi/trace 2>>"$WARP_LOG" | grep -q "warp=on\|warp=plus"; then
        log_info "WARP 连接验证成功"
        WARP_WORKING=true
    else
        log_error "WARP 连接验证失败，但服务可能仍在工作"
        WARP_WORKING=false
    fi

    # 输出最终状态
    if [ "$PROXY_RUNNING" = "true" ]; then
        echo "✅ WARP 服务已启动"
        echo "📋 代理配置: SOCKS5://127.0.0.1:$WARP_PROXY_PORT"
        if [ "$WARP_WORKING" = "true" ]; then
            echo "🌐 WARP 状态: 连接正常"
            log_info "WARP 服务完全启动成功"
        else
            echo "⚠️ WARP 状态: 连接待验证"
            log_info "WARP 服务启动，但连接验证失败"
        fi
        echo "📋 详细日志: $WARP_LOG"
    else
        echo "❌ WARP 服务启动失败，应用将以直连模式运行"
        echo "📋 错误日志: $WARP_LOG"
        log_error "WARP 服务启动失败"
    fi
    echo ""
else
    echo "ℹ️ WARP 功能已禁用"
fi

# 启动应用
echo "🚀 启动主应用..."
exec python main.py
