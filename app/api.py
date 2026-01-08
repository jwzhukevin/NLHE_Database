# -*- coding: utf-8 -*-
# app/api.py
"""
本模块提供所有后端API接口，主要分为两大功能：
1. 材料结构数据API：提供晶体结构数据的查询、转换（如原胞、超晶胞）及文件下载功能。
2. AI聊天API：提供与大语言模型交互的流式聊天接口。

所有接口均定义在 /api 蓝图下，并遵循RESTful原则。
"""

import json
import os
from datetime import datetime

import requests
from flask import (Blueprint, Response, current_app, jsonify, request, session)
from flask_login import current_user, login_required
from pymatgen.io.cif import CifWriter

from .models import Material
from .structure_parser import (
    _process_structure, find_structure_file, generate_supercell, parse_cif_file
)

# ==============================================================================
# API 蓝图定义
# ==============================================================================

# 创建一个名为 'api' 的蓝图，所有在此定义的路由都会自动添加 /api 前缀
bp = Blueprint('api', __name__, url_prefix='/api')


# ==============================================================================
# 内部辅助函数 (Internal Helper Functions)
# ==============================================================================

def _find_structure_file_path(material_id, material_name=None):
    """根据材料ID和名称查找结构文件的绝对路径，封装重复逻辑。"""
    # 优先使用 material_id 查找
    file_relative_path = find_structure_file(material_id=material_id)
    
    # 如果找不到，且提供了 material_name，则尝试使用名称查找（兼容旧目录结构）
    if not file_relative_path and material_name:
        file_relative_path = find_structure_file(material_name=material_name)
        
    if not file_relative_path:
        return None

    # 构建并返回绝对路径
    file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
    return file_path if os.path.exists(file_path) else None

# ==============================================================================
# (一) 材料结构数据 API (Structure Data APIs)
# ==============================================================================

@bp.route('/database/functional_materials/structure/<int:material_id>', methods=['GET'])
def get_structure(material_id):
    """
    获取指定ID材料的基础结构数据。

    这是最核心的结构数据查询接口，返回包含原子、晶格等信息的JSON。
    """
    try:
        # 验证材料是否存在，若不存在则直接返回404
        Material.query.get_or_404(material_id)
        
        # 调用解析器获取结构数据
        structure_data = parse_cif_file(material_id=material_id)
        result = json.loads(structure_data)
        
        # 如果解析过程中出现错误（如文件损坏），则返回404
        if 'error' in result:
            return jsonify({
                "error": f"Could not find or parse structure data for material ID: {material_id}",
                "details": result['error']
            }), 404
        
        # 成功则返回JSON格式的结构数据
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        current_app.logger.error(f"[API get_structure] Error for ID {material_id}: {e}")
        return jsonify({"error": "An internal error occurred."}), 500


@bp.route('/database/functional_materials/structure', methods=['GET'])
def get_structure_by_params():
    """
    通过URL查询参数 `?material_id=<id>` 获取结构数据。
    
    这是详情页调用的主要结构数据接口。
    """
    try:
        material_id_str = request.args.get('material_id')
    
        # 验证 material_id 参数是否存在
        if not material_id_str:
            return jsonify({"error": "Query parameter 'material_id' is required."}), 400
    
        try:
            material_id = int(material_id_str)
            # 直接调用核心函数，复用逻辑
            return get_structure(material_id)
            
        except ValueError:
            return jsonify({"error": "Invalid material_id format. Must be an integer."}), 400
    
    except Exception as e:
        current_app.logger.error(f"[API get_structure_by_params] Error: {e}")
        return jsonify({"error": "An internal error occurred."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/conventional', methods=['GET'])
def get_conventional_cell(material_id):
    """
    获取指定材料的“传统晶胞”(conventional cell)结构数据。
    """
    try:
        material = Material.query.get_or_404(material_id)
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 使用pymatgen加载结构并转换为传统晶胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='conventional')
        structure_data['id'] = material_id
        
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"[API get_conventional_cell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to process conventional cell."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/primitive', methods=['GET'])
def get_primitive_cell(material_id):
    """
    获取指定材料的“原始晶胞”(primitive cell)结构数据。
    """
    try:
        material = Material.query.get_or_404(material_id)
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404

        # 使用pymatgen加载结构并转换为原始晶胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='primitive')
        structure_data['id'] = material_id
        
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"[API get_primitive_cell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to process primitive cell."}), 500


