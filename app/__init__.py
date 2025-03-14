# __init__.py:
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)

    # 配置代码保持不变...
    WIN = sys.platform.startswith('win')
    prefix = 'sqlite:///' if WIN else 'sqlite:////'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(
        os.path.dirname(app.root_path), os.getenv('DATABASE_FILE', 'data.db')
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 初始化扩展
    db.init_app(app)
    migrate = Migrate(app, db)  # 新增此行
    login_manager.init_app(app)

    # 用户加载器
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    # 上下文处理器
    @app.context_processor
    def inject_user():
        from .models import User
        user = User.query.first()
        return dict(user=user)

    # 注册蓝图（关键修复！）
    with app.app_context():
        from .views import bp as views_bp
        from .errors import bp as errors_bp
        from .commands import bp as commands_bp

        app.register_blueprint(views_bp)
        app.register_blueprint(errors_bp)
        app.register_blueprint(commands_bp)

    return app