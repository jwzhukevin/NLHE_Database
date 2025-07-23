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
from .band_gap_calculator import band_gap_calculator
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
        
        # 验证角色是否有效
        if role not in ['admin', 'user']:
            click.echo(f'Invalid role: {role}. Must be "admin" or "user".')
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
        """从users.dat文件初始化用户"""
        users_file = os.path.join(os.path.dirname(app.root_path), 'app/static/users/users.dat')
        
        # 检查用户数据文件是否存在
        if not os.path.exists(users_file):
            click.echo(f'Error: User data file not found {users_file}')
            return 1

        click.echo(f'Initializing users from {users_file}...')
        count = 0
        
        # 读取并处理用户数据文件
        with open(users_file, 'r') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                try:
                    # 解析用户数据行
                    parts = line.split(':')
                    if len(parts) < 4:
                        click.echo(f'Error: Invalid line format: {line}')
                        continue

                    email, username, password, role = parts[0], parts[1], parts[2], parts[3]

                    # 验证邮箱格式
                    email = email.strip().lower()
                    if '@' not in email:
                        click.echo(f'Warning: Invalid email format "{email}". Skipping this user.')
                        continue

                    # 验证用户角色
                    if role not in ['admin', 'user']:
                        click.echo(f'Warning: Invalid role "{role}" for user {username}. Setting to "user".')
                        role = 'user'
                    
                    # 检查用户是否存在
                    user = User.query.filter_by(email=email).first()
                    if user:
                        # 更新现有用户信息
                        user.username = username
                        user.set_password(password)
                        user.role = role
                        user.name = user.name or username  # 如果name存在则保留，否则使用username
                        click.echo(f'Updated user: {username} ({email}) role: {role}')
                    else:
                        # 创建新用户
                        user = User(username=username, name=username, email=email, role=role)
                        user.set_password(password)
                        db.session.add(user)
                        click.echo(f'Added user: {username} ({email}) role: {role}')

                    count += 1
                except Exception as e:
                    click.echo(f'Error processing line "{line}": {str(e)}')
        
        try:
            db.session.commit()
            click.echo(f'Successfully processed {count} users.')
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f'Database error: {str(e)}')
            return 1
        
        return 0

    # 添加其他CLI命令...
    @app.cli.command('import-materials')
    @click.option('--dir', default='app/static/materials', help='材料数据目录路径')
    def import_materials_data(dir):
        """从sc_data/data.json文件批量导入材料数据"""



        materials_base_dir = os.path.abspath(dir)
        click.echo(f"Starting to import material data from directory {materials_base_dir}...")

        # 检查目录是否存在
        if not os.path.exists(materials_base_dir):
            click.echo(f"Error: Directory {materials_base_dir} does not exist")
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
                # 读取sc_data/data.json文件
                sc_data_path = os.path.join(material_path, 'sc_data', 'data.json')
                sc_data = None

                if os.path.exists(sc_data_path):
                    try:
                        with open(sc_data_path, 'r', encoding='utf-8') as f:
                            sc_data = json.load(f)
                        click.echo(f"Found sc_data for {material_id}")
                    except Exception as e:
                        click.echo(f"Error reading sc_data for {material_id}: {str(e)}")
                        sc_data = None
                else:
                    click.echo(f"Warning: sc_data/data.json not found for {material_id}")

                # 确定材料名称：优先使用CIF文件提取的化学式，其次使用sc_data中的formula
                material_name = None

                # 首先尝试从CIF文件提取化学式
                structure_dir = os.path.join(material_path, 'structure')
                if os.path.exists(structure_dir):
                    cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                    if cif_files:
                        cif_file_path = os.path.join(structure_dir, cif_files[0])
                        chemical_formula = extract_chemical_formula_from_cif(cif_file_path)
                        if chemical_formula:
                            material_name = chemical_formula

                # 如果CIF文件没有提供名称，使用sc_data中的formula
                if not material_name and sc_data and 'formula' in sc_data:
                    material_name = sc_data['formula']

                # 最后的备用名称
                if not material_name:
                    material_name = f"Material_{material_id}"

                # 准备材料数据
                material_data = {
                    'name': material_name,
                    'status': 'done' if sc_data else 'unknown',
                    'structure_file': None,  # 将在后面设置
                    'mp_id': sc_data.get('mp_id', 'Unknown') if sc_data else 'Unknown',
                    'sg_name': sc_data.get('sg_name', 'Unknown') if sc_data else 'Unknown',
                    'sg_num': sc_data.get('sg_num', None) if sc_data else None,
                    'fermi_level': sc_data.get('Energy', None) if sc_data else None,
                    'metal_type': 'Unknown',  # 需要单独确定
                    'max_sc': sc_data.get('max_sc', None) if sc_data else None,
                    'max_photon_energy': sc_data.get('max_photon_energy', None) if sc_data else None,
                    'max_tensor_type': sc_data.get('max_tensor_type', 'Unknown') if sc_data else 'Unknown'
                }

                # 检查材料是否已存在
                id_number = int(material_id.replace('IMR-', ''))
                existing_material = Material.query.filter_by(id=id_number).first()

                if existing_material:
                    # 更新现有材料
                    existing_material.name = material_data['name']
                    existing_material.status = material_data['status']
                    existing_material.mp_id = material_data['mp_id']
                    existing_material.sg_name = material_data['sg_name']
                    existing_material.sg_num = material_data['sg_num']
                    existing_material.fermi_level = material_data['fermi_level']
                    existing_material.metal_type = material_data['metal_type']
                    existing_material.max_sc = material_data['max_sc']
                    existing_material.max_photon_energy = material_data['max_photon_energy']
                    existing_material.max_tensor_type = material_data['max_tensor_type']
                    click.echo(f"Updated material: {material_id} - {material_data['name']}")
                else:
                    # 创建新材料
                    new_material = Material(
                        id=id_number,
                        name=material_data['name'],
                        status=material_data['status'],
                        structure_file=material_data['structure_file'],
                        mp_id=material_data['mp_id'],
                        sg_name=material_data['sg_name'],
                        sg_num=material_data['sg_num'],
                        fermi_level=material_data['fermi_level'],
                        metal_type=material_data['metal_type'],
                        max_sc=material_data['max_sc'],
                        max_photon_energy=material_data['max_photon_energy'],
                        max_tensor_type=material_data['max_tensor_type']
                    )
                    db.session.add(new_material)
                    click.echo(f"Added material: {material_id} - {material_data['name']}")

                import_count += 1

            except Exception as e:
                click.echo(f"Error: Failed to process material {material_id}: {str(e)}")
                error_count += 1
                continue
                
            except Exception as e:
                click.echo(f"Error: Failed to process material {material_id}: {str(e)}")
                error_count += 1
                continue

        try:
            db.session.commit()
            click.echo(f"Data import completed: successfully imported {import_count} materials, failed {error_count}")

            # 自动计算所有导入材料的Band Gap
            click.echo("Starting automatic Band Gap calculation for imported materials...")
            try:
                stats = band_gap_calculator.calculate_all_band_gaps(force_recalculate=False)
                click.echo(f"Band Gap calculation completed: {stats['calculated']} calculated, {stats['cached']} cached, {stats['failed']} failed")
            except Exception as e:
                click.echo(f"Warning: Band Gap calculation failed: {str(e)}")

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
    @click.option('--username', prompt=True)
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def admin(username, email, password):
        """创建管理员用户"""
        db.create_all()
        
        # 验证邮箱格式
        email = email.strip().lower()
        if '@' not in email:
            click.echo(f'Invalid email format: {email}')
            return 1
        
        # 检查用户是否已存在（通过邮箱或用户名）
        user_by_email = User.query.filter_by(email=email).first()
        user_by_username = User.query.filter_by(username=username).first()
        
        if user_by_email:
            click.echo('Updating existing user...')
            user = user_by_email
            user.username = username
            user.set_password(password)

            # 确保用户具有管理员角色
            if user.role != 'admin':
                user.role = 'admin'
                click.echo('User role updated to admin.')
        elif user_by_username:
            click.echo('Updating existing user and adding email...')
            user = user_by_username
            user.email = email
            user.set_password(password)

            # 确保用户具有管理员角色
            if user.role != 'admin':
                user.role = 'admin'
                click.echo('User role updated to admin.')
        else:
            click.echo('Creating new admin user...')
            user = User(username=username, name='NLHE Database', email=email, role='admin')
            user.set_password(password)
            db.session.add(user)
        
        try:
            db.session.commit()
            click.echo('Admin account updated successfully.')
            return 0
        except Exception as e:
            db.session.rollback()
            click.echo(f'Error creating/updating admin: {str(e)}')
            return 1

    @app.cli.command()
    def update_nullable_columns():
        """更新数据表结构，允许字段可为空"""
        try:
            # SQLite不直接支持修改列的nullable属性，需要创建新表并复制数据
            # 为简化操作，我们将使用pragma_table_info来验证字段设置
            
            table_info = db.session.execute(text("PRAGMA table_info(material)")).fetchall()
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

    @app.cli.command()
    @click.option('--drop', is_flag=True, help='删除并重新创建所有表')
    @click.option('--json-dir', default='app/static/materials', help='包含JSON材料数据文件的目录')
    @click.option('--test', is_flag=True, help='使用示例CIF文件运行测试模式')
    def initialize_database(drop, json_dir, test):
        """一次性初始化数据库并从JSON文件导入所有数据"""
        # 初始化数据库
        if drop:
            click.echo('Dropping and recreating all tables...')
            db.drop_all()
        db.create_all()
        click.echo('Database structure initialization completed.')
        
        import_count = 0
        error_count = 0
        
        # 测试模式：直接从CIF文件创建材料记录
        if test and json_dir == 'app/static/structures':
            click.echo('Test mode enabled: creating materials from CIF files...')

            # 获取结构文件目录
            structures_dir = os.path.abspath(json_dir)
            if not os.path.exists(structures_dir):
                click.echo(f"Error: Directory {structures_dir} does not exist")
                return
            
            # 遍历所有CIF文件
            for file_name in os.listdir(structures_dir):
                if file_name.endswith('.cif'):
                    try:
                        # 生成一个ID
                        material_id = import_count + 1  # 简单递增
                        
                        # 从CIF文件中读取化学式作为材料名称
                        cif_file_path = os.path.join(structures_dir, file_name)
                        chemical_formula = extract_chemical_formula_from_cif(cif_file_path)
                        
                        # 如果无法从CIF获取，则使用测试材料名称
                        material_name = chemical_formula if chemical_formula else f"Test Material {material_id}"
                        
                        # 创建材料记录
                        material = Material(
                            id=material_id,
                            name=material_name,
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
                            click.echo(f"Added test material: {material_id} - {material_name}")
                            import_count += 1
                        except Exception as e:
                            db.session.rollback()
                            click.echo(f"Failed to add material {material_name}: {str(e)}")
                            error_count += 1

                    except Exception as e:
                        click.echo(f"Error processing test material file {file_name}: {str(e)}")
                        error_count += 1
                        continue

            click.echo(f"Test data import completed: successfully imported {import_count} materials, failed {error_count}")
            click.echo('Test database initialization completed successfully.')
            return
        
        # 正常模式：从JSON文件导入
        click.echo('Importing material data from JSON files...')
        
        # 递归扫描所有子目录查找JSON文件
        for root, dirs, files in os.walk(json_dir):
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                continue
            
            # 从目录名中提取ID (如 IMR-1)
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
            
            # 检查是否有CIF文件并从中读取化学式
            structure_dir = os.path.join(root, 'structure')
            material_name = None
            if os.path.exists(structure_dir):
                cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                if cif_files:
                    cif_file_path = os.path.join(structure_dir, cif_files[0])
                    chemical_formula = extract_chemical_formula_from_cif(cif_file_path)
                    if chemical_formula:
                        material_name = chemical_formula
            # 如果没有CIF或解析失败，则用Material+ID
            if not material_name:
                material_name = f"Material_{dir_name}"
            
            # 处理当前目录中的第一个JSON文件
            file_name = json_files[0]  # 只处理第一个JSON文件
            file_path = os.path.join(root, file_name)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    material_data = json.load(file)
                
                # 设置材料名称为从CIF文件中读取的化学式或Material+ID
                material_data['name'] = material_name
                
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
                    click.echo(f"Added material: {material_id} - {material_data['name']}")

                import_count += 1

            except json.JSONDecodeError:
                click.echo(f"Error: Incorrect JSON file format for material {dir_name}")
                error_count += 1
                continue

            except Exception as e:
                click.echo(f"Error processing material {dir_name}: {str(e)}")
                error_count += 1
                continue

        try:
            db.session.commit()
            click.echo(f"Data import completed: successfully imported {import_count} materials, failed {error_count}")

            # 自动计算所有导入材料的Band Gap
            click.echo("Starting automatic Band Gap calculation for imported materials...")
            try:
                stats = band_gap_calculator.calculate_all_band_gaps(force_recalculate=False)
                click.echo(f"Band Gap calculation completed: {stats['calculated']} calculated, {stats['cached']} cached, {stats['failed']} failed")
            except Exception as e:
                click.echo(f"Warning: Band Gap calculation failed: {str(e)}")

        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f"Database commit error: {str(e)}")

        click.echo('Database initialization and data import completed successfully.')

    @app.cli.command('migrate-users-email')
    def migrate_users_email():
        """迁移用户表以包含email字段"""
        try:
            # 导入迁移脚本
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(app.root_path), 'migrations'))

            from migrations.add_email_field import migrate_database
            migrate_database()

            click.echo("User migration completed successfully.")
            return 0
        except Exception as e:
            click.echo(f"Error during migration: {str(e)}")
            return 1

    @app.cli.command('check-db-structure')
    def check_db_structure():
        """检查数据库结构与模型的兼容性"""
        from sqlalchemy import inspect, text

        try:
            with db.engine.begin() as conn:
                inspector = inspect(conn)

                # 检查material表
                if 'material' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('material')]
                    click.echo(f"Material table fields: {', '.join(columns)}")

                    # 检查必要字段
                    required_fields = ['id', 'formatted_id', 'name']
                    missing_fields = [field for field in required_fields if field not in columns]
                    if missing_fields:
                        click.echo(f"⚠ Missing fields: {', '.join(missing_fields)}")
                    else:
                        click.echo("✓ Material table structure is normal")
                else:
                    click.echo("⚠ Material table does not exist")

                # 检查user表
                if 'user' in inspector.get_table_names():
                    columns = [col['name'] for col in inspector.get_columns('user')]
                    click.echo(f"User table fields: {', '.join(columns)}")

                    required_fields = ['id', 'username', 'email', 'password_hash']
                    missing_fields = [field for field in required_fields if field not in columns]
                    if missing_fields:
                        click.echo(f"⚠ Missing fields: {', '.join(missing_fields)}")
                    else:
                        click.echo("✓ User table structure is normal")
                else:
                    click.echo("⚠ User table does not exist")

        except Exception as e:
            click.echo(f"Error checking database structure: {str(e)}")
            return 1

    @app.cli.command('import-member')
    @click.option('--info', required=True, help='成员信息json文件路径')
    @click.option('--photo', required=True, help='成员照片文件路径')
    def import_member(info, photo):
        """导入单个成员信息"""
        try:
            with open(info, 'r', encoding='utf-8') as f:
                data = json.load(f)
            member = Member(
                name=data.get('name'),
                title=data.get('title'),
                bio=data.get('bio'),
                achievements='\n'.join(data.get('achievements', [])),
                photo=data.get('photo') or photo.split('/')[-1]
            )
            db.session.add(member)
            db.session.commit()
            click.echo(f"Imported member: {member.name}")
            return 0
        except Exception as e:
            click.echo(f"Error importing member: {str(e)}")
            return 1

    # 注册命令到Flask
    app.cli.add_command(import_member)