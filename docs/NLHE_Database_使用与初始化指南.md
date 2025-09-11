# NLHE_Database 使用与初始化指南（Ubuntu）

本指南面向运维与开发人员，详细说明在 Ubuntu 环境下的项目部署、初始化、数据导入、国际化（i18n）流程、网站使用与编辑、以及搜索缓存的运维操作。所有命令均以 Ubuntu 为默认运行环境，若与 Windows 有差异会单独标注。

- 相关源码位置：`app/`、`migrations/`、`scripts/`、`app/templates/`、`app/static/`
- 关键参考文件：
  - `README.md`
  - `app/commands.py`（CLI 命令定义）
  - `config/i18n/babel.cfg`（Babel 抽取配置）
  - `app/__init__.py`（应用工厂，已集成搜索缓存失效与运维 CLI）

---

## 1. 环境准备（Ubuntu）

- Python 版本：3.8+（建议 3.10/3.11）
- 数据库：SQLite 3（默认）
- 建议使用虚拟环境

```bash
# 进入项目根目录
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

- 环境变量文件
  - `.env`、`.flaskenv` 可用于配置 Flask 环境、密钥等（请勿提交敏感信息）。

- 字体与静态资源
  - 验证码字体必须存在：`app/static/fonts/DejaVuSans-Bold.ttf`、`app/static/fonts/DejaVuSans.ttf`
  - 推荐使用脚本下载：
    ```bash
    python scripts/download_fonts.py
    ```

---

## 2. 启动方式

- 开发模式
  ```bash
  # 确保已激活虚拟环境
  export FLASK_APP=run.py
  export FLASK_ENV=development
  flask run  # http://127.0.0.1:5000
  ```

- 生产部署
  - WSGI 入口：`wsgi.py`
  - 可结合 Gunicorn/Supervisor/Systemd/Nginx 等进行部署
  - 建议将字体文件随镜像或发布产物一并打包

---

## 3. 数据库初始化与迁移（CLI）

以下命令由 `app/commands.py` 提供，需在项目根目录、激活虚拟环境下执行。

- 初始化数据库（创建所有表）
  ```bash
  flask initdb
  ```
  - 重新创建（会删除现有数据）
    ```bash
    flask initdb --drop
    ```

- 通过 Alembic 迁移（如果使用 Flask-Migrate 流程）
  ```bash
  flask db upgrade
  # 如需创建迁移脚本
  # flask db migrate -m "message"
  ```

- 一次性初始化并从 JSON 导入（多场景工具）
  ```bash
  # 正常模式：从目录递归导入 JSON（默认 app/static/materials）
  flask initialize_database --json-dir app/static/materials

  # 测试模式：从 CIF 直接创建材料记录（仅当 --json-dir 指向 app/static/structures 时生效）
  flask initialize_database --drop --json-dir app/static/structures --test
  ```
  - 逻辑摘要（见 `initialize_database()`）：
    - 可选 `--drop` 清空并重建表
    - 正常模式递归扫描 `--json-dir` 下符合 `IMR-*/**.json` 的材料，根据目录名推断 `IMR-<id>`
    - 优先从 `structure/*.cif` 提取化学式命名材料；失败则退回 `Material_<IMR-id>`
    - 导入完成后自动运行批量能带分析，填充 `band_gap` 与 `materials_type`

- 批量导入材料数据（常用，适配「目录/IMR-*/sc_data/data.json + structure/*.cif」结构）
  ```bash
  # 目录默认 app/static/materials，可自定义
  flask import-materials --dir app/static/materials
  ```
  - 逻辑摘要（见 `import_materials_data()`）：
    - 遍历 `IMR-*` 目录
    - 解析 `structure/*.cif` 获取化学式、空间群；若失败再尝试 `sc_data/data.json` 的 `formula`
    - 创建或更新 `Material` 记录
    - 完成后批量能带分析，填充 `band_gap` 与 `materials_type`

- 检查数据库结构
  ```bash
  flask check-db-structure
  ```

- 兼容性辅助命令（仅排查用）
  ```bash
  # 提示如何移除某些 NOT NULL 约束（SQLite 限制）
  flask update_nullable_columns

  #（若存在）迁移用户表以包含 email 字段
  flask migrate-users-email
  ```

---

## 4. 用户与权限管理（CLI）

- 创建管理员（推荐）
  ```bash
  flask admin
  # 按提示输入 username / email / password
  ```

- 添加用户（含角色）
  ```bash
  flask user-add <email> <username> <password> [role]
  # role 可为 admin 或 user，默认 user
  ```

- 成员导入
  ```bash
  flask import-member --info path/to/member.json --photo path/to/photo.jpg
  # JSON 字段示例：name、title、bio、achievements（数组）
  ```

- 权限说明
  - 管理员可访问材料新增/编辑、导入、删除等敏感操作
  - 普通用户可浏览、搜索、下载等只读操作

---

## 5. 搜索缓存运维（CLI & 机制）

- 机制说明
  - 在 `app/__init__.py` 中已注册 `register_material_cache_invalidation()`（位于 `app/search_optimizer.py`）
  - 当 `Material` 数据被插入、更新或删除时，会自动失效搜索缓存，确保前台结果不陈旧

- 观测与清理（CLI）
  ```bash
  # 命中率、大小等统计
  flask search-cache-stats

  # 手动清理
  flask clear-search-cache
  ```

-（可选）仅管理员可见的缓存统计只读接口（文档）
  - 建议路由：`/admin/cache/search-stats`，返回 JSON（命中数、未命中数、大小、键数量等）
  - 鉴权：复用现有登录 + 角色校验（仅 `role=admin` 放行）
  - 安全：仅返回非敏感聚合信息；禁止暴露具体缓存键内容
  - 部署：建议仅在内网或启用强访问控制后开放

---

## 6. 网站使用与编辑功能

- 登录与权限
  - 支持角色控制；管理员可访问敏感页面

- 材料浏览、搜索与过滤
  - 列表页支持分页、关键词、结构/能带相关过滤

- 材料新增（参考 `app/views.py: add()`）
  - 上传内容：`structure_file`（CIF）、能带文件、属性 JSON、Shift Current 文件
  - 系统会解析化学式、空间群，并保存到对应目录

- 材料编辑（参考 `app/views.py: edit()`）
  - 支持替换上传文件并自动更新材料名称、对称信息

- 3D 可视化与 API（参考 `app/api.py`）
  - 获取结构：`GET /api/structure/<int:material_id>`（返回结构 JSON）
  - 上传结构：`POST /api/structure/upload/<int:material_id>`（更新材料名称）
  - 超晶胞等转换：见相关 API 端点说明

---

## 7. 国际化（i18n）工作流（完整命令模板）

- 目录约定
  - 抽取配置：`config/i18n/babel.cfg`
  - 模板文件：`i18n/messages.pot`
  - 语言目录：`app/translations/<lang>/LC_MESSAGES/messages.po|.mo`

- 抽取模板（扫描源码与模板）
  ```bash
  pybabel extract -F config/i18n/babel.cfg -o i18n/messages.pot .
  ```

- 更新现有语言（示例：中文 zh）
  ```bash
  pybabel update -i i18n/messages.pot -d app/translations -l zh
  ```

- 初始化新语言（示例：英文 en；若需要新增）
  ```bash
  pybabel init -i i18n/messages.pot -d app/translations -l en
  ```

- 编译翻译（生成 .mo 文件）
  ```bash
  pybabel compile -d app/translations
  # 开发阶段可允许模糊条目：
  # pybabel compile -d app/translations --use-fuzzy
  ```

- 配置文件参考：`config/i18n/babel.cfg`
  ```ini
  [python: app/**.py]

  [jinja2: app/templates/**.html]
  extensions=jinja2.ext.do,jinja2.ext.loopcontrols
  ```

- 常见问题
  - 新增文案未被抽取：确认是否使用了 `_()`、`gettext()`、`lazy_gettext()` 等标记
  - 模板路径不生效：检查 `babel.cfg` 与命令中的工作目录是否为项目根目录
  - 编译失败：通常是 `.po` 语法错误或占位符不匹配，修复后重跑 `pybabel compile`

---

## 8. 数据目录结构与导入约定

- 材料目录：`app/static/materials/IMR-XXXXXXXX/`
  - `structure/*.cif`：晶体结构（用于解析化学式、空间群）
  - `band/`：能带数据（DAT 等）
  - `sc/`：Shift Current 数据
  - `sc_data/data.json`：结构化元数据与数值属性

- 导入建议
  - 先保证目录命名规范与文件完整性
  - 大批量导入前先在测试环境执行 `flask import-materials` 验证

---

## 9. 备份与运维建议

- 数据库备份：`instance/app.db` 定期备份
- 迁移前先备份数据库与 `app/static/materials` 目录
- 日志与监控：在生产环境接入进程管理与反向代理日志

---

## 10. 故障排查（FAQ）

- 导入失败
  - 路径/权限：确认 `--dir` 或 `--json-dir` 指向有效路径且可读
  - JSON 结构：`json.load` 失败通常为格式错误
  - CIF 解析：若失败会回退到默认名称；同时空间群可能为 `Unknown`

- 字体加载问题
  - 使用 `python scripts/download_fonts.py` 预置字体，避免运行时下载
  - 启动前校验字体二进制与 Pillow 可读性

- 缓存问题
  - 使用 `flask search-cache-stats` 查看命中率与大小
  - `flask clear-search-cache` 手动清理

---

## 附：完整 CLI 速查（来自 `app/commands.py` 与应用工厂）

```bash
# 数据库
flask initdb [--drop]
flask db upgrade
flask initialize_database [--drop] [--json-dir <dir>] [--test]

# 数据导入
flask import-materials --dir <materials_dir>

# 用户与成员
flask admin
flask user-add <email> <username> <password> [role]
flask import-member --info <json> --photo <file>

# 结构检查与辅助
flask check-db-structure
flask update_nullable_columns
flask migrate-users-email

# 搜索缓存（应用工厂中新增）
flask search-cache-stats
flask clear-search-cache
```

---

以上流程经过项目源码与现有 README 的交叉验证，适配 Ubuntu 部署场景。若在特定集群/容器环境中运行，请结合本指南与企业内部规范进行加固与扩展。

## 11. Nginx 部署示例（Ubuntu）

说明：本节提供反向代理到 Gunicorn 的通用 Nginx 配置，包含静态资源加速、上传大小、超时、基础安全头、Gzip、缓存策略与 HTTPS 模板。请根据实际域名与监听端口替换占位符。

- 约定
  - Flask/Gunicorn 服务监听：`127.0.0.1:8000`
  - 项目根目录：`/opt/NLHE_Database`
  - 静态资源：`/opt/NLHE_Database/app/static/`
  - 域名占位：`example.com`

- 创建站点配置
  - 文件：`/etc/nginx/sites-available/nlhe_database`
  - 软链：`/etc/nginx/sites-enabled/nlhe_database`

示例一：HTTP（可用于内网或测试环境）
```nginx
# /etc/nginx/sites-available/nlhe_database
upstream nlhe_gunicorn {
    server 127.0.0.1:8000;  # Gunicorn 监听地址
    keepalive 32;
}

server {
    listen 80;
    server_name example.com;

    # 最大上传尺寸（根据需求调整）
    client_max_body_size 20m;

    # Gzip 压缩
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript application/xml+rss application/xml application/octet-stream image/svg+xml;
    gzip_vary on;

    # 静态资源直接由 Nginx 提供
    location /static/ {
        alias /opt/NLHE_Database/app/static/;
        # 缓存策略（可按需调整）
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        access_log off;
    }

    # 健康检查（可选）
    location = /healthz {
        return 200 "ok";
        add_header Content-Type text/plain;
    }

    # 反向代理到 Gunicorn
    location / {
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout  120s;
        proxy_connect_timeout 30s;
        proxy_send_timeout 120s;

        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_pass http://nlhe_gunicorn;
    }

    # 基础安全头（按需增减）
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 日志（按需调整）
    access_log /var/log/nginx/nlhe_access.log;
    error_log  /var/log/nginx/nlhe_error.log warn;
}
```

示例二：HTTPS（建议生产使用，配合 Certbot）
```nginx
# HTTP -> HTTPS 跳转
server {
    listen 80;
    server_name example.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}

# HTTPS 主站
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    client_max_body_size 20m;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript application/xml+rss application/xml application/octet-stream image/svg+xml;
    gzip_vary on;

    location /static/ {
        alias /opt/NLHE_Database/app/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000, immutable";
        access_log off;
    }

    location = /healthz {
        return 200 "ok";
        add_header Content-Type text/plain;
    }

    location / {
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout  120s;
        proxy_connect_timeout 30s;
        proxy_send_timeout 120s;

        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_pass http://nlhe_gunicorn;
    }

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header X-XSS-Protection "1; mode=block" always;

    access_log /var/log/nginx/nlhe_access.log;
    error_log  /var/log/nginx/nlhe_error.log warn;
}
```

可选：限流与防护（防暴力登录/爬虫）
```nginx
# /etc/nginx/nginx.conf http{} 中定义
limit_req_zone $binary_remote_addr zone=login_zone:10m rate=10r/m;

# 站点 server{} 中使用
location /login {
    limit_req zone=login_zone burst=20 nodelay;
    proxy_pass http://nlhe_gunicorn;
}
```

- 启动/验证
```bash
sudo ln -s /etc/nginx/sites-available/nlhe_database /etc/nginx/sites-enabled/nlhe_database
sudo nginx -t
sudo systemctl reload nginx
```

- Gunicorn 服务（示例，若需要）
```bash
# 项目根：/opt/NLHE_Database
# 安装：pip install gunicorn

# 直接启动（测试）
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app

# systemd 单元（/etc/systemd/system/nlhe.service）
[Unit]
Description=NLHE_Database gunicorn service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/NLHE_Database
Environment="PATH=/opt/NLHE_Database/.venv/bin"
ExecStart=/opt/NLHE_Database/.venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target

# 生效
sudo systemctl daemon-reload
sudo systemctl enable nlhe
sudo systemctl start nlhe

## 12. 快速上手（10 分钟体验）

说明：本节面向首次接触者，尽量用最少步骤跑通网站、创建管理员、导入一条材料数据，验证基本功能。

- 基础准备
  - 推荐系统：Ubuntu 20.04/22.04 LTS
  - 必备软件：Python 3.9+、Git、GCC/Make、Nginx（生产）
  - 克隆项目：`git clone <repo> /opt/NLHE_Database`

- 创建虚拟环境并安装依赖
```bash
cd /opt/NLHE_Database
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

- 准备最小化配置（开发）
```bash
cat > .flaskenv <<'EOF'
FLASK_APP=wsgi.py
FLASK_ENV=development
EOF

cat > .env <<'EOF'
SECRET_KEY="请替换为强随机值"
SQLALCHEMY_DATABASE_URI="sqlite:///instance/app.db"
LANGUAGES="en,zh"
EOF
```

- 初始化数据库与管理员
```bash
flask initdb
flask admin   # 按提示设置用户名/邮箱/密码
```

- 准备字体与静态资源
```bash
mkdir -p app/static/fonts
# 确保存在下列字体（验证码用），可用脚本或自行下载
# app/static/fonts/DejaVuSans.ttf
# app/static/fonts/DejaVuSans-Bold.ttf
```

- 启动与验证
```bash
flask run  # http://127.0.0.1:5000
# 或（生产预览）
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
```

- 导入一条示例材料（可选）
```bash
# 确保 app/static/materials/IMR-0001/ 结构齐全后：
flask import-materials --dir app/static/materials
```

## 13. 环境与依赖细化（系统/科学计算/前端/字体）

说明：本节细化系统包与科学计算库的安装建议，降低编译/运行故障概率。

- 系统依赖（Ubuntu）
```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential \
  libopenblas-dev liblapack-dev libspglib-dev \
  libfreetype6-dev pkg-config
```

- Python 科学计算库注意事项
  - `numpy`/`scipy`：优先使用二进制轮子；若需源编译，确保 BLAS/LAPACK 完整。
  - `pymatgen`/`spglib`：涉及材料学解析与空间群分析，版本建议与 `requirements.txt` 保持一致。
  - 安装顺序建议：升级 `pip` → 安装 `numpy` → 其他科学库 → 业务依赖。

- 字体与验证码
  - 必备：`app/static/fonts/DejaVuSans.ttf`、`DejaVuSans-Bold.ttf`
  - 若缺失将导致验证码生成异常（参见“故障定位清单”）。

- 前端静态库
  - 由模板在 `app/static/js/` 引用（如 Three.js/Plotly.js）。
  - 若路径改动，需同步更新对应模板（如 `app/templates/main/database.html`）。

## 14. 配置与目录规范（.env 示例/权限）

说明：本节明确环境变量与关键目录权限，避免运行期权限问题与路径不一致。

- `.env`（生产）示例
```dotenv
FLASK_ENV=production
SECRET_KEY="请替换为强随机值"
SQLALCHEMY_DATABASE_URI="sqlite:///instance/app.db"
LANGUAGES="en,zh"
PREFERRED_URL_SCHEME="https"
```

- `.flaskenv`（开发）示例
```dotenv
FLASK_APP=wsgi.py
FLASK_ENV=development
```

- 目录与权限建议
  - `instance/`：存放数据库/运行态数据，仅应用用户可写（示例：`chown -R www-data:www-data instance/`，`chmod 750`）。
  - `app/static/materials/IMR-*/`：材料数据归档目录，导入/编辑会写入；确保运行用户具备写权限。
  - 若 Nginx 与 Gunicorn 运行不同用户，请统一对写目录授权。

## 15. 初始化与导入全流程剧本（命令/预期/常见问题）

说明：从零到可用的一次性剧本，包含每步预期与常见故障提示。

```bash
# 1) 环境
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip && pip install -r requirements.txt

