# commands.py:
import click
from flask import Blueprint
from . import db
from .models import User, Material
import csv
import os
import json
from sqlalchemy.exc import SQLAlchemyError

# 独立定义命令蓝图
bp = Blueprint('commands', __name__)

def safe_float(value):
    """安全转换为浮点数"""
    try:
        return float(value) if value not in ('', None) else None
    except (ValueError, TypeError):
        return None

def safe_int(value):
    """安全转换为整数"""
    try:
        return int(value) if value not in ('', None) else None
    except (ValueError, TypeError):
        return None

# app/commands.py
@bp.cli.command()
@click.option('--file', default='materials.csv', help='CSV文件路径')
def import_energy_data(file):
    """批量导入材料数据"""
    try:
        # 使用更高效的读取方式
        with open(file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)  # 一次性读取所有数据

        # 预处理数据并批量验证
        required_fields = ['name', 'status', 'total_energy', 'formation_energy', 'metal_type']
        valid_data = []
        error_log = []

        for idx, row in enumerate(rows, start=2):  # 假设CSV有标题行，从第2行开始
            try:
                # 转换数值类型
                converted = {
                    'name': row['name'],
                    'status': row['status'],
                    'total_energy': float(row['total_energy']),
                    'formation_energy': float(row['formation_energy']),
                    'metal_type': row['metal_type'],
                    'fermi_level': safe_float(row.get('fermi_level')),
                    'vacuum_level': safe_float(row.get('vacuum_level')),
                    'workfunction': safe_float(row.get('workfunction')),
                    'gap': safe_float(row.get('gap')),
                    'vbm_energy': safe_float(row.get('vbm_energy')),
                    'cbm_energy': safe_float(row.get('cbm_energy')),
                    'vbm_coordi': row.get('vbm_coordi'),
                    'cbm_coordi': row.get('cbm_coordi'),
                    'vbm_index': safe_int(row.get('vbm_index')),
                    'cbm_index': safe_int(row.get('cbm_index'))
                }

                # 验证必填字段
                missing = [field for field in required_fields if not converted.get(field)]
                if missing:
                    raise ValueError(f"缺少必填字段: {', '.join(missing)}")

                valid_data.append(converted)

            except (ValueError, KeyError) as e:
                error_log.append(f"第{idx}行错误: {str(e)}")
                continue

        # 批量插入
        if valid_data:
            try:
                # 使用更高效的批量插入方法
                db.session.bulk_insert_mappings(Material, valid_data)
                db.session.commit()
                click.echo(f"成功导入 {len(valid_data)} 条材料数据")
            except SQLAlchemyError as e:
                db.session.rollback()
                click.echo(f"数据库错误: {str(e)}")
        
        # 输出错误日志
        if error_log:
            click.echo("\n遇到以下错误:")
            click.echo("\n".join(error_log))
            click.echo(f"共计 {len(error_log)} 条错误记录")

    except FileNotFoundError:
        click.echo(f"错误：文件 {file} 不存在")

