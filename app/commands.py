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
            click.echo(f'无效的角色: {role}。必须是 "admin" 或 "user"。')
            return 1
        
        # 验证邮箱格式
        email = email.strip().lower()
        if '@' not in email:
            click.echo(f'无效的邮箱格式: {email}')
            return 1
        
        # 检查邮箱是否已存在
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            click.echo(f'邮箱 {email} 已被注册。')
            return 1
        
        # 检查用户名是否可用
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            click.echo(f'用户名 {username} 已被使用。请选择其他用户名。')
            return 1
        
        # 创建新用户
        click.echo(f'正在创建新的 {role} 账户，用户名: {username} (邮箱: {email})...')
        user = User(username=username, name=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        
        try:
            db.session.commit()
            click.echo(f'用户 {username} (角色: {role}) 创建成功。')
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f'创建用户时出错: {str(e)}')
            return 1
        
        return 0
    
    @app.cli.command('init-users')
    def init_users():
        """从users.dat文件初始化用户"""
        users_file = os.path.join(os.path.dirname(app.root_path), 'app/static/users/users.dat')
        
        # 检查用户数据文件是否存在
        if not os.path.exists(users_file):
            click.echo(f'错误: 未找到用户数据文件 {users_file}')
            return 1
        
        click.echo(f'正在从 {users_file} 初始化用户...')
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
                        click.echo(f'错误: 行格式无效: {line}')
                        continue
                    
                    email, username, password, role = parts[0], parts[1], parts[2], parts[3]
                    
                    # 验证邮箱格式
                    email = email.strip().lower()
                    if '@' not in email:
                        click.echo(f'警告: 邮箱格式无效 "{email}"。跳过此用户。')
                        continue
                    
                    # 验证用户角色
                    if role not in ['admin', 'user']:
                        click.echo(f'警告: 用户 {username} 的角色 "{role}" 无效。设置为 "user"。')
                        role = 'user'
                    
                    # 检查用户是否存在
                    user = User.query.filter_by(email=email).first()
                    if user:
                        # 更新现有用户信息
                        user.username = username
                        user.set_password(password)
                        user.role = role
                        user.name = user.name or username  # 如果name存在则保留，否则使用username
                        click.echo(f'更新用户: {username} ({email}) 角色: {role}')
                    else:
                        # 创建新用户
                        user = User(username=username, name=username, email=email, role=role)
                        user.set_password(password)
                        db.session.add(user)
                        click.echo(f'添加用户: {username} ({email}) 角色: {role}')
                    
                    count += 1
                except Exception as e:
                    click.echo(f'处理行 "{line}" 时出错: {str(e)}')
        
        try:
            db.session.commit()
            click.echo(f'成功处理 {count} 个用户。')
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f'数据库错误: {str(e)}')
            return 1
        
        return 0

    # 添加其他CLI命令...
    @app.cli.command('import-json')
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
                # 首先检查是否有CIF文件并从中读取化学式
                structure_dir = os.path.join(material_path, 'structure')
                cif_file_path = os.path.join(structure_dir, 'structure.cif')
                if not os.path.exists(cif_file_path):
                    # 如果没有structure.cif，查找目录下第一个.cif文件
                    cif_files = [f for f in os.listdir(structure_dir) if f.endswith('.cif')]
                    if cif_files:
                        cif_file_path = os.path.join(structure_dir, cif_files[0])
                    else:
                        cif_file_path = None
                if cif_file_path and os.path.exists(cif_file_path):
                    chemical_formula = extract_chemical_formula_from_cif(cif_file_path)
                    if chemical_formula:
                        default_data['name'] = chemical_formula
                    else:
                        default_data['name'] = f"Material {material_id}"
                else:
                    default_data['name'] = f"Material {material_id}"
                
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
                    
                    # 设置材料名称为从CIF文件中提取的化学式
                    material_data['name'] = default_data['name']
                    
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
                    
                except (json.JSONDecodeError, IOError) as e:
                    click.echo(f"错误：材料 {material_id} 的JSON文件读取失败: {str(e)}")
                    error_count += 1
                    continue
                
            except Exception as e:
                click.echo(f"处理材料 {material_id} 时出错: {str(e)}")
                error_count += 1
                continue
        
        try:
            db.session.commit()
            click.echo(f"数据导入完成: 成功导入 {import_count} 个材料, 失败 {error_count} 个")
        except SQLAlchemyError as e:
            db.session.rollback()
            click.echo(f"数据库提交错误: {str(e)}")

    @app.cli.command()
    @click.option('--drop', is_flag=True, help='删除现有数据库后重新创建')
    def initdb(drop):
        """初始化数据库"""
        if drop:
            db.drop_all()
        db.create_all()
        click.echo('数据库初始化完成。')

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
            click.echo(f'无效的邮箱格式: {email}')
            return 1
        
        # 检查用户是否已存在（通过邮箱或用户名）
        user_by_email = User.query.filter_by(email=email).first()
        user_by_username = User.query.filter_by(username=username).first()
        
        if user_by_email:
            click.echo('更新现有用户...')
            user = user_by_email
            user.username = username
            user.set_password(password)
            
            # 确保用户具有管理员角色
            if user.role != 'admin':
                user.role = 'admin'
                click.echo('用户角色已更新为管理员。')
        elif user_by_username:
            click.echo('更新现有用户并添加邮箱...')
            user = user_by_username
            user.email = email
            user.set_password(password)
            
            # 确保用户具有管理员角色
            if user.role != 'admin':
                user.role = 'admin'
                click.echo('用户角色已更新为管理员。')
        else:
            click.echo('创建新管理员用户...')
            user = User(username=username, name='NLHE Database', email=email, role='admin')
            user.set_password(password)
            db.session.add(user)
        
        try:
            db.session.commit()
            click.echo('管理员账户更新成功。')
            return 0
        except Exception as e:
            db.session.rollback()
            click.echo(f'创建/更新管理员时出错: {str(e)}')
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
            click.echo('删除并重新创建所有表...')
            db.drop_all()
        db.create_all()
        click.echo('数据库结构初始化完成。')
        
        import_count = 0
        error_count = 0
        
        # 测试模式：直接从CIF文件创建材料记录
        if test and json_dir == 'app/static/structures':
            click.echo('测试模式已启用：正在从CIF文件创建材料...')
            
            # 获取结构文件目录
            structures_dir = os.path.abspath(json_dir)
            if not os.path.exists(structures_dir):
                click.echo(f"错误：目录 {structures_dir} 不存在")
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
                            click.echo(f"添加测试材料: {material_id} - {material_name}")
                            import_count += 1
                        except Exception as e:
                            db.session.rollback()
                            click.echo(f"添加材料 {material_name} 失败: {str(e)}")
                            error_count += 1
                        
                    except Exception as e:
                        click.echo(f"处理测试材料文件 {file_name} 时出错: {str(e)}")
                        error_count += 1
                        continue
            
            click.echo(f"测试数据导入完成: 成功导入 {import_count} 个材料, 失败 {error_count} 个")
            click.echo('测试数据库初始化成功完成。')
            return
        
        # 正常模式：从JSON文件导入    
        click.echo('从JSON文件导入材料数据...')
        
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
            
        click.echo('数据库初始化和数据导入成功完成。')

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
            
            click.echo("用户迁移成功完成。")
            return 0
        except Exception as e:
            click.echo(f"迁移过程中出错: {str(e)}")
            return 1

    @app.cli.command('import-member')
    @click.option('--info', required=True, help='成员信息json文件路径')
    @click.option('--photo', required=True, help='成员照片文件路径')
    def import_member(info, photo):
        """导入单个成员信息"""
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
        click.echo(f"导入成员：{member.name}")

    # 注册命令到Flask
    app.cli.add_command(import_member)