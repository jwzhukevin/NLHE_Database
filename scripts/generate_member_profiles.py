# -*- coding: utf-8 -*-
"""
批量生成成员多语言 profile.json 脚本

使用说明：
    python scripts/generate_member_profiles.py [--force]

行为：
    - 读取数据库 Member 表，获取 name、photo、title、bio、achievements
    - 生成 slug（name 小写去空格）并在 app/static/members/<slug>/ 下创建
      profile.json
    - 对 DB 字段自动判别语言（含 CJK 视为中文），填入 *_zh 或 *_en
    - 若存在旧版 info.json，按语言合并至对应槽位；仅在目标为空时补齐
    - achievements 若为字符串按换行拆分为列表
    - 默认不覆盖已存在文件，如需覆盖请加 --force

备注：
    - 需要在可导入本项目的环境下运行（项目根目录）
"""

import os
import sys
import json
import argparse
import re

# 4 空格缩进，行宽尽量 ≤ 79 字符


def create_app_context():
    """创建并推入 Flask 应用上下文。"""
    # 解释：导入应用工厂并创建 app，再推入上下文
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from app import create_app, db  # noqa: WPS433 (延迟导入)
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    return app, db, ctx


def get_all_members(db):
    """查询所有成员模型实例。"""
    # 解释：延迟导入模型以避免循环依赖
    from app.models import Member  # noqa: WPS433
    return db.session.query(Member).all()


def to_slug(name):
    """按约定生成 slug：小写 + 去空格。"""
    return (name or '').lower().replace(' ', '')


def ensure_dir(path):
    """确保目录存在。"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def split_achievements(value):
    """将成就字段规范为列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        # 解释：过滤空白项
        return [str(x).strip() for x in value if str(x).strip()]
    # 解释：按换行拆分
    return [
        line.strip() for line in str(value).split('\n') if line.strip()
    ]


def detect_lang(text):
    """简单语言检测：含中日韩字符则视为 zh，否则 en。"""
    if not text:
        return 'en'
    # CJK 统一表意字符范围
    return 'zh' if re.search(r"[\u4e00-\u9fff]", text) else 'en'


def read_info_json(member_dir):
    """读取旧版 info.json（若存在则返回其 dict，否则 None）。"""
    info_path = os.path.join(member_dir, 'info.json')
    if os.path.exists(info_path):
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def build_profile_payload(member, info=None):
    """从 DB 与可选 info.json 构建 profile.json 内容（双语，自动判别语言）。"""
    # 1) 初始化空 payload
    payload = {
        'title_zh': '',
        'title_en': '',
        'bio_zh': '',
        'bio_en': '',
        'achievements_zh': [],
        'achievements_en': [],
    }

    # 2) 处理 DB 字段：自动语言判别并填入对应槽位
    db_title = (member.title or '').strip()
    db_bio = (member.bio or '').strip()
    db_ach_list = split_achievements(member.achievements or '')

    if db_title:
        if detect_lang(db_title) == 'zh':
            payload['title_zh'] = db_title
        else:
            payload['title_en'] = db_title

    if db_bio:
        if detect_lang(db_bio) == 'zh':
            payload['bio_zh'] = db_bio
        else:
            payload['bio_en'] = db_bio

    if db_ach_list:
        # 简化：按首项判定
        lang_a = detect_lang(db_ach_list[0])
        if lang_a == 'zh':
            payload['achievements_zh'] = db_ach_list
        else:
            payload['achievements_en'] = db_ach_list

    # 3) 合并 info.json：仅在目标为空时补齐
    if isinstance(info, dict):
        title = str(info.get('title', '') or '').strip()
        bio = str(info.get('bio', '') or '').strip()
        ach = info.get('achievements', [])
        ach_list = split_achievements(ach)

        if title:
            if detect_lang(title) == 'zh':
                if not payload['title_zh']:
                    payload['title_zh'] = title
            else:
                if not payload['title_en']:
                    payload['title_en'] = title

        if bio:
            if detect_lang(bio) == 'zh':
                if not payload['bio_zh']:
                    payload['bio_zh'] = bio
            else:
                if not payload['bio_en']:
                    payload['bio_en'] = bio

        if ach_list:
            lang_a = detect_lang(ach_list[0])
            if lang_a == 'zh':
                if not payload['achievements_zh']:
                    payload['achievements_zh'] = ach_list
            else:
                if not payload['achievements_en']:
                    payload['achievements_en'] = ach_list

    return payload


def write_profile(path, payload, force=False):
    """将 payload 写入 path（存在时按 force 决定是否覆盖）。"""
    if os.path.exists(path) and not force:
        return False, 'exists'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return True, 'written'


def main():
    parser = argparse.ArgumentParser(
        description='生成成员 profile.json（多语言占位）'
    )
    parser.add_argument(
        '--force', action='store_true', help='覆盖已存在的 profile.json'
    )
    args = parser.parse_args()

    app, db, ctx = create_app_context()
    try:
        members = get_all_members(db)
        base_dir = os.path.join(app.root_path, 'static', 'members')

        created = 0
        skipped = 0
        failed = 0

        for m in members:
            slug = to_slug(m.name or '')
            if not slug:
                app.logger.warning('跳过无效成员（缺少 name）')
                failed += 1
                continue

            member_dir = os.path.join(base_dir, slug)
            ensure_dir(member_dir)
            profile_path = os.path.join(member_dir, 'profile.json')
            # 若存在 info.json，优先作为迁移来源补全语言槽位
            info = read_info_json(member_dir)
            payload = build_profile_payload(m, info=info)

            ok, status = write_profile(profile_path, payload, force=args.force)
            if ok:
                created += 1
                print(f'[OK] {slug}/profile.json {status}')
            else:
                skipped += 1
                print(f'[SKIP] {slug}/profile.json already exists')

        print('\n总结:')
        print(f'  新建: {created}')
        print(f'  跳过: {skipped}')
        print(f'  失败: {failed}')
        if failed:
            sys.exit(1)
    finally:
        ctx.pop()


if __name__ == '__main__':
    main()