@bp.route('/database/functional_materials/structure/<int:material_id>/supercell', methods=['GET'])
def get_supercell(material_id):
    """
    根据请求参数动态生成并返回“超晶胞”(supercell)结构。
    
    查询参数:
        a, b, c (int): 沿三个晶轴方向的扩展倍数 (1-5)。
        cellType (str): 'primitive' 或 'conventional'，指定在哪种晶胞基础上扩展。
    """
    try:
        material = Material.query.get_or_404(material_id)
        
        # --- 参数获取与验证 --- #
        a = int(request.args.get('a', 1))
        b = int(request.args.get('b', 1))
        c = int(request.args.get('c', 1))
        cell_type = request.args.get('cellType', 'primitive')
        
        # 验证扩展倍数是否在合理范围内
        if not (1 <= a <= 5 and 1 <= b <= 5 and 1 <= c <= 5):
            return jsonify({"error": "Invalid supercell dimensions. Each must be between 1 and 5."}), 400
        
        # 验证基础晶胞类型是否合法
        if cell_type not in ['primitive', 'conventional']:
            return jsonify({"error": "Invalid cell type. Must be 'primitive' or 'conventional'."}), 400
        
        # --- 核心逻辑 --- #
        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
            
        # 调用生成超晶胞的函数
        result = generate_supercell(file_path, a=a, b=b, c=c, cell_type=cell_type)
        result_data = json.loads(result)
        
        if 'error' in result_data:
            return jsonify({"error": result_data['error']}), 400
        
        return result, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        current_app.logger.error(f"[API get_supercell] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to generate supercell."}), 500

# ==============================================================================
# (二) 结构文件下载 API (File Download API)
# ==============================================================================

