#!/bin/bash

set -e

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
    echo -e "\033[33m[备份] 已自动备份数据库到 $backup_file\033[0m"
fi

# 2. 数据库初始化
echo -e "\033[36m[1/3] 正在重建数据库（执行 ./initdb.sh --drop ）...\033[0m"
if $NOINPUT; then
    yes | ./initdb.sh --drop
else
    ./initdb.sh --drop
fi
if [ $? -eq 0 ]; then
    echo -e "\033[32m[成功] 数据库初始化成功。\033[0m"
else
    echo -e "\033[31m[失败] 数据库初始化失败，终止。\033[0m"
    exit 1
fi

# 3. 管理员初始化
echo -e "\033[36m[2/3] 正在初始化管理员信息（执行 ./admin.sh ）...\033[0m"
if $NOINPUT; then
    echo -e "\033[33m[提示] --noinput模式下请确保admin.sh支持自动输入，否则仍需人工输入。\033[0m"
fi
./admin.sh
if [ $? -eq 0 ]; then
    echo -e "\033[32m[成功] 管理员初始化成功。\033[0m"
else
    echo -e "\033[31m[失败] 管理员初始化失败，终止。\033[0m"
    exit 1
fi

# 4. 用户数据初始化
echo -e "\033[36m[3/3] 正在初始化用户数据（执行 ./users.sh ）...\033[0m"
./users.sh
if [ $? -eq 0 ]; then
    echo -e "\033[32m[成功] 用户静态资源初始化成功。\033[0m"
else
    echo -e "\033[31m[失败] 用户静态资源初始化失败，终止。\033[0m"
    exit 1
fi

echo -e "\033[1;32m网站初始化全部完成！\033[0m" 