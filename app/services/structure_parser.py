# structure_parser.py
# 用于解析CIF文件并生成Three.js可用的JSON数据
# 本文件包含处理晶体结构文件的核心功能，包括CIF文件解析、保存、查找以及超晶胞生成
#
# 架构概览:
#   StructureLoader  — 支持缓存、多源输入（文件/字符串/Materials Project ID）
#   StructureValidator — 验证结构有效性（空结构、晶格异常、原子重叠等）
#   StructureConverter — 原胞/传统胞/超晶胞转换
#   BondAnalyzer — 键合信息分析（用于 Three.js 3D 可视化）
#   StructureSerializer — 提取原子/晶格/对称性数据，序列化为 JSON

import os
import json
import glob
import logging
import hashlib
from functools import lru_cache
from typing import Optional, Dict, Any, List, Tuple

from pymatgen.core import Structure
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from flask import current_app

from ..models import Material


# ==============================================================================
# 默认配置常量
# ==============================================================================

DEFAULT_SYMPREC = 0.1          # 对称性容差（Å）
DEFAULT_ANGLE_TOLERANCE = 5    # 角度容差（°）
DEFAULT_DENSITY = 5.0          # 默认密度（g/cm³），当 pymatgen 无法计算时使用
CACHE_MAX_SIZE = 64            # 结构缓存最大条目数
MIN_LATTICE_PARAM = 0.5        # 最小晶格参数（Å），低于此值视为无效
MERGE_SITE_TOL = 0.01          # 合并重复位点的容差（Å）


# ==============================================================================
# (一) 结构加载器 — StructureLoader
# ==============================================================================

class StructureLoader:
    """
    支持缓存和多种输入源的结构加载器。

    使用 LRU 缓存避免重复解析同一 CIF 文件，
    基于文件内容的 MD5 哈希作为缓存键，确保文件变更时自动刷新。
    """

    # 类级别的缓存字典：{file_hash: Structure}
    _cache: Dict[str, Structure] = {}
    _cache_order: List[str] = []

    @classmethod
    def load(cls, source: str, source_type: str = 'file') -> Structure:
        """
        统一结构加载入口，支持多种输入源。

        参数:
            source: 数据源（文件路径 / CIF 字符串 / Materials Project ID）
            source_type: 'file'（默认）| 'string' | 'mp_id'

        返回:
            pymatgen Structure 对象

        异常:
            FileNotFoundError: 文件不存在
            ValueError: 无法识别的 source_type 或解析失败
        """
        if source_type == 'file':
            return cls._load_from_file(source)
        elif source_type == 'string':
            return cls._load_from_string(source)
        elif source_type == 'mp_id':
            return cls._load_from_mp(source)
        else:
            raise ValueError(f"不支持的 source_type: {source_type}，"
                             f"可选值: 'file', 'string', 'mp_id'")

    @classmethod
    def _load_from_file(cls, file_path: str) -> Structure:
        """从文件加载结构，带缓存。"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"结构文件未找到: {file_path}")
        if os.path.getsize(file_path) == 0:
            raise ValueError(f"结构文件为空: {file_path}")

        # 计算文件内容哈希作为缓存键
        file_hash = cls._compute_file_hash(file_path)

        if file_hash in cls._cache:
            return cls._cache[file_hash].copy()

        structure = Structure.from_file(file_path)

        # 维护缓存大小
        cls._cache[file_hash] = structure
        cls._cache_order.append(file_hash)
        if len(cls._cache_order) > CACHE_MAX_SIZE:
            evict_key = cls._cache_order.pop(0)
            cls._cache.pop(evict_key, None)

        return structure.copy()

    @classmethod
    def _load_from_string(cls, cif_string: str) -> Structure:
        """从 CIF 字符串加载结构。"""
        if not cif_string or not cif_string.strip():
            raise ValueError("CIF 字符串内容为空")
        return Structure.from_str(cif_string, fmt='cif')

    @classmethod
    def _load_from_mp(cls, mp_id: str) -> Structure:
        """从 Materials Project 下载结构。"""
        try:
            from mp_api.client import MPRester
            with MPRester() as mpr:
                return mpr.get_structure_by_material_id(mp_id)
        except ImportError:
            raise ImportError(
                "需要安装 mp-api 包才能从 Materials Project 下载结构: "
                "pip install mp-api"
            )
        except Exception as e:
            raise ValueError(f"从 Materials Project 下载结构失败 (ID={mp_id}): {e}")

    @classmethod
    def _compute_file_hash(cls, file_path: str) -> str:
        """计算文件内容的 MD5 哈希。"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def clear_cache(cls):
        """手动清空缓存。"""
        cls._cache.clear()
        cls._cache_order.clear()


