# __init__.py:
# 应用初始化模块
# 本文件实现了Flask应用工厂模式，用于创建和配置Flask应用实例，
# 注册扩展、蓝图和路由，设置数据库连接等

# 导入系统模块（处理路径和操作系统检测）
import os  # 用于操作系统路径处理（如拼接数据库路径）
import sys  # 用于检测操作系统平台（Windows/Linux）

# 导入 Flask 核心模块和扩展库
from flask import Flask  # Flask 应用核心类
from flask_sqlalchemy import SQLAlchemy  # ORM 数据库扩展
from flask_login import LoginManager  # 用户登录管理扩展
from flask_migrate import Migrate  # 数据库迁移工具

# 导入安全相关扩展
try:
    from flask_wtf.csrf import CSRFProtect  # CSRF保护
    csrf_available = True
except ImportError:
    csrf_available = False

try:
    from flask_limiter import Limiter  # 速率限制
    from flask_limiter.util import get_remote_address
    limiter_available = True
except ImportError:
    limiter_available = False

# 初始化全局扩展对象（此时未绑定应用实例）
# 使用延迟绑定模式，支持应用工厂模式
db = SQLAlchemy()  # 创建 SQLAlchemy 实例，后续通过 init_app() 绑定应用
login_manager = LoginManager()  # 创建登录管理实例，支持多应用实例场景

# 初始化安全扩展
csrf = None
limiter = None

