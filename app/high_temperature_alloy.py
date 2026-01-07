# -*- coding: utf-8 -*-
"""
High Temperature Alloy (CSV) Blueprint

说明：
- 提供 /High_temperature_alloy 列表页与 /query JSON 接口，以及 /detail/HTA-<row>-<hash10> 详情页。
- 采用 DuckDB 直接读取 CSV，并基于 CSV 的 mtime 实现热更新（无需重启）。
- ID 策略：
  - 展示 ID：HTA-<row>（行号为 A 规则：按当前筛选+排序后的全局序号，跨分页累积）
  - 稳定 ID：HTA-<HASH10>（固定列序拼接经 MD5，取前 10 位大写）。用于详情定位。

注意：本文件仅提供后端接口与页面渲染入口；页面模板与前端脚本在后续批次新增。
"""

import os
import hashlib
from typing import Dict, Any, List, Tuple

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
)

import duckdb  # 依赖在 requirements 中追加

from .csv_config import get_csv_path

# --------------------------
# 蓝图定义
# --------------------------
high_temperature_alloy_bp = Blueprint(
    'high_temperature_alloy', __name__, url_prefix='/database/structural_materials/ceramics/model_prediction'
)

# --------------------------
# DuckDB 会话与热更新视图
# --------------------------
_duck_conn = None
_csv_mtime_cache: float = -1.0
_view_name = 'v_high_temperature_alloy'

# 固定列顺序（用于哈希与字段映射）
_FIXED_COLUMNS = [
    'Ag', 'Au', 'Cu', 'I', 'K', 'S', 'Se', 'Te',
    'Material',
    'crystal_structure',
    'process_type',
    'heat_treatment_process',
    'Bending Strength (MPa)',
    'zt',
    'Bending Strain',
]

# 列名映射：将含空格/括号的列转为后端返回的蛇形命名
_DISPLAY_TO_KEY = {
    'Bending Strength (MPa)': 'bending_strength_mpa',
    'Bending Strain': 'bending_strain',
}


def _get_conn():
    """获取（或创建）DuckDB 连接。"""
    global _duck_conn
    if _duck_conn is None:
        # 解释：内存模式，避免持久化数据库文件
        _duck_conn = duckdb.connect(database=':memory:')
    return _duck_conn


def _ensure_view_up_to_date() -> Tuple[str, str]:
    """确保 DuckDB 视图与 CSV 同步。

    返回:
        (csv_path, view_name)
    """
    global _csv_mtime_cache

    app = current_app._get_current_object()
    csv_path = get_csv_path(app)
    mtime = os.path.getmtime(csv_path)

    conn = _get_conn()

    # 若 CSV 发生变更，则刷新 VIEW
    if mtime != _csv_mtime_cache:
        # 解释：使用 read_csv_auto 自动识别类型；header=True 使用首行作为表头
        sql = (
            f"CREATE OR REPLACE VIEW {_view_name} AS "
            f"SELECT * FROM read_csv_auto('{csv_path}', header=True, "
            f"sample_size=-1, nullstr=['', 'None'])"
        )
        conn.execute(sql)
        _csv_mtime_cache = mtime
    return csv_path, _view_name


def _coalesce_value(v: Any) -> str:
    """将任意值转为字符串（用于哈希），None 转为空字符串。"""
    if v is None:
        return ''
    return str(v)


def _hash_row(row: Dict[str, Any]) -> str:
    """基于固定列顺序计算短哈希（前 10 位大写），并加前缀 HTA-。"""
    sep = '\x1F'
    parts = []
    for col in _FIXED_COLUMNS:
        parts.append(_coalesce_value(row.get(col)))
    raw = sep.join(parts)
    h = hashlib.md5(raw.encode('utf-8')).hexdigest().upper()[:10]
    return f'HTA-{h}'


def _parse_multi_select(arg_val: str) -> List[str]:
    """解析多选参数，约定用逗号分隔。"""
    if not arg_val:
        return []
    return [s for s in (arg_val.split(',') if isinstance(arg_val, str) else []) if s != '']


