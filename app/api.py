# api.py
# 提供结构数据的API接口
# 本文件包含所有与晶体结构相关的API端点，处理结构数据的获取、上传和转换

import json
import os
import glob
from flask import Blueprint, jsonify, request, current_app, Response, session
from flask_login import login_required, current_user
import requests
import redis
from datetime import datetime
import re
from .models import Material, db
from .structure_parser import parse_cif_file, save_structure_file, find_structure_file, generate_supercell, get_cif_data, _process_structure, generate_primitive_cell
from pymatgen.io.cif import CifWriter
from .material_importer import extract_chemical_formula_from_cif

# 创建API蓝图
# 定义前缀为/api的路由组
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/structure/<int:material_id>', methods=['GET'])
def get_structure(material_id):
    """
    获取指定材料的结构数据（原/常规由 parser 内部按策略处理）。

    参数：
        material_id: 材料 ID，用于查询材料记录与查找结构文件。

    返回：
        JSON（字符串或 jsonify 响应）：包含原子坐标、晶格参数与对称信息。
        当找不到文件或解析失败时，返回 404 或 500 错误信息。
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 获取结构数据
        structure_data = parse_cif_file(material_id=material_id)
        result = json.loads(structure_data)
        
        # 检查是否存在错误
        if 'error' in result:
            return jsonify({
                "error": f"Could not find structure data for material ID: {material_id}",
                "details": result['error']
            }), 404
        
        return structure_data, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
@bp.route('/structure/<int:material_id>/conventional', methods=['GET'])
def get_conventional_cell(material_id):
    """
    获取指定材料的传统胞（conventional cell）结构数据。

    参数：
        material_id: 材料 ID。

    返回：
        JSON（jsonify）：包含常规胞结构与对称性。
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 说明：全局统一 ID 显示为 IMR-{id}（不补零），避免多种格式混用
        formatted_id = f"IMR-{int(material_id)}"
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
            
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 加载结构并转换为传统胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='conventional')
        
        # 添加材料ID到结构数据中
        structure_data['id'] = material_id
        
        # 返回JSON响应
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"Error converting to conventional cell: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/structure/upload/<int:material_id>', methods=['POST'])
def upload_structure(material_id):
    """
    [Deprecated 20251001] 写操作端点已禁用：只读模式
    """
    return jsonify({
        "success": False,
        "error": "Write operations are disabled (read-only mode).",
        "status": 410
    }), 410


@bp.route('/structure/<int:material_id>/supercell', methods=['GET'])
def get_supercell(material_id):
    """
    生成并返回扩展的超晶胞结构。

    参数：
        material_id: 材料 ID；
        a, b, c: 查询参数，分别为 a/b/c 方向的扩展倍数（1-5）；
        cellType: 查询参数，可取 'primitive' 或 'conventional'。

    返回：
        JSON（字符串或 jsonify）：包含超晶胞结构数据与晶格参数。
    """
    try:
        material = Material.query.get_or_404(material_id)
        
        # 获取请求参数并验证
        a = int(request.args.get('a', 1))
        b = int(request.args.get('b', 1))
        c = int(request.args.get('c', 1))
        cell_type = request.args.get('cellType', 'primitive')
        
        # 参数验证
        if min(a, b, c) < 1 or max(a, b, c) > 5:
            return jsonify({"error": "Invalid supercell dimensions. Must be between 1 and 5."}), 400
        
        if cell_type not in ['primitive', 'conventional']:
            return jsonify({"error": "Invalid cell type. Must be 'primitive' or 'conventional'."}), 400
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
            
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 生成超晶胞
        result = generate_supercell(file_path, a=a, b=b, c=c, cell_type=cell_type)
        result_data = json.loads(result)
        
        # 检查错误
        if 'error' in result_data:
            return jsonify({"error": result_data['error']}), 400
        
        return result, 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/cif', methods=['GET'])
