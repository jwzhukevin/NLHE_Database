import click
from flask import Blueprint
from . import db
from .models import User, Movie

# 独立定义命令蓝图
bp = Blueprint('commands', __name__)

@bp.cli.command()
def forge():
    """Generate fake data."""
    db.create_all()
    name = 'NLHE Database'
    movies = [
        {'title': 'My Neighbor Totoro', 'year': '1988'},
        {'title': 'Dead Poets Society', 'year': '1989'},
    ]
    user = User(name=name)
    db.session.add(user)
    for m in movies:
        movie = Movie(title=m['title'], year=m['year'])
        db.session.add(movie)
    db.session.commit()
    click.echo('Done.')

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
        user = User(username=username, name='Admin')
        user.set_password(password)
        db.session.add(user)
    db.session.commit()
    click.echo('Admin account updated successfully.')