# api.py
# 提供结构数据的API接口
# 本文件包含所有与晶体结构相关的API端点，处理结构数据的获取、上传和转换

import json
import os
from flask import Blueprint, jsonify, request, current_app
from .models import Material, db
from .structure_parser import parse_cif_file, save_structure_file, find_structure_file, generate_supercell, get_cif_data, _process_structure, generate_primitive_cell
from pymatgen.io.cif import CifWriter
from .material_importer import extract_chemical_formula_from_cif

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
        
        # 保存文件到指定目录（使用新路径结构：app/static/materials/IMR-0000xxxx/structure/structure.cif）
        filename = save_structure_file(
            file_content, 
            file.filename, 
            material_id=material_id, 
            material_name=material.name
        )
        
        # 检查文件是否保存成功
        if not filename:
            return jsonify({"error": "Failed to save structure file"}), 500
        
        # 更新材料数据库记录，更新化学式等信息
        try:
            # 构建完整文件路径
            file_path = os.path.join(current_app.root_path, 'static', filename)
            
            # 从CIF文件提取化学式
            chemical_name = extract_chemical_formula_from_cif(file_path)
            
            # 如果成功提取到化学式，更新材料名称
            if chemical_name:
                material.name = chemical_name
                current_app.logger.info(f"Updated material name to '{material.name}' from CIF chemical formula")
            else:
                # 如果无法直接提取化学式，尝试解析CIF获取计算的化学式
            structure_data_json = parse_cif_file(filename=filename)
            structure_data = json.loads(structure_data_json)
            
            if 'error' not in structure_data:
                    if 'formula' in structure_data:
                    material.name = structure_data.get('formula')
                    current_app.logger.info(f"Updated material name to '{material.name}' from CIF formula")
                
                # 更新金属类型等其他属性
                # 在这里可以添加其他需要从CIF文件更新的属性
                
                db.session.commit()
                current_app.logger.info(f"Updated material record for ID {material_id} from CIF file")
        except Exception as e:
            current_app.logger.warning(f"Failed to update material record from CIF: {str(e)}")
            # 继续执行，不中断上传过程
        
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
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
        
        # 检查是否找到文件
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
            
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
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

@bp.route('/structure', methods=['GET'])
def get_structure_by_params():
    """
    Get structure data by material_id or material_name
    
    Args:
        material_id: Material ID parameter
        material_name: Material name parameter
    
    Returns:
        JSON response with structure data including detailed atomic positions
    """
    try:
        # Get query parameters
    material_id = request.args.get('material_id')
    material_name = request.args.get('material_name')
    
        # At least one parameter must be provided
    if not material_id and not material_name:
            return jsonify({"error": "Either material_id or material_name must be provided"}), 400
    
        # If material_id is provided, try to find the corresponding cif file
        if material_id:
            try:
                material_id = int(material_id)
                # Get structure data using the id
                structure_data = parse_cif_file(material_id=material_id)
                
                # Check for errors in the result
                result = json.loads(structure_data)
                if 'error' in result:
                    # If no file found in new directory structure, try with material name
                material = Material.query.get(material_id)
                    if material and 'No structure file found' in result['error']:
                        structure_data = parse_cif_file(material_name=material.name)
            except ValueError:
                return jsonify({"error": "Invalid material_id format"}), 400
        else:
            # Use material_name to find structure file
            structure_data = parse_cif_file(material_name=material_name)
        
        # Process the result
        result = json.loads(structure_data)
        if 'error' in result:
            return jsonify(result), 404
            
        # Ensure sites data is properly formatted for the frontend
        if 'atoms' in result and isinstance(result['atoms'], list):
            # Create a sites array with the needed format
            sites = []
            for atom in result['atoms']:
                site = {
                    'species': [{'element': atom['element']}],
                    'xyz': atom['position'],
                    'frac_coords': atom['frac_coords'],
                    'wyckoff': atom.get('wyckoff', '')
                }
                sites.append(site)
        
            # Add sites to the result if not already present
            if 'sites' not in result or not result['sites']:
                result['sites'] = sites
                
        # Return JSON response
        return jsonify(result)
    
    except Exception as e:
        current_app.logger.error(f"Error getting structure data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/structure/update-names', methods=['POST'])
def update_material_names():
    """
    从现有的CIF文件更新材料名称
    
    可选参数:
        material_id: 特定材料的ID（如果提供，只更新这个材料）
    
    返回:
        更新结果的JSON响应
    """
    try:
        # 检查是否提供了具体的材料ID
        material_id = request.args.get('material_id')
        
        if material_id:
            # 如果提供了ID，只更新这个特定材料
            material = Material.query.get_or_404(int(material_id))
            materials = [material]
        else:
            # 否则，获取所有材料
            materials = Material.query.all()
        
        updated_count = 0
        errors = []
        
        # 遍历每个材料
        for material in materials:
            try:
                # 获取结构文件路径
                file_relative_path = find_structure_file(material_id=material.id)
                
                if not file_relative_path:
                    # 如果在新目录结构中没有找到，尝试在旧目录中查找
                    file_relative_path = find_structure_file(material_name=material.name)
                
                if not file_relative_path:
                    errors.append(f"No structure file found for material ID: {material.id}")
                    continue
                
                # 构建完整文件路径
                file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
                
                if not os.path.exists(file_path):
                    errors.append(f"Structure file not found on disk: {file_path}")
                    continue
                
                # 使用提取函数从CIF文件中读取化学式
                chemical_name = extract_chemical_formula_from_cif(file_path)
                
                # 如果找到了化学式，更新材料名称
                if chemical_name:
                    old_name = material.name
                    material.name = chemical_name
                    current_app.logger.info(f"Updated material ID {material.id} name from '{old_name}' to '{chemical_name}'")
                    updated_count += 1
                else:
                    # 如果没有找到化学式，尝试解析CIF获取计算的化学式
                    structure_data_json = parse_cif_file(filename=file_relative_path)
                    structure_data = json.loads(structure_data_json)
                    
                    if 'error' not in structure_data and 'formula' in structure_data:
                        old_name = material.name
                        material.name = structure_data['formula']
                        current_app.logger.info(f"Updated material ID {material.id} name from '{old_name}' to '{structure_data['formula']}' using formula")
                        updated_count += 1
            
            except Exception as e:
                errors.append(f"Error processing material ID {material.id}: {str(e)}")
        
        # 提交所有更改
        db.session.commit()
        
        # 返回更新结果
        return jsonify({
            "success": True,
            "message": f"Updated {updated_count} material names",
            "errors": errors
        })
    
    except Exception as e:
        # 回滚会话并返回错误
        db.session.rollback()
        current_app.logger.error(f"Error updating material names: {str(e)}")
        return jsonify({"error": str(e)}), 500