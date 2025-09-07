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
import re


def get_material_dir(material_id):
    """
    根据材料 ID 返回材料目录路径。

    目录策略：
    - 新标准：`IMR-{id}`（不补零）；
    - 兼容回退：若新目录不存在，则尝试旧格式 `IMR-{id:08d}`；
    - 返回值：若两者都不存在，返回新格式路径（调用方可据此创建）。
    """
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    if os.path.exists(new_dir):
        return new_dir
    # 兼容旧格式
    old_dir = os.path.join(base_dir, f'IMR-{int(material_id):08d}')
    if os.path.exists(old_dir):
        return old_dir
    return new_dir  # 默认返回新格式路径


def save_structure_file(file_content, filename, material_id=None, material_name=None):
    """
    保存上传的 CIF 文件到材料对应的结构目录。

    参数:
        file_content: 文件内容（二进制数据）
        filename: 原始文件名
        material_id: 材料 ID，用于标识文件目录
        material_name: 材料名称（保留参数，当前不用于命名）

    返回:
        保存的文件相对路径，保存失败则返回 None
    """
    try:
        if not material_id:
            current_app.logger.error("Material ID not provided")
            return None
        
        # 构建路径和目录
        material_dir = get_material_dir(material_id)
        structure_dir = os.path.join(material_dir, 'structure')
        os.makedirs(structure_dir, exist_ok=True)
        
        # 处理文件名和保存文件
        save_filename = filename if filename.lower().endswith('.cif') else filename + ".cif"
        file_path = os.path.join(structure_dir, save_filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 返回相对路径
        relative_path = os.path.join('materials', os.path.basename(material_dir), 'structure', save_filename)
        return relative_path
    
    except Exception as e:
        current_app.logger.error(f"Error saving structure file: {str(e)}")
        return None


def find_structure_file(material_id=None, material_name=None):
    """
    根据材料 ID 查找对应的 CIF 文件。

    策略：
    - 优先在新目录 `IMR-{id}` 下查找；
    - 若不存在则回退旧格式 `IMR-{id:08d}`；
    - 成功返回相对路径，失败返回 None；
    - 说明：为降低维护成本，回退逻辑集中在本模块，其它模块不再感知旧格式。

    参数:
        material_id: 材料 ID，用于构建目录路径
        material_name: 材料名称（保留参数，不再使用）

    返回:
        CIF 文件相对路径，未找到则返回 None
    """
    try:
        if material_id is None:
            return None
        material_dir = get_material_dir(material_id)
        structure_dir = os.path.join(material_dir, 'structure')
        if not os.path.exists(structure_dir):
            return None
        cif_files = glob.glob(os.path.join(structure_dir, "*.cif"))
        if cif_files:
            relative_path = os.path.relpath(cif_files[0], os.path.join(current_app.root_path, 'static'))
            return relative_path
        return None
    except Exception as e:
        current_app.logger.error(f"Error finding structure file: {str(e)}")
        return None


def parse_cif_file(filename=None, material_id=None, material_name=None):
    """
    使用 pymatgen 解析 CIF 文件，返回结构数据的 JSON 字符串。

    参数:
        filename: CIF 文件相对路径
        material_id: 材料 ID，用于查找文件
        material_name: 材料名称，参数保留但不再使用

    返回:
        JSON 字符串：包含原子坐标、晶格参数与对称信息；解析失败返回错误 JSON。
    """
    try:
        # 参数验证和文件查找
        if not filename and not material_id:
            return json.dumps({"error": "No filename or material_id provided"})
        
        if not filename and material_id:
            filename = find_structure_file(material_id=material_id)
            if not filename:
                return json.dumps({"error": f"No structure file found for material ID: {material_id}"})
        
        # 构建文件路径并检查文件
        file_path = os.path.join(current_app.root_path, 'static', filename)
        if not os.path.exists(file_path):
            return json.dumps({"error": f"Structure file not found: {filename}"})
        
        if os.path.getsize(file_path) == 0:
            return json.dumps({"error": f"Structure file is empty: {filename}"})
        
        # 尝试从CIF文件中读取化学式名称
        chemical_name = None
        try:
            with open(file_path, 'r') as f:
                cif_content = f.readlines()
                for line in cif_content:
                    if '_chemical_formula_structural' in line:
                        parts = line.strip().split()
                        if len(parts) > 1:
                            chemical_name = parts[1].strip("'").strip('"')
                            break
                    elif '_chemical_formula_sum' in line:
                        parts = line.strip().split()
                        if len(parts) > 1:
                            chemical_name = parts[1].strip("'").strip('"')
                            # 继续查找，优先使用structural公式
                    elif '_chemical_name_systematic' in line and not chemical_name:
                        parts = line.strip().split()
                        if len(parts) > 1:
                            chemical_name = parts[1].strip("'").strip('"')
        except Exception:
            pass  # 如果无法读取化学式，继续处理
        
        # 加载晶体结构
        try:
            structure = Structure.from_file(file_path)
        except Exception as e:
            return json.dumps({"error": f"Error loading structure from file: {str(e)}"})
        
        # 提取结构信息
        try:
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
            analyzer = SpacegroupAnalyzer(structure)
            spacegroup_symbol = analyzer.get_space_group_symbol()
            spacegroup_number = analyzer.get_space_group_number()
            crystal_system = analyzer.get_crystal_system()
            point_group = analyzer.get_point_group_symbol()
            conventional_structure = analyzer.get_conventional_standard_structure()
        except Exception:
            conventional_structure = structure
            spacegroup_symbol = "Unknown"
            spacegroup_number = 0
            crystal_system = "Unknown"
            point_group = "Unknown"
        
        # 提取晶格参数（使用常规胞）
        lattice = conventional_structure.lattice
        lattice_data = {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'volume': lattice.volume,
            'matrix': lattice.matrix.tolist()
        }
        
        # 如果未能从CIF文件中读取化学式，则使用pymatgen计算的化学式
        composition_name = conventional_structure.composition.reduced_formula
        if not chemical_name:
            chemical_name = composition_name
        
        # 提取原子信息
        atoms = []
        try:
            wyckoff_sites = analyzer.get_symmetry_dataset()['wyckoffs']
            equivalent_atoms = analyzer.get_symmetry_dataset()['equivalent_atoms']
        except Exception:
            wyckoff_sites = None
            equivalent_atoms = None

        for i, site in enumerate(conventional_structure.sites):
            element_str = site.species_string
            wyckoff = wyckoff_sites[i] if wyckoff_sites is not None else None
                
            atom = {
                'element': element_str,
                'position': site.coords.tolist(),
                'frac_coords': site.frac_coords.tolist(),
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str),
                    'wyckoff': wyckoff
                }
            }
            atoms.append(atom)
        
        # 计算密度（如果pymatgen的density属性不可用，则使用简单估算）
        try:
            density = conventional_structure.density
        except (AttributeError, Exception):
            # 如果无法获取密度，使用一个合理的默认值
            density = 5.0  # g/cm³，一个合理的默认值
        
        # 构建完整的结构数据，包含晶胞和对称性信息
        structure_data = {
            'id': material_id,
            'formula': chemical_name,
            'composition': composition_name,
            'lattice': lattice_data,
            'atoms': atoms,
            'num_atoms': len(atoms),
            'density': density,
            'symmetry': {
                'symbol': spacegroup_symbol,
                'number': spacegroup_number,
                'crystal_system': crystal_system,
                'point_group': point_group
            }
        }
        
        # 返回JSON字符串
        return json.dumps(structure_data)
    
    except Exception as e:
        return json.dumps({"error": str(e)})


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
        # 参数验证
        if not all(isinstance(x, (int, float)) and x > 0 for x in [a, b, c]):
            return json.dumps({"error": "Supercell parameters must be positive numbers"})
        
        if cell_type not in ['primitive', 'conventional']:
            return json.dumps({"error": "Cell type must be either 'primitive' or 'conventional'"})
        
        # 检查文件
        if not os.path.exists(file_path):
            return json.dumps({"error": f"Structure file not found: {file_path}"})
        
        # 加载结构
        try:
            structure = Structure.from_file(file_path)
        except Exception as e:
            return json.dumps({"error": f"Error loading structure file: {str(e)}"})
        
        # 应用晶胞转换
        if cell_type == 'conventional':
            try:
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure, symprec=0.1, angle_tolerance=5)
                conventional_structure = analyzer.get_conventional_standard_structure()
                if conventional_structure:
                    structure = conventional_structure
            except Exception:
                pass  # 如果转换失败，使用原始结构
        
        # 创建超晶胞
        supercell = structure.copy()
        supercell.make_supercell([float(a), float(b), float(c)])
            
        # 提取晶格参数
        lattice = supercell.lattice
        lattice_data = {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'matrix': lattice.matrix.tolist()
        }
        
        # 提取原子信息
        atoms = []
        for site in supercell.sites:
            element_str = site.species_string
            atom = {
                'element': element_str,
                'position': site.coords.tolist(),
                'frac_coords': site.frac_coords.tolist(),
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str)
                }
            }
            atoms.append(atom)
        
        # 构建完整的结构数据
        structure_data = {
            'formula': supercell.formula,
            'lattice': lattice_data,
            'atoms': atoms,
            'num_atoms': len(atoms),
            'supercell': {
                'a': a,
                'b': b,
                'c': c,
                'type': cell_type
            }
        }
        
        return json.dumps(structure_data)
    
    except Exception as e:
        return json.dumps({"error": str(e)})


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
            if not converted_structure:
                converted_structure = structure
            is_primitive = True
        else:  # conventional
            converted_structure = analyzer.get_conventional_standard_structure()
            if not converted_structure:
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
            'volume': lattice.volume
        }
        
        # 提取原子信息
        atoms = []
        try:
            wyckoff_sites = analyzer.get_symmetry_dataset()['wyckoffs']
            equivalent_atoms = analyzer.get_symmetry_dataset()['equivalent_atoms']
        except Exception:
            wyckoff_sites = None
            equivalent_atoms = None
        
        for i, site in enumerate(converted_structure.sites):
            element_str = site.species_string
            wyckoff = wyckoff_sites[i] if wyckoff_sites is not None else None
                
            atom = {
                'element': element_str,
                'position': site.coords.tolist(),
                'frac_coords': site.frac_coords.tolist(),
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str),
                    'wyckoff': wyckoff
                }
            }
            atoms.append(atom)
        
        # 计算密度
        try:
            density = converted_structure.density
        except (AttributeError, Exception):
            # 如果无法获取密度，使用一个合理的默认值
            density = 5.0  # g/cm³，一个合理的默认值
        
        # 构建结构数据
        structure_data = {
            'formula': converted_structure.formula,
            'composition': converted_structure.composition.reduced_formula,
            'lattice': lattice_data,
            'atoms': atoms,
            'num_atoms': len(atoms),
            'is_primitive': is_primitive,
            'density': density,
            'symmetry': {
                'symbol': analyzer.get_space_group_symbol(),
                'number': analyzer.get_space_group_number(),
                'crystal_system': analyzer.get_crystal_system(),
                'point_group': analyzer.get_point_group_symbol()
            }
        }
        
        return structure_data
        
    except Exception as e:
        # 如果处理失败，返回简化的数据
        lattice = structure.lattice
        
        # 计算密度
        try:
            density = structure.density
        except (AttributeError, Exception):
            # 如果无法获取密度，使用一个合理的默认值
            density = 5.0  # g/cm³，一个合理的默认值
            
        return {
            'formula': structure.formula,
            'composition': structure.composition.reduced_formula,
            'lattice': {
                'a': lattice.a,
                'b': lattice.b,
                'c': lattice.c,
                'alpha': lattice.alpha,
                'beta': lattice.beta,
                'gamma': lattice.gamma,
                'matrix': lattice.matrix.tolist(),
                'volume': lattice.volume
            },
            'atoms': [
                {
                    'element': site.species_string,
                    'position': site.coords.tolist(),
                    'frac_coords': site.frac_coords.tolist(),
                    'properties': {
                        'label': site.species_string,
                        'radius': get_atom_radius(site.species_string)
                    }
                } for site in structure.sites
            ],
            'num_atoms': len(structure),
            'is_primitive': cell_type == 'primitive',
            'density': density,
            'symmetry': {
                'symbol': 'Unknown',
                'number': 0,
                'crystal_system': 'Unknown',
                'point_group': 'Unknown'
            }
        }


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