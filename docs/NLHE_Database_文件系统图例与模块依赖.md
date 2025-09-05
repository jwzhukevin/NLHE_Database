# NLHE_Database 文件系统图例与模块依赖说明

本文档系统性描述 NLHE_Database 的文件/目录结构、模块职责、相互引用与依赖关系，并给出典型数据流示例，便于快速定位代码、评估变更影响与进行运维。

---

## 1. 顶层目录概览（仅列出仓库中已存在条目）

- `app/`
  - `__init__.py`：应用工厂，注册扩展/蓝图/CLI，集成搜索缓存失效监听。
  - `commands.py`：CLI 命令集合（初始化、导入、用户/成员管理、结构检查、缓存运维等）。
  - `search_optimizer.py`：搜索缓存、统计与失效策略（由 `__init__.py` 注册事件）。
  - `templates/`：Jinja2 模板
    - `main/index.html`：首页/主要视图入口
    - `components/periodic_table.html`：元素周期表组件
    - `errors/429.html`：限流错误页
    - 其他页面目录：`articles/`、`auth/`、`components/` 等
  - `static/`：静态资源
    - `css/`、`js/`、`images/`
    - `fonts/`：验证码所需字体（`DejaVuSans.ttf`、`DejaVuSans-Bold.ttf`）
    - `materials/IMR-*/`：材料数据（结构/能带/属性 JSON/SC 数据等）
  - `api.py`：结构等数据的 JSON API（如 `get_structure()`、`upload_structure()`）。
  - `views.py`：页面路由与后台表单（如 `add()`、`edit()`）。
- `config/i18n/babel.cfg`：Babel 抽取配置
- `docs/`
  - `NLHE_Database_使用与初始化指南.md`
  - `NLHE_Database材料数据库管理系统_说明书.md`
  - 本文档：`NLHE_Database_文件系统图例与模块依赖.md`
- `i18n/messages.pot`：抽取后的翻译模板
- `migrations/`：Alembic 迁移脚本与环境
- `scripts/`：运维/辅助脚本（如 `download_fonts.py`、`install_valkey.sh` 等）
- `tests/`：测试用例（如 `test_font_manager.py`、`test_valkey_connection.py`）
- `run.py`：开发运行入口（可选）
- `wsgi.py`：WSGI 生产入口
- `README.md`、`requirements.txt`、`pyproject.toml`、`.flaskenv`、`.env.example`

---

## 2. 模块总览与职责矩阵

- 应用工厂（`app/__init__.py`）
  - 初始化 Flask、注册蓝图/扩展
  - 注册 CLI（来自 `app/commands.py`）
  - 注册搜索缓存失效监听（调用 `register_material_cache_invalidation()`）

- 页面视图（`app/views.py`）
  - 页面路由、模板渲染
  - 后台表单：材料新增/编辑，写入静态目录与数据库

- API 服务（`app/api.py`）
  - 提供 JSON 接口：如材料结构获取 `get_structure()`、结构上传 `upload_structure()`

- 搜索优化与缓存（`app/search_optimizer.py`）
  - 缓存键管理、统计接口（CLI 侧）
  - SQLAlchemy 事件监听：材料数据变更触发缓存失效

- CLI 运维（`app/commands.py`）
  - 初始化数据库：`flask initdb`
  - 批量导入：`flask import-materials`、`flask initialize_database`
  - 用户/成员管理：`flask admin`、`flask user-add`、`flask import-member`
  - 结构/数据维护：`flask check-db-structure`、`flask update_nullable_columns`、`flask migrate-users-email`
  - 缓存运维：`flask search-cache-stats`、`flask clear-search-cache`

- 国际化（`config/i18n/babel.cfg`、`i18n/`、`app/translations/`）
  - 抽取、更新与编译翻译文件

- 模板与静态资源（`app/templates/`、`app/static/`）
  - 页面/组件模板、前端脚本与样式、材料数据文件、字体

---

## 3. 引用与依赖关系（概念图）

```text
浏览器/前端
  └── 访问视图路由(app/views.py)  ─┬─> 渲染模板(app/templates/)
                                     └─> 读取静态(app/static/)
  └── 调用 API(app/api.py) ─────────────> 返回 JSON 数据

app/__init__.py
  ├─> 注册 CLI(app/commands.py)
  ├─> 注册缓存失效(app/search_optimizer.py)
  └─> 挂载蓝图/扩展/数据库

app/commands.py
  ├─> 读写数据库/模型
  ├─> 读写材料目录(app/static/materials/IMR-*/)
  └─> 触发缓存清理(通过注册的事件)

app/search_optimizer.py
  └─> 监听模型事件(新增/编辑/删除) ⇒ 失效相关搜索缓存键
```

说明：上图为概念性关系图，实装以源码为准。各模块在 `__init__.py` 中被串联后对外工作。

---

## 4. 功能模块 → 相关文件与职责要点

