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
    保存上传的CIF文件到材料对应的结构目录
    
    参数:
        file_content: 文件内容（二进制数据）
        filename: 原始文件名
        material_id: 材料ID，用于标识文件目录
        material_name: 材料名称（可选），用于命名文件
    
    返回:
        保存的文件相对路径，保存失败则返回None
    """
    try:
        # 构建材料ID格式化字符串
        formatted_id = f"IMR-{int(material_id):08d}" if material_id else None
        
        if not formatted_id and not material_name:
            current_app.logger.error("Neither material_id nor material_name provided")
            return None
        
        # 构建材料目录路径
        materials_dir = os.path.join(current_app.root_path, 'static/materials')
        
        # 确保基础目录存在
        if not os.path.exists(materials_dir):
            os.makedirs(materials_dir)
        
        # 构建特定材料目录
        material_dir = os.path.join(materials_dir, formatted_id)
        if not os.path.exists(material_dir):
            os.makedirs(material_dir)
        
        # 构建结构文件目录
        structure_dir = os.path.join(material_dir, 'structure')
        if not os.path.exists(structure_dir):
            os.makedirs(structure_dir)
        
        # 设置保存的文件名（统一使用structure.cif）
        save_filename = "structure.cif"
        
        # 构建完整的文件保存路径
        file_path = os.path.join(structure_dir, save_filename)
        
        # 以二进制模式写入文件内容
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 记录日志
        current_app.logger.info(f"Saved structure file for material {formatted_id}: {file_path}")
        
        # 返回相对于static的路径
        relative_path = os.path.join('materials', formatted_id, 'structure', save_filename)
        return relative_path
    
    except Exception as e:
        # 记录错误并返回None
        current_app.logger.error(f"Error saving structure file: {str(e)}")
        return None


def find_structure_file(material_id=None, material_name=None):
    """
    根据材料ID或名称查找对应的CIF文件
    
    参数:
        material_id: 材料ID，用于构建目录路径
        material_name: 材料名称，用于向后兼容旧版本的查找方式
    
    返回:
        CIF文件相对路径，未找到则返回None
    """
    try:
        # 首先尝试使用材料ID查找文件
        if material_id is not None:
            # 构建材料ID格式化字符串
            formatted_id = f"IMR-{int(material_id):08d}"
            
            # 构建结构文件路径
            material_dir = os.path.join(current_app.root_path, 'static/materials', formatted_id)
            structure_dir = os.path.join(material_dir, 'structure')
            structure_file = os.path.join(structure_dir, 'structure.cif')
            
            # 检查文件是否存在
            if os.path.exists(structure_file):
                # 返回相对于static目录的路径
                relative_path = os.path.join('materials', formatted_id, 'structure', 'structure.cif')
                return relative_path
        
        # 如果通过材料ID没有找到，或未提供材料ID，尝试使用材料名称查找
        # 这部分用于向后兼容，查找旧版系统的结构文件
        if material_name:
            # 尝试在旧的结构目录中查找文件
            old_structures_dir = os.path.join(current_app.root_path, 'static/structures')
            
            # 使用材料名称构建可能的文件名（精确匹配）
            file_pattern = os.path.join(old_structures_dir, f"{material_name}.cif")
            matching_files = glob.glob(file_pattern)
            
            if matching_files:
                # 如果找到文件，返回相对于static的路径
                file_path = matching_files[0]
                relative_path = os.path.relpath(file_path, os.path.join(current_app.root_path, 'static'))
                return relative_path
            
            # 尝试模糊匹配
            file_pattern = os.path.join(old_structures_dir, f"*{material_name}*.cif")
            matching_files = glob.glob(file_pattern)
            
            if matching_files:
                file_path = matching_files[0]
                relative_path = os.path.relpath(file_path, os.path.join(current_app.root_path, 'static'))
                return relative_path
        
        # 记录未找到文件的信息
        current_app.logger.error(f"No structure file found for material ID: {material_id} or name: {material_name}")
        return None
    
    except Exception as e:
        # 记录错误并返回None
        current_app.logger.error(f"Error finding structure file: {str(e)}")
        return None


def parse_cif_file(filename=None, material_id=None, material_name=None):
    """
    使用pymatgen解析CIF文件，返回结构数据的JSON格式
    
    参数:
        filename: CIF文件相对路径
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
        
        # 构建完整的文件路径（filename现在是相对于static目录的路径）
        file_path = os.path.join(current_app.root_path, 'static', filename)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {filename}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 尝试从CIF文件中读取化学式名称
        chemical_name = None
        try:
            with open(file_path, 'r') as f:
                cif_content = f.readlines()
                for line in cif_content:
                    if '_chemical_formula_structural' in line:
                        # 提取_chemical_formula_structural后的值
                        parts = line.strip().split()
                        if len(parts) > 1:
                            chemical_name = parts[1].strip("'").strip('"')
                            break
            current_app.logger.info(f"Read chemical formula from CIF: {chemical_name}")
        except Exception as e:
            current_app.logger.warning(f"Could not read chemical formula from CIF file: {str(e)}")
        
        # 使用pymatgen加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 提取更多结构信息
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        analyzer = SpacegroupAnalyzer(structure)
        
        # 获取空间群信息
        spacegroup_symbol = analyzer.get_space_group_symbol()
        spacegroup_number = analyzer.get_space_group_number()
        crystal_system = analyzer.get_crystal_system()
        point_group = analyzer.get_point_group_symbol()
        
        # 获取常规胞结构以展示标准化的数据
        conventional_structure = analyzer.get_conventional_standard_structure()
        
        # 提取晶格参数（使用常规胞）
        lattice = conventional_structure.lattice
        lattice_data = {
            'a': lattice.a,  # a轴长度（埃）
            'b': lattice.b,  # b轴长度（埃）
            'c': lattice.c,  # c轴长度（埃）
            'alpha': lattice.alpha,  # alpha角（度）
            'beta': lattice.beta,    # beta角（度）
            'gamma': lattice.gamma,  # gamma角（度）
            'volume': lattice.volume,  # 晶胞体积（埃^3）
            'matrix': lattice.matrix.tolist()  # 晶格矩阵，转换为列表以便JSON序列化
        }
        
        # 如果未能从CIF文件中读取化学式，则使用pymatgen计算的化学式
        composition_name = conventional_structure.composition.reduced_formula
        if not chemical_name:
            chemical_name = composition_name  # 默认使用计算的化学式作为名称
        
        # 提取原子信息
        atoms = []
        wyckoff_sites = analyzer.get_symmetry_dataset()['wyckoffs']
        equivalent_atoms = analyzer.get_symmetry_dataset()['equivalent_atoms']
        
        for i, site in enumerate(conventional_structure.sites):
            # 获取Wyckoff位置
            wyckoff = wyckoff_sites[equivalent_atoms[i]] if i < len(equivalent_atoms) else "?"
            
            # 获取元素符号
            element_str = site.species_string
            
            atom = {
                'element': element_str,  # 元素符号
                'position': site.coords.tolist(),  # 笛卡尔坐标
                'frac_coords': site.frac_coords.tolist(),  # 分数坐标
                'wyckoff': wyckoff,  # Wyckoff位置
                'properties': {
                    'label': element_str,  # 原子标签（用于显示）
                    'radius': get_atom_radius(element_str)  # 原子半径（用于3D渲染）
                }
            }
            atoms.append(atom)
        
        # 提取可能的氧化态
        possible_oxidation_states = {}
        for element in conventional_structure.composition.elements:
            # 处理元素符号，确保移除可能的电荷标记
            elem_symbol = str(element)
            # 提取纯元素符号（去除任何+、-等电荷标记）
            pure_elem_symbol = ''.join(c for c in elem_symbol if c.isalpha())
            
            try:
                from pymatgen.core.periodic_table import Element
                possible_oxidation_states[elem_symbol] = Element(pure_elem_symbol).oxidation_states
            except Exception as e:
                # 如果获取氧化态失败，记录错误但继续处理
                current_app.logger.warning(f"Could not get oxidation states for element {elem_symbol}: {str(e)}")
                possible_oxidation_states[elem_symbol] = []
        
        # 构建完整的结构数据
        structure_data = {
            'name': chemical_name,  # 使用从CIF读取的化学式名称
            'formula': conventional_structure.formula,  # 完整化学式
            'lattice': lattice_data,  # 晶格参数
            'atoms': atoms,  # 原子列表
            'sites': [  # 单独添加sites数据以便前端使用
                {
                    'species': [{'element': atom['element']}],
                    'xyz': atom['position'],
                    'frac_coords': atom['frac_coords'],
                    'wyckoff': atom.get('wyckoff', '')
                } for atom in atoms
            ],
            'num_atoms': len(atoms),  # 原子总数
            'density': conventional_structure.density,  # 密度 (g/cm^3)
            'symmetry': {
                'crystal_system': crystal_system,  # 晶系
                'space_group_symbol': spacegroup_symbol,  # 空间群符号
                'space_group_number': spacegroup_number,  # 空间群编号
                'point_group': point_group,  # 点群
                # 'hall_number': analyzer.get_hall_number(),  # Hall编号
            },
            'dimensionality': '3D',  # 默认为3D
            'possible_oxidation_states': possible_oxidation_states,  # 可能的氧化态
            'id': material_id,  # 添加材料ID便于前端引用
            'chemical_formula_structural': chemical_name  # 添加原始的结构化化学式
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
        element: 元素符号（如H, O, Fe等），可能包含电荷标记如Li+、O2-
    
    返回:
        原子半径（单位：埃），如果元素不在字典中，则返回默认值1.0
    """
    # 处理可能带有电荷的元素符号，提取纯元素部分
    # 例如：Li+ -> Li, O2- -> O, Fe3+ -> Fe
    pure_element = ''.join(c for c in element if c.isalpha())
    
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
    return radii.get(pure_element, 1.0)


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
        # 验证输入参数
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or not isinstance(c, (int, float)):
            error_msg = "Supercell parameters (a, b, c) must be numbers"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        if a <= 0 or b <= 0 or c <= 0:
            error_msg = "Supercell parameters (a, b, c) must be positive"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        if cell_type not in ['primitive', 'conventional']:
            error_msg = "Cell type must be either 'primitive' or 'conventional'"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 规范化文件路径
        if not os.path.isabs(file_path):
            file_path = os.path.join(current_app.root_path, 'static/structures', file_path)
        file_path = os.path.normpath(file_path)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {file_path}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        try:
            # 使用pymatgen加载晶体结构
            structure = Structure.from_file(file_path)
        except Exception as e:
            error_msg = f"Error loading structure file: {str(e)}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 根据需要转换为常规胞（如果选择了conventional类型）
        if cell_type == 'conventional':
            try:
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure, symprec=0.1, angle_tolerance=5)
                conventional_structure = analyzer.get_conventional_standard_structure()
                if conventional_structure is not None:
                    structure = conventional_structure
                else:
                    current_app.logger.warning("Could not determine conventional cell, using original structure")
            except Exception as e:
                error_msg = f"Error converting to conventional cell: {str(e)}"
                current_app.logger.error(error_msg)
                return json.dumps({"error": error_msg})
        
        try:
            # 创建超晶胞（通过复制原胞）
            supercell = structure.copy()
            supercell.make_supercell([float(a), float(b), float(c)])  # 确保使用浮点数
        except Exception as e:
            error_msg = f"Error creating supercell: {str(e)}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
            
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
            element_str = site.species_string
            atom = {
                'element': element_str,
                'position': site.coords.tolist(),  # 笛卡尔坐标
                'frac_coords': site.frac_coords.tolist(),  # 分数坐标
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str)  # 现在get_atom_radius可以处理带电荷的元素
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


def _process_structure(structure, cell_type='primitive', symprec=0.1, angle_tolerance=5):
    """
    处理晶体结构，转换为指定类型的晶胞并提取结构数据
    
    参数:
        structure: pymatgen Structure对象
        cell_type: 晶胞类型，'primitive'或'conventional'
        symprec: 对称性判断的容差
        angle_tolerance: 角度判断的容差（度）
    
    返回:
        转换后的结构数据字典
    """
    try:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        analyzer = SpacegroupAnalyzer(structure, symprec=symprec, angle_tolerance=angle_tolerance)
        
        # 获取空间群信息
        spacegroup = analyzer.get_space_group_symbol()
        
        # 根据cell_type选择合适的转换方法
        if cell_type == 'primitive':
            converted_structure = analyzer.find_primitive()
            if converted_structure is None:
                current_app.logger.warning(f"Could not find primitive cell, using original structure")
                converted_structure = structure
            is_primitive = True
        else:  # conventional
            converted_structure = analyzer.get_conventional_standard_structure()
            if converted_structure is None:
                current_app.logger.warning(f"Could not determine conventional cell, using original structure")
                converted_structure = structure
            is_primitive = False
        
        # 提取晶格参数
        lattice = converted_structure.lattice
        lattice_data = {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'matrix': lattice.matrix.tolist(),
            'volume': lattice.volume  # 添加晶胞体积信息
        }
        
        # 提取空间群信息
        spacegroup_data = {
            'symbol': analyzer.get_space_group_symbol(),
            'number': analyzer.get_space_group_number(),
            'crystal_system': analyzer.get_crystal_system(),
            'point_group': analyzer.get_point_group_symbol()
        }
        
        # 提取原子信息
        atoms = []
        for site in converted_structure.sites:
            # 确保使用纯元素符号
            element_str = site.species_string
            # 安全获取氧化态信息
            oxidation_state = None
            try:
                if site.species.get_oxidation_states():
                    oxidation_state = site.species.get_oxidation_states()[0]
            except Exception:
                # 如果获取氧化态失败，设为None
                oxidation_state = None
                
            atom = {
                'element': element_str,
                'position': site.coords.tolist(),
                'frac_coords': site.frac_coords.tolist(),
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str.split('+')[0].split('-')[0]),  # 只使用元素符号部分获取半径
                    'oxidation_state': oxidation_state
                }
            }
            atoms.append(atom)
        
        # 构建完整的结构数据
        structure_data = {
            'formula': converted_structure.formula,
            'name': converted_structure.composition.reduced_formula,
            'lattice': lattice_data,
            'atoms': atoms,
            'num_atoms': len(atoms),
            'isPrimitive': is_primitive,
            'spacegroup': spacegroup_data,
            'density': converted_structure.density,
            'cell_type': cell_type
        }
        
        return structure_data
        
    except Exception as e:
        error_msg = f"Error processing structure: {str(e)}"
        current_app.logger.error(error_msg)
        raise Exception(error_msg)


def generate_primitive_cell(file_path):
    """
    生成晶体结构的原胞
    
    参数:
        file_path: CIF文件路径
    
    返回:
        原胞结构的JSON字符串，失败则返回错误JSON
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {file_path}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 处理结构并获取数据
        structure_data = _process_structure(structure, cell_type='primitive')
        
        # 返回JSON字符串
        return json.dumps(structure_data)
        
    except Exception as e:
        error_msg = f"Error generating primitive cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})


def generate_conventional_cell(file_path):
    """
    生成晶体结构的常规胞（传统胞）
    
    参数:
        file_path: CIF文件路径
    
    返回:
        常规胞结构的JSON字符串，失败则返回错误JSON
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"Structure file not found: {file_path}"
            current_app.logger.error(error_msg)
            return json.dumps({"error": error_msg})
        
        # 加载晶体结构
        structure = Structure.from_file(file_path)
        
        # 处理结构并获取数据
        structure_data = _process_structure(structure, cell_type='conventional')
        
        # 返回JSON字符串
        return json.dumps(structure_data)
        
    except Exception as e:
        error_msg = f"Error generating conventional cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})