# 2) 配置
cp .env.example .env  # 再按需修改
echo -e "FLASK_APP=wsgi.py\nFLASK_ENV=development" > .flaskenv

# 3) 初始化数据库
flask initdb

# 4) 创建管理员
flask admin

# 5) 导入材料数据（目录需包含 IMR-*/ 子目录与必要文件）
flask import-materials --dir app/static/materials

# 6) 一次性初始化并导入（可选）
flask initialize_database --json-dir app/static/materials

# 7) 结构一致性检查
flask check-db-structure

# 8) 启动
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
```

- 预期结果与提示
  - `initdb`：生成/迁移数据库；日志出现成功提示。
  - `admin`：交互式创建管理员；可登录后台。
  - `import-materials`：遍历目录、导入材料、触发能带分析（若配置）。

## 16. 缓存与 Valkey/Redis（安装/连通/CLI 运维）

说明：搜索缓存用于降低重复查询成本；材料数据变更时通过 SQLAlchemy 事件自动失效。

- 安装与启动（示例：Valkey）
```bash
sudo ./scripts/install_valkey.sh  # 或参考企业内置 Redis 服务
```

- 连通性与安全
  - 建议仅监听 `127.0.0.1`，生产环境增加密码与网络层 ACL。
  - 应用侧连接参数放置于 `.env`（如使用）。

- CLI 运维
```bash
flask search-cache-stats   # 查看缓存键与命中概况
flask clear-search-cache   # 清理搜索缓存键
```

- 自动失效
  - `app/__init__.py` 调用 `register_material_cache_invalidation()`，当 `Material` 新增/编辑/删除时自动清理相关键。

## 17. 备份与恢复（数据库/静态/翻译）

说明：确保可回滚与灾备恢复。建议例行备份并校验可恢复性。

- 备份示例
```bash
tar czf backup-$(date +%F).tgz \
  instance/ \
  app/static/materials/ \
  app/translations/
