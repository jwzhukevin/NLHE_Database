# utils.py
# 公共工具函数模块：提供跨模块共享的辅助函数
#
# 重要：本文件是所有通用辅助函数的唯一来源（Single Source of Truth）。
# 其他模块（blueprints/auth.py、blueprints/members.py、commands.py 等）
# 应通过 `from ..utils import xxx` 引用，而非重新定义。

import os
import re
import json
from flask import current_app, request


# ==============================================================================
# (一) 类型转换辅助
# ==============================================================================

def safe_float(value):
    """
    安全地将字符串转换为浮点数（允许空值）。

    参数：
        value: 输入字符串

    返回：
        float 或 None；转换失败或输入为空时返回 None。
    """
    try:
        return float(value) if value not in ('', None) else None
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """
    安全地将字符串转换为整数（允许空值）。

    参数：
        value: 输入字符串

    返回：
        int 或 None；转换失败或输入为空时返回 None。
    """
    try:
        return int(value) if value not in ('', None) else None
    except (ValueError, TypeError):
        return None


# ==============================================================================
# (二) 材料目录辅助
# ==============================================================================

def get_material_dir(material_id):
    """
    根据材料ID返回材料目录路径。

    目录策略：
    - 新标准：`IMR-{id}`（不补零）；
    - 兼容回退：若新目录不存在，则尝试旧格式 `IMR-{id:08d}`；
    - 返回值：若两者都不存在，返回新格式路径（调用方可据此创建）。
    """
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    if os.path.exists(new_dir):
        return new_dir
    old_dir = os.path.join(base_dir, f'IMR-{int(material_id):08d}')
    if os.path.exists(old_dir):
        return old_dir
    return new_dir


# ==============================================================================
# (三) 网络辅助
# ==============================================================================

def get_client_ip():
    """获取客户端IP地址，优先从代理头读取。"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr


# ==============================================================================
# (四) 成员目录辅助
# ==============================================================================

def to_slug(name):
    """将姓名转为 slug：小写并移除空白字符。"""
    if not name:
        return ''
    return re.sub(r'\s+', '', str(name).strip().lower())


def read_json(path):
    """安全读取 JSON 文件，失败返回 None。"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        current_app.logger.warning(f'read_json failed: {path}: {e}')
    return None


def split_achievements(value):
    """成就字段规范化为列表：支持字符串按行拆分或原生列表。"""
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [line.strip() for line in str(value).split('\n') if line.strip()]


def load_member_profile(slug):
    """
    在成员目录下按分类查找 profile.json（兼容新旧分类名）：
    优先路径：
    - 新：members/Supervisors/<slug>/profile.json → members/Students/<slug>/profile.json
    - 旧：members/Teacher/<slug>/profile.json → members/Student/<slug>/profile.json
    - 根：members/<slug>/profile.json
    """
    members_root = os.path.join(current_app.root_path, 'static', 'members')

    def find_dir_name(cat_dir):
        if not os.path.isdir(cat_dir):
            return None
        try:
            for name in os.listdir(cat_dir):
                full = os.path.join(cat_dir, name)
                if os.path.isdir(full) and to_slug(name) == slug:
                    return name
        except Exception:
            return None
        return None

    supervisors_dir = find_dir_name(os.path.join(members_root, 'Supervisors')) or find_dir_name(os.path.join(members_root, 'Teacher'))
    students_dir = find_dir_name(os.path.join(members_root, 'Students')) or find_dir_name(os.path.join(members_root, 'Student'))
    root_dir = find_dir_name(members_root)

    search_paths = []
    if supervisors_dir:
        search_paths.append((os.path.join(members_root, 'Supervisors', supervisors_dir, 'profile.json'), 'Supervisors'))
        search_paths.append((os.path.join(members_root, 'Teacher', supervisors_dir, 'profile.json'), 'Supervisors'))
    else:
        search_paths.append((os.path.join(members_root, 'Supervisors', slug, 'profile.json'), 'Supervisors'))
        search_paths.append((os.path.join(members_root, 'Teacher', slug, 'profile.json'), 'Supervisors'))
    if students_dir:
        search_paths.append((os.path.join(members_root, 'Students', students_dir, 'profile.json'), 'Students'))
        search_paths.append((os.path.join(members_root, 'Student', students_dir, 'profile.json'), 'Students'))
    else:
        search_paths.append((os.path.join(members_root, 'Students', slug, 'profile.json'), 'Students'))
        search_paths.append((os.path.join(members_root, 'Student', slug, 'profile.json'), 'Students'))
    if root_dir:
        search_paths.append((os.path.join(members_root, root_dir, 'profile.json'), None))
    else:
        search_paths.append((os.path.join(members_root, slug, 'profile.json'), None))

    for path, cat in search_paths:
        profile = read_json(path)
        if profile is not None:
            return profile, (cat or 'profile')
    return None, None


def select_by_locale(profile, member, locale):
    """根据语言选择显示字段，并内置回退到 DB 字段。"""
    lang = str(locale) if locale else 'en'
    prefer_zh = lang.startswith('zh')

    db_title = (member.title or '').strip() if getattr(member, 'title', None) else ''
    db_bio = (member.bio or '').strip() if getattr(member, 'bio', None) else ''
    db_ach = split_achievements(getattr(member, 'achievements', '') or '')

    title_zh = (profile or {}).get('title_zh') or ''
    title_en = (profile or {}).get('title_en') or ''
    bio_zh = (profile or {}).get('bio_zh') or ''
    bio_en = (profile or {}).get('bio_en') or ''
    ach_zh = (profile or {}).get('achievements_zh') or []
    ach_en = (profile or {}).get('achievements_en') or []

    if prefer_zh:
        display_title = title_zh or db_title or title_en
        display_bio = bio_zh or db_bio or bio_en
        display_achievements = ach_zh or db_ach or ach_en
    else:
        display_title = title_en or title_zh or db_title
        display_bio = bio_en or bio_zh or db_bio
        display_achievements = ach_en or ach_zh or db_ach

    if not isinstance(display_achievements, list):
        display_achievements = split_achievements(display_achievements)

    return {
        'display_title': display_title,
        'display_bio': display_bio,
        'display_achievements': display_achievements,
    }


def list_member_dirs_by_category():
    """扫描分类目录，返回 {category: [subdir_names]}（兼容新旧分类名）。"""
    members_root = os.path.join(current_app.root_path, 'static', 'members')
    result = {'Supervisors': [], 'Students': []}
    mapping = {
        'Supervisors': ['Supervisors', 'Teacher'],
        'Students': ['Students', 'Student'],
    }
    for norm_cat, dirs in mapping.items():
        seen = set()
        for d in dirs:
            cat_dir = os.path.join(members_root, d)
            if os.path.isdir(cat_dir):
                try:
                    for name in os.listdir(cat_dir):
                        full = os.path.join(cat_dir, name)
                        if os.path.isdir(full) and name not in seen:
                            result[norm_cat].append(name)
                            seen.add(name)
                except Exception:
                    pass
    return result


def find_member_dir_name(slug):
    """根据 slug 在 Supervisors/Students（含旧名 Teacher/Student）目录中查找原始目录名。"""
    members_root = os.path.join(current_app.root_path, 'static', 'members')
    for cat in ['Supervisors', 'Teacher', 'Students', 'Student']:
        cat_dir = os.path.join(members_root, cat)
        if os.path.isdir(cat_dir):
            try:
                for name in os.listdir(cat_dir):
                    full = os.path.join(cat_dir, name)
                    if os.path.isdir(full) and to_slug(name) == slug:
                        return name
            except Exception:
                continue
    return None