# ==============================================================================
# (二) 结构验证器 — StructureValidator
# ==============================================================================

class StructureValidator:
    """
    验证晶体结构的有效性，在转换前后使用。

    检查内容:
    - 结构是否为空（无原子）
    - 晶格参数是否异常（过小）
    - 是否存在重叠原子（距离 < 0.5 Å）
    """

    @staticmethod
    def validate(structure: Structure, label: str = "结构") -> List[str]:
        """
        验证结构有效性，返回警告列表。

        参数:
            structure: 待验证的 pymatgen Structure 对象
            label: 用于日志/错误信息的标签

        返回:
            warnings: 警告信息列表，空列表表示验证通过

        异常:
            ValueError: 当存在严重问题（空结构、晶格参数过小）时抛出
        """
        warnings = []

        # 1. 空结构检查
        if structure.num_sites == 0:
            raise ValueError(f"{label}: 转换后结构为空（无原子位点）")

        # 2. 晶格参数检查
        abc = structure.lattice.abc
        for i, param_name in enumerate(['a', 'b', 'c']):
            if abc[i] < MIN_LATTICE_PARAM:
                raise ValueError(
                    f"{label}: 晶格参数 {param_name}={abc[i]:.4f} Å 过小 "
                    f"(最小值: {MIN_LATTICE_PARAM} Å)"
                )

        # 3. 原子重叠检查（距离 < 0.5 Å 的原子对）
        try:
            dist_matrix = structure.distance_matrix
            import numpy as np
            n = len(structure)
            for i in range(n):
                for j in range(i + 1, n):
                    if dist_matrix[i][j] < 0.5:
                        warnings.append(
                            f"原子 {i} ({structure[i].species_string}) 和 "
                            f"原子 {j} ({structure[j].species_string}) "
                            f"距离过近: {dist_matrix[i][j]:.3f} Å"
                        )
        except Exception:
            warnings.append("无法计算原子间距离矩阵，跳过重叠检查")

        return warnings


# ==============================================================================
# (三) 结构标准化 — standardize_structure
# ==============================================================================

def standardize_structure(structure: Structure) -> Structure:
    """
    标准化结构处理流程：
    1. 排序（按元素序号排列）
    2. 将分数坐标归一化到 [0, 1)
    3. 合并重复位点（距离 < MERGE_SITE_TOL）

    参数:
        structure: 原始 pymatgen Structure 对象

    返回:
        标准化后的 Structure 对象（不修改原结构）
    """
    std = structure.copy()

    # 1. 按元素排序
    std = std.get_sorted_structure()

    # 2. 分数坐标归一化到 [0, 1)
    for site in std:
        site.frac_coords = site.frac_coords % 1.0

    # 3. 合并重复位点
    try:
        std.merge_sites(tol=MERGE_SITE_TOL, mode='average')
    except Exception:
        pass  # 某些情况下 merge_sites 可能失败，保持原状

    return std


# ==============================================================================
# (四) 结构转换器 — StructureConverter
# ==============================================================================