```

- 恢复示例（停机或只读模式）
```bash
systemctl stop nlhe || true
tar xzf backup-YYYY-MM-DD.tgz -C /opt/NLHE_Database
systemctl start nlhe || flask run
```

## 18. 性能与安全加固（进程/超时/上传/安全头）

说明：结合第 11 章 Nginx 模板进行整体优化。

- Gunicorn 参数建议
```bash
gunicorn -w 4 --threads 2 -t 120 -b 127.0.0.1:8000 wsgi:app
```

- 上传与超时
  - Nginx `client_max_body_size` 与 `proxy_read_timeout` 同步调整。

- 基础安全
  - 采用 HTTPS 与 HSTS（参见第 11 章）。
  - 管理路由可结合限流/二次校验。

## 19. 故障定位清单（常见报错与解决路径）

说明：快速定位问题根因，避免盲目修改。

- 数据库相关
  - 症状：无法连接/迁移失败
  - 排查：检查 `SQLALCHEMY_DATABASE_URI`、执行 `flask db upgrade`、查看 `migrations/` 日志

- 字体/验证码
  - 症状：验证码显示异常
  - 排查：确认 `app/static/fonts/DejaVuSans*.ttf` 存在与权限

- CIF 解析
  - 症状：导入失败/化学式解析为空
  - 排查：核对 CIF 格式/编码；查看 `extract_chemical_formula_from_cif()` 调用链与日志

- 缓存与连通
  - 症状：缓存命中率异常/连不通
  - 排查：检查 Valkey/Redis 服务与网络；运行 `tests/test_valkey_connection.py`

- 权限/写入
  - 症状：上传/导入报权限错误
  - 排查：`instance/` 与 `app/static/materials/` 的属主/权限是否与运行用户一致

## 20. 附录（CLI 速查/.env 模板/目录树）

- CLI 速查（来自 `app/commands.py`，仅列出已实现命令）
```bash
flask initdb [--drop]
flask admin
flask user-add
flask import-materials --dir <path>
flask initialize_database [--drop] [--json-dir <dir>] [--test]
flask check-db-structure
flask update_nullable_columns
flask migrate-users-email
flask search-cache-stats
flask clear-search-cache
```

- `.env` 最小模板
```dotenv
SECRET_KEY="请替换为强随机值"
SQLALCHEMY_DATABASE_URI="sqlite:///instance/app.db"
LANGUAGES="en,zh"
```

- 目录树（摘录，实际以仓库为准）
```
app/
  __init__.py
  models.py
  views.py
  api.py
  search_optimizer.py
  templates/
    main/database.html
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
i18n/
  messages.pot
