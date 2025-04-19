# api.py
# 提供结构数据的API接口
# 本文件包含所有与晶体结构相关的API端点，处理结构数据的获取、上传和转换

import json
import os
from flask import Blueprint, jsonify, request, current_app
from .models import Material, db
from .structure_parser import parse_cif_file, save_structure_file, find_structure_file, generate_supercell, get_cif_data, _process_structure, generate_primitive_cell
from pymatgen.io.cif import CifWriter

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
        # 现在直接使用material_id查找对应目录中的结构文件
        structure_data = parse_cif_file(material_id=material_id)
        
        # 检查是否有错误
        result = json.loads(structure_data)
        if 'error' in result:
            # 如果新目录结构下没有找到文件，尝试使用材料名称在旧目录结构中查找
            if 'No structure file found' in result['error']:
                structure_data = parse_cif_file(material_name=material.name)
                result = json.loads(structure_data)
                if 'error' in result:
                    return jsonify(result), 404  # 返回错误信息和404状态码
        
        # 返回JSON响应，设置正确的内容类型
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        # 捕获所有异常并返回500错误
        current_app.logger.error(f"Error getting structure data: {str(e)}")
        return jsonify({"error": str(e)}), 500




@bp.route('/structure/<int:material_id>/conventional', methods=['GET'])
def get_conventional_cell(material_id):
    """
    获取指定材料的传统胞结构数据
    
    参数:
        material_id: 材料ID，用于在数据库中查找对应的材料记录
    
    返回:
        包含传统胞结构数据的JSON响应
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 构建材料ID格式化字符串
        formatted_id = f"IMR-{int(material_id):08d}"
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
            
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 加载结构并转换为传统胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='conventional')
        
        # 添加材料ID到结构数据中
        structure_data['id'] = material_id
        
        # 返回JSON响应
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"Error converting to conventional cell: {str(e)}")
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
        
        # 构建材料ID格式化字符串
        formatted_id = f"IMR-{int(material_id):08d}"
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
            
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 根据请求参数处理文件
        if is_supercell:
            # 如果请求超晶胞，生成并返回超晶胞CIF
            from pymatgen.core import Structure
            structure = Structure.from_file(file_path)
            
            # 将参数转换为整数
            a_val = int(a)
            b_val = int(b)
            c_val = int(c)
            
            # 参数验证
            if a_val < 1 or b_val < 1 or c_val < 1 or a_val > 5 or b_val > 5 or c_val > 5:
                return jsonify({"error": "Invalid supercell dimensions. Must be between 1 and 5."}), 400
            
            # 处理晶胞类型
            if cell_type == 'conventional':
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure)
                structure = analyzer.get_conventional_standard_structure()
            
            # 生成超晶胞
            supercell = structure.make_supercell([a_val, b_val, c_val])
            
            # 创建CIF写入器
            cif_writer = CifWriter(supercell)
            cif_string = cif_writer.write_str()
            
            # 构建文件名
            filename = f"{material.name}_supercell_{a_val}x{b_val}x{c_val}.cif"
        else:
            # 普通下载，直接读取文件内容
            with open(file_path, 'r') as f:
                cif_string = f.read()
            
            # 使用材料名称作为文件名
            filename = f"{material.name}.cif"
        
        # 返回CIF文件内容，设置正确的响应头
        response = current_app.response_class(
            cif_string,
            mimetype="chemical/x-cif",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        return response
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error downloading CIF file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/primitive', methods=['GET'])
def get_primitive_cell(material_id):
    """
    获取指定材料的原始胞结构数据
    
    参数:
        material_id: 材料ID，用于在数据库中查找对应的材料记录
    
    返回:
        包含原始胞结构数据的JSON响应
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 构建材料ID格式化字符串
        formatted_id = f"IMR-{int(material_id):08d}"
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
            
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 加载结构并转换为原始胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='primitive')
        
        # 添加材料ID到结构数据中
        structure_data['id'] = material_id
        
        # 返回JSON响应
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"Error converting to primitive cell: {str(e)}")
        return jsonify({"error": str(e)}), 500