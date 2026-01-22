# chemical_parser.py
# 智能化学式解析器模块
# 用于解析化学式、提取元素信息和实现智能搜索匹配

import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

class ChemicalFormulaParser:
    """
    化学式解析器类
    
    功能:
    1. 解析化学式，提取元素和化学计量比
    2. 支持复杂化学式（如Ca(OH)2, Al2(SO4)3等）
    3. 提供元素组合匹配和相似性分析
    """
    
    def __init__(self):
        # 元素周期表数据（原子序数1-118）
        self.elements = {
            'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
            'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
            'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
            'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
            'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
            'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
            'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
            'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
            'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
            'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm',
            'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds',
            'Rg', 'Cn', 'Nh', 'Fl', 'Mc', 'Lv', 'Ts', 'Og'
        }
        
        # 元素族分类（用于智能搜索）
        self.element_groups = {
            'alkali_metals': {'Li', 'Na', 'K', 'Rb', 'Cs', 'Fr'},
            'alkaline_earth': {'Be', 'Mg', 'Ca', 'Sr', 'Ba', 'Ra'},
            'transition_metals': {
                'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
                'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
                'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg'
            },
            'halogens': {'F', 'Cl', 'Br', 'I', 'At'},
            'noble_gases': {'He', 'Ne', 'Ar', 'Kr', 'Xe', 'Rn', 'Og'},
            'metalloids': {'B', 'Si', 'Ge', 'As', 'Sb', 'Te', 'Po'},
            'lanthanides': {
                'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd',
                'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu'
            },
            'actinides': {
                'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm',
                'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr'
            }
        }
    
    def parse_formula(self, formula: str) -> Dict[str, int]:
        """
        解析化学式，返回元素及其化学计量比
        
        参数:
            formula: 化学式字符串，如 "TiO2", "Ca(OH)2", "Al2(SO4)3"
            
        返回:
            字典，键为元素符号，值为化学计量比
            例如: {"Ti": 1, "O": 2}
        """
        if not formula:
            return {}
            
        # 清理输入：移除空格和特殊字符
        formula = re.sub(r'[^\w\(\)]', '', formula.strip())
        
        try:
            return self._parse_complex_formula(formula)
        except Exception as e:
            # 如果解析失败，尝试简单解析
            return self._parse_simple_formula(formula)
    
    def _parse_complex_formula(self, formula: str) -> Dict[str, int]:
        """解析复杂化学式（支持括号）"""
        element_count = defaultdict(int)
        
        # 处理括号：先展开括号内容
        while '(' in formula:
            # 找到最内层括号
            match = re.search(r'\(([^()]+)\)(\d*)', formula)
            if not match:
                break
                
            inner_formula = match.group(1)
            multiplier = int(match.group(2)) if match.group(2) else 1
            
            # 解析括号内的元素
            inner_elements = self._parse_simple_formula(inner_formula)
            
            # 将括号内容展开
            expanded = ''
            for element, count in inner_elements.items():
                expanded += element + str(count * multiplier)
            
            # 替换原括号部分
            formula = formula[:match.start()] + expanded + formula[match.end():]
        
        # 解析展开后的简单化学式
        return self._parse_simple_formula(formula)
    
    def _parse_simple_formula(self, formula: str) -> Dict[str, int]:
        """解析简单化学式（无括号）"""
        element_count = defaultdict(int)
        
        # 正则表达式匹配元素和数字
        pattern = r'([A-Z][a-z]?)(\d*)'
        matches = re.findall(pattern, formula)
        
        for element, count_str in matches:
            if element in self.elements:
                count = int(count_str) if count_str else 1
                element_count[element] += count
        
        return dict(element_count)
    
    def get_elements_from_formula(self, formula: str) -> Set[str]:
        """从化学式中提取所有元素"""
        parsed = self.parse_formula(formula)
        return set(parsed.keys())
    
    def contains_elements(self, formula: str, target_elements: List[str], 
                         match_type: str = 'any') -> bool:
        """
        检查化学式是否包含指定元素
        
        参数:
            formula: 化学式
            target_elements: 目标元素列表
            match_type: 匹配类型 ('any', 'all', 'exact')
                - 'any': 包含任一元素
                - 'all': 包含所有元素
                - 'exact': 精确匹配（只包含这些元素）
        """
        formula_elements = self.get_elements_from_formula(formula)
        target_set = set(target_elements)
        
        if match_type == 'any':
            return bool(formula_elements & target_set)
        elif match_type == 'all':
            return target_set.issubset(formula_elements)
        elif match_type == 'exact':
            return formula_elements == target_set
        else:
            return False
    
    def calculate_similarity(self, formula1: str, formula2: str) -> float:
        """
        计算两个化学式的相似度
        
        返回:
            0.0-1.0之间的相似度分数
        """
        elements1 = self.get_elements_from_formula(formula1)
        elements2 = self.get_elements_from_formula(formula2)
        
        if not elements1 and not elements2:
            return 1.0
        if not elements1 or not elements2:
            return 0.0
        
        # 计算Jaccard相似度
        intersection = len(elements1 & elements2)
        union = len(elements1 | elements2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_element_group_matches(self, target_elements: List[str]) -> Dict[str, Set[str]]:
        """
        根据元素族找到相关元素
        
        返回:
            字典，键为族名，值为匹配的元素集合
        """
        matches = {}
        target_set = set(target_elements)
        
        for group_name, group_elements in self.element_groups.items():
            if target_set & group_elements:
                matches[group_name] = group_elements
        
        return matches
    
    def suggest_similar_elements(self, elements: List[str]) -> List[str]:
        """
        基于元素族建议相似元素
        """
        suggestions = set()
        
        for element in elements:
            for group_name, group_elements in self.element_groups.items():
                if element in group_elements:
                    suggestions.update(group_elements)
        
        # 移除原始元素
        suggestions -= set(elements)
        return list(suggestions)

# 创建全局解析器实例
chemical_parser = ChemicalFormulaParser()