migrations/
scripts/
tests/
run.py
wsgi.py

### 20.1 模块关系简图与跳转索引

 本小节给出详细、可操作的模块关系图，并提供到关键文件/文档的跳转索引，便于快速定位与排查。

 - 参考全文档：`docs/NLHE_Database_文件系统图例与模块依赖.md`
 - 关联源码：`app/__init__.py`、`app/commands.py`、`app/search_optimizer.py`、`app/api.py`、`app/views.py`、`app/templates/`、`app/static/`

 1) 全站总体关系图（入口/路由/模板/静态/API/缓存）
 ```text
 浏览器(用户)
   ├─ 页面路由请求 ──> app/views.py ───────────┬─ 渲染模板: app/templates/*
   │                                           └─ 读取静态: app/static/*
   └─ 异步/数据请求 ─> app/api.py ───────────────> 返回 JSON 数据
 
 WSGI 入口
   └─ wsgi.py → app/__init__.py:create_app()
                  ├─ 注册蓝图/扩展/登录/i18n
                  ├─ 挂载 CLI: app/commands.py
                  ├─ 注册缓存失效: app/search_optimizer.py
                  └─ 绑定数据库与迁移
 
 数据与文件
   ├─ 关系型数据: instance/app.db (SQLite)
   ├─ 材料文件: app/static/materials/IMR-*/ (cif/sc/band/json)
   └─ 字体/前端: app/static/fonts, js, css
 ```
 
 2) 初始化与批量导入流程（CLI 主导）
 ```text
 管理员/CI 执行 CLI (flask ...)
   ├─ initdb → 创建/迁移 DB → instance/app.db
   ├─ admin → 创建管理员用户
   ├─ import-materials --dir app/static/materials
   │     └─ 遍历 IMR-*/ → 读取 cif/json/sc → 写 DB
   └─ initialize_database --json-dir DIR (可选)
 
 导入后
   ├─ 可能触发能带分析: app/band_analyzer.py (若在 commands 中调用)
   └─ SQLAlchemy 事件触发 → app/search_optimizer.py → 失效相关搜索缓存
 
 关键文件
   ├─ app/commands.py (导入/初始化/用户/检查)
   ├─ app/static/materials/IMR-*/ (材料目录结构)
   └─ app/__init__.py (注册 CLI 与缓存失效)
 ```
 
 3) 搜索缓存与失效机制（写后读一致）
 ```text
 读路径（有缓存）
   用户检索 → 视图/服务查询 → 命中缓存键 → 返回结果更快
 
 写路径（自动失效）
   新增/编辑/删除 Material → 触发 SQLAlchemy 事件
     → app/search_optimizer.py 中的失效回调
       → 删除/更新相关搜索键
 
 关键位置
   ├─ app/search_optimizer.py: register_material_cache_invalidation()
   └─ app/__init__.py: 在应用启动时注册上述监听
 
 运维命令
   ├─ flask search-cache-stats  # 观测缓存
   └─ flask clear-search-cache  # 清理缓存
 ```
 
 4) API 与前端可视化数据流
 ```text
 前端 JS (如 crystal-viewer.js, band-plot.js)
   └─ 请求 /api/structure/<id> 或相关数据端点
        → app/api.py:get_structure() 读取材料结构
            └─ 从 app/static/materials/IMR-*/ 或解析器读取
        → 返回 JSON
 
 模板/页面
   ├─ app/templates/main/database.html (入口/汇总)
   └─ app/templates/components/periodic_table.html (组件)
 
 关键文件
   ├─ app/api.py (REST 接口)
   ├─ app/templates/* (Jinja 页面)
   └─ app/static/js/* (前端渲染/交互)
 ```
 
 5) 国际化（i18n）工作流
 ```text
 源码与模板 → 根据 config/i18n/babel.cfg 抽取
   ├─ 生成/更新: i18n/messages.pot
   ├─ 合并到: app/translations/<lang>/LC_MESSAGES/messages.po
   └─ 编译: messages.mo → 运行期使用
 
 运行期
   app/__init__.py 中启用 Flask-Babel
   模板与视图使用 _()/trans 指令
 ```
 
 6) 跳转索引（按任务定位）
 - 搭建/运行：`wsgi.py`、`run.py`、`docs/NLHE_Database_使用与初始化指南.md`
 - 导入材料：`app/commands.py`、`app/static/materials/IMR-*/`
 - 搜索性能：`app/search_optimizer.py`、`app/__init__.py`
 - 页面改版：`app/templates/`、`app/views.py`、`app/static/`
 - API 对接：`app/api.py`
 - 国际化：`config/i18n/babel.cfg`、`i18n/messages.pot`、`app/translations/`
 - 体系结构详解：`docs/NLHE_Database_文件系统图例与模块依赖.md`

