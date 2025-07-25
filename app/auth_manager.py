"""
用户认证状态管理模块

提供统一的登录/登出处理，确保状态一致性和安全性
避免与Flask-Login的LoginManager命名冲突
"""

from datetime import datetime, timezone, timezone
from flask import session, request, current_app, flash
from flask_login import login_user as flask_login_user, logout_user as flask_logout_user, current_user
from .security_utils import log_security_event, regenerate_session
from .models import db


class LoginStateManager:
    """
    登录状态管理器

    核心逻辑：只在用户状态真正发生变化时显示提示消息
    - 游客 → 登录用户：显示"Welcome back, username!"
    - 登录用户 → 游客：显示"You have been logged out successfully."
    - 其他情况（如已登录用户重新登录）：不显示消息
    """
    
    @staticmethod
    def login_user(user, remember=False):
        """
        统一的用户登录处理

        只有当用户从游客状态变为登录状态时才显示欢迎消息，
        避免在已登录状态下重复显示消息。

        Args:
            user: 用户对象
            remember: 是否记住登录状态（当前不支持，保留参数兼容性）

        Returns:
            tuple: (success: bool, message: str, redirect_url: str)
        """
        try:
            # 1. 检查当前用户状态（登录前）
            try:
                was_authenticated_before = current_user and current_user.is_authenticated
            except (AttributeError, RuntimeError):
                # 在测试环境或没有请求上下文时
                was_authenticated_before = False

            # 2. 记录登录尝试
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', 'Unknown')

            current_app.logger.info(
                f"Login attempt - User: {user.username}, IP: {ip_address}, "
                f"Was authenticated before: {was_authenticated_before}, "
                f"User-Agent: {user_agent[:100]}..."
            )

            # 3. 清理旧会话并重新生成会话ID（防止会话固定攻击）
            LoginStateManager._cleanup_old_session()
            regenerate_session()

            # 4. 执行Flask-Login登录
            flask_login_user(user, remember=False)  # 不支持记住我功能

            # 5. 只有在状态真正发生变化时才显示登录消息（游客 → 登录用户）
            if not was_authenticated_before:
                flash(f'Welcome back, {user.username}!', 'success')
                current_app.logger.info(f"Login status changed: Guest → {user.role} user, showing welcome message")
            else:
                current_app.logger.info(f"User was already authenticated, no welcome message shown")
            
            # 6. 记录成功登录事件
            log_security_event(
                "LOGIN_SUCCESS", 
                f"User: {user.username}, Role: {user.role}, Session: {session.get('_id', 'unknown')}", 
                ip_address
            )
            
            # 7. 更新用户最后登录信息
            try:
                user.last_login_ip = ip_address
                user.last_login_time = datetime.now(timezone.utc)
                db.session.commit()
            except Exception as e:
                # 如果字段不存在，跳过更新但不影响登录
                current_app.logger.warning(f"Could not update login tracking fields: {e}")
                db.session.rollback()
            
            current_app.logger.info(f"User {user.username} logged in successfully from {ip_address}")
            
            return True, f"Welcome back, {user.username}!", None
            
        except Exception as e:
            current_app.logger.error(f"Login error for user {user.username}: {e}")
            log_security_event("LOGIN_ERROR", f"User: {user.username}, Error: {str(e)}", request.remote_addr)
            return False, "Login failed due to system error. Please try again.", None
    
    @staticmethod
    def logout_user():
        """
        统一的用户登出处理

        只有当用户从登录状态变为游客状态时才显示登出消息，
        避免在游客状态下重复显示消息。

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            ip_address = request.remote_addr

            # 1. 检查当前用户状态（登出前）
            try:
                was_authenticated_before = current_user and current_user.is_authenticated
                username = current_user.username if was_authenticated_before else None
            except (AttributeError, RuntimeError):
                # 在测试环境或没有请求上下文时
                was_authenticated_before = False
                username = None

            current_app.logger.info(
                f"Logout attempt - Was authenticated: {was_authenticated_before}, "
                f"User: {username}, IP: {ip_address}"
            )

            if was_authenticated_before:
                # 2. 记录登出事件
                log_security_event("LOGOUT", f"User: {username}", ip_address)

                # 3. 执行Flask-Login登出
                flask_logout_user()

                # 4. 只有在状态真正发生变化时才显示登出消息（登录用户 → 游客）
                flash('You have been logged out successfully.', 'info')
                current_app.logger.info(f"Logout status changed: {username} → Guest, showing logout message")

                # 5. 完全清理会话
                session.clear()

                # 6. 重新生成会话ID
                regenerate_session()

                current_app.logger.info(f"User {username} logged out successfully from {ip_address}")
                return True, "You have been logged out successfully."

            else:
                # 用户未登录，静默处理（不显示消息，因为状态没有变化）
                current_app.logger.info(f"User was already unauthenticated, no logout message shown")
                session.clear()
                regenerate_session()
                return True, None  # 不显示消息
                
        except Exception as e:
            current_app.logger.error(f"Logout error: {e}")
            log_security_event("LOGOUT_ERROR", f"Error: {str(e)}", request.remote_addr)
            
            # 强制清理会话
            try:
                flask_logout_user()
                session.clear()
                regenerate_session()
            except:
                pass
                
            return True, "Logout completed."
    
    @staticmethod
    def _cleanup_old_session():
        """清理旧会话数据"""
        # 清理可能残留的登录相关数据
        old_keys = [
            'last_login_message_time', 'login_message_shown'
        ]
        for key in old_keys:
            session.pop(key, None)
    
    @staticmethod
    def get_user_state_description():
        """获取当前用户状态描述"""
        try:
            if current_user and current_user.is_authenticated:
                return f"{current_user.username} ({current_user.role})"
            else:
                return "Guest"
        except (AttributeError, RuntimeError):
            # 在测试环境或没有请求上下文时，current_user可能为None
            return "Guest (no request context)"

    @staticmethod
    def verify_state_consistency():
        """验证登录状态一致性"""
        try:
            # 检查Flask-Login状态
            try:
                is_authenticated = current_user and current_user.is_authenticated
            except (AttributeError, RuntimeError):
                # 在测试环境或没有请求上下文时
                is_authenticated = False

            # 如果用户未认证，清理可能残留的登录相关会话数据
            if not is_authenticated:
                login_related_keys = ['_user_id']  # 只清理Flask-Login相关的数据
                cleaned = False
                for key in login_related_keys:
                    if key in session:
                        session.pop(key, None)
                        cleaned = True
                
                if cleaned:
                    current_app.logger.debug("Cleaned inconsistent session data for unauthenticated user")
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"State consistency check failed: {e}")
            return False


# MessageManager类已删除，消息现在在登录/登出时立即显示


class LoginErrorHandler:
    """登录错误处理器"""
    
    ERROR_MESSAGES = {
        'user_not_found': 'Email address not found. Please check your email or register a new account.',
        'invalid_password': 'Invalid password. Please check your password and try again.',
        'account_locked': 'Account temporarily locked due to multiple failed attempts. Please try again later.',
        'system_error': 'System error occurred. Please try again later.',
        'invalid_credentials': 'Invalid email or password. Please check your credentials.',
        'rate_limited': 'Too many login attempts. Please wait before trying again.'
    }
    
    @staticmethod
    def handle_login_error(error_type, details=None):
        """
        处理登录错误
        
        Args:
            error_type: 错误类型
            details: 错误详情
            
        Returns:
            str: 用户友好的错误消息
        """
        # 记录详细错误信息
        ip_address = request.remote_addr
        log_security_event(
            "LOGIN_FAILED", 
            f"Error: {error_type}, Details: {details}, IP: {ip_address}", 
            ip_address
        )
        
        # 返回用户友好的错误消息
        return LoginErrorHandler.ERROR_MESSAGES.get(error_type, 'Login failed. Please try again.')
