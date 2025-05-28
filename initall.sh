#!/bin/bash

# 网站初始化整合脚本
# 依次执行数据库重建、管理员初始化、用户静态资源初始化

echo "[1/3] 正在重建数据库（执行 ./initdb.sh --drop ）..."
./initdb.sh --drop
if [ $? -ne 0 ]; then
    echo "数据库初始化失败，终止后续操作。"
    exit 1
fi

echo "[2/3] 正在初始化管理员信息（执行 ./admin.sh ）..."
./admin.sh
if [ $? -ne 0 ]; then
    echo "管理员初始化失败，终止后续操作。"
    exit 1
fi

echo "[3/3] 正在初始化用户静态资源（执行 app/static/users/users.sh ）..."
./app/static/users/users.sh
if [ $? -ne 0 ]; then
    echo "用户静态资源初始化失败。"
    exit 1
fi

echo "网站初始化全部完成！" 