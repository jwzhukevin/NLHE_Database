# Gunicorn配置文件
import os

# 服务器绑定
bind = "0.0.0.0:8000"

# Worker进程配置
workers = 4
worker_class = "sync"
worker_connections = 1000

# 请求处理
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2

# 应用预加载（避免多进程初始化问题）
preload_app = True

# 日志配置
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"

# 进程管理
daemon = False
pidfile = "gunicorn.pid"

# 环境变量
raw_env = [
    'SKIP_DB_INIT=1',  # 跳过数据库初始化
    'FLASK_ENV=production',  # 设置为生产环境
]

def when_ready(server):
    """服务器准备就绪时的回调"""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Worker进程中断时的回调"""
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Fork worker进程前的回调"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    """Fork worker进程后的回调"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
