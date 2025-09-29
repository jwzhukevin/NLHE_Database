# NLHE_Database - 材料数据库管理系统

## 项目概述

NLHE_Database是一个专为材料科学研究设计的综合数据库管理系统，用于高效存储、管理和可视化材料数据。系统基于Flask框架开发，提供直观的Web界面，支持晶体结构的3D可视化、能带结构分析以及批量数据处理功能。

## 核心功能

- **材料数据管理**：完整的CRUD操作，支持材料记录的增删改查
- **高级搜索与过滤**：多维度过滤系统，支持按名称/化学式/状态/属性等条件筛选
- **晶体结构可视化**：基于Three.js的交互式3D晶体结构查看器，支持旋转、缩放和超胞生成
- **能带结构分析**：能带数据的可视化显示和分析工具
- **文章内容管理**：支持相关研究文章的编辑和发布
- **批量数据处理**：支持CSV和JSON格式的数据批量导入导出
- **用户认证与权限**：多级权限控制系统，支持管理员账户和普通用户区分
- **安全防护措施**：IP封锁保护机制，防止暴力登录尝试
- **文件格式转换**：支持TXT文件转换为DAT和DOCX格式的工具

## 技术架构

### 后端框架
- **Flask**：轻量级Web应用框架，采用工厂模式组织代码
- **SQLAlchemy ORM**：提供数据库抽象层，简化数据操作
- **Flask-Login**：管理用户会话和认证
- **Flask-Migrate**：处理数据库模式迁移

### 前端技术
- **Bootstrap**：响应式UI组件库
- **Three.js**：WebGL 3D渲染引擎，用于晶体结构可视化
- **Plotly.js**：交互式科学图表库，用于能带数据和SC数据可视化
- **JavaScript**：实现客户端交互和动态功能

### 科学计算
- **Pymatgen**：材料基因组工具包，处理晶体结构和分析
- **NumPy/SciPy**：科学计算库，提供数值计算支持
- **Spglib**：空间群计算，用于晶体对称性分析


## 项目结构

```
NLHE_Database/
├── app/                   # 应用主目录
│   ├── __init__.py        # 应用初始化（工厂模式）
│   ├── models.py          # 数据模型定义
│   ├── views.py           # 视图函数和路由
│   ├── api.py             # RESTful API接口
│   ├── articles.py        # 文章管理模块
│   ├── program.py         # 文件格式转换工具模块
│   ├── structure_parser.py # 结构文件解析工具
│   ├── commands.py        # CLI命令工具
│   ├── static/            # 静态资源
│   │   ├── css/           # 样式表
│   │   ├── js/            # JavaScript文件
│   │   │   ├── crystal-viewer.js  # 晶体结构可视化
│   │   │   ├── band-plot.js       # 能带图绘制
│   │   │   └── sc-plot.js         # SC结构图绘制
│   │   ├── images/        # 图片资源
│   │   └── materials/     # 材料数据文件（按IMR-ID组织）
│   └── templates/         # HTML模板
├── instance/              # Flask实例文件夹
│   └── app.db             # SQLite数据库文件
├── migrations/            # 数据库迁移脚本
├── NLHE/                  # Python虚拟环境
├── requirements.txt       # 依赖包清单
├── wsgi.py                # WSGI应用入口
├── config.py              # 配置文件
├── initdb.sh              # 数据库初始化脚本
└── web.sh                 # Web服务启动脚本
```

## 安装与部署

### 环境要求
- Python 3.8+
- SQLite 3
- 现代浏览器（推荐Chrome、Firefox或Edge）

### 快速启动
1. **克隆仓库**
   ```bash
   git clone https://github.com/your-username/NLHE_Database.git
   cd NLHE_Database
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv NLHE
   source NLHE/bin/activate  # Linux/Mac
   # 或
   NLHE\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **初始化数据库**
   ```bash
   ./initdb.sh
   ```

5. **创建管理员账户**
   ```bash
   ./admin.sh
   ```

6. **启动应用**
   ```bash
   ./web.sh
   ```
   访问 http://localhost:5000 开始使用

## 数据组织

系统采用结构化的方式组织材料数据：

- 每个材料分配唯一的IMR格式ID（例如：IMR-00000001）
- 晶体结构（CIF格式）存储在对应的structure目录中
- 能带数据（DAT格式）存储在对应的band目录中
- SC数据（DAT格式）存储在对应的sc目录中
- 元数据以JSON格式存储，包含材料的基本属性和计算结果

## 使用指南

### 材料管理
- **浏览材料**：首页提供分页材料列表，支持排序和过滤
- **材料详情**：点击材料名称查看详细信息、结构和能带数据
- **添加/编辑**：管理员可添加新材料或编辑现有材料信息
- **批量操作**：支持数据的批量导入和导出

### 结构可视化
- 3D交互式查看器支持旋转、缩放和平移操作
- 支持生成不同尺寸的超胞结构
- 可选择原胞或常规胞显示模式
- 支持导出为图片格式

### 能带与SC结构分析
- 交互式能带图表，支持高对称点标记和费米能级参考线
- SC结构图表，支持曲线分组和关系分析
- 图表支持缩放、平移和数据提取功能

### 文章管理
- 发布与材料相关的研究文章和报告
- 支持富文本编辑，可插入图片和引用


### 文件格式转换
- 支持TXT文件转换为DAT和DOCX格式
- 简单直观的文件上传和下载界面

## 维护与备份

- 定期备份`instance/app.db`数据库文件
- 系统日志记录在应用实例目录中
- 建议按计划对材料数据进行增量备份

## 开发者说明

- 项目采用工厂模式组织Flask应用结构
- 使用蓝图(Blueprint)分离不同功能模块
- 数据库迁移通过Flask-Migrate管理
- 结构解析模块使用Pymatgen库处理CIF文件

## 技术亮点

- **高效数据处理**：优化的数据库查询和缓存机制
- **交互式可视化**：前端使用WebGL技术实现高性能3D渲染
- **材料ID系统**：采用标准化的材料编码系统（IMR-XXXXXXXX）
- **多层次安全**：包括数据验证、用户认证和防暴力攻击机制

## 许可与贡献

- 项目采用MIT许可证
- 欢迎通过Issue和Pull Request参与贡献
- 开发前请先阅读贡献指南 

## 国际化（i18n）工作流

为保持清晰、专业的目录结构，项目采用以下约定：

- `config/i18n/babel.cfg`：Babel 抽取配置文件
- `i18n/messages.pot`：主翻译模板文件（不要直接编辑 `app/translations/` 下的语言文件结构）
- `app/translations/`：各语言目录，存放 `.po`（可编辑）与 `.mo`（编译产物）

常用命令：

```bash
# 1) 抽取模板（扫描源码与模板）
pybabel extract -F config/i18n/babel.cfg -o i18n/messages.pot .

