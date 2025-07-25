#!/bin/bash


# ./initdb.sh              # 正常模式，保留现有数据库结构
# ./initdb.sh --drop       # 删除并重建数据库（需确认）
# ./initdb.sh --force      # 强制删除并重建数据库（无需确认）
# ./initdb.sh --test       # 使用测试数据集
# ./initdb.sh --force --test  # 强制重建并使用测试数据集


# 虚拟环境由调用脚本管理

# 设置默认选项
DROP_OPTION=""
FORCE_REBUILD=false
TEST_MODE=false
TEST_OPTION=""

# 检查命令行参数
for arg in "$@"
do
    if [ "$arg" == "--drop" ]; then
        echo "WARNING: You are about to DROP all tables and recreate them."
        echo "This will delete ALL existing data in the database."
        read -p "Are you sure you want to continue? (y/n): " confirm
        
        if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
            DROP_OPTION="--drop"
            echo "Proceeding with database drop and recreation..."
        else
            echo "Operation cancelled."
            exit 0
        fi
    fi
    
    if [ "$arg" == "--force" ]; then
        FORCE_REBUILD=true
        DROP_OPTION="--drop"
        echo "Force rebuilding database (no confirmation required)..."
    fi
    
    if [ "$arg" == "--test" ]; then
        TEST_MODE=true
        TEST_OPTION="--test"
        echo "Running in test mode with sample data..."
    fi
done

# 设置JSON目录
if [ "$TEST_MODE" == true ]; then
    # 使用较小的测试数据集
    JSON_DIR="app/static/structures"
else
    # 使用完整的数据集
    JSON_DIR="app/static/materials"
fi

# 设置Flask环境变量
export FLASK_APP="wsgi.py"

# 如果强制重建或选择了drop选项，则先删除数据库文件
if [ "$FORCE_REBUILD" == true ] || [ "$DROP_OPTION" == "--drop" ]; then
    # 查找配置中的数据库文件名
    DB_FILE=$(grep -oP "DATABASE_FILE.*?['\"]\\K[^'\"]*" app/__init__.py || echo "app.db")
    
    # 如果找不到，使用默认值
    if [ -z "$DB_FILE" ]; then
        DB_FILE="app.db"
    fi
    
    # 构建完整数据库路径（在instance目录下）
    DB_PATH="instance/$DB_FILE"
    
    # 如果数据库文件存在，则删除它
    if [ -f "$DB_PATH" ]; then
        echo "Removing existing database file: $DB_PATH"
        rm "$DB_PATH"
    fi
    
    echo "Database file removed. Will be recreated with new schema."
fi

# 初始化数据库并导入数据
echo "Running database initialization..."
flask initdb $DROP_OPTION

# 数据库创建后导入数据
if [ $? -eq 0 ]; then
    echo "Database schema created successfully."
    
    # 导入材料数据
    if [ -n "$TEST_OPTION" ]; then
        echo "Importing test data..."
        flask import-materials --dir="$JSON_DIR" $TEST_OPTION
    else
        echo "Importing material data..."
        flask import-materials --dir="$JSON_DIR"
    fi
    
    # 验证数据导入是否成功
    if [ $? -eq 0 ]; then
        echo "Data import completed successfully."

        # 分析能带数据并生成band.json文件
        echo "Analyzing band data and generating band.json files..."
        flask analyze-bands

        if [ $? -eq 0 ]; then
            echo "Band analysis completed successfully."
        else
            echo "WARNING: Band analysis finished with errors."
        fi
    else
        echo "WARNING: Data import finished with errors."
    fi

    echo "Database initialization completed."
else
    echo "ERROR: Database initialization failed!"
    exit 1
fi

# 虚拟环境由调用脚本管理