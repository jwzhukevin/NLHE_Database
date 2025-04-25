# view.py:
# 视图函数模块，处理所有用户界面相关的路由和请求
# 包含首页、材料详情页、添加/编辑材料、用户认证等路由

# 导入所需模块
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app  # Flask 核心模块
from flask_login import login_user, logout_user, login_required, current_user  # 用户认证模块
from sqlalchemy import and_, or_  # 数据库查询条件构造器
from .models import User, Material, BlockedIP  # 自定义数据模型
from . import db  # 数据库实例
import datetime  # 处理日期和时间
import functools  # 用于装饰器
from .material_importer import extract_chemical_formula_from_cif  # 导入材料数据模块
import os

# 创建名为'views'的蓝图，用于模块化路由管理
bp = Blueprint('views', __name__)

# 注册模板过滤器
@bp.app_template_filter('any')
def any_filter(d):
    """检查字典是否存在至少一个非空值（用于前端条件判断）
    
    参数:
        d: 待检查的字典
    
    返回: 
        布尔值，表示字典是否有有效数据，用于判断是否显示重置搜索按钮等
    """
    return any(v for v in d.values() if v)

@bp.app_template_filter('remove_key')
def remove_key_filter(d, exclude_key):
    """生成排除指定键的新字典（用于清理搜索参数）
    
    参数:
        d: 原始字典
        exclude_key: 需要排除的键
    
    返回: 
        处理后的新字典，用于构建去除某个过滤条件的URL
    """
    return {k: v for k, v in d.items() if k != exclude_key}

# 首页路由（支持复杂搜索和分页）
@bp.route('/')
def landing():
    """网站介绍页面 - 展示网站特性和功能概览"""
    return render_template('landing.html')

@bp.route('/database')
def index():
    """材料数据库页面 - 显示材料列表，支持搜索、筛选和分页
    
    支持的GET参数:
        q: 搜索关键词
        status: 材料状态筛选
        metal_type: 金属类型筛选
        formation_energy_min/max: 形成能范围筛选
        fermi_level_min/max: 费米能级范围筛选
        page: 当前页码
    """
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
            Material.name.ilike(f'%{search_params["q"]}%'),  # 名称模糊匹配（不区分大小写）
            Material.vbm_coordi.ilike(f'%{search_params["q"]}%'),  # VBM坐标匹配
            Material.cbm_coordi.ilike(f'%{search_params["q"]}%')  # CBM坐标匹配
        ))
    
    # 精确匹配条件
    if search_params['status']:
        filters.append(Material.status == search_params['status'])  # 状态精确匹配
    if search_params['metal_type']:
        filters.append(Material.metal_type == search_params['metal_type'])  # 金属类型精确匹配
    
    # 数值范围过滤（包含异常处理，确保输入的是有效数值）
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
    
    # 应用所有过滤条件（使用AND逻辑组合，即所有条件都必须满足）
    if filters:
        query = query.filter(and_(*filters))
    
    # 分页配置（每页10条记录）
    page = request.args.get('page', 1, type=int)  # 获取当前页码，默认第1页
    per_page = 10  # 每页条目数
    pagination = query.order_by(Material.name.asc()).paginate(  # 按名称升序排序
        page=page, 
        per_page=per_page, 
        error_out=False  # 禁用无效页码错误，超出范围会返回空列表
    )
    
    # 渲染模板并传递分页对象和搜索参数
    return render_template('index.html',
                         materials=pagination.items,  # 当前页数据
                         pagination=pagination,  # 分页对象（包含页码信息）
                         search_params=search_params)  # 搜索参数（用于表单回显）

