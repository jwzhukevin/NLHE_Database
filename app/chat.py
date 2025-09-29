# chat.py
# 聊天页面蓝图：提供受登录保护的聊天入口页面
# 说明：仅提供页面渲染，实际模型交互走 /api/chat/stream

from flask import Blueprint, render_template, current_app, session
from flask_login import login_required, current_user
import redis

# [用户规则] 逻辑前解释：
# 本蓝图仅负责渲染前端页面，避免与 API 交织；权限控制使用 @login_required。

chat_bp = Blueprint('chat', __name__, url_prefix='/chat')


@chat_bp.route('/', methods=['GET'])
@login_required
def chat_page():
    """
    聊天页面入口

    逻辑：
    - 受登录保护，仅登录用户可访问
    - 进入页面即尝试占位：在 Redis 写入 chat:active_user:{username}，TTL=60s
    - 若当前已有两名活跃用户且当前用户未占位，则渲染拒绝页面
    - 否则渲染聊天页
    """
    username = getattr(current_user, 'username', 'user') or 'user'
    rurl = current_app.config.get('RATELIMIT_STORAGE_URL') or current_app.config.get('REDIS_URL')
    if not rurl:
        # 未配置 Redis 时，不进行并发限制，直接放行
        # 仍创建本次会话的保存文件名
        session_filename = f"session_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        session['chat_session_file'] = session_filename
        return render_template('chat/chat.html', chat_session_file=session_filename)

    r = redis.from_url(rurl)
    # 统计当前活跃用户数量
    try:
        pattern = 'chat:active_user:*'
        active = list(r.scan_iter(pattern))
        active_count = len(active)
    except Exception:
        active_count = 0

    user_key = f'chat:active_user:{username}'
    already = False
    try:
        already = r.exists(user_key) == 1
    except Exception:
        already = False

    # 已满且当前用户未占位，渲染拒绝页
    if active_count >= 2 and not already:
        return render_template('errors/403.html', active_count=active_count), 403

    # 设置/续期当前用户占位
    try:
        r.set(user_key, 1, ex=60)
    except Exception:
        pass

    return render_template('chat/chat.html')
