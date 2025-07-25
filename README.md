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
- **AI对话集成**：集成Deepseek AI对话接口，支持科研问题咨询和材料知识问答
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

### AI集成
- **Deepseek API**：集成QwQ-32B大型语言模型，提供科研问题解答
- **会话管理**：支持多会话保存、切换和管理

## 项目结构

```
NLHE_Database/
├── app/                   # 应用主目录
│   ├── __init__.py        # 应用初始化（工厂模式）
│   ├── models.py          # 数据模型定义
│   ├── views.py           # 视图函数和路由
│   ├── api.py             # RESTful API接口
│   ├── articles.py        # 文章管理模块
│   ├── deepseek.py        # AI对话接口模块
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
│   │   ├── chat/          # AI对话历史记录
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

### AI对话助手
- 基于Deepseek API的科研问题咨询
- 支持多会话保存和管理
- 历史对话查看和编辑功能

### 文件格式转换
- 支持TXT文件转换为DAT和DOCX格式
- 简单直观的文件上传和下载界面

## 维护与备份

- 定期备份`instance/app.db`数据库文件
- 系统日志记录在应用实例目录中
- 建议按计划对材料数据进行增量备份
- AI对话历史存储在用户目录下，可单独备份

## 开发者说明

- 项目采用工厂模式组织Flask应用结构
- 使用蓝图(Blueprint)分离不同功能模块
- 数据库迁移通过Flask-Migrate管理
- 结构解析模块使用Pymatgen库处理CIF文件
- AI模块使用Deepseek API，可配置为其他兼容接口

## 技术亮点

- **高效数据处理**：优化的数据库查询和缓存机制
- **交互式可视化**：前端使用WebGL技术实现高性能3D渲染
- **材料ID系统**：采用标准化的材料编码系统（IMR-XXXXXXXX）
- **多层次安全**：包括数据验证、用户认证和防暴力攻击机制
- **AI辅助研究**：集成大型语言模型，辅助材料研究和数据分析

## 许可与贡献

- 项目采用MIT许可证
- 欢迎通过Issue和Pull Request参与贡献
- 开发前请先阅读贡献指南 