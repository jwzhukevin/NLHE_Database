"""
材料数据处理模块：从CIF文件中提取化学式

此模块负责从CIF文件中提取化学式，用于在添加和编辑材料时自动获取材料名称。
如果CIF文件不存在或数据缺失，则返回None。
"""

import os

def extract_chemical_formula_from_cif(cif_file_path):
    """
    从CIF文件中提取化学式作为材料名称
    
    参数:
        cif_file_path: CIF文件的完整路径
    
    返回:
        提取到的化学式字符串，若失败则返回None
    """
    try:
        if not os.path.exists(cif_file_path):
            return None
            
        # 尝试从CIF文件中读取化学式名称
        chemical_name = None
        with open(cif_file_path, 'r') as f:
            cif_content = f.readlines()
            for line in cif_content:
                if '_chemical_formula_structural' in line:
                    # 提取_chemical_formula_structural后的值
                    parts = line.strip().split()
                    if len(parts) > 1:
                        chemical_name = parts[1].strip("'").strip('"')
                        break
                # 尝试读取其他化学式字段
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