#!/bin/bash
# 创建或更新管理员用户的脚本

# 设置Flask环境变量
export FLASK_APP=app

# 显示调试信息
echo "==============================="
echo "Admin User Creation Script"
echo "==============================="
echo "FLASK_APP = $FLASK_APP"
echo "Current directory: $(pwd)"
echo "NOTE: You will be prompted for username, email, and password"
echo "==============================="

# 确保数据库已初始化
echo "Ensuring database is initialized..."
flask initdb
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize database."
    exit 1
fi

# 运行邮箱字段迁移（如果需要）
echo "Checking and running email field migration if needed..."
flask migrate-users-email
if [ $? -ne 0 ]; then
    echo "Warning: Email migration may have encountered issues."
    echo "You might need to recreate the database with 'flask initdb --drop' if problems persist."
fi

# 运行管理员创建命令
echo "Creating/updating admin user..."
flask admin

# Check if command was successful
if [ $? -eq 0 ]; then
    echo "==============================="
    echo "Admin account created/updated successfully!"
    echo "==============================="
else
    echo "==============================="
    echo "Error: Failed to create/update admin account."
    echo "==============================="
    exit 1
fi
