# view.py:
# View functions module, handling all user interface related routes and requests
# Includes homepage, material details page, add/edit materials, user authentication, etc.

# Import required modules
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify  # Flask core modules
from flask_login import login_user, logout_user, login_required, current_user  # User authentication modules
from sqlalchemy import and_, or_  # Database query condition builders
from .models import User, Material, BlockedIP, Member  # Custom data models
from . import db  # Database instance
import datetime  # Processing dates and times
import functools  # For decorators
from .material_importer import extract_chemical_formula_from_cif  # Material data import module
from .chemical_parser import chemical_parser  # 智能化学式解析器
from .search_optimizer import search_cache, QueryOptimizer, performance_monitor, cached_search  # 搜索性能优化
from .band_analyzer import band_analyzer  # 合并后的能带分析器
import os
import re
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import random, string, io
from .security_utils import log_security_event, sanitize_input, regenerate_session, check_rate_limit
from .auth_manager import LoginStateManager, LoginErrorHandler

# 尝试导入CSRF豁免装饰器
try:
    from flask_wtf.csrf import exempt as csrf_exempt
    csrf_exempt_available = True
except ImportError:
    csrf_exempt_available = False
    def csrf_exempt(f):
        return f  # 如果没有Flask-WTF，返回原函数

# Create a blueprint named 'views' for modular route management
bp = Blueprint('views', __name__)

# Register template filters
@bp.app_template_filter('any')
def any_filter(d):
    """Check if a dictionary has at least one non-empty value (for frontend conditional judgment)
    
    Parameters:
        d: Dictionary to check
    
    Returns: 
        Boolean value indicating whether the dictionary has valid data, used to determine whether to display the reset search button, etc.
    """
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """Generate a new dictionary excluding the specified key (for cleaning search parameters)
    
    Parameters:
        d: Original dictionary
        exclude_key: Key to exclude
    
    Returns: 
        Processed new dictionary, used to build URLs that remove a certain filter condition
    """
    return {k: v for k, v in d.items() if k != exclude_key}

# Landing page route
@bp.route('/')
def landing():
    """Website introduction page - displays website features and functionality overview"""
    return render_template('main/landing.html')

