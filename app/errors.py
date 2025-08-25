from flask import Blueprint, render_template, request, session
from .models import User
import time

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

@bp.app_errorhandler(429)
def too_many_requests(e):
    """处理 429 限流错误：要求"等待+验证码"后才能恢复访问。"""
    try:
        user = User.query.first()
    except Exception:
        user = None

    now = int(time.time())
    # 进入/刷新429页面即开始新的60秒倒计时
    session['rl_locked_until'] = now + 60
    session['rl_verified'] = False

    return render_template('errors/429.html', user=user, retry_after=60), 429