def _fetch_hta_data(args: Dict[str, Any]) -> Dict[str, Any]:
    """从 CSV 查询高温合金数据的核心逻辑。"""
    _, view = _ensure_view_up_to_date()
    conn = _get_conn()

    def rng(name: str) -> Tuple[Any, Any]:
        try:
            lo = float(args.get(f'{name}_min')) if args.get(f'{name}_min') else None
            hi = float(args.get(f'{name}_max')) if args.get(f'{name}_max') else None
            return lo, hi
        except (ValueError, TypeError):
            return None, None

    elem_cols = ['Ag', 'Au', 'Cu', 'I', 'K', 'S', 'Se', 'Te']
    multi_cats = {
        'crystal_structure': _parse_multi_select(args.get('crystal_structure')),
        'process_type': _parse_multi_select(args.get('process_type')),
        'heat_treatment_process': _parse_multi_select(args.get('heat_treatment_process')),
    }
    bs_lo, bs_hi = rng('bending_strength')
    zt_lo, zt_hi = rng('zt')
    bs_strain_lo, bs_strain_hi = rng('bending_strain')

    try:
        page = max(1, int(args.get('page', '1')))
        page_size = min(200, max(1, int(args.get('page_size', '20'))))
    except (ValueError, TypeError):
        page = 1
        page_size = 20
    offset = (page - 1) * page_size

    where_clauses: List[str] = []
    params: List[Any] = []

    for col in elem_cols:
        lo, hi = rng(col.lower())
        if lo is not None: where_clauses.append(f'"{col}" >= ?'); params.append(lo)
        if hi is not None: where_clauses.append(f'"{col}" <= ?'); params.append(hi)

    for cat_col, values in multi_cats.items():
        if values:
            placeholders = ','.join(['?'] * len(values))
            where_clauses.append(f'"{cat_col}" IN ({placeholders})')
            params.extend(values)

    q_text = str(args.get('q', '')).strip()
    if q_text:
        like = f"%{q_text}%"
        where_clauses.append('("Material" ILIKE ? OR "process_type" ILIKE ? OR "heat_treatment_process" ILIKE ?)')
        params.extend([like, like, like])

    if bs_lo is not None: where_clauses.append('"Bending Strength (MPa)" >= ?'); params.append(bs_lo)
    if bs_hi is not None: where_clauses.append('"Bending Strength (MPa)" <= ?'); params.append(bs_hi)
    if zt_lo is not None: where_clauses.append('"zt" >= ?'); params.append(zt_lo)
    if zt_hi is not None: where_clauses.append('"zt" <= ?'); params.append(zt_hi)
    if bs_strain_lo is not None: where_clauses.append('"Bending Strain" >= ?'); params.append(bs_strain_lo)
    if bs_strain_hi is not None: where_clauses.append('"Bending Strain" <= ?'); params.append(bs_strain_hi)

    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    count_sql = f'SELECT COUNT(*) FROM {view}{where_sql}'
    total = conn.execute(count_sql, params).fetchone()[0]

    select_cols = 'Ag, Au, Cu, I, K, S, Se, Te, Material, crystal_structure, process_type, heat_treatment_process, "Bending Strength (MPa)", zt, "Bending Strain"'
    data_sql = f'SELECT {select_cols} FROM {view}{where_sql} LIMIT ? OFFSET ?'
    rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
    col_names = [c.strip().replace('"', '') for c in select_cols.split(',')]

    items: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        row_dict = {col_names[i]: row[i] for i in range(len(col_names))}
        hta_hash = _hash_row(row_dict)
        hta_row = offset + idx + 1
        
        item = {
            'hta_row': hta_row,
            'hta_display_id': f'HTA-{hta_row}',
            'hta_hash': hta_hash,
            'Ag': row_dict.get('Ag'),
            'Au': row_dict.get('Au'),
            'Cu': row_dict.get('Cu'),
            'I': row_dict.get('I'),
            'K': row_dict.get('K'),
            'S': row_dict.get('S'),
            'Se': row_dict.get('Se'),
            'Te': row_dict.get('Te'),
            'Material': row_dict.get('Material'),
            'crystal_structure': row_dict.get('crystal_structure'),
            'process_type': row_dict.get('process_type'),
            'heat_treatment_process': row_dict.get('heat_treatment_process'),
            'bending_strength_mpa': row_dict.get('Bending Strength (MPa)'),
            'zt': row_dict.get('zt'),
            'bending_strain': row_dict.get('Bending Strain'),
        }
        items.append(item)

    return {'items': items, 'total': total, 'page': page, 'page_size': page_size}


