#!/bin/bash

set -e

# 清理函数：确保虚拟环境正确退出
cleanup() {
    echo "Cleaning up..."
    if command -v deactivate &> /dev/null; then
        deactivate
        echo "✓ Virtual environment deactivated"
    fi
}

# 设置陷阱，确保脚本异常退出时也能清理
trap cleanup EXIT

# 记录开始时间
START_TIME=$(date +%s)
echo "========================================"
echo "NLHE Database Initialization Script"
echo "Started at: $(date)"
echo "========================================"

# 激活Python虚拟环境
echo "Activating NLHE virtual environment..."
if [ -d "NLHE/bin" ]; then
    source NLHE/bin/activate
    echo "✓ Virtual environment activated successfully"
elif [ -d "NLHE/Scripts" ]; then
    # Windows环境
    source NLHE/Scripts/activate
    echo "✓ Virtual environment activated successfully (Windows)"
else
    echo "⚠ Warning: Virtual environment directory not found"
    echo "Please ensure NLHE virtual environment exists"
    exit 1
fi

# 检查是否有--noinput参数
NOINPUT=false
for arg in "$@"; do
    if [ "$arg" == "--noinput" ]; then
        NOINPUT=true
    fi
done

# 1. 数据库备份
DB_PATH="app/data/database.db"
if [ -f "$DB_PATH" ]; then
    backup_file="backup/database_$(date +%Y%m%d_%H%M%S).db"
    mkdir -p backup
    cp "$DB_PATH" "$backup_file"
    echo -e "\033[33m[Backup] Database automatically backed up to $backup_file\033[0m"
fi

# 2. 数据库初始化
echo -e "\033[36m[1/4] Rebuilding database (executing ./initdb.sh --drop)...\033[0m"
if $NOINPUT; then
    yes | ./initdb.sh --drop
else
    ./initdb.sh --drop
fi
if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] Database initialization successful.\033[0m"
else
    echo -e "\033[31m[Failed] Database initialization failed, terminating.\033[0m"
    exit 1
fi

# 3. 管理员初始化
echo -e "\033[36m[2/4] Initializing admin information (executing ./admin.sh)...\033[0m"
if $NOINPUT; then
    echo -e "\033[33m[Note] In --noinput mode, please ensure admin.sh supports automatic input, otherwise manual input is still required.\033[0m"
fi
./admin.sh
if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] Admin initialization successful.\033[0m"
else
    echo -e "\033[31m[Failed] Admin initialization failed, terminating.\033[0m"
    exit 1
fi

# 4. 用户数据初始化
echo -e "\033[36m[3/4] Initializing user data (executing ./users.sh)...\033[0m"
./users.sh
if [ $? -eq 0 ]; then
    echo -e "\033[32m[Success] User data initialization successful.\033[0m"
else
    echo -e "\033[31m[Failed] User data initialization failed, terminating.\033[0m"
    exit 1
fi

# 5. 成员信息导入
echo -e "\033[36m[4/4] Importing member information (executing ./import_members.sh)...\033[0m"
if [ -f "./import_members.sh" ]; then
    ./import_members.sh
    if [ $? -eq 0 ]; then
        echo -e "\033[32m[Success] Member information import successful.\033[0m"
    else
        echo -e "\033[33m[Warning] Member information import completed with warnings.\033[0m"
    fi
else
    echo -e "\033[33m[Info] import_members.sh not found, skipping member import.\033[0m"
fi

# 计算执行时间
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo "========================================"
echo -e "\033[1;32mWebsite initialization completed successfully!\033[0m"
echo "Completed at: $(date)"
echo "Total execution time: ${MINUTES}m ${SECONDS}s"
echo "========================================"
# 虚拟环境将通过trap清理函数自动退出