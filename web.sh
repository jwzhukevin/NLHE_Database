#!/bin/bash

# NLHE数据库系统启动脚本
# 功能：启动Flask开发服务器

echo "🚀 启动NLHE数据库系统..."

# 激活虚拟环境（如果存在）
if [ -d "NLHE" ]; then
    echo "🔧 激活虚拟环境..."
    source NLHE/bin/activate
    if [ $? -eq 0 ]; then
        echo "✅ 虚拟环境激活成功"
    else
        echo "⚠️  虚拟环境激活失败，继续使用系统Python"
    fi
fi

# 设置环境变量
export FLASK_APP=run.py
export FLASK_ENV=development

# 显示启动信息
echo "📋 启动信息:"
echo "   应用: $FLASK_APP"
echo "   环境: $FLASK_ENV"
echo "   模式: 调试模式"
echo "   地址: http://127.0.0.1:5000"
echo ""
echo "🔒 安全提示: 当前为开发模式，生产环境请使用WSGI服务器"
echo ""

# 启动Flask应用
flask run --debug --host=0.0.0.0 --port=5000