@bp.route('/database')
@performance_monitor
@cached_search(cache_enabled=True)
def index():
    """Material database page - displays material list, supports search, filtering and pagination

    Supported GET parameters:
        q: Search keywords
        status: Material status filter
        materials_type: Materials type filter (从band.json读取)
        fermi_level_min/max: Fermi level range filter
        page: Current page number
    """
    try:
        # Get all search parameters (stored in dictionary for unified processing)
        search_params = {
            'q': request.args.get('q', '').strip(),  # Text search keywords
            'materials_type': request.args.get('materials_type', '').strip(),  # Materials type (从band.json读取)
            'elements': request.args.get('elements', '').strip(),  # Selected elements from periodic table
            'fermi_level_min': request.args.get('fermi_level_min', '').strip(),  # Fermi level minimum
            'fermi_level_max': request.args.get('fermi_level_max', '').strip(),  # Fermi level maximum
            'max_sc_min': request.args.get('max_sc_min', '').strip(),  # Max SC minimum
            'max_sc_max': request.args.get('max_sc_max', '').strip(),  # Max SC maximum
            'band_gap_min': request.args.get('band_gap_min', '').strip(),  # Band gap minimum
            'band_gap_max': request.args.get('band_gap_max', '').strip(),  # Band gap maximum
        }

        # 使用优化的查询器
        optimization_result = QueryOptimizer.optimize_material_search(search_params)
        query = optimization_result['query']

        # 记录性能信息
        current_app.logger.info(
            f"Search optimization: {optimization_result['filters_applied']} filters, "
            f"{optimization_result['total_count']} results, "
            f"{optimization_result['execution_time']:.3f}s"
        )

        # 处理元素搜索（QueryOptimizer不处理的特殊逻辑）
        additional_filters = []

        # Element-based search (智能化学式搜索) - 这是QueryOptimizer不处理的特殊逻辑
        if search_params['elements']:
            element_list = [elem.strip() for elem in search_params['elements'].split(',') if elem.strip()]
            if element_list:
                # 智能元素搜索：支持精确匹配、包含匹配和相似元素建议
                element_filters = []

                # 优化：只获取当前查询结果中的材料进行元素匹配
                current_materials = query.all()
                matching_material_ids = []

                for material in current_materials:
                    if material.name:
                        # 使用化学式解析器检查元素匹配
                        if chemical_parser.contains_elements(material.name, element_list, 'any'):
                            matching_material_ids.append(material.id)

                # 如果找到匹配的材料，添加到过滤条件
                if matching_material_ids:
                    additional_filters.append(Material.id.in_(matching_material_ids))
                else:
                    # 如果没有精确匹配，尝试模糊匹配
                    for element in element_list:
                        element_filters.append(Material.name.ilike(f'%{element}%'))
                    if element_filters:
                        additional_filters.append(or_(*element_filters))

        # 应用额外的过滤条件（主要是元素搜索）
        if additional_filters:
            query = query.filter(and_(*additional_filters))

        # 添加搜索结果验证
        total_results = query.count()
        current_app.logger.info(f"Search query returned {total_results} results with search params: {search_params}")

        # Pagination configuration (10 records per page)
        page = request.args.get('page', 1, type=int)  # Get current page number, default is page 1
        per_page = 10  # Items per page
        pagination = query.order_by(Material.name.asc()).paginate(  # Sort by name in ascending order
            page=page,
            per_page=per_page,
            error_out=False  # Disable invalid page number errors, out of range will return empty list
        )

        # Render template and pass pagination object and search parameters
        return render_template('main/index.html',
                             materials=pagination.items,  # Current page data
                             pagination=pagination,  # Pagination object (including page number information)
                             search_params=search_params)  # Search parameters (for form display)

    except Exception as e:
        current_app.logger.error(f"Database query error: {str(e)}")
        # Return empty material list and search parameters
        from flask_sqlalchemy import Pagination
        empty_pagination = Pagination(query=None, page=1, per_page=10, total=0, items=[])
        return render_template('main/index.html',
                             materials=[],
                             pagination=empty_pagination,
                             search_params={},
                             error_message="Database not initialized, please contact administrator")

# Define an admin check decorator
def admin_required(view_func):
    """
    Decorator to restrict route access to admin users only
    
    If user is not authenticated or not an admin, redirect to login page
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. This feature requires administrator privileges.', 'error')
            return redirect(url_for('views.login'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# 工具函数：根据材料ID获取材料目录，自动兼容新旧格式
def get_material_dir(material_id):
    """
    根据材料ID返回材料目录路径，优先新格式IMR-{id}，找不到则兼容旧格式IMR-00000001。
    """
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    if os.path.exists(new_dir):
        return new_dir
    # 兼容旧格式
    old_dir = os.path.join(base_dir, f'IMR-{int(material_id):08d}')
    if os.path.exists(old_dir):
        return old_dir
    return new_dir  # 默认返回新格式路径

# Material add route (admin required)
@bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    """
    添加新材料，ID目录用IMR-{id}格式，兼容旧格式。
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

            # 材料名优先用CIF解析结果，否则用Material+ID
            material_data = {
                'name': chemical_name if chemical_name else None,
                'status': request.form.get('status'),
                'structure_file': structure_filename,  # 仅作记录，实际读取时遍历目录
                'properties_json': properties_json.filename if properties_json and properties_json.filename else None,
                'sc_structure_file': sc_structure_file.filename if sc_structure_file and sc_structure_file.filename else None,
                'fermi_level': safe_float(request.form.get('fermi_level')),
                'band_gap': safe_float(request.form.get('band_gap')),
                'materials_type': request.form.get('materials_type')
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
                flash(f'Shift Current file {sc_filename} uploaded successfully', 'success')

                # 如果是dat文件，尝试重命名为sc.dat
                if sc_filename.endswith('.dat') and sc_filename != 'sc.dat':
                    try:
                        new_sc_path = os.path.join(sc_dir, 'sc.dat')
                        os.rename(sc_path, new_sc_path)
                        material.sc_structure_file = 'sc.dat'
                        flash('Shift Current file renamed to sc.dat', 'success')
                    except Exception as e:
                        current_app.logger.warning(f"Failed to rename SC file: {str(e)}")

            db.session.commit()
            flash(f'Material {material.name} added successfully!', 'success')
            return redirect(url_for('views.detail', material_id=material.id))

        except ValueError as e:
            flash(f'Invalid data: {str(e)}', 'error')
            return redirect(url_for('views.add'))
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('views.add'))

    return render_template('materials/add.html')