### 20.2 IMR-* 材料目录结构详图

说明：材料相关的结构/能带/属性/Shift Current 等文件以材料 ID 作为目录名归档在 `app/static/materials/` 下。下图为典型目录组织与文件职责，实际以数据导入规范与现有文件为准。

1) 目录树（示例）
```text
app/static/materials/
  IMR-0001/
    structure/                 # 结构文件目录（CIF 等）
      sample.cif               # 结构源文件，供解析化学式/对称性
    band/                      # 能带相关数据（可选，具体格式按项目现行）
      band.dat                 # 示例：能带数据（命名仅示意）
    sc_data/                   # Shift Current 数据目录（如存在）
      data.json                # Shift Current 核心数据文件
    properties.json            # 属性汇总（可选：材料元数据/标签等）
    uploads/                   # 其他由表单上传的原始文件（可选）
```

2) 文件职责与引用关系
- 结构（`structure/*.cif`）
  - 被谁使用：
    - `app/views.py: add()/edit()` 在上传/编辑时保存与解析
    - 解析化学式：`extract_chemical_formula_from_cif()`（由相关导入/视图逻辑调用）
    - 可能被 `app/api.py:get_structure()` 或解析器读取用于 JSON 输出

- 能带（`band/*`）
  - 被谁使用：
    - 导入/分析：`app/commands.py`（批量导入流程中如有分析步骤则读取）
    - 前端可视化：对应 JS 使用 API/静态资源进行渲染（按模板与前端实现）

