from flask import Blueprint, render_template
from .models import User

# 独立定义错误处理蓝图
bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def page_not_found(e):
    user = User.query.first()
    return render_template('404.html', user=user), 404

@bp.app_errorhandler(500)
def internal_error(e):
    user = User.query.first()
    return render_template('500.html', user=user), 500