#!/usr/bin/env python3
"""
测试能带数据解析的脚本
用于调试为什么有些材料的band.dat文件存在但界面显示"能带无数据"
"""

import os
import sys

def test_band_file_parsing(file_path):
    """测试能带文件解析"""
    print(f"测试文件: {file_path}")
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"✅ 文件存在")
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        print(f"✅ 文件可读，共 {len(lines)} 行")
        
        if len(lines) < 3:
            print(f"❌ 文件格式错误：至少需要3行，实际只有 {len(lines)} 行")
            return False
        
        # 解析第一行：高对称点标签
        k_labels = lines[0].strip().split()
        print(f"✅ 高对称点标签 ({len(k_labels)}个): {k_labels}")
        
        # 解析第二行：高对称点位置
        try:
            k_positions = list(map(float, lines[1].strip().split()))
            print(f"✅ 高对称点位置 ({len(k_positions)}个): {k_positions[:5]}..." if len(k_positions) > 5 else f"✅ 高对称点位置: {k_positions}")
        except ValueError as e:
            print(f"❌ 第二行解析失败: {e}")
            return False
        
        # 解析数据行
        kpoints = []
        bands = []
        
        for i in range(2, min(len(lines), 7)):  # 只检查前5行数据
            line = lines[i].strip()
            if not line:
                continue
                
            try:
                values = list(map(float, line.split()))
                if len(values) < 2:
                    print(f"❌ 第{i+1}行数据不足: {len(values)} 个值")
                    continue
                    
                kpoints.append(values[0])
                
                # 初始化能带数组
                if not bands:
                    num_bands = len(values) - 1
                    bands = [[] for _ in range(num_bands)]
                    print(f"✅ 检测到 {num_bands} 条能带")
                
                # 添加能带数据
                for j in range(1, len(values)):
                    if j-1 < len(bands):
                        bands[j-1].append(values[j])
                        
            except ValueError as e:
                print(f"❌ 第{i+1}行解析失败: {e}")
                continue
        
        print(f"✅ 成功解析 {len(kpoints)} 个k点")
        print(f"✅ 每条能带有 {len(bands[0]) if bands else 0} 个数据点")
        
        # 检查数据完整性
        if not kpoints:
            print("❌ 没有k点数据")
            return False
        
        if not bands:
            print("❌ 没有能带数据")
            return False
            
        if len(k_labels) == 0:
            print("❌ 没有高对称点标签")
            return False
            
        if len(k_positions) == 0:
            print("❌ 没有高对称点位置")
            return False
        
        print("✅ 所有数据验证通过")
        return True
        
    except Exception as e:
        print(f"❌ 文件读取或解析出错: {e}")
        return False

def main():
    """主函数"""
    print("=== 能带数据文件解析测试 ===\n")
    
    # 测试几个材料的band.dat文件
    test_files = [
        "app/static/materials/IMR-1/band/band.dat",
        "app/static/materials/IMR-10/band/band.dat",
        "app/static/materials/IMR-2/band/band.dat",
    ]
    
    for file_path in test_files:
        print(f"\n{'='*50}")
        result = test_band_file_parsing(file_path)
        print(f"结果: {'通过' if result else '失败'}")
    
    print(f"\n{'='*50}")
    print("测试完成")

if __name__ == "__main__":
    main()