class StructureConverter:
    """
    晶胞转换器，支持原胞/传统胞/超晶胞转换。

    所有转换方法返回转换后的 Structure 对象，
    转换失败时回退到原始结构并记录警告。
    """

    @staticmethod
    def to_primitive(structure: Structure,
                     symprec: float = DEFAULT_SYMPREC,
                     angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE) -> Structure:
        """转换为原胞。"""
        try:
            analyzer = SpacegroupAnalyzer(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )
            primitive = analyzer.find_primitive()
            if primitive and primitive.num_sites > 0:
                return primitive
        except Exception:
            pass
        return structure.copy()

    @staticmethod
    def to_conventional(structure: Structure,
                        symprec: float = DEFAULT_SYMPREC,
                        angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE) -> Structure:
        """转换为传统胞。"""
        try:
            analyzer = SpacegroupAnalyzer(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )
            conventional = analyzer.get_conventional_standard_structure()
            if conventional and conventional.num_sites > 0:
                return conventional
        except Exception:
            pass
        return structure.copy()

    @staticmethod
    def to_supercell(structure: Structure, a: int = 1, b: int = 1, c: int = 1) -> Structure:
        """生成超晶胞。"""
        if not all(isinstance(x, (int, float)) and x > 0 for x in [a, b, c]):
            raise ValueError("超晶胞参数必须为正数")
        supercell = structure.copy()
        supercell.make_supercell([float(a), float(b), float(c)])
        return supercell

    @classmethod
    def convert(cls, structure: Structure,
                cell_type: str = 'primitive',
                symprec: float = DEFAULT_SYMPREC,
                angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE) -> Structure:
        """
        统一转换入口。

        参数:
            structure: 原始结构
            cell_type: 'primitive' 或 'conventional'
            symprec: 对称性容差
            angle_tolerance: 角度容差

        返回:
            转换后的 Structure 对象
        """
        if cell_type == 'primitive':
            return cls.to_primitive(structure, symprec, angle_tolerance)
        elif cell_type == 'conventional':
            return cls.to_conventional(structure, symprec, angle_tolerance)
        else:
            raise ValueError(f"无效的 cell_type: {cell_type}，可选: 'primitive', 'conventional'")


# ==============================================================================
# (五) 键合分析器 — BondAnalyzer
# ==============================================================================

class BondAnalyzer:
    """
    使用 CrystalNN 算法分析晶体结构中的化学键，
    为 Three.js 3D 可视化提供键合数据。
    """

    @staticmethod
    def get_bonds(structure: Structure, max_bonds_per_atom: int = 12) -> List[Dict[str, Any]]:
        """
        计算结构中的化学键信息。

        参数:
            structure: pymatgen Structure 对象
            max_bonds_per_atom: 每个原子的最大键合数（防止过密结构生成过多键）

        返回:
            键合列表，每个键包含:
            - from_idx: 起始原子索引
            - to_idx: 终止原子索引
            - from_element: 起始原子元素
            - to_element: 终止原子元素
            - distance: 键长 (Å)
        """
        try:
            from pymatgen.analysis.local_env import CrystalNN
        except ImportError:
            return []

        bonds = []
        seen_pairs = set()

        try:
            nn = CrystalNN()
            for i in range(len(structure)):
                try:
                    neighbors = nn.get_nn_info(structure, i)
                    for neighbor in neighbors[:max_bonds_per_atom]:
                        j = neighbor['site_index']
                        # 去重：只保留 (min, max) 对
                        pair = (min(i, j), max(i, j))
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            distance = structure.get_distance(i, j)
                            bonds.append({
                                'from_idx': i,
                                'to_idx': j,
                                'from_element': structure[i].species_string,
                                'to_element': structure[j].species_string,
                                'distance': round(distance, 4)
                            })
                except Exception:
                    continue  # 跳过无法分析的原子
        except Exception:
            pass  # CrystalNN 初始化失败时返回空列表

        return bonds


# ==============================================================================
# (六) 结构序列化器 — StructureSerializer
# ==============================================================================

