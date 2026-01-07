# -*- coding: utf-8 -*-
"""
Ceramics Literature CSV Module
路由前缀：/Ceramics/literature
功能：
- 列表页模板渲染
- /query JSON 查询（文本搜索/分页）
- 基于 DuckDB 的 CSV 即时读取（mtime 热更新）
"""
from typing import Any, Dict
import os
from flask import Blueprint, current_app, jsonify, render_template, request
from .csv_table import CsvDuckView


def _csv_path(app) -> str:
    return os.path.join(app.root_path, 'static', 'CSV_data', '文献数据.csv')


# 原始列名（与 CSV 一致）
_SELECT_COLUMNS = [
    'DOI',
    'Compound Name',
    'Single Crystal',
    'Polycrystalline',
    'Space Group',
    'Bending Strain',
    'Bending Strenth',
    'Bending Strenth Unit',
]

# 搜索列（ILIKE 模糊）
_SEARCH_COLUMNS = [
    'Compound Name', 'Space Group'
]

# 返回对象键名映射（蛇形）
_COLUMN_MAP = {
    'DOI': 'doi',
    'Compound Name': 'compound_name',
    'Single Crystal': 'single_crystal',
    'Polycrystalline': 'polycrystalline',
    'Space Group': 'space_group',
    'Bending Strain': 'bending_strain',
    'Bending Strenth': 'bending_strength',  # 拼写按原始列，映射为标准键
    'Bending Strenth Unit': 'bending_strength_unit',
}

_view = CsvDuckView(
    csv_path_fn=_csv_path,
    view_name='v_ceramics_literature',
    select_columns=_SELECT_COLUMNS,
    search_columns=_SEARCH_COLUMNS,
    column_map=_COLUMN_MAP,
)

ceramics_literature = Blueprint('ceramics_literature', __name__, url_prefix='/database/structural_materials/ceramics/literature')


@ceramics_literature.route('')
def index():
    return render_template('Ceramics/Literature/index.html')


@ceramics_literature.route('/query')
def query():
    data: Dict[str, Any] = _view.query_table(request.args)
    return jsonify(data)
