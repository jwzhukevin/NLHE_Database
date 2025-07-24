#!/usr/bin/env python3
"""
用户管理工具

目的：安全地管理NLHE数据库系统的用户
功能：
1. 添加新用户
2. 查看所有用户
3. 修改用户信息
4. 删除用户
5. 重置用户密码

使用方法：python user_management.py
"""

import os
import sys
import getpass
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import User
from app.security_utils import validate_password_strength

def add_user():
    """添加新用户"""
    print("\n➕ 添加新用户")
    print("-" * 30)
    
    # 获取用户信息
    email = input("邮箱地址: ").strip()
    if not email:
        print("❌ 邮箱地址不能为空")
        return
    
    username = input("用户名: ").strip()
    if not username:
        print("❌ 用户名不能为空")
        return
    
    # 选择角色
    print("\n可用角色:")
    print("1. admin - 管理员（完全访问权限）")
    print("2. user - 普通用户（查看和编辑权限）")
    print("3. guest - 访客（只读权限）")
    
    role_choice = input("选择角色 (1-3): ").strip()
    role_map = {'1': 'admin', '2': 'user', '3': 'guest'}
    
    if role_choice not in role_map:
        print("❌ 无效的角色选择")
        return
    
    role = role_map[role_choice]
    
    # 获取密码
    while True:
        password = getpass.getpass("密码: ")
        if not password:
            print("❌ 密码不能为空")
            continue
        
        # 验证密码强度
        is_strong, message = validate_password_strength(password)
        if not is_strong:
            print(f"❌ {message}")
            continue
        
        confirm_password = getpass.getpass("确认密码: ")
        if password != confirm_password:
            print("❌ 两次输入的密码不一致")
            continue
        
        break
    
    # 检查用户是否已存在
    app = create_app()
    with app.app_context():
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"❌ 邮箱 {email} 已被使用")
            return
        
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            print(f"❌ 用户名 {username} 已被使用")
            return
        
        # 创建新用户
        try:
            user = User(
                email=email,
                username=username,
                role=role
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            print(f"\n✅ 用户创建成功！")
            print(f"   邮箱: {email}")
            print(f"   用户名: {username}")
            print(f"   角色: {role}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 创建用户失败: {e}")

def list_users():
    """查看所有用户"""
    print("\n👥 用户列表")
    print("-" * 50)
    
    app = create_app()
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("没有找到用户")
            return
        
        print(f"{'ID':<5} {'邮箱':<25} {'用户名':<15} {'角色':<10}")
        print("-" * 50)
        
        for user in users:
            print(f"{user.id:<5} {user.email:<25} {user.username:<15} {user.role:<10}")
        
        print(f"\n总计: {len(users)} 个用户")

def modify_user():
    """修改用户信息"""
    print("\n✏️  修改用户信息")
    print("-" * 30)
    
    app = create_app()
    with app.app_context():
        # 显示用户列表
        users = User.query.all()
        if not users:
            print("没有找到用户")
            return
        
        print("选择要修改的用户:")
        for i, user in enumerate(users, 1):
            print(f"{i}. {user.email} ({user.username}) - {user.role}")
        
        try:
            choice = int(input("\n输入用户编号: ")) - 1
            if choice < 0 or choice >= len(users):
                print("❌ 无效的用户编号")
                return
            
            user = users[choice]
            print(f"\n修改用户: {user.email}")
            
            # 修改用户名
            new_username = input(f"新用户名 (当前: {user.username}, 回车跳过): ").strip()
            if new_username:
                # 检查用户名是否已被使用
                existing = User.query.filter(User.username == new_username, User.id != user.id).first()
                if existing:
                    print(f"❌ 用户名 {new_username} 已被使用")
                    return
                user.username = new_username
            
            # 修改角色
            print(f"\n当前角色: {user.role}")
            print("1. admin - 管理员")
            print("2. user - 普通用户") 
            print("3. guest - 访客")
            role_choice = input("新角色 (1-3, 回车跳过): ").strip()
            
            if role_choice:
                role_map = {'1': 'admin', '2': 'user', '3': 'guest'}
                if role_choice in role_map:
                    user.role = role_map[role_choice]
                else:
                    print("❌ 无效的角色选择")
                    return
            
            db.session.commit()
            print("✅ 用户信息修改成功")
            
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            db.session.rollback()
            print(f"❌ 修改失败: {e}")

def reset_password():
    """重置用户密码"""
    print("\n🔑 重置用户密码")
    print("-" * 30)
    
    app = create_app()
    with app.app_context():
        # 显示用户列表
        users = User.query.all()
        if not users:
            print("没有找到用户")
            return
        
        print("选择要重置密码的用户:")
        for i, user in enumerate(users, 1):
            print(f"{i}. {user.email} ({user.username})")
        
        try:
            choice = int(input("\n输入用户编号: ")) - 1
            if choice < 0 or choice >= len(users):
                print("❌ 无效的用户编号")
                return
            
            user = users[choice]
            print(f"\n重置用户密码: {user.email}")
            
            # 获取新密码
            while True:
                password = getpass.getpass("新密码: ")
                if not password:
                    print("❌ 密码不能为空")
                    continue
                
                # 验证密码强度
                is_strong, message = validate_password_strength(password)
                if not is_strong:
                    print(f"❌ {message}")
                    continue
                
                confirm_password = getpass.getpass("确认新密码: ")
                if password != confirm_password:
                    print("❌ 两次输入的密码不一致")
                    continue
                
                break
            
            user.set_password(password)
            db.session.commit()
            print("✅ 密码重置成功")
            
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            db.session.rollback()
            print(f"❌ 重置失败: {e}")

def delete_user():
    """删除用户"""
    print("\n🗑️  删除用户")
    print("-" * 30)
    
    app = create_app()
    with app.app_context():
        # 显示用户列表
        users = User.query.all()
        if not users:
            print("没有找到用户")
            return
        
        print("选择要删除的用户:")
        for i, user in enumerate(users, 1):
            print(f"{i}. {user.email} ({user.username}) - {user.role}")
        
        try:
            choice = int(input("\n输入用户编号: ")) - 1
            if choice < 0 or choice >= len(users):
                print("❌ 无效的用户编号")
                return
            
            user = users[choice]
            
            # 防止删除最后一个管理员
            admin_count = User.query.filter_by(role='admin').count()
            if user.role == 'admin' and admin_count <= 1:
                print("❌ 不能删除最后一个管理员用户")
                return
            
            print(f"\n⚠️  确认删除用户: {user.email} ({user.username})?")
            confirm = input("输入 'DELETE' 确认删除: ")
            
            if confirm == 'DELETE':
                db.session.delete(user)
                db.session.commit()
                print("✅ 用户删除成功")
            else:
                print("❌ 删除操作已取消")
                
        except ValueError:
            print("❌ 请输入有效的数字")
        except Exception as e:
            db.session.rollback()
            print(f"❌ 删除失败: {e}")

def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 50)
        print("🔧 NLHE数据库用户管理工具")
        print("=" * 50)
        print("1. 添加新用户")
        print("2. 查看所有用户")
        print("3. 修改用户信息")
        print("4. 重置用户密码")
        print("5. 删除用户")
        print("0. 退出")
        
        choice = input("\n请选择操作 (0-5): ").strip()
        
        if choice == '1':
            add_user()
        elif choice == '2':
            list_users()
        elif choice == '3':
            modify_user()
        elif choice == '4':
            reset_password()
        elif choice == '5':
            delete_user()
        elif choice == '0':
            print("👋 再见！")
            break
        else:
            print("❌ 无效的选择，请重试")

if __name__ == "__main__":
    print("NLHE数据库用户管理工具")
    print("安全提示：所有密码都使用bcrypt加密存储")
    main()
