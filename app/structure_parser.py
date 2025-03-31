# structure_parser.py
# 用于解析CIF文件并生成Three.js可用的JSON数据
# 本文件包含处理晶体结构文件的核心功能，包括CIF文件解析、保存、查找以及超晶胞生成

import os
import json
import glob
from pymatgen.core import Structure  # pymatgen库用于处理晶体结构
from pymatgen.io.cif import CifWriter  # 用于生成CIF文件
from flask import current_app, abort
from .models import Material


def save_structure_file(file_content, filename, material_id=None, material_name=None):
    """
    保存上传的CIF文件到结构目录
    
    参数:
        file_content: 文件内容（二进制数据）
        filename: 原始文件名
        material_id: 材料ID（可选），用于标识文件
        material_name: 材料名称（可选），用于命名文件
    
    返回:
        保存的文件名，保存失败则返回None
    """
    try:
        # 构建结构文件目录路径（相对于Flask应用根目录）
        structures_dir = os.path.join(current_app.root_path, 'static/structures')
        
        # 确保目录存在，如果不存在则创建
        if not os.path.exists(structures_dir):
            os.makedirs(structures_dir)
        
        # 如果提供了材料名称，使用它来命名文件（更有意义的文件名）
        if material_name:
            # 清理材料名称，移除不适合文件名的字符（只保留字母、数字和下划线）
            safe_name = ''.join(c for c in material_name if c.isalnum() or c in '_-')
            filename = f"{safe_name}.cif"
        
        # 构建完整的文件保存路径
        file_path = os.path.join(structures_dir, filename)
        
        # 以二进制模式写入文件内容
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 记录日志
        current_app.logger.info(f"Saved structure file: {filename}")
        return filename
    
    except Exception as e:
        # 记录错误并返回None
        current_app.logger.error(f"Error saving structure file: {str(e)}")
        return None


def find_structure_file(material_id=None, material_name=None):
    """
    根据材料ID或名称查找对应的CIF文件
    
    参数:
        material_id: 材料ID，用于查询数据库获取材料名称
        material_name: 材料名称，用于直接查找文件
    
    返回:
        CIF文件名（不包含路径），未找到则返回None
    """
    try:
        # 如果提供了材料ID，则通过ID查询材料记录获取名称
        if material_id is not None:
            material = Material.query.get_or_404(material_id)
            material_name = material.name
        
        # 如果没有材料名称，则无法查找结构文件
        if not material_name:
            current_app.logger.error(f"No material name provided for ID: {material_id}")
            return None
        
        # 构建结构文件路径模式（使用精确的材料名称）
        structures_dir = os.path.join(current_app.root_path, 'static/structures')
        file_pattern = os.path.join(structures_dir, f"{material_name}.cif")
        
        # 使用glob查找匹配的文件
        matching_files = glob.glob(file_pattern)
        
        # 如果找到精确匹配的文件，返回文件名（不包含路径）
        if matching_files:
            return os.path.basename(matching_files[0])
        
        # 如果没有找到精确匹配，尝试使用模糊匹配（文件名包含材料名称）
        file_pattern = os.path.join(structures_dir, f"*{material_name}*.cif")
        matching_files = glob.glob(file_pattern)
        
        if matching_files:
            return os.path.basename(matching_files[0])
        
        # 如果仍然没有找到，记录错误并返回None
        current_app.logger.error(f"No structure file found for material: {material_name}")
        return None
    
    except Exception as e:
        # 记录错误并返回None
        current_app.logger.error(f"Error finding structure file: {str(e)}")
        return None