- Shift Current（`sc_data/data.json`）
  - 被谁使用：
    - 视图/前端：用于可视化与查询（按前端组件实现）

- 属性（`properties.json`，可选）
  - 被谁使用：
    - 导入/视图：用于补充材料标签/描述等元信息

3) 命名/校验建议
- 目录名：`IMR-<材料ID>`，例如 `IMR-0001`（与数据库记录一致）
- 结构文件：优先使用规范的 CIF 扩展名，文件编码为 UTF-8
- 校验要点：
  - 结构解析失败时，检查 CIF 格式与非法字符
  - 目录权限需允许运行用户写入（导入/编辑）

4) 与导入/编辑/API 的关系图（概念）
```text
app/static/materials/IMR-*/
  ├─ structure/*.cif ─┬─> 视图 add/edit 解析 → 更新 models.Material → DB 提交
  │                    └─> API get_structure() → 返回 JSON（前端渲染）
  ├─ band/*          ───> 导入/分析流程（CLI）与前端图形组件
  └─ sc_data/data.json ─> 前端 Shift Current 可视化
```

5) 最小必需文件清单（勾选表）
 - [ ] 目录已创建：`app/static/materials/IMR-<id>/`
 - [ ] 至少一个结构文件：`structure/*.cif`（UTF-8，格式可被解析）
 - [ ] 目录可写权限：运行用户可写 `IMR-<id>/` 及子目录
 - [ ] 如需验证码：`app/static/fonts/DejaVuSans.ttf`、`DejaVuSans-Bold.ttf` 存在
 - [ ] 可选：`sc_data/data.json`（若前端需要 Shift Current 可视化）
 - [ ] 可选：`band/*`（若需要能带可视化/分析）
 - [ ] 可选：`properties.json`（补充标签/描述等元信息）

