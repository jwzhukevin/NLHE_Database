# models.py:
# 导入bcrypt密码哈希库（用于安全密码存储）
import bcrypt
# 导入Flask-Login的用户基类（提供用户认证接口）
from flask_login import UserMixin
# 从当前包导入共享的SQLAlchemy实例
from . import db

# 用户模型类（同时继承SQLAlchemy模型和Flask-Login用户接口）
class User(db.Model, UserMixin):
    # 用户表字段定义
    id = db.Column(db.Integer, primary_key=True)  # 主键ID，自动递增
    name = db.Column(db.String(20))               # 用户显示名称（最长20字符）
    username = db.Column(db.String(20), unique=True)  # 唯一登录用户名（防重复注册）
    password_hash = db.Column(db.String(128))      # 存储加密后的密码哈希值

    # 密码加密方法
    def set_password(self, password):
        # 使用bcrypt生成带盐哈希：参数为密码字节流和12轮加密盐
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),       # 将字符串密码转为字节
            bcrypt.gensalt(rounds=12)       # 生成加密盐（12轮强度平衡安全与性能）
        ).decode('utf-8')                   # 将字节哈希转为字符串存储

    # 密码验证方法
    def validate_password(self, password):
        try:
            # 使用bcrypt的恒定时间比较函数（防时序攻击）
            return bcrypt.checkpw(
                password.encode('utf-8'),       # 输入密码转字节
                self.password_hash.encode('utf-8')  # 数据库存储的哈希值转字节
            )
        except Exception:  # 捕获编码错误或空值异常
            return False   # 验证失败时返回False


# 材料数据模型类
class Material(db.Model):
    # 材料表字段定义
    id = db.Column(db.Integer, primary_key=True)  # 主键ID
    name = db.Column(db.String(120), unique=True, nullable=False)  # 唯一材料名称（必填）
    status = db.Column(db.String(20), nullable=False)  # 材料状态（如实验/理论）
    structure_file = db.Column(db.String(255))  # 结构文件路径
    
    # 能量相关参数（单位：eV）
    total_energy = db.Column(db.Float, nullable=False)        # 总能量（必填）
    formation_energy = db.Column(db.Float, nullable=False)    # 形成能（必填）
    
    # 表面特性参数（允许空值）
    fermi_level = db.Column(db.Float)          # 费米能级（eV）
    vacuum_level = db.Column(db.Float)         # 真空能级（eV）
    workfunction = db.Column(db.Float)        # 功函数（eV）
    
    # 材料类型参数
    metal_type = db.Column(db.String(20))     # 金属分类（如过渡金属）
    
    # 能带结构参数
    gap = db.Column(db.Float)                 # 带隙宽度（eV）
    vbm_energy = db.Column(db.Float)          # 价带顶能量（eV）
    cbm_energy = db.Column(db.Float)          # 导带底能量（eV）
    
    # 坐标参数（字符串存储格式）
    vbm_coordi = db.Column(db.String(120))    # 价带顶坐标（如"x,y,z"）
    cbm_coordi = db.Column(db.String(120))    # 导带底坐标
    
    # 能带索引参数
    vbm_index = db.Column(db.Integer)         # 价带顶能带索引
    cbm_index = db.Column(db.Integer)         # 导带底能带索引

    # 数据验证方法
    def validate(self):
        # 验证总能量在合理物理范围内
        if not (-1e6 < self.total_energy < 1e6):
            # 抛出值错误异常（后续由视图层捕获处理）
            raise ValueError("Total energy out of valid range")
        
        # 当存在形成能时验证其范围
        if self.formation_energy and not (-1e4 < self.formation_energy < 1e4):
            raise ValueError("Formation energy out of valid range")
        # 可扩展其他参数验证逻辑（当前仅示例两个参数）