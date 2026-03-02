# -*- coding: utf-8 -*-
"""
AI 聊天流式 API 蓝图

从 api.py 拆分而来，专注于与大语言模型交互的流式聊天接口。
支持本地 Ollama 和云端 SiliconFlow 两种模型后端。
"""

import json
import os
from datetime import datetime

import requests
from flask import Blueprint, Response, current_app, request, session
from flask_login import current_user, login_required

# ==============================================================================
# 蓝图定义
# ==============================================================================

chat_api_bp = Blueprint('chat_api', __name__, url_prefix='/api')

# 全局缓存 SiliconFlow API 密钥
SILICONFLOW_API_KEY = None


def _get_siliconflow_api_key():
    """
    读取并缓存 SiliconFlow API 密钥。
    返回密钥字符串，如果文件不存在或为空则返回空字符串。
    """
    global SILICONFLOW_API_KEY
    if SILICONFLOW_API_KEY is not None:
        return SILICONFLOW_API_KEY

    try:
        key_path = os.path.join(current_app.root_path, 'static', 'chat_api', 'siliconflow_cloud.key')
        if not os.path.exists(key_path):
            current_app.logger.warning("SiliconFlow API key file not found.")
            SILICONFLOW_API_KEY = ""
            return ""

        with open(key_path, 'r') as f:
            key = f.read().strip()
            SILICONFLOW_API_KEY = key
            return key
    except Exception as e:
        current_app.logger.error(f"Error reading SiliconFlow API key: {e}")
        SILICONFLOW_API_KEY = ""
        return ""


# ==============================================================================
# 聊天流式接口
# ==============================================================================

@chat_api_bp.route('/chat/stream', methods=['POST'])
@login_required
def chat_stream():
    """
    处理流式聊天请求，根据模型名称智能选择本地 Ollama 或云端 SiliconFlow API。
    """
    try:
        # 预热 API 密钥缓存
        _get_siliconflow_api_key()

        # 解析前端请求
        data = request.get_json(silent=True) or {}
        messages = data.get('messages') or []
        model = data.get('model', 'deepseek-r1:14b').strip()
        lang = data.get('lang', 'en')

        # 设置日志与会话文件路径
        username = getattr(current_user, 'username', 'guest')
        base_dir = os.path.join(current_app.root_path, 'static', 'chat', username)
        os.makedirs(base_dir, exist_ok=True)
        session_filename = session.get('chat_session_file')
        if not session_filename:
            session_filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            session['chat_session_file'] = session_filename
        session_log_path = os.path.join(base_dir, session_filename)
        audit_log_path = os.path.join(base_dir, f"audit-{datetime.now().strftime('%Y%m%d')}.log")

        # 写入请求历史到会话文件
        _log_chat_request(session_log_path, username, model, lang, session_filename, messages)

        # 构造并返回流式响应
        ip_addr = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

        # 根据模型名称选择不同的生成器
        if '/' in model:  # SiliconFlow 模型，格式如 'deepseek-ai/deepseek-llm-67b-chat'
            generator = _siliconflow_stream_generator(
                model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename
            )
        else:  # 本地 Ollama 模型
            generator = _ollama_stream_generator(
                model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename
            )

        return Response(generator, mimetype='text/plain; charset=utf-8')

    except Exception as e:
        current_app.logger.error(f"[chat_api chat_stream] Unhandled error: {e}")
        return Response(f"An unexpected error occurred on the server: {e}", status=500, mimetype='text/plain')


# ==============================================================================
# 流式生成器
# ==============================================================================

def _ollama_stream_generator(model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename):
    """生成器函数，用于处理对本地 Ollama 的流式请求。"""
    final_assistant_message = ''
    error_text = None
    total_chars = 0
    ollama_url = 'http://127.0.0.1:11434/api/chat'
    payload = {'model': model, 'messages': messages, 'stream': True}

    try:
        with requests.post(ollama_url, json=payload, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                error_text = f'Ollama API Error ({resp.status_code}): {resp.text}'
                current_app.logger.error(error_text)
                yield error_text
                return
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get('message', {}).get('content', '')
                    if content:
                        final_assistant_message += content
                        total_chars += len(content)
                        yield content
                    if chunk.get('done'):
                        break
                except json.JSONDecodeError:
                    continue
        if final_assistant_message:
            _log_chat_response(session_log_path, final_assistant_message)
    except requests.exceptions.RequestException as e:
        error_text = f"Connection error to Ollama: {e}"
        yield error_text
    finally:
        _log_audit_record(audit_log_path, username, ip_addr, model, session_filename, total_chars, error_text)


def _siliconflow_stream_generator(model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename):
    """生成器函数，用于处理对 SiliconFlow 云端 API 的流式请求。"""
    final_assistant_message = ''
    error_text = None
    total_chars = 0
    api_key = _get_siliconflow_api_key()

    if not api_key:
        error_text = "SiliconFlow API key is missing or invalid."
        yield error_text
        _log_audit_record(audit_log_path, username, ip_addr, model, session_filename, 0, error_text)
        return

    api_url = 'https://api.siliconflow.cn/v1/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}'}
    payload = {'model': model, 'messages': messages, 'stream': True}

    try:
        with requests.post(api_url, json=payload, headers=headers, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                error_text = f'SiliconFlow API Error ({resp.status_code}): {resp.text}'
                current_app.logger.error(error_text)
                yield error_text
                return
            for byte_line in resp.iter_lines():
                if not byte_line:
                    continue

                line = byte_line.decode('utf-8')

                if line.startswith('data: '):
                    line_data = line[len('data: '):].strip()
                    if line_data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(line_data)
                        content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            final_assistant_message += content
                            total_chars += len(content)
                            yield content
                    except json.JSONDecodeError:
                        continue
        if final_assistant_message:
            _log_chat_response(session_log_path, final_assistant_message)
    except requests.exceptions.RequestException as e:
        error_text = f"Connection error to SiliconFlow: {e}"
        yield error_text
    finally:
        _log_audit_record(audit_log_path, username, ip_addr, model, session_filename, total_chars, error_text)


# ==============================================================================
# 聊天日志辅助函数
# ==============================================================================

def _log_chat_request(file_path, user, model, lang, session_file, messages):
    """记录用户请求和会话元数据到日志文件。"""
    try:
        is_new_file = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
        with open(file_path, 'a', encoding='utf-8') as f:
            if is_new_file:
                meta = {
                    'type': 'meta', 'timestamp': datetime.now().isoformat(),
                    'user': user, 'model': model, 'lang': lang, 'session_file': session_file,
                }
                f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            for msg in messages:
                f.write(json.dumps({'type': 'message', **msg}, ensure_ascii=False) + '\n')
    except Exception as e:
        current_app.logger.warning(f'Failed to write chat request to {file_path}: {e}')


def _log_chat_response(file_path, content):
    """记录模型的最终完整回复。"""
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            response_msg = {'type': 'message', 'role': 'assistant', 'content': content}
            f.write(json.dumps(response_msg, ensure_ascii=False) + '\n')
    except Exception as e:
        current_app.logger.warning(f'Failed to write chat response to {file_path}: {e}')


def _log_audit_record(audit_path, user, ip, model, title, length, error):
    """记录单次请求的审计信息。"""
    try:
        log_entry = {
            'time': datetime.now().isoformat(), 'user': user, 'ip': ip,
            'model': model, 'title': title, 'resp_length': length, 'error': error,
        }
        with open(audit_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        current_app.logger.warning(f'Failed to write audit log to {audit_path}: {e}')
