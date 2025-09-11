# view.py:
# 视图函数模块：处理与用户界面相关的所有路由与请求
# 覆盖：主页、材料详情、添加/编辑材料、用户认证等

# 导入所需模块
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify, abort  # Flask 核心模块
from flask_login import login_user, logout_user, login_required, current_user  # 用户认证模块
from flask_babel import _, get_locale  # 国际化：gettext 与当前语言
from sqlalchemy import and_, or_  # 数据库查询条件构造器
from .models import User, Material, BlockedIP, Member  # 自定义数据模型
from . import db, csrf  # 数据库实例与 CSRF 保护实例
import datetime  # 日期与时间处理
import time  # 429 限流倒计时用
import functools  # 装饰器工具
from .material_importer import extract_chemical_formula_from_cif  # 材料数据导入模块
from .chemical_parser import chemical_parser  # 智能化学式解析器
from .search_optimizer import search_cache, QueryOptimizer, performance_monitor, cached_search  # 搜索性能优化
from .band_analyzer import band_analyzer  # 合并后的能带分析器
from .font_manager import FontManager  # 字体管理器
from .captcha_logger import CaptchaLogger  # 验证码日志记录器
import os
import json
import re
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import random, string, io
from .security_utils import log_security_event, sanitize_input, regenerate_session, check_rate_limit
from .auth_manager import LoginStateManager, LoginErrorHandler
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import math

# 尝试导入CSRF豁免装饰器
try:
    from flask_wtf.csrf import exempt as csrf_exempt
    csrf_exempt_available = True
except ImportError:
    csrf_exempt_available = False
    def csrf_exempt(f):
        return f  # 如果没有Flask-WTF，返回原函数

# 创建名为 'views' 的蓝图，用于模块化管理路由
bp = Blueprint('views', __name__)

# 全局拦截：若存在限流挑战且未通过验证码，一律拦截到 /rate-limited
@bp.before_app_request
def enforce_429_challenge():
    try:
        endpoint = (request.endpoint or '')
        # 放行静态资源、错误页、验证码相关端点，避免循环
        if endpoint.startswith('static') or endpoint.startswith('errors.'):
            return
        if endpoint in {'views.captcha429', 'views.verify_captcha_429', 'views.rate_limited'}:
            return
        # 路径级白名单，避免端点名因装饰器导致不匹配
        path = request.path or ''
        if path in {'/captcha429', '/verify_captcha_429', '/rate-limited'}:
            return

        # 已通过验证码则放行
        if bool(session.get('rl_verified', False)):
            return

        # 只要存在限流挑战会话标记（无论是否过期），均需在 429 页面完成验证码
        if 'rl_locked_until' in session:
            return redirect(url_for('views.rate_limited'))

        return
    except Exception:
        # 拦截器出错时不阻断正常流程
        return

@bp.route('/rate-limited')
def rate_limited():
    """
    固定的限流页面：进入即重置 60 秒，并渲染 429 模板。

    说明：错误路径应尽量减少副作用，此处不做数据库查询，仅使用 session 记录限制窗口与验证码通过状态。
    通过验证码后，由业务端将 session['rl_verified'] 置为 True 即可恢复。
    """
    now = int(time.time())
    session['rl_locked_until'] = now + 60
    session['rl_verified'] = False
    return render_template('errors/429.html', retry_after=60), 429

# 注册模板过滤器
@bp.app_template_filter('any')
def any_filter(d):
    """
    检查字典是否至少包含一个非空值（用于前端条件渲染）。

    参数：
        d: 待检查的字典

    返回：
        布尔值；若存在有效数据，则用于决定是否展示“重置搜索”按钮等。
    """
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """
    生成一个不包含指定键的新字典（用于清理搜索参数）。

    参数：
        d: 原始字典
        exclude_key: 需要排除的键名

    返回：
        处理后的新字典，用于拼装去除某个过滤条件的 URL。
    """
    return {k: v for k, v in d.items() if k != exclude_key}

# 落地页路由
@bp.route('/')
def landing():
    """
    网站落地页：展示网站特性与功能概览。
    """
    return render_template('main/landing.html')

@bp.route('/database')
@performance_monitor
@cached_search(cache_enabled=True)
def index():
    """
    材料数据库页：展示材料列表，支持搜索、过滤与分页。

    支持的查询参数（GET）：
        q: 关键字搜索
        materials_type: 材料类型过滤（从 band.json 读取）
        fermi_level_min/max: 费米能级范围过滤
        page: 当前页码
    """
    try:
        # 获取所有搜索参数（存储在字典中以便统一处理）
        search_params = {
            'q': request.args.get('q', '').strip(),                # 文本搜索关键字
            'materials_type': request.args.get('materials_type', '').strip(),  # 材料类型过滤（从 band.json 读取）
            'elements': request.args.get('elements', '').strip(),  # 选定元素（来自元素周期表筛选）
            'fermi_level_min': request.args.get('fermi_level_min', '').strip(),  # 费米能级最小值
            'fermi_level_max': request.args.get('fermi_level_max', '').strip(),  # 费米能级最大值
            'max_sc_min': request.args.get('max_sc_min', '').strip(),  # 最大 SC 最小值
            'max_sc_max': request.args.get('max_sc_max', '').strip(),  # 最大 SC 最大值
            'band_gap_min': request.args.get('band_gap_min', '').strip(),  # 带隙最小值
            'band_gap_max': request.args.get('band_gap_max', '').strip(),  # 带隙最大值
            'mp_id': request.args.get('mp_id', '').strip(),          # MP-ID 过滤（精确或模糊）
            'space_group': request.args.get('space_group', '').strip(),  # 空间群过滤（名称或编号）
        }

        # 优先处理 MP 编号直达查询（形如 mp-xxxxx）
        mp_query = search_params['q']
        if mp_query and re.match(r'^mp-\w+$', mp_query):
            query = db.session.query(Material).filter(Material.mp_id == mp_query)
            # 直接分页返回
            page = request.args.get('page', 1, type=int)
            # 优先读取 URL 参数并写入 session，否则回退到 session
            per_page_arg = request.args.get('per_page', type=int)
            if per_page_arg in {10, 15, 20, 25, 30}:
                per_page = per_page_arg
                session['per_page'] = per_page
            else:
                per_page = session.get('per_page', 10)
                try:
                    per_page = int(per_page)
                except Exception:
                    per_page = 10
                if per_page not in {10, 15, 20, 25, 30}:
                    per_page = 10
            # 校验页码有效性：若当前页超过总页数，则回到第 1 页（MP 直达场景通常只有 0 或 1 页）
            total_results = query.count()
            total_pages = math.ceil(total_results / per_page) if per_page > 0 else 0
            if total_pages > 0 and page > total_pages:
                page = 1

            pagination = query.order_by(Material.name.asc()).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            return render_template('main/database.html',
                                 materials=pagination.items,
                                 pagination=pagination,
                                 # per_page 仅用于显示，不参与搜索参数
                                 search_params={**search_params})

        # 使用优化的查询器（常规路径）
        # 说明：QueryOptimizer 返回已优化的 query 与 total_count，可直接复用，避免重复统计
        optimization_result = QueryOptimizer.optimize_material_search(search_params)
        query = optimization_result['query']

        # 记录性能信息
        current_app.logger.info(
            f"Search optimization: {optimization_result['filters_applied']} filters, "
            f"{optimization_result['total_count']} results, "
            f"{optimization_result['execution_time']:.3f}s"
        )

        # 处理元素搜索（QueryOptimizer不处理的特殊逻辑）
        # 说明：将元素包含匹配下推到 SQL 条件，避免先 query.all() 再 Python 侧过滤导致的
        #       大量内存消耗与延迟。此处采用 ilike 包含匹配的 OR 组合作为性能友好的近似。
        additional_filters = []

        # Element-based search (智能化学式搜索) - 这是QueryOptimizer不处理的特殊逻辑
        if search_params['elements']:
            element_list = [elem.strip() for elem in search_params['elements'].split(',') if elem.strip()]
            if element_list:
                element_filters = []
                for elem in element_list:
                    like_pat = f"%{elem}%"
                    element_filters.append(Material.name.ilike(like_pat))
                if element_filters:
                    additional_filters.append(or_(*element_filters))

        # MP-ID 过滤：形如 mp-xxxxx 则精确匹配，否则模糊匹配（包含）
        if search_params['mp_id']:
            mp_val = search_params['mp_id']
            try:
                # 安全清洗输入
                mp_val = sanitize_input(mp_val)
            except Exception:
                mp_val = mp_val
            if re.match(r'^mp-\w+$', mp_val):
                additional_filters.append(Material.mp_id == mp_val)
            else:
                additional_filters.append(Material.mp_id.ilike(f'%{mp_val}%'))

        # 空间群过滤：纯数字 → 按编号；否则按名称模糊匹配
        if search_params['space_group']:
            sg_val = search_params['space_group']
            try:
                sg_val = sanitize_input(sg_val)
            except Exception:
                sg_val = sg_val
            if re.fullmatch(r'\d+', sg_val):
                # 数字编号
                try:
                    sg_num = int(sg_val)
                    additional_filters.append(Material.sg_num == sg_num)
                except ValueError:
                    pass
            else:
                additional_filters.append(Material.sg_name.ilike(f'%{sg_val}%'))

        # 应用额外的过滤条件（主要是元素搜索）
        if additional_filters:
            query = query.filter(and_(*additional_filters))

        # 添加搜索结果验证
        # 说明：避免重复 count()，复用优化器返回的统计值
        total_results = optimization_result.get('total_count', None)
        if total_results is None:
            # 兜底：若优化器未给出统计值，再做一次 count()
            total_results = query.count()
        current_app.logger.info(f"Search query returned {total_results} results with search params: {search_params}")

        # Pagination configuration
        page = request.args.get('page', 1, type=int)  # 当前页码，默认第1页
        # 优先读取 URL 参数并写入 session，否则回退到 session
        per_page_arg = request.args.get('per_page', type=int)
        if per_page_arg in {10, 15, 20, 25, 30}:
            per_page = per_page_arg
            session['per_page'] = per_page
        else:
            per_page = session.get('per_page', 10)
            try:
                per_page = int(per_page)
            except Exception:
                per_page = 10
            if per_page not in {10, 15, 20, 25, 30}:
                per_page = 10
        # 校验页码有效性：若当前页超过总页数，则回到第 1 页
        total_pages = math.ceil(total_results / per_page) if per_page > 0 else 0
        if total_pages > 0 and page > total_pages:
            page = 1

        pagination = query.order_by(Material.name.asc()).paginate(  # 按名称升序排序
            page=page,
            per_page=per_page,
            error_out=False  # 禁用页码越界报错（越界返回空列表）
        )

        # 渲染模板并传入分页对象与搜索参数
        return render_template('main/database.html',
                             materials=pagination.items,  # 当前页数据
                             pagination=pagination,  # 分页对象（含页码信息）
                             # per_page 仅用于显示，不参与搜索参数
                             search_params={**search_params})

    except Exception as e:
        current_app.logger.error(f"Database query error: {str(e)}")
        # 返回空材料列表与空搜索参数
        from flask_sqlalchemy import Pagination
        empty_pagination = Pagination(query=None, page=1, per_page=10, total=0, items=[])
        return render_template('main/database.html',
                             materials=[],
                             pagination=empty_pagination,
                             search_params={},
                             error_message="Database not initialized, please contact administrator")

