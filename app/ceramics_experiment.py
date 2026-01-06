# -*- coding: utf-8 -*-
"""
Ceramics Experiment CSV Module
路由前缀：/Ceramics/experiment
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
    return os.path.join(app.root_path, 'static', 'CSV_data', '实验数据.csv')


# 原始列名（与 CSV 一致）
_SELECT_COLUMNS = [
    'Material',
    'Crystal Structure',
    'Bending Strength (MPa)',
    'Bending Strain (%)',
    'zT',
    'Heat Treatment Process',
]

# 搜索列（ILIKE 模糊）
_SEARCH_COLUMNS = [
    'Material', 'Crystal Structure', 'Heat Treatment Process'
]

# 返回对象键名映射（蛇形）
_COLUMN_MAP = {
    'Material': 'material',
    'Crystal Structure': 'crystal_structure',
    'Bending Strength (MPa)': 'bending_strength_mpa',
    'Bending Strain (%)': 'bending_strain_percent',
    'zT': 'zt',
    'Heat Treatment Process': 'heat_treatment_process',
}

_view = CsvDuckView(
    csv_path_fn=_csv_path,
    view_name='v_ceramics_experiment',
    select_columns=_SELECT_COLUMNS,
    search_columns=_SEARCH_COLUMNS,
    column_map=_COLUMN_MAP,
)

ceramics_experiment = Blueprint('ceramics_experiment', __name__, url_prefix='/Ceramics/experiment')


@ceramics_experiment.route('')
def index():
    search_params = {k: v for k, v in request.args.items()}
    initial_data = _view.query_table(request.args)
    return render_template(
        'Ceramics/Experiment/index.html',
        items=initial_data.get('items', []),
        data=initial_data,
        search_params=search_params
    )


@ceramics_experiment.route('/query')
def query():
    data: Dict[str, Any] = _view.query_table(request.args)
    return jsonify(data)
