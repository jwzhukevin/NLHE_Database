"""
材料数据处理模块：从CIF文件中提取化学式

此模块负责从CIF文件中提取化学式，用于在添加和编辑材料时自动获取材料名称。
如果CIF文件不存在或数据缺失，则返回None。
"""

import os

def extract_chemical_formula_from_cif(cif_file_path):
    """
    从CIF文件中提取化学式作为材料名称
    优先顺序：
    1. data_开头行（如data_TiS2，提取TiS2）
    2. _chemical_formula_structural
    3. _chemical_formula_sum
    4. _chemical_name_systematic
    参数:
        cif_file_path: CIF文件的完整路径
    返回:
        提取到的化学式字符串，若失败则返回None
    """
    try:
        if not os.path.exists(cif_file_path):
            return None
        chemical_name = None
        with open(cif_file_path, 'r') as f:
            cif_content = f.readlines()
            # 1. 优先查找data_开头的行
            for line in cif_content:
                line_strip = line.strip()
                if not line_strip or line_strip.startswith('#'):
                    continue  # 跳过注释和空行
                if line_strip.lower().startswith('data_'):
                    # 提取data_后面的内容
                    data_val = line_strip[5:].strip()
                    if data_val:
                        chemical_name = data_val
                        break
            # 如果没找到，再用原有三种方式
            if not chemical_name:
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
                            break
                    elif '_chemical_name_systematic' in line:
                        parts = line.strip().split()
                        if len(parts) > 1:
                            chemical_name = parts[1].strip("'").strip('"')
                            break
        return chemical_name
    except Exception as e:
        print(f"Error extracting chemical formula from CIF: {str(e)}")
        return None 