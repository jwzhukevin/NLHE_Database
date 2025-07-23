#!/usr/bin/env python3
"""
调试能带数据显示问题的脚本
检查可能导致"能带无数据"的各种原因
"""

import os
import sys
from flask import Flask
from app import create_app
from app.models import Material

def check_file_permissions():
    """检查文件权限"""
    print("=== 检查文件权限 ===")
    
    test_files = [
        "app/static/materials/IMR-1/band/band.dat",
        "app/static/materials/IMR-10/band/band.dat",
        "app/static/materials/IMR-2/band/band.dat",
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            # 检查文件权限
            stat_info = os.stat(file_path)
            permissions = oct(stat_info.st_mode)[-3:]
            size = stat_info.st_size
            print(f"✅ {file_path}")
            print(f"   权限: {permissions}, 大小: {size} bytes")
        else:
            print(f"❌ {file_path} - 文件不存在")

def check_url_paths():
    """检查URL路径构建"""
    print("\n=== 检查URL路径构建 ===")
    
    # 模拟JavaScript中的路径构建逻辑
    material_ids = [1, 10, 2]
    
    for material_id in material_ids:
        # 这是JavaScript中使用的路径格式
        js_path = f"/static/materials/IMR-{material_id}/band/band.dat"
        # 对应的实际文件路径
        actual_path = f"app/static/materials/IMR-{material_id}/band/band.dat"
        
        print(f"材料ID: {material_id}")
        print(f"  JS路径: {js_path}")
        print(f"  实际路径: {actual_path}")
        print(f"  文件存在: {'✅' if os.path.exists(actual_path) else '❌'}")

def check_database_materials():
    """检查数据库中的材料数据"""
    print("\n=== 检查数据库中的材料数据 ===")
    
    try:
        app = create_app()
        with app.app_context():
            # 查询前几个材料
            materials = Material.query.limit(5).all()
            
            for material in materials:
                print(f"材料ID: {material.id}")
                print(f"  格式化ID: {material.formatted_id}")
                print(f"  名称: {material.name}")
                print(f"  Band Gap: {material.band_gap}")
                
                # 检查对应的文件是否存在
                if material.formatted_id:
                    if material.formatted_id.startswith('IMR-'):
                        folder_name = f"IMR-{int(material.formatted_id.split('-')[1])}"
                    else:
                        folder_name = material.formatted_id
                    
                    band_file = f"app/static/materials/{folder_name}/band/band.dat"
                    print(f"  预期文件: {band_file}")
                    print(f"  文件存在: {'✅' if os.path.exists(band_file) else '❌'}")
                print()
                
    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")

def check_static_file_serving():
    """检查静态文件服务配置"""
    print("\n=== 检查静态文件服务配置 ===")
    
    try:
        app = create_app()
        print(f"✅ Flask应用创建成功")
        print(f"静态文件夹: {app.static_folder}")
        print(f"静态URL路径: {app.static_url_path}")
        
        # 检查静态文件夹是否存在
        if os.path.exists(app.static_folder):
            print(f"✅ 静态文件夹存在: {app.static_folder}")
        else:
            print(f"❌ 静态文件夹不存在: {app.static_folder}")
            
    except Exception as e:
        print(f"❌ Flask应用创建失败: {e}")

def simulate_js_fetch():
    """模拟JavaScript的fetch请求"""
    print("\n=== 模拟JavaScript fetch请求 ===")
    
    import requests
    
    # 假设服务器运行在localhost:5000
    base_url = "http://localhost:5000"
    
    test_urls = [
        "/static/materials/IMR-1/band/band.dat",
        "/static/materials/IMR-10/band/band.dat",
        "/static/materials/IMR-2/band/band.dat",
    ]
    
    print("注意：此测试需要Flask服务器运行在localhost:5000")
    
    for url in test_urls:
        full_url = base_url + url
        try:
            response = requests.get(full_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {url} - 状态码: {response.status_code}")
                # 检查内容是否正确
                content = response.text
                lines = content.strip().split('\n')
                if len(lines) >= 3:
                    print(f"   内容正常: {len(lines)} 行")
                else:
                    print(f"   ⚠️ 内容可能有问题: 只有 {len(lines)} 行")
            else:
                print(f"❌ {url} - 状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {url} - 请求失败: {e}")

def main():
    """主函数"""
    print("=== 能带数据显示问题调试 ===\n")
    
    check_file_permissions()
    check_url_paths()
    check_database_materials()
    check_static_file_serving()
    simulate_js_fetch()
    
    print("\n=== 调试完成 ===")
    print("\n建议的解决步骤：")
    print("1. 确保Flask服务器正在运行")
    print("2. 检查浏览器开发者工具的Network标签页，查看是否有404错误")
    print("3. 检查浏览器开发者工具的Console标签页，查看JavaScript错误")
    print("4. 确认材料详情页面的material.id与文件夹名称匹配")

if __name__ == "__main__":
    main()
