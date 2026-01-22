# -*- coding: utf-8 -*-
"""
功能材料数据库蓝图
路由：材料列表页、材料详情页、MP编号跳转
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required
from flask_babel import _
from sqlalchemy import and_, or_
import os
import re
import glob
import math

functional_materials_bp = Blueprint('functional_materials', __name__, url_prefix='/database/functional_materials')


# ==================== 辅助函数 ====================

def get_material_dir(material_id):
    """根据材料ID返回材料目录路径"""
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    return new_dir


def safe_float(value):
    """安全地将字符串转换为浮点数"""
    try:
        return float(value) if value else None
    except ValueError:
        return None


def safe_int(value):
    """安全地将字符串转换为整数"""
    try:
        return int(value) if value else None
    except ValueError:
        return None


# ==================== 路由 ====================

@functional_materials_bp.route('')
def index():
    """
    材料数据库页：展示材料列表，支持搜索、过滤与分页。
    """
    from ....models import Material
    from .... import db
    from ....services import QueryOptimizer, performance_monitor, cached_search
    from ....services import chemical_parser
    from ....security import sanitize_input

    try:
        search_params = {
            'q': request.args.get('q', '').strip(),
            'materials_type': request.args.get('materials_type', '').strip(),
            'elements': request.args.get('elements', '').strip(),
            'fermi_level_min': request.args.get('fermi_level_min', '').strip(),
            'fermi_level_max': request.args.get('fermi_level_max', '').strip(),
            'max_sc_min': request.args.get('max_sc_min', '').strip(),
            'max_sc_max': request.args.get('max_sc_max', '').strip(),
            'band_gap_min': request.args.get('band_gap_min', '').strip(),
            'band_gap_max': request.args.get('band_gap_max', '').strip(),
            'mp_id': request.args.get('mp_id', '').strip(),
            'space_group': request.args.get('space_group', '').strip(),
            'prop_sc': request.args.get('prop_sc'),
            'prop_bcd': request.args.get('prop_bcd'),
            'prop_dw': request.args.get('prop_dw'),
        }

        # MP 编号直达查询
        mp_query = search_params['q']
        if mp_query and re.match(r'^mp-\w+$', mp_query):
            query = db.session.query(Material).filter(Material.mp_id == mp_query)
            page = request.args.get('page', 1, type=int)
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
            total_results = query.count()
            total_pages = math.ceil(total_results / per_page) if per_page > 0 else 0
            if total_pages > 0 and page > total_pages:
                page = 1

            pagination = query.order_by(Material.name.asc()).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            return render_template('database/functional/functional_materials.html',
                                 materials=pagination.items,
                                 pagination=pagination,
                                 search_params={**search_params})

        # 使用优化的查询器
        optimization_result = QueryOptimizer.optimize_material_search(search_params)
        query = optimization_result['query']

        current_app.logger.info(
            f"Search optimization: {optimization_result['filters_applied']} filters, "
            f"{optimization_result['total_count']} results, "
            f"{optimization_result['execution_time']:.3f}s"
        )

        additional_filters = []

        # 元素搜索
        if search_params['elements']:
            element_list = [elem.strip() for elem in search_params['elements'].split(',') if elem.strip()]
            if element_list:
                element_filters = []
                for elem in element_list:
                    like_pat = f"%{elem}%"
                    element_filters.append(Material.name.ilike(like_pat))
                if element_filters:
                    additional_filters.append(or_(*element_filters))

        # MP-ID 过滤
        if search_params['mp_id']:
            mp_val = search_params['mp_id']
            try:
                mp_val = sanitize_input(mp_val)
            except Exception:
                pass
            if re.match(r'^mp-\w+$', mp_val):
                additional_filters.append(Material.mp_id == mp_val)
            else:
                additional_filters.append(Material.mp_id.ilike(f'%{mp_val}%'))

        # 空间群过滤
        if search_params['space_group']:
            sg_val = search_params['space_group']
            try:
                sg_val = sanitize_input(sg_val)
            except Exception:
                pass
            if re.fullmatch(r'\d+', sg_val):
                try:
                    sg_num = int(sg_val)
                    additional_filters.append(Material.sg_num == sg_num)
                except ValueError:
                    pass
            else:
                additional_filters.append(Material.sg_name.ilike(f'%{sg_val}%'))

        # 特殊性质筛选
        if search_params.get('prop_sc'):
            additional_filters.append(Material.has_sc == True)
        if search_params.get('prop_bcd'):
            additional_filters.append(Material.has_bcd == True)
        if search_params.get('prop_dw'):
            additional_filters.append(Material.has_dw == True)

        if additional_filters:
            query = query.filter(and_(*additional_filters))

        total_results = optimization_result.get('total_count', None)
        if total_results is None:
            total_results = query.count()
        current_app.logger.info(f"Search query returned {total_results} results with search params: {search_params}")

        page = request.args.get('page', 1, type=int)
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
        total_pages = math.ceil(total_results / per_page) if per_page > 0 else 0
        if total_pages > 0 and page > total_pages:
            page = 1

        pagination = query.order_by(Material.name.asc()).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        return render_template('database/functional/functional_materials.html',
                             materials=pagination.items,
                             pagination=pagination,
                             search_params={**search_params})

    except Exception as e:
        current_app.logger.error(f"Database query error: {str(e)}")
        from flask_sqlalchemy import Pagination
        empty_pagination = Pagination(query=None, page=1, per_page=10, total=0, items=[])
        return render_template('database/functional/functional_materials.html',
                             materials=[],
                             pagination=empty_pagination,
                             search_params={},
                             error_message="Database not initialized, please contact administrator")


@functional_materials_bp.route('/IMR-<string:material_id>')
def detail(material_id):
    """材料详情页"""
    from ....models import Material
    from .... import db
    from ....services import band_analyzer

    try:
        numeric_id = int(material_id)
    except ValueError:
        return render_template('errors/404.html'), 404
    
    material = Material.query.get_or_404(numeric_id)

    # 自动分析能带数据
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

    # band文件
    band_dat_files = glob.glob(os.path.join(band_dir, '*.dat')) if os.path.exists(band_dir) else []
    if len(band_dat_files) == 1:
        band_file = os.path.relpath(band_dat_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(band_dat_files) > 1:
        flash(_('Error: Multiple band .dat files found in band directory. Please keep only one!'), 'error')
        band_file = None
    else:
        band_file = None

    # SC文件
    sc_files = glob.glob(os.path.join(sc_dir, '*.dat')) if os.path.exists(sc_dir) else []
    if len(sc_files) == 1:
        sc_file = os.path.relpath(sc_files[0], os.path.join(current_app.root_path, 'static'))
    elif len(sc_files) > 1:
        flash(_('Error: Multiple SC files found in sc directory. Please keep only one!'), 'error')
        sc_file = None
    else:
        sc_file = None

    # BCD/DW 目录
    materials_base = os.path.join(current_app.root_path, 'static', 'materials')
    static_root = os.path.join(current_app.root_path, 'static')

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

    return render_template(
        'database/functional/functional_materials_detail.html',
        material=material,
        structure_file=structure_file,
        band_file=band_file,
        sc_file=sc_file,
        bcd_dir=bcd_dir,
        dw_dir=dw_dir,
        bcd_matrix_path=bcd_matrix_path,
        dw_matrix_path=dw_matrix_path
    )


@functional_materials_bp.route('/by-mp/<string:mp_id>')
def material_by_mp(mp_id):
    """通过 MP 编号跳转到 IMR 详情页"""
    from ....models import Material
    from .... import db

    try:
        material = db.session.query(Material).filter(Material.mp_id == mp_id).first()
        if not material:
            flash(_('Material with MP ID %(mp_id)s not found.', mp_id=mp_id), 'error')
            return render_template('errors/404.html'), 404
        return redirect(url_for('functional_materials.detail', material_id=material.id))
    except Exception as e:
        current_app.logger.error(f"material_by_mp error: {e}")
        return render_template('errors/500.html'), 500


# ==================== 已废弃的路由（只读模式）====================

@functional_materials_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """[已废弃] 新增功能已移除"""
    return render_template('errors/404.html'), 404


@functional_materials_bp.route('/edit/IMR-<string:material_id>', methods=['GET', 'POST'])
@login_required
def edit(material_id):
    """[已废弃] 编辑功能已移除"""
    return render_template('errors/404.html'), 404


@functional_materials_bp.route('/delete/IMR-<string:material_id>', methods=['POST'])
@login_required
def delete(material_id):
    """[已废弃] 删除功能已移除"""
    return render_template('errors/404.html'), 404
