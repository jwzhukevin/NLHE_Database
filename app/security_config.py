# security_config.py
# 安全配置模块

import os
from datetime import timedelta

class SecurityConfig:
    """安全配置类"""
    
    # CSRF保护
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1小时
    
    # 会话安全
    SESSION_COOKIE_SECURE = False  # 开发环境设为False，生产环境应为True
    SESSION_COOKIE_HTTPONLY = True  # 防止XSS
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF保护
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)  # 2小时超时
    
    # 文件上传安全
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_EXTENSIONS = {'.txt', '.dat', '.cif', '.json', '.csv'}
    
    # 密码策略
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # 速率限制
    # RATELIMIT_STORAGE_URL在__init__.py中动态配置，支持Valkey存储
    # RATELIMIT_STORAGE_URL = "memory://"  # 已移至__init__.py动态配置
    RATELIMIT_DEFAULT = "100 per hour"
    
    # 安全头部
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        # 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',  # 仅在HTTPS环境启用
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://threejs.org; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; connect-src 'self' https:;"
    }
    
    # 登录安全
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_ATTEMPT_TIMEOUT = 300  # 5分钟
    
    # API安全
    API_RATE_LIMIT = "50 per minute"
    
    # 日志配置
    SECURITY_LOG_FILE = 'logs/security.log'
    SECURITY_LOG_LEVEL = 'INFO'