def download_cif(material_id):
    """
    获取材料的 CIF 文件数据（可选生成超晶胞后导出）。

    参数：
        material_id: 材料 ID；
        a, b, c: 查询参数，生成超晶胞的扩展倍数（可选）；
        cellType: 查询参数，'primitive' 或 'conventional'（可选）。

    返回：
        Flask Response：`chemical/x-cif` 响应并附下载文件名。
    """
    try:
        # 查询材料记录，如果不存在则返回404
        material = Material.query.get_or_404(material_id)
        
        # 获取请求参数，确定是否需要生成超晶胞
        a = request.args.get('a')
        b = request.args.get('b')
        c = request.args.get('c')
        cell_type = request.args.get('cellType')
        
        # 判断是否为普通下载还是超晶胞下载
        is_supercell = all([a, b, c])
        
        # 说明：全局统一 ID 文本为 IMR-{id}（不补零），此处不再构造 8 位补零格式
        # 注意：下载文件名仍以材料 name 为主，ID 文本仅用于显示/日志，不强制需要
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
        
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
            
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 根据请求参数处理文件
        if is_supercell:
            # 如果请求超晶胞，生成并返回超晶胞CIF
            from pymatgen.core import Structure
            structure = Structure.from_file(file_path)
            
            # 将参数转换为整数
            a_val = int(a)
            b_val = int(b)
            c_val = int(c)
            
            # 参数验证
            if a_val < 1 or b_val < 1 or c_val < 1 or a_val > 5 or b_val > 5 or c_val > 5:
                return jsonify({"error": "Invalid supercell dimensions. Must be between 1 and 5."}), 400
            
            # 处理晶胞类型
            if cell_type == 'conventional':
                from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                analyzer = SpacegroupAnalyzer(structure)
                structure = analyzer.get_conventional_standard_structure()
            
            # 生成超晶胞
            supercell = structure.make_supercell([a_val, b_val, c_val])
            
            # 创建CIF写入器
            cif_writer = CifWriter(supercell)
            cif_string = cif_writer.write_str()
            
            # 构建文件名
            filename = f"{material.name}_supercell_{a_val}x{b_val}x{c_val}.cif"
        else:
            # 普通下载，直接读取文件内容
            with open(file_path, 'r') as f:
                cif_string = f.read()
            
            # 使用材料名称作为文件名
            filename = f"{material.name}.cif"
        
        # 返回CIF文件内容，设置正确的响应头
        response = current_app.response_class(
            cif_string,
            mimetype="chemical/x-cif",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
        return response
    
    except Exception as e:
        # 记录错误并返回500错误
        current_app.logger.error(f"Error downloading CIF file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@bp.route('/structure/<int:material_id>/primitive', methods=['GET'])
def get_primitive_cell(material_id):
    """
    获取指定材料的原始胞（primitive cell）结构数据。

    参数：
        material_id: 材料 ID。

    返回：
        JSON（jsonify）：包含原胞结构与对称性。
    """
    try:
        # 查询材料记录
        material = Material.query.get_or_404(material_id)
        
        # 说明：全局统一 ID 文本为 IMR-{id}（不补零），此处无需构造补零格式
        
        # 获取结构文件路径
        file_relative_path = find_structure_file(material_id=material_id)
        
        if not file_relative_path:
            # 如果在新目录结构中没有找到，尝试在旧目录中查找
            file_relative_path = find_structure_file(material_name=material.name)
        
        if not file_relative_path:
            return jsonify({"error": "Structure file not found"}), 404
        
        # 构建完整文件路径
        file_path = os.path.join(current_app.root_path, 'static', file_relative_path)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Structure file not found"}), 404
        
        # 加载结构并转换为原始胞
        from pymatgen.core import Structure
        structure = Structure.from_file(file_path)
        structure_data = _process_structure(structure, cell_type='primitive')
        
        # 添加材料ID到结构数据中
        structure_data['id'] = material_id
        
        # 返回JSON响应
        return jsonify(structure_data)
    
    except Exception as e:
        current_app.logger.error(f"Error converting to primitive cell: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/structure', methods=['GET'])
def get_structure_by_params():
    """
    通过 `material_id` 查询参数获取结构数据（便于简单前端调用）。

    参数：
        material_id: 查询字符串参数。

    返回：
        JSON：结构数据或错误信息；material_id 缺失/无效返回 400。
    """
    try:
        # 获取查询参数
        material_id = request.args.get('material_id')
    
        # 必须提供material_id参数
        if not material_id:
            return jsonify({"error": "Material ID must be provided"}), 400
    
        # 使用material_id查找对应的cif文件
        try:
            material_id = int(material_id)
            # 获取结构数据
            structure_data = parse_cif_file(material_id=material_id)
            
            # 解析JSON结果
            result = json.loads(structure_data)
    
            # 检查结果中是否有错误
            if 'error' in result:
                return jsonify(result), 404
            
            # 确保sites数据格式正确（用于前端显示）
            if 'atoms' in result and isinstance(result['atoms'], list):
                # 创建前端需要的sites数组格式
                sites = []
                for atom in result['atoms']:
                    # 从properties中获取wyckoff位置
                    wyckoff = atom.get('properties', {}).get('wyckoff', '-')
                    site = {
                        'species': [{'element': atom['element']}],
                        'xyz': atom['position'],
                        'frac_coords': atom['frac_coords'],
                        'wyckoff': wyckoff
                    }
                    sites.append(site)
            
                # 如果结果中没有sites字段，添加它
                if 'sites' not in result or not result['sites']:
                    result['sites'] = sites
            
            # 确保symmetry对象包含space_group_symbol字段
            if 'symmetry' in result:
                result['symmetry']['space_group_symbol'] = result['symmetry'].get('symbol', 'Unknown')
            
            # 返回JSON响应
            return jsonify(result)
            
        except ValueError:
            return jsonify({"error": "Invalid material_id format"}), 400
    
    except Exception as e:
        current_app.logger.error(f"Error getting structure data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/structure/update-names', methods=['POST'])
def update_material_names():
    """
    [Deprecated 20251001] 写操作端点已禁用：只读模式
    """
    return jsonify({
        "success": False,
        "error": "Write operations are disabled (read-only mode).",
        "status": 410
    }), 410

@bp.route('/materials/<int:material_id>/update-metal-type', methods=['POST'])
def update_material_metal_type(material_id):
    """
    [Deprecated 20250825]
    旧逻辑：手动更新 metal_type。现已废弃，材料类型改由 band.json
    自动分析生成并写入模型字段 materials_type，禁止通过此端点修改。

    参数:
        material_id: 材料ID（为保持向后兼容而保留）

    返回:
        410 Gone，提示接口已废弃
    """
    # 说明性日志：提醒调用方迁移到新机制
    try:
        _ = Material.query.get_or_404(material_id)
        current_app.logger.warning(
            "[Deprecated] update-metal-type endpoint called. "
            "materials_type is derived from band.json and cannot be updated "
            "via API."
        )
        return jsonify({
            "success": False,
            "error": "This endpoint is deprecated. materials_type is derived "
                      "from band.json and cannot be updated via API.",
            "status": 410
        }), 410
    except Exception as e:
        current_app.logger.error(
            f"Error handling deprecated update-metal-type: {str(e)}"
        )
        return jsonify({"error": str(e)}), 500

# ===================== Chat Streaming Endpoint =====================
@bp.route('/chat/stream', methods=['POST'])
@login_required
def chat_stream():
    """
    流式聊天端点：对接硅基流动 DeepSeek（OpenAI 兼容接口）。

    输入（JSON）：
      - messages: [{role: 'user'|'assistant'|'system', content: str}, ...]
      - model: 默认 'deepseek-chat'
      - lang: 'zh'|'en'（可选）
    """
    data = request.get_json(silent=True) or {}
    messages = data.get('messages') or []
    raw_model = (data.get('model') or '').strip()
    # 兼容旧值：deepseek-chat/deepseek 统一映射为 Hunyuan V3
    if not raw_model or raw_model.lower() in ('deepseek-chat', 'deepseek'):
        model = 'tencent/Hunyuan-MT-7B'
    else:
        model = raw_model
    lang = data.get('lang') or 'en'

    # 不做并发席位限制；仅组织存档路径
    username = getattr(current_user, 'username', 'user') or 'user'

    # 目录与标题
    base_dir = os.path.join(current_app.root_path, 'static', 'chat', username)
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass

    # 使用会话固定文件名：进入聊天页时生成，整场会话复用
    session_filename = session.get('chat_session_file')
    if not session_filename:
        session_filename = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        session['chat_session_file'] = session_filename
    file_path = os.path.join(base_dir, session_filename)
    # 生成审计文件按日期聚合
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    audit_path = os.path.join(base_dir, f"audit-{datetime.now().strftime('%Y%m%d')}.log")

    # 优先：代码内密钥；兜底：环境变量
    try:
        from .credentials import SILICONFLOW_API_KEY as CODE_API_KEY
    except Exception:
        CODE_API_KEY = ''
    api_key = CODE_API_KEY or os.getenv('SILICONFLOW_API_KEY', '')
    if not api_key:
        return Response('Server missing SILICONFLOW_API_KEY', status=500, mimetype='text/plain; charset=utf-8')

    url = 'https://api.siliconflow.cn/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': model,
        'messages': messages,
        'stream': True
    }

    # 预取可跨上下文使用的信息（避免生成器 finally 阶段访问上下文）
    try:
        logger_ref = current_app.logger
    except Exception:
        logger_ref = None
    ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

    # 写入 meta 与历史到存档（仅在文件为空时写入 meta）
    try:
        file_exists = os.path.exists(file_path)
        file_empty = (not file_exists) or (os.path.getsize(file_path) == 0)
        with open(file_path, 'a', encoding='utf-8') as f:
            if file_empty:
                meta = {
                    'type': 'meta',
                    'timestamp': ts,
                    'user': username,
                    'model': model,
                    'lang': lang,
                    'session_file': session_filename
                }
                f.write(json.dumps(meta, ensure_ascii=False) + '\n')
            for m in messages:
                f.write(json.dumps({'type': 'message', **m}, ensure_ascii=False) + '\n')
    except Exception as e:
        if logger_ref:
            logger_ref.warning(f'failed to write chat meta/messages: {e}')

    def stream_generator():
        total_len = 0
        err_text = None
        try:
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as resp:
                if resp.status_code != 200:
                    err = resp.text
                    err_text = f'Upstream {resp.status_code}: {err}'
                    yield err_text
                    return
                # 强制按 UTF-8 处理，避免编码猜测导致乱码
                resp.encoding = 'utf-8'
                assistant_acc = ''
                for raw_line in resp.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    # 明确以 UTF-8 解码，忽略异常字节
                    line = raw_line.decode('utf-8', 'ignore').strip()
                    if line == 'data: [DONE]':
                        break
                    if not line.startswith('data:'):
                        continue
                    try:
                        j = json.loads(line[len('data:'):].strip())
                        choices = j.get('choices') or []
                        delta = (choices[0].get('delta') if choices else {}) or {}
                        content = delta.get('content')
                        if content:
                            assistant_acc += content
                            total_len += len(content)
                            yield content
                    except Exception:
                        # 解析失败：不透传原始行，避免将 "data: {...}" 泄漏到前端
                        continue

                # 写入 assistant 最终回复
                try:
                    with open(file_path, 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'type': 'message', 'role': 'assistant', 'content': assistant_acc}, ensure_ascii=False) + '\n')
                except Exception as e:
                    if logger_ref:
                        logger_ref.warning(f'failed to write assistant message: {e}')
        finally:
            # 审计
            try:
                with open(audit_path, 'a', encoding='utf-8') as af:
                    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    logline = {
                        'time': stamp,
                        'user': username,
                        'ip': ip,
                        'model': model,
                        'title': session_filename,
                        'resp_length': total_len,
                        'error': err_text
                    }
                    af.write(json.dumps(logline, ensure_ascii=False) + '\n')
            except Exception as e:
                if logger_ref:
                    logger_ref.warning(f'failed to write audit log: {e}')

    
    return Response(stream_generator(), mimetype='text/plain; charset=utf-8')

# 为流式端点豁免 CSRF（仅此端点）
try:
    from . import csrf as _csrf
    if _csrf is not None:
        _csrf.exempt(chat_stream)
except Exception:
    pass

#（已移除占位限制相关 API）