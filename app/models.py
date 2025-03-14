# models.py:
import bcrypt
from flask_login import UserMixin
from . import db

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    username = db.Column(db.String(20), unique=True)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def validate_password(self, password):
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                self.password_hash.encode('utf-8')
            )
        except Exception:
            return False

# 保持 User 类不变，完整修改 Material 类
class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    total_energy = db.Column(db.Float, nullable=False)
    formation_energy = db.Column(db.Float, nullable=False)
    fermi_level = db.Column(db.Float)
    vacuum_level = db.Column(db.Float)
    workfunction = db.Column(db.Float)
    metal_type = db.Column(db.String(20))
    gap = db.Column(db.Float)
    vbm_energy = db.Column(db.Float)
    cbm_energy = db.Column(db.Float)
    vbm_coordi = db.Column(db.String(120))
    cbm_coordi = db.Column(db.String(120))
    vbm_index = db.Column(db.Integer)
    cbm_index = db.Column(db.Integer)

    # 新增数据完整性验证方法
    def validate(self):
        if not (-1e6 < self.total_energy < 1e6):
            raise ValueError("Total energy out of valid range")
        if self.formation_energy and not (-1e4 < self.formation_energy < 1e4):
            raise ValueError("Formation energy out of valid range")