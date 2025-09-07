# security_config.py
# 安全配置模块

import os
from datetime import timedelta

class SecurityConfig:
    """
    安全配置类

    说明：
    - 本配置作为默认安全基线，生产环境可通过环境变量或实例配置覆盖；
    - 与 security_utils.add_security_headers 的响应头策略相辅相成；
    - Ubuntu 部署为主要目标环境，HTTPS 场景建议开启 HSTS（此处保持注释以免影响本地开发）。
    """
    
    # CSRF保护
    WTF_CSRF_ENABLED = True  # 开启表单 CSRF 保护
    WTF_CSRF_TIME_LIMIT = 3600  # 1 小时，过期后需刷新页面
    
    # 会话安全
    SESSION_COOKIE_SECURE = False  # 仅 HTTPS 传输；开发环境为 False，生产应为 True
    SESSION_COOKIE_HTTPONLY = True  # 禁止 JS 访问 Cookie，降低 XSS 风险
    SESSION_COOKIE_SAMESITE = 'Lax'  # 跨站请求限制，降低 CSRF 风险
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)  # 会话时长：2 小时
    
    # 文件上传安全
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 单次请求最大体积：16MB
    UPLOAD_EXTENSIONS = {'.txt', '.dat', '.cif', '.json', '.csv'}  # 白名单扩展名
    
    # 密码策略
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # 速率限制
    # RATELIMIT_STORAGE_URL在__init__.py中动态配置，支持Valkey存储
    # RATELIMIT_STORAGE_URL = "memory://"  # 已移至__init__.py动态配置
    RATELIMIT_DEFAULT = "50 per minute"  # 全局限流：每分钟 50 次
    
    # 安全头部
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        # 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',  # 仅在HTTPS环境启用
        # 注意：CSP 的允许来源需与 security_utils.add_security_headers 保持一致
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://threejs.org; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; connect-src 'self' https:;"
    }
    
    # 登录安全
    MAX_LOGIN_ATTEMPTS = 5  # 登录失败上限
    LOGIN_ATTEMPT_TIMEOUT = 300  # 冷却时间：5 分钟
    
    # API安全
    API_RATE_LIMIT = "50 per minute"  # API 速率限制
    
    # 日志配置
    SECURITY_LOG_FILE = 'logs/security.log'  # 安全事件日志文件路径
    SECURITY_LOG_LEVEL = 'INFO'  # 日志级别（生产建议 INFO/WARN）
