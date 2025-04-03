# api.py
# 提供结构数据的API接口
# 本文件包含所有与晶体结构相关的API端点，处理结构数据的获取、上传和转换

import json
import os
from flask import Blueprint, jsonify, request, current_app
from .models import Material, db
from .structure_parser import parse_cif_file, save_structure_file, find_structure_file, generate_supercell, get_cif_data, generate_primitive_cell

# 创建API蓝图
# 定义前缀为/api的路由组
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/structure/<int:material_id>', methods=['GET'])
def get_structure(material_id):
    """
    获取指定材料的结构数据
    
    参数:
        material_id: 材料ID，用于在数据库中查找对应的材料记录
    
    返回:
        包含原子坐标、晶格参数等信息的JSON响应
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 解析CIF文件并获取结构数据
        # 首先尝试使用material.structure_file（如果存在）
        if hasattr(material, 'structure_file') and material.structure_file:
            structure_data = parse_cif_file(filename=material.structure_file)
        else:
            # 否则，使用材料ID或名称查找并解析CIF文件
            structure_data = parse_cif_file(material_id=material_id, material_name=material.name)
        
        # 检查是否有错误
        result = json.loads(structure_data)
        if 'error' in result:
            return jsonify(result), 404  # 返回错误信息和404状态码
        
        # 返回JSON响应，设置正确的内容类型
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        # 捕获所有异常并返回500错误
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/upload/<int:material_id>', methods=['POST'])
def upload_structure(material_id):
    """
    上传材料的CIF结构文件
    
    参数:
        material_id: 材料ID，用于关联上传的结构文件
    
    返回:
        上传结果的JSON响应，包含成功信息或错误信息
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        
        # 检查文件名是否为空
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # 检查文件扩展名是否为.cif
        if not file.filename.lower().endswith('.cif'):
            return jsonify({"error": "File must be a CIF file"}), 400
        
        # 读取文件内容
        file_content = file.read()
        
        # 保存文件到指定目录
        filename = save_structure_file(
            file_content, 
            file.filename, 
            material_id=material_id, 
            material_name=material.name
        )
        
        # 检查文件是否保存成功
        if not filename:
            return jsonify({"error": "Failed to save structure file"}), 500
        
        # 更新材料记录以关联新的结构文件
        if hasattr(material, 'structure_file'):
            material.structure_file = filename
            db.session.commit()  # 提交数据库更改
            current_app.logger.info(f"Updated structure file for material ID {material_id}: {filename}")
        
        # 返回成功响应
        return jsonify({
            "success": True,
            "message": "Structure file uploaded successfully",
            "filename": filename
        }), 200
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error uploading structure file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/supercell', methods=['GET'])
def get_supercell(material_id):
    """
    生成并返回扩展的超晶胞结构
    
    参数:
        material_id: 材料ID
        a, b, c: 沿a, b, c方向的扩展倍数（查询参数）
        cellType: 晶胞类型，可选 'primitive'或'conventional'（查询参数）
    
    返回:
        包含超晶胞结构数据的JSON响应
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 获取请求参数，并设置默认值
        a = int(request.args.get('a', 1))
        b = int(request.args.get('b', 1))
        c = int(request.args.get('c', 1))
        cell_type = request.args.get('cellType', 'primitive')
        
        # 参数验证：确保扩展倍数在有效范围内
        if a < 1 or b < 1 or c < 1 or a > 5 or b > 5 or c > 5:
            return jsonify({"error": "Invalid supercell dimensions. Must be between 1 and 5."}), 400
        
        # 参数验证：确保晶胞类型是有效值
        if cell_type not in ['primitive', 'conventional']:
            return jsonify({"error": "Invalid cell type. Must be 'primitive' or 'conventional'."}), 400
        
        # 解析原始CIF文件
        # 首先尝试使用material.structure_file（如果存在）
        if hasattr(material, 'structure_file') and material.structure_file:
            file_path = material.structure_file
        else:
            # 否则，使用材料ID或名称查找CIF文件
            file_path = find_structure_file(material_id=material_id, material_name=material.name)
        
        # 检查是否找到文件
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 生成超晶胞
        supercell_data = generate_supercell(
            file_path, 
            a=a, 
            b=b, 
            c=c,
            cell_type=cell_type
        )
        
        # 检查是否有错误
        result = json.loads(supercell_data)
        if 'error' in result:
            return jsonify(result), 500
        
        # 返回JSON响应，设置正确的内容类型
        return supercell_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error generating supercell: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/cif', methods=['GET'])
def download_cif(material_id):
    """
    获取材料的CIF文件数据，可选择返回超晶胞的CIF
    
    参数:
        material_id: 材料ID
        a, b, c: 可选，沿a, b, c方向的扩展倍数（查询参数）
        cellType: 可选，晶胞类型，可选 'primitive'或'conventional'（查询参数）
    
    返回:
        CIF文件内容，带有适当的MIME类型和文件名
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 获取请求参数，确定是否需要生成超晶胞
        a = request.args.get('a')
        b = request.args.get('b')
        c = request.args.get('c')
        cell_type = request.args.get('cellType')
        
        # 判断是否为普通下载还是超晶胞下载
        is_supercell = all([a, b, c])
        
        # 解析原始CIF文件
        # 首先尝试使用material.structure_file（如果存在）
        if hasattr(material, 'structure_file') and material.structure_file:
            file_path = material.structure_file
        else:
            # 否则，使用材料ID或名称查找CIF文件
            file_path = find_structure_file(material_id=material_id, material_name=material.name)
        
        # 检查是否找到文件
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 如果需要超晶胞，生成超晶胞的CIF数据
        if is_supercell:
            try:
                # 将字符串参数转换为整数
                a = int(a)
                b = int(b)
                c = int(c)
                
                # 参数验证：确保扩展倍数在有效范围内
                if a < 1 or b < 1 or c < 1 or a > 5 or b > 5 or c > 5:
                    return jsonify({"error": "Invalid supercell dimensions. Must be between 1 and 5."}), 400
                
                # 参数验证：确保晶胞类型是有效值
                if cell_type and cell_type not in ['primitive', 'conventional']:
                    return jsonify({"error": "Invalid cell type. Must be 'primitive' or 'conventional'."}), 400
                
                # 获取超晶胞CIF数据
                cif_data = get_cif_data(
                    file_path, 
                    a=a, 
                    b=b, 
                    c=c,
                    cell_type=cell_type or 'primitive'  # 如果未提供cell_type，默认使用primitive
                )
            except Exception as e:
                # 记录错误并返回500错误
                current_app.logger.error(f"Error generating supercell CIF: {str(e)}")
                return jsonify({"error": f"Error generating supercell: {str(e)}"}), 500
        else:
            # 读取原始CIF文件
            with open(file_path, 'r', encoding='utf-8') as f:
                cif_data = f.read()
        
        # 返回CIF数据，设置正确的MIME类型和文件名
        return cif_data, 200, {
            'Content-Type': 'chemical/x-cif',  # CIF文件的标准MIME类型
            'Content-Disposition': f'attachment; filename="{material.name or material_id}.cif"'  # 设置下载文件名
        }
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error downloading CIF file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/primitive', methods=['GET'])
def get_primitive_cell(material_id):
    """
    生成并返回晶体结构的原胞
    
    参数:
        material_id: 材料ID
    
    返回:
        包含原胞结构数据的JSON响应
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 解析原始CIF文件
        # 首先尝试使用material.structure_file（如果存在）
        if hasattr(material, 'structure_file') and material.structure_file:
            file_path = material.structure_file
        else:
            # 否则，使用材料ID或名称查找CIF文件
            file_path = find_structure_file(material_id=material_id, material_name=material.name)
        
        # 检查是否找到文件
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 文件路径需要完整，所以要添加应用根目录路径
        full_file_path = os.path.join(current_app.root_path, 'static/structures', file_path)
        
        # 生成原胞
        primitive_data = generate_primitive_cell(full_file_path)
        
        # 检查是否有错误
        result = json.loads(primitive_data)
        if 'error' in result:
            return jsonify(result), 500
        
        # 返回JSON响应，设置正确的内容类型
        return primitive_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error generating primitive cell: {str(e)}")
        return jsonify({"error": str(e)}), 500