# Safe numeric conversion helper functions
def safe_float(value):
    """Safely convert string to float (allows empty values)
    
    Parameters:
        value: Input string
    
    Returns: 
        float or None, returns None if conversion fails or input is empty
    """
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    """Safely convert string to integer (allows empty values)
    
    Parameters:
        value: Input string
    
    Returns: 
        int or None, returns None if conversion fails or input is empty
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
                    flash('Please upload a .cif format structure file!', 'error')
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
                        flash(f'Material name "{chemical_name}" already exists, please change CIF file', 'error')
                        return redirect(url_for('views.edit', material_id=material_id))
                    material.name = chemical_name
                    flash(f'Material name updated from CIF file: {chemical_name}', 'info')

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
                flash('Material name cannot be empty!', 'error')
                return redirect(url_for('views.edit', material_id=material_id))
            material.status = request.form.get('status')
            material.fermi_level = safe_float(request.form.get('fermi_level'))
            # 电子性质参数 - 只保留带隙和材料类型
            material.band_gap = safe_float(request.form.get('band_gap'))
            material.materials_type = request.form.get('materials_type')
            db.session.commit()
            flash('Material information updated successfully.', 'success')
            return redirect(url_for('views.detail', material_id=material_id))
        except ValueError as e:
            flash(f'Invalid data: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
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
            flash('Warning: Multiple CIF files found in structure directory. Please keep only one!', 'warning')

    # 检查能带文件（只检查.dat文件，.json是分析结果文件）
    if os.path.exists(band_dir):
        band_dat_files = [f for f in os.listdir(band_dir) if f.endswith('.dat')]
        if len(band_dat_files) > 1:
            flash('Warning: Multiple band .dat files found in band directory. Please keep only one!', 'warning')
        # 获取所有能带相关文件用于显示
        band_files = [f for f in os.listdir(band_dir) if f.endswith('.dat') or f.endswith('.json')]

    # 检查SC文件
    if os.path.exists(sc_dir):
        sc_files = [f for f in os.listdir(sc_dir) if f.endswith('.dat')]
        if len(sc_files) > 1:
            flash('Warning: Multiple SC files found in sc directory. Please keep only one!', 'warning')
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
        flash('Error: Multiple CIF files found in structure directory. Please keep only one!', 'error')
        structure_file = None
    else:
        structure_file = None
    # band文件（只检查.dat文件，.json是分析结果文件）
    band_dat_files = glob.glob(os.path.join(band_dir, '*.dat')) if os.path.exists(band_dir) else []
    if len(band_dat_files) == 1:
        band_file = os.path.relpath(band_dat_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(band_dat_files) > 1:
        flash('Error: Multiple band .dat files found in band directory. Please keep only one!', 'error')
        band_file = None
    else:
        band_file = None
    # Shift Current文件
    sc_files = glob.glob(os.path.join(sc_dir, '*.dat')) if os.path.exists(sc_dir) else []
    if len(sc_files) == 1:
        sc_file = os.path.relpath(sc_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(sc_files) > 1:
        flash('Error: Multiple SC files found in sc directory. Please keep only one!', 'error')
        sc_file = None
    else:
        sc_file = None
    return render_template('materials/detail.html', material=material, structure_file=structure_file, band_file=band_file, sc_file=sc_file)

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
    flash(f'Material "{material.name}" and all related files have been successfully deleted.', 'success')  # Display success message
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
            flash('Access denied. Your IP has been blocked due to multiple failed login attempts.', 'error')
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
            flash('Security token expired or invalid. Please try again.', 'error')
            current_app.logger.warning(f"CSRF validation failed for login: {str(e)}")
            return render_template('auth/login.html')

        email = request.form.get('email')
        username = request.form.get('username')
        captcha_input = request.form.get('captcha', '').upper()
        real_captcha = session.get('captcha', '')
        if captcha_input != real_captcha:
            flash('Invalid captcha code, please try again', 'error')
            return render_template('auth/login.html')
        password = request.form.get('password')
        remember = 'remember' in request.form
        login_type = request.form.get('login_type')
        admin_login = login_type == 'admin'
        
        # Form validation
        if not email or not username or not password:
            flash('All fields are required.', 'error')
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
                flash('Your IP has been blocked due to too many failed login attempts.', 'error')
                return redirect(url_for('views.login'))
            
            flash(f'Email not found. Please check your email address. You have {remaining_attempts} attempts remaining.', 'error')
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
                flash('Your IP has been blocked due to too many failed login attempts.', 'error')
                return redirect(url_for('views.login'))
            
            flash(f'Username does not match this email address. You have {remaining_attempts} attempts remaining.', 'error')
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
                flash('Your IP has been blocked due to too many unauthorized admin login attempts.', 'error')
                return redirect(url_for('views.login'))
            
            flash(f'This account does not have administrator privileges. You have {remaining_attempts} attempts remaining.', 'error')
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
                flash('Your IP has been blocked due to too many failed login attempts.', 'error')
                return redirect(url_for('views.login'))
            
            flash(f'Incorrect password. You have {remaining_attempts} attempts remaining.', 'error')
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
        flash('Logout completed.', 'info')
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
    flash('Session cleared successfully.', 'info')
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

    # 智能字体加载 - 根据缩放因子调整字体大小
    base_font_size = 28
    font_size = int(base_font_size * scale_factor)

    # 按优先级尝试加载字体，确保跨平台兼容性
    font_candidates = [
        "arial.ttf",                    # Windows
        "Arial.ttf",                    # macOS
        "DejaVuSans-Bold.ttf",         # Linux
        "calibri.ttf",                  # Windows备选
        "Helvetica.ttc",               # macOS备选
        "/System/Library/Fonts/Arial.ttf",  # macOS系统路径
        "C:/Windows/Fonts/arial.ttf",  # Windows系统路径
    ]

    font = None
    for font_name in font_candidates:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except (OSError, IOError):
            continue

    # 如果所有字体都加载失败，使用默认字体
    if font is None:
        font = ImageFont.load_default()

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

@bp.route('/members')
def members():
    """
    研究部成员展示页面
    """
    members = Member.query.all()  # 查询所有成员
    return render_template('members/index.html', members=members)

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

        # 统计包含这些元素的材料数量
        material_count = 0
        all_materials = Material.query.all()
        for material in all_materials:
            if material.name and chemical_parser.contains_elements(material.name, elements, 'any'):
                material_count += 1

        return jsonify({
            'selected_elements': elements,
            'similar_elements': similar_elements[:10],  # 限制建议数量
            'element_groups': {k: list(v) for k, v in group_matches.items()},
            'material_count': material_count,
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

        flash(f'Band analysis completed! '
              f'Analyzed: {analyzed}, '
              f'Cached: {cached}, '
              f'Failed: {failed}', 'success')

    except Exception as e:
        current_app.logger.error(f"Error in batch band analysis: {e}")
        flash(f'Batch analysis failed: {str(e)}', 'error')

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