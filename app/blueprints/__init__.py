# -*- coding: utf-8 -*-
"""
蓝图注册中心
将原views.py拆分为多个独立模块，按功能域组织路由
"""
from .main import main_bp
from .auth import auth_bp
from .members import members_bp
from .chat_api import chat_api_bp
from .database.functional import functional_materials_bp
from .search_api import search_api_bp

__all__ = [
    'main_bp',
    'auth_bp', 
    'members_bp',
    'chat_api_bp',
    'functional_materials_bp',
    'search_api_bp',
    'register_blueprints',
]


def register_blueprints(app):
    """
    注册所有拆分后的蓝图到Flask应用
    
    参数:
        app: Flask应用实例
    """
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(chat_api_bp)
    app.register_blueprint(functional_materials_bp)
    app.register_blueprint(search_api_bp)
    
    app.logger.info("已注册拆分蓝图: main, auth, members, chat_api, functional_materials, search_api")
