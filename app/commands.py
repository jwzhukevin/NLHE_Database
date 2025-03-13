# commands.py
import click
from flask import Blueprint
from . import db
from .models import User, Material

# 独立定义命令蓝图
bp = Blueprint('commands', __name__)

# app/commands.py
@bp.cli.command()
def forge():
    """Generate data with required fields"""
    db.create_all()
    
    # 完整填充所有 NOT NULL 字段的样本数据
    materials = [
        {
            'name': 'Bi2Te3',
            'status': 'done',  # 必填字段补充
            'total_energy': -1234.56,
            'formation_energy': -0.78,
            'efermi': 0.45,
            'metal_type': 'semimetallic',  # 假设该字段为必填
            # 其他非空字段补全
            'vacuum_level': 5.2,
            'workfunction': 4.8,
            'gap': 0.15,
            'vbm_energy': -1.2,
            'cbm_energy': 0.9,
            'vbm_coordi': "[0.333, 0.333, 0.000]",
            'cbm_coordi': "[0.000, 0.000, 0.000]",
            'vbm_index': 32,
            'cbm_index': 35
        },
        {
            'name': 'Sb2Te3',
            'status': 'done',
            'total_energy': -1289.01,
            'formation_energy': -0.65,
            'efermi': 0.32,
            'metal_type': 'semimetallic',
            'vacuum_level': 5.1,
            'workfunction': 4.7,
            'gap': 0.18,
            'vbm_energy': -1.3,
            'cbm_energy': 0.8,
            'vbm_coordi': "[0.250, 0.250, 0.000]",
            'cbm_coordi': "[0.000, 0.000, 0.000]",
            'vbm_index': 28,
            'cbm_index': 31
        }
    ]
    
    for material_data in materials:
        # 验证必填字段
        required_fields = ['name', 'status', 'total_energy', 'formation_energy', 'metal_type']
        for field in required_fields:
            if field not in material_data:
                raise ValueError(f"Missing required field: {field}")
        
        material = Material(**material_data)
        db.session.add(material)
    
    db.session.commit()
    click.echo(f'Successfully added {len(materials)} materials with full data')

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