@bp.route('/database/functional_materials/structure/<int:material_id>/cif', methods=['GET'])
def download_cif(material_id):
    """
    提供CIF格式的结构文件下载功能，支持动态生成超晶胞后下载。

    查询参数 (可选):
        a, b, c (int): 用于生成超晶胞的扩展倍数。
        cellType (str): 'primitive' 或 'conventional'。
    """
    try:
        material = Material.query.get_or_404(material_id)
        
        # --- 参数解析 --- #
        a = request.args.get('a')
        b = request.args.get('b')
        c = request.args.get('c')
        cell_type = request.args.get('cellType')
        is_supercell = all([a, b, c])

        file_path = _find_structure_file_path(material_id, material.name)
        if not file_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # --- CIF 内容生成 --- #
        if is_supercell:
            # 动态生成超晶胞的CIF内容
            from pymatgen.core import Structure
            structure = Structure.from_file(file_path)
            
            a_val, b_val, c_val = int(a), int(b), int(c)
            if not (1 <= a_val <= 5 and 1 <= b_val <= 5 and 1 <= c_val <= 5):
                return jsonify({"error": "Invalid supercell dimensions."}), 400
            
            if cell_type == 'conventional':
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure)
                structure = analyzer.get_conventional_standard_structure()
            
            supercell = structure.make_supercell([a_val, b_val, c_val])
            cif_string = CifWriter(supercell).write_str()
            filename = f"{material.name}_supercell_{a_val}x{b_val}x{c_val}.cif"
        else:
            # 直接读取原始CIF文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                cif_string = f.read()
            filename = f"{material.name}.cif"
        
        # --- 构造文件下载响应 --- #
        return Response(
            cif_string,
            mimetype="chemical/x-cif",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    
    except Exception as e:
        current_app.logger.error(f"[API download_cif] Error for ID {material_id}: {e}")
        return jsonify({"error": "Failed to generate CIF file for download."}), 500


# ==============================================================================
# (三) AI聊天 API (Chat Streaming API)
# ==============================================================================

# 全局缓存SiliconFlow API密钥
SILICONFLOW_API_KEY = None

def _get_siliconflow_api_key():
    """
    读取并缓存SiliconFlow API密钥。
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


@bp.route('/chat/stream', methods=['POST'])
@login_required
def chat_stream():
    """
    处理流式聊天请求，根据模型名称智能选择本地Ollama或云端SiliconFlow API。
    """
    try:
        # --- 0. 预热API密钥缓存 --- #
        # 在请求上下文中调用此函数，以安全地缓存密钥供生成器稍后使用
        _get_siliconflow_api_key()

        # --- 1. 解析前端请求 --- #
        data = request.get_json(silent=True) or {}
        messages = data.get('messages') or []
        model = data.get('model', 'deepseek-r1:14b').strip()
        lang = data.get('lang', 'en')

        # --- 2. 设置日志与会话文件路径 --- #
        username = getattr(current_user, 'username', 'guest')
        base_dir = os.path.join(current_app.root_path, 'static', 'chat', username)
        os.makedirs(base_dir, exist_ok=True)
        session_filename = session.get('chat_session_file')
        if not session_filename:
            session_filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            session['chat_session_file'] = session_filename
        session_log_path = os.path.join(base_dir, session_filename)
        audit_log_path = os.path.join(base_dir, f"audit-{datetime.now().strftime('%Y%m%d')}.log")

        # --- 3. 写入请求历史到会话文件 --- #
        _log_chat_request(session_log_path, username, model, lang, session_filename, messages)

        # --- 4. 构造并返回流式响应 --- #
        ip_addr = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
        
        # 根据模型名称选择不同的生成器
        if '/' in model:  # SiliconFlow模型，格式如 'deepseek-ai/deepseek-llm-67b-chat'
            generator = _siliconflow_stream_generator(model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename)
        else:  # 本地Ollama模型
            generator = _ollama_stream_generator(model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename)

        return Response(generator, mimetype='text/plain; charset=utf-8')

    except Exception as e:
        current_app.logger.error(f"[API chat_stream] Unhandled error: {e}")
        return Response(f"An unexpected error occurred on the server: {e}", status=500, mimetype='text/plain')

def _ollama_stream_generator(model, messages, audit_log_path, session_log_path, username, ip_addr, session_filename):
    """生成器函数，用于处理对本地Ollama的流式请求。"""
    final_assistant_message = ''
    error_text = None
    total_chars = 0
    ollama_url = 'http://127.0.0.1:11434/api/chat'
    payload = {'model': model, 'messages': messages, 'stream': True}

    try:
        with requests.post(ollama_url, json=payload, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                error_text = f'Ollama API Error ({resp.status_code}): {resp.text}'
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
    """生成器函数，用于处理对SiliconFlow云端API的流式请求。"""
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
                yield error_text
                return
            for byte_line in resp.iter_lines():
                if not byte_line:
                    continue
                
                line = byte_line.decode('utf-8')  # 强制使用UTF-8解码

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


# --- 聊天日志辅助函数 --- #

def _log_chat_request(file_path, user, model, lang, session_file, messages):
    """记录用户请求和会话元数据到日志文件。"""
    try:
        is_new_file = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
        with open(file_path, 'a', encoding='utf-8') as f:
            if is_new_file:
                meta = {'type': 'meta', 'timestamp': datetime.now().isoformat(), 'user': user, 'model': model, 'lang': lang, 'session_file': session_file}
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
        log_entry = {'time': datetime.now().isoformat(), 'user': user, 'ip': ip, 'model': model, 'title': title, 'resp_length': length, 'error': error}
        with open(audit_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        current_app.logger.warning(f'Failed to write audit log to {audit_path}: {e}')


# ==============================================================================
# CSRF 豁免设置
# ==============================================================================

# 为流式聊天端点豁免CSRF保护，因为它不使用传统的表单提交机制
try:
    from . import csrf as _csrf
    if _csrf is not None:
        _csrf.exempt(chat_stream)
except (ImportError, AttributeError):
    # 如果应用中没有配置CSRF模块，则静默忽略
    pass