class StructureSerializer:
    """
    将 pymatgen Structure 对象序列化为 JSON 兼容的字典，
    供 Three.js 前端使用。

    核心改进：在转换后的结构上重新创建 SpacegroupAnalyzer，
    确保 Wyckoff 位置与原子索引正确对应。
    """

    @staticmethod
    def extract_lattice(structure: Structure) -> Dict[str, Any]:
        """提取晶格参数。"""
        lattice = structure.lattice
        return {
            'a': lattice.a,
            'b': lattice.b,
            'c': lattice.c,
            'alpha': lattice.alpha,
            'beta': lattice.beta,
            'gamma': lattice.gamma,
            'volume': lattice.volume,
            'matrix': lattice.matrix.tolist()
        }

    @staticmethod
    def extract_symmetry(structure: Structure,
                         symprec: float = DEFAULT_SYMPREC,
                         angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE) -> Dict[str, Any]:
        """
        提取对称性信息。

        关键：使用传入的（已转换的）结构创建 analyzer，
        确保 Wyckoff 位置与该结构的原子索引一致。
        """
        try:
            analyzer = SpacegroupAnalyzer(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )
            return {
                'symbol': analyzer.get_space_group_symbol(),
                'number': analyzer.get_space_group_number(),
                'crystal_system': analyzer.get_crystal_system(),
                'point_group': analyzer.get_point_group_symbol()
            }
        except Exception:
            return {
                'symbol': 'Unknown',
                'number': 0,
                'crystal_system': 'Unknown',
                'point_group': 'Unknown'
            }

    @staticmethod
    def extract_wyckoff(structure: Structure,
                        symprec: float = DEFAULT_SYMPREC,
                        angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE) -> Optional[list]:
        """
        提取 Wyckoff 位置标签。

        **关键修复**：基于已转换后的目标结构创建 SpacegroupAnalyzer，
        而非原始结构，确保 Wyckoff 索引与原子索引一一对应。
        """
        try:
            analyzer = SpacegroupAnalyzer(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )
            dataset = analyzer.get_symmetry_dataset()
            return dataset.get('wyckoffs')
        except Exception:
            return None

    @staticmethod
    def extract_atoms(structure: Structure,
                      wyckoff_sites: Optional[list] = None) -> List[Dict[str, Any]]:
        """提取原子信息列表。"""
        atoms = []
        for i, site in enumerate(structure.sites):
            element_str = site.species_string
            wyckoff = None
            if wyckoff_sites is not None and i < len(wyckoff_sites):
                wyckoff = wyckoff_sites[i]

            atoms.append({
                'element': element_str,
                'position': site.coords.tolist(),
                'frac_coords': site.frac_coords.tolist(),
                'properties': {
                    'label': element_str,
                    'radius': get_atom_radius(element_str),
                    'wyckoff': wyckoff
                }
            })
        return atoms

    @staticmethod
    def get_density(structure: Structure) -> float:
        """安全获取密度。"""
        try:
            return structure.density
        except Exception:
            return DEFAULT_DENSITY

    @classmethod
    def to_dict(cls, structure: Structure,
                symprec: float = DEFAULT_SYMPREC,
                angle_tolerance: float = DEFAULT_ANGLE_TOLERANCE,
                include_bonds: bool = False,
                is_primitive: Optional[bool] = None) -> Dict[str, Any]:
        """
        将结构序列化为完整的字典。

        参数:
            structure: 已转换后的 pymatgen Structure 对象
            symprec: 对称性容差
            angle_tolerance: 角度容差
            include_bonds: 是否包含键合信息
            is_primitive: 是否为原胞（用于标记）

        返回:
            包含所有结构信息的字典
        """
        # 在目标结构上提取 Wyckoff（修复索引不匹配问题）
        wyckoff_sites = cls.extract_wyckoff(structure, symprec, angle_tolerance)

        data = {
            'formula': structure.formula,
            'composition': structure.composition.reduced_formula,
            'lattice': cls.extract_lattice(structure),
            'atoms': cls.extract_atoms(structure, wyckoff_sites),
            'num_atoms': structure.num_sites,
            'density': cls.get_density(structure),
            'symmetry': cls.extract_symmetry(structure, symprec, angle_tolerance),
        }

        if is_primitive is not None:
            data['is_primitive'] = is_primitive

        if include_bonds:
            data['bonds'] = BondAnalyzer.get_bonds(structure)

        return data


# ==============================================================================
# (七) 原子半径数据
# ==============================================================================

