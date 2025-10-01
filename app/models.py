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

    # 登录记录字段
    last_login_ip = db.Column(db.String(45))  # 最后登录IP地址（支持IPv6）
    last_login_time = db.Column(db.DateTime)  # 最后登录时间

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

    def check_password_strength(self, password):
        """检查密码强度"""
        from .security_utils import validate_password_strength
        return validate_password_strength(password)
    
    # 管理员检查方法
    def is_admin(self):
        """检查用户是否为管理员

        [Deprecated 20251001] 取消管理员机制：所有用户均视为非管理员。
        无论数据库中角色字段为何值，均返回 False。
        """
        return False
    
    # 注册用户检查方法
    def is_registered_user(self):
        """检查用户是否为注册用户（非游客）"""
        return self.role in ['admin', 'user']


# 材料数据模型类
class Material(db.Model):
    """
    材料数据模型类

    存储材料的结构信息、Materials Project信息、空间群信息和Shift Current特性
    数据主要来源于sc_data/data.json文件
    """
    # 基本字段定义
    id = db.Column(db.Integer, primary_key=True)  # 主键ID（用于唯一标识材料）
    formatted_id = db.Column(db.String(20), unique=True)  # 格式化ID（如IMR-00000001）
    name = db.Column(db.String(120), nullable=False)  # 材料名称（从CIF文件提取，formula作为备用）
    # [Deprecated 20250822] 旧逻辑：status 字段已移除
    structure_file = db.Column(db.String(255))  # 结构文件路径（存储CIF文件的相对路径）
    properties_json = db.Column(db.String(255))  # 材料属性JSON文件路径（保留用于向后兼容）
    sc_structure_file = db.Column(db.String(255))  # SC结构DAT文件路径

    # Materials Project相关信息（来自sc_data/data.json）
    mp_id = db.Column(db.String(20))  # Materials Project ID（如mp-19）

    # 空间群信息（来自sc_data/data.json）
    sg_name = db.Column(db.String(50))  # 空间群名称（如P3_121）
    sg_num = db.Column(db.Integer)  # 空间群号（如152）

    # 能量参数（来自sc_data/data.json）
    fermi_level = db.Column(db.Float)  # 费米能级（eV，从Energy字段读取）

    # 材料类型参数已移除 - 现在从band.json文件中读取

    # Shift Current特性参数（来自sc_data/data.json）
    max_sc = db.Column(db.Float)  # 最大Shift Current值（uA/V^2）
    max_photon_energy = db.Column(db.Float)  # 最大光子能量（eV）
    max_tensor_type = db.Column(db.String(10))  # 最大张量类型（如yyy、xxx等）

    # 电子性质参数
    band_gap = db.Column(db.Float)  # 带隙（eV，从能带分析计算得出）
    materials_type = db.Column(db.String(20))  # 材料类型（metal/semimetal/semiconductor/insulator/unknown）

    # 数据验证方法
    def validate(self):
        """
        验证材料数据的有效性和合理性

        如果数据无效，将抛出ValueError异常

        验证规则:
            1. 名称不能为空
            2. 如果提供了费米能级，必须在合理范围内
            3. 如果提供了空间群号，必须在有效范围内
            4. 如果提供了Shift Current参数，必须在合理范围内
        """
        # 验证名称不能为空
        if not self.name:
            raise ValueError("Material name is required")

        # 验证费米能级在合理物理范围内（如果有值）
        if self.fermi_level is not None and not (-100 < self.fermi_level < 100):
            raise ValueError("Fermi level out of valid range")

        # 验证空间群号在有效范围内（1-230）
        if self.sg_num is not None and not (1 <= self.sg_num <= 230):
            raise ValueError("Space group number must be between 1 and 230")

        # 验证Shift Current参数范围
        if self.max_sc is not None and self.max_sc < 0:
            raise ValueError("Max SC value cannot be negative")

        if self.max_photon_energy is not None and self.max_photon_energy < 0:
            raise ValueError("Max photon energy cannot be negative")

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

    说明：全局统一命名规范为 IMR-{id}（不补零）。
    与 app/__init__.py 中的初始化命令保持一致，避免 ID 文本出现多种格式，
    便于日志、路径与前端展示的一致性与可读性。
    """
    _ = mapper  # 忽略未使用的参数
    # 使用原始SQL更新，避免触发额外的事件
    connection.execute(
        Material.__table__.update().
        where(Material.__table__.c.id == target.id).
        values(formatted_id=f"IMR-{target.id}")
    )
    # 更新内存中的对象
    target.formatted_id = f"IMR-{target.id}"

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