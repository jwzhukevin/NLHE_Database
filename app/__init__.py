# __init__.py:
# 导入系统模块（处理路径和操作系统检测）
import os  # 用于操作系统路径处理（如拼接数据库路径）
import sys  # 用于检测操作系统平台（Windows/Linux）

# 导入 Flask 核心模块和扩展库
from flask import Flask  # Flask 应用核心类
from flask_sqlalchemy import SQLAlchemy  # ORM 数据库扩展
from flask_login import LoginManager  # 用户登录管理扩展
from flask_migrate import Migrate  # 数据库迁移工具

# 初始化全局扩展对象（此时未绑定应用实例）
db = SQLAlchemy()  # 创建 SQLAlchemy 实例，后续通过 init_app() 绑定应用
login_manager = LoginManager()  # 创建登录管理实例，支持多应用实例场景

def create_app():
    """应用工厂函数：创建并配置 Flask 应用实例"""
    app = Flask(__name__)  # 实例化 Flask 应用，__name__ 用于确定根目录路径

    # --- 配置部分 ---
    # 动态生成数据库 URI（适配不同操作系统）
    WIN = sys.platform.startswith('win')  # 检测是否为 Windows 系统
    prefix = 'sqlite:///' if WIN else 'sqlite:////'  # Windows 用 3 斜杠，Linux 用 4 斜杠
    
    # 从环境变量读取密钥（生产环境推荐），默认值 'dev' 用于开发
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    
    # 动态构建数据库路径（基于应用根目录）[1,5]
    app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(
        os.path.dirname(app.root_path),  # 获取应用根目录的父目录（项目根目录）
        os.getenv('DATABASE_FILE', 'data.db')  # 从环境变量读取数据库文件名，默认 'data.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 禁用 SQLAlchemy 事件系统以提升性能

    # --- 扩展初始化 ---
    db.init_app(app)  # 延迟绑定 SQLAlchemy 到应用（工厂模式核心）
    migrate = Migrate(app, db)  # 初始化数据库迁移工具（生成迁移脚本）
    login_manager.init_app(app)  # 绑定登录管理到应用[1]

    # --- 用户加载器（必须实现） ---
    @login_manager.user_loader
    def load_user(user_id):
        """根据用户 ID 加载用户对象（Flask-Login 要求）"""
        from .models import User  # 延迟导入避免循环依赖
        return User.query.get(int(user_id))  # 查询数据库并返回用户实例

    # --- 模板上下文处理器 ---
    @app.context_processor
    def inject_user():
        """向所有模板注入全局变量（例如当前用户）"""
        from .models import User
        user = User.query.first()  # 示例：注入第一个用户（可替换为实际逻辑）
        return dict(user=user)  # 模板中可通过 {{ user }} 访问

    # --- 蓝图注册（模块化路由） ---
    with app.app_context():  # 确保在应用上下文中操作（避免上下文缺失错误）
        from .views import bp as views_bp  # 导入主视图蓝图
        from .errors import bp as errors_bp  # 导入错误处理蓝图
        from .commands import bp as commands_bp  # 导入 CLI 命令蓝图

        # 注册蓝图到应用实例
        app.register_blueprint(views_bp)
        app.register_blueprint(errors_bp)
        app.register_blueprint(commands_bp)

    return app  # 返回完全初始化的应用实例