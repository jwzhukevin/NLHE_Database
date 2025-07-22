#!/usr/bin/env python3
"""
数据库迁移脚本：更新Material表结构
从原有的JSON数据结构迁移到sc_data/data.json数据结构

变更内容：
1. 添加新字段：mp_id, sg_name, sg_num, max_sc, max_photon_energy, max_tensor_type
2. 删除废弃字段：total_energy, formation_energy, vacuum_level, workfunction, gap, 
   vbm_energy, cbm_energy, vbm_coordi, cbm_coordi, vbm_index, cbm_index
3. 保留字段：metal_type, fermi_level（但数据源改变）

执行方式：
python migrations/update_material_schema.py
"""

import os
import sys
import sqlite3
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Material

def backup_database():
    """创建数据库备份"""
    app = create_app()
    with app.app_context():
        db_path = app.config.get('DATABASE_PATH', 'app.db')
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if os.path.exists(db_path):
            import shutil
            shutil.copy2(db_path, backup_path)
            print(f"Database backed up to: {backup_path}")
            return backup_path
        else:
            print("Database file not found, skipping backup")
            return None

def read_sc_data(material_id):
    """读取材料的sc_data/data.json文件"""
    try:
        app = create_app()
        with app.app_context():
            sc_data_path = os.path.join(
                app.root_path, 'static', 'materials', f'IMR-{material_id}', 'sc_data', 'data.json'
            )
            
            if os.path.exists(sc_data_path):
                with open(sc_data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Warning: sc_data/data.json not found for material IMR-{material_id}")
                return None
    except Exception as e:
        print(f"Error reading sc_data for material {material_id}: {str(e)}")
        return None

def migrate_database():
    """执行数据库迁移"""
    app = create_app()

    with app.app_context():
        print("Starting database migration...")

        # 首先检查数据库是否已初始化
        try:
            # 尝试查询material表
            existing_materials = Material.query.all()
            print(f"Found existing database with {len(existing_materials)} materials")
        except Exception as e:
            print(f"Database not initialized or corrupted: {str(e)}")
            print("Initializing database...")

            # 创建所有表
            db.create_all()
            print("Database tables created successfully")

            # 如果没有现有数据，直接返回，让用户重新导入数据
            print("Database initialized. Please run 'flask import-materials' to import data.")
            return

        # 获取数据库连接
        db_path = app.config.get('DATABASE_PATH', 'app.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # 1. 添加新字段
            print("Adding new columns...")
            new_columns = [
                ("mp_id", "TEXT"),
                ("sg_name", "TEXT"),
                ("sg_num", "INTEGER"),
                ("max_sc", "REAL"),
                ("max_photon_energy", "REAL"),
                ("max_tensor_type", "TEXT")
            ]
            
            for column_name, column_type in new_columns:
                try:
                    cursor.execute(f"ALTER TABLE material ADD COLUMN {column_name} {column_type}")
                    print(f"Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        print(f"Column {column_name} already exists, skipping")
                    else:
                        raise
            
            conn.commit()
            
            # 2. 迁移数据
            print("Migrating data from sc_data/data.json files...")
            materials = Material.query.all()
            
            for material in materials:
                sc_data = read_sc_data(material.id)
                
                if sc_data:
                    # 更新材料数据
                    material.mp_id = sc_data.get('mp_id', 'Unknown')
                    material.sg_name = sc_data.get('sg_name', 'Unknown')
                    material.sg_num = sc_data.get('sg_num', None)
                    material.fermi_level = sc_data.get('Energy', None)  # 费米能级从Energy字段读取
                    material.max_sc = sc_data.get('max_sc', None)
                    material.max_photon_energy = sc_data.get('max_photon_energy', None)
                    material.max_tensor_type = sc_data.get('max_tensor_type', 'Unknown')
                    
                    # 如果材料名称为空或是默认格式，尝试使用formula
                    if not material.name or material.name.startswith('Material_'):
                        if 'formula' in sc_data:
                            material.name = sc_data['formula']
                    
                    print(f"Updated material {material.id}: {material.name}")
                else:
                    # 设置默认值
                    material.mp_id = 'Unknown'
                    material.sg_name = 'Unknown'
                    material.sg_num = None
                    material.max_sc = None
                    material.max_photon_energy = None
                    material.max_tensor_type = 'Unknown'
                    print(f"Set default values for material {material.id}: {material.name}")
            
            db.session.commit()
            
            # 3. 删除废弃字段
            print("Removing deprecated columns...")
            deprecated_columns = [
                'total_energy', 'formation_energy', 'vacuum_level', 'workfunction',
                'gap', 'vbm_energy', 'cbm_energy', 'vbm_coordi', 'cbm_coordi',
                'vbm_index', 'cbm_index'
            ]
            
            # SQLite不支持直接删除列，需要重建表
            print("Recreating table without deprecated columns...")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE material_new (
                    id INTEGER PRIMARY KEY,
                    formatted_id VARCHAR(20) UNIQUE,
                    name VARCHAR(120) NOT NULL,
                    status VARCHAR(20),
                    structure_file VARCHAR(255),
                    properties_json VARCHAR(255),
                    sc_structure_file VARCHAR(255),
                    mp_id TEXT,
                    sg_name TEXT,
                    sg_num INTEGER,
                    fermi_level REAL,
                    metal_type VARCHAR(20),
                    max_sc REAL,
                    max_photon_energy REAL,
                    max_tensor_type TEXT
                )
            ''')
            
            # 复制数据到新表
            cursor.execute('''
                INSERT INTO material_new 
                (id, formatted_id, name, status, structure_file, properties_json, 
                 sc_structure_file, mp_id, sg_name, sg_num, fermi_level, metal_type,
                 max_sc, max_photon_energy, max_tensor_type)
                SELECT id, formatted_id, name, status, structure_file, properties_json,
                       sc_structure_file, mp_id, sg_name, sg_num, fermi_level, metal_type,
                       max_sc, max_photon_energy, max_tensor_type
                FROM material
            ''')
            
            # 删除旧表，重命名新表
            cursor.execute('DROP TABLE material')
            cursor.execute('ALTER TABLE material_new RENAME TO material')
            
            conn.commit()
            print("Migration completed successfully!")
            
        except Exception as e:
            conn.rollback()
            print(f"Migration failed: {str(e)}")
            raise
        finally:
            conn.close()

if __name__ == '__main__':
    print("Material Database Schema Migration")
    print("=" * 50)
    
    # 创建备份
    backup_path = backup_database()
    
    # 执行迁移
    try:
        migrate_database()
        print("\n✅ Migration completed successfully!")
        print("New fields added: mp_id, sg_name, sg_num, max_sc, max_photon_energy, max_tensor_type")
        print("Deprecated fields removed: total_energy, formation_energy, vacuum_level, etc.")
        print("Data migrated from sc_data/data.json files")
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        if backup_path:
            print(f"You can restore from backup: {backup_path}")
        sys.exit(1)
