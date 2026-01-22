# -*- coding: utf-8 -*-
"""
通用 CSV 表视图辅助（DuckDB）

特性：
- 基于文件 mtime 的热更新（CREATE OR REPLACE VIEW）
- 文本搜索（多列 ILIKE 模糊）、分页
- 统一将 CSV 原始列名映射为蛇形命名键（可选）

使用方法：
- 在具体蓝图中，定义 CSV 路径、视图名、可选择/显示列与搜索列
- 调用 ensure_view_up_to_date(app) 保证视图与 CSV 同步
- 使用 query_table() 构造分页数据
"""
from typing import List, Dict, Any, Tuple, Optional
import os
import duckdb
from flask import current_app


class CsvDuckView:
    def __init__(
        self,
        csv_path_fn,
        view_name: str,
        select_columns: List[str],
        search_columns: Optional[List[str]] = None,
        column_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        参数:
            csv_path_fn: (app) -> str 返回 CSV 绝对路径的函数
            view_name: DuckDB 视图名
            select_columns: SELECT 的列名（使用 CSV 原始列名）
            search_columns: ILIKE 搜索的列名列表（使用 CSV 原始列名）
            column_map: 将返回对象中的键名从显示列映射到蛇形统一键
        """
        self.csv_path_fn = csv_path_fn
        self.view_name = view_name
        self.select_columns = select_columns
        self.search_columns = search_columns or []
        self.column_map = column_map or {}
        self._conn = None
        self._mtime_cache: float = -1.0

    def _get_conn(self):
        if self._conn is None:
            self._conn = duckdb.connect(database=':memory:')
        return self._conn

    def ensure_view_up_to_date(self) -> Tuple[str, str]:
        app = current_app._get_current_object()
        csv_path = self.csv_path_fn(app)
        mtime = os.path.getmtime(csv_path)
        conn = self._get_conn()
        if mtime != self._mtime_cache:
            sql = (
                f"CREATE OR REPLACE VIEW {self.view_name} AS "
                f"SELECT * FROM read_csv_auto('{csv_path}', header=True, sample_size=-1, nullstr=['', 'None'])"
            )
            conn.execute(sql)
            self._mtime_cache = mtime
        return csv_path, self.view_name

    def query_table(self, q: Dict[str, Any]) -> Dict[str, Any]:
        _, view = self.ensure_view_up_to_date()
        conn = self._get_conn()
        page = max(1, int(q.get('page', 1) or 1))
        page_size = min(200, max(1, int(q.get('page_size', 20) or 20)))
        offset = (page - 1) * page_size

        where_clauses: List[str] = []
        params: List[Any] = []

        q_text = str(q.get('q') or '').strip()
        regex_flag = str(q.get('regex') or '').strip().lower() in ('1','true','yes','on')
        if q_text and self.search_columns:
            ors = []
            if regex_flag:
                # 使用 DuckDB 的正则匹配，添加 (?i) 前缀实现不区分大小写
                pattern = f"(?i){q_text}"
                for col in self.search_columns:
                    ors.append(f"regexp_matches(CAST(\"{col}\" AS VARCHAR), ?)")
                    params.append(pattern)
            else:
                like = f"%{q_text}%"
                for col in self.search_columns:
                    ors.append(f'"{col}" ILIKE ?')
                    params.append(like)
            where_clauses.append('(' + ' OR '.join(ors) + ')')

        where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
        count_sql = f'SELECT COUNT(*) FROM {view}{where_sql}'
        total = conn.execute(count_sql, params).fetchone()[0]

        select_cols_sql = ', '.join([f'"{c}"' if any(ch in c for ch in [' ', '(', ')']) else c for c in self.select_columns])
        data_sql = f'SELECT {select_cols_sql} FROM {view}{where_sql} LIMIT ? OFFSET ?'
        rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            orig = {self.select_columns[i]: row[i] for i in range(len(self.select_columns))}
            # 统一键名
            obj: Dict[str, Any] = {}
            for k, v in orig.items():
                key = self.column_map.get(k, k)
                obj[key] = v
            items.append(obj)

        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
        }
