# -*- coding: utf-8 -*-
"""
成员蓝图
路由：成员列表页、成员详情页

说明：所有辅助函数统一从 app.utils 导入，避免重复定义。
"""
from flask import Blueprint, render_template, current_app
from flask_babel import get_locale

# 统一从 utils.py 导入辅助函数（消除代码重复）
from ..utils import (
    to_slug,
    load_member_profile,
    select_by_locale,
    list_member_dirs_by_category,
    find_member_dir_name,
)

members_bp = Blueprint('members', __name__, url_prefix='/members')


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

    cats = list_member_dirs_by_category()
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
            real_dir = dir_name if category == cat else (find_member_dir_name(slug) or dir_name)
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
    
    dir_name = find_member_dir_name(slug)
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
        real_dir = find_member_dir_name(slug) or slug
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