@high_temperature_alloy_bp.route('')
def index():
    """列表页，支持服务端预渲染。"""
    # 将请求参数转换为普通字典以传递给辅助函数
    search_params = {k: v for k, v in request.args.items()}
    initial_data = _fetch_hta_data(search_params)
    return render_template(
        'High_temperature_alloy/index.html',
        items=initial_data.get('items', []),
        data=initial_data,
        search_params=search_params
    )


@high_temperature_alloy_bp.route('/query')
def query():
    """JSON 查询接口。"""
    data = _fetch_hta_data(request.args.to_dict())
    return jsonify(data)


@high_temperature_alloy_bp.route('/detail/<hta_id>')
def detail(hta_id: str):
    """详情页：路由格式 HTA-<row>-<hash10>，以 <hash10> 精确定位记录。"""
    _, view = _ensure_view_up_to_date()
    conn = _get_conn()

    # 解析路由 ID：HTA-<row>-<hash10>
    try:
        # 允许大小写 HTA-
        id_str = hta_id.strip()
        if not id_str.upper().startswith('HTA-'):
            return render_template('errors/404.html'), 404
        # 去掉前缀后按最后一个 '-' 分离 row 与 hash10（hash 中不包含 '-')
        tail = id_str[4:]
        # 从右侧分割，仅一次
        if '-' not in tail:
            return render_template('errors/404.html'), 404
        row_part, hash_part = tail.rsplit('-', 1)
        short_hash = hash_part.upper()
        if len(short_hash) != 10:
            return render_template('errors/404.html'), 404
    except Exception:
        return render_template('errors/404.html'), 404

    # 为了定位记录：扫描表（受限于 5 万行，性能可接受），找到哈希匹配的第一条
    select_cols = (
        'Ag, Au, Cu, I, K, S, Se, Te,'
        ' Material,'
        ' crystal_structure, process_type, heat_treatment_process,'
        ' "Bending Strength (MPa)", zt, "Bending Strain"'
    )
    data_sql = f'SELECT {select_cols} FROM {view}'
    col_names = [
        'Ag', 'Au', 'Cu', 'I', 'K', 'S', 'Se', 'Te',
        'Material', 'crystal_structure', 'process_type', 'heat_treatment_process',
        'Bending Strength (MPa)', 'zt', 'Bending Strain'
    ]

    # 逐行比对哈希（DuckDB 侧直接计算字符串拼接与 md5 的可移植性不如在后端稳定）
    # 若数据很大，可进一步做分页扫描或建立投影缓存。本期简单实现。
    cursor = conn.execute(data_sql)
    record = None
    for row in cursor.fetchall():
        row_dict = {col_names[i]: row[i] for i in range(len(col_names))}
        h = _hash_row(row_dict)
        if h.endswith(short_hash):  # h 为 HTA-XXXXXXXXXX
            record = row_dict
            hta_hash = h
            break

    if record is None:
        return render_template('errors/404.html'), 404

    # 规范化 keys 供模板使用
    normalized = {
        'Ag': record['Ag'],
        'Au': record['Au'],
        'Cu': record['Cu'],
        'I': record['I'],
        'K': record['K'],
        'S': record['S'],
        'Se': record['Se'],
        'Te': record['Te'],
        'Material': record['Material'],
        'process_type': record['process_type'],
        'heat_treatment_process': record['heat_treatment_process'],
        'crystal_structure': record['crystal_structure'],
        'bending_strength_mpa': record['Bending Strength (MPa)'],
        'zt': record['zt'],
        'bending_strain': record['Bending Strain'],
    }

    # 详情页展示：
    # - 显示可读 ID（来自路由的行号部分）与稳定哈希 ID（HTA-<hash10>）
    # - 模块化布局在模板实现
    return render_template(
        'High_temperature_alloy/detail.html',
        hta_display_id=f'HTA-{row_part}',
        hta_hash=hta_hash,
        data=normalized,
    )
