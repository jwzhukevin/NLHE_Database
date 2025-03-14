# view.py:
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import and_, or_
from .models import User, Material
from . import db

bp = Blueprint('views', __name__)

@bp.app_template_filter('any')
def any_filter(d):
    """检查字典是否有非空值的过滤器"""
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """从字典中移除指定键的模板过滤器"""
    return {k: v for k, v in d.items() if k != exclude_key}

@bp.route('/')
def index():
    # 基础查询
    query = Material.query
    
    # 获取搜索参数
    search_params = {
        'q': request.args.get('q', '').strip(),
        'status': request.args.get('status', '').strip(),
        'metal_type': request.args.get('metal_type', '').strip(),
        'formation_energy_min': request.args.get('formation_energy_min', '').strip(),
        'formation_energy_max': request.args.get('formation_energy_max', '').strip(),
        'fermi_level_min': request.args.get('fermi_level_min', '').strip(),
        'fermi_level_max': request.args.get('fermi_level_max', '').strip(),
    }
    
    # 构建过滤条件
    filters = []
    
    # 文本搜索
    if search_params['q']:
        filters.append(or_(
            Material.name.ilike(f'%{search_params["q"]}%'),
            Material.vbm_coordi.ilike(f'%{search_params["q"]}%'),
            Material.cbm_coordi.ilike(f'%{search_params["q"]}%')
        ))
    
    # 精确匹配
    if search_params['status']:
        filters.append(Material.status == search_params['status'])
    if search_params['metal_type']:
        filters.append(Material.metal_type == search_params['metal_type'])
    
    # 范围搜索
    if search_params['formation_energy_min']:
        try:
            filters.append(Material.formation_energy >= float(search_params['formation_energy_min']))
        except ValueError:
            pass
    if search_params['formation_energy_max']:
        try:
            filters.append(Material.formation_energy <= float(search_params['formation_energy_max']))
        except ValueError:
            pass
    
    if search_params['fermi_level_min']:
        try:
            filters.append(Material.fermi_level >= float(search_params['fermi_level_min']))
        except ValueError:
            pass
    if search_params['fermi_level_max']:
        try:
            filters.append(Material.fermi_level <= float(search_params['fermi_level_max']))
        except ValueError:
            pass   
    # 应用过滤条件
    if filters:
        query = query.filter(and_(*filters))
    
    # 分页设置
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.order_by(Material.name.asc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('index.html',
                         materials=pagination.items,
                         pagination=pagination,
                         search_params=search_params)




# 修改 add 路由
@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        try:
            # 获取所有表单字段
            material_data = {
                'name': request.form.get('name'),
                'status': request.form.get('status'),
                'total_energy': float(request.form.get('total_energy')),
                'formation_energy': float(request.form.get('formation_energy')),
                'fermi_level': safe_float(request.form.get('fermi_level')),
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

            # 必填字段验证
            if not all([material_data['name'], material_data['status']]):
                flash('Name and Status are required!')
                return redirect(url_for('views.add'))

            # 创建对象
            material = Material(**material_data)
            material.validate()  # 执行数据验证
            
            db.session.add(material)
            db.session.commit()
            flash('Material added successfully.')
            return redirect(url_for('views.index'))

        except ValueError as e:
            flash(f'Invalid data: {str(e)}')
            return redirect(url_for('views.add'))
        except Exception as e:
            db.session.rollback()
            flash('Database error occurred')
            return redirect(url_for('views.add'))

    return render_template('add.html')

# 新增辅助函数
def safe_float(value):
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    try:
        return int(value) if value else None
    except ValueError:
        return None

# 修改 edit 路由
@bp.route('/material/edit/<int:material_id>', methods=['GET', 'POST'])
@login_required
def edit(material_id):
    material = Material.query.get_or_404(material_id)
    if request.method == 'POST':
        try:
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

            material.validate()
            
            db.session.commit()
            flash('Material updated.')
            return redirect(url_for('views.detail', material_id=material.id))
        
        except ValueError as e:
            flash(f'Invalid data: {str(e)}')
            return redirect(url_for('views.edit', material_id=material.id))
        except Exception:
            db.session.rollback()
            flash('Database error')
            return redirect(url_for('views.edit', material_id=material.id))
    
    return render_template('edit.html', material=material)

@bp.route('/material/<int:material_id>')
def detail(material_id):
    material = Material.query.get_or_404(material_id)
    return render_template('detail.html', material=material)


@bp.route('/material/delete/<int:material_id>', methods=['POST'])
@login_required
def delete(material_id):
    material = Material.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()
    flash('Material deleted.')
    return redirect(url_for('views.index'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Invalid input.')
            return redirect(url_for('views.login'))
        user = User.query.first()
        if user and username == user.username and user.validate_password(password):
            login_user(user)
            flash('Login success.')
            return redirect(url_for('views.index'))
        flash('Invalid username or password.')
        return redirect(url_for('views.login'))
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Goodbye.')
    return redirect(url_for('views.index'))

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']
        if not name or len(name) > 20:
            flash('Invalid input.')
            return redirect(url_for('views.settings'))
        current_user.name = name
        db.session.commit()
        flash('Settings updated.')
        return redirect(url_for('views.index'))
    return render_template('settings.html')