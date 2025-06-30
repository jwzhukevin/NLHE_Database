import os, json, time
from flask import Blueprint, render_template, request, flash, session, current_app, redirect, url_for, jsonify
from flask_login import current_user, login_required
import requests

siliconflow_bp = Blueprint('siliconflow', __name__, url_prefix='/siliconflow')

API_URL = 'https://api.siliconflow.cn/v1/chat/completions'
API_KEY = 'sk-ywrgajeyefkbzukcxouatcqgxtebnbjdhmvrqtrqnvffykpn'

# 工具函数

def get_user_chat_dir():
    username = getattr(current_user, 'username', None)
    # 用 Flask 推荐的方式拼接路径，保证跨平台
    chat_dir = os.path.join(current_app.root_path, 'static', 'chat', str(username))
    os.makedirs(chat_dir, exist_ok=True)
    return chat_dir

def get_history_path(filename='history.json'):
    chat_dir = get_user_chat_dir()
    return os.path.join(chat_dir, filename)

def list_histories():
    chat_dir = get_user_chat_dir()
    files = [f for f in os.listdir(chat_dir) if f.endswith('.json')]
    # 排除默认history.json
    return [f for f in files if f != 'history.json']

def load_history(filename='history.json'):
    path = get_history_path(filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(history, filename='history.json'):
    path = get_history_path(filename)
    print(f"[调试] 保存历史到: {path}")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False)

def call_siliconflow(messages):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": "Qwen/QwQ-32B",
        "messages": messages,
        "stream": False,
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "response_format": {"type": "text"}
    }
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=20)
        print("[调试] AI接口原始响应：", response.text)
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        raise RuntimeError("AI接口请求超时，请稍后重试或检查网络/API服务状态。")
    except Exception as e:
        raise RuntimeError(f"AI接口返回异常：{e}，内容：{getattr(response, 'text', '')}")

@siliconflow_bp.route('/', methods=['GET', 'POST'])
@login_required
def chat():
    print("[调试] 进入 chat 视图函数")
    # 处理历史会话选择
    selected_history = request.form.get('history_select') or request.args.get('history') or 'current'
    print(f"[调试] selected_history: {selected_history}")
    if selected_history == 'current':
        filename = 'history.json'
    else:
        filename = selected_history
    # 加载历史会话列表
    history_list = list_histories()
    print(f"[调试] history_list: {history_list}")
    # 加载当前会话
    if 'chat_history' not in session or session.get('selected_history') != filename:
        session['chat_history'] = load_history(filename)
        session['selected_history'] = filename
    chat_history = session['chat_history']

    if request.method == 'POST':
        print(f"[调试] POST 数据: {request.form}")
        if 'delete_session' in request.form:
            # 删除当前会话历史文件，然后新建空会话
            if filename != 'history.json':
                import os
                file_path = get_history_path(filename)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"[调试] 已删除历史文件: {file_path}")
                except Exception as e:
                    print(f"[调试] 删除历史文件失败: {e}")
            else:
                # 默认会话只清空不删除
                save_history([], 'history.json')
            chat_history = []
            session['chat_history'] = []
            session['selected_history'] = 'history.json'
            return redirect(url_for('siliconflow.chat'))
        # 重新回答功能
        if 'retry_index' in request.form:
            retry_idx = int(request.form.get('retry_index'))
            print(f"[调试] 重新回答 index: {retry_idx}")
            if 0 <= retry_idx < len(chat_history):
                # 只删除该轮AI回答，保留用户问题
                user_question = chat_history[retry_idx]['user']
                chat_history = chat_history[:retry_idx]  # 保留之前的历史
                session['chat_history'] = chat_history
                # 重新请求AI
                messages = []
                for turn in chat_history:
                    messages.append({'role': 'user', 'content': turn['user']})
                    messages.append({'role': 'assistant', 'content': turn['assistant']})
                messages.append({'role': 'user', 'content': user_question})
                ai_reply = call_siliconflow(messages)
                chat_history.append({'user': user_question, 'assistant': ai_reply})
                session['chat_history'] = chat_history
                save_history(chat_history, filename)
            return redirect(url_for('siliconflow.chat', history=selected_history))
        # 删除回答功能
        if 'delete_index' in request.form:
            del_idx = int(request.form.get('delete_index'))
            print(f"[调试] 删除问答 index: {del_idx}")
            if 0 <= del_idx < len(chat_history):
                chat_history.pop(del_idx)
                session['chat_history'] = chat_history
                save_history(chat_history, filename)
            return redirect(url_for('siliconflow.chat', history=selected_history))
        if 'clear' in request.form:
            chat_history = []
            session['chat_history'] = []
            save_history([], filename)
            return redirect(url_for('siliconflow.chat', history=selected_history))
        elif 'new' in request.form:
            chat_history = []
            session['chat_history'] = []
            session['selected_history'] = 'history.json'
            return redirect(url_for('siliconflow.chat'))
        elif 'save' in request.form:
            # 保存为新会话
            save_name = request.form.get('save_name')
            print(f"[调试] save_name: {save_name}")
            if save_name:
                save_file = save_name + '.json'
                save_path = get_history_path(save_file)
                save_history(chat_history, save_file)
                flash(f'Session saved as {save_file}', 'success')
                return redirect(url_for('siliconflow.chat', history=save_file))
        elif 'rename' in request.form:
            old_file = selected_history
            new_name = request.form.get('rename_name')
            print(f"[调试] rename: {old_file} -> {new_name}")
            if new_name:
                new_file = new_name + '.json'
                old_path = get_history_path(old_file)
                new_path = get_history_path(new_file)
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
                    flash(f'Session renamed to {new_file}', 'success')
                    return redirect(url_for('siliconflow.chat', history=new_file))
        elif 'history_select' in request.form:
            # 切换历史会话
            session['chat_history'] = load_history(filename)
            session['selected_history'] = filename
            return redirect(url_for('siliconflow.chat', history=filename))
        else:
            user_input = request.form.get('prompt')
            print(f"[调试] user_input: {user_input}")
            if user_input:
                messages = []
                for turn in chat_history:
                    messages.append({'role': 'user', 'content': turn['user']})
                    messages.append({'role': 'assistant', 'content': turn['assistant']})
                messages.append({'role': 'user', 'content': user_input})
                ai_reply = call_siliconflow(messages)
                chat_history.append({'user': user_input, 'assistant': ai_reply})
                session['chat_history'] = chat_history
                save_history(chat_history, filename)
    return render_template('deepseek/chat.html', chat_history=chat_history, history_list=history_list, selected_history=filename)

@siliconflow_bp.route('/ask', methods=['POST'])
@login_required
def ask():
    data = request.get_json()
    user_input = data.get('prompt', '').strip()
    filename = data.get('history', 'history.json')
    if not user_input:
        return jsonify({'error': '问题不能为空'}), 400
    # 加载历史
    chat_history = load_history(filename)
    messages = []
    for turn in chat_history:
        messages.append({'role': 'user', 'content': turn['user']})
        messages.append({'role': 'assistant', 'content': turn['assistant']})
    messages.append({'role': 'user', 'content': user_input})
    ai_reply = call_siliconflow(messages)
    chat_history.append({'user': user_input, 'assistant': ai_reply})
    save_history(chat_history, filename)
    return jsonify({
        'assistant': ai_reply,
        'chat_history': chat_history
    }) 