#!/bin/bash

# 设置Flask应用程序入口点
export FLASK_APP=app

# 定义成员目录路径
MEMBERS_DIR="app/static/members"

echo "==============================="
echo "Member Import Script"
echo "==============================="
echo "FLASK_APP = $FLASK_APP"
echo "Members directory: $MEMBERS_DIR"
echo "==============================="

# 初始化计数器
import_count=0
error_count=0
skip_count=0

# 检查成员目录是否存在
if [ ! -d "$MEMBERS_DIR" ]; then
    echo "Error: Members directory not found at $MEMBERS_DIR"
    exit 1
fi

# 遍历成员目录下的所有子目录
for dir in "$MEMBERS_DIR"/*/ ; do
    # 检查是否为目录，不是则跳过
    [ -d "$dir" ] || continue

    # 获取目录名（去掉路径和尾部斜杠）
    member_name=$(basename "$dir")

    # 构建info.json和photo.jpg的完整路径
    info_file="${dir}info.json"
    photo_file="${dir}photo.jpg"

    # 检查info.json文件是否存在
    if [ -f "$info_file" ]; then
        # 使用flask命令导入成员信息
        echo "Importing member: $member_name"
        if flask import-member --info "$info_file" --photo "$photo_file"; then
            echo "✓ Successfully imported member: $member_name"
            ((import_count++))
        else
            echo "✗ Failed to import member: $member_name"
            ((error_count++))
        fi
    else
        echo "⚠ Info file not found at $info_file, skipping $member_name"
        ((skip_count++))
    fi
done

# 显示结果摘要
echo "==============================="
echo "Member import summary:"
echo "Successfully imported: $import_count members"
echo "Failed to import: $error_count members"
echo "Skipped: $skip_count members"
echo "==============================="

# 根据结果设置退出码
if [ $error_count -eq 0 ]; then
    echo "Member import completed successfully!"
    exit 0
else
    echo "Member import completed with errors!"
    exit 1
fi