# 定义管理员校验装饰器
def admin_required(view_func):
    """
    路由管理员权限装饰器：仅允许管理员访问。

    若用户未登录或非管理员，则引导至登录页。
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash(_('Access denied. This feature requires administrator privileges.'), 'error')
            return redirect(url_for('views.login'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# 工具函数：根据材料ID获取材料目录，仅使用新格式 IMR-{id}
def get_material_dir(material_id):
    """
    根据材料ID返回材料目录路径（统一为 IMR-{id}，不再兼容 IMR-00000001 旧格式）。
    """
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    return new_dir

# Material add route (admin required)
@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """
    添加新材料。

    目录策略说明：
    - 仅使用新目录 `IMR-{id}`；
    - 旧目录（`IMR-00000001` 这类补零格式）的回退与兼容由 `structure_parser` 内部集中处理，
      本视图不直接感知旧格式，避免多处维护导致不一致。
    """
    if request.method == 'POST':
        try:
            # 获取上传的文件
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')

            from werkzeug.utils import secure_filename
            import os

            # 先保存结构文件到临时目录
            structure_filename = None
            temp_structure_path = None
            chemical_name = None
            if structure_file and structure_file.filename.endswith('.cif'):
                # 直接用原始文件名保存
                structure_filename = secure_filename(structure_file.filename)
                temp_structure_path = os.path.join(current_app.root_path, 'static/temp', structure_filename)
                os.makedirs(os.path.dirname(temp_structure_path), exist_ok=True)
                structure_file.save(temp_structure_path)
                # 尝试提取化学式
                chemical_name = extract_chemical_formula_from_cif(temp_structure_path)
                # 解释：仅从 CIF 解析空间群；失败则 Unknown/None
                sg_name_from_cif = 'Unknown'
                sg_num_from_cif = None
                try:
                    _structure = Structure.from_file(temp_structure_path)
                    _analyzer = SpacegroupAnalyzer(_structure)
                    sg_name_from_cif = _analyzer.get_space_group_symbol() or 'Unknown'
                    sg_num_from_cif = _analyzer.get_space_group_number() or None
                except Exception as e:
                    current_app.logger.warning(f"CIF symmetry parse failed in add(): {e}")

            # 材料名优先用CIF解析结果，否则用Material+ID
            material_data = {
                'name': chemical_name if chemical_name else None,
                'structure_file': structure_filename,  # 仅作记录，实际读取时遍历目录
                'properties_json': properties_json.filename if properties_json and properties_json.filename else None,
                'sc_structure_file': sc_structure_file.filename if sc_structure_file and sc_structure_file.filename else None,
                'fermi_level': safe_float(request.form.get('fermi_level')),
                'band_gap': safe_float(request.form.get('band_gap')),
                'materials_type': request.form.get('materials_type'),
                'sg_name': sg_name_from_cif if 'sg_name_from_cif' in locals() else 'Unknown',
                'sg_num': sg_num_from_cif if 'sg_num_from_cif' in locals() else None
            }

            material = Material(**material_data)
            db.session.add(material)
            db.session.flush()  # 获取ID

            if not material.name:
                material.name = f"Material_IMR-{material.id}"
            material.validate()

            # 目录用新格式
            material_dir = get_material_dir(material.id)
            structure_dir = os.path.join(material_dir, 'structure')
            band_dir = os.path.join(material_dir, 'band')
            sc_dir = os.path.join(material_dir, 'sc')
            os.makedirs(structure_dir, exist_ok=True)
            os.makedirs(band_dir, exist_ok=True)
            os.makedirs(sc_dir, exist_ok=True)

            # 保存CIF文件
            if temp_structure_path and structure_filename:
                structure_path = os.path.join(structure_dir, structure_filename)
                os.rename(temp_structure_path, structure_path)

            # 处理其他文件，直接保存原始文件名
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(material_dir, properties_json_filename)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename
            if band_file and band_file.filename:
                band_filename = secure_filename(band_file.filename)
                band_path = os.path.join(band_dir, band_filename)
                band_file.save(band_path)
            # 处理Shift Current文件
            if sc_structure_file and sc_structure_file.filename:
                sc_filename = secure_filename(sc_structure_file.filename)
                sc_path = os.path.join(sc_dir, sc_filename)
                sc_structure_file.save(sc_path)
                material.sc_structure_file = sc_filename
                flash(_('Shift Current file %(filename)s uploaded successfully', filename=sc_filename), 'success')

                # 如果是dat文件，尝试重命名为sc.dat
                if sc_filename.endswith('.dat') and sc_filename != 'sc.dat':
                    try:
                        new_sc_path = os.path.join(sc_dir, 'sc.dat')
                        os.rename(sc_path, new_sc_path)
                        material.sc_structure_file = 'sc.dat'
                        flash(_('Shift Current file renamed to sc.dat'), 'success')
                    except Exception as e:
                        current_app.logger.warning(f"Failed to rename SC file: {str(e)}")

            db.session.commit()
            flash(_('Material %(name)s added successfully!', name=material.name), 'success')
            return redirect(url_for('views.detail', material_id=material.id))

        except ValueError as e:
            flash(_('Invalid data: %(error)s', error=str(e)), 'error')
            return redirect(url_for('views.add'))
        except Exception as e:
            flash(_('An error occurred: %(error)s', error=str(e)), 'error')
            return redirect(url_for('views.add'))

    return render_template('materials/add.html')

@bp.route('/set-language')
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
        return redirect(url_for('views.landing'))

    # 写入 session
    session['lang'] = lang

    # 构造重定向响应并设置 cookie（30 天）
    resp = redirect(request.referrer or url_for('views.landing'))
    resp.set_cookie('lang', lang, max_age=30*24*3600, samesite='Lax')
    return resp

# i18n 运行时调试路由（只读）
@bp.route('/i18n-debug')
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

# ------------------------- 成员视图支持函数 -------------------------
def to_slug(name):
    """将姓名转为 slug：小写并移除空白字符。"""
    if not name:
        return ''
    return re.sub(r'\s+', '', str(name).strip().lower())


def read_json(path):
    """安全读取 JSON 文件，失败返回 None。"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        current_app.logger.warning(f'read_json failed: {path}: {e}')
    return None


