# api.py
# 提供结构数据的API接口

import json
from flask import Blueprint, jsonify, request, current_app
from .models import Material, db
from .structure_parser import parse_cif_file, save_structure_file, find_structure_file

# 创建API蓝图
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/structure/<int:material_id>', methods=['GET'])
def get_structure(material_id):
    """
    获取指定材料的结构数据
    
    参数:
        material_id: 材料ID
    
    返回:
        包含原子坐标、晶格参数等信息的JSON响应
    """
    try:
        # 查询材料记录
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
            return jsonify(result), 404
        
        # 返回JSON响应
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/upload/<int:material_id>', methods=['POST'])
def upload_structure(material_id):
    """
    上传材料的CIF结构文件
    
    参数:
        material_id: 材料ID
    
    返回:
        上传结果的JSON响应
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        # 检查文件扩展名
        if not file.filename.lower().endswith('.cif'):
            return jsonify({"error": "File must be a CIF file"}), 400
        
        # 读取文件内容
        file_content = file.read()
        
        # 保存文件
        filename = save_structure_file(
            file_content, 
            file.filename, 
            material_id=material_id, 
            material_name=material.name
        )
        
        if not filename:
            return jsonify({"error": "Failed to save structure file"}), 500
        
        # 更新材料记录以关联新的结构文件
        if hasattr(material, 'structure_file'):
            material.structure_file = filename
            db.session.commit()
            current_app.logger.info(f"Updated structure file for material ID {material_id}: {filename}")
        
        # 返回成功响应
        return jsonify({
            "success": True,
            "message": "Structure file uploaded successfully",
            "filename": filename
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Error uploading structure file: {str(e)}")
        return jsonify({"error": str(e)}), 500