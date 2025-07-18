from flask import Blueprint, render_template
from .models import User

# 独立定义错误处理蓝图
bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def page_not_found(e):
    try:
        user = User.query.first()
    except Exception:
        user = None
    return render_template('errors/404.html', user=user), 404

@bp.app_errorhandler(500)
def internal_error(e):
    try:
        user = User.query.first()
    except Exception:
        user = None
    return render_template('errors/500.html', user=user), 500