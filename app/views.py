# views.py
# 视图函数模块（精简版）：仅保留模板过滤器和调试路由
# 主要路由已迁移至 blueprints/ 目录下的独立模块：
# - set_language / i18n_debug → blueprints/main.py
# - get_band_config / update_band_gap → blueprints/search_api.py
# - generate_captcha_image / get_client_ip 等工具函数 → utils.py

from flask import Blueprint, request, jsonify, current_app, session
from flask_babel import _

# 创建名为 'views' 的蓝图（仅保留模板过滤器和调试路由）
bp = Blueprint('views', __name__)


# ==================== 模板过滤器 ====================

@bp.app_template_filter('any')
def any_filter(d):
    """
    检查字典是否至少包含一个非空值（用于前端条件渲染）。
    """
    return any(v for v in d.values() if v)


@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """
    生成一个不包含指定键的新字典（用于清理搜索参数）。
    """
    return {k: v for k, v in d.items() if k != exclude_key}


# ==================== 调试路由（仅 Debug 模式可用）====================

@bp.route('/debug/user-status')
def debug_user_status():
    """调试用户登录状态"""
    from flask_login import current_user
    
    if not current_app.debug:
        return "Debug mode only", 403

    status = {
        'is_authenticated': current_user.is_authenticated,
        'session_keys_count': len(session.keys()),
        'remote_addr': request.remote_addr,
    }

    html = f"""
    <html>
    <head><title>用户状态调试</title></head>
    <body>
        <h1>🔍 用户状态调试信息</h1>
        <table border="1">
            {''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in status.items())}
        </table>
        <h2>快速操作</h2>
        <a href="/logout">登出</a> |
        <a href="/login">登录</a> |
        <a href="/database/functional_materials">返回首页</a>
    </body>
    </html>
    """
    return html


@bp.route('/debug/clear-session')
def debug_clear_session():
    """清理所有会话数据（调试用）"""
    from flask import flash, redirect, url_for
    
    if not current_app.debug:
        return "Debug mode only", 403

    session.clear()
    flash(_('Session cleared successfully.'), 'info')
    return redirect(url_for('functional_materials.index'))


@bp.route('/debug/show-403')
def debug_show_403():
    if not current_app.debug:
        return "Debug mode only", 403
    from flask import abort
    abort(403)


@bp.route('/debug/show-404')
def debug_show_404():
    if not current_app.debug:
        return "Debug mode only", 403
    from flask import abort
    abort(404)


@bp.route('/debug/show-410')
def debug_show_410():
    if not current_app.debug:
        return "Debug mode only", 403
    from flask import abort
    abort(410)


@bp.route('/debug/show-429')
def debug_show_429():
    if not current_app.debug:
        return "Debug mode only", 403
    from flask import abort
    abort(429)


@bp.route('/debug/show-500')
def debug_show_500():
    if not current_app.debug:
        return "Debug mode only", 403
    from flask import abort
    abort(500)
