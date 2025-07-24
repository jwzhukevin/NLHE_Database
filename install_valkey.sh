#!/bin/bash
# Valkey安装脚本
# Valkey是Redis的开源分支，由Linux基金会维护，更适合生产环境

echo "🚀 Valkey安装脚本"
echo "=================="
echo "Valkey是Redis的开源分支，由Linux基金会维护"
echo ""

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if [ -f /etc/debian_version ]; then
        OS="Ubuntu/Debian"
        PACKAGE_MANAGER="apt"
    elif [ -f /etc/redhat-release ]; then
        OS="CentOS/RHEL"
        PACKAGE_MANAGER="yum"
    elif [ -f /etc/fedora-release ]; then
        OS="Fedora"
        PACKAGE_MANAGER="dnf"
    else
        OS="Linux (Unknown)"
        PACKAGE_MANAGER="unknown"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    PACKAGE_MANAGER="brew"
else
    OS="Unknown"
    PACKAGE_MANAGER="unknown"
fi

echo "检测到操作系统: $OS"
echo "包管理器: $PACKAGE_MANAGER"
echo ""

# 检查是否已安装
check_valkey_installed() {
    if command -v valkey-server &> /dev/null; then
        echo "✅ Valkey已安装"
        valkey-server --version
        return 0
    elif command -v redis-server &> /dev/null; then
        echo "⚠️  检测到Redis，建议迁移到Valkey"
        redis-server --version
        return 1
    else
        echo "❌ Valkey未安装"
        return 2
    fi
}

# 安装依赖
install_dependencies() {
    echo "🔧 安装编译依赖..."
    case $PACKAGE_MANAGER in
        "apt")
            sudo apt update
            sudo apt install -y build-essential wget curl git
            ;;
        "yum")
            sudo yum groupinstall -y "Development Tools"
            sudo yum install -y wget curl git
            ;;
        "dnf")
            sudo dnf groupinstall -y "Development Tools"
            sudo dnf install -y wget curl git
            ;;
        "brew")
            # macOS通常已有这些工具
            echo "macOS环境，跳过依赖安装"
            ;;
        *)
            echo "⚠️  未知包管理器，请手动安装: build-essential wget curl git"
            ;;
    esac
}

# 从源码安装Valkey
install_valkey_from_source() {
    echo "🔧 从源码编译安装Valkey..."
    
    # 创建临时目录
    TEMP_DIR="/tmp/valkey-install"
    mkdir -p $TEMP_DIR
    cd $TEMP_DIR
    
    # 下载最新版本
    echo "📥 下载Valkey源码..."
    VALKEY_VERSION="7.2.5"  # 使用稳定版本
    wget "https://github.com/valkey-io/valkey/archive/refs/tags/${VALKEY_VERSION}.tar.gz" -O valkey.tar.gz
    
    if [ $? -ne 0 ]; then
        echo "❌ 下载失败，尝试备用方法..."
        git clone https://github.com/valkey-io/valkey.git
        cd valkey
    else
        tar -xzf valkey.tar.gz
        cd valkey-${VALKEY_VERSION}
    fi
    
    # 编译
    echo "🔨 编译Valkey..."
    make
    
    if [ $? -ne 0 ]; then
        echo "❌ 编译失败"
        return 1
    fi
    
    # 安装
    echo "📦 安装Valkey..."
    sudo make install
    
    if [ $? -ne 0 ]; then
        echo "❌ 安装失败"
        return 1
    fi
    
    # 清理
    cd /
    rm -rf $TEMP_DIR
    
    echo "✅ Valkey安装完成"
    return 0
}

# 使用包管理器安装（如果可用）
install_valkey_package() {
    echo "🔧 尝试使用包管理器安装Valkey..."
    
    case $PACKAGE_MANAGER in
        "apt")
            # Ubuntu/Debian - 添加Valkey仓库
            echo "📥 添加Valkey仓库..."
            curl -fsSL https://download.valkey.io/valkey-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/valkey-archive-keyring.gpg
            echo "deb [signed-by=/usr/share/keyrings/valkey-archive-keyring.gpg] https://download.valkey.io/debian $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/valkey.list
            sudo apt update
            sudo apt install -y valkey
            ;;
        "yum"|"dnf")
            # CentOS/RHEL/Fedora - 从源码安装
            echo "⚠️  包管理器暂不支持Valkey，使用源码安装"
            return 1
            ;;
        "brew")
            # macOS - 使用Homebrew
            echo "📥 使用Homebrew安装Valkey..."
            brew tap valkey-io/valkey
            brew install valkey
            ;;
        *)
            echo "❌ 不支持的包管理器"
            return 1
            ;;
    esac
    
    return $?
}

