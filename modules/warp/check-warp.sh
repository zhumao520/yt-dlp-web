#!/bin/bash
# WARP 状态检查工具

echo "🔍 WARP 状态检查工具"
echo "===================="

# 检查 WARP 是否可用
if [ ! -f /warp-available ]; then
    echo "❌ 当前镜像不支持 WARP 功能"
    exit 1
fi

WARP_AVAILABLE=$(cat /warp-available)
if [ "$WARP_AVAILABLE" != "true" ]; then
    echo "❌ WARP 功能未安装"
    exit 1
fi

echo "✅ WARP 功能已安装"

# 检查环境变量
echo ""
echo "📋 环境配置:"
echo "   ENABLE_WARP: ${ENABLE_WARP:-未设置}"
echo "   WARP_PROXY_PORT: ${WARP_PROXY_PORT:-未设置}"
echo "   WARP_LICENSE_KEY: ${WARP_LICENSE_KEY:+已设置}"

# 检查进程状态
echo ""
echo "🔧 进程状态:"

# 检查 warp-svc
if pgrep -f "warp-svc" >/dev/null; then
    WARP_PID=$(pgrep -f "warp-svc")
    echo "   ✅ warp-svc 运行中 (PID: $WARP_PID)"
else
    echo "   ❌ warp-svc 未运行"
fi

# 检查 gost
if pgrep -f "gost" >/dev/null; then
    GOST_PID=$(pgrep -f "gost")
    echo "   ✅ gost 代理运行中 (PID: $GOST_PID)"
else
    echo "   ❌ gost 代理未运行"
fi

# 检查端口监听
echo ""
echo "🌐 网络状态:"

PROXY_PORT=${WARP_PROXY_PORT:-1080}
if command -v netstat >/dev/null; then
    if netstat -ln 2>/dev/null | grep -q ":$PROXY_PORT "; then
        echo "   ✅ 代理端口 $PROXY_PORT 正在监听"
    else
        echo "   ❌ 代理端口 $PROXY_PORT 未监听"
    fi
elif command -v ss >/dev/null; then
    if ss -ln 2>/dev/null | grep -q ":$PROXY_PORT "; then
        echo "   ✅ 代理端口 $PROXY_PORT 正在监听"
    else
        echo "   ❌ 代理端口 $PROXY_PORT 未监听"
    fi
else
    echo "   ⚠️ 无法检查端口状态（缺少 netstat/ss）"
fi

# 检查 WARP 连接状态
echo ""
echo "🔗 WARP 连接:"

if command -v warp-cli >/dev/null; then
    WARP_STATUS=$(warp-cli status 2>/dev/null || echo "获取状态失败")
    echo "   状态: $WARP_STATUS"
    
    # 测试连接
    if timeout 5 curl -s https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -q "warp=on\|warp=plus"; then
        echo "   ✅ WARP 连接验证成功"
    else
        echo "   ⚠️ WARP 连接验证失败"
    fi
else
    echo "   ❌ warp-cli 不可用"
fi

# 检查日志
echo ""
echo "📋 日志信息:"

WARP_LOG="/app/data/logs/warp/warp.log"
if [ -f "$WARP_LOG" ]; then
    echo "   📁 日志文件: $WARP_LOG"
    echo "   📊 日志大小: $(du -h "$WARP_LOG" | cut -f1)"
    echo "   🕐 最后更新: $(stat -c %y "$WARP_LOG" 2>/dev/null || echo "未知")"
    
    echo ""
    echo "📄 最近 10 条日志:"
    echo "----------------------------------------"
    tail -n 10 "$WARP_LOG" 2>/dev/null || echo "无法读取日志"
    echo "----------------------------------------"
else
    echo "   ❌ 日志文件不存在: $WARP_LOG"
fi

# 网络配置检查
echo ""
echo "⚙️ 网络配置:"

# 检查 IPv4 转发
IPV4_FORWARD=$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo "未知")
echo "   IPv4 转发: $IPV4_FORWARD $([ "$IPV4_FORWARD" = "1" ] && echo "✅" || echo "❌")"

# 检查 IPv6 状态
IPV6_DISABLED=$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6 2>/dev/null || echo "未知")
echo "   IPv6 状态: $([ "$IPV6_DISABLED" = "0" ] && echo "启用 ✅" || echo "禁用 ❌")"

# 检查源验证标记
SRC_VALID_MARK=$(cat /proc/sys/net/ipv4/conf/all/src_valid_mark 2>/dev/null || echo "未知")
echo "   源验证标记: $SRC_VALID_MARK $([ "$SRC_VALID_MARK" = "1" ] && echo "✅" || echo "❌")"

echo ""
echo "🎯 检查完成！"

# 给出建议
echo ""
echo "💡 使用建议:"
echo "   - 查看完整日志: cat $WARP_LOG"
echo "   - 重启 WARP: 重启容器"
echo "   - 代理配置: SOCKS5://127.0.0.1:$PROXY_PORT"