def create_app():
    """
    应用工厂函数：创建并配置 Flask 应用实例
    
    工厂模式好处:
        1. 便于测试（可创建多个独立实例）
        2. 支持不同配置的多环境部署
        3. 避免循环导入问题
        4. 符合蓝图架构模式
    
    返回:
        配置完成的Flask应用实例
    """
    app = Flask(__name__)  # 实例化 Flask 应用，__name__ 用于确定根目录路径

    # --- 配置部分 ---
    # 动态生成数据库 URI（适配不同操作系统）
    WIN = sys.platform.startswith('win')  # 检测是否为 Windows 系统
    prefix = 'sqlite:///' if WIN else 'sqlite:////'  # Windows 用 3 斜杠，Linux 用 4 斜杠
    
    # 从环境变量读取密钥（生产环境推荐），默认值 'dev' 用于开发
    # SECRET_KEY用于会话安全和CSRF保护
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # 使用Flask实例目录中的data.db文件作为默认数据库
    app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(
        app.instance_path,  # 使用Flask应用实例目录
        os.getenv('DATABASE_FILE', 'data.db')  # 从环境变量读取数据库文件名，默认为'data.db'
    )
    # 禁用SQLAlchemy的事件通知系统以提高性能
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 禁用 SQLAlchemy 事件系统以提升性能

    # 安全配置
    from .security_config import SecurityConfig
    app.config.update(SecurityConfig.__dict__)

    # 会话安全配置
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = SecurityConfig.PERMANENT_SESSION_LIFETIME

    # --- 扩展初始化 ---
    # 延迟绑定模式：先创建扩展实例，再与应用关联
    db.init_app(app)  # 延迟绑定 SQLAlchemy 到应用（工厂模式核心）
    migrate = Migrate(app, db)  # 初始化数据库迁移工具（生成迁移脚本）
    login_manager.init_app(app)  # 绑定登录管理到应用

    # 初始化安全扩展
    global csrf, limiter

    # CSRF保护
    global csrf
    if csrf_available:
        csrf = CSRFProtect(app)
        app.logger.info("CSRF protection enabled")
    else:
        csrf = None
        app.logger.warning("Flask-WTF not available, CSRF protection disabled")

    # 速率限制
    if limiter_available:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"]
        )
        limiter.init_app(app)
        app.logger.info("Rate limiting enabled")
    else:
        app.logger.warning("Flask-Limiter not available, rate limiting disabled")
    
    # --- 用户加载器（必须实现） ---
    # Flask-Login要求实现的回调函数，用于从会话cookie恢复用户
    @login_manager.user_loader
    def load_user(user_id):
        """
        根据用户 ID 加载用户对象（Flask-Login 要求）

        参数:
            user_id: 从会话中恢复的用户ID（字符串类型）

        返回:
            用户对象，未找到则返回None
        """
        from .models import User  # 延迟导入避免循环依赖
        return User.query.get(int(user_id))  # 查询数据库并返回用户实例

    # --- 安全头部处理器 ---
    @app.after_request
    def add_security_headers(response):
        """为所有响应添加安全头部"""
        from .security_utils import add_security_headers
        return add_security_headers(response)

    # --- 模板上下文处理器 ---
    # 向所有模板注入全局变量，避免在每个视图函数中重复传递
    @app.context_processor
    def inject_user():
        """
        向所有模板注入全局变量（例如当前用户）

        返回:
            字典，包含要注入模板的全局变量
        """
        try:
            from .models import User
            user = User.query.first()  # 示例：注入第一个用户（可替换为实际逻辑）
            return dict(user=user)  # 模板中可通过 {{ user }} 访问
        except Exception as e:
            app.logger.warning(f"无法查询用户表: {str(e)}")
            return dict(user=None)  # 返回空用户，避免模板错误

    # --- 初始化格式化ID ---
    def init_formatted_ids():
        """
        安全地初始化材料格式化ID:
        1. 检查数据库和表是否存在
        2. 检查字段兼容性
        3. 使用原生SQL避免ORM字段映射问题
        4. 在多进程环境下安全执行
        """
        from sqlalchemy import inspect, text
        from sqlalchemy.exc import SQLAlchemyError, OperationalError
        import time
        import random

        # 在多进程环境下添加随机延迟，避免并发冲突
        time.sleep(random.uniform(0.1, 0.5))

        try:
            # 完全使用原生SQL，避免ORM模型依赖
            with db.engine.begin() as conn:
                inspector = inspect(conn)

                # 检查material表是否存在
                table_names = inspector.get_table_names()
                if 'material' not in table_names:
                    app.logger.info("material表不存在，跳过格式化ID初始化")
                    return

                # 检查必要的列是否存在
                columns = [col['name'] for col in inspector.get_columns('material')]
                required_columns = ['id', 'formatted_id']

                # 如果不存在formatted_id列，添加它
                if 'formatted_id' not in columns:
                    conn.execute(text("ALTER TABLE material ADD COLUMN formatted_id VARCHAR(20)"))
                    app.logger.info("已添加formatted_id列到material表")
                    columns.append('formatted_id')

                # 检查是否有所有必要的列
                missing_columns = [col for col in required_columns if col not in columns]
                if missing_columns:
                    app.logger.warning(f"material表缺少必要字段: {missing_columns}")
                    return

                # 使用原生SQL查询和更新
                result = conn.execute(text(
                    "SELECT id, formatted_id FROM material WHERE formatted_id IS NULL OR formatted_id = '' OR formatted_id = 'IMR-PENDING'"
                ))
                materials_to_update = result.fetchall()

                count = 0
                for material in materials_to_update:
                    formatted_id = f"IMR-{material.id:08d}"
                    conn.execute(text(
                        "UPDATE material SET formatted_id = :formatted_id WHERE id = :id"
                    ), {"formatted_id": formatted_id, "id": material.id})
                    count += 1

                if count > 0:
                    app.logger.info(f"已更新 {count} 条材料记录的格式化ID")
                else:
                    app.logger.info("所有材料记录的格式化ID都已存在")
            # 尝试添加唯一索引（如果不存在）
            try:
                with db.engine.begin() as conn:
                    inspector_local = inspect(conn)
                    indices = inspector_local.get_indexes('material')
                    has_index = any(idx.get('name') == 'ix_material_formatted_id' for idx in indices)
                    if not has_index:
                        conn.execute(text("CREATE UNIQUE INDEX ix_material_formatted_id ON material (formatted_id)"))
                        app.logger.info("已为formatted_id列创建唯一索引")
            except SQLAlchemyError as e:
                app.logger.warning(f"创建唯一索引失败: {str(e)}")
            except Exception as e:
                app.logger.warning(f"创建唯一索引时发生错误: {str(e)}")
        except OperationalError as e:
            # 数据库操作错误，在多进程环境下可能是正常的竞争条件
            app.logger.info(f"数据库操作被跳过（可能是多进程竞争）: {str(e)}")
        except SQLAlchemyError as e:
            app.logger.warning(f"初始化格式化ID时发生数据库错误: {str(e)}")
            try:
                db.session.rollback()
            except:
                pass
        except Exception as e:
            app.logger.warning(f"初始化格式化ID时发生错误: {str(e)}")

    # --- 蓝图注册（模块化路由） ---
    # 使用应用上下文确保数据库操作在正确的环境中执行
    with app.app_context():  # 确保在应用上下文中操作（避免上下文缺失错误）
        # 导入各个功能模块的蓝图
        from .views import bp as views_bp  # 导入主视图蓝图
        from .errors import bp as errors_bp  # 导入错误处理蓝图
        from .commands import bp as commands_bp, register_commands  # 导入 CLI 命令蓝图和注册函数

        # 注册蓝图到应用实例
        app.register_blueprint(views_bp)  # 注册主视图路由
        app.register_blueprint(errors_bp)  # 注册错误处理路由
        app.register_blueprint(commands_bp)  # 注册命令行接口
        
        # 注册API蓝图（用于提供JSON接口）
        from .api import bp as api_bp
        app.register_blueprint(api_bp)  # 注册API路由
        
        # 注册内容蓝图（用于文档和内容展示）
        from .articles import articles as articles_bp
        app.register_blueprint(articles_bp)  # 注册内容路由

        # 注册deepseek蓝图
        from .deepseek import siliconflow_bp
        app.register_blueprint(siliconflow_bp)
        # 注册程序蓝图
        from .program import program_bp
        app.register_blueprint(program_bp)

        # 注册命令行命令
        register_commands(app)

        # 添加手动初始化命令，避免自动初始化导致的问题
        @app.cli.command('init-formatted-ids')
        def init_formatted_ids_command():
            """手动初始化材料格式化ID"""
            try:
                init_formatted_ids()
                print("格式化ID初始化完成")
            except Exception as e:
                print(f"初始化失败: {e}")
                return 1

        # 添加数据库索引初始化命令
        @app.cli.command('init-search-indexes')
        def init_search_indexes_command():
            """初始化搜索性能优化索引"""
            try:
                from .search_optimizer import QueryOptimizer
                QueryOptimizer.create_database_indexes()
                print("搜索索引初始化完成")
            except Exception as e:
                print(f"索引初始化失败: {e}")
                return 1

        # 添加能带数据分析命令
        @app.cli.command('analyze-bands')
        def analyze_bands_command():
            """分析所有材料的能带数据并生成band.json文件"""
            try:
                from .band_analyzer import band_analyzer
                from .models import Material

                print("开始分析能带数据...")

                # 获取所有材料
                materials = Material.query.all()
                total_materials = len(materials)
                analyzed_count = 0
                error_count = 0

                print(f"找到 {total_materials} 个材料需要分析")

                for i, material in enumerate(materials, 1):
                    print(f"[{i}/{total_materials}] 分析材料 {material.formatted_id}...")

                    try:
                        # 分析能带数据
                        result = band_analyzer.analyze_material_band(material.id)

                        if result:
                            # 更新数据库中的band_gap字段
                            material.band_gap = result['band_gap']
                            analyzed_count += 1
                            print(f"  ✅ 成功: 带隙 = {result['band_gap']:.4f} eV, 类型 = {result['materials_type']}")
                        else:
                            error_count += 1
                            print(f"  ❌ 分析失败")

                    except Exception as e:
                        error_count += 1
                        print(f"  ❌ 错误: {str(e)}")

                # 提交数据库更改
                db.session.commit()

                print(f"\n能带分析完成!")
                print(f"✅ 成功分析: {analyzed_count}")
                print(f"❌ 失败: {error_count}")
                print(f"📊 总计: {total_materials}")

            except Exception as e:
                print(f"能带分析错误: {str(e)}")
                return 1

        # 添加一个安全的初始化检查函数
        def safe_init_check():
            """安全地检查是否需要初始化"""
            if os.environ.get('SKIP_DB_INIT'):
                return
            try:
                # 只在明确需要时才初始化
                from sqlalchemy import text
                with db.engine.begin() as conn:
                    result = conn.execute(text(
                        "SELECT COUNT(*) as count FROM material WHERE formatted_id IS NULL OR formatted_id = '' OR formatted_id = 'IMR-PENDING'"
                    ))
                    count = result.scalar()
                    if count > 0:
                        app.logger.info(f"发现 {count} 条记录需要初始化格式化ID，请运行: flask init-formatted-ids")
            except Exception:
                # 如果检查失败，静默忽略
                pass

        # 在应用上下文中进行安全检查
        with app.app_context():
            safe_init_check()

    return app  # 返回完全初始化的应用实例