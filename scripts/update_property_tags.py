# scripts/update_property_tags.py
# 这个脚本用于遍历所有材料，并根据特定规则更新它们的特殊性质标签（has_sc, has_bcd, has_dw）。

import os
import sys
from sqlalchemy import inspect

# 将项目根目录添加到Python路径中，以便导入app模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Material

def update_sc_tags():
    """根据 max_sc 字段更新 has_sc 标签。"""
    print("开始更新 has_sc 标签...")
    materials_to_update = Material.query.filter(Material.max_sc.isnot(None)).all()
    updated_count = 0
    for material in materials_to_update:
        if not material.has_sc:
            material.has_sc = True
            updated_count += 1
    
    # 将所有 max_sc 为 NULL 的材料的 has_sc 设为 False
    materials_to_reset = Material.query.filter(Material.max_sc.is_(None), Material.has_sc == True).all()
    reset_count = 0
    for material in materials_to_reset:
        material.has_sc = False
        reset_count += 1

    if updated_count > 0 or reset_count > 0:
        db.session.commit()
        print(f"更新了 {updated_count} 个材料的 has_sc 标签为 True。")
        print(f"重置了 {reset_count} 个材料的 has_sc 标签为 False。")
    else:
        print("没有需要更新的 has_sc 标签。")

def update_bcd_tags():
    """根据 'bcd' 文件夹是否存在来更新 has_bcd 标签。"""
    print("\n开始更新 has_bcd 标签...")
    all_materials = Material.query.all()
    updated_count = 0
    
    # 获取项目根目录的绝对路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    materials_base_dir = os.path.join(project_root, 'app', 'static', 'materials')

    for material in all_materials:
        material_dir = os.path.join(materials_base_dir, f'IMR-{material.id}')
        bcd_dir_path = os.path.join(material_dir, 'bcd')
        
        should_have_bcd = os.path.isdir(bcd_dir_path)
        
        if material.has_bcd != should_have_bcd:
            material.has_bcd = should_have_bcd
            updated_count += 1

    if updated_count > 0:
        db.session.commit()
        print(f"更新了 {updated_count} 个材料的 has_bcd 标签状态。")
    else:
        print("没有需要更新的 has_bcd 标签。")

def update_dw_tags():
    """根据 'dw' 文件夹是否存在来更新 has_dw 标签。"""
    print("\n开始更新 has_dw 标签...")
    all_materials = Material.query.all()
    updated_count = 0

    # 获取项目根目录的绝对路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    materials_base_dir = os.path.join(project_root, 'app', 'static', 'materials')

    for material in all_materials:
        material_dir = os.path.join(materials_base_dir, f'IMR-{material.id}')
        dw_dir_path = os.path.join(material_dir, 'dw')
        
        should_have_dw = os.path.isdir(dw_dir_path)
        
        if material.has_dw != should_have_dw:
            material.has_dw = should_have_dw
            updated_count += 1

    if updated_count > 0:
        db.session.commit()
        print(f"更新了 {updated_count} 个材料的 has_dw 标签状态。")
    else:
        print("没有需要更新的 has_dw 标签。")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # 检查 Material 表和所需列是否存在
        inspector = inspect(db.engine)
        if not inspector.has_table(Material.__tablename__):
            print(f"错误：数据库中不存在 '{Material.__tablename__}' 表。")
            sys.exit(1)

        required_columns = ['has_sc', 'has_bcd', 'has_dw', 'max_sc']
        columns = [c['name'] for c in inspector.get_columns(Material.__tablename__)]
        missing_columns = [col for col in required_columns if col not in columns]

        if missing_columns:
            print(f"错误：Material 表中缺少以下列: {', '.join(missing_columns)}")
            print("请先运行 'flask db upgrade' 应用数据库迁移。")
            sys.exit(1)

        update_sc_tags()
        update_bcd_tags()
        update_dw_tags()
        print("\n所有标签更新完成。")
