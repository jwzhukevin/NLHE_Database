# NLHE_Database - 材料数据库管理系统

## 项目概述

NLHE_Database是一个专为材料科学设计的数据库管理系统，用于存储、管理和可视化材料数据，包括晶体结构、能带结构及各种物理化学属性。系统基于Flask框架开发，提供了直观的Web界面，支持材料数据的添加、编辑、导入、导出和可视化功能。

## 主要功能

- **材料数据管理**：支持添加、编辑、删除材料记录
- **晶体结构可视化**：基于Three.js的交互式3D晶体结构查看器
- **能带结构绘制**：能带数据的可视化显示
- **批量导入导出**：支持CSV和JSON格式的数据批量导入导出
- **用户认证系统**：管理员用户登录及权限控制
- **IP封锁保护**：防止暴力登录尝试的安全措施

## 目录结构

```
NLHE_Database/
├── app/                    # 主应用代码
│   ├── static/             # 静态资源（CSS, JS, 结构文件等）
│   │   ├── materials/      # 材料数据目录
│   │   │   ├── IMR-xxxxxxxx/  # 按ID组织的材料文件夹
│   │   │   │   ├── structure/ # 结构文件目录
│   │   │   │   └── band/      # 能带数据目录
│   ├── templates/          # HTML模板
│   ├── api.py              # API接口
│   ├── commands.py         # 命令行工具
│   ├── models.py           # 数据模型定义
│   ├── structure_parser.py # 结构文件解析工具
│   └── views.py            # 视图函数
├── NLHE/                   # 虚拟环境
├── migrations/             # 数据库迁移文件
├── instance/               # 实例配置
├── data.db                 # SQLite数据库文件
├── requirements.txt        # 依赖包列表
├── initdb.sh               # 数据库初始化脚本
├── web.sh                  # Web服务启动脚本
├── admin.sh                # 管理员账户创建脚本
```

## 技术栈与依赖关系

本项目使用多种Python库和框架协同工作，以下是主要依赖及其功能:

### 核心框架
- **Flask (2.2.5)**: 轻量级Web应用框架，提供路由、模板渲染和请求处理
- **Flask-SQLAlchemy (3.0.3)**: 集成SQLAlchemy的Flask扩展，提供ORM数据访问
- **Flask-Login (0.6.3)**: 用户认证与会话管理扩展
- **Flask-Migrate (4.1.0)**: 数据库迁移工具，基于Alembic

### 数据处理与科学计算
- **NumPy (2.2.4)**: 科学计算基础库，处理晶体和能带数据的数值运算
- **Pandas (2.2.3)**: 用于材料数据的表格处理和批量导入导出
- **SciPy (1.15.2)**: 提供科学计算和优化功能
- **Pymatgen (2025.3.10)**: 材料基因组工具包，用于晶体结构分析和处理
- **Spglib (2.6.0)**: 结晶学空间群计算库，与Pymatgen配合使用

### 可视化工具
- **Matplotlib (3.10.1)**: 静态图表生成库，用于能带结构绘制
- **Plotly (6.0.1)**: 交互式图表库，增强数据可视化体验

### 安全与认证
- **Bcrypt (4.0.1)**: 密码哈希存储和验证
- **Cryptography (38.0.4)**: 提供高级加密功能

### 数据解析与格式化
- **PyYAML (6.0.2)**: YAML格式解析，用于配置和数据交换
- **JSONSchema (4.23.0)**: JSON数据验证
- **Tabulate (0.9.0)**: 格式化表格输出

### 工具与辅助库
- **Werkzeug (2.2.3)**: WSGI工具库，Flask的依赖
- **Python-dotenv (1.0.1)**: 环境变量管理
- **Tqdm (4.67.1)**: 进度条显示，用于长时间运行的操作

这些库之间的协作关系:
- Flask框架作为核心，通过扩展集成数据库和用户认证
- NumPy和SciPy提供科学计算能力，Pymatgen和Spglib专注于材料科学计算
- 可视化层由Matplotlib和Plotly提供，前者生成静态图表，后者提供交互功能
- 数据从CIF和DAT文件解析，通过ORM映射到SQLite数据库

## 安装指南

### 环境要求

- Python 3.8+
- Flask 2.0+
- SQLite 3
- Web浏览器（推荐Chrome或Firefox）

### 安装步骤

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/NLHE_Database.git
   cd NLHE_Database
   ```

2. 创建并激活虚拟环境：
   ```bash
   python -m venv NLHE
   source NLHE/bin/activate  # Linux/Mac
   # 或
   NLHE\Scripts\activate     # Windows
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 初始化数据库：
   ```bash
   ./initdb.sh
   ./admin.sh
   ```
   按照提示输入管理员用户名和密码。

## 使用方法

### 启动Web服务

```bash
./web.sh
```

服务器默认在 http://127.0.0.1:5000 启动。

### 材料管理操作

1. **浏览材料**：访问首页查看所有材料列表
2. **添加材料**：登录后点击"添加材料"
3. **编辑材料**：在材料详情页点击"编辑"
4. **删除材料**：在材料详情页点击"删除"

### 数据可视化

- **晶体结构**：在材料详情页点击"晶体结构"选项卡
- **能带结构**：在材料详情页点击"能带结构"选项卡

### 文件要求

- **结构文件**：CIF格式，存放在 `app/static/materials/IMR-xxxxxxxx/structure/structure.cif`
- **能带文件**：DAT格式，存放在 `app/static/materials/IMR-xxxxxxxx/band/band.dat`
- **SC文件**：DAT格式，存放在 `app/static/materials/IMR-xxxxxxxx/bcd/sc.dat`

## 文件结构规范

### 目录结构

每个材料都有一个唯一的IMR格式ID（如IMR-00000001），对应目录结构：
```
app/static/materials/IMR-xxxxxxxx/
├── 材料元数据.json      # 材料的元数据文件
├── structure/          # 结构文件目录
│   └── structure.cif   # CIF格式的结构文件
└── band/               # 能带数据目录
    └── band.dat        # 能带数据文件
```

### 材料元数据文件格式
JSON格式，包含材料的基本属性，例如：
```json
{
  "name": "材料名称",
  "status": "数据状态",
  "structure_file": "structure.cif",
  "total_energy": -56.28475,
  "formation_energy": -0.89216,
  "metal_type": "semiconductor",
  "gap": 1.8945
}
```

## 脚本说明

- **web.sh**：启动Web应用服务器
- **initdb.sh**：初始化或重置数据库
- **admin.sh**：创建或更新管理员账户

## 注意事项

- 初始化数据库后，请妥善保管管理员账户信息
- 保持结构文件和能带文件的命名规范一致
- 定期备份数据库文件`data.db`

## 贡献指南

1. Fork本仓库
2. 创建功能分支: `git checkout -b feature/your-feature`
3. 提交更改: `git commit -am '添加新功能'`
4. 推送分支: `git push origin feature/your-feature`
5. 提交Pull Request 