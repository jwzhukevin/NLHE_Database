# commands.py: 
import click
from flask import Blueprint, current_app
from . import db
from .models import User, Material, Member
import os
import json
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from .material_importer import extract_chemical_formula_from_cif
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from .band_analyzer import band_analyzer
import functools

# 独立定义命令蓝图 - 用于API路由而非CLI命令
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

# 注册Flask CLI命令
def register_commands(app):
    """注册Flask CLI命令"""
    
    @app.cli.command('user-add')
    @click.argument('email')
    @click.argument('username')
    @click.argument('password')
    @click.argument('role', default='user')
    def user_add(email, username, password, role):
        """添加新用户"""
        db.create_all()
        
        # [Deprecated 20251001] 只读模式：仅允许创建普通用户
        if role != 'user':
            click.echo(f'Invalid role: {role}. Only "user" is allowed in read-only mode.')
            return 1

        # 验证邮箱格式
        email = email.strip().lower()
        if '@' not in email:
            click.echo(f'Invalid email format: {email}')
            return 1

        # 检查邮箱是否已存在
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            click.echo(f'Email {email} is already registered.')
            return 1

        # 检查用户名是否可用
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            click.echo(f'Username {username} is already taken. Please choose another username.')
            return 1
        
        # 创建新用户
        click.echo(f'Creating new {role} account, username: {username} (email: {email})...')
        user = User(username=username, name=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)

        try:
            db.session.commit()
            click.echo(f'User {username} (role: {role}) created successfully.')
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f'Error creating user: {str(e)}')
            return 1
        
        return 0
    
    @app.cli.command('init-users')
    def init_users():
        """DEPRECATED: 此命令已弃用，不再使用users.dat文件"""
        click.echo("❌ 此命令已弃用！")
        click.echo("安全改进：系统不再使用users.dat文件存储用户数据")
        click.echo("请使用 'python user_management.py' 来管理用户")
        return 1

    # 添加其他CLI命令...
    @app.cli.command('import-materials')
    @click.option('--dir', default='app/static/materials', help='材料数据目录路径')
    def import_materials_data(dir):
        """从sc_data/data.json文件批量导入材料数据"""
        materials_base_dir = os.path.abspath(dir)
        click.echo(f"Starting to import material data from directory {materials_base_dir}...")

        if not os.path.exists(materials_base_dir):
            click.echo(f"Error: Directory {materials_base_dir} does not exist")
            return

        import_count = 0
        error_count = 0
        
        for material_folder in os.listdir(materials_base_dir):
            if not material_folder.startswith('IMR-'):
                continue
            
            material_dir = os.path.join(materials_base_dir, material_folder)
            if not os.path.isdir(material_dir):
                continue
            
            material_id = material_folder
            material_path = os.path.join(materials_base_dir, material_folder)
            
            try:
                sc_data_path = os.path.join(material_path, 'sc_data', 'data.json')
                sc_data = None
                if os.path.exists(sc_data_path):
                    try:
                        with open(sc_data_path, 'r', encoding='utf-8') as f:
                            sc_data = json.load(f)
                    except Exception as e:
                        click.echo(f"Error reading sc_data for {material_id}: {str(e)}")
                        sc_data = None
                
                material_name = None
                structure_dir = os.path.join(material_path, 'structure')
                if os.path.exists(structure_dir):
                    cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                    if cif_files:
                        cif_file_path = os.path.join(structure_dir, cif_files[0])
                        material_name = extract_chemical_formula_from_cif(cif_file_path)

                sg_name_from_cif, sg_num_from_cif = 'Unknown', None
                try:
                    if material_name and os.path.exists(structure_dir):
                        cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                        if cif_files:
                            cif_file_path = os.path.join(structure_dir, cif_files[0])
                            _structure = Structure.from_file(cif_file_path)
                            _analyzer = SpacegroupAnalyzer(_structure)
                            sg_name_from_cif = _analyzer.get_space_group_symbol() or 'Unknown'
                            sg_num_from_cif = _analyzer.get_space_group_number() or None
                except Exception as e:
                    click.echo(f"Warning: CIF symmetry parse failed for {material_id}: {e}")

                if not material_name and sc_data and 'formula' in sc_data:
                    material_name = sc_data['formula']
                if not material_name:
                    material_name = f"Material_{material_id}"

                material_data = {
                    'name': material_name,
                    'mp_id': sc_data.get('mp_id', 'Unknown') if sc_data else 'Unknown',
                    'sg_name': sg_name_from_cif,
                    'sg_num': sg_num_from_cif,
                    'fermi_level': sc_data.get('Energy', None) if sc_data else None,
                    'max_sc': sc_data.get('max_sc', None) if sc_data else None,
                    'max_photon_energy': sc_data.get('max_photon_energy', None) if sc_data else None,
                    'max_tensor_type': sc_data.get('max_tensor_type', 'Unknown') if sc_data else 'Unknown'
                }

                id_number = int(material_id.replace('IMR-', ''))
                existing_material = Material.query.get(id_number)

                if existing_material:
                    for key, value in material_data.items():
                        setattr(existing_material, key, value)
                    click.echo(f"Updated material: {material_id} - {material_data['name']}")
                else:
                    new_material = Material(id=id_number, **material_data)
                    db.session.add(new_material)
                    click.echo(f"Added material: {material_id} - {material_data['name']}")
                import_count += 1
            except Exception as e:
                click.echo(f"Error: Failed to process material {material_id}: {str(e)}")
                error_count += 1
                continue

        try:
            db.session.commit()
            click.echo(f"Data import completed: successfully imported {import_count} materials, failed {error_count}")

            click.echo("Starting automatic band structure analysis for imported materials...")
            try:
                materials = Material.query.all()
                results = band_analyzer.batch_analyze(materials)
                analyzed = sum(1 for res in results.values() if res.get('band_gap') is not None)
                failed = len(materials) - analyzed
                db.session.commit()
                click.echo(f"Band analysis completed: {analyzed} analyzed, {failed} failed")
            except Exception as e:
                click.echo(f"Warning: Band analysis failed: {str(e)}")
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f"Database commit error: {str(e)}")

    @app.cli.command()
    @click.option('--drop', is_flag=True, help='删除现有数据库后重新创建')
    def initdb(drop):
        """初始化数据库"""
        if drop:
            db.drop_all()
        db.create_all()
        click.echo('Database initialization completed.')

    @app.cli.command()
    def admin():
        """[Deprecated 20251001] 创建管理员用户命令已禁用（只读模式）"""
        click.echo('❌ This command is disabled. The site runs in read-only mode; admin role is not supported.')
        return 1

    @app.cli.command()
    @click.option('--drop', is_flag=True, help='删除并重新创建所有表')
    @click.option('--json-dir', default='app/static/materials', help='包含JSON材料数据文件的目录')
    @click.option('--test', is_flag=True, help='使用示例CIF文件运行测试模式')
    def initialize_database(drop, json_dir, test):
        """一次性初始化数据库并从JSON文件导入所有数据"""
        if drop:
            click.echo('Dropping and recreating all tables...')
            db.drop_all()
        db.create_all()
        click.echo('Database structure initialization completed.')
        
        import_count = 0
        error_count = 0
        
        if test:
            click.echo('Test mode enabled: creating materials from CIF files...')
            structures_dir = os.path.abspath(json_dir)
            if not os.path.exists(structures_dir):
                click.echo(f"Error: Directory {structures_dir} does not exist")
                return
            
            for file_name in os.listdir(structures_dir):
                if file_name.endswith('.cif'):
                    try:
                        material_id = import_count + 1
                        cif_file_path = os.path.join(structures_dir, file_name)
                        chemical_formula = extract_chemical_formula_from_cif(cif_file_path)
                        material_name = chemical_formula or f"Test Material {material_id}"
                        
                        material = Material(
                            id=material_id, name=material_name, structure_file=file_name,
                            fermi_level=0.5, band_gap=0.0, materials_type="metal"
                        )
                        db.session.add(material)
                        db.session.commit()
                        click.echo(f"Added test material: {material_id} - {material_name}")
                        import_count += 1
                    except Exception as e:
                        db.session.rollback()
                        click.echo(f"Failed to add material {material_name}: {str(e)}")
                        error_count += 1
        else:
            click.echo('Importing material data from JSON files...')
            for root, _, files in os.walk(json_dir):
                for file_name in files:
                    if file_name.endswith('.json'):
                        dir_name = os.path.basename(root)
                        if dir_name.startswith('IMR-'):
                            try:
                                material_id = int(dir_name.replace('IMR-', ''))
                                file_path = os.path.join(root, file_name)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                
                                structure_dir = os.path.join(root, 'structure')
                                material_name = None
                                if os.path.exists(structure_dir):
                                    cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                                    if cif_files:
                                        cif_path = os.path.join(structure_dir, cif_files[0])
                                        material_name = extract_chemical_formula_from_cif(cif_path)
                                if not material_name:
                                    material_name = f"Material_{dir_name}"
                                
                                existing = Material.query.get(material_id)
                                if existing:
                                    click.echo(f"Updating material: {material_id} - {material_name}")
                                    for key, value in data.items():
                                        if hasattr(existing, key):
                                            setattr(existing, key, value)
                                    existing.name = material_name
                                else:
                                    new_material = Material(id=material_id, name=material_name, **data)
                                    db.session.add(new_material)
                                    click.echo(f"Added material: {material_id} - {material_name}")
                                import_count += 1
                            except Exception as e:
                                click.echo(f"Error processing {dir_name}: {e}")
                                error_count += 1
        try:
            db.session.commit()
            click.echo(f"Data import completed: {import_count} imported, {error_count} failed.")

            click.echo("Starting automatic band structure analysis...")
            materials = Material.query.all()
            if materials:
                results = band_analyzer.batch_analyze(materials)
                analyzed = sum(1 for res in results.values() if res.get('band_gap') is not None)
                failed = len(materials) - analyzed
                db.session.commit()
                click.echo(f"Band analysis completed: {analyzed} analyzed, {failed} failed.")
            else:
                click.echo("No materials to analyze.")
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f"Database commit error: {e}")

        click.echo('Database initialization and data import completed successfully.')

    @app.cli.command('check-db-structure')
    def check_db_structure():
        """检查数据库结构与模型的兼容性"""
        from sqlalchemy import inspect
        try:
            with db.engine.begin() as conn:
                inspector = inspect(conn)
                if 'material' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('material')]
                    click.echo(f"Material table fields: {', '.join(columns)}")
                    required = ['id', 'formatted_id', 'name']
                    missing = [f for f in required if f not in columns]
                    if missing:
                        click.echo(f"⚠ Missing fields: {', '.join(missing)}")
                    else:
                        click.echo("✓ Material table structure is normal")
                else:
                    click.echo("⚠ Material table does not exist")
        except Exception as e:
            click.echo(f"Error checking database structure: {e}")

    @app.cli.command('import-member')
    @click.option('--info', required=True, help='成员信息json文件路径')
    @click.option('--photo', required=True, help='成员照片文件路径')
    def import_member(info, photo):
        """导入单个成员信息"""
        try:
            with open(info, 'r', encoding='utf-8') as f:
                data = json.load(f)
            member = Member(
                name=data.get('name'), title=data.get('title'),
                bio=data.get('bio'), achievements='\n'.join(data.get('achievements', [])),
                photo=data.get('photo') or os.path.basename(photo)
            )
            db.session.add(member)
            db.session.commit()
            click.echo(f"Imported member: {member.name}")
        except Exception as e:
            click.echo(f"Error importing member: {e}")

    app.cli.add_command(import_member)