### 20.3 后台添加/编辑时序图（views.add/edit）

说明：本节以详尽时序展示“后台表单上传 → 保存 → 解析 → DB 提交 → 缓存失效 → 页面返回”的全链路，便于排查问题与理解触发点。

1) 成功路径（简要时序）
```text
用户(管理员)
  └─ 提交表单(含 structure_file / band / 属性JSON / SC 数据 等)
     → app/views.py:add() 或 edit(material_id)
        1) 接收文件(Flask request.files)
        2) 保存到 app/static/materials/IMR-<id>/*
        3) 解析结构
           ├─ 从 <dir>/structure/*.cif 读取
           └─ 提取化学式/对称信息: extract_chemical_formula_from_cif()
        4) 更新数据库 models.Material 字段
        5) db.session.commit()
        6) SQLAlchemy 事件触发 → app/search_optimizer.py 失效相关搜索缓存
        7) 返回视图/重定向 → 页面渲染最新数据
```

2) 失败与回滚（常见分支）
```text
A. 结构解析失败
   - 日志提示：CIF 格式/编码异常
   - 处理：返回表单并提示；保留原始上传以便排查

B. 权限/写入失败
   - 症状：无法写入 app/static/materials/IMR-*/ 或 instance/
   - 处理：检查属主/权限；按第 14 章建议修正

C. 数据库提交异常
   - 症状：commit 报错导致页面 500
   - 处理：回滚事务，校验字段与约束；检查 migrations 与模型一致性

D. 缓存未失效导致旧结果
   - 症状：页面仍显示旧搜索结果
   - 处理：确认 app/__init__.py 已注册 register_material_cache_invalidation()
           运维可执行：flask clear-search-cache
```

