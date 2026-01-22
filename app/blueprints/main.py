# -*- coding: utf-8 -*-
"""
主页蓝图
路由：落地页、语言切换、轮播图API
"""
from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify, current_app, flash
from flask_babel import _
import os

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def landing():
    """
    网站落地页：展示网站特性与功能概览。
    """
    return render_template('main/landing.html')


@main_bp.route('/api/landing-pictures')
def api_landing_pictures():
    """返回落地页轮播图列表（static/Picture/ 下的图片URL）。"""
    try:
        static_root = os.path.join(current_app.root_path, 'static', 'Picture')
        exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
        files = []
        if os.path.isdir(static_root):
            for name in sorted(os.listdir(static_root)):
                lower = name.lower()
                _, ext = os.path.splitext(lower)
                if ext in exts:
                    files.append(url_for('static', filename=f'Picture/{name}'))
        return jsonify({'images': files})
    except Exception as e:
        current_app.logger.error(f"/api/landing-pictures error: {e}")
        return jsonify({'images': []})


@main_bp.route('/set-language')
def set_language():
    """
    设置界面语言（国际化）：
    - 读取查询参数 ?lang=en/zh
    - 将语言首选项写入 session 与 cookie（30 天）
    - 重定向回来源页，若无来源则回到落地页
    """
    # 读取支持语言
    supported = current_app.config.get('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
    # 获取目标语言
    lang = (request.args.get('lang') or '').strip()
    if lang not in supported:
        flash(_('Unsupported language.'), 'error')
        return redirect(url_for('main.landing'))

    # 写入 session
    session['lang'] = lang

    # 构造重定向响应并设置 cookie（30 天）
    resp = redirect(request.referrer or url_for('main.landing'))
    resp.set_cookie('lang', lang, max_age=30*24*3600, samesite='Lax')
    return resp


@main_bp.route('/i18n-debug')
def i18n_debug():
    """
    返回当前请求的国际化判定信息，便于调试：
    - current_locale: Flask-Babel 的当前语言
    - session.lang: 会话中的语言字段
    - cookie.lang: Cookie 中的语言字段
    - args.lang: 查询参数中的语言字段
    - accept_language_raw: 浏览器请求头
    - best_match: 基于受支持语言的最佳匹配
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
