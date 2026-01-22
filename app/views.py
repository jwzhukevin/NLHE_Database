# views.py
# 视图函数模块（精简版）：仅保留全局中间件、模板过滤器和API端点
# 主要路由已迁移至 blueprints/ 目录下的独立模块

from flask import Blueprint, request, jsonify, current_app, session
from flask_babel import _
from . import db
from .models import Material

# 创建名为 'views' 的蓝图（保留用于全局过滤器和API端点）
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


# ==================== API 端点 ====================

@bp.route('/api/band-config')
def get_band_config():
    """获取能带分析配置，供前端使用"""
    try:
        from .services import BandAnalysisConfig
        config = {
            'fermiLevel': BandAnalysisConfig.DEFAULT_FERMI_LEVEL,
            'tolerance': BandAnalysisConfig.FERMI_TOLERANCE,
            'metalThreshold': BandAnalysisConfig.METAL_THRESHOLD,
            'semimetalThreshold': BandAnalysisConfig.SEMIMETAL_THRESHOLD,
            'semiconductorThreshold': BandAnalysisConfig.SEMICONDUCTOR_THRESHOLD,
            'energyPrecision': BandAnalysisConfig.ENERGY_PRECISION
        }
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get band config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/materials/update-band-gap', methods=['POST'])
def update_band_gap():
    """
    [Deprecated 20251001] 写操作端点已禁用：只读模式
    """
    return jsonify({
        'success': False,
        'error': 'Write operations are disabled (read-only mode).',
        'status': 410
    }), 410


@bp.route('/set-language')
def set_language():
    """
    设置界面语言（国际化）：
    - 读取查询参数 ?lang=en/zh
    - 将语言首选项写入 session 与 cookie（30 天）
    - 重定向回来源页
    """
    from flask import redirect, url_for, flash
    
    supported = current_app.config.get('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
    lang = (request.args.get('lang') or '').strip()
    if lang not in supported:
        flash(_('Unsupported language.'), 'error')
        return redirect(url_for('main.landing'))

    session['lang'] = lang
    resp = redirect(request.referrer or url_for('main.landing'))
    resp.set_cookie('lang', lang, max_age=30*24*3600, samesite='Lax')
    return resp


@bp.route('/i18n-debug')
def i18n_debug():
    """
    返回当前请求的国际化判定信息，便于调试
    """
    from flask_babel import get_locale
    
    try:
        current_locale = str(get_locale()) if get_locale() else None
    except Exception:
        current_locale = None

    supported = current_app.config.get('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
    best_match = request.accept_languages.best_match(supported)

    data = {
        'current_locale': current_locale,
        'session_lang': session.get('lang'),
        'cookie_lang': request.cookies.get('lang'),
        'args_lang': request.args.get('lang'),
        'accept_language_raw': request.headers.get('Accept-Language'),
        'best_match': best_match,
        'supported_locales': supported,
    }
    return jsonify(data)


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
