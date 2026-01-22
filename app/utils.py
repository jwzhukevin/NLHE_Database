# utils.py
# 公共工具函数模块：提供跨模块共享的辅助函数

import os
import re
import json
import random
import io
import time
from flask import current_app, session, send_file
from PIL import Image, ImageDraw


def get_material_dir(material_id):
    """
    根据材料ID返回材料目录路径（统一为 IMR-{id}，不再兼容 IMR-00000001 旧格式）。
    """
    base_dir = os.path.join(current_app.root_path, 'static', 'materials')
    new_dir = os.path.join(base_dir, f'IMR-{material_id}')
    return new_dir


def safe_float(value):
    """
    安全地将字符串转换为浮点数（允许空值）。

    参数：
        value: 输入字符串

    返回：
        float 或 None；转换失败或输入为空时返回 None。
    """
    try:
        return float(value) if value else None
    except ValueError:
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
        return int(value) if value else None
    except ValueError:
        return None


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


def get_client_ip():
    """Get client IP address of the current request"""
    from flask import request
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR']
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.remote_addr


def generate_captcha_image(text, width=140, height=50, scale_factor=2):
    """
    使用Pillow生成符合网站风格的验证码图片
    采用高分辨率渲染后缩放的方式，确保在各种环境下都清晰显示
    """
    from .services import FontManager
    
    THEME_COLORS = {
        'primary': (0, 71, 171),
        'secondary': (30, 92, 179),
        'accent': (0, 127, 255),
        'light_bg': (245, 248, 255),
        'nav_bg': (181, 222, 253),
        'text_dark': (51, 51, 51),
    }

    render_width = int(width * scale_factor)
    render_height = int(height * scale_factor)

    image = Image.new('RGB', (render_width, render_height), color=THEME_COLORS['light_bg'])
    draw = ImageDraw.Draw(image)

    for y in range(render_height):
        ratio = y / render_height
        r = int(THEME_COLORS['light_bg'][0] + (THEME_COLORS['nav_bg'][0] - THEME_COLORS['light_bg'][0]) * ratio * 0.3)
        g = int(THEME_COLORS['light_bg'][1] + (THEME_COLORS['nav_bg'][1] - THEME_COLORS['light_bg'][1]) * ratio * 0.3)
        b = int(THEME_COLORS['light_bg'][2] + (THEME_COLORS['nav_bg'][2] - THEME_COLORS['light_bg'][2]) * ratio * 0.3)
        draw.line([(0, y), (render_width, y)], fill=(r, g, b))

    base_font_size = 32
    font_size = int(base_font_size * scale_factor)
    font = FontManager.get_captcha_font(font_size)
    
    if hasattr(font, '_use_embedded') and font._use_embedded:
        from .services import EmbeddedFont
        return EmbeddedFont.generate_embedded_captcha(text, width, height)

    dot_count = int(30 * scale_factor)
    dot_size = int(1 * scale_factor)
    for _ in range(dot_count):
        x = random.randint(0, render_width)
        y = random.randint(0, render_height)
        alpha = random.uniform(0.1, 0.3)
        base_color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        color = tuple(int(c + (255 - c) * (1 - alpha)) for c in base_color)
        draw.ellipse([x-dot_size, y-dot_size, x+dot_size, y+dot_size], fill=color)

    try:
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError:
        text_width = len(text) * int(20 * scale_factor)
        text_height = int(28 * scale_factor)

    start_x = (render_width - text_width) // 2
    start_y = (render_height - text_height) // 2

    char_colors = [
        THEME_COLORS['primary'],
        THEME_COLORS['secondary'],
        THEME_COLORS['accent'],
        THEME_COLORS['text_dark']
    ]

    char_width = text_width // len(text) if len(text) > 0 else int(20 * scale_factor)
    offset_range = int(3 * scale_factor)

    for i, char in enumerate(text):
        color = char_colors[i % len(char_colors)]
        char_x = start_x + i * char_width + random.randint(-offset_range, offset_range)
        char_y = start_y + random.randint(-offset_range, offset_range)
        draw.text((char_x, char_y), char, font=font, fill=color)

    line_width = max(1, int(1 * scale_factor))
    for _ in range(2):
        color = random.choice([THEME_COLORS['primary'], THEME_COLORS['accent']])
        alpha_color = tuple(int(c + (255 - c) * 0.6) for c in color)
        start_x_line = random.randint(0, render_width // 3)
        start_y_line = random.randint(render_height // 4, 3 * render_height // 4)
        end_x_line = random.randint(2 * render_width // 3, render_width)
        end_y_line = random.randint(render_height // 4, 3 * render_height // 4)
        draw.line([(start_x_line, start_y_line), (end_x_line, end_y_line)],
                 fill=alpha_color, width=line_width)

    if scale_factor != 1:
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG', quality=100, optimize=True)
    img_buffer.seek(0)

    return img_buffer
