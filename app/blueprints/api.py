# -*- coding: utf-8 -*-
# app/api.py
"""
本模块提供所有后端API接口，主要分为两大功能：
1. 材料结构数据API：提供晶体结构数据的查询、转换（如原胞、超晶胞）及文件下载功能。
2. AI聊天API：提供与大语言模型交互的流式聊天接口。

所有接口均定义在 /api 蓝图下，并遵循RESTful原则。
"""

import json
import os

from flask import (Blueprint, Response, current_app, jsonify, request)
from flask_login import login_required
from pymatgen.io.cif import CifWriter

from ..models import Material
from ..services.structure_parser import (
    _process_structure, find_structure_file, generate_supercell, parse_cif_file
)

# ==============================================================================
# API 蓝图定义
# ==============================================================================

# 创建一个名为 'api' 的蓝图，所有在此定义的路由都会自动添加 /api 前缀
bp = Blueprint('api', __name__, url_prefix='/api')


# ==============================================================================
# 内部辅助函数 (Internal Helper Functions)
# ==============================================================================

def _find_structure_file_path(material_id, material_name=None):
    """根据材料ID和名称查找结构文件的绝对路径，封装重复逻辑。"""
    # 优先使用 material_id 查找
    file_relative_path = find_structure_file(material_id=material_id)
    
    # 如果找不到，且提供了 material_name，则尝试使用名称查找（兼容旧目录结构）
    if not file_relative_path and material_name:
        file_relative_path = find_structure_file(material_name=material_name)
        
    if not file_relative_path:
        return None

    # 构建并返回绝对路径
    file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
    return file_path if os.path.exists(file_path) else None

# ==============================================================================
# (一) 材料结构数据 API (Structure Data APIs)
# ==============================================================================

@bp.route('/database/functional_materials/structure/<int:material_id>', methods=['GET'])
def get_structure(material_id):
    """
    获取指定ID材料的基础结构数据。

    这是最核心的结构数据查询接口，返回包含原子、晶格等信息的JSON。
    """
    try:
        # 验证材料是否存在，若不存在则直接返回404
        Material.query.get_or_404(material_id)
        
        # 调用解析器获取结构数据
        structure_data = parse_cif_file(material_id=material_id)
        result = json.loads(structure_data)
        
        # 如果解析过程中出现错误（如文件损坏），则返回404
        if 'error' in result:
            return jsonify({
                "error": f"Could not find or parse structure data for material ID: {material_id}",
                "details": result['error']
            }), 404
        
        # 成功则返回JSON格式的结构数据
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        current_app.logger.error(f"[API get_structure] Error for ID {material_id}: {e}")
        return jsonify({"error": "An internal error occurred."}), 500


