# __init__.py:
# 应用初始化模块
# 本文件实现了Flask应用工厂模式，用于创建和配置Flask应用实例，
# 注册扩展、蓝图和路由，设置数据库连接等

# 导入系统模块（处理路径和操作系统检测）
import os  # 用于操作系统路径处理（如拼接数据库路径）
import sys  # 用于检测操作系统平台（Windows/Linux）

# 导入 Flask 核心模块和扩展库
from flask import Flask  # Flask 应用核心类
from flask_sqlalchemy import SQLAlchemy  # ORM 数据库扩展
from flask_login import LoginManager  # 用户登录管理扩展
from flask_migrate import Migrate  # 数据库迁移工具

# 初始化全局扩展对象（此时未绑定应用实例）
# 使用延迟绑定模式，支持应用工厂模式
db = SQLAlchemy()  # 创建 SQLAlchemy 实例，后续通过 init_app() 绑定应用
login_manager = LoginManager()  # 创建登录管理实例，支持多应用实例场景

def create_app():
    """
    应用工厂函数：创建并配置 Flask 应用实例
    
    工厂模式好处:
        1. 便于测试（可创建多个独立实例）
        2. 支持不同配置的多环境部署
        3. 避免循环导入问题
        4. 符合蓝图架构模式
    
    返回:
        配置完成的Flask应用实例
    """
    app = Flask(__name__)  # 实例化 Flask 应用，__name__ 用于确定根目录路径

    # --- 配置部分 ---
    # 动态生成数据库 URI（适配不同操作系统）
    WIN = sys.platform.startswith('win')  # 检测是否为 Windows 系统
    prefix = 'sqlite:///' if WIN else 'sqlite:////'  # Windows 用 3 斜杠，Linux 用 4 斜杠
    
    # 从环境变量读取密钥（生产环境推荐），默认值 'dev' 用于开发
    # SECRET_KEY用于会话安全和CSRF保护
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    
    # 动态构建数据库路径（基于应用根目录）
    # SQLite数据库文件存放在项目根目录下
    app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(
        os.path.dirname(app.root_path),  # 获取应用根目录的父目录（项目根目录）
        os.getenv('DATABASE_FILE', 'data.db')  # 从环境变量读取数据库文件名，默认 'data.db'
    )
    # 禁用SQLAlchemy的事件通知系统以提高性能
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 禁用 SQLAlchemy 事件系统以提升性能

    # --- 扩展初始化 ---
    # 延迟绑定模式：先创建扩展实例，再与应用关联
    db.init_app(app)  # 延迟绑定 SQLAlchemy 到应用（工厂模式核心）
    migrate = Migrate(app, db)  # 初始化数据库迁移工具（生成迁移脚本）
    login_manager.init_app(app)  # 绑定登录管理到应用

    # --- 用户加载器（必须实现） ---
    # Flask-Login要求实现的回调函数，用于从会话cookie恢复用户
    @login_manager.user_loader
    def load_user(user_id):
        """
        根据用户 ID 加载用户对象（Flask-Login 要求）
        
        参数:
            user_id: 从会话中恢复的用户ID（字符串类型）
            
        返回:
            用户对象，未找到则返回None
        """
        from .models import User  # 延迟导入避免循环依赖
        return User.query.get(int(user_id))  # 查询数据库并返回用户实例

    # --- 模板上下文处理器 ---
    # 向所有模板注入全局变量，避免在每个视图函数中重复传递
    @app.context_processor
    def inject_user():
        """
        向所有模板注入全局变量（例如当前用户）
        
        返回:
            字典，包含要注入模板的全局变量
        """
        from .models import User
        user = User.query.first()  # 示例：注入第一个用户（可替换为实际逻辑）
        return dict(user=user)  # 模板中可通过 {{ user }} 访问

    # --- 初始化格式化ID ---
    def init_formatted_ids():
        """
        初始化材料格式化ID:
        1. 确保数据库中存在formatted_id列
        2. 为所有空的格式化ID赋值
        """
        from sqlalchemy import inspect, text
        from sqlalchemy.exc import SQLAlchemyError
        
        try:
            # 导入Material模型
            from .models import Material
            
            # 检查formatted_id列是否存在
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('material')]
            
            # 如果不存在formatted_id列，添加它（不带UNIQUE约束）
            if 'formatted_id' not in columns:
                # SQLite不支持直接添加带UNIQUE约束的列，所以先添加普通列
                db.engine.execute("ALTER TABLE material ADD COLUMN formatted_id VARCHAR(20)")
                app.logger.info("已添加formatted_id列到material表")
            
            # 更新所有没有格式化ID的记录
            materials = Material.query.filter(Material.formatted_id.is_(None)).all()
            count = 0
            
            for material in materials:
                material.formatted_id = f"IMR-{material.id:08d}"
                count += 1
            
            if count > 0:
                db.session.commit()
                app.logger.info(f"已更新 {count} 条材料记录的格式化ID")
            
            # 尝试添加唯一索引（如果不存在）
            try:
                # 检查索引是否存在
                indices = inspector.get_indexes('material')
                has_index = any(idx.get('name') == 'ix_material_formatted_id' for idx in indices)
                
                if not has_index:
                    # 创建唯一索引
                    db.engine.execute(text("CREATE UNIQUE INDEX ix_material_formatted_id ON material (formatted_id)"))
                    app.logger.info("已为formatted_id列创建唯一索引")
            except SQLAlchemyError as e:
                # 如果创建索引失败，记录错误但不终止应用启动
                app.logger.warning(f"创建唯一索引失败: {str(e)}")
        
        except SQLAlchemyError as e:
            app.logger.error(f"初始化格式化ID时发生错误: {str(e)}")
            db.session.rollback()
        except Exception as e:
            app.logger.error(f"初始化格式化ID时发生未知错误: {str(e)}")

    # --- 蓝图注册（模块化路由） ---
    # 使用应用上下文确保数据库操作在正确的环境中执行
    with app.app_context():  # 确保在应用上下文中操作（避免上下文缺失错误）
        # 导入各个功能模块的蓝图
        from .views import bp as views_bp  # 导入主视图蓝图
        from .errors import bp as errors_bp  # 导入错误处理蓝图
        from .commands import bp as commands_bp  # 导入 CLI 命令蓝图

        # 注册蓝图到应用实例
        app.register_blueprint(views_bp)  # 注册主视图路由
        app.register_blueprint(errors_bp)  # 注册错误处理路由
        app.register_blueprint(commands_bp)  # 注册命令行接口
        
        # 注册API蓝图（用于提供JSON接口）
        from .api import bp as api_bp
        app.register_blueprint(api_bp)  # 注册API路由

        # 初始化格式化ID
        init_formatted_ids()

    return app  # 返回完全初始化的应用实例