# 常见元素的共价半径（单位：Å），用于 Three.js 可视化
_ATOM_RADII = {
    'H': 0.31, 'He': 0.28,
    'Li': 1.28, 'Be': 0.96, 'B': 0.84, 'C': 0.76, 'N': 0.71,
    'O': 0.66, 'F': 0.57, 'Ne': 0.58,
    'Na': 1.66, 'Mg': 1.41, 'Al': 1.21, 'Si': 1.11, 'P': 1.07,
    'S': 1.05, 'Cl': 1.02, 'Ar': 1.06,
    'K': 2.03, 'Ca': 1.76, 'Sc': 1.70, 'Ti': 1.60, 'V': 1.53,
    'Cr': 1.39, 'Mn': 1.39, 'Fe': 1.32, 'Co': 1.26, 'Ni': 1.24,
    'Cu': 1.32, 'Zn': 1.22, 'Ga': 1.22, 'Ge': 1.20, 'As': 1.19,
    'Se': 1.20, 'Br': 1.20, 'Kr': 1.16,
    'Rb': 2.20, 'Sr': 1.95, 'Y': 1.90, 'Zr': 1.75, 'Nb': 1.64,
    'Mo': 1.54, 'Tc': 1.47, 'Ru': 1.46, 'Rh': 1.42, 'Pd': 1.39,
    'Ag': 1.45, 'Cd': 1.44, 'In': 1.42, 'Sn': 1.39, 'Sb': 1.39,
    'Te': 1.38, 'I': 1.39, 'Xe': 1.40,
    'Cs': 2.44, 'Ba': 2.15, 'La': 2.07, 'Ce': 2.04, 'Pr': 2.03,
    'Nd': 2.01, 'Pm': 1.99, 'Sm': 1.98, 'Eu': 1.98, 'Gd': 1.96,
    'Tb': 1.94, 'Dy': 1.92, 'Ho': 1.92, 'Er': 1.89, 'Tm': 1.90,
    'Yb': 1.87, 'Lu': 1.87,
    'Hf': 1.75, 'Ta': 1.70, 'W': 1.62, 'Re': 1.51, 'Os': 1.44,
    'Ir': 1.41, 'Pt': 1.36, 'Au': 1.36, 'Hg': 1.32, 'Tl': 1.45,
    'Pb': 1.46, 'Bi': 1.48, 'Po': 1.40, 'At': 1.50, 'Rn': 1.50,
    'Fr': 2.60, 'Ra': 2.21, 'Ac': 2.15, 'Th': 2.06, 'Pa': 2.00,
    'U': 1.96, 'Np': 1.90, 'Pu': 1.87, 'Am': 1.80, 'Cm': 1.69
}


def get_atom_radius(element: str) -> float:
    """
    返回元素的原子半径（用于 Three.js 可视化）。

    参数:
        element: 元素符号，可能包含电荷标记（如 Li+、O2-、Fe3+）

    返回:
        原子半径（Å），未知元素返回 1.0
    """
    pure_element = ''.join(c for c in element if c.isalpha())
    return _ATOM_RADII.get(pure_element, 1.0)


# ==============================================================================
# (八) CIF 文件中化学式名称提取
# ==============================================================================

def _extract_chemical_name_from_cif(file_path: str) -> Optional[str]:
    """
    从 CIF 文件文本中提取化学式名称。

    优先级: _chemical_formula_structural > _chemical_formula_sum > _chemical_name_systematic
    """
    chemical_name = None
    fallback_name = None
    try:
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                if '_chemical_formula_structural' in line:
                    parts = line.strip().split(None, 1)
                    if len(parts) > 1:
                        chemical_name = parts[1].strip("'\"")
                        break  # 最高优先级，直接返回
                elif '_chemical_formula_sum' in line:
                    parts = line.strip().split(None, 1)
                    if len(parts) > 1:
                        fallback_name = parts[1].strip("'\"")
                elif '_chemical_name_systematic' in line and not fallback_name:
                    parts = line.strip().split(None, 1)
                    if len(parts) > 1:
                        fallback_name = parts[1].strip("'\"")
    except Exception:
        pass
    return chemical_name or fallback_name


# ==============================================================================
# (九) 文件管理公共函数（保持原有接口不变）
# ==============================================================================

def get_material_dir(material_id):
    """
    根据材料 ID 返回材料目录路径（代理至 utils.py 统一实现）。

    注意：此函数保留用于向后兼容，实际逻辑由 app.utils.get_material_dir 提供。
    """
    from ..utils import get_material_dir as _get_material_dir
    return _get_material_dir(material_id)


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

        material_dir = get_material_dir(material_id)
        structure_dir = os.path.join(material_dir, 'structure')
        os.makedirs(structure_dir, exist_ok=True)

        save_filename = filename if filename.lower().endswith('.cif') else filename + ".cif"
        file_path = os.path.join(structure_dir, save_filename)

        with open(file_path, 'wb') as f:
            f.write(file_content)

        # 保存后清除缓存中该文件的条目（如果有）
        StructureLoader.clear_cache()

        relative_path = os.path.join(
            'materials', os.path.basename(material_dir), 'structure', save_filename
        )
        return relative_path

    except Exception as e:
        current_app.logger.error(f"Error saving structure file: {str(e)}")
        return None