def parse_cif_file(filename=None, material_id=None, material_name=None):
    """
    使用pymatgen解析CIF文件，返回结构数据的JSON格式
    
    参数:
        filename: CIF文件名（不包含路径）
        material_id: 材料ID（如果未提供filename），用于查找文件
        material_name: 材料名称（如果未提供filename和material_id），用于查找文件
    
    返回:
        包含原子坐标、晶格参数等信息的JSON字符串，解析失败则返回错误JSON
    """
    try:
        # 如果未提供文件名，则尝试通过材料ID或名称查找
        if not filename and (material_id or material_name):
            filename = find_structure_file(material_id, material_name)
            
            # 如果仍然没有找到文件，则返回错误JSON
            if not filename:
                error_msg = f"No structure file found for material ID: {material_id} or name: {material_name}"
                current_app.logger.error(error_msg)
                return json.dumps({"error": error_msg})
        
        # 构建完整的文件路径
        file_path = os.path.join(current_app.root_path, 'static/structures', filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {filename}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 使用pymatgen加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 提取晶格参数
        lattice = structure.lattice
        lattice_data = {
            'a': lattice.a,  # a轴长度（埃）
            'b': lattice.b,  # b轴长度（埃）
            'c': lattice.c,  # c轴长度（埃）
            'alpha': lattice.alpha,  # alpha角（度）
            'beta': lattice.beta,    # beta角（度）
            'gamma': lattice.gamma,  # gamma角（度）
            'matrix': lattice.matrix.tolist()  # 晶格矩阵，转换为列表以便JSON序列化
        }
        
        # 提取原子信息
        atoms = []
        for site in structure.sites:
            atom = {
                'element': site.species_string,  # 元素符号
                'position': site.coords.tolist(),  # 笛卡尔坐标
                'frac_coords': site.frac_coords.tolist(),  # 分数坐标
                'properties': {
                    'label': site.species_string,  # 原子标签（用于显示）
                    'radius': get_atom_radius(site.species_string)  # 原子半径（用于3D渲染）
                }
            }
            atoms.append(atom)
        
        # 构建完整的结构数据
        structure_data = {
            'formula': structure.formula,  # 化学式
            'lattice': lattice_data,        # 晶格参数
            'atoms': atoms,                 # 原子列表
            'num_atoms': len(atoms)         # 原子总数
        }
        
        # 返回JSON字符串
        return json.dumps(structure_data)
    
    except Exception as e:
        # 记录错误并返回错误JSON
        error_msg = f"Error parsing CIF file {filename}: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})


def get_atom_radius(element):
    """
    返回元素的原子半径（用于Three.js中的可视化）
    
    参数:
        element: 元素符号（如H, O, Fe等）
    
    返回:
        原子半径（单位：埃），如果元素不在字典中，则返回默认值1.0
    """
    # 常见元素的原子半径（单位：埃）
    # 这些值用于Three.js中的可视化，不一定反映真实的原子半径
    radii = {
        'H': 0.31,
        'He': 0.28,
        'Li': 1.28,
        'Be': 0.96,
        'B': 0.84,
        'C': 0.76,
        'N': 0.71,
        'O': 0.66,
        'F': 0.57,
        'Ne': 0.58,
        'Na': 1.66,
        'Mg': 1.41,
        'Al': 1.21,
        'Si': 1.11,
        'P': 1.07,
        'S': 1.05,
        'Cl': 1.02,
        'Ar': 1.06,
        'K': 2.03,
        'Ca': 1.76,
        'Sc': 1.70,
        'Ti': 1.60,
        'V': 1.53,
        'Cr': 1.39,
        'Mn': 1.39,
        'Fe': 1.32,
        'Co': 1.26,
        'Ni': 1.24,
        'Cu': 1.32,
        'Zn': 1.22,
        'Ga': 1.22,
        'Ge': 1.20,
        'As': 1.19,
        'Se': 1.20,
        'Br': 1.20,
        'Kr': 1.16,
        'Rb': 2.20,
        'Sr': 1.95,
        'Y': 1.90,
        'Zr': 1.75,
        'Nb': 1.64,
        'Mo': 1.54,
        'Tc': 1.47,
        'Ru': 1.46,
        'Rh': 1.42,
        'Pd': 1.39,
        'Ag': 1.45,
        'Cd': 1.44,
        'In': 1.42,
        'Sn': 1.39,
        'Sb': 1.39,
        'Te': 1.38,
        'I': 1.39,
        'Xe': 1.40,
        'Cs': 2.44,
        'Ba': 2.15,
        'La': 2.07,
        'Ce': 2.04,
        'Pr': 2.03,
        'Nd': 2.01,
        'Pm': 1.99,
        'Sm': 1.98,
        'Eu': 1.98,
        'Gd': 1.96,
        'Tb': 1.94,
        'Dy': 1.92,
        'Ho': 1.92,
        'Er': 1.89,
        'Tm': 1.90,
        'Yb': 1.87,
        'Lu': 1.87,
        'Hf': 1.75,
        'Ta': 1.70,
        'W': 1.62,
        'Re': 1.51,
        'Os': 1.44,
        'Ir': 1.41,
        'Pt': 1.36,
        'Au': 1.36,
        'Hg': 1.32,
        'Tl': 1.45,
        'Pb': 1.46,
        'Bi': 1.48,
        'Po': 1.40,
        'At': 1.50,
        'Rn': 1.50,
        'Fr': 2.60,
        'Ra': 2.21,
        'Ac': 2.15,
        'Th': 2.06,
        'Pa': 2.00,
        'U': 1.96,
        'Np': 1.90,
        'Pu': 1.87,
        'Am': 1.80,
        'Cm': 1.69
    }
    
    # 如果元素在字典中，返回对应的半径，否则返回默认值1.0
    return radii.get(element, 1.0)


def generate_supercell(file_path, a=1, b=1, c=1, cell_type='primitive'):
    """
    生成超晶胞结构并返回JSON数据
    
    参数:
        file_path: CIF文件路径
        a, b, c: 沿a, b, c方向的扩展倍数（默认为1，即不扩展）
        cell_type: 晶胞类型，可选值 'primitive'（原胞）或 'conventional'（常规胞）
    
    返回:
        包含超晶胞结构的JSON字符串，出错则返回错误JSON
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {file_path}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 获取完整路径（如果传入的是相对路径）
        if not os.path.isabs(file_path):
            file_path = os.path.join(current_app.root_path, 'static/structures', file_path)
        
        # 使用pymatgen加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 根据需要转换为常规胞（如果选择了conventional类型）
        if cell_type == 'conventional':
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            analyzer = SpacegroupAnalyzer(structure)
            structure = analyzer.get_conventional_standard_structure()
        
        # 创建超晶胞（通过复制原胞）
        supercell = structure.copy()
        supercell.make_supercell([a, b, c])  # 指定a、b、c方向的扩展倍数
        
        # 提取晶格参数
        lattice = supercell.lattice
        lattice_data = {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'matrix': lattice.matrix.tolist()  # 转换为列表以便JSON序列化
        }
        
        # 提取原子信息
        atoms = []
        for site in supercell.sites:
            atom = {
                'element': site.species_string,
                'position': site.coords.tolist(),  # 笛卡尔坐标
                'frac_coords': site.frac_coords.tolist(),  # 分数坐标
                'properties': {
                    'label': site.species_string,
                    'radius': get_atom_radius(site.species_string)
                }
            }
            atoms.append(atom)
        
        # 构建完整的结构数据，包含超晶胞信息
        structure_data = {
            'formula': supercell.formula,
            'lattice': lattice_data,
            'atoms': atoms,
            'num_atoms': len(atoms),
            'supercell': {
                'a': a,  # a方向扩展倍数
                'b': b,  # b方向扩展倍数
                'c': c,  # c方向扩展倍数
                'type': cell_type  # 晶胞类型
            }
        }
        
        # 返回JSON字符串
        return json.dumps(structure_data)
    
    except Exception as e:
        # 记录错误并返回错误JSON
        error_msg = f"Error generating supercell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})


def get_cif_data(file_path, a=1, b=1, c=1, cell_type='primitive'):
    """
    生成超晶胞结构的CIF数据，用于文件下载
    
    参数:
        file_path: CIF文件路径
        a, b, c: 沿a, b, c方向的扩展倍数（默认为1，即不扩展）
        cell_type: 晶胞类型，可选值 'primitive'（原胞）或 'conventional'（常规胞）
    
    返回:
        CIF文件内容字符串
    
    异常:
        如果文件不存在或处理过程出错，将抛出异常
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {file_path}"
            current_app.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 获取完整路径（如果传入的是相对路径）
        if not os.path.isabs(file_path):
            file_path = os.path.join(current_app.root_path, 'static/structures', file_path)
        
        # 使用pymatgen加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 根据需要转换为常规胞
        if cell_type == 'conventional':
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            analyzer = SpacegroupAnalyzer(structure)
            structure = analyzer.get_conventional_standard_structure()
        
        # 创建超晶胞
        supercell = structure.copy()
        supercell.make_supercell([a, b, c])
        
        # 使用CifWriter生成CIF数据
        cif_writer = CifWriter(supercell)
        cif_content = cif_writer.write_string()
        
        # 返回CIF文件内容
        return cif_content
    
    except Exception as e:
        # 记录错误并抛出异常（由调用者处理）
        error_msg = f"Error generating CIF data: {str(e)}"
        current_app.logger.error(error_msg)
        raise Exception(error_msg)