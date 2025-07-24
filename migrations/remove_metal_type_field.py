#!/usr/bin/env python3
"""
数据库迁移脚本：移除metal_type字段

移除Material模型中的metal_type字段，因为现在材料类型从band.json文件中读取
"""

import os
import sys
import sqlite3
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def remove_metal_type_field():
    """移除metal_type字段"""
    
    # 数据库文件路径
    db_path = 'instance/database.db'
    
    if not os.path.exists(db_path):
        print("❌ 数据库文件不存在，跳过迁移")
        return False
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查metal_type字段是否存在
        cursor.execute("PRAGMA table_info(material)")
        columns = cursor.fetchall()
        
        metal_type_exists = any(col[1] == 'metal_type' for col in columns)
        
        if not metal_type_exists:
            print("✅ metal_type字段不存在，无需迁移")
            conn.close()
            return True
        
        print("🔄 开始移除metal_type字段...")
        
        # 备份当前表数据
        print("📦 备份现有数据...")
        cursor.execute("SELECT * FROM material")
        all_data = cursor.fetchall()
        
        # 获取列名（除了metal_type）
        column_names = [col[1] for col in columns if col[1] != 'metal_type']
        column_definitions = []
        
        for col in columns:
            if col[1] != 'metal_type':
                col_name = col[1]
                col_type = col[2]
                not_null = "NOT NULL" if col[3] else ""
                default_val = f"DEFAULT {col[4]}" if col[4] is not None else ""
                primary_key = "PRIMARY KEY" if col[5] else ""
                
                col_def = f"{col_name} {col_type} {not_null} {default_val} {primary_key}".strip()
                column_definitions.append(col_def)
        
        # 创建新表（不包含metal_type字段）
        print("🔧 创建新表结构...")
        new_table_sql = f"""
        CREATE TABLE material_new (
            {', '.join(column_definitions)}
        )
        """
        
        cursor.execute(new_table_sql)
        
        # 将数据迁移到新表（排除metal_type列）
        print("📋 迁移数据...")
        
        # 找到metal_type字段的索引
        metal_type_index = next(i for i, col in enumerate(columns) if col[1] == 'metal_type')
        
        # 准备插入语句
        placeholders = ', '.join(['?' for _ in column_names])
        insert_sql = f"INSERT INTO material_new ({', '.join(column_names)}) VALUES ({placeholders})"
        
        # 迁移每一行数据（排除metal_type列）
        for row in all_data:
            new_row = list(row)
            new_row.pop(metal_type_index)  # 移除metal_type列的数据
            cursor.execute(insert_sql, new_row)
        
        # 删除旧表，重命名新表
        print("🔄 替换表结构...")
        cursor.execute("DROP TABLE material")
        cursor.execute("ALTER TABLE material_new RENAME TO material")
        
        # 提交更改
        conn.commit()
        
        print(f"✅ 成功移除metal_type字段，迁移了 {len(all_data)} 条记录")
        
        # 验证迁移结果
        cursor.execute("PRAGMA table_info(material)")
        new_columns = cursor.fetchall()
        
        print("📊 新表结构:")
        for col in new_columns:
            print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """主函数"""
    print("🎯 数据库迁移：移除metal_type字段")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = remove_metal_type_field()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 迁移完成！")
        print()
        print("📋 迁移总结:")
        print("✅ 移除了Material模型中的metal_type字段")
        print("✅ 保留了所有其他数据")
        print("✅ 材料类型现在从band.json文件中读取")
    else:
        print("❌ 迁移失败！")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
