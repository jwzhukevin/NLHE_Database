#!/bin/bash
# Redis启动脚本
# 用于在不同系统上启动Redis服务

echo "🚀 Redis服务启动脚本"
echo "===================="

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="Windows"
else
    OS="Unknown"
fi

echo "检测到操作系统: $OS"

# 检查Redis是否已安装
check_redis_installed() {
    if command -v redis-server &> /dev/null; then
        echo "✅ Redis已安装"
        redis-server --version
        return 0
    else
        echo "❌ Redis未安装"
        return 1
    fi
}

# 检查Redis是否正在运行
check_redis_running() {
    if pgrep -f "redis-server" > /dev/null; then
        echo "✅ Redis服务正在运行"
        return 0
    else
        echo "❌ Redis服务未运行"
        return 1
    fi
}

# 启动Redis服务
start_redis() {
    case $OS in
        "Linux")
            echo "🔧 在Linux上启动Redis..."
            if command -v systemctl &> /dev/null; then
                # 使用systemd
                sudo systemctl start redis-server
                sudo systemctl enable redis-server
                echo "✅ Redis服务已启动并设置为开机自启"
            elif command -v service &> /dev/null; then
                # 使用service命令
                sudo service redis-server start
                echo "✅ Redis服务已启动"
            else
                # 直接启动
                redis-server --daemonize yes
                echo "✅ Redis服务已后台启动"
            fi
            ;;
        "macOS")
            echo "🔧 在macOS上启动Redis..."
            if command -v brew &> /dev/null; then
                brew services start redis
                echo "✅ Redis服务已启动"
            else
                redis-server --daemonize yes
                echo "✅ Redis服务已后台启动"
            fi
            ;;
        "Windows")
            echo "🔧 在Windows上启动Redis..."
            echo "请手动启动Redis服务或使用WSL"
            ;;
        *)
            echo "⚠️  未知操作系统，尝试直接启动..."
            redis-server --daemonize yes
            ;;
    esac
}

# 安装Redis
install_redis() {
    echo "🔧 安装Redis..."
    case $OS in
        "Linux")
            if command -v apt &> /dev/null; then
                sudo apt update
                sudo apt install -y redis-server
            elif command -v yum &> /dev/null; then
                sudo yum install -y redis
            elif command -v dnf &> /dev/null; then
                sudo dnf install -y redis
            else
                echo "❌ 无法自动安装Redis，请手动安装"
                return 1
            fi
            ;;
        "macOS")
            if command -v brew &> /dev/null; then
                brew install redis
            else
                echo "❌ 请先安装Homebrew，然后运行: brew install redis"
                return 1
            fi
            ;;
        "Windows")
            echo "❌ 请在WSL中安装Redis或下载Windows版本"
            echo "WSL安装命令: sudo apt install redis-server"
            return 1
            ;;
        *)
            echo "❌ 无法在此系统上自动安装Redis"
            return 1
            ;;
    esac
}

# 测试Redis连接
test_redis() {
    echo "🧪 测试Redis连接..."
    if redis-cli ping | grep -q "PONG"; then
        echo "✅ Redis连接测试成功"
        return 0
    else
        echo "❌ Redis连接测试失败"
        return 1
    fi
}

# 主逻辑
main() {
    echo ""
    
    # 检查是否已安装
    if ! check_redis_installed; then
        echo ""
        read -p "是否要安装Redis? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_redis
            if [ $? -ne 0 ]; then
                echo "❌ Redis安装失败"
                exit 1
            fi
        else
            echo "❌ Redis未安装，无法继续"
            exit 1
        fi
    fi
    
    echo ""
    
    # 检查是否正在运行
    if check_redis_running; then
        echo "Redis服务已在运行"
    else
        echo "启动Redis服务..."
        start_redis
        sleep 2  # 等待服务启动
    fi
    
    echo ""
    
    # 测试连接
    test_redis
    
    echo ""
    echo "🎉 Redis配置完成！"
    echo ""
    echo "📋 下一步:"
    echo "1. 安装Python Redis客户端: pip install redis"
    echo "2. 运行测试脚本: python test_redis_connection.py"
    echo "3. 重启Flask应用以使用Redis存储"
    echo ""
    echo "🔧 Redis管理命令:"
    echo "- 查看状态: redis-cli ping"
    echo "- 连接Redis: redis-cli"
    echo "- 停止服务: redis-cli shutdown"
}

# 运行主函数
main