@bp.route('/database/functional_materials/structure', methods=['GET'])
def get_structure_by_params():
    """
    通过URL查询参数 `?material_id=<id>` 获取结构数据。
    
    这是详情页调用的主要结构数据接口。
    """
    try:
        material_id_str = request.args.get('material_id')
    
        # 验证 material_id 参数是否存在
        if not material_id_str:
            return jsonify({"error": "Query parameter 'material_id' is required."}), 400
    
        try:
            material_id = int(material_id_str)
            # 直接调用核心函数，复用逻辑
            return get_structure(material_id)
            
        except ValueError:
            return jsonify({"error": "Invalid material_id format. Must be an integer."}), 400
    
    except Exception as e:
        current_app.logger.error(f"[API get_structure_by_params] Error: {e}")
        return jsonify({"error": "An internal error occurred."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/conventional', methods=['GET'])
def get_conventional_cell(material_id):
    """
    获取指定材料的“传统晶胞”(conventional cell)结构数据。
    """
    try:
        material = Material.query.get_or_404(material_id)
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 使用pymatgen加载结构并转换为传统晶胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='conventional')
        structure_data['id'] = material_id
        
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"[API get_conventional_cell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to process conventional cell."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/primitive', methods=['GET'])
def get_primitive_cell(material_id):
    """
    获取指定材料的“原始晶胞”(primitive cell)结构数据。
    """
    try:
        material = Material.query.get_or_404(material_id)
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404

        # 使用pymatgen加载结构并转换为原始晶胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='primitive')
        structure_data['id'] = material_id
        
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"[API get_primitive_cell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to process primitive cell."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/supercell', methods=['GET'])
def get_supercell(material_id):
    """
    根据请求参数动态生成并返回“超晶胞”(supercell)结构。
    
    查询参数:
        a, b, c (int): 沿三个晶轴方向的扩展倍数 (1-5)。
        cellType (str): 'primitive' 或 'conventional'，指定在哪种晶胞基础上扩展。
    """
    try:
        material = Material.query.get_or_404(material_id)
        
        # --- 参数获取与验证 --- #
        a = int(request.args.get('a', 1))
        b = int(request.args.get('b', 1))
        c = int(request.args.get('c', 1))
        cell_type = request.args.get('cellType', 'primitive')
        
        # 验证扩展倍数是否在合理范围内
        if not (1 <= a <= 5 and 1 <= b <= 5 and 1 <= c <= 5):
            return jsonify({"error": "Invalid supercell dimensions. Each must be between 1 and 5."}), 400
        
        # 验证基础晶胞类型是否合法
        if cell_type not in ['primitive', 'conventional']:
            return jsonify({"error": "Invalid cell type. Must be 'primitive' or 'conventional'."}), 400
        
        # --- 核心逻辑 --- #
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
            
        # 调用生成超晶胞的函数
        result = generate_supercell(file_path, a=a, b=b, c=c, cell_type=cell_type)
        result_data = json.loads(result)
        
        if 'error' in result_data:
            return jsonify({"error": result_data['error']}), 400
        
        return result, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        current_app.logger.error(f"[API get_supercell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to generate supercell."}), 500

# ==============================================================================
# (二) 结构文件下载 API (File Download API)
# ==============================================================================

@bp.route('/database/functional_materials/structure/<int:material_id>/cif', methods=['GET'])
def download_cif(material_id):
    """
    提供CIF格式的结构文件下载功能，支持动态生成超晶胞后下载。

    查询参数 (可选):
        a, b, c (int): 用于生成超晶胞的扩展倍数。
        cellType (str): 'primitive' 或 'conventional'。
    """
    try:
        material = Material.query.get_or_404(material_id)
        
        # --- 参数解析 --- #
        a = request.args.get('a')
        b = request.args.get('b')
        c = request.args.get('c')
        cell_type = request.args.get('cellType')
        is_supercell = all([a, b, c])

        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # --- CIF 内容生成 --- #
        if is_supercell:
            # 动态生成超晶胞的CIF内容
            from pymatgen.core import Structure
            structure = Structure.from_file(file_path)
            
            a_val, b_val, c_val = int(a), int(b), int(c)
            if not (1 <= a_val <= 5 and 1 <= b_val <= 5 and 1 <= c_val <= 5):
                return jsonify({"error": "Invalid supercell dimensions."}), 400
            
            if cell_type == 'conventional':
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure)
                structure = analyzer.get_conventional_standard_structure()
            
            structure.make_supercell([a_val, b_val, c_val])
            cif_string = str(CifWriter(structure))
            filename = f"{material.name}_supercell_{a_val}x{b_val}x{c_val}.cif"
        else:
            # 直接读取原始CIF文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                cif_string = f.read()
            filename = f"{material.name}.cif"
        
        # --- 构造文件下载响应 --- #
        return Response(
            cif_string,
            mimetype="chemical/x-cif",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    
    except Exception as e:
        current_app.logger.error(f"[API download_cif] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to generate CIF file for download."}), 500


# ==============================================================================
# 注意：AI 聊天 API（/api/chat/stream）已拆分到 chat_api.py 蓝图中，
# 本模块仅保留材料结构数据相关的 API 接口。
# ==============================================================================
