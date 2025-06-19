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
    echo "🔧 启动 WARP 守护进程..."
    log_info "启动 WARP 守护进程..."
    nohup warp-svc >>"$WARP_LOG" 2>&1 &
    WARP_PID=$!
    sleep 5

    # 检查守护进程是否启动成功
    if ! kill -0 $WARP_PID 2>/dev/null; then
        log_error "WARP 守护进程启动失败"
        echo "⚠️ WARP 守护进程启动失败，应用将以直连模式运行"
        echo "📋 错误详情查看: $WARP_LOG"
    else
        log_info "WARP 守护进程启动成功 (PID: $WARP_PID)"
        echo "✅ WARP 守护进程已启动"

        # 等待守护进程完全启动
        sleep 3

        # 注册和连接 WARP（静默）
        if [ ! -f /var/lib/cloudflare-warp/reg.json ]; then
            echo "🔑 注册 WARP 客户端..."
            log_info "注册 WARP 客户端..."
            if ! timeout 30 warp-cli registration new --accept-tos >>"$WARP_LOG" 2>&1; then
                log_error "WARP 注册失败"
                echo "⚠️ WARP 注册失败，应用将以直连模式运行"
            else
                log_info "WARP 注册成功"
                echo "✅ WARP 客户端注册成功"

                # 设置许可证（如果提供）
                if [ -n "$WARP_LICENSE_KEY" ]; then
                    echo "🔑 设置 WARP+ 许可证..."
                    log_info "设置 WARP+ 许可证..."
                    if ! timeout 10 warp-cli set-license "$WARP_LICENSE_KEY" >>"$WARP_LOG" 2>&1; then
                        log_error "许可证设置失败"
                        echo "⚠️ 许可证设置失败"
                    else
                        log_info "许可证设置成功"
                        echo "✅ WARP+ 许可证设置成功"
                    fi
                fi
            fi
        else
            echo "✅ WARP 客户端已注册"
            log_info "WARP 客户端已注册"
        fi

        # 设置代理模式
        echo "🔧 设置 WARP 代理模式..."
        log_info "设置 WARP 代理模式..."
        if ! timeout 10 warp-cli mode proxy >>"$WARP_LOG" 2>&1; then
            log_error "WARP 代理模式设置失败"
            echo "⚠️ WARP 代理模式设置失败"
        else
            log_info "WARP 代理模式设置成功"
            echo "✅ WARP 代理模式已设置"
        fi

        # 连接 WARP（静默）
        echo "🌐 连接到 WARP..."
        log_info "连接到 WARP..."
        if ! timeout 30 warp-cli connect >>"$WARP_LOG" 2>&1; then
            log_error "WARP 连接失败"
            echo "⚠️ WARP 连接失败，应用将以直连模式运行"
        else
            log_info "WARP 连接成功"
            echo "✅ WARP 连接成功"
            sleep 3
        fi
    fi
    
    # 检查 WARP 代理端口
    echo "🔍 检查 WARP 代理端口..."
    log_info "检查 WARP 代理端口..."

    # 等待 WARP 代理端口启动
    WARP_INTERNAL_PORT=""
    for i in {1..10}; do
        # 检查常见的 WARP 代理端口
        for port in 40000 1080 8080; do
            if netstat -ln 2>/dev/null | grep -q ":$port " || ss -ln 2>/dev/null | grep -q ":$port "; then
                # 验证这是 WARP 的端口
                if timeout 5 curl -s --socks5 127.0.0.1:$port http://httpbin.org/ip >/dev/null 2>&1; then
                    WARP_INTERNAL_PORT=$port
                    break 2
                fi
            fi
        done
        sleep 2
    done

    if [ -n "$WARP_INTERNAL_PORT" ]; then
        echo "✅ 发现 WARP 代理端口: $WARP_INTERNAL_PORT"
        log_info "发现 WARP 代理端口: $WARP_INTERNAL_PORT"

        # 如果 WARP 已经监听用户指定的端口，直接使用
        if [ "$WARP_INTERNAL_PORT" = "$WARP_PROXY_PORT" ]; then
            echo "✅ WARP 已监听目标端口 $WARP_PROXY_PORT，无需 GOST 转发"
            log_info "WARP 已监听目标端口 $WARP_PROXY_PORT，无需 GOST 转发"
            PROXY_RUNNING=true
        else
            # 使用 GOST 转发到用户指定的端口
            echo "📡 启动 GOST 代理转发（$WARP_INTERNAL_PORT → $WARP_PROXY_PORT）..."
            log_info "启动 GOST 代理转发（$WARP_INTERNAL_PORT → $WARP_PROXY_PORT）..."
            nohup gost -L "socks5://:$WARP_PROXY_PORT" -F "socks5://127.0.0.1:$WARP_INTERNAL_PORT" >>"$WARP_LOG" 2>&1 &
            GOST_PID=$!
            sleep 3
        fi
    else
        echo "⚠️ 未发现 WARP 代理端口，尝试直接启动 GOST..."
        log_info "未发现 WARP 代理端口，尝试直接启动 GOST..."
        # 直接启动 GOST，不转发（可能 WARP 在其他模式）
        nohup gost -L "socks5://:$WARP_PROXY_PORT" >>"$WARP_LOG" 2>&1 &
        GOST_PID=$!
        sleep 3
    fi

    # 验证最终代理服务
    if [ "$PROXY_RUNNING" != "true" ]; then
        echo "🔍 验证代理服务状态..."
        log_info "验证代理服务状态..."
        if command -v netstat >/dev/null && netstat -ln 2>/dev/null | grep -q ":$WARP_PROXY_PORT "; then
            log_info "SOCKS5 代理端口 $WARP_PROXY_PORT 监听成功"
            echo "✅ SOCKS5 代理已启动"
            PROXY_RUNNING=true
        elif command -v ss >/dev/null && ss -ln 2>/dev/null | grep -q ":$WARP_PROXY_PORT "; then
            log_info "SOCKS5 代理端口 $WARP_PROXY_PORT 监听成功"
            echo "✅ SOCKS5 代理已启动"
            PROXY_RUNNING=true
        else
            log_error "SOCKS5 代理端口 $WARP_PROXY_PORT 验证失败"
            echo "⚠️ SOCKS5 代理状态未知"
            PROXY_RUNNING=false
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
