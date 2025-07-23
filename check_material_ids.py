#!/usr/bin/env python3
"""
检查材料ID和文件夹名称的匹配情况
"""

import os
from app import create_app
from app.models import Material

def main():
    """主函数"""
    print("=== 检查材料ID和文件夹匹配情况 ===\n")
    
    try:
        app = create_app()
        with app.app_context():
            # 查询前10个材料
            materials = Material.query.limit(10).all()
            
            print("数据库中的材料信息：")
            print("-" * 80)
            
            for material in materials:
                print(f"ID: {material.id}")
                print(f"格式化ID: {material.formatted_id}")
                print(f"名称: {material.name}")
                
                # 检查对应的文件夹是否存在
                folder_name = f"IMR-{material.id}"
                folder_path = f"app/static/materials/{folder_name}"
                band_file = f"{folder_path}/band/band.dat"
                
                print(f"预期文件夹: {folder_name}")
                print(f"文件夹存在: {'✅' if os.path.exists(folder_path) else '❌'}")
                print(f"band.dat存在: {'✅' if os.path.exists(band_file) else '❌'}")
                
                # 如果文件夹不存在，检查是否有其他命名方式
                if not os.path.exists(folder_path):
                    # 检查是否有formatted_id对应的文件夹
                    if material.formatted_id:
                        alt_folder = f"app/static/materials/{material.formatted_id}"
                        if os.path.exists(alt_folder):
                            print(f"找到替代文件夹: {material.formatted_id}")
                
                print("-" * 40)
                
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