# 创建配置文件
create_valkey_config() {
    echo "📝 创建Valkey配置文件..."
    
    # 配置文件路径
    CONFIG_DIR="/etc/valkey"
    CONFIG_FILE="$CONFIG_DIR/valkey.conf"
    
    # 创建配置目录
    sudo mkdir -p $CONFIG_DIR
    
    # 创建配置文件
    sudo tee $CONFIG_FILE > /dev/null <<EOF
# Valkey配置文件
# 基于Redis配置，适配Valkey

# 网络配置
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 300

# 通用配置
daemonize yes
pidfile /var/run/valkey/valkey-server.pid
loglevel notice
logfile /var/log/valkey/valkey-server.log

# 数据库配置
databases 16
save 900 1
save 300 10
save 60 10000

# 持久化配置
dir /var/lib/valkey
dbfilename dump.rdb
rdbcompression yes
rdbchecksum yes

# 内存管理
maxmemory 256mb
maxmemory-policy allkeys-lru

# 安全配置
# requirepass your_secure_password_here

# 客户端配置
maxclients 10000

# 慢查询日志
slowlog-log-slower-than 10000
slowlog-max-len 128

# 延迟监控
latency-monitor-threshold 100
EOF

    echo "✅ 配置文件创建完成: $CONFIG_FILE"
}

# 创建系统服务
create_systemd_service() {
    echo "📝 创建systemd服务..."
    
    sudo tee /etc/systemd/system/valkey.service > /dev/null <<EOF
[Unit]
Description=Valkey In-Memory Data Store
After=network.target

[Service]
User=valkey
Group=valkey
ExecStart=/usr/local/bin/valkey-server /etc/valkey/valkey.conf
ExecStop=/usr/local/bin/valkey-cli shutdown
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

    # 重新加载systemd
    sudo systemctl daemon-reload
    
    echo "✅ systemd服务创建完成"
}

# 创建用户和目录
setup_valkey_user() {
    echo "👤 设置Valkey用户和目录..."
    
    # 创建valkey用户
    if ! id "valkey" &>/dev/null; then
        sudo useradd --system --home /var/lib/valkey --shell /bin/false valkey
        echo "✅ 创建valkey用户"
    else
        echo "✅ valkey用户已存在"
    fi
    
    # 创建必要目录
    sudo mkdir -p /var/lib/valkey
    sudo mkdir -p /var/log/valkey
    sudo mkdir -p /var/run/valkey
    
    # 设置权限
    sudo chown -R valkey:valkey /var/lib/valkey
    sudo chown -R valkey:valkey /var/log/valkey
    sudo chown -R valkey:valkey /var/run/valkey
    
    echo "✅ 目录和权限设置完成"
}

# 启动Valkey服务
start_valkey() {
    echo "🚀 启动Valkey服务..."
    
    if command -v systemctl &> /dev/null; then
        sudo systemctl enable valkey
        sudo systemctl start valkey
        
        # 检查状态
        if sudo systemctl is-active --quiet valkey; then
            echo "✅ Valkey服务启动成功"
            return 0
        else
            echo "❌ Valkey服务启动失败"
            sudo systemctl status valkey
            return 1
        fi
    else
        # 直接启动
        valkey-server /etc/valkey/valkey.conf
        echo "✅ Valkey服务已启动"
        return 0
    fi
}

# 测试Valkey
test_valkey() {
    echo "🧪 测试Valkey连接..."
    
    sleep 2  # 等待服务启动
    
    if valkey-cli ping | grep -q "PONG"; then
        echo "✅ Valkey连接测试成功"
        valkey-cli info server | head -10
        return 0
    else
        echo "❌ Valkey连接测试失败"
        return 1
    fi
}

# 主安装流程
main() {
    echo "开始安装Valkey..."
    echo ""
    
    # 检查当前状态
    check_result=$(check_valkey_installed)
    check_code=$?
    
    if [ $check_code -eq 0 ]; then
        echo "Valkey已安装，跳过安装步骤"
    elif [ $check_code -eq 1 ]; then
        echo ""
        read -p "检测到Redis，是否继续安装Valkey? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "取消安装"
            exit 0
        fi
    fi
    
    # 安装依赖
    install_dependencies
    
    # 尝试包管理器安装
    if ! install_valkey_package; then
        echo "包管理器安装失败，尝试源码安装..."
        if ! install_valkey_from_source; then
            echo "❌ Valkey安装失败"
            exit 1
        fi
    fi
    
    # 设置用户和目录
    setup_valkey_user
    
    # 创建配置文件
    create_valkey_config
    
    # 创建系统服务
    if command -v systemctl &> /dev/null; then
        create_systemd_service
    fi
    
    # 启动服务
    start_valkey
    
    # 测试连接
    test_valkey
    
    echo ""
    echo "🎉 Valkey安装完成！"
    echo ""
    echo "📋 管理命令:"
    echo "  启动服务: sudo systemctl start valkey"
    echo "  停止服务: sudo systemctl stop valkey"
    echo "  重启服务: sudo systemctl restart valkey"
    echo "  查看状态: sudo systemctl status valkey"
    echo "  连接测试: valkey-cli ping"
    echo ""
    echo "📁 重要文件:"
    echo "  配置文件: /etc/valkey/valkey.conf"
    echo "  日志文件: /var/log/valkey/valkey-server.log"
    echo "  数据目录: /var/lib/valkey"
    echo ""
    echo "🔧 下一步:"
    echo "  1. 运行: python setup_valkey_complete.py"
    echo "  2. 配置Flask应用使用Valkey"
    echo "  3. 重启Flask应用"
}

# 运行主函数
main