@bp.cli.command()
@click.option('--dir', default='app/static/materials', help='材料数据JSON文件所在目录')
def import_json_data(dir):
    """从JSON文件批量导入材料数据"""
    
    # 设置默认值
    default_data = {
        "name": "No Data",
        "status": "No Data",
        "structure_file": None,
        "total_energy": None,
        "formation_energy": None,
        "fermi_level": None,
        "vacuum_level": None,
        "workfunction": None,
        "metal_type": "No Data",
        "gap": None,
        "vbm_energy": None,
        "cbm_energy": None,
        "vbm_coordi": "No Data",
        "cbm_coordi": "No Data",
        "vbm_index": None,
        "cbm_index": None
    }

    materials_base_dir = os.path.abspath(dir)
    click.echo(f"开始从目录 {materials_base_dir} 导入材料数据...")
    
    # 检查目录是否存在
    if not os.path.exists(materials_base_dir):
        click.echo(f"错误：目录 {materials_base_dir} 不存在")
        return

    # 导入计数
    import_count = 0
    error_count = 0
    
    # 遍历所有材料文件夹
    for material_folder in os.listdir(materials_base_dir):
        # 检查文件夹名称是否符合IMR-格式
        if not material_folder.startswith('IMR-'):
            continue
            
        material_dir = os.path.join(materials_base_dir, material_folder)
        if not os.path.isdir(material_dir):
            continue
        
        material_id = material_folder
        material_path = os.path.join(materials_base_dir, material_folder)
        
        try:
            # 获取文件夹中的所有JSON文件
            json_files = [f for f in os.listdir(material_path) if f.endswith('.json')]
            
            if not json_files:
                click.echo(f"警告：材料 {material_id} 文件夹中没有JSON文件")
                continue
                
            # 使用第一个JSON文件
            json_file_path = os.path.join(material_path, json_files[0])
            
            try:
                # 读取JSON文件内容
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    material_data = json.load(f)
                
                # 设置材料名称为JSON文件名（不包括扩展名）
                material_name = os.path.splitext(json_files[0])[0]
                if 'name' not in material_data or not material_data['name']:
                    material_data['name'] = material_name
                
                # 合并默认值和JSON数据
                for key in default_data:
                    if key not in material_data or material_data[key] is None:
                        material_data[key] = default_data[key]
                
                # 检查材料是否已存在
                id_number = int(material_id.replace('IMR-', ''))
                existing_material = Material.query.filter_by(id=id_number).first()
                
                if existing_material:
                    # 更新现有材料
                    existing_material.name = material_data['name']
                    existing_material.status = material_data['status']
                    existing_material.structure_file = material_data['structure_file']
                    existing_material.total_energy = material_data['total_energy']
                    existing_material.formation_energy = material_data['formation_energy']
                    existing_material.fermi_level = material_data['fermi_level']
                    existing_material.vacuum_level = material_data['vacuum_level']
                    existing_material.workfunction = material_data['workfunction']
                    existing_material.metal_type = material_data['metal_type']
                    existing_material.gap = material_data['gap']
                    existing_material.vbm_energy = material_data['vbm_energy']
                    existing_material.cbm_energy = material_data['cbm_energy']
                    existing_material.vbm_coordi = material_data['vbm_coordi']
                    existing_material.cbm_coordi = material_data['cbm_coordi']
                    existing_material.vbm_index = material_data['vbm_index']
                    existing_material.cbm_index = material_data['cbm_index']
                    click.echo(f"更新材料: {material_id} - {material_data['name']}")
                else:
                    # 创建新材料
                    new_material = Material(
                        id=id_number,
                        name=material_data['name'],
                        status=material_data['status'],
                        structure_file=material_data['structure_file'],
                        total_energy=material_data['total_energy'],
                        formation_energy=material_data['formation_energy'],
                        fermi_level=material_data['fermi_level'],
                        vacuum_level=material_data['vacuum_level'],
                        workfunction=material_data['workfunction'],
                        metal_type=material_data['metal_type'],
                        gap=material_data['gap'],
                        vbm_energy=material_data['vbm_energy'],
                        cbm_energy=material_data['cbm_energy'],
                        vbm_coordi=material_data['vbm_coordi'],
                        cbm_coordi=material_data['cbm_coordi'],
                        vbm_index=material_data['vbm_index'],
                        cbm_index=material_data['cbm_index']
                    )
                    db.session.add(new_material)
                    click.echo(f"添加材料: {material_id} - {material_data['name']}")
                
                import_count += 1
                
            except json.JSONDecodeError:
                click.echo(f"错误：材料 {material_id} 的JSON文件格式不正确")
                error_count += 1
                continue
                
        except Exception as e:
            click.echo(f"处理材料 {material_id} 时出错: {str(e)}")
            error_count += 1
            continue
    
    try:
        db.session.commit()
        click.echo(f"导入完成: 成功导入 {import_count} 个材料, 失败 {error_count} 个")
    except SQLAlchemyError as e:
        db.session.rollback()
        click.echo(f"数据库提交错误: {str(e)}")

