# view.py:
# 导入所需模块
from flask import Blueprint, render_template, request, redirect, url_for, flash  # Flask 核心模块
from flask_login import login_user, logout_user, login_required, current_user  # 用户认证模块
from sqlalchemy import and_, or_  # 数据库查询条件构造器
from .models import User, Material  # 自定义数据模型
from . import db  # 数据库实例

# 创建名为'views'的蓝图，用于模块化路由管理
bp = Blueprint('views', __name__)

# 注册模板过滤器
@bp.app_template_filter('any')
def any_filter(d):
    """检查字典是否存在至少一个非空值（用于前端条件判断）
    参数d: 待检查的字典
    返回: 布尔值，表示字典是否有有效数据"""
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """生成排除指定键的新字典（用于清理搜索参数）
    参数d: 原始字典
    exclude_key: 需要排除的键
    返回: 处理后的新字典"""
    return {k: v for k, v in d.items() if k != exclude_key}

# 首页路由（支持复杂搜索和分页）
@bp.route('/')
def index():
    # 基础查询（获取所有材料记录）
    query = Material.query
    
    # 获取所有搜索参数（使用字典存储便于统一处理）
    search_params = {
        'q': request.args.get('q', '').strip(),  # 文本搜索关键词
        'status': request.args.get('status', '').strip(),  # 材料状态
        'metal_type': request.args.get('metal_type', '').strip(),  # 金属类型
        'formation_energy_min': request.args.get('formation_energy_min', '').strip(),  # 形成能最小值
        'formation_energy_max': request.args.get('formation_energy_max', '').strip(),  # 形成能最大值
        'fermi_level_min': request.args.get('fermi_level_min', '').strip(),  # 费米能级最小值
        'fermi_level_max': request.args.get('fermi_level_max', '').strip(),  # 费米能级最大值
    }
    
    # 构建复合过滤条件（使用SQLAlchemy的逻辑运算符）
    filters = []
    
    # 文本搜索（支持名称、VBM/CBM坐标的模糊查询）
    if search_params['q']:
        filters.append(or_(
            Material.name.ilike(f'%{search_params["q"]}%'),  # 名称模糊匹配
            Material.vbm_coordi.ilike(f'%{search_params["q"]}%'),  # VBM坐标匹配
            Material.cbm_coordi.ilike(f'%{search_params["q"]}%')  # CBM坐标匹配
        ))
    
    # 精确匹配条件
    if search_params['status']:
        filters.append(Material.status == search_params['status'])  # 状态精确匹配
    if search_params['metal_type']:
        filters.append(Material.metal_type == search_params['metal_type'])  # 金属类型精确匹配
    
    # 数值范围过滤（包含异常处理）
    for param in ['formation_energy', 'fermi_level']:
        min_val = search_params[f'{param}_min']
        max_val = search_params[f'{param}_max']
        if min_val:
            try:
                filters.append(getattr(Material, param) >= float(min_val))  # 最小值过滤
            except ValueError:  # 处理非法数值输入
                pass
        if max_val:
            try:
                filters.append(getattr(Material, param) <= float(max_val))  # 最大值过滤
            except ValueError:
                pass
    
    # 应用所有过滤条件（使用AND逻辑组合）
    if filters:
        query = query.filter(and_(*filters))
    
    # 分页配置（每页10条记录）
    page = request.args.get('page', 1, type=int)  # 获取当前页码
    per_page = 10  # 每页条目数
    pagination = query.order_by(Material.name.asc()).paginate(  # 按名称升序排序
        page=page, 
        per_page=per_page, 
        error_out=False  # 禁用无效页码错误
    )
    
    # 渲染模板并传递分页对象和搜索参数
    return render_template('index.html',
                         materials=pagination.items,  # 当前页数据
                         pagination=pagination,  # 分页对象（包含页码信息）
                         search_params=search_params)  # 搜索参数（用于表单回显）

