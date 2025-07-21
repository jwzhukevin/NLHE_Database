# view.py:
# View functions module, handling all user interface related routes and requests
# Includes homepage, material details page, add/edit materials, user authentication, etc.

# Import required modules
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file  # Flask core modules
from flask_login import login_user, logout_user, login_required, current_user  # User authentication modules
from sqlalchemy import and_, or_  # Database query condition builders
from .models import User, Material, BlockedIP, Member  # Custom data models
from . import db  # Database instance
import datetime  # Processing dates and times
import functools  # For decorators
from .material_importer import extract_chemical_formula_from_cif  # Material data import module
import os
import re
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
import random, string, io

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
def index():
    """Material database page - displays material list, supports search, filtering and pagination

    Supported GET parameters:
        q: Search keywords
        status: Material status filter
        metal_type: Metal type filter
        formation_energy_min/max: Formation energy range filter
        fermi_level_min/max: Fermi level range filter
        page: Current page number
    """
    try:
        # Basic query (get all material records)
        query = Material.query

        # Get all search parameters (stored in dictionary for unified processing)
        search_params = {
            'q': request.args.get('q', '').strip(),  # Text search keywords
            'status': request.args.get('status', '').strip(),  # Material status
            'metal_type': request.args.get('metal_type', '').strip(),  # Metal type
            'formation_energy_min': request.args.get('formation_energy_min', '').strip(),  # Formation energy minimum
            'formation_energy_max': request.args.get('formation_energy_max', '').strip(),  # Formation energy maximum
            'fermi_level_min': request.args.get('fermi_level_min', '').strip(),  # Fermi level minimum
            'fermi_level_max': request.args.get('fermi_level_max', '').strip(),  # Fermi level maximum
        }

        # Build compound filter conditions (using SQLAlchemy logical operators)
        filters = []

        # Text search (supports fuzzy query of name, VBM/CBM coordinates)
        if search_params['q']:
            filters.append(or_(
                Material.name.ilike(f'%{search_params["q"]}%'),  # Name fuzzy matching (case insensitive)
                Material.vbm_coordi.ilike(f'%{search_params["q"]}%'),  # VBM coordinate matching
                Material.cbm_coordi.ilike(f'%{search_params["q"]}%')  # CBM coordinate matching
            ))

        # Exact match conditions
        if search_params['status']:
            filters.append(Material.status == search_params['status'])  # Status exact match
        if search_params['metal_type']:
            filters.append(Material.metal_type == search_params['metal_type'])  # Metal type exact match

        # Numeric range filtering (including exception handling to ensure valid numerical input)
        for param in ['formation_energy', 'fermi_level']:
            min_val = search_params[f'{param}_min']
            max_val = search_params[f'{param}_max']
            if min_val:
                try:
                    filters.append(getattr(Material, param) >= float(min_val))  # Minimum value filter
                except ValueError:  # Handle invalid numerical input
                    pass
            if max_val:
                try:
                    filters.append(getattr(Material, param) <= float(max_val))  # Maximum value filter
                except ValueError:
                    pass

        # Apply all filter conditions (using AND logic combination, i.e., all conditions must be met)
        if filters:
            query = query.filter(and_(*filters))

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
        current_app.logger.error(f"数据库查询错误: {str(e)}")
        # 返回空的材料列表和搜索参数
        from flask_sqlalchemy import Pagination
        empty_pagination = Pagination(query=None, page=1, per_page=10, total=0, items=[])
        return render_template('main/index.html',
                             materials=[],
                             pagination=empty_pagination,
                             search_params={},
                             error_message="数据库未初始化，请联系管理员")

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
                'total_energy': safe_float(request.form.get('total_energy')),
                'formation_energy': safe_float(request.form.get('formation_energy')),
                'fermi_level': safe_float(request.form.get('efermi')),
                'vacuum_level': safe_float(request.form.get('vacuum_level')),
                'workfunction': safe_float(request.form.get('workfunction')),
                'metal_type': request.form.get('metal_type'),
                'gap': safe_float(request.form.get('gap')),
                'vbm_energy': safe_float(request.form.get('vbm_energy')),
                'cbm_energy': safe_float(request.form.get('cbm_energy')),
                'vbm_coordi': request.form.get('vbm_coordi'),
                'cbm_coordi': request.form.get('cbm_coordi'),
                'vbm_index': safe_int(request.form.get('vbm_index')),
                'cbm_index': safe_int(request.form.get('cbm_index'))
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
                    flash('请上传.cif格式的结构文件！', 'error')
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
                        flash(f'材料名"{chemical_name}"已存在，请更换CIF文件', 'error')
                        return redirect(url_for('views.edit', material_id=material_id))
                    material.name = chemical_name
                    flash(f'材料名已从CIF文件更新: {chemical_name}', 'info')

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
                flash('材料名不能为空！', 'error')
                return redirect(url_for('views.edit', material_id=material_id))
            material.status = request.form.get('status')
            material.total_energy = safe_float(request.form.get('total_energy'))
            material.formation_energy = safe_float(request.form.get('formation_energy'))
            material.fermi_level = safe_float(request.form.get('efermi'))
            material.vacuum_level = safe_float(request.form.get('vacuum_level'))
            material.workfunction = safe_float(request.form.get('workfunction'))
            material.metal_type = request.form.get('metal_type')
            material.gap = safe_float(request.form.get('gap'))
            material.vbm_energy = safe_float(request.form.get('vbm_energy'))
            material.cbm_energy = safe_float(request.form.get('cbm_energy'))
            material.vbm_coordi = request.form.get('vbm_coordi')
            material.cbm_coordi = request.form.get('cbm_coordi')
            material.vbm_index = safe_int(request.form.get('vbm_index'))
            material.cbm_index = safe_int(request.form.get('cbm_index'))
            db.session.commit()
            flash('材料信息已更新。', 'success')
            return redirect(url_for('views.detail', material_id=material_id))
        except ValueError as e:
            flash(f'数据无效: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'发生错误: {str(e)}', 'error')
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

    # 检查能带文件
    if os.path.exists(band_dir):
        band_files = [f for f in os.listdir(band_dir) if f.endswith('.dat') or f.endswith('.json')]
        if len(band_files) > 1:
            flash('Warning: Multiple band files found in band directory. Please keep only one!', 'warning')

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
    # band文件
    band_files = glob.glob(os.path.join(band_dir, '*.dat')) + glob.glob(os.path.join(band_dir, '*.json')) if os.path.exists(band_dir) else []
    if len(band_files) == 1:
        band_file = os.path.relpath(band_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(band_files) > 1:
        flash('Error: Multiple band files found in band directory. Please keep only one!', 'error')
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

# User login route
@bp.route('/login', methods=['GET', 'POST'])
@check_ip_blocked
def login():
    """
    User login page and processing logic
    
    GET request: Display login form
    POST request: Validate user credentials and process login
    """
    # If user is already logged in, redirect to homepage
    if current_user.is_authenticated:
        return redirect(url_for('views.index'))
    
    if request.method == 'POST':
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
        
        # Check login failure count
        ip = get_client_ip()
        failed_key = f"login_failed:{ip}"
        failed_attempts = session.get(failed_key, 0)
        max_attempts = 5  # Maximum attempts
        
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
        
        # Login successful, clear failure count
        session.pop(failed_key, None)
        login_user(user_by_email, remember=remember)
        
        # Show welcome message with username
        flash(f'Welcome back, {user_by_email.username}!', 'success')
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('views.index'))
        
    return render_template('auth/login.html')

# User logout route
@bp.route('/logout')
@login_required  # Login protection decorator, ensuring only logged-in users can logout
def logout():
    """
    Handle user logout
    
    Perform logout operation and redirect to homepage
    """
    logout_user()  # Flask-Login logout method, clear user session
    flash('Goodbye.', 'info')  # Display information message
    return redirect(url_for('views.index'))  # Redirect to homepage

# User settings route
@bp.route('/settings', methods=['GET', 'POST'])
@login_required  # Login protection decorator
def settings():
    """
    User settings page and processing logic
    
    GET request: Display settings form
    POST request: Update user settings
    """
    if request.method == 'POST':
        username = request.form['username'].strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Store original values for comparison
        original_username = current_user.username
        has_password_change = bool(new_password)
        
        # Validate inputs
        if not username:
            flash('Username is required.', 'error')
            return redirect(url_for('views.settings'))
        
        if len(username) > 20:
            flash('Username must be 20 characters or less.', 'error')
            return redirect(url_for('views.settings'))
        
        # Check if another user already has this username (except current user)
        if username != original_username:
            existing_user = User.query.filter(User.username == username, User.email != current_user.email).first()
            if existing_user:
                flash('This username is already taken. Please choose another.', 'error')
                return redirect(url_for('views.settings'))
        
        # Password change logic
        if has_password_change:
            # Verify current password
            if not current_user.validate_password(current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('views.settings'))
            
            # Validate new password
            if len(new_password) < 8:
                flash('New password must be at least 8 characters long.', 'error')
                return redirect(url_for('views.settings'))
            
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('views.settings'))
        
        try:
            # Start a transaction
            # First update the database
            current_user.username = username
            
            # Set new password if provided
            if has_password_change:
                current_user.set_password(new_password)
                
            # Now directly update the users.dat file
            users_file = os.path.join(current_app.root_path, 'static/users/users.dat')
            
            # Create backup of original file
            backup_file = f"{users_file}.bak"
            if os.path.exists(users_file):
                import shutil
                try:
                    shutil.copy2(users_file, backup_file)
                except Exception as e:
                    current_app.logger.warning(f"Could not create backup of users.dat: {str(e)}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            
            # Read all lines from users.dat
            lines = []
            if os.path.exists(users_file):
                try:
                    with open(users_file, 'r') as f:
                        lines = f.readlines()
                except Exception as e:
                    current_app.logger.error(f"Error reading users.dat: {str(e)}")
                    lines = []
            
            # Find and update the current user's line
            updated = False
            new_lines = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    new_lines.append(line)
                    continue
                
                parts = line.split(':')
                if len(parts) >= 4:
                    email, old_username, password, role = parts[0], parts[1], parts[2], parts[3]
                    
                    # If this is the current user's line
                    if email == current_user.email:
                        # Update username
                        old_username = username
                        
                        # Update password if changed
                        if has_password_change:
                            # We need to extract the raw password from bcrypt hash
                            # Since we can't do that, we'll use the new_password directly
                            password = new_password
                        
                        updated = True
                        new_line = f"{email}:{old_username}:{password}:{role}"
                        new_lines.append(new_line)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            # If user wasn't found in the file, add them
            if not updated:
                role = current_user.role
                password = new_password if has_password_change else "password123"  # Default password
                new_line = f"{current_user.email}:{username}:{password}:{role}"
                new_lines.append(new_line)
            
            # Write updated content back to users.dat
            try:
                with open(users_file, 'w') as f:
                    for i, line in enumerate(new_lines):
                        # Add newline except for the last line
                        if i < len(new_lines) - 1 or not line.strip():
                            f.write(line + '\n')
                        else:
                            f.write(line)
                
                current_app.logger.info(f"Updated user {current_user.email} in users.dat file")
            except Exception as e:
                current_app.logger.error(f"Failed to update users.dat: {str(e)}")
                db.session.rollback()
                flash(f'An error occurred while saving your settings: {str(e)}', 'error')
                return redirect(url_for('views.settings'))
            
            # Commit database changes after successful file update
            db.session.commit()
            
            if has_password_change:
                flash('Settings updated successfully. Your password has been changed.', 'success')
            else:
                flash('Settings updated successfully.', 'success')
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating user settings: {str(e)}")
            flash(f'An error occurred while saving your settings: {str(e)}', 'error')
            
        return redirect(url_for('views.index'))
    
    return render_template('auth/settings.html', user=current_user)

# Helper function to update users.dat file (kept for backward compatibility)
def update_users_dat():
    """Update users.dat file with latest user information"""
    users_file = os.path.join(current_app.root_path, 'static/users/users.dat')
    
    # Get all users from database
    users = User.query.all()
    
    # Create backup of original file
    backup_file = f"{users_file}.bak"
    if os.path.exists(users_file):
        import shutil
        try:
            shutil.copy2(users_file, backup_file)
        except Exception as e:
            current_app.logger.warning(f"Could not create backup of users.dat: {str(e)}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(users_file), exist_ok=True)
    
    # Read existing users.dat file to preserve passwords
    existing_data = {}
    if os.path.exists(users_file):
        try:
            with open(users_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split(':')
                    if len(parts) >= 4:
                        email, username, password, role = parts[0], parts[1], parts[2], parts[3]
                        # Store data by email
                        existing_data[email] = {'username': username, 'password': password, 'role': role}
        except Exception as e:
            current_app.logger.error(f"Error reading users.dat: {str(e)}")
    
    # Write updated user data to file
    try:
        with open(users_file, 'w') as f:
            f.write("# Format: email:username:password:role\n")
            f.write("# Available roles: admin, user\n")
            f.write("# One user per line\n")
            
            for user in users:
                # Get password from existing file or use default
                password = None
                
                if user.email in existing_data:
                    password = existing_data[user.email]['password']
                    
                # If password not found, use a placeholder
                if not password:
                    password = "password123"  # Default password
                    current_app.logger.warning(f"No existing password found for {user.email}, using default")
                
                line = f"{user.email}:{user.username}:{password}:{user.role}\n"
                f.write(line)
        
        current_app.logger.info(f"Updated users.dat file with {len(users)} users")
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to update users.dat: {str(e)}")
        raise

def generate_captcha_image(text, width=140, height=50):
    """
    使用Pillow生成符合网站风格的验证码图片

    参数:
        text: 验证码文本
        width: 图片宽度
        height: 图片高度

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

    # 创建渐变背景
    image = Image.new('RGB', (width, height), color=THEME_COLORS['light_bg'])
    draw = ImageDraw.Draw(image)

    # 添加微妙的渐变背景效果
    for y in range(height):
        # 从浅蓝到更浅的蓝色渐变
        ratio = y / height
        r = int(THEME_COLORS['light_bg'][0] + (THEME_COLORS['nav_bg'][0] - THEME_COLORS['light_bg'][0]) * ratio * 0.3)
        g = int(THEME_COLORS['light_bg'][1] + (THEME_COLORS['nav_bg'][1] - THEME_COLORS['light_bg'][1]) * ratio * 0.3)
        b = int(THEME_COLORS['light_bg'][2] + (THEME_COLORS['nav_bg'][2] - THEME_COLORS['light_bg'][2]) * ratio * 0.3)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 尝试加载字体
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 28)
    except (OSError, IOError):
        try:
            # 尝试使用其他常见字体
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("calibri.ttf", 28)
            except (OSError, IOError):
                # 使用默认字体
                font = ImageFont.load_default()

    # 添加精致的背景装饰点
    for _ in range(30):
        x = random.randint(0, width)
        y = random.randint(0, height)
        # 使用主题色的浅色版本作为装饰点
        alpha = random.uniform(0.1, 0.3)
        base_color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        color = tuple(int(c + (255 - c) * (1 - alpha)) for c in base_color)
        draw.ellipse([x-1, y-1, x+1, y+1], fill=color)

    # 计算文本位置
    try:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError:
        # 兼容旧版本Pillow
        text_width = len(text) * 20
        text_height = 28

    start_x = (width - text_width) // 2
    start_y = (height - text_height) // 2

    # 绘制验证码文本 - 使用网站主题色
    char_colors = [
        THEME_COLORS['primary'],
        THEME_COLORS['secondary'],
        THEME_COLORS['accent'],
        THEME_COLORS['text_dark']
    ]

    char_width = text_width // len(text) if len(text) > 0 else 20
    for i, char in enumerate(text):
        # 为每个字符选择主题色
        color = char_colors[i % len(char_colors)]

        # 添加轻微的位置偏移，但保持可读性
        char_x = start_x + i * char_width + random.randint(-2, 2)
        char_y = start_y + random.randint(-3, 3)

        # 绘制字符
        draw.text((char_x, char_y), char, font=font, fill=color)

    # 添加优雅的装饰线条
    for _ in range(2):
        # 使用主题色绘制装饰线
        color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        # 让线条更加柔和
        alpha_color = tuple(int(c + (255 - c) * 0.6) for c in color)

        start_x_line = random.randint(0, width // 3)
        start_y_line = random.randint(height // 4, 3 * height // 4)
        end_x_line = random.randint(2 * width // 3, width)
        end_y_line = random.randint(height // 4, 3 * height // 4)

        draw.line([(start_x_line, start_y_line), (end_x_line, end_y_line)],
                 fill=alpha_color, width=1)

    # 添加边框效果
    border_color = THEME_COLORS['primary']
    border_alpha = tuple(int(c + (255 - c) * 0.7) for c in border_color)
    draw.rectangle([0, 0, width-1, height-1], outline=border_alpha, width=1)

    # 保存到BytesIO
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', quality=95)
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

        # 生成验证码图片
        img_buffer = generate_captcha_image(captcha_text)

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