def find_structure_file(material_id=None, material_name=None):
    """
    根据材料 ID 查找对应的 CIF 文件。

    参数:
        material_id: 材料 ID
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
            relative_path = os.path.relpath(
                cif_files[0], os.path.join(current_app.root_path, 'static')
            )
            return relative_path
        return None
    except Exception as e:
        current_app.logger.error(f"Error finding structure file: {str(e)}")
        return None


# ==============================================================================
# (十) 核心公共 API（保持原有接口签名完全兼容）
# ==============================================================================

def parse_cif_file(filename=None, material_id=None, material_name=None,
                   cell_type='conventional', symprec=DEFAULT_SYMPREC,
                   angle_tolerance=DEFAULT_ANGLE_TOLERANCE,
                   include_bonds=False):
    """
    使用 pymatgen 解析 CIF 文件，返回结构数据的 JSON 字符串。

    参数:
        filename: CIF 文件相对路径
        material_id: 材料 ID，用于查找文件
        material_name: 材料名称（保留参数）
        cell_type: 晶胞类型，'conventional'（默认）或 'primitive'
        symprec: 对称性容差（默认 0.1）
        angle_tolerance: 角度容差（默认 5°）
        include_bonds: 是否包含键合信息（默认 False）

    返回:
        JSON 字符串：包含原子坐标、晶格参数与对称信息；解析失败返回错误 JSON。
    """
    try:
        # 1. 参数验证和文件查找
        if not filename and not material_id:
            return json.dumps({"error": "No filename or material_id provided"})

        if not filename and material_id:
            filename = find_structure_file(material_id=material_id)
            if not filename:
                return json.dumps({
                    "error": f"No structure file found for material ID: {material_id}"
                })

        # 2. 构建文件路径
        file_path = os.path.join(current_app.root_path, 'static', filename)

        # 3. 从 CIF 文件提取化学式名称
        chemical_name = _extract_chemical_name_from_cif(file_path)

        # 4. 加载结构（带缓存）
        try:
            structure = StructureLoader.load(file_path, source_type='file')
        except (FileNotFoundError, ValueError) as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": f"Error loading structure from file: {str(e)}"})

        # 5. 标准化结构
        structure = standardize_structure(structure)

        # 6. 转换晶胞
        try:
            converted = StructureConverter.convert(
                structure, cell_type=cell_type,
                symprec=symprec, angle_tolerance=angle_tolerance
            )
        except ValueError as e:
            return json.dumps({"error": str(e)})

        # 7. 验证转换后的结构
        try:
            warnings = StructureValidator.validate(converted, label=f"材料 {material_id}")
            if warnings:
                current_app.logger.warning(
                    f"Structure warnings for material {material_id}: {warnings}"
                )
        except ValueError as e:
            return json.dumps({"error": str(e)})

        # 8. 序列化（Wyckoff 索引基于 converted 结构，不再错位）
        structure_data = StructureSerializer.to_dict(
            converted,
            symprec=symprec,
            angle_tolerance=angle_tolerance,
            include_bonds=include_bonds
        )

        # 9. 补充额外字段
        structure_data['id'] = material_id
        composition_name = converted.composition.reduced_formula
        if chemical_name:
            structure_data['formula'] = chemical_name
        # composition 保持 pymatgen 计算的值

        return json.dumps(structure_data)

    except Exception as e:
        return json.dumps({"error": str(e)})


def _process_structure(structure, cell_type='primitive',
                       symprec=DEFAULT_SYMPREC, angle_tolerance=DEFAULT_ANGLE_TOLERANCE,
                       include_bonds=False):
    """
    处理晶体结构，转换为指定类型的晶胞并提取结构数据。

    参数:
        structure: pymatgen Structure 对象
        cell_type: 晶胞类型，'primitive' 或 'conventional'
        symprec: 对称性容差
        angle_tolerance: 角度容差
        include_bonds: 是否包含键合信息

    返回:
        转换后的结构数据字典
    """
    try:
        # 1. 标准化
        structure = standardize_structure(structure)

        # 2. 转换
        converted = StructureConverter.convert(
            structure, cell_type=cell_type,
            symprec=symprec, angle_tolerance=angle_tolerance
        )

        # 3. 验证
        try:
            warnings = StructureValidator.validate(converted)
            if warnings:
                current_app.logger.warning(f"Structure validation warnings: {warnings}")
        except ValueError as e:
            current_app.logger.error(f"Structure validation failed: {e}")
            # 回退到原始结构
            converted = structure

        # 4. 序列化（Wyckoff 基于 converted 结构，保证索引正确）
        is_primitive = (cell_type == 'primitive')
        return StructureSerializer.to_dict(
            converted,
            symprec=symprec,
            angle_tolerance=angle_tolerance,
            include_bonds=include_bonds,
            is_primitive=is_primitive
        )

    except Exception as e:
        # 回退：返回原始结构的简化数据
        current_app.logger.error(f"_process_structure failed: {e}")
        return StructureSerializer.to_dict(
            structure,
            symprec=symprec,
            angle_tolerance=angle_tolerance,
            is_primitive=(cell_type == 'primitive')
        )


def generate_supercell(file_path, a=1, b=1, c=1, cell_type='primitive',
                       symprec=DEFAULT_SYMPREC, angle_tolerance=DEFAULT_ANGLE_TOLERANCE):
    """
    生成超晶胞结构并返回 JSON 数据。

    参数:
        file_path: CIF 文件路径
        a, b, c: 沿 a, b, c 方向的扩展倍数（默认 1）
        cell_type: 基础晶胞类型，'primitive' 或 'conventional'
        symprec: 对称性容差
        angle_tolerance: 角度容差

    返回:
        包含超晶胞结构的 JSON 字符串
    """
    try:
        # 参数验证
        if not all(isinstance(x, (int, float)) and x > 0 for x in [a, b, c]):
            return json.dumps({"error": "Supercell parameters must be positive numbers"})

        if cell_type not in ['primitive', 'conventional']:
            return json.dumps({"error": "Cell type must be either 'primitive' or 'conventional'"})

        # 加载结构（带缓存）
        try:
            structure = StructureLoader.load(file_path, source_type='file')
        except (FileNotFoundError, ValueError) as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": f"Error loading structure file: {str(e)}"})

        # 转换晶胞类型
        if cell_type == 'conventional':
            structure = StructureConverter.to_conventional(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )

        # 生成超晶胞
        try:
            supercell = StructureConverter.to_supercell(structure, a=a, b=b, c=c)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        # 提取数据
        lattice_data = StructureSerializer.extract_lattice(supercell)
        atoms = StructureSerializer.extract_atoms(supercell)

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


def get_cif_data(file_path, a=1, b=1, c=1, cell_type='primitive',
                 symprec=DEFAULT_SYMPREC, angle_tolerance=DEFAULT_ANGLE_TOLERANCE):
    """
    生成超晶胞结构的 CIF 数据，用于文件下载。

    参数:
        file_path: CIF 文件路径
        a, b, c: 扩展倍数
        cell_type: 'primitive' 或 'conventional'
        symprec: 对称性容差
        angle_tolerance: 角度容差

    返回:
        CIF 文件内容字符串

    异常:
        FileNotFoundError / Exception
    """
    try:
        # 加载结构（带缓存）
        structure = StructureLoader.load(file_path, source_type='file')

        # 转换晶胞类型
        if cell_type == 'conventional':
            structure = StructureConverter.to_conventional(
                structure, symprec=symprec, angle_tolerance=angle_tolerance
            )

        # 生成超晶胞
        supercell = StructureConverter.to_supercell(structure, a=a, b=b, c=c)

        # 生成 CIF
        cif_writer = CifWriter(supercell)
        return cif_writer.write_string()

    except FileNotFoundError:
        raise
    except Exception as e:
        error_msg = f"Error generating CIF data: {str(e)}"
        current_app.logger.error(error_msg)
        raise Exception(error_msg)


# ==============================================================================
# (十一) 便捷函数（保持原有接口）
# ==============================================================================

def generate_primitive_cell(file_path):
    """
    生成晶体结构的原胞。

    参数:
        file_path: CIF 文件路径

    返回:
        原胞结构的 JSON 字符串
    """
    try:
        structure = StructureLoader.load(file_path, source_type='file')
        structure_data = _process_structure(structure, cell_type='primitive')
        return json.dumps(structure_data)
    except (FileNotFoundError, ValueError) as e:
        error_msg = f"Error generating primitive cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error generating primitive cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})


def generate_conventional_cell(file_path):
    """
    生成晶体结构的常规胞（传统胞）。

    参数:
        file_path: CIF 文件路径

    返回:
        常规胞结构的 JSON 字符串
    """
    try:
        structure = StructureLoader.load(file_path, source_type='file')
        structure_data = _process_structure(structure, cell_type='conventional')
        return json.dumps(structure_data)
    except (FileNotFoundError, ValueError) as e:
        error_msg = f"Error generating conventional cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Error generating conventional cell: {str(e)}"
        current_app.logger.error(error_msg)
        return json.dumps({"error": error_msg})
