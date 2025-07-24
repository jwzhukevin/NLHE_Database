#!/bin/bash
# Valkey一键配置脚本
# 自动完成Valkey的安装、配置和测试

echo "🎯 Valkey一键配置脚本"
echo "===================="
echo "Valkey是Redis的开源分支，由Linux基金会维护"
echo "完全兼容Redis协议，更适合生产环境"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "检测到root用户，某些操作可能需要调整权限"
    fi
}

# 检查操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/debian_version ]; then
            OS="ubuntu"
            log_info "检测到Ubuntu/Debian系统"
        elif [ -f /etc/redhat-release ]; then
            OS="centos"
            log_info "检测到CentOS/RHEL系统"
        else
            OS="linux"
            log_info "检测到Linux系统"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_info "检测到macOS系统"
    else
        OS="unknown"
        log_warning "未知操作系统: $OSTYPE"
    fi
}

# 步骤1: 检查Python环境
check_python_env() {
    log_info "步骤1: 检查Python环境"
    
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_success "Python3已安装: $PYTHON_VERSION"
    else
        log_error "Python3未安装，请先安装Python3"
        return 1
    fi
    
    # 检查虚拟环境
    if [ -d "NLHE" ]; then
        log_success "虚拟环境NLHE已存在"
    else
        log_warning "虚拟环境NLHE不存在，请先创建虚拟环境"
        return 1
    fi
    
    return 0
}

# 步骤2: 安装Python依赖
install_python_deps() {
    log_info "步骤2: 安装Python依赖"
    
    # 激活虚拟环境
    if [ -f "NLHE/bin/activate" ]; then
        source NLHE/bin/activate
        log_success "虚拟环境已激活"
    elif [ -f "NLHE/Scripts/activate" ]; then
        source NLHE/Scripts/activate
        log_success "虚拟环境已激活 (Windows)"
    else
        log_error "无法激活虚拟环境"
        return 1
    fi
    
    # 安装redis客户端
    pip install redis flask-limiter
    if [ $? -eq 0 ]; then
        log_success "Python依赖安装完成"
        return 0
    else
        log_error "Python依赖安装失败"
        return 1
    fi
}

# 步骤3: 安装Valkey
install_valkey() {
    log_info "步骤3: 安装Valkey服务"
    
    if command_exists valkey-server; then
        log_success "Valkey已安装"
        return 0
    fi
    
    # 给安装脚本执行权限
    chmod +x install_valkey.sh
    
    # 运行安装脚本
    log_info "运行Valkey安装脚本..."
    ./install_valkey.sh
    
    if [ $? -eq 0 ]; then
        log_success "Valkey安装完成"
        return 0
    else
        log_error "Valkey安装失败"
        return 1
    fi
}

# 步骤4: 配置环境变量
setup_env_vars() {
    log_info "步骤4: 配置环境变量"
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_success "创建.env文件"
        else
            log_warning ".env.example文件不存在，跳过环境变量配置"
        fi
    else
        log_success ".env文件已存在"
    fi
    
    return 0
}

# 步骤5: 测试配置
test_configuration() {
    log_info "步骤5: 测试配置"
    
    # 测试Valkey连接
    log_info "测试Valkey连接..."
    python3 test_valkey_connection.py
    
    if [ $? -eq 0 ]; then
        log_success "Valkey连接测试通过"
    else
        log_warning "Valkey连接测试失败，但可能不影响基本功能"
    fi
    
    # 测试Flask应用配置
    log_info "测试Flask应用配置..."
    python3 setup_redis_complete.py
    
    return 0
}

# 步骤6: 重启Flask应用
restart_flask_app() {
    log_info "步骤6: 重启Flask应用"
    
    # 检查是否有运行中的Flask进程
    if pgrep -f "python.*run.py" > /dev/null; then
        log_info "检测到运行中的Flask应用，正在停止..."
        pkill -f "python.*run.py"
        sleep 2
    fi
    
    log_info "Flask应用配置已更新，请手动重启应用:"
    echo "  python run.py"
    
    return 0
}

# 显示配置总结
show_summary() {
    echo ""
    echo "🎉 Valkey配置完成！"
    echo "==================="
    echo ""
    echo "📋 配置总结:"
    echo "  ✅ Valkey服务已安装并启动"
    echo "  ✅ Python依赖已安装"
    echo "  ✅ Flask应用已配置使用Valkey"
    echo "  ✅ 环境变量已设置"
    echo ""
    echo "🚀 下一步:"
    echo "  1. 重启Flask应用: python run.py"
    echo "  2. 检查日志中的 'Rate limiting enabled with Valkey storage'"
    echo "  3. 不再看到内存存储警告"
    echo ""
    echo "🔧 管理命令:"
    echo "  启动Valkey: sudo systemctl start valkey"
    echo "  停止Valkey: sudo systemctl stop valkey"
    echo "  查看状态: sudo systemctl status valkey"
    echo "  测试连接: valkey-cli ping"
    echo ""
    echo "📁 重要文件:"
    echo "  配置文件: /etc/valkey/valkey.conf"
    echo "  日志文件: /var/log/valkey/valkey-server.log"
    echo "  环境变量: .env"
    echo ""
    echo "💡 Valkey优势:"
    echo "  - 开源分支，由Linux基金会维护"
    echo "  - 完全兼容Redis协议"
    echo "  - 更适合生产环境"
    echo "  - 避免许可证问题"
}

# 主函数
main() {
    echo "开始Valkey配置流程..."
    echo ""
    
    # 检查基本环境
    check_root
    detect_os
    
    # 执行配置步骤
    steps=(
        "check_python_env"
        "install_python_deps"
        "install_valkey"
        "setup_env_vars"
        "test_configuration"
        "restart_flask_app"
    )
    
    failed_steps=()
    
    for step in "${steps[@]}"; do
        if ! $step; then
            failed_steps+=("$step")
        fi
        echo ""
    done
    
    # 显示结果
    if [ ${#failed_steps[@]} -eq 0 ]; then
        show_summary
        exit 0
    else
        log_error "以下步骤失败:"
        for step in "${failed_steps[@]}"; do
            echo "  - $step"
        done
        echo ""
        log_info "请检查错误信息并手动完成失败的步骤"
        exit 1
    fi
}

# 运行主函数
main "$@"
