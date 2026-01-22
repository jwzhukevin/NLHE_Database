# __init__.py:
# 应用初始化模块
# 本文件实现了Flask应用工厂模式，用于创建和配置Flask应用实例，
# 注册扩展、蓝图和路由，设置数据库连接等

# 导入系统模块（处理路径和操作系统检测）
import os  # 用于操作系统路径处理（如拼接数据库路径）
import sys  # 用于检测操作系统平台（Windows/Linux）
import threading  # 用于后台非阻塞预热字体

# 导入 Flask 核心模块和扩展库
from flask import Flask, request, g, render_template  # Flask 应用核心类与请求上下文与错误页渲染
from flask_sqlalchemy import SQLAlchemy  # ORM 数据库扩展
from flask_login import LoginManager  # 用户登录管理扩展
from flask_migrate import Migrate  # 数据库迁移工具
from flask_babel import Babel, get_locale, _  # 国际化支持
from flask_mail import Mail, Message  # 邮件发送

# 导入安全相关扩展
try:
    from flask_wtf.csrf import CSRFProtect  # CSRF保护
    csrf_available = True
except ImportError:
    csrf_available = False

try:
    from flask_limiter import Limiter  # 速率限制
    from flask_limiter.util import get_remote_address  # 获取客户端IP地址的工具函数
    limiter_available = True
except ImportError:
    # 如果 Flask-Limiter 未安装，定义一个默认的地址获取函数
    limiter_available = False
    def get_remote_address():
        """备用的IP地址获取函数，当Flask-Limiter不可用时使用"""
        from flask import request
        return request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

