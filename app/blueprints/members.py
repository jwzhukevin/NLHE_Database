# -*- coding: utf-8 -*-
"""
成员蓝图
路由：成员列表页、成员详情页
"""
from flask import Blueprint, render_template, current_app
from flask_babel import get_locale
import os
import re
import json

members_bp = Blueprint('members', __name__, url_prefix='/members')


# ==================== 辅助函数 ====================

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
    在成员目录下按分类查找 profile.json（兼容新旧分类名）
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


def _list_member_dirs_by_category():
    """扫描分类目录，返回 {category: [subdir_names]}"""
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


def _find_member_dir_name(slug):
    """根据 slug 在分类目录中查找原始目录名"""
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


# ==================== 路由 ====================

@members_bp.route('')
def index():
    """成员列表页：按 Supervisors/Students 分类展示"""
    from ..models import Member
    from .. import db

    db_members = db.session.query(Member).all()
    db_by_slug = {to_slug(m.name or ''): m for m in db_members}

    try:
        current_locale = get_locale()
    except Exception:
        current_locale = 'en'

    cats = _list_member_dirs_by_category()
    grouped = {'Supervisors': [], 'Students': []}
    
    for cat, names in cats.items():
        for dir_name in sorted(names):
            slug = to_slug(dir_name)
            profile, found_cat = load_member_profile(slug)
            m = db_by_slug.get(slug)
            
            if m:
                selected = select_by_locale(profile, m, current_locale)
            else:
                from ..models import Member as MemberModel
                selected = select_by_locale(profile, MemberModel(name=dir_name), current_locale)
            
            photo = ''
            if isinstance(profile, dict):
                photo = str(profile.get('photo', '') or '').strip()
            if not photo and m:
                photo = (m.photo or '').strip()
            
            category = found_cat if found_cat in ('Supervisors', 'Students') else cat
            real_dir = dir_name if category == cat else (_find_member_dir_name(slug) or dir_name)
            photo_rel = None
            if photo:
                if category in ('Supervisors', 'Students'):
                    photo_rel = f'members/{category}/{real_dir}/{photo}'
                else:
                    photo_rel = f'members/{real_dir}/{photo}'
            
            grouped[cat].append({
                'slug': slug,
                'name': (m.name if m else dir_name),
                'photo': photo,
                'photo_rel': photo_rel,
                'category': category,
                **selected,
            })

    return render_template('members/index.html', supervisors=grouped['Supervisors'], students=grouped['Students'])


@members_bp.route('/<string:slug>')
def detail(slug):
    """成员详情页"""
    from ..models import Member
    from .. import db

    all_members = db.session.query(Member).all()
    target = None
    for m in all_members:
        if to_slug(m.name or '') == slug:
            target = m
            break
    
    dir_name = _find_member_dir_name(slug)
    if target is None and dir_name is None:
        return render_template('errors/404.html'), 404

    try:
        current_locale = get_locale()
    except Exception:
        current_locale = 'en'

    profile, source = load_member_profile(slug)

    if target is not None:
        selected = select_by_locale(profile, target, current_locale)
    else:
        class _Tmp:
            name = dir_name or slug
            title = ''
            bio = ''
            achievements = []
            photo = ''
        selected = select_by_locale(profile, _Tmp(), current_locale)

    photo = ''
    if isinstance(profile, dict):
        photo = str(profile.get('photo', '') or '').strip()
    if not photo and target is not None:
        photo = (target.photo or '').strip()

    category = source if source in ('Supervisors', 'Students') else None
    photo_rel = None
    real_dir = None
    if category in ('Supervisors', 'Students'):
        real_dir = _find_member_dir_name(slug) or slug
    else:
        real_dir = (dir_name or slug)
    if photo:
        if category in ('Supervisors', 'Students'):
            photo_rel = f'members/{category}/{real_dir}/{photo}'
        else:
            photo_rel = f'members/{real_dir}/{photo}'

    phone = None
    email = None
    affiliation = None
    if isinstance(profile, dict):
        phone = profile.get('phone') or phone
        email = profile.get('email') or email
        affiliation = profile.get('department') or profile.get('affiliation') or affiliation

    vm = {
        'slug': slug,
        'name': (target.name if target is not None else (dir_name or slug)),
        'photo': photo,
        'photo_rel': photo_rel,
        'category': category,
        'display_title': selected.get('display_title') or '',
        'display_bio': selected.get('display_bio') or '',
        'display_achievements': selected.get('display_achievements') or [],
        'phone': phone,
        'email': email,
        'affiliation': affiliation,
    }

    return render_template('members/detail.html', member=vm)
