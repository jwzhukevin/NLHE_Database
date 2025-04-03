# wsgi.py
import os
from dotenv import load_dotenv

# 加载环境变量（需先安装 python-dotenv）
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# 通过工厂函数创建应用实例
from app import create_app
app = create_app()

# 生产环境部署时需要以下配置（例如使用 Gunicorn）
if __name__ == "__main__":
    # 当直接运行该文件时启动开发服务器
    app.run(host='0.0.0.0', port=5000)