# 材料添加路由（需登录）
@bp.route('/add', methods=['GET', 'POST'])
@login_required  # 登录保护装饰器
def add():
    if request.method == 'POST':
        try:
            # 获取并处理上传的文件
            structure_file = request.files.get('structure_file')
            if not structure_file or not structure_file.filename.endswith('.cif'):
                flash('Please upload a valid CIF file!', 'error')
                return redirect(url_for('views.add'))
            
            # 生成安全的文件名并保存
            from werkzeug.utils import secure_filename
            import os
            filename = secure_filename(structure_file.filename)
            file_path = os.path.join(current_app.root_path, 'static/structures', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            structure_file.save(file_path)
            
            # 获取并转换表单数据（使用safe_float处理空值）
            material_data = {
                'name': request.form.get('name'),  # 材料名称（必填）
                'status': request.form.get('status'),  # 状态（必填）
                'structure_file': filename,  # 结构文件路径
                'total_energy': float(request.form.get('total_energy')),  # 总能量
                'formation_energy': float(request.form.get('formation_energy')),  # 形成能
                'fermi_level': safe_float(request.form.get('fermi_level')),  # 费米能级（允许空）
                'vacuum_level': safe_float(request.form.get('vacuum_level')),  # 真空能级
                'workfunction': safe_float(request.form.get('workfunction')),  # 功函数
                'metal_type': request.form.get('metal_type'),  # 金属类型
                'gap': safe_float(request.form.get('gap')),  # 带隙
                'vbm_energy': safe_float(request.form.get('vbm_energy')),  # VBM能量
                'cbm_energy': safe_float(request.form.get('cbm_energy')),  # CBM能量
                'vbm_coordi': request.form.get('vbm_coordi'),  # VBM坐标
                'cbm_coordi': request.form.get('cbm_coordi'),  # CBM坐标
                'vbm_index': safe_int(request.form.get('vbm_index')),  # VBM索引
                'cbm_index': safe_int(request.form.get('cbm_index'))  # CBM索引
            }

            # 必填字段验证
            if not all([material_data['name'], material_data['status']]):
                flash('Name and Status are required!', 'error')  # 闪现错误消息
                return redirect(url_for('views.add'))

            # 创建Material对象并验证数据
            material = Material(**material_data)
            material.validate()  # 调用模型自定义验证方法
            
            # 数据库操作
            db.session.add(material)
            db.session.commit()  # 提交事务
            flash('Material added successfully.', 'success')
            return redirect(url_for('views.index'))

        except ValueError as e:  # 处理数据类型错误
            flash(f'Invalid data: {str(e)}', 'error')
            return redirect(url_for('views.add'))
        except Exception as e:  # 处理其他数据库错误
            db.session.rollback()  # 回滚事务
            flash('Database error occurred', 'error')
            return redirect(url_for('views.add'))

    return render_template('add.html')  # GET请求返回表单页

# 安全数值转换辅助函数
def safe_float(value):
    """将字符串安全转换为浮点数（允许空值）
    参数value: 输入字符串
    返回: float或None"""
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    """将字符串安全转换为整数（允许空值）
    参数value: 输入字符串
    返回: int或None"""
    try:
        return int(value) if value else None
    except ValueError:
        return None

# 材料编辑路由
@bp.route('/material/edit/<int:material_id>', methods=['GET', 'POST'])
@login_required
def edit(material_id):
    material = Material.query.get_or_404(material_id)  # 获取材料或返回404
    if request.method == 'POST':
        try:
            # 处理文件上传
            structure_file = request.files.get('structure_file')
            if structure_file and structure_file.filename.endswith('.cif'):
                from werkzeug.utils import secure_filename
                import os
                filename = secure_filename(structure_file.filename)
                file_path = os.path.join('app/static/structures', filename)
                structure_file.save(file_path)
                material.structure_file = filename

            # 更新所有字段
            material.name = request.form.get('name')
            material.status = request.form.get('status')
            material.total_energy = float(request.form.get('total_energy'))
            material.formation_energy = float(request.form.get('formation_energy'))
            material.fermi_level = safe_float(request.form.get('fermi_level'))
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

            material.validate()  # 执行数据验证
            
            db.session.commit()
            flash('Material updated.', 'success')
            return redirect(url_for('views.detail', material_id=material.id))
        
        except ValueError as e:
            flash(f'Invalid data: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material.id))
        except Exception:
            db.session.rollback()
            flash('Database error', 'error')
            return redirect(url_for('views.edit', material_id=material.id))
    
    return render_template('edit.html', material=material)  # GET请求返回编辑表单

# 材料详情页
@bp.route('/material/<int:material_id>')
def detail(material_id):
    material = Material.query.get_or_404(material_id)
    structure_file = f'structures/{material.structure_file}'
    return render_template('detail.html', 
                          material=material,
                          structure_file=structure_file)

# 材料删除路由（仅POST请求）
@bp.route('/material/delete/<int:material_id>', methods=['POST'])
@login_required
def delete(material_id):
    material = Material.query.get_or_404(material_id)
    db.session.delete(material)  # 删除记录
    db.session.commit()
    flash('Material deleted.', 'success')
    return redirect(url_for('views.index'))  # 重定向到首页

# 用户登录路由
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:  # 空值检查
            flash('Invalid input.', 'error')
            return redirect(url_for('views.login'))
        
        user = User.query.filter_by(username=username).first()  # 根据用户名精确查询
        if user and user.validate_password(password):
            login_user(user)  # Flask-Login登录方法
            flash('Login success.', 'success')
            return redirect(url_for('views.index'))
        
        flash('Invalid username or password.', 'error')
        return redirect(url_for('views.login'))
    return render_template('login.html')  # GET请求返回登录表单

# 用户退出路由
@bp.route('/logout')
@login_required
def logout():
    logout_user()  # Flask-Login退出方法
    flash('Goodbye.', 'info')
    return redirect(url_for('views.index'))

# 用户设置路由
@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']
        if not name or len(name) > 20:  # 输入验证
            flash('Invalid input.', 'error')
            return redirect(url_for('views.settings'))
        
        current_user.name = name  # 更新当前用户信息
        db.session.commit()
        flash('Settings updated.', 'success')
        return redirect(url_for('views.index'))
    return render_template('settings.html')  # GET请求返回设置表单