def split_achievements(value):
    """成就字段规范化为列表：支持字符串按行拆分或原生列表。"""
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [line.strip() for line in str(value).split('\n') if line.strip()]


def load_member_profile(slug):
    """按优先级读取成员资料：profile.json → info.json。"""
    base_dir = os.path.join(current_app.root_path, 'static', 'members', slug)
    profile_path = os.path.join(base_dir, 'profile.json')
    info_path = os.path.join(base_dir, 'info.json')

    profile = read_json(profile_path)
    if profile is not None:
        return profile, 'profile'

    info = read_json(info_path)
    if info is not None:
        # 将旧结构 info.json 映射为双语结构（默认当作英文）
        mapped = {
            'title_zh': '',
            'title_en': str(info.get('title', '') or '').strip(),
            'bio_zh': '',
            'bio_en': str(info.get('bio', '') or '').strip(),
            'achievements_zh': [],
            'achievements_en': split_achievements(info.get('achievements') or []),
        }
        return mapped, 'info'

    return None, None


def select_by_locale(profile, member, locale):
    """根据语言选择显示字段，并内置回退到 DB 字段。"""
    # 当前语言判断
    lang = str(locale) if locale else 'en'
    prefer_zh = lang.startswith('zh')

    # 取 DB 作为兜底
    db_title = (member.title or '').strip() if getattr(member, 'title', None) else ''
    db_bio = (member.bio or '').strip() if getattr(member, 'bio', None) else ''
    db_ach = split_achievements(getattr(member, 'achievements', '') or '')

    # 读取 profile 字段
    title_zh = (profile or {}).get('title_zh') or ''
    title_en = (profile or {}).get('title_en') or ''
    bio_zh = (profile or {}).get('bio_zh') or ''
    bio_en = (profile or {}).get('bio_en') or ''
    ach_zh = (profile or {}).get('achievements_zh') or []
    ach_en = (profile or {}).get('achievements_en') or []

    # 选择与回退
    if prefer_zh:
        display_title = title_zh or db_title or title_en
        display_bio = bio_zh or db_bio or bio_en
        display_achievements = ach_zh or db_ach or ach_en
    else:
        display_title = title_en or title_zh or db_title
        display_bio = bio_en or bio_zh or db_bio
        display_achievements = ach_en or ach_zh or db_ach

    # 确保类型
    if not isinstance(display_achievements, list):
        display_achievements = split_achievements(display_achievements)

    return {
        'display_title': display_title,
        'display_bio': display_bio,
        'display_achievements': display_achievements,
    }


@bp.route('/members')
def members_index():
    """成员列表页：读取 profile.json（兼容 info.json）并按语言展示。"""
    # 解释：查询所有成员并按 slug 读取静态资料
    members = db.session.query(Member).order_by(Member.name.asc()).all()

    # 获取当前语言
    try:
        current_locale = get_locale()
    except Exception:
        current_locale = 'en'

    view_models = []
    for m in members:
        slug = to_slug(m.name or '')
        profile, source = load_member_profile(slug)
        if source is None:
            current_app.logger.info(
                f'members: no profile/info for slug={slug}, fallback to DB'
            )
        selected = select_by_locale(profile, m, current_locale)

        # 解释：选择头像，优先 DB，其次 info/profile 中的 photo
        photo = (m.photo or '').strip()
        if not photo:
            # 尝试从旧 info.json 读取 photo（若映射不到则忽略）
            base_dir = os.path.join(current_app.root_path, 'static', 'members', slug)
            info_json = read_json(os.path.join(base_dir, 'info.json'))
            if isinstance(info_json, dict):
                photo = str(info_json.get('photo', '')).strip()

        view_models.append({
            'slug': slug,
            'name': m.name,
            'photo': photo,
            **selected,
        })

    return render_template('members/index.html', members=view_models)

# 数值安全转换的辅助函数
def safe_float(value):
    """
    安全地将字符串转换为浮点数（允许空值）。

    参数：
        value: 输入字符串

    返回：
        float 或 None；转换失败或输入为空时返回 None。
    """
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    """
    安全地将字符串转换为整数（允许空值）。

    参数：
        value: 输入字符串

    返回：
        int 或 None；转换失败或输入为空时返回 None。
    """
    try:
        return int(value) if value else None
    except ValueError:
        return None

# Material edit route (admin required)
@bp.route('/materials/edit/IMR-<string:material_id>', methods=['GET', 'POST'])
@login_required  
@admin_required
def edit(material_id):
    """
    编辑材料，ID目录用IMR-{id}格式，兼容旧格式。
    """
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
    material = Material.query.get_or_404(numeric_id)

    import glob
    if request.method == 'POST':
        try:
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')

            material_dir = get_material_dir(material.id)
            structure_dir = os.path.join(material_dir, 'structure')
            band_dir = os.path.join(material_dir, 'band')
            sc_dir = os.path.join(material_dir, 'sc')
            os.makedirs(structure_dir, exist_ok=True)
            os.makedirs(band_dir, exist_ok=True)
            os.makedirs(sc_dir, exist_ok=True)

            # 结构文件上传，直接保存原始文件名
            if structure_file and structure_file.filename:
                if not structure_file.filename.endswith('.cif'):
                    flash(_('Please upload a .cif format structure file!'), 'error')
                    return redirect(url_for('views.edit', material_id=material_id))
                structure_filename = secure_filename(structure_file.filename)
                structure_path = os.path.join(structure_dir, structure_filename)
                structure_file.save(structure_path)
                material.structure_file = structure_filename
                # 提取化学式
                chemical_name = extract_chemical_formula_from_cif(structure_path)
                if chemical_name:
                    existing_material = Material.query.filter(
                        Material.name == chemical_name,
                        Material.id != numeric_id
                    ).first()
                    if existing_material:
                        flash(_('Material name "%(chemical_name)s" already exists, please change CIF file', chemical_name=chemical_name), 'error')
                        return redirect(url_for('views.edit', material_id=material_id))
                    material.name = chemical_name
                    flash(_('Material name updated from CIF file: %(chemical_name)s', chemical_name=chemical_name), 'info')
                # 解释：仅从 CIF 解析空间群；失败则 Unknown/None
                try:
                    _structure = Structure.from_file(structure_path)
                    _analyzer = SpacegroupAnalyzer(_structure)
                    material.sg_name = _analyzer.get_space_group_symbol() or 'Unknown'
                    material.sg_num = _analyzer.get_space_group_number() or None
                except Exception as e:
                    current_app.logger.warning(f"CIF symmetry parse failed in edit(): {e}")
                    material.sg_name = 'Unknown'
                    material.sg_num = None

            # band文件上传
            if band_file and band_file.filename:
                if band_file.filename.endswith(('.json', '.dat')):
                    band_filename = secure_filename(band_file.filename)
                    band_path = os.path.join(band_dir, band_filename)
                    band_file.save(band_path)

            # SC结构文件上传
            if sc_structure_file and sc_structure_file.filename:
                sc_structure_filename = secure_filename(sc_structure_file.filename)
                sc_structure_path = os.path.join(sc_dir, sc_structure_filename)
                sc_structure_file.save(sc_structure_path)
                material.sc_structure_file = sc_structure_filename

            # 属性json
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(material_dir, properties_json_filename)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename

            # 其他属性
            if not structure_file or not structure_file.filename or not material.name:
                material.name = request.form.get('name')
            if not material.name:
                flash(_('Material name cannot be empty!'), 'error')
                return redirect(url_for('views.edit', material_id=material_id))
            # [Deprecated 20250822] status 字段已移除
            material.fermi_level = safe_float(request.form.get('fermi_level'))
            # 电子性质参数 - 只保留带隙和材料类型
            material.band_gap = safe_float(request.form.get('band_gap'))
            material.materials_type = request.form.get('materials_type')
            db.session.commit()
            flash(_('Material information updated successfully.'), 'success')
            return redirect(url_for('views.detail', material_id=material_id))
        except ValueError as e:
            flash(_('Invalid data: %(error)s', error=str(e)), 'error')
            return redirect(url_for('views.edit', material_id=material_id))
        except Exception as e:
            db.session.rollback()
            flash(_('An error occurred: %(error)s', error=str(e)), 'error')
            return redirect(url_for('views.edit', material_id=material_id))

    # GET请求，显示所有.cif、band、sc文件
    material_dir = get_material_dir(material.id)
    structure_dir = os.path.join(material_dir, 'structure')
    band_dir = os.path.join(material_dir, 'band')
    sc_dir = os.path.join(material_dir, 'sc')
    # 获取文件列表并检查多文件情况
    cif_files = []
    band_files = []
    sc_files = []

    # 检查结构文件
    if os.path.exists(structure_dir):
        cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
        if len(cif_files) > 1:
            flash(_('Warning: Multiple CIF files found in structure directory. Please keep only one!'), 'warning')

    # 检查能带文件（只检查.dat文件，.json是分析结果文件）
    if os.path.exists(band_dir):
        band_dat_files = [f for f in os.listdir(band_dir) if f.endswith('.dat')]
        if len(band_dat_files) > 1:
            flash(_('Warning: Multiple band .dat files found in band directory. Please keep only one!'), 'warning')
        # 获取所有能带相关文件用于显示
        band_files = [f for f in os.listdir(band_dir) if f.endswith('.dat') or f.endswith('.json')]

    # 检查SC文件
    if os.path.exists(sc_dir):
        sc_files = [f for f in os.listdir(sc_dir) if f.endswith('.dat')]
        if len(sc_files) > 1:
            flash(_('Warning: Multiple SC files found in sc directory. Please keep only one!'), 'warning')
    return render_template('materials/edit.html', material=material, cif_files=cif_files, band_files=band_files, sc_files=sc_files, structure_dir=structure_dir, band_dir=band_dir, sc_dir=sc_dir)

