# security_utils.py
# 安全工具模块

import re
import os
import logging
import bleach
from functools import wraps
from flask import request, abort, current_app, session
from werkzeug.utils import secure_filename
from flask_login import current_user

# 创建logs目录
os.makedirs('logs', exist_ok=True)

# 设置安全日志
security_logger = logging.getLogger('security')
if not security_logger.handlers:
    handler = logging.FileHandler('logs/security.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)
    security_logger.setLevel(logging.INFO)

def validate_password_strength(password):
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码至少需要8位字符"
    
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含大写字母"
    
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含小写字母"
    
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    
    if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
        return False, "密码必须包含特殊字符"
    
    return True, "密码强度符合要求"

def sanitize_input(text):
    """清理用户输入，防止XSS"""
    if not text:
        return text
    
    # 允许的HTML标签
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
    
    # 清理HTML
    clean_text = bleach.clean(text, tags=allowed_tags, strip=True)
    
    return clean_text

def secure_file_upload(file):
    """安全文件上传检查"""
    if not file or not file.filename:
        return False, "没有选择文件"
    
    # 检查文件名
    filename = secure_filename(file.filename)
    if not filename:
        return False, "文件名无效"
    
    # 检查文件扩展名
    allowed_extensions = {'.txt', '.dat', '.cif', '.json', '.csv'}
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in allowed_extensions:
        return False, f"不支持的文件类型: {file_ext}"
    
    # 检查文件大小
    file.seek(0, 2)  # 移动到文件末尾
    file_size = file.tell()
    file.seek(0)  # 重置到开头
    
    max_size = 16 * 1024 * 1024  # 16MB
    if file_size > max_size:
        return False, f"文件过大，最大允许 {max_size // (1024*1024)}MB"
    
    return True, filename

def log_security_event(event_type, details, ip_address=None):
    """记录安全事件"""
    if not ip_address:
        ip_address = request.remote_addr if request else 'unknown'
    
    security_logger.warning(f"{event_type} - IP: {ip_address} - Details: {details}")

def require_admin(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            log_security_event("UNAUTHORIZED_ACCESS", f"Attempted access to {request.endpoint}")
            abort(401)
        
        if current_user.role != 'admin':
            log_security_event("PRIVILEGE_ESCALATION", f"User {current_user.username} attempted admin access")
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def add_security_headers(response):
    """
    为响应统一添加安全头部。

    说明：
    - X-Content-Type-Options / X-Frame-Options / X-XSS-Protection：基础安全增强；
    - Content-Security-Policy（CSP）：按需放开三方资源（js/css/fonts/connect），
      当前允许 jsdelivr/cdnjs/threejs/plotly、Google Fonts 等；
      若未来接入新三方资源，应在此处集中放开，避免分散配置导致安全策略不一致；
    - 严格传输安全（HSTS）在 HTTPS 环境启用，避免本地开发误伤，故保持注释。
    """
    headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        # 移除过于严格的CSP，允许必要的外部资源
        # 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',  # 仅在HTTPS环境启用
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://threejs.org https://cdn.plot.ly; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; connect-src 'self' https: https://materialsproject.org https://next-gen.materialsproject.org https://www.cas.cn https://github.com;"
    }

    for header, value in headers.items():
        response.headers[header] = value

    return response

def check_rate_limit(key, limit=5, window=300):
    """
    检查速率限制（基于 session 的简易实现）。

    参数：
        key: 业务键（例如登录/某接口名）；
        limit: 窗口内允许的最大请求数；
        window: 时间窗口（秒）。

    返回：
        bool：是否允许继续。
    """
    import time
    
    current_time = time.time()
    session_key = f"rate_limit_{key}"
    
    if session_key not in session:
        session[session_key] = []
    
    # 清理过期的请求记录
    session[session_key] = [
        timestamp for timestamp in session[session_key] 
        if current_time - timestamp < window
    ]
    
    # 检查是否超过限制
    if len(session[session_key]) >= limit:
        return False
    
    # 记录当前请求
    session[session_key].append(current_time)
    return True

def regenerate_session():
    """
    重新生成 session ID（防止会话固定攻击）。

    说明：
    - 保留关键字段（_user_id / csrf_token），其它数据清空；
    - 在登录/登出等安全敏感操作后调用，降低会话固定风险。
    """
    # 保存重要的session数据
    user_id = session.get('_user_id')
    csrf_token = session.get('csrf_token')
    
    # 清空session
    session.clear()
    
    # 恢复重要数据
    if user_id:
        session['_user_id'] = user_id
    if csrf_token:
        session['csrf_token'] = csrf_token
