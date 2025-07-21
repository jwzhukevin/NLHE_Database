# models.py:
# 数据模型定义模块
# 本文件定义了应用中使用的所有数据模型类，包括用户和材料数据结构

# 导入bcrypt密码哈希库（用于安全密码存储）
import bcrypt
# 导入Flask-Login的用户基类（提供用户认证接口）
from flask_login import UserMixin
# 从当前包导入共享的SQLAlchemy实例
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

# 用户模型类（同时继承SQLAlchemy模型和Flask-Login用户接口）
class User(db.Model, UserMixin):
    """
    用户数据模型类

    负责存储用户认证信息和基本资料，集成了Flask-Login接口用于用户会话管理
    """
    # 用户表字段定义（保持与当前数据库结构一致）
    id = db.Column(db.Integer, primary_key=True)  # 主键ID，自动递增
    name = db.Column(db.String(20))               # 用户显示名称（最长20字符）
    username = db.Column(db.String(20))           # 登录用户名
    email = db.Column(db.String(120), unique=True, nullable=False)  # 唯一邮箱（作为唯一标识符）
    password_hash = db.Column(db.String(128))     # 存储加密后的密码哈希值（不直接存储明文密码）
    role = db.Column(db.String(10), default='user')  # 用户角色：admin, user, guest

    # 密码加密方法
    def set_password(self, password):
        """
        设置用户密码（加密存储）
        
        参数:
            password: 明文密码
            
        说明:
            使用bcrypt算法生成带盐的密码哈希，提供防御彩虹表攻击的安全性
        """
        # 使用bcrypt生成带盐哈希：参数为密码字节流和12轮加密盐
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),       # 将字符串密码转为字节
            bcrypt.gensalt(rounds=12)       # 生成加密盐（12轮强度平衡安全与性能）
        ).decode('utf-8')                   # 将字节哈希转为字符串存储

    # 密码验证方法
    def validate_password(self, password):
        """
        验证用户密码是否正确
        
        参数:
            password: 待验证的明文密码
            
        返回:
            布尔值，表示密码是否正确
            
        说明:
            使用bcrypt的恒定时间比较函数，防止时序攻击
        """
        try:
            # 使用bcrypt的恒定时间比较函数（防时序攻击）
            return bcrypt.checkpw(
                password.encode('utf-8'),       # 输入密码转字节
                self.password_hash.encode('utf-8')  # 数据库存储的哈希值转字节
            )
        except Exception:  # 捕获编码错误或空值异常
            return False   # 验证失败时返回False
    
    # 管理员检查方法
    def is_admin(self):
        """检查用户是否为管理员"""
        return self.role == 'admin'
    
    # 注册用户检查方法
    def is_registered_user(self):
        """检查用户是否为注册用户（非游客）"""
        return self.role in ['admin', 'user']