# 初始化全局扩展对象（此时未绑定应用实例）
# 使用延迟绑定模式，支持应用工厂模式
db = SQLAlchemy()  # 创建 SQLAlchemy 实例，后续通过 init_app() 绑定应用
login_manager = LoginManager()  # 创建登录管理实例，支持多应用实例场景
babel = Babel()  # 创建 Babel 实例，延迟绑定
mail = Mail()    # 创建 Mail 实例，延迟绑定

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

    # Valkey配置 - 用于速率限制存储 (Valkey是Redis的开源分支)
    # 支持Redis协议，可以无缝替换Redis
    app.config['VALKEY_URL'] = os.getenv('VALKEY_URL', 'redis://localhost:6379/0')
    app.config['RATELIMIT_STORAGE_URL'] = os.getenv('RATELIMIT_STORAGE_URL', 'redis://localhost:6379/1')

    # 向后兼容Redis配置
    app.config['REDIS_URL'] = app.config['VALKEY_URL']

    # --- 字体与验证码相关默认配置（可在环境或实例配置中覆盖） ---
    app.config.setdefault('FONT_DIR', os.path.join(app.root_path, 'static', 'fonts'))
    app.config.setdefault('ENABLE_FONT_DOWNLOAD', True)
    app.config.setdefault('FONT_PRELOAD_SIZES', [28, 32, 36])
    app.config.setdefault('FONT_DOWNLOAD_TIMEOUT', 5)
    app.config.setdefault('FONT_CACHE_MAX_ITEMS', 32)
    app.config.setdefault('CAPTCHA_FONT_SOURCES', [
        'https://github.com/dejavu-fonts/dejavu-fonts/raw/main/ttf/DejaVuSans-Bold.ttf',
        'https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf',
        'https://fonts.gstatic.com/s/liberationsans/v15/LiberationSans-Bold.ttf'
    ])

    # 安全配置
    from .security import SecurityConfig
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
    # 邮件配置（从环境变量读取，保持默认关闭状态，缺失配置将导致发送时报错并被捕获）
    app.config.setdefault('MAIL_SERVER', os.getenv('MAIL_SERVER', ''))
    app.config.setdefault('MAIL_PORT', int(os.getenv('MAIL_PORT', '587') or 587))
    app.config.setdefault('MAIL_USE_TLS', (os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'))
    app.config.setdefault('MAIL_USE_SSL', (os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'))
    app.config.setdefault('MAIL_USERNAME', os.getenv('MAIL_USERNAME', ''))
    app.config.setdefault('MAIL_PASSWORD', os.getenv('MAIL_PASSWORD', ''))
    app.config.setdefault('MAIL_DEFAULT_SENDER', os.getenv('MAIL_DEFAULT_SENDER', 'no-reply@nlhe-database.org'))
    app.config.setdefault('APPLICATION_RECEIVER', os.getenv('APPLICATION_RECEIVER', ''))
    # 初始化 Mail 扩展
    try:
        mail.init_app(app)
        app.logger.info("Mail extension initialized")
    except Exception as e:
        app.logger.warning(f"Mail extension init failed: {e}")

    # --- 国际化（i18n）配置 ---
    # 默认语言与受支持语言，可通过实例配置/环境覆盖
    app.config.setdefault('BABEL_DEFAULT_LOCALE', 'en')
    app.config.setdefault('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
    app.config.setdefault('BABEL_DEFAULT_TIMEZONE', 'UTC')

    # 语言选择器：优先级 query -> session -> cookie -> 浏览器首选
    # 说明：
    # - 通过统一入口 select_locale() 判定语言，避免各处自行解析导致行为不一致；
    # - 记录判定日志便于定位国际化问题（浏览器头/查询参数/会话与 Cookie）；
    # - 任何异常均回退默认语言，保证服务可用性。
    def select_locale():
        try:
            supported = app.config.get('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
            # 从查询参数读取
            lang = (request.args.get('lang') or None)
            app.logger.info(f"i18n.select_locale: args.lang={lang}, supported={supported}")
            if not lang:
                # 从 session 读取
                try:
                    from flask import session as flask_session
                    lang = flask_session.get('lang')
                    app.logger.info(f"i18n.select_locale: session.lang={lang}")
                except Exception:
                    lang = None
            if not lang:
                # 从 cookie 读取
                lang = request.cookies.get('lang')
                app.logger.info(f"i18n.select_locale: cookie.lang={lang}")
            if lang and lang in supported:
                g.current_locale = lang
                app.logger.info(f"i18n.select_locale: use_explicit lang={lang}")
                return lang
            # 按浏览器首选匹配
            best = request.accept_languages.best_match(supported)
            app.logger.info(
                f"i18n.select_locale: accept_language_raw={request.headers.get('Accept-Language')}, best_match={best}"
            )
            g.current_locale = best or app.config.get('BABEL_DEFAULT_LOCALE', 'en')
            app.logger.info(f"i18n.select_locale: final_locale={g.current_locale}")
            return g.current_locale
        except Exception:
            # 任何异常时回退默认语言
            g.current_locale = app.config.get('BABEL_DEFAULT_LOCALE', 'en')
            app.logger.warning("i18n.select_locale: exception occurred, fallback to default")
            return g.current_locale

    # 初始化 Babel，并注册语言选择器
    babel.init_app(app, locale_selector=select_locale)
    # 将 `_` 注册为 Jinja 全局，供模板中直接使用
    app.jinja_env.globals.update(_=_)

    # 配置Flask-Login
    login_manager.login_view = 'views.login'  # 未登录时重定向的视图
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

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
        try:
            limiter = Limiter(
                key_func=get_remote_address,
                default_limits=["50 per minute", "250 per 5 minutes"],
                storage_uri=app.config['RATELIMIT_STORAGE_URL']
            )
            limiter.init_app(app)
            app.logger.info("Rate limiting enabled with Valkey storage")
        except Exception as e:
            # 如果Valkey连接失败，回退到内存存储
            app.logger.warning(f"Valkey connection failed, falling back to memory storage: {e}")
            limiter = Limiter(
                key_func=get_remote_address,
                default_limits=["50 per minute", "250 per 5 minutes"]
            )
            limiter.init_app(app)
            app.logger.info("Rate limiting enabled with memory storage (Valkey fallback)")
    else:
        app.logger.warning("Flask-Limiter not available, rate limiting disabled")

    # 向模板注入当前语言与支持的语言列表
    @app.context_processor
    def inject_i18n_context():
        """
        注入 i18n 相关变量：
        - current_locale: 当前生效语言
        - supported_locales: 支持的语言列表
        """
        try:
            current = str(get_locale()) if get_locale() else app.config.get('BABEL_DEFAULT_LOCALE', 'en')
        except Exception:
            current = app.config.get('BABEL_DEFAULT_LOCALE', 'en')
        return dict(
            current_locale=current,
            supported_locales=app.config.get('BABEL_SUPPORTED_LOCALES', ['en', 'zh'])
        )
    
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

    # --- 会话状态检查和消息处理中间件 ---
    @app.before_request
    def check_session_and_messages():
        """检查会话状态一致性并处理登录/登出消息"""
        from flask import request
        from flask_login import current_user
        from .security import LoginStateManager

        # 跳过静态文件和API路由
        if request.endpoint and (request.endpoint.startswith('static') or
                                request.endpoint.startswith('api') or
                                request.endpoint in ['views.logout', 'views.login']):
            return

        # 验证登录状态一致性
        LoginStateManager.verify_state_consistency()

        # 消息处理已移至登录/登出路由中直接处理，避免重复显示
        # 这里不再处理消息显示逻辑

    # --- 安全头部处理器 ---
    @app.after_request
    def add_security_headers(response):
        """
        为所有响应添加安全头部。

        说明：统一在 after_request 注入安全头，避免分散在各视图函数中；
        头部策略在 security_utils.add_security_headers 中集中维护，
        便于按环境/需求做放开或收紧（如 CSP 的外部资源白名单）。
        """
        from .security import add_security_headers
        return add_security_headers(response)

    # --- 全局错误处理器：统一渲染错误模板 ---
    @app.errorhandler(403)
    def handle_403(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def handle_404(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(410)
    def handle_410(e):
        return render_template('errors/410.html'), 410

    @app.errorhandler(429)
    def handle_429(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def handle_500(e):
        return render_template('errors/500.html'), 500

    # --- 非阻塞字体预热（首次请求后启动，避免阻塞应用启动与 preload_app 阶段） ---
    @app.before_first_request
    def preload_captcha_fonts_async():
        """
        验证码字体预热（异步）

        说明：
        - 仅在首个请求后异步触发，避免应用启动阶段等待网络/IO；
        - 在独立线程内确保应用上下文，逐尺寸加载字体，失败不影响主流程；
        - 结合 FontManager 的“快速失败与缓存”机制，进一步降低超时风险。
        """
        try:
            sizes = app.config.get('FONT_PRELOAD_SIZES') or []
            if not sizes:
                return

            def _worker():
                # 确保在线程中拥有应用上下文，避免 Working outside of application context 警告
                try:
                    from .services import FontManager
                    with app.app_context():
                        # 确保字体目录存在
                        try:
                            FontManager.ensure_fonts_dir()
                        except Exception as e:
                            app.logger.warning(f"创建字体目录失败: {e}")
                        # 逐个尺寸预热，不抛出异常
                        for s in sizes:
                            try:
                                FontManager.get_captcha_font(s)
                            except Exception as e:
                                app.logger.warning(f"字体预热失败 size={s}: {e}")
                        app.logger.info(f"字体预热完成: {sizes}")
                except Exception as e:
                    app.logger.warning(f"字体预热线程内部错误: {e}")

            t = threading.Thread(target=_worker, name='captcha-font-preload', daemon=True)
            t.start()
            app.logger.info(f"已启动字体预热线程（非阻塞）: {sizes}")
        except Exception as e:
            app.logger.warning(f"启动字体预热线程失败: {e}")

    # --- 模板上下文处理器 ---
    # 向所有模板注入全局变量，避免在每个视图函数中重复传递
    @app.context_processor
    def inject_global_vars():
        """
        向所有模板注入全局变量

        注意：current_user 由 Flask-Login 自动注入，这里不需要重复处理

        返回:
            字典，包含要注入模板的全局变量
        """
        try:
            # 注入一些全局配置或统计信息
            from .models import Material
            total_materials = Material.query.count()
            return dict(
                total_materials=total_materials,
                app_name="NLHE MatdataX"
            )
        except Exception as e:
            app.logger.warning(f"无法查询统计信息: {str(e)}")
            return dict(
                total_materials=0,
                app_name="NLHE MatdataX"
            )

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
                # 说明：全局标准化为 IMR-{id}（不补零），避免多种显示格式混用
                for material in materials_to_update:
                    formatted_id = f"IMR-{material.id}"
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
    with app.app_context():
        # 将所有蓝图的导入和注册放在函数内部，以避免循环导入问题
        from .blueprints.api import bp as api_bp
        from .views import bp as views_bp
        from .errors import bp as errors_bp
        from .commands import bp as commands_bp, register_commands
        from .blueprints.articles import articles as articles_bp
        from .blueprints.chat import chat_bp
        from .blueprints.database.structural import high_temperature_alloy_bp, ceramics_experiment, ceramics_literature
        from .services import register_material_cache_invalidation, get_search_cache_stats, search_cache
        
        # 新增：导入拆分后的蓝图
        from .blueprints import register_blueprints

        # 注册拆分后的蓝图（main, auth, members, functional_materials, search_api）
        register_blueprints(app)
        
        # 注册其他蓝图
        app.register_blueprint(api_bp)
        app.register_blueprint(views_bp)  # 保留views_bp用于调试路由
        app.register_blueprint(errors_bp)
        app.register_blueprint(commands_bp)
        app.register_blueprint(articles_bp)
        app.register_blueprint(chat_bp)
        app.register_blueprint(high_temperature_alloy_bp)
        app.register_blueprint(ceramics_experiment)
        app.register_blueprint(ceramics_literature)

        # 注入陶瓷三个子模块的数据条数（带 mtime 缓存）
        from .services.csv_config import get_csv_path as _get_ai_csv_path

        # 使用 app.extensions 作为简单缓存容器
        app.extensions.setdefault('csv_counts_cache', {})

        def _count_csv_rows(csv_abs_path: str) -> int:
            try:
                if not os.path.isfile(csv_abs_path):
                    return 0
                cache = app.extensions['csv_counts_cache']
                mtime = os.path.getmtime(csv_abs_path)
                entry = cache.get(csv_abs_path)
                if entry and entry.get('mtime') == mtime:
                    return entry.get('count', 0)
                # 统计行数，去掉表头
                count = 0
                with open(csv_abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, _line in enumerate(f, start=0):
                        count += 1
                count = max(0, count - 1)
                cache[csv_abs_path] = {'mtime': mtime, 'count': count}
                return count
            except Exception as _e:
                app.logger.debug(f"CSV row count failed for {csv_abs_path}: {_e}")
                return 0

        @app.context_processor
        def inject_ceramics_counts():
            try:
                lit_path = os.path.join(app.root_path, 'static', 'CSV_data', '文献数据.csv')
                exp_path = os.path.join(app.root_path, 'static', 'CSV_data', '实验数据.csv')
                ai_path = _get_ai_csv_path(app)

                return dict(
                    ceramics_literature_count=_count_csv_rows(lit_path),
                    ceramics_experiment_count=_count_csv_rows(exp_path),
                    ceramics_ai_count=_count_csv_rows(ai_path),
                )
            except Exception as e:
                app.logger.debug(f"inject_ceramics_counts failed: {e}")
                return dict(
                    ceramics_literature_count=0,
                    ceramics_experiment_count=0,
                    ceramics_ai_count=0,
                )

        # 注册命令行命令
        register_commands(app)

        # [新增调用] 注册 Material 的变更事件监听，自动触发搜索缓存失效
        try:
            register_material_cache_invalidation()
            app.logger.info("已启用材料变更事件监听（触发搜索缓存失效）")
        except Exception as e:
            app.logger.warning(f"注册材料变更事件监听失败: {e}")

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
                from .services import QueryOptimizer
                QueryOptimizer.create_database_indexes()
                print("搜索索引初始化完成")
            except Exception as e:
                print(f"索引初始化失败: {e}")
                return 1

        # [新增] 打印搜索缓存指标（命中率、大小等）
        @app.cli.command('search-cache-stats')
        def search_cache_stats_command():
            """
            打印搜索缓存统计信息。
            用法: flask search-cache-stats
            """
            try:
                import json
                stats = get_search_cache_stats()
                print(json.dumps(stats, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"获取缓存统计失败: {e}")
                return 1

        # [新增] 手动清空搜索缓存（一般用于紧急回滚或调试）
        @app.cli.command('clear-search-cache')
        def clear_search_cache_command():
            """
            清空搜索缓存。
            用法: flask clear-search-cache
            """
            try:
                search_cache.clear()
                print("搜索缓存已清空")
            except Exception as e:
                print(f"清空缓存失败: {e}")
                return 1

        # 添加能带数据分析命令
        @app.cli.command('analyze-bands')
        def analyze_bands_command():
            """分析所有材料的能带数据并生成band.json文件"""
            try:
                from .services import band_analyzer
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
                        material_path = f"app/static/materials/{material.formatted_id}/band"
                        result = band_analyzer.analyze_material(material_path)

                        if result and result['band_gap'] is not None:
                            # 更新数据库中的band_gap字段
                            material.band_gap = result['band_gap']
                            material.materials_type = result['materials_type']
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
