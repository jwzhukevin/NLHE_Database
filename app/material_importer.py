"""
材料数据导入模块：从JSON文件导入材料数据

此模块负责从存储在app/static/materials文件夹下的JSON文件中读取材料数据。
如果JSON文件不存在或数据缺失，则返回默认值。
"""

import os
import json
from flask import current_app
from .models import Material
from . import db

def get_material_data_from_json(material_id):
    """
    从对应材料ID的JSON文件中获取材料数据
    
    参数:
        material_id: 材料ID (格式如 'IMR-00000001')
    
    返回:
        包含材料属性的字典，如果文件不存在或读取失败则包含默认值
    """
    # 设置默认值
    default_data = {
        "name": "No Data",
        "status": "No Data",
        "structure_file": None,
        "total_energy": None,
        "formation_energy": None,
        "fermi_level": None,
        "vacuum_level": None,
        "workfunction": None,
        "metal_type": "No Data",
        "gap": None,
        "vbm_energy": None,
        "cbm_energy": None,
        "vbm_coordi": "No Data",
        "cbm_coordi": "No Data",
        "vbm_index": None,
        "cbm_index": None
    }
    
    # 构建材料文件夹路径
    materials_dir = os.path.join(current_app.root_path, 'static', 'materials', material_id)
    
    # 检查材料文件夹是否存在
    if not os.path.exists(materials_dir):
        return default_data
    
    # 获取文件夹中的所有JSON文件
    json_files = [f for f in os.listdir(materials_dir) if f.endswith('.json')]
    
    # 如果没有JSON文件，返回默认值
    if not json_files:
        return default_data
    
    # 使用第一个JSON文件作为数据源
    json_file_path = os.path.join(materials_dir, json_files[0])
    
    try:
        # 尝试读取JSON文件
        with open(json_file_path, 'r') as f:
            material_data = json.load(f)
            
        # 设置材料名称为JSON文件名（不包括扩展名）
        material_data['name'] = os.path.splitext(json_files[0])[0]
        
        # 合并JSON数据和默认值，确保所有字段都有值
        for key in default_data:
            if key not in material_data or material_data[key] is None:
                material_data[key] = default_data[key]
                
        return material_data
    
    except (json.JSONDecodeError, IOError, Exception) as e:
        # 如果读取失败，记录错误并返回默认值
        print(f"Error reading material data for {material_id}: {str(e)}")
        return default_data

def import_material_from_json(material_id):
    """
    从JSON文件导入材料数据并创建/更新材料记录
    
    参数:
        material_id: 材料ID (格式如 'IMR-00000001')
    
    返回:
        创建/更新的Material对象
    """
    # 检查材料是否已存在
    material = Material.query.filter_by(formatted_id=material_id).first()
    
    # 从JSON获取材料数据
    material_data = get_material_data_from_json(material_id)
    
    if material:
        # 更新现有材料
        material.name = material_data['name']
        material.status = material_data['status']
        material.structure_file = material_data['structure_file']
        material.total_energy = material_data['total_energy']
        material.formation_energy = material_data['formation_energy']
        material.fermi_level = material_data['fermi_level']
        material.vacuum_level = material_data['vacuum_level']
        material.workfunction = material_data['workfunction']
        material.metal_type = material_data['metal_type']
        material.gap = material_data['gap']
        material.vbm_energy = material_data['vbm_energy']
        material.cbm_energy = material_data['cbm_energy']
        material.vbm_coordi = material_data['vbm_coordi']
        material.cbm_coordi = material_data['cbm_coordi']
        material.vbm_index = material_data['vbm_index']
        material.cbm_index = material_data['cbm_index']
    else:
        # 创建新材料
        # 从ID中提取数字部分
        id_number = int(material_id.replace('IMR-', ''))
        
        # 创建新的Material对象
        material = Material(
            id=id_number,
            formatted_id=material_id,
            name=material_data['name'],
            status=material_data['status'],
            structure_file=material_data['structure_file'],
            total_energy=material_data['total_energy'],
            formation_energy=material_data['formation_energy'],
            fermi_level=material_data['fermi_level'],
            vacuum_level=material_data['vacuum_level'],
            workfunction=material_data['workfunction'],
            metal_type=material_data['metal_type'],
            gap=material_data['gap'],
            vbm_energy=material_data['vbm_energy'],
            cbm_energy=material_data['cbm_energy'],
            vbm_coordi=material_data['vbm_coordi'],
            cbm_coordi=material_data['cbm_coordi'],
            vbm_index=material_data['vbm_index'],
            cbm_index=material_data['cbm_index']
        )
        db.session.add(material)
    
    # 保存变更
    db.session.commit()
    
    return material

def scan_and_import_all_materials():
    """
    扫描materials文件夹并导入所有材料
    
    返回:
        导入的材料数量
    """
    materials_base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    
    # 检查基础目录是否存在
    if not os.path.exists(materials_base_dir):
        return 0
    
    # 计数器
    imported_count = 0
    
    # 遍历所有材料文件夹
    for material_folder in os.listdir(materials_base_dir):
        # 检查文件夹名称是否符合IMR-格式
        if material_folder.startswith('IMR-'):
            try:
                import_material_from_json(material_folder)
                imported_count += 1
            except Exception as e:
                print(f"Error importing material {material_folder}: {str(e)}")
    
    return imported_count 