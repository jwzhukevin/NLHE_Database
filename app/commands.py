# commands.py:
import click
from flask import Blueprint
from . import db
from .models import User, Material
import csv
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
    """批量导入能源材料数据"""
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
                click.echo(f"成功插入 {len(valid_data)} 条记录")
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