# 2) 更新现有语言（示例：中文 zh）
pybabel update -i i18n/messages.pot -d app/translations -l zh

# 3) 编译翻译（生成 .mo 文件）
pybabel compile -d app/translations
# 开发调试可允许 fuzzy：
# pybabel compile -d app/translations --use-fuzzy
```

说明：

- 请优先维护 `i18n/messages.pot` 为模板单一来源；根目录旧文件已标记为 Deprecated。
- 若有脚本/CI 仍引用旧路径，请同步更新以避免双源。

## 验证码字体下载与校验

- __放置目录__：`app/static/fonts/`
- __脚本下载（推荐）__：
  ```bash
  python scripts/download_fonts.py
  ```
- __手动下载（可选）__：
  - DejaVuSans-Bold.ttf
    https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans-Bold.ttf
  - DejaVuSans.ttf
    https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans.ttf
  下载后将文件放入 `app/static/fonts/`。

- __快速校验__：确保文件不是 HTML，并能被 Pillow 读取
  ```bash
  # 文件头不应出现 <!DO...（应显示 TrueType 头部）
  head -c 16 app/static/fonts/DejaVuSans-Bold.ttf | hexdump -C
  head -c 16 app/static/fonts/DejaVuSans.ttf       | hexdump -C

  # 类型应为 TrueType/二进制
  file app/static/fonts/DejaVuSans-Bold.ttf
  file app/static/fonts/DejaVuSans.ttf

  # Pillow 实载测试（应从项目目录加载）
  python - <<'PY'
  import os
  from PIL import ImageFont
  d = os.path.realpath(os.path.join('app','static','fonts'))
  for n in ['DejaVuSans-Bold.ttf','DejaVuSans.ttf']:
      p = os.path.join(d,n)
      f = ImageFont.truetype(p,28)
      print('OK:', p, 'loaded_from:', getattr(f,'path',None))
  PY
  ```

说明：验证码优先使用项目目录下的字体文件；如缺失或无效，将尝试系统字体；仍失败时才会触发网络下载。为确保部署可复现，建议随项目一并提供上述 TTF 文件。

## 部署要求（重要）

- __必须随包附带验证码字体文件__（避免依赖系统字体或网络）：
  - `app/static/fonts/DejaVuSans-Bold.ttf`
  - `app/static/fonts/DejaVuSans.ttf`

- __生产环境建议__：
  - 将上述 TTF 文件打包进发布产物或容器镜像（示例 Dockerfile 片段）：
    ```dockerfile
    # 将项目字体复制到镜像内（按你的工作目录调整目标路径）
    COPY app/static/fonts/ /app/app/static/fonts/
    ```
  - 如需严格禁止网络回退，可在环境或实例配置中设置 `ENABLE_FONT_DOWNLOAD=False`，以便缺失字体立即暴露。

- __启动前自检（任选其一）__：
  - 文件类型与文件头应为 TrueType：
    ```bash
    file app/static/fonts/DejaVuSans-Bold.ttf
    head -c 16 app/static/fonts/DejaVuSans-Bold.ttf | hexdump -C  # 应显示 TTF 头部而非 <!DO...
    ```
  - Pillow 实载路径应指向项目目录：
    ```bash
    python - <<'PY'
    import os
    from PIL import ImageFont
    d = os.path.realpath(os.path.join('app','static','fonts'))
    for n in ['DejaVuSans-Bold.ttf','DejaVuSans.ttf']:
        p = os.path.join(d,n)
        f = ImageFont.truetype(p,28)
        print('OK:', p, 'loaded_from:', getattr(f,'path',None))
    PY
    ```

- __CI/CD 建议__：
  - 在流水线中新增检查步骤，缺少上述字体文件时直接失败。
  - 在容器构建阶段完成字体校验，防止运行时回退到系统字体或触发网络下载。

- __运行日志提示__：