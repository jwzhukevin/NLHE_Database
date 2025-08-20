# -*- coding: utf-8 -*-
"""
扫描 profile.json，列出“中文槽位为空但英文有值”的成员。

使用：
    python scripts/scan_profiles_missing_zh.py [--format txt|csv|md]

说明：
    - 只读操作，不会修改任何文件。
    - 扫描目录 app/static/members/<slug>/profile.json。
    - 检查字段：title/bio/achievements 三类（*_zh 与 *_en）。
    - 输出报告：显示成员 slug 与缺失中文的字段项。

编码规范：
    - 4 空格缩进，行宽尽量 ≤ 79。
    - 命名使用蛇形命名法。
"""

import os
import sys
import json
import argparse
from typing import List, Dict


def load_json(path: str):
    """安全读取 JSON 文件，失败返回 None。"""
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        return None
    return None


def is_empty_text(value: str) -> bool:
    """判断文本是否为空（None/空串/全空白）。"""
    return not (str(value or '').strip())


def is_empty_list(value) -> bool:
    """判断列表是否为空或无有效项。"""
    if not value:
        return True
    if isinstance(value, list):
        return not [str(x).strip() for x in value if str(x).strip()]
    return False


def find_member_dirs(base_dir: str) -> List[str]:
    """获取成员 slug 目录列表。"""
    if not os.path.exists(base_dir):
        return []
    return [
        d for d in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, d))
    ]


def scan_profiles(base_dir: str) -> List[Dict[str, str]]:
    """扫描并返回问题列表（每项为 dict）。"""
    issues = []
    for slug in find_member_dirs(base_dir):
        profile_path = os.path.join(base_dir, slug, 'profile.json')
        data = load_json(profile_path)
        if not isinstance(data, dict):
            continue

        title_zh = data.get('title_zh')
        title_en = data.get('title_en')
        bio_zh = data.get('bio_zh')
        bio_en = data.get('bio_en')
        ach_zh = data.get('achievements_zh')
        ach_en = data.get('achievements_en')

        # 检查三类字段
        if is_empty_text(title_zh) and not is_empty_text(title_en):
            issues.append({'slug': slug, 'field': 'title', 'zh': 'empty',
                           'en': 'present'})
        if is_empty_text(bio_zh) and not is_empty_text(bio_en):
            issues.append({'slug': slug, 'field': 'bio', 'zh': 'empty',
                           'en': 'present'})
        if is_empty_list(ach_zh) and not is_empty_list(ach_en):
            issues.append({'slug': slug, 'field': 'achievements', 'zh': 'empty',
                           'en': 'present'})
    return issues


def print_txt(issues: List[Dict[str, str]]):
    """以文本格式输出报告。"""
    if not issues:
        print('未发现需要补齐的中文项。')
        return
    print('需要补齐的中文项：')
    by_slug: Dict[str, List[str]] = {}
    for it in issues:
        by_slug.setdefault(it['slug'], []).append(it['field'])
    for slug, fields in sorted(by_slug.items()):
        print(f'- {slug}: {", ".join(sorted(set(fields)))}')
    print(f'总计成员数：{len(by_slug)}；问题项：{len(issues)}')


def print_csv(issues: List[Dict[str, str]]):
    """以 CSV 格式输出报告（header: slug,field,zh,en）。"""
    print('slug,field,zh,en')
    for it in issues:
        print(f"{it['slug']},{it['field']},{it['zh']},{it['en']}")


def print_md(issues: List[Dict[str, str]]):
    """以 Markdown 表格输出报告。"""
    if not issues:
        print('未发现需要补齐的中文项。')
        return
    print('| slug | field | zh | en |')
    print('| ---- | ----- | -- | -- |')
    for it in issues:
        print(f"| {it['slug']} | {it['field']} | {it['zh']} | {it['en']} |")


def parse_args(argv: List[str]):
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description='扫描 profile.json 缺失中文项'
    )
    parser.add_argument(
        '--format', dest='fmt', choices=['txt', 'csv', 'md'], default='txt',
        help='输出格式（默认 txt）'
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    """主入口：扫描并输出报告。"""
    args = parse_args(argv)
    base_dir = os.path.join('app', 'static', 'members')
    issues = scan_profiles(base_dir)

    if args.fmt == 'csv':
        print_csv(issues)
    elif args.fmt == 'md':
        print_md(issues)
    else:
        print_txt(issues)

    # 如需严格模式可在此返回非零，但默认返回 0
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