3) 涉及关键文件与函数索引
- 视图：`app/views.py: add()`、`app/views.py: edit(material_id)`
- 解析：`extract_chemical_formula_from_cif()`（由视图/导入流程调用）
- 模型：`app/models.py` 中 `Material` 及相关关系
- 事件与缓存：`app/search_optimizer.py: register_material_cache_invalidation()`（由 `app/__init__.py` 注册）
- 静态目录：`app/static/materials/IMR-*/`

4) 字段级变更与缓存键影响清单（参考）
 - 变更项：结构文件（`structure/*.cif`）
   - 影响：名称/化学式/对称信息可能变化 → 应失效相关搜索缓存键
 - 变更项：材料展示名称/化学式/空间群等检索字段
   - 影响：搜索结果与列表排序/过滤 → 应失效相关搜索缓存键
 - 变更项：能带数据（`band/*`）
   - 影响：依赖能带的查询与可视化缓存（若存在）
 - 变更项：Shift Current 数据（`sc_data/data.json`）
   - 影响：依赖 SC 数据的查询与可视化缓存（若存在）
 - 变更项：属性（`properties.json`）
   - 影响：涉及属性筛选/标签的查询缓存（若存在）
 - 机制说明：
   - `app/__init__.py` 在应用启动时调用 `register_material_cache_invalidation()`
   - 通过 SQLAlchemy 事件监听 `Material` 的新增/编辑/删除，自动失效相关搜索缓存键
   - 如遇异常，可用 CLI 强制清理：`flask clear-search-cache`
