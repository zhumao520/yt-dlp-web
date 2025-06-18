#!/bin/bash

# YT-DLP Web 部署脚本
# 使用方法: ./deploy.sh [start|stop|restart|update|logs|status]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_NAME="yt-dlp-web"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    log_success "系统依赖检查通过"
}

# 初始化环境
init_environment() {
    log_info "初始化部署环境..."
    
    # 创建必要目录
    mkdir -p data/{downloads,database,logs,temp,cookies}
    mkdir -p config
    
    # 复制环境变量文件
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example "$ENV_FILE"
            log_warning "已创建 .env 文件，请根据需要修改配置"
        else
            log_warning "未找到 .env.example 文件，请手动创建 .env 文件"
        fi
    fi
    
    # 设置目录权限
    chmod -R 755 data/
    
    log_success "环境初始化完成"
}

# 启动服务
start_service() {
    log_info "启动 $PROJECT_NAME 服务..."
    
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_warning "服务已在运行中"
        return
    fi
    
    docker compose -f "$COMPOSE_FILE" up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查服务状态
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_success "服务启动成功"
        log_info "访问地址: http://localhost:8090"
    else
        log_error "服务启动失败，请查看日志"
        docker compose -f "$COMPOSE_FILE" logs
    fi
}

# 停止服务
stop_service() {
    log_info "停止 $PROJECT_NAME 服务..."
    docker compose -f "$COMPOSE_FILE" down
    log_success "服务已停止"
}

# 重启服务
restart_service() {
    log_info "重启 $PROJECT_NAME 服务..."
    stop_service
    start_service
}

# 更新服务
update_service() {
    log_info "更新 $PROJECT_NAME 服务..."
    
    # 拉取最新镜像
    docker compose -f "$COMPOSE_FILE" pull
    
    # 重启服务
    restart_service
    
    # 清理旧镜像
    docker image prune -f
    
    log_success "服务更新完成"
}

# 查看日志
show_logs() {
    log_info "显示 $PROJECT_NAME 服务日志..."
    docker compose -f "$COMPOSE_FILE" logs -f --tail=100
}

# 查看状态
show_status() {
    log_info "$PROJECT_NAME 服务状态:"
    docker compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "资源使用情况:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" $(docker compose -f "$COMPOSE_FILE" ps -q) 2>/dev/null || log_warning "无法获取资源使用情况"
}

# 备份数据
backup_data() {
    log_info "备份数据..."
    
    BACKUP_DIR="backup/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份数据目录
    if [ -d "data" ]; then
        cp -r data "$BACKUP_DIR/"
        log_success "数据备份完成: $BACKUP_DIR"
    else
        log_warning "未找到数据目录"
    fi
}

# 显示帮助信息
show_help() {
    echo "YT-DLP Web 部署脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [命令]"
    echo ""
    echo "可用命令:"
    echo "  start     启动服务"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  update    更新服务"
    echo "  logs      查看日志"
    echo "  status    查看状态"
    echo "  backup    备份数据"
    echo "  init      初始化环境"
    echo "  help      显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start    # 启动服务"
    echo "  $0 logs     # 查看实时日志"
}

# 主函数
main() {
    case "${1:-help}" in
        "start")
            check_dependencies
            init_environment
            start_service
            ;;
        "stop")
            stop_service
            ;;
        "restart")
            restart_service
            ;;
        "update")
            check_dependencies
            update_service
            ;;
        "logs")
            show_logs
            ;;
        "status")
            show_status
            ;;
        "backup")
            backup_data
            ;;
        "init")
            check_dependencies
            init_environment
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# 执行主函数
main "$@"