# 材料添加路由（需登录）
@bp.route('/add', methods=['GET', 'POST'])
@login_required  # 登录保护装饰器，确保只有登录用户可以添加材料
def add():
    """
    添加新材料记录的页面和处理逻辑
    
    GET请求: 显示添加材料表单
    POST请求: 处理表单提交，添加新材料到数据库
    """
    if request.method == 'POST':
        try:
            # 获取并处理上传的文件
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')
            
            # 验证CIF文件是否有效
            if not structure_file or not structure_file.filename.endswith('.cif'):
                flash('请上传有效的CIF文件！', 'error')
                return redirect(url_for('views.add'))
            
            # 生成安全的文件名并保存结构文件
            from werkzeug.utils import secure_filename
            import os
            from flask import current_app
            
            # 先保存结构文件到临时位置用于提取化学式
            structure_filename = secure_filename(structure_file.filename)
            temp_structure_path = os.path.join(current_app.root_path, 'static/temp', structure_filename)
            os.makedirs(os.path.dirname(temp_structure_path), exist_ok=True)
            structure_file.save(temp_structure_path)
            
            # 从CIF文件中提取化学式
            chemical_name = extract_chemical_formula_from_cif(temp_structure_path)
            
            # 验证是否成功提取到材料名称
            if not chemical_name:
                flash('无法从CIF文件中提取材料名称，请检查文件格式', 'error')
                return redirect(url_for('views.add'))
            
            # 验证材料名称是否已存在
            if Material.query.filter_by(name=chemical_name).first():
                flash(f'材料名称 "{chemical_name}" 已存在，请使用不同的CIF文件', 'error')
                return redirect(url_for('views.add'))
            
            # 创建材料对象并添加到数据库，以获取ID
            material_data = {
                'name': chemical_name,  # 使用CIF提取的化学式
                'status': request.form.get('status'),  # 状态
                'structure_file': structure_filename,  # 结构文件路径
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

            # 创建Material对象并验证数据
            material = Material(**material_data)
            material.validate()  # 调用模型自定义验证方法，检查数据完整性
            
            # 先添加到数据库以获取ID
            db.session.add(material)
            db.session.flush()  # 获取ID但不提交事务

            # 格式化ID (IMR-00000XXX)
            formatted_id = f"IMR-{material.id:08d}"
            
            # 创建材料专用文件夹结构
            material_dir = os.path.join(current_app.root_path, 'static/materials', formatted_id)
            structure_dir = os.path.join(material_dir, 'structure')
            band_dir = os.path.join(material_dir, 'band')
            bcd_dir = os.path.join(material_dir, 'bcd')
            
            # 创建所有目录
            os.makedirs(material_dir, exist_ok=True)
            os.makedirs(structure_dir, exist_ok=True)
            os.makedirs(band_dir, exist_ok=True)
            os.makedirs(bcd_dir, exist_ok=True)
            
            # 保存CIF文件到structure文件夹
            structure_path = os.path.join(structure_dir, structure_filename)
            os.rename(temp_structure_path, structure_path)
            
            # 处理JSON属性文件
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(material_dir, properties_json_filename)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename
            else:
                # 创建包含必要字段的JSON文件，而不是空的JSON对象
                import json
                json_data = {
                  "name": chemical_name,
                  "status": request.form.get('status') or "pending",
                  "structure_file": structure_filename,
                  "total_energy": material.total_energy,
                  "formation_energy": material.formation_energy,
                  "fermi_level": material.fermi_level,
                  "vacuum_level": material.vacuum_level,
                  "workfunction": material.workfunction,
                  "metal_type": material.metal_type or "No Data",
                  "gap": material.gap,
                  "vbm_energy": material.vbm_energy,
                  "cbm_energy": material.cbm_energy,
                  "vbm_coordi": material.vbm_coordi or "No Data",
                  "cbm_coordi": material.cbm_coordi or "No Data",
                  "vbm_index": material.vbm_index,
                  "cbm_index": material.cbm_index
                }
                json_file_path = os.path.join(material_dir, 'material.json')
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                material.properties_json = 'material.json'
            
            # 处理能带dat文件
            if band_file and band_file.filename.endswith('.dat'):
                band_filename = secure_filename(band_file.filename)
                band_path = os.path.join(band_dir, band_filename)
                band_file.save(band_path)
            
            # 处理SC结构dat文件
            if sc_structure_file and sc_structure_file.filename.endswith('.dat'):
                sc_filename = secure_filename(sc_structure_file.filename)
                sc_path = os.path.join(bcd_dir, sc_filename)
                sc_structure_file.save(sc_path)
            
            # 同时保存到常规文件夹以保持向后兼容
            if band_file and band_file.filename:
                band_path = os.path.join(current_app.root_path, 'static/band', secure_filename(band_file.filename))
                os.makedirs(os.path.dirname(band_path), exist_ok=True)
                # 创建副本而不是复制，防止二次存储消耗空间
                try:
                    os.symlink(os.path.join(band_dir, secure_filename(band_file.filename)), band_path)
                except:
                    import shutil
                    shutil.copy2(os.path.join(band_dir, secure_filename(band_file.filename)), band_path)
            
            # 提交数据库事务
            db.session.commit()
            
            flash(f'材料添加成功。数据已同步到 {formatted_id} 文件夹。', 'success')
            return redirect(url_for('views.index'))  # 重定向到首页

        except ValueError as e:  # 处理数据类型错误
            flash(f'数据无效: {str(e)}', 'error')  # 显示详细错误消息
            return redirect(url_for('views.add'))
        except Exception as e:  # 处理其他数据库错误
            db.session.rollback()  # 回滚事务，放弃所有更改
            flash(f'发生错误: {str(e)}', 'error')  # 显示一般错误消息
            return redirect(url_for('views.add'))

    return render_template('add.html')  # GET请求返回表单页

# 安全数值转换辅助函数
def safe_float(value):
    """将字符串安全转换为浮点数（允许空值）
    
    参数:
        value: 输入字符串
    
    返回: 
        float或None，如果转换失败或输入为空则返回None
    """
    try:
        return float(value) if value else None
    except ValueError:
        return None

def safe_int(value):
    """将字符串安全转换为整数（允许空值）
    
    参数:
        value: 输入字符串
    
    返回: 
        int或None，如果转换失败或输入为空则返回None
    """
    try:
        return int(value) if value else None
    except ValueError:
        return None

# 材料编辑路由
@bp.route('/materials/edit/IMR-<string:material_id>', methods=['GET', 'POST'])
@login_required  # 登录保护装饰器
def edit(material_id):
    """
    编辑现有材料记录
    
    GET请求: 显示编辑表单，预填充当前数据
    POST请求: 处理表单提交，更新数据库记录
    
    参数:
        material_id: 要编辑的材料ID（格式为数字部分，不含IMR-前缀）
    """
    # 从字符串ID提取数字部分
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
        
    # 查询要编辑的材料记录
    material = Material.query.get_or_404(numeric_id)  # 获取材料或返回404
    
    if request.method == 'POST':
        try:
            # 处理结构文件更新
            structure_file = request.files.get('structure_file')
            band_file = request.files.get('band_file')
            properties_json = request.files.get('properties_json')
            sc_structure_file = request.files.get('sc_structure_file')
            
            # 如果上传了新的结构文件
            if structure_file and structure_file.filename:
                if not structure_file.filename.endswith('.cif'):
                    flash('请上传有效的CIF文件！', 'error')
                    return redirect(url_for('views.edit', material_id=material_id))
                
                # 保存新结构文件
                from werkzeug.utils import secure_filename
                import os
                structure_filename = secure_filename(structure_file.filename)
                structure_path = os.path.join(current_app.root_path, 'static/structures', structure_filename)
                os.makedirs(os.path.dirname(structure_path), exist_ok=True)
                structure_file.save(structure_path)
                material.structure_file = structure_filename
                
                # 从CIF文件中提取化学式
                chemical_name = extract_chemical_formula_from_cif(structure_path)
                if chemical_name:
                    # 检查新名称是否与其他材料重名（排除当前材料）
                    existing_material = Material.query.filter(
                        Material.name == chemical_name,
                        Material.id != numeric_id
                    ).first()
                    
                    if existing_material:
                        flash(f'材料名称 "{chemical_name}" 已存在，请使用不同的CIF文件', 'error')
                        return redirect(url_for('views.edit', material_id=material_id))
                    
                    # 更新材料名称
                    material.name = chemical_name
                    flash(f'材料名称已从CIF文件更新为: {chemical_name}', 'info')
            
            # 处理属性JSON文件
            if properties_json and properties_json.filename:
                properties_json_filename = secure_filename(properties_json.filename)
                properties_json_path = os.path.join(current_app.root_path, 'static/properties', properties_json_filename)
                os.makedirs(os.path.dirname(properties_json_path), exist_ok=True)
                properties_json.save(properties_json_path)
                material.properties_json = properties_json_filename
            
            # 处理SC结构文件
            if sc_structure_file and sc_structure_file.filename:
                sc_structure_filename = secure_filename(sc_structure_file.filename)
                sc_structure_path = os.path.join(current_app.root_path, 'static/sc_structures', sc_structure_filename)
                os.makedirs(os.path.dirname(sc_structure_path), exist_ok=True)
                sc_structure_file.save(sc_structure_path)
                material.sc_structure_file = sc_structure_filename
            
            # 处理能带文件更新
            if band_file and band_file.filename:
                if band_file.filename.endswith(('.json', '.dat')):
                    band_filename = secure_filename(band_file.filename)
                    band_path = os.path.join(current_app.root_path, 'static/band', band_filename)
                    os.makedirs(os.path.dirname(band_path), exist_ok=True)
                    band_file.save(band_path)
            
            # 更新其他材料属性（仅当没有上传新的CIF文件时才使用表单的名称）
            if not structure_file or not structure_file.filename or not material.name:
                material.name = request.form.get('name')
            
            # 验证名称不为空
            if not material.name:
                flash('材料名称不能为空！', 'error')
                return redirect(url_for('views.edit', material_id=material_id))
            
            # 更新其他材料属性
            material.status = request.form.get('status')
            material.total_energy = safe_float(request.form.get('total_energy'))
            material.formation_energy = safe_float(request.form.get('formation_energy'))
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
            
            # 保存更改
            db.session.commit()
            flash('材料更新成功。', 'success')
            return redirect(url_for('views.detail', material_id=material_id))
            
        except ValueError as e:
            flash(f'数据无效: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
        except Exception as e:
            db.session.rollback()
            flash(f'发生错误: {str(e)}', 'error')
            return redirect(url_for('views.edit', material_id=material_id))
    
    # GET请求: 显示编辑表单
    return render_template('edit.html', material=material)

# 材料详情页
@bp.route('/materials/IMR-<string:material_id>')
def detail(material_id):
    """
    显示材料详细信息的页面
    
    参数:
        material_id: 要显示的材料ID（格式为数字部分，不含IMR-前缀）
    
    返回:
        渲染的详情页模板，包含材料数据和结构文件路径
    """
    # 从字符串ID提取数字部分
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
    
    # 从数据库获取材料，不存在则返回404
    material = Material.query.get_or_404(numeric_id)
    
    # 如果需要，这里可以添加从JSON文件更新材料数据的逻辑
    # 例如：如果材料状态为"需更新"，则自动从JSON刷新数据
    
    # 构建结构文件路径 - 首先尝试新的目录结构
    # 格式化ID (IMR-00000XXX)
    formatted_id = f"IMR-{numeric_id:08d}"
    structure_file = None
    
    # 检查新目录结构中是否存在结构文件
    new_structure_path = f'materials/{formatted_id}/structure/structure.cif'
    if os.path.exists(os.path.join(current_app.root_path, 'static', new_structure_path)):
        structure_file = new_structure_path
    # 如果新目录结构中没有找到，尝试旧的目录结构
    elif material.structure_file:
        old_structure_path = f'structures/{material.structure_file}'
        if os.path.exists(os.path.join(current_app.root_path, 'static', old_structure_path)):
            structure_file = old_structure_path
    
    # 渲染详情页模板
    return render_template('detail.html', 
                          material=material,
                          structure_file=structure_file)

# 材料删除路由（仅POST请求）
@bp.route('/materials/delete/IMR-<string:material_id>', methods=['POST'])
@login_required  # 登录保护装饰器
def delete(material_id):
    """
    删除材料记录
    
    参数:
        material_id: 要删除的材料ID（格式为数字部分，不含IMR-前缀）
    
    注意:
        只接受POST请求，防止CSRF攻击
    """
    # 从字符串ID提取数字部分
    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('404.html'), 404
        
    material = Material.query.get_or_404(numeric_id)  # 获取材料或返回404错误
    
    # 删除相关文件
    import os
    import shutil
    from flask import current_app
    
    # 格式化ID (IMR-00000XXX)
    formatted_id = f"IMR-{numeric_id:08d}"
    
    # 删除材料专用文件夹及其所有内容
    material_dir = os.path.join(current_app.root_path, 'static/materials', formatted_id)
    if os.path.exists(material_dir):
        shutil.rmtree(material_dir)
    
    # 保持原有的文件删除逻辑以保证向后兼容
    # 删除结构文件
    if material.structure_file:
        structure_path = os.path.join(current_app.root_path, 'static/structures', material.structure_file)
        if os.path.exists(structure_path):
            os.remove(structure_path)
    
    # 删除能带文件
    band_path = os.path.join(current_app.root_path, 'static/band', f'{material.id}.dat')
    if os.path.exists(band_path):
        os.remove(band_path)
    
    # 删除属性JSON文件
    if material.properties_json:
        json_path = os.path.join(current_app.root_path, 'static/properties', material.properties_json)
        if os.path.exists(json_path):
            os.remove(json_path)
    
    # 删除SC结构文件
    if material.sc_structure_file:
        sc_path = os.path.join(current_app.root_path, 'static/sc_structures', material.sc_structure_file)
        if os.path.exists(sc_path):
            os.remove(sc_path)
    
    db.session.delete(material)  # 删除记录
    db.session.commit()  # 提交事务
    flash(f'材料"{material.name}"及其所有相关文件已成功删除。', 'success')  # 显示成功消息
    return redirect(url_for('views.index'))  # 重定向到首页

# 获取客户端IP的辅助函数
def get_client_ip():
    """获取当前请求的客户端IP地址
    
    返回: 
        字符串，表示客户端的IP地址
    """
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr

# IP封锁检查装饰器
def check_ip_blocked(view_func):
    """检查IP是否被封锁的装饰器
    
    如果IP被封锁，重定向到首页并显示警告信息
    """
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        client_ip = get_client_ip()
        
        # 检查IP是否在封锁列表中
        blocked = BlockedIP.query.filter_by(ip_address=client_ip).first()
        if blocked:
            flash('Access denied. Your IP has been blocked due to multiple failed login attempts.', 'error')
            return redirect(url_for('views.landing'))
        
        return view_func(*args, **kwargs)
    
    return wrapped_view

# 用户登录路由
@bp.route('/login', methods=['GET', 'POST'])
@check_ip_blocked  # 应用IP封锁检查装饰器
def login():
    """
    用户登录页面和处理逻辑
    
    GET请求: 显示登录表单
    POST请求: 验证凭据并执行登录，跟踪失败尝试次数
    """
    if request.method == 'POST':
        username = request.form['username']  # 获取表单中的用户名
        password = request.form['password']  # 获取表单中的密码
        client_ip = get_client_ip()  # 获取客户端IP
        
        # 使用会话存储登录尝试次数
        if 'login_attempts' not in session:
            session['login_attempts'] = 0
        
        if not username or not password:  # 空值检查
            flash('Invalid input.', 'error')  # 显示错误消息
            return redirect(url_for('views.login'))  # 重定向回登录页
        
        user = User.query.filter_by(username=username).first()  # 根据用户名精确查询
        if user and user.validate_password(password):  # 验证密码
            # 登录成功，重置尝试次数
            session.pop('login_attempts', None)
            login_user(user)  # Flask-Login登录方法，管理用户会话
            flash('Login success.', 'success')  # 显示成功消息
            return redirect(url_for('views.index'))  # 重定向到首页
        
        # 登录失败，增加尝试次数
        session['login_attempts'] += 1
        current_attempts = session['login_attempts']
        
        # 检查是否达到最大尝试次数
        if current_attempts >= 10:
            # 创建新的IP封锁记录
            blocked_ip = BlockedIP(
                ip_address=client_ip,
                blocked_at=datetime.datetime.now()
            )
            db.session.add(blocked_ip)
            db.session.commit()
            
            # 清除会话中的尝试计数
            session.pop('login_attempts', None)
            
            flash('Your IP has been blocked due to too many failed login attempts.', 'error')
            return redirect(url_for('views.landing'))
        
        # 显示错误消息和剩余尝试次数
        remaining_attempts = 10 - current_attempts
        flash(f'Invalid username or password. You have {remaining_attempts} attempts remaining before being blocked.', 'error')
        return redirect(url_for('views.login'))
        
    return render_template('login.html')  # GET请求返回登录表单

# 用户退出路由
@bp.route('/logout')
@login_required  # 登录保护装饰器，确保只有登录用户可以退出
def logout():
    """
    处理用户退出登录
    
    执行登出操作并重定向到首页
    """
    logout_user()  # Flask-Login退出方法，清除用户会话
    flash('Goodbye.', 'info')  # 显示信息消息
    return redirect(url_for('views.index'))  # 重定向到首页

# 用户设置路由
@bp.route('/settings', methods=['GET', 'POST'])
@login_required  # 登录保护装饰器
def settings():
    """
    用户设置页面和处理逻辑
    
    GET请求: 显示设置表单
    POST请求: 更新用户设置
    """
    if request.method == 'POST':
        name = request.form['name']  # 获取表单中的名称
        if not name or len(name) > 20:  # 输入验证：不能为空且长度限制
            flash('Invalid input.', 'error')  # 显示错误消息
            return redirect(url_for('views.settings'))  # 重定向回设置页
        
        current_user.name = name  # 更新当前用户信息（使用Flask-Login的current_user）
        db.session.commit()  # 提交更改到数据库
        flash('Settings updated.', 'success')  # 显示成功消息
        return redirect(url_for('views.index'))  # 重定向到首页
    return render_template('settings.html')  # GET请求返回设置表单