- 材料数据的增删改查（视图）
  - 相关：`app/views.py`、`app/templates/...`、`app/static/materials/IMR-*/`
  - 要点：
    - 表单上传结构/能带/属性文件，写入对应材料目录
    - 解析化学式与对称性（调用内部解析工具链），更新数据库
    - 提交后触发事件，搜索缓存自动失效

- 材料结构 API
  - 相关：`app/api.py`
  - 要点：
    - `get_structure(material_id)`：读取材料结构并返回 JSON
    - `upload_structure(material_id)`：接收并保存结构文件，更新名称/对称信息

- 搜索与缓存
  - 相关：`app/search_optimizer.py`、`app/__init__.py`
  - 要点：
    - 提供缓存统计/清理 CLI
    - 注册 SQLAlchemy 事件，保证数据变更后搜索结果不陈旧

- 批量导入与初始化（CLI）
  - 相关：`app/commands.py`
  - 要点：
    - 从 `app/static/materials/` 遍历导入材料数据
    - 一次性初始化并导入（可选）
    - 结构一致性检查与字段维护

- 国际化（i18n）
  - 相关：`config/i18n/babel.cfg`、`i18n/messages.pot`、`app/translations/`
  - 要点：
    - 提取/更新/编译翻译，模板与视图通过 Flask-Babel 使用

- 错误与安全
  - 相关：`app/templates/errors/429.html`、Nginx 配置（文档第 11 章）
  - 要点：
    - 限流错误展示
    - 生产部署建议采用 HTTPS、安全头、限流

- 测试与外部服务
  - 相关：`tests/test_font_manager.py`、`tests/test_valkey_connection.py`、`scripts/install_valkey.sh`
  - 要点：
    - 字体与缓存服务连通性校验

---

## 5. 目录树（摘录，保持与仓库一致）

```text
app/
  __init__.py
  api.py
  commands.py
  search_optimizer.py
  templates/
    main/index.html
    components/periodic_table.html
    errors/429.html
    ...
  static/
    css/
    js/
    fonts/DejaVuSans*.ttf
    materials/IMR-*/
config/
  i18n/babel.cfg
docs/
  NLHE_Database_使用与初始化指南.md
  NLHE_Database材料数据库管理系统_说明书.md
  NLHE_Database_文件系统图例与模块依赖.md
i18n/
  messages.pot
migrations/
scripts/
  download_fonts.py
  install_valkey.sh
  ...
tests/
  test_font_manager.py
  test_valkey_connection.py
run.py
wsgi.py
```

---

## 6. 典型数据流示例

- 材料新增（后台表单）
  1) 前端提交表单（包含结构/能带/属性/SC 等文件）
  2) `app/views.py:add()` 接收并保存到 `app/static/materials/IMR-*/`
  3) 解析化学式/对称性，更新数据库并提交
  4) SQLAlchemy 事件触发 → `search_optimizer` 使相关搜索缓存失效
  5) 页面重定向展示最新数据

- 批量导入（运维 CLI）
  1) `flask import-materials --dir app/static/materials`
  2) 遍历 `IMR-*/` 读取结构与属性 JSON，创建/更新记录
  3) （如配置）触发能带/属性分析流程
  4) 提交后事件触发缓存失效

- 结构获取（前端可视化）
  1) 前端 JS 请求 `GET /api/structure/<id>`
  2) `app/api.py:get_structure()` 读取并返回 JSON
  3) 前端 Three.js/Plotly.js 渲染

---

## 7. 变更影响评估指南

- 变更 `app/static/materials/` 组织结构
  - 影响：导入 CLI、视图上传/读取、API 读取路径
  - 建议：先在测试环境验证导入/查看/编辑全链路

- 变更模板或静态路径
  - 影响：页面资源 404、功能 UI 异常
  - 建议：同步修改模板引用路径，检查浏览器控制台与 Nginx 日志

- 变更缓存策略
  - 影响：搜索结果一致性、性能
  - 建议：保留 `register_material_cache_invalidation()`，确保写后读一致

- 变更 CLI 行为
  - 影响：初始化/导入/维护流程
  - 建议：文档化参数变化，补充 `tests/` 场景与回滚策略

---

## 8. 快速索引（按任务查文件）

- 搭建/运行：`wsgi.py`、`run.py`、`docs/NLHE_Database_使用与初始化指南.md`
- 导入材料：`app/commands.py`、`app/static/materials/IMR-*/`
- 搜索性能：`app/search_optimizer.py`、`app/__init__.py`
- 页面改版：`app/templates/`、`app/views.py`、`app/static/`
- API 对接：`app/api.py`
- 国际化：`config/i18n/babel.cfg`、`i18n/messages.pot`、`app/translations/`
- 测试/连通：`tests/`、`scripts/`

---

本文仅引用仓库中已存在的文件与目录，若后续新增模块（如更细粒度的解析/分析组件），建议更新本图例并补充调用链说明。