# Material detail page
@bp.route('/materials/IMR-<string:material_id>')
def detail(material_id):
    """
    材料详情页，ID目录用IMR-{id}格式，兼容旧格式。
    """
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
    material = Material.query.get_or_404(numeric_id)

    # 自动分析能带数据（如果尚未分析）
    try:
        if material.band_gap is None or material.materials_type is None:
            current_app.logger.info(f"Auto-analyzing band data for {material.formatted_id}")
            material_path = f"app/static/materials/{material.formatted_id}/band"
            result = band_analyzer.analyze_material(material_path)
            if result['band_gap'] is not None:
                material.band_gap = result['band_gap']
                material.materials_type = result['materials_type']
                db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Failed to auto-analyze band data for {material.formatted_id}: {e}")
    import glob
    material_dir = get_material_dir(material.id)
    structure_dir = os.path.join(material_dir, 'structure')
    band_dir = os.path.join(material_dir, 'band')
    sc_dir = os.path.join(material_dir, 'sc')
    # 结构文件
    cif_files = glob.glob(os.path.join(structure_dir, '*.cif')) if os.path.exists(structure_dir) else []
    if len(cif_files) == 1:
        structure_file = os.path.relpath(cif_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(cif_files) > 1:
        flash(_('Error: Multiple CIF files found in structure directory. Please keep only one!'), 'error')
        structure_file = None
    else:
        structure_file = None
    # band文件（只检查.dat文件，.json是分析结果文件）
    band_dat_files = glob.glob(os.path.join(band_dir, '*.dat')) if os.path.exists(band_dir) else []
    if len(band_dat_files) == 1:
        band_file = os.path.relpath(band_dat_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(band_dat_files) > 1:
        flash(_('Error: Multiple band .dat files found in band directory. Please keep only one!'), 'error')
        band_file = None
    else:
        band_file = None
    # Shift Current文件
    sc_files = glob.glob(os.path.join(sc_dir, '*.dat')) if os.path.exists(sc_dir) else []
    if len(sc_files) == 1:
        sc_file = os.path.relpath(sc_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(sc_files) > 1:
        flash(_('Error: Multiple SC files found in sc directory. Please keep only one!'), 'error')
        sc_file = None
    else:
        sc_file = None
    
    # ========== 新增：BCD/DW 目录与矩阵探测 ==========
    # 解释：为前端 BCD/DW 模块提供目录与矩阵文件路径（相对 static/）。
    # 策略：优先使用材料目录 IMR-{formatted_id}/{bcd|dw}，若不存在则回退到全局 materials/{bcd|dw}。
    materials_base = os.path.join(current_app.root_path, 'static', 'materials')
    static_root = os.path.join(current_app.root_path, 'static')

    # BCD 目录优先 IMR-<id>/bcd，其次全局 bcd
    bcd_dir_abs = os.path.join(materials_base, material.formatted_id, 'bcd')
    if not os.path.isdir(bcd_dir_abs):
        global_bcd_abs = os.path.join(materials_base, 'bcd')
        bcd_dir_abs = global_bcd_abs if os.path.isdir(global_bcd_abs) else None
    bcd_dir = os.path.relpath(bcd_dir_abs, static_root) if bcd_dir_abs else None
    bcd_matrix_path = None
    if bcd_dir_abs:
        bcd_matrix_abs = os.path.join(bcd_dir_abs, 'matrix.dat')
        if os.path.isfile(bcd_matrix_abs):
            bcd_matrix_path = os.path.relpath(bcd_matrix_abs, static_root)

    # DW 目录优先 IMR-<id>/dw，其次全局 dw
    dw_dir_abs = os.path.join(materials_base, material.formatted_id, 'dw')
    if not os.path.isdir(dw_dir_abs):
        global_dw_abs = os.path.join(materials_base, 'dw')
        dw_dir_abs = global_dw_abs if os.path.isdir(global_dw_abs) else None
    dw_dir = os.path.relpath(dw_dir_abs, static_root) if dw_dir_abs else None
    dw_matrix_path = None
    if dw_dir_abs:
        dw_matrix_abs = os.path.join(dw_dir_abs, 'matrix.dat')
        if os.path.isfile(dw_matrix_abs):
            dw_matrix_path = os.path.relpath(dw_matrix_abs, static_root)

    # ==============================================

    return render_template(
        'materials/detail.html',
        material=material,
        structure_file=structure_file,
        band_file=band_file,
        sc_file=sc_file,
        bcd_dir=bcd_dir,
        dw_dir=dw_dir,
        bcd_matrix_path=bcd_matrix_path,
        dw_matrix_path=dw_matrix_path
    )

# 通过 MP 编号跳转到 IMR 详情
@bp.route('/materials/by-mp/<string:mp_id>')
def material_by_mp(mp_id):
    """
    通过 Materials Project 编号（mp-xxxxx）查找材料，并跳转到 IMR 详情页。
    """
    try:
        material = db.session.query(Material).filter(Material.mp_id == mp_id).first()
        if not material:
            flash(_('Material with MP ID %(mp_id)s not found.', mp_id=mp_id), 'error')
            return render_template('404.html'), 404
        return redirect(url_for('views.detail', material_id=material.id))
    except Exception as e:
        current_app.logger.error(f"material_by_mp error: {e}")
        return render_template('500.html'), 500

# Material delete route (admin required)
@bp.route('/materials/delete/IMR-<string:material_id>', methods=['POST'])
@login_required  
@admin_required
def delete(material_id):
    """
    Delete material record
    
    Parameters:
        material_id: ID of the material to delete (format is number part, no IMR-prefix)
    
    Note:
        Only accepts POST requests, to prevent CSRF attacks
    """
    # Extract numeric part from string ID
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
        
    material = Material.query.get_or_404(numeric_id)  # Get material or return 404 error
    
    # Delete related files
    import os
    import shutil
    from flask import current_app
    
    # Delete material-specific folder and all its contents
    material_dir = get_material_dir(numeric_id)
    if os.path.exists(material_dir):
        shutil.rmtree(material_dir)
    
    # Keep original file deletion logic to ensure backward compatibility
    # Delete structure file
    if material.structure_file:
        structure_path = os.path.join(current_app.root_path, 'static/structures', material.structure_file)
        if os.path.exists(structure_path):
            os.remove(structure_path)
    
    # Delete band file
    band_path = os.path.join(current_app.root_path, 'static/band', f'{material.id}.dat')
    if os.path.exists(band_path):
        os.remove(band_path)
    
    # Delete attribute JSON file
    if material.properties_json:
        json_path = os.path.join(current_app.root_path, 'static/properties', material.properties_json)
        if os.path.exists(json_path):
            os.remove(json_path)
    
    # Delete Shift Current file
    if material.sc_structure_file:
        sc_path = os.path.join(current_app.root_path, 'static/sc_structures', material.sc_structure_file)
        if os.path.exists(sc_path):
            os.remove(sc_path)
    
    db.session.delete(material)  # Delete record
    db.session.commit()  # Commit transaction
    flash(_('Material "%(name)s" and all related files have been successfully deleted.', name=material.name), 'success')  # Display success message
    return redirect(url_for('views.index'))  # Redirect to homepage

# Helper function to get client IP
def get_client_ip():
    """Get client IP address of the current request
    
    Returns: 
        String representing client IP address
    """
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr

# IP block check decorator
def check_ip_blocked(view_func):
    """Decorator to check if IP is blocked
    
    If IP is blocked, redirect to homepage and display warning message
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        client_ip = get_client_ip()
        
        # Check if IP is in blocked list
        blocked = BlockedIP.query.filter_by(ip_address=client_ip).first()
        if blocked:
            flash(_('Access denied. Your IP has been blocked due to multiple failed login attempts.'), 'error')
            return redirect(url_for('views.landing'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# User login route - 重构版本
@bp.route('/login', methods=['GET', 'POST'])
@check_ip_blocked
def login():
    """
    用户登录页面和处理逻辑 - 重构版本

    使用统一的登录状态管理，确保状态一致性和安全性

    GET request: 显示登录表单
    POST request: 验证用户凭据并处理登录
    """
    # 如果用户已登录，重定向到首页（不显示消息）
    if current_user.is_authenticated:
        return redirect(url_for('views.index'))

    if request.method == 'POST':
        # 检查CSRF令牌（如果启用了CSRF保护）
        try:
            from flask_wtf.csrf import validate_csrf
            validate_csrf(request.form.get('csrf_token'))
        except Exception as e:
            # CSRF验证失败，可能是令牌过期或无效
            flash(_('Security token expired or invalid. Please try again.'), 'error')
            current_app.logger.warning(f"CSRF validation failed for login: {str(e)}")
            return render_template('auth/login.html')

        email = request.form.get('email')
        username = request.form.get('username')
        captcha_input = request.form.get('captcha', '').upper()
        real_captcha = session.get('captcha', '')
        if captcha_input != real_captcha:
            flash(_('Invalid captcha code, please try again'), 'error')
            return render_template('auth/login.html')
        password = request.form.get('password')
        remember = 'remember' in request.form
        login_type = request.form.get('login_type')
        admin_login = login_type == 'admin'
        
        # Form validation
        if not email or not username or not password:
            flash(_('All fields are required.'), 'error')
            return render_template('auth/login.html')
        
        # Check login failure count with enhanced security logging
        ip = get_client_ip()
        failed_key = f"login_failed:{ip}"
        failed_attempts = session.get(failed_key, 0)
        max_attempts = 5  # Maximum attempts

        # 记录登录尝试
        log_security_event("LOGIN_ATTEMPT", f"User: {username}, Email: {email}", ip)
        
        # Check if email exists
        user_by_email = User.query.filter_by(email=email).first()
        if not user_by_email:
            # Update failure count
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            
            # If failure count reaches limit, block IP
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('views.login'))
            
            flash(_('Email not found. Please check your email address. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')
        
        # Check if username matches the email
        if user_by_email.username != username:
            # Update failure count
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            
            # If failure count reaches limit, block IP
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('views.login'))
            
            flash(_('Username does not match this email address. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')
        
        # Distinguish between admin login and regular login
        if admin_login and user_by_email.role != 'admin':
            # Update failure count
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            
            # If failure count reaches limit, block IP
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed admin login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many unauthorized admin login attempts.'), 'error')
                return redirect(url_for('views.login'))
            
            flash(_('This account does not have administrator privileges. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')
        
        # Check password
        if not user_by_email.validate_password(password):
            # Update failure count
            failed_attempts += 1
            session[failed_key] = failed_attempts
            remaining_attempts = max_attempts - failed_attempts
            
            # If failure count reaches limit, block IP
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                flash(_('Your IP has been blocked due to too many failed login attempts.'), 'error')
                return redirect(url_for('views.login'))
            
            flash(_('Incorrect password. You have %(n)d attempts remaining.', n=remaining_attempts), 'error')
            return render_template('auth/login.html')
        
        # 登录成功，清除失败计数
        session.pop(failed_key, None)

        # 使用统一的登录状态管理器处理登录
        try:
            success, message, redirect_url = LoginStateManager.login_user(user_by_email)

            if success:
                # 登录成功，重定向到目标页面
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('views.index'))
            else:
                # 登录失败（系统错误）
                flash(message, 'error')
                return render_template('auth/login.html')

        except Exception as e:
            current_app.logger.error(f"Login system error: {e}")
            error_msg = LoginErrorHandler.handle_login_error('system_error')
            flash(error_msg, 'error')
            return render_template('auth/login.html')
        
    return render_template('auth/login.html')

# JSON 登录接口：供前端 AJAX 校验使用
@bp.route('/auth/login_json', methods=['POST'])
@check_ip_blocked
@csrf.exempt
def login_json():
    """
    JSON 登录接口（方案B）：
    - 输入：email, username, password, captcha, login_type
    - 逻辑：与表单登录一致的校验流程（验证码→邮箱→用户名→管理员→密码）
    - 成功：login_user，并返回 { ok: true, redirect }
    - 失败：返回 { ok: false, error }
    """
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        captcha_input = (data.get('captcha') or '').strip().upper()
        login_type = (data.get('login_type') or 'user').strip()
        admin_login = login_type == 'admin'

        # 验证码校验
        real_captcha = session.get('captcha', '')
        if not captcha_input or captcha_input != real_captcha:
            return jsonify({
                'ok': False,
                'error': _('Invalid captcha code, please try again')
            }), 200

        # 基础字段校验
        if not email or not username or not password:
            return jsonify({
                'ok': False,
                'error': _('All fields are required.')
            }), 200

        # 登录失败计数
        ip = get_client_ip()
        failed_key = f"login_failed:{ip}"
        failed_attempts = session.get(failed_key, 0)
        max_attempts = 5

        # 记录尝试
        log_security_event("LOGIN_ATTEMPT_JSON", f"User: {username}, Email: {email}", ip)

        # 邮箱存在性
        user_by_email = User.query.filter_by(email=email).first()
        if not user_by_email:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Email not found. Please check your email address. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        # 用户名匹配
        if user_by_email.username != username:
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Username does not match this email address. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        # 管理员登录权限
        if admin_login and user_by_email.role != 'admin':
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed admin login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many unauthorized admin login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('This account does not have administrator privileges. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        # 密码校验
        if not user_by_email.validate_password(password):
            failed_attempts += 1
            session[failed_key] = failed_attempts
            if failed_attempts >= max_attempts:
                block_ip = BlockedIP(ip_address=ip, reason="Multiple failed login attempts")
                db.session.add(block_ip)
                db.session.commit()
                session.pop(failed_key, None)
                return jsonify({'ok': False, 'error': _('Your IP has been blocked due to too many failed login attempts.')}), 200
            remaining_attempts = max_attempts - failed_attempts
            return jsonify({'ok': False, 'error': _('Incorrect password. You have %(n)d attempts remaining.', n=remaining_attempts)}), 200

        # 登录成功，清除失败计数
        session.pop(failed_key, None)

        # 使用统一登录状态管理器
        try:
            success, message, redirect_url = LoginStateManager.login_user(user_by_email)
            if success:
                next_page = request.args.get('next')
                return jsonify({'ok': True, 'redirect': next_page or url_for('views.index')})
            else:
                return jsonify({'ok': False, 'error': message or _('An error occurred: %(error)s', error='login')})
        except Exception as e:
            current_app.logger.error(f"Login system error (JSON): {e}")
            error_msg = LoginErrorHandler.handle_login_error('system_error')
            return jsonify({'ok': False, 'error': error_msg}), 200

    except Exception as e:
        current_app.logger.error(f"login_json unexpected error: {e}")
        return jsonify({'ok': False, 'error': 'Internal server error'}), 500

# User logout route - 重构版本
@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    用户登出处理 - 重构版本

    使用统一的登录状态管理，确保：
    1. 用户身份正确恢复为游客状态
    2. 会话数据完全清理和会话ID重新生成
    3. 只显示一次登出消息
    4. 多标签页状态同步
    """
    try:
        # 使用统一的登出状态管理器
        success, message = LoginStateManager.logout_user()

        # 重定向到首页（数据库页面）
        return redirect(url_for('views.index'))

    except Exception as e:
        # 发生错误时的兜底处理
        current_app.logger.error(f"Logout system error: {e}")
        try:
            from flask_login import logout_user as flask_logout_user
            flask_logout_user()
            session.clear()
            regenerate_session()
        except:
            pass
        flash(_('Logout completed.'), 'info')
        return redirect(url_for('views.index'))

# 调试路由：检查用户状态
@bp.route('/debug/user-status')
def debug_user_status():
    """调试用户登录状态和导航栏显示逻辑"""
    if not current_app.debug:
        return "Debug mode only", 403

    # 收集系统状态信息（不显示用户个人信息）
    status = {
        'is_authenticated': current_user.is_authenticated,
        'user_role_type': 'admin' if current_user.is_authenticated and current_user.is_admin() else 'user' if current_user.is_authenticated else 'guest',
        'session_keys_count': len(session.keys()),
        'remote_addr': request.remote_addr,
        'user_agent_browser': request.headers.get('User-Agent', 'N/A')[:50] + '...' if len(request.headers.get('User-Agent', '')) > 50 else request.headers.get('User-Agent', 'N/A')
    }

    # 生成HTML调试页面
    html = f"""
    <html>
    <head><title>用户状态调试</title></head>
    <body>
        <h1>🔍 用户状态调试信息</h1>
        <h2>基本状态</h2>
        <table border="1" style="border-collapse: collapse;">
            <tr><th>属性</th><th>值</th></tr>
            {''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in status.items())}
        </table>

        <h2>导航栏显示逻辑测试</h2>
        <ul>
            <li>显示SiliconFlow按钮: {'是' if current_user.is_authenticated else '否'}</li>
            <li>显示Program按钮: {'是' if current_user.is_authenticated else '否'}</li>
            <li>显示Add按钮: {'是' if current_user.is_authenticated and current_user.is_admin() else '否'}</li>
            <li>显示Login按钮: {'是' if not current_user.is_authenticated else '否'}</li>
            <li>用户类型: {status['user_role_type']}</li>
        </ul>

        <h2>系统状态信息</h2>
        <ul>
            <li>会话键数量: {status['session_keys_count']}</li>
            <li>用户设置功能: 已禁用（安全考虑）</li>
        </ul>

        <h3>消息系统状态:</h3>
        <p>✅ 消息现在在登录/登出时立即显示，不再使用会话标记</p>

        <h2>快速操作</h2>
        <a href="/logout">登出</a> |
        <a href="/login">登录</a> |
        <a href="/database">返回首页</a> |
        <a href="/debug/clear-session">清理会话</a>
    </body>
    </html>
    """

    return html

# 调试路由：清理会话
@bp.route('/debug/clear-session')
def debug_clear_session():
    """清理所有会话数据（调试用）"""
    if not current_app.debug:
        return "Debug mode only", 403

    session.clear()
    flash(_('Session cleared successfully.'), 'info')
    return redirect(url_for('views.index'))

# 用户设置功能已删除，为了安全考虑，用户无法在网页上修改个人信息
# 如需管理用户，请使用 user_management.py 脚本或管理员命令

# 注意：旧的users.dat文件管理函数已被移除
# 现在所有用户数据都安全地存储在数据库中，使用bcrypt加密
# 如需管理用户，请使用 user_management.py 脚本

def generate_captcha_image(text, width=140, height=50, scale_factor=2):
    """
    使用Pillow生成符合网站风格的验证码图片
    采用高分辨率渲染后缩放的方式，确保在各种环境下都清晰显示

    参数:
        text: 验证码文本
        width: 最终图片宽度
        height: 最终图片高度
        scale_factor: 渲染缩放因子，用于提高清晰度

    返回:
        BytesIO对象，包含PNG格式的图片数据
    """
    # 网站主题色彩配置
    THEME_COLORS = {
        'primary': (0, 71, 171),      # #0047AB - 主色
        'secondary': (30, 92, 179),   # #1E5CB3 - 次色
        'accent': (0, 127, 255),      # #007FFF - 强调色
        'light_bg': (245, 248, 255),  # #F5F8FF - 浅色背景
        'nav_bg': (181, 222, 253),    # 导航栏背景色
        'text_dark': (51, 51, 51),    # #333333 - 深色文字
    }

    # 使用高分辨率渲染，然后缩放到目标尺寸
    # 这样可以确保在各种DPI和浏览器环境下都清晰显示
    render_width = int(width * scale_factor)
    render_height = int(height * scale_factor)

    # 创建高分辨率图像
    image = Image.new('RGB', (render_width, render_height), color=THEME_COLORS['light_bg'])
    draw = ImageDraw.Draw(image)

    # 添加微妙的渐变背景效果（适应高分辨率）
    for y in range(render_height):
        # 从浅蓝到更浅的蓝色渐变
        ratio = y / render_height
        r = int(THEME_COLORS['light_bg'][0] + (THEME_COLORS['nav_bg'][0] - THEME_COLORS['light_bg'][0]) * ratio * 0.3)
        g = int(THEME_COLORS['light_bg'][1] + (THEME_COLORS['nav_bg'][1] - THEME_COLORS['light_bg'][1]) * ratio * 0.3)
        b = int(THEME_COLORS['light_bg'][2] + (THEME_COLORS['nav_bg'][2] - THEME_COLORS['light_bg'][2]) * ratio * 0.3)
        draw.line([(0, y), (render_width, y)], fill=(r, g, b))

    # 使用字体管理器加载字体 - 根据缩放因子调整字体大小
    base_font_size = 32  # 增大基础字体大小
    font_size = int(base_font_size * scale_factor)
    
    # 使用FontManager获取最佳字体
    font = FontManager.get_captcha_font(font_size)
    
    # 检查是否需要使用嵌入式字体
    if hasattr(font, '_use_embedded') and font._use_embedded:
        from .embedded_font import EmbeddedFont
        current_app.logger.info("使用嵌入式字体生成验证码")
        return EmbeddedFont.generate_embedded_captcha(text, width, height)
    
    # 记录字体加载状态
    current_app.logger.info(f"验证码字体大小: {font_size}, 缩放因子: {scale_factor}")

    # 添加精致的背景装饰点（适应高分辨率）
    dot_count = int(30 * scale_factor)
    dot_size = int(1 * scale_factor)
    for _ in range(dot_count):
        x = random.randint(0, render_width)
        y = random.randint(0, render_height)
        # 使用主题色的浅色版本作为装饰点
        alpha = random.uniform(0.1, 0.3)
        base_color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        color = tuple(int(c + (255 - c) * (1 - alpha)) for c in base_color)
        draw.ellipse([x-dot_size, y-dot_size, x+dot_size, y+dot_size], fill=color)

    # 计算文本位置（在高分辨率画布上）
    try:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError:
        # 兼容旧版本Pillow
        text_width = len(text) * int(20 * scale_factor)
        text_height = int(28 * scale_factor)

    start_x = (render_width - text_width) // 2
    start_y = (render_height - text_height) // 2

    # 绘制验证码文本 - 使用网站主题色
    char_colors = [
        THEME_COLORS['primary'],
        THEME_COLORS['secondary'],
        THEME_COLORS['accent'],
        THEME_COLORS['text_dark']
    ]

    char_width = text_width // len(text) if len(text) > 0 else int(20 * scale_factor)
    offset_range = int(3 * scale_factor)  # 根据缩放因子调整偏移范围

    for i, char in enumerate(text):
        # 为每个字符选择主题色
        color = char_colors[i % len(char_colors)]

        # 添加轻微的位置偏移，但保持可读性
        char_x = start_x + i * char_width + random.randint(-offset_range, offset_range)
        char_y = start_y + random.randint(-offset_range, offset_range)

        # 绘制字符
        draw.text((char_x, char_y), char, font=font, fill=color)

    # 添加优雅的装饰线条（适应高分辨率）
    line_width = max(1, int(1 * scale_factor))
    for _ in range(2):
        # 使用主题色绘制装饰线
        color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        # 让线条更加柔和
        alpha_color = tuple(int(c + (255 - c) * 0.6) for c in color)

        start_x_line = random.randint(0, render_width // 3)
        start_y_line = random.randint(render_height // 4, 3 * render_height // 4)
        end_x_line = random.randint(2 * render_width // 3, render_width)
        end_y_line = random.randint(render_height // 4, 3 * render_height // 4)

        draw.line([(start_x_line, start_y_line), (end_x_line, end_y_line)],
                 fill=alpha_color, width=line_width)

    # 移除边框效果，保持简洁外观

    # 如果使用了缩放，将图像缩放回目标尺寸
    if scale_factor != 1:
        # 使用高质量的重采样算法
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    # 保存到BytesIO，使用最高质量
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', quality=100, optimize=True)
    img_buffer.seek(0)

    return img_buffer

@bp.route('/captcha')
def captcha():
    """
    生成符合网站风格的验证码图片

    返回:
        PNG格式的验证码图片，带有适当的缓存控制头
    """
    start_time = time.time()
    try:
        # 生成5位随机验证码（大写字母和数字，排除容易混淆的字符）
        # 排除 0, O, 1, I, l 等容易混淆的字符
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        captcha_text = ''.join(random.choices(chars, k=5))

        # 将验证码保存到session中
        session['captcha'] = captcha_text
        session.permanent = True  # 确保session持久化

        # 生成验证码图片 - 使用2倍缩放提高清晰度
        img_buffer = generate_captcha_image(captcha_text, scale_factor=2)
        
        generation_time = time.time() - start_time
        
        # 记录验证码生成成功
        CaptchaLogger.log_captcha_generation(
            text_length=len(captcha_text),
            image_size='140x50',
            generation_time=generation_time,
            success=True
        )

        # 创建响应并设置缓存控制头
        response = send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name='captcha.png'
        )

        # 设置缓存控制头，防止浏览器缓存验证码
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        # 记录验证码生成失败
        CaptchaLogger.log_captcha_generation(
            text_length=5,
            image_size='140x50',
            generation_time=time.time() - start_time,
            success=False,
            error=str(e)
        )
        
        # 如果生成验证码失败，返回一个简单的错误图片
        current_app.logger.error(f"Error generating captcha: {str(e)}")

        # 创建一个简单的错误提示图片
        error_image = Image.new('RGB', (140, 50), color=(245, 248, 255))
        error_draw = ImageDraw.Draw(error_image)
        error_draw.text((10, 15), "ERROR", fill=(220, 53, 69))

        error_buffer = io.BytesIO()
        error_image.save(error_buffer, format='PNG')
        error_buffer.seek(0)

        return send_file(error_buffer, mimetype='image/png')

@bp.route('/captcha429')
def captcha429():
    """为429页面生成验证码（与登录同逻辑，但使用独立会话键）。"""
    start_time = time.time()
    try:
        # 生成5位验证码（排除易混字符）
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        captcha_text = ''.join(random.choices(chars, k=5))

        # 保存到独立的 session 键，避免与登录互相覆盖
        session['captcha_429'] = captcha_text
        session.permanent = True

        # 复用统一的图片生成函数
        img_buffer = generate_captcha_image(captcha_text, scale_factor=2)

        generation_time = time.time() - start_time
        # 记录日志（标注来源为429）
        CaptchaLogger.log_captcha_generation(
            text_length=len(captcha_text),
            image_size='140x50',
            generation_time=generation_time,
            success=True
        )

        response = send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=False,
            download_name='captcha429.png'
        )
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        current_app.logger.error(f"Error generating captcha429: {e}")
        # 返回简单错误图片
        error_image = Image.new('RGB', (140, 50), color=(245, 248, 255))
        error_draw = ImageDraw.Draw(error_image)
        error_draw.text((10, 15), "ERROR", fill=(220, 53, 69))
        error_buffer = io.BytesIO()
        error_image.save(error_buffer, format='PNG')
        error_buffer.seek(0)
        return send_file(error_buffer, mimetype='image/png')

@bp.route('/verify_captcha_429', methods=['POST'])
@csrf.exempt
def verify_captcha_429():
    """校验429页面验证码，返回JSON。只有'时间到且验证码正确'才解除封禁。"""
    import time
    try:
        data = request.get_json(silent=True) or {}
        code = str(data.get('captcha', '')).strip().upper()
        real = str(session.get('captcha_429', '')).strip().upper()
        ok = bool(code) and code == real

        now = int(time.time())
        locked_until = int(session.get('rl_locked_until') or 0)
        remaining = max(0, locked_until - now)

        if ok:
            if remaining > 0:
                return jsonify({'ok': False, 'need_wait': True, 'seconds': remaining})
            # 时间到且验证码正确：解除封禁
            session.pop('captcha_429', None)
            session['rl_verified'] = True
            session.pop('rl_locked_until', None)
            return jsonify({'ok': True})
        else:
            return jsonify({'ok': False})
    except Exception as e:
        current_app.logger.error(f"verify_captcha_429 error: {e}")
        return jsonify({'ok': False})

@bp.route('/members')
def members():
    """
    研究部成员展示页面（多语言，方案B：静态JSON）

    逻辑：
    - 基础信息（name、photo）来自数据库 Member
    - 文案信息（title/bio/achievements）优先读取 app/static/members/<slug>/profile.json
    - 根据当前语言(locale)选择 *_<locale> 字段，带回退
    - 组装 display_* 字段供模板直接渲染
    """
    db_members = Member.query.all()

    # 获取当前语言（两位，如 'en'/'zh'）
    try:
        locale = str(get_locale())[:2] if get_locale() else 'en'
    except Exception:
        locale = 'en'

    static_members_dir = os.path.join(current_app.root_path, 'static', 'members')

    display_members = []

    for m in db_members:
        # 依据 name 生成 slug：小写+去空格，用于目录名
        base_name = m.name or ''
        slug = base_name.lower().replace(' ', '')
        profile_path = os.path.join(static_members_dir, slug, 'profile.json')

        data = {}
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                current_app.logger.warning(f"Failed to read member profile.json for {slug}: {e}")
                data = {}

        # 选择多语言文本，带回退：优先 *_<locale>，其次无后缀字段，再次 DB 字段，最后空串
        def pick_text(prefix: str, default: str = '') -> str:
            return (
                data.get(f'{prefix}_{locale}')
                or data.get(prefix)
                or default
                or ''
            )

        # 成就：期望列表，兼容字符串（按换行拆分）
        def pick_achievements():
            ach = (
                data.get(f'achievements_{locale}')
                or data.get('achievements')
                or (m.achievements or '')
            )
            if isinstance(ach, list):
                return [str(s).strip() for s in ach if str(s).strip()]
            if isinstance(ach, str):
                return [line.strip() for line in ach.split('\n') if line.strip()]
            return []

        display_members.append({
            'name': base_name,
            'photo': m.photo or 'photo.jpg',  # 回退一个占位名，防止模板路径拼接失败
            'slug': slug,
            'display_title': pick_text('title', m.title or ''),
            'display_bio': pick_text('bio', m.bio or ''),
            'display_achievements': pick_achievements(),
        })

    return render_template('members/index.html', members=display_members)

# ==================== 智能搜索API端点 ====================

@bp.route('/api/search/suggestions')
def search_suggestions():
    """
    提供实时搜索建议

    参数:
        q: 搜索查询字符串
        type: 建议类型 ('all', 'materials', 'elements', 'mp_ids', 'space_groups')
        limit: 返回结果数量限制 (默认10)

    返回:
        JSON格式的搜索建议列表
    """
    query = request.args.get('q', '').strip()
    suggestion_type = request.args.get('type', 'all')
    limit = min(int(request.args.get('limit', 10)), 50)  # 最多50个建议

    if len(query) < 2:
        return jsonify({'suggestions': []})

    suggestions = []

    try:
        if suggestion_type in ['all', 'materials']:
            # 材料名称建议
            material_suggestions = Material.query.filter(
                Material.name.ilike(f'%{query}%')
            ).limit(limit).all()

            for material in material_suggestions:
                suggestions.append({
                    'type': 'material',
                    'value': material.name,
                    'label': f"{material.name} ({material.formatted_id})",
                    'category': 'Materials'
                })

        if suggestion_type in ['all', 'mp_ids']:
            # Materials Project ID建议
            mp_suggestions = Material.query.filter(
                Material.mp_id.ilike(f'%{query}%')
            ).limit(limit).all()

            for material in mp_suggestions:
                if material.mp_id:
                    suggestions.append({
                        'type': 'mp_id',
                        'value': material.mp_id,
                        'label': f"{material.mp_id} - {material.name}",
                        'category': 'MP IDs'
                    })

        if suggestion_type in ['all', 'space_groups']:
            # 空间群建议
            sg_suggestions = Material.query.filter(
                Material.sg_name.ilike(f'%{query}%')
            ).distinct(Material.sg_name).limit(limit).all()

            for material in sg_suggestions:
                if material.sg_name:
                    suggestions.append({
                        'type': 'space_group',
                        'value': material.sg_name,
                        'label': f"{material.sg_name} (#{material.sg_num})",
                        'category': 'Space Groups'
                    })

        if suggestion_type in ['all', 'elements']:
            # 元素建议
            element_suggestions = _get_element_suggestions(query)
            suggestions.extend(element_suggestions)

        # 去重并限制数量
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            key = (suggestion['type'], suggestion['value'])
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= limit:
                    break

        return jsonify({'suggestions': unique_suggestions})

    except Exception as e:
        current_app.logger.error(f"Search suggestions error: {str(e)}")
        return jsonify({'suggestions': [], 'error': 'Internal server error'}), 500

def _get_element_suggestions(query):
    """获取元素建议"""
    suggestions = []
    query_lower = query.lower()

    # 从化学式解析器获取所有元素
    for element in chemical_parser.elements:
        if element.lower().startswith(query_lower):
            suggestions.append({
                'type': 'element',
                'value': element,
                'label': f"{element} (Element)",
                'category': 'Elements'
            })

    return suggestions[:10]  # 限制元素建议数量

@bp.route('/api/search/element-analysis')
def element_analysis():
    """
    分析选中元素的相关信息

    参数:
        elements: 逗号分隔的元素列表

    返回:
        元素分析结果，包括相似元素建议、元素族信息等
    """
    elements_param = request.args.get('elements', '')
    if not elements_param:
        return jsonify({'error': 'No elements provided'}), 400

    elements = [e.strip() for e in elements_param.split(',') if e.strip()]

    try:
        # 获取相似元素建议
        similar_elements = chemical_parser.suggest_similar_elements(elements)

        # 获取元素族匹配
        group_matches = chemical_parser.find_element_group_matches(elements)

        # 统计包含这些元素的材料数量（默认 OR 逻辑）并计算“最适搭配元素”
        elements_logic = (request.args.get('elements_logic', 'or') or 'or').lower()
        if elements_logic not in ('or', 'and'):
            elements_logic = 'or'

        # 读取本地全部材料
        all_materials = Material.query.all()

        # 解析所有材料的元素集合，并做基础计数
        from collections import defaultdict
        total = 0
        count_S = 0  # 满足 S（OR/AND）的材料数量
        count_e = defaultdict(int)      # 每个元素在全库中的出现材料数
        count_S_e = defaultdict(int)    # 满足 S 且包含元素 e 的材料数

        # 为减少重复解析，缓存每条材料解析结果
        parsed_material_elements = []  # list[set]

        S = set(elements)

        for material in all_materials:
            name = getattr(material, 'name', None)
            if not name:
                continue
            try:
                elems = chemical_parser.get_elements_from_formula(name)
            except Exception:
                elems = set()
            if not elems:
                continue

            parsed_material_elements.append(elems)
            total += 1

            # 全库元素计数
            for e in elems:
                count_e[e] += 1

        # 第二遍：计算满足 S 的材料数与共现
        def match_S(elems: set) -> bool:
            if not S:
                return False
            if elements_logic == 'and':
                return S.issubset(elems)
            # 默认 OR
            return bool(S & elems)

        for elems in parsed_material_elements:
            if match_S(elems):
                count_S += 1
                # 对每个不在 S 的元素做共现计数
                for e in elems:
                    if e in S:
                        continue
                    count_S_e[e] += 1

        # material_count 用于前端显示“包含这些元素的材料数量”
        material_count = count_S

        # 计算推荐搭配元素（partners）
        partners = []
        if total > 0 and count_S > 0:
            for e, c_se in count_S_e.items():
                c_e = count_e.get(e, 0)
                # 基础过滤：避免噪声
                cond = c_se / max(count_S, 1)
                if c_se < 2 or cond < 0.1:
                    continue
                # 提升度与评分（加入极小数防 0 除）
                lift = (c_se / total) / (((count_S / total) * (c_e / total)) + 1e-12)
                score = lift * cond
                partners.append({
                    'element': e,
                    'score': float(score),
                    'count_s_e': int(c_se),
                    'count_s': int(count_S),
                    'count_e': int(c_e),
                    'lift': float(lift),
                    'cond': float(cond),
                })

            # 排序并截断 Top-K（默认 10）
            partners.sort(key=lambda x: x['score'], reverse=True)
            partners = partners[:10]

        return jsonify({
            'selected_elements': elements,
            'similar_elements': similar_elements[:10],  # 限制建议数量
            'element_groups': {k: list(v) for k, v in group_matches.items()},
            'material_count': material_count,
            'partners': partners,
            'analysis': {
                'total_elements': len(elements),
                'has_metals': bool(set(elements) & chemical_parser.element_groups.get('transition_metals', set())),
                'has_nonmetals': bool(set(elements) & {'C', 'N', 'O', 'F', 'P', 'S', 'Cl', 'Se', 'Br', 'I'}),
            }
        })

    except Exception as e:
        current_app.logger.error(f"Element analysis error: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500

@bp.route('/api/materials/update-band-gap', methods=['POST'])
@csrf_exempt  # CSRF豁免，因为这是API端点
def update_band_gap():
    """
    更新材料的Band Gap值

    接收从前端计算得出的Band Gap值并保存到数据库
    """
    try:
        data = request.get_json()
        current_app.logger.info(f"Band gap update request data: {data}")

        if not data:
            current_app.logger.error("No JSON data provided in band gap update request")
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        material_id = data.get('material_id')
        band_gap = data.get('band_gap')

        current_app.logger.info(f"Extracted material_id: {material_id}, band_gap: {band_gap}")

        if material_id is None:
            return jsonify({'success': False, 'error': 'Material ID is required'}), 400

        if band_gap is None:
            return jsonify({'success': False, 'error': 'Band gap value is required'}), 400

        # 转换material_id为整数
        try:
            material_id_int = int(material_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid material ID format'}), 400

        # 查找材料
        material = Material.query.get(material_id_int)
        if not material:
            return jsonify({'success': False, 'error': 'Material not found'}), 404

        # 验证Band Gap值的合理性
        try:
            band_gap_float = float(band_gap)
            if band_gap_float < 0 or band_gap_float > 20:  # 合理范围检查
                return jsonify({'success': False, 'error': 'Band gap value out of reasonable range (0-20 eV)'}), 400
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid band gap value'}), 400

        # 更新Band Gap值
        old_band_gap = material.band_gap
        material.band_gap = band_gap_float

        try:
            db.session.commit()
            current_app.logger.info(
                f"Updated band gap for material {material.formatted_id}: "
                f"{old_band_gap} -> {band_gap_float} eV"
            )

            return jsonify({
                'success': True,
                'message': 'Band gap updated successfully',
                'material_id': material_id,
                'old_band_gap': old_band_gap,
                'new_band_gap': band_gap_float
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Database error updating band gap: {str(e)}")
            return jsonify({'success': False, 'error': 'Database update failed'}), 500

    except Exception as e:
        current_app.logger.error(f"Error in update_band_gap: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# update_metal_type API端点已移除 - 现在材料类型从band.json文件中读取

@bp.route('/admin/analyze-bands')
@login_required
@admin_required
def admin_analyze_bands():
    """管理员批量分析能带数据功能"""
    force_recalculate = request.args.get('force', 'false').lower() == 'true'

    try:
        # 获取所有材料
        materials = Material.query.all()
        material_paths = []

        for material in materials:
            if force_recalculate or material.band_gap is None or material.materials_type is None:
                material_path = f"app/static/materials/{material.formatted_id}/band"
                material_paths.append((material_path, material))

        # 批量分析
        analyzed = 0
        failed = 0
        cached = len(materials) - len(material_paths)

        for material_path, material in material_paths:
            try:
                result = band_analyzer.analyze_material(material_path)
                if result['band_gap'] is not None:
                    material.band_gap = result['band_gap']
                    material.materials_type = result['materials_type']
                    analyzed += 1
                else:
                    failed += 1
            except Exception as e:
                current_app.logger.error(f"Failed to analyze {material.formatted_id}: {e}")
                failed += 1

        db.session.commit()

        flash(_('Band analysis completed! Analyzed: %(analyzed)d, Cached: %(cached)d, Failed: %(failed)d', analyzed=analyzed, cached=cached, failed=failed), 'success')

    except Exception as e:
        current_app.logger.error(f"Error in batch band analysis: {e}")
        flash(_('Batch analysis failed: %(error)s', error=str(e)), 'error')

    return redirect(url_for('views.index'))

@bp.route('/api/band-config')
def get_band_config():
    """获取能带分析配置，供前端使用"""
    try:
        from .band_analyzer import BandAnalysisConfig
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