@bp.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    """Initialize the database."""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')

@bp.cli.command()
@click.option('--username', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def admin(username, password):
    """Create admin user."""
    db.create_all()
    user = User.query.filter_by(username=username).first()
    if user:
        click.echo('Updating existing user...')
        user.set_password(password)
    else:
        click.echo('Creating new admin user...')
        user = User(username=username, name='NLHE Datebase')
        user.set_password(password)
        db.session.add(user)
    db.session.commit()
    click.echo('Admin account updated successfully.')

@bp.cli.command()
def update_nullable_columns():
    """更新数据表结构，允许字段可为空"""
    try:
        # SQLite不直接支持修改列的nullable属性，需要创建新表并复制数据
        # 为简化操作，我们将使用pragma_table_info来验证字段设置
        
        table_info = db.session.execute("PRAGMA table_info(material)").fetchall()
        column_info = {col[1]: col for col in table_info}
        
        # 检查需要变更的字段是否存在NOT NULL约束(notnull值为1表示NOT NULL)
        changes_needed = []
        for field in ['status', 'total_energy', 'formation_energy']:
            if field in column_info and column_info[field][3] == 1:  # 列存在且有NOT NULL约束
                changes_needed.append(field)
        
        if changes_needed:
            click.echo(f"需要移除的NOT NULL约束字段: {', '.join(changes_needed)}")
            click.echo("由于SQLite限制，需要创建临时表来修改字段。您可以使用以下方法之一:")
            click.echo("1. 使用Flask-Migrate进行数据库迁移: flask db migrate && flask db upgrade")
            click.echo("2. 手动重建数据库: flask initdb --drop (注意: 此操作会删除所有现有数据)")
            click.echo("3. 使用SQLite工具如DB Browser手动修改表结构")
        else:
            click.echo("所有字段已正确设置，无需更改")
            
    except Exception as e:
        click.echo(f"检查数据库结构时出错: {str(e)}")

@bp.cli.command()
@click.option('--drop', is_flag=True, help='Drop and recreate all tables.')
@click.option('--json-dir', default='app/static/materials', help='Directory containing JSON material data files.')
@click.option('--test', is_flag=True, help='Run in test mode with sample CIF files.')
def initialize_database(drop, json_dir, test):
    """Initialize database and import all data from JSON files in one operation."""
    # 初始化数据库
    if drop:
        click.echo('Dropping and recreating all tables...')
        db.drop_all()
    db.create_all()
    click.echo('Database structure initialized.')
    
    import_count = 0
    error_count = 0
    
    # 测试模式：直接从CIF文件创建材料记录
    if test and json_dir == 'app/static/structures':
        click.echo('Test mode enabled: Creating materials from CIF files...')
        
        # 获取结构文件目录
        structures_dir = os.path.abspath(json_dir)
        if not os.path.exists(structures_dir):
            click.echo(f"错误：目录 {structures_dir} 不存在")
            return
            
        # 遍历所有CIF文件
        for file_name in os.listdir(structures_dir):
            if file_name.endswith('.cif'):
                try:
                    # 从文件名提取材料名称
                    material_name = file_name.replace('.cif', '')
                    
                    # 生成一个ID
                    material_id = import_count + 1  # 简单递增
                    
                    # 提取第一部分作为简化名称
                    simple_name = material_name.split('-POSCAR-')[0] if '-POSCAR-' in material_name else material_name
                    
                    # 创建材料记录
                    material = Material(
                        id=material_id,
                        name=simple_name,
                        status="done",
                        structure_file=file_name,
                        total_energy=-20.0 - import_count,  # 示例值
                        formation_energy=-2.0 - (import_count * 0.1),  # 示例值
                        fermi_level=0.5,
                        vacuum_level=4.5,
                        workfunction=5.0,
                        metal_type="metal" if import_count % 2 == 0 else "semiconductor",
                        gap=0.0 if import_count % 2 == 0 else 1.5,
                        vbm_energy=-1.0,
                        cbm_energy=0.5,
                        vbm_coordi="[0, 0, 0]",
                        cbm_coordi="[0.5, 0.5, 0]",
                        vbm_index=10,
                        cbm_index=11
                    )
                    
                    # 添加到数据库并立即提交
                    db.session.add(material)
                    try:
                        db.session.commit()
                        click.echo(f"添加测试材料: {material_id} - {simple_name}")
                        import_count += 1
                    except Exception as e:
                        db.session.rollback()
                        click.echo(f"添加材料 {simple_name} 失败: {str(e)}")
                        error_count += 1
                    
                except Exception as e:
                    click.echo(f"处理测试材料文件 {file_name} 时出错: {str(e)}")
                    error_count += 1
                    continue
        
        click.echo(f"测试数据导入完成: 成功导入 {import_count} 个材料, 失败 {error_count} 个")
        click.echo('Test database initialization completed successfully.')
        return
    
    # 正常模式：从JSON文件导入    
    click.echo('Importing material data from JSON files...')
    
    # 递归扫描所有子目录查找JSON文件
    for root, dirs, files in os.walk(json_dir):
        json_files = [f for f in files if f.endswith('.json')]
        
        if not json_files:
            continue
            
        # 从目录名中提取ID (如 IMR-00000001)
        dir_name = os.path.basename(root)
        material_id = None
        
        if dir_name.startswith('IMR-'):
            try:
                material_id = int(dir_name.replace('IMR-', ''))
            except ValueError:
                # 如果无法提取有效ID，跳过该目录
                click.echo(f"警告: 无法从目录名 {dir_name} 提取有效ID")
                continue
        else:
            # 如果目录名不符合IMR-格式，跳过该目录
            continue
            
        # 处理当前目录中的第一个JSON文件
        file_name = json_files[0]  # 只处理第一个JSON文件
        file_path = os.path.join(root, file_name)
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                material_data = json.load(file)
            
            # 提取完整的结构文件名作为材料名称（如有必要）
            structure_file = material_data.get('structure_file')
            if structure_file and not material_data.get('name'):
                material_data['name'] = structure_file.replace('.cif', '')
            
            # 检查该ID的材料是否已存在
            existing_material = Material.query.filter_by(id=material_id).first()
            if existing_material:
                click.echo(f"更新材料: {material_id} - {material_data['name']}")
                # 更新现有材料的属性
                for key, value in material_data.items():
                    if hasattr(existing_material, key):
                        setattr(existing_material, key, value)
            else:
                # 创建新材料记录
                new_material = Material(
                    id=material_id,
                    name=material_data['name'],
                    status=material_data['status'],
                    structure_file=material_data['structure_file'],
                    total_energy=material_data['total_energy'],
                    formation_energy=material_data['formation_energy'],
                    fermi_level=material_data['fermi_level'],
                    vacuum_level=material_data['vacuum_level'],
                    workfunction=material_data['workfunction'],
                    metal_type=material_data['metal_type'],
                    gap=material_data['gap'],
                    vbm_energy=material_data['vbm_energy'],
                    cbm_energy=material_data['cbm_energy'],
                    vbm_coordi=material_data['vbm_coordi'],
                    cbm_coordi=material_data['cbm_coordi'],
                    vbm_index=material_data['vbm_index'],
                    cbm_index=material_data['cbm_index']
                )
                db.session.add(new_material)
                click.echo(f"添加材料: {material_id} - {material_data['name']}")
            
            import_count += 1
                
        except json.JSONDecodeError:
            click.echo(f"错误：材料 {dir_name} 的JSON文件格式不正确")
            error_count += 1
            continue
                
        except Exception as e:
            click.echo(f"处理材料 {dir_name} 时出错: {str(e)}")
            error_count += 1
            continue
    
    try:
        db.session.commit()
        click.echo(f"数据导入完成: 成功导入 {import_count} 个材料, 失败 {error_count} 个")
    except SQLAlchemyError as e:
        db.session.rollback()
        click.echo(f"数据库提交错误: {str(e)}")
        
    click.echo('Database initialization and data import completed successfully.')