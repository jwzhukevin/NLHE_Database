#!/bin/bash
# 设置可执行权限: chmod +x app/static/users/users.sh

# 定义变量
export FLASK_APP=app
USERS_FILE="app/static/users/users.dat"

echo "==============================="
echo "User Initialization Script"
echo "==============================="
echo "FLASK_APP = $FLASK_APP"
echo "Current directory: $(pwd)"
echo "Users data file: $USERS_FILE"

# 检查用户数据文件是否存在
if [ ! -f "$USERS_FILE" ]; then
    echo "Error: User data file not found at $USERS_FILE"
    exit 1
fi

# 显示用户数据文件内容
echo "==============================="
echo "Users to be initialized:"
grep -v "^#" "$USERS_FILE" | grep -v "^$"
echo "==============================="

# 确保数据库包含用户表和最新的角色字段
echo "Ensuring database contains the latest schema..."
flask initdb
if [ $? -ne 0 ]; then
    echo "Error: Failed to initialize database."
    exit 1
fi

# 初始化用户
echo "Initializing users..."
SUCCESS_COUNT=0
FAILURE_COUNT=0

# 方法1: 使用init-users命令一次性导入所有用户
echo "Attempting to initialize all users at once..."
flask init-users
RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo "==============================="
    echo "User initialization completed successfully!"
    echo "==============================="
    exit 0
else
    echo "==============================="
    echo "Failed to initialize users using init-users command."
    echo "Trying to add users one by one..."
    echo "==============================="
fi

# 方法2: 逐行读取用户数据文件并添加用户
while IFS=: read -r username password role || [ -n "$username" ]; do
    # 跳过注释行和空行
    [[ "$username" =~ ^#.*$ || -z "$username" ]] && continue
    
    echo "Adding user: $username with role: $role"
    # 使用Flask命令行添加用户
    flask user-add "$username" "$password" "$role"
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully added user: $username"
        ((SUCCESS_COUNT++))
    else
        echo "✗ Failed to add user: $username"
        ((FAILURE_COUNT++))
    fi
done < "$USERS_FILE"

# 显示结果摘要
echo "==============================="
if [ $FAILURE_COUNT -eq 0 ]; then
    echo "User initialization completed successfully!"
    echo "Total users added: $SUCCESS_COUNT"
    echo "==============================="
    exit 0
else
    echo "User initialization completed with errors!"
    echo "Successfully added: $SUCCESS_COUNT users"
    echo "Failed to add: $FAILURE_COUNT users"
    echo "==============================="
    exit 1
fi 