from flask import Blueprint, render_template, request, session
import time

# 独立定义错误处理蓝图
bp = Blueprint('errors', __name__)

@bp.app_errorhandler(404)
def page_not_found(e):
    """
    404 错误处理
    说明：错误路径应尽量减少副作用，不做数据库查询，避免在异常情况下加重系统负载。
    模板如需用户信息，请自行通过 current_user 获取；此处不强行注入。
    """
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(e):
    """
    500 错误处理
    说明：与 404 一致，不做任何 DB 访问，确保错误路径最小副作用。
    """
    return render_template('errors/500.html'), 500

@bp.app_errorhandler(429)
def too_many_requests(e):
    """
    429 限流错误处理
    说明：进入/刷新该页面即开始新的 60 秒倒计时；不做 DB 查询，
    仅使用 session 记录限流状态，由业务端自行在通过验证码后置 rl_verified=True。
    """

    now = int(time.time())
    # 进入/刷新429页面即开始新的60秒倒计时
    session['rl_locked_until'] = now + 60
    session['rl_verified'] = False

    return render_template('errors/429.html', retry_after=60), 429