# 材料数据模型类
class Material(db.Model):
    """
    材料数据模型类

    存储材料的结构信息、能量特性、表面特性和能带结构等物理化学属性
    作为应用的核心数据模型，包含了丰富的材料性质字段
    """
    # 材料表字段定义（保持与当前数据库结构一致）
    id = db.Column(db.Integer, primary_key=True)  # 主键ID（用于唯一标识材料）
    formatted_id = db.Column(db.String(20), unique=True)  # 格式化ID（如IMR-00000001）
    name = db.Column(db.String(120), nullable=False)  # 材料名称（必填，允许重复）
    status = db.Column(db.String(20))  # 材料状态（如"实验"或"理论"，指示数据来源）
    structure_file = db.Column(db.String(255))  # 结构文件路径（存储CIF文件的相对路径）
    properties_json = db.Column(db.String(255))  # 材料属性JSON文件路径
    sc_structure_file = db.Column(db.String(255))  # SC结构DAT文件路径
    
    # 能量相关参数（单位：eV，电子伏特）
    total_energy = db.Column(db.Float)        # 总能量（材料的总能量计算值）
    formation_energy = db.Column(db.Float)    # 形成能（材料的形成能，用于评估稳定性）
    
    # 表面特性参数（允许空值，这些值通常用于表面科学和电子学应用）
    fermi_level = db.Column(db.Float)          # 费米能级（eV，决定电子分布）
    vacuum_level = db.Column(db.Float)         # 真空能级（eV，表面势能参考点）
    workfunction = db.Column(db.Float)        # 功函数（eV，电子从材料逸出所需能量）
    
    # 材料类型参数（用于分类和筛选）
    metal_type = db.Column(db.String(20))     # 金属分类（如"过渡金属"、"碱金属"等）
    
    # 能带结构参数（描述材料的电子能带特性）
    gap = db.Column(db.Float)                 # 带隙宽度（eV，半导体或绝缘体的关键参数）
    vbm_energy = db.Column(db.Float)          # 价带顶能量（eV，价带最大值）
    cbm_energy = db.Column(db.Float)          # 导带底能量（eV，导带最小值）
    
    # 坐标参数（字符串存储格式，用于描述布里渊区中的特殊点）
    vbm_coordi = db.Column(db.String(120))    # 价带顶坐标（如"Γ"或"0.5,0.5,0.5"）
    cbm_coordi = db.Column(db.String(120))    # 导带底坐标（描述导带最小值位置）
    
    # 能带索引参数（用于能带数据分析和绘图）
    vbm_index = db.Column(db.Integer)         # 价带顶能带索引（在能带数据中的索引位置）
    cbm_index = db.Column(db.Integer)         # 导带底能带索引（在能带数据中的索引位置）

    # 数据验证方法
    def validate(self):
        """
        验证材料数据的有效性和合理性

        如果数据无效，将抛出ValueError异常

        验证规则:
            1. 名称不能为空
            2. 如果提供了总能量，必须在合理范围内
            3. 如果提供了形成能，必须在合理范围内
        """
        # 验证名称不能为空
        if not self.name:
            raise ValueError("Material name is required")

        # 验证总能量在合理物理范围内（如果有值）
        if self.total_energy is not None and not (-1e6 < self.total_energy < 1e6):
            raise ValueError("Total energy out of valid range")

        # 当存在形成能时验证其范围（防止异常值）
        if self.formation_energy is not None and not (-1e4 < self.formation_energy < 1e4):
            raise ValueError("Formation energy out of valid range")

        # 可扩展其他参数验证逻辑
        # 例如验证带隙、功函数等是否在合理范围内
        # 或检查坐标格式是否正确

# IP封锁模型
class BlockedIP(db.Model):
    """存储被封锁的IP地址
    
    Attributes:
        id: 主键
        ip_address: 被封锁的IP地址
        blocked_at: 封锁时间
        reason: 封锁原因
    """
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)  # IPv6最长45字符
    blocked_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    reason = db.Column(db.String(100), default="Multiple failed login attempts")
    
    def __repr__(self):
        """返回封锁IP的字符串表示
        
        返回:
            字符串，格式为: "<BlockedIP ip_address>"
        """
        return f"<BlockedIP {self.ip_address}>"

# 添加材料创建前的事件监听器，自动设置格式化ID
from sqlalchemy import event

@event.listens_for(Material, 'before_insert')
def set_formatted_id(mapper, connection, target):
    """
    在材料记录插入前自动设置格式化ID

    由于此时还没有实际ID，我们会在after_insert中再设置一次格式化ID
    这里先插入一个占位符
    """
    _ = mapper, connection  # 忽略未使用的参数
    target.formatted_id = 'IMR-PENDING'  # 设置一个临时占位符

@event.listens_for(Material, 'after_insert')
def update_formatted_id(mapper, connection, target):
    """
    在材料记录插入后更新格式化ID

    这时material.id已经生成，可以使用它来构建格式化ID
    """
    _ = mapper  # 忽略未使用的参数
    # 使用原始SQL更新，避免触发额外的事件
    connection.execute(
        Material.__table__.update().
        where(Material.__table__.c.id == target.id).
        values(formatted_id=f"IMR-{target.id:08d}")
    )
    # 更新内存中的对象
    target.formatted_id = f"IMR-{target.id:08d}"

class Member(db.Model):
    """
    研究部成员数据模型
    """
    id = db.Column(db.Integer, primary_key=True)  # 主键
    name = db.Column(db.String(64), nullable=False)  # 姓名
    title = db.Column(db.String(64))  # 职位/头衔
    photo = db.Column(db.String(128))  # 照片文件名
    bio = db.Column(db.Text)  # 简介
    achievements = db.Column(db.Text)  # 成就（可用Markdown格式）

    def __repr__(self):
        return f'<Member {self.name}>'