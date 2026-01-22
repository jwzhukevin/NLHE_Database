# -*- coding: utf-8 -*-
"""
CSV 路径解析工具

说明：
- 按你的最新确认，CSV 路径固定为应用内：app/static/CSV_data/output_first_50000.csv
- 本模块提供 get_csv_path(app) 用于在运行时解析并校验路径是否存在；
- 若不存在则抛出明确异常，由上层捕获并返回友好错误提示。

代码风格：
- 4 空格缩进；蛇形命名；中文解释性注释；行长控制；
"""

import os


def get_csv_path(app):
    """获取固定的 CSV 路径并进行存在性校验。

    返回:
        str: CSV 绝对路径

    异常:
        FileNotFoundError: 当文件不存在时抛出，供上层友好提示
    """
    # 解释：使用应用根路径拼接固定位置，确保跨平台路径正确
    csv_path = os.path.join(
        app.root_path,
        'static',
        'CSV_data',
        'output_first_50000.csv'
    )

    # 解释：校验文件存在性，避免后续 DuckDB 读取失败
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"CSV 文件不存在: {csv_path}. 请确认文件路径与部署是否正确。"
        )

    return csv_path
