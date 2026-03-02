# errors.py:
from flask import Blueprint

# 独立定义错误处理蓝图
# 注意：错误处理器已统一在 app/__init__.py 的 create_app() 中通过 @app.errorhandler 注册，
# 避免两处同时注册同一错误码导致行为不确定。
# 此蓝图保留用于可能的错误相关路由扩展，但不再注册 app_errorhandler。
bp = Blueprint('errors', __name__)
