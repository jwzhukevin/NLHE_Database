# -*- coding: utf-8 -*-
"""
搜索API蓝图
路由：搜索建议、元素分析、能带配置
"""
from flask import Blueprint, jsonify, request, current_app
from collections import defaultdict

search_api_bp = Blueprint('search_api', __name__, url_prefix='/api/search')


# ==================== 辅助函数 ====================

def _get_element_suggestions(query):
    """获取元素建议"""
    from ..services import chemical_parser
    
    suggestions = []
    query_lower = query.lower()

    for element in chemical_parser.elements:
        if element.lower().startswith(query_lower):
            suggestions.append({
                'type': 'element',
                'value': element,
                'label': f"{element} (Element)",
                'category': 'Elements'
            })

    return suggestions[:10]


# ==================== 路由 ====================

@search_api_bp.route('/suggestions')
def search_suggestions():
    """
    提供实时搜索建议

    参数:
        q: 搜索查询字符串
        type: 建议类型 ('all', 'materials', 'elements', 'mp_ids', 'space_groups')
        limit: 返回结果数量限制 (默认10)
    """
    from ..models import Material

    query = request.args.get('q', '').strip()
    suggestion_type = request.args.get('type', 'all')
    limit = min(int(request.args.get('limit', 10)), 50)

    if len(query) < 2:
        return jsonify({'suggestions': []})

    suggestions = []

    try:
        if suggestion_type in ['all', 'materials']:
            material_suggestions = Material.query.filter(
                Material.name.ilike(f'%{query}%')
            ).limit(limit).all()

            for material in material_suggestions:
                suggestions.append({
                    'type': 'material',
                    'value': material.name,
                    'label': f"{material.name} ({material.formatted_id})",
                    'category': 'Materials'
                })

        if suggestion_type in ['all', 'mp_ids']:
            mp_suggestions = Material.query.filter(
                Material.mp_id.ilike(f'%{query}%')
            ).limit(limit).all()

            for material in mp_suggestions:
                if material.mp_id:
                    suggestions.append({
                        'type': 'mp_id',
                        'value': material.mp_id,
                        'label': f"{material.mp_id} - {material.name}",
                        'category': 'MP IDs'
                    })

        if suggestion_type in ['all', 'space_groups']:
            sg_suggestions = Material.query.filter(
                Material.sg_name.ilike(f'%{query}%')
            ).distinct(Material.sg_name).limit(limit).all()

            for material in sg_suggestions:
                if material.sg_name:
                    suggestions.append({
                        'type': 'space_group',
                        'value': material.sg_name,
                        'label': f"{material.sg_name} (#{material.sg_num})",
                        'category': 'Space Groups'
                    })

        if suggestion_type in ['all', 'elements']:
            element_suggestions = _get_element_suggestions(query)
            suggestions.extend(element_suggestions)

        # 去重并限制数量
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            key = (suggestion['type'], suggestion['value'])
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
                if len(unique_suggestions) >= limit:
                    break

        return jsonify({'suggestions': unique_suggestions})

    except Exception as e:
        current_app.logger.error(f"Search suggestions error: {str(e)}")
        return jsonify({'suggestions': [], 'error': 'Internal server error'}), 500


@search_api_bp.route('/element-analysis')
def element_analysis():
    """
    分析选中元素的相关信息

    参数:
        elements: 逗号分隔的元素列表
    """
    from ..models import Material
    from ..services import chemical_parser

    elements_param = request.args.get('elements', '')
    if not elements_param:
        return jsonify({'error': 'No elements provided'}), 400

    elements = [e.strip() for e in elements_param.split(',') if e.strip()]

    try:
        similar_elements = chemical_parser.suggest_similar_elements(elements)
        group_matches = chemical_parser.find_element_group_matches(elements)

        elements_logic = (request.args.get('elements_logic', 'or') or 'or').lower()
        if elements_logic not in ('or', 'and'):
            elements_logic = 'or'

        all_materials = Material.query.all()

        total = 0
        count_S = 0
        count_e = defaultdict(int)
        count_S_e = defaultdict(int)

        parsed_material_elements = []
        S = set(elements)

        for material in all_materials:
            name = getattr(material, 'name', None)
            if not name:
                continue
            try:
                elems = chemical_parser.get_elements_from_formula(name)
            except Exception:
                elems = set()
            if not elems:
                continue

            parsed_material_elements.append(elems)
            total += 1

            for e in elems:
                count_e[e] += 1

        def match_S(elems: set) -> bool:
            if not S:
                return False
            if elements_logic == 'and':
                return S.issubset(elems)
            return bool(S & elems)

        for elems in parsed_material_elements:
            if match_S(elems):
                count_S += 1
                for e in elems:
                    if e in S:
                        continue
                    count_S_e[e] += 1

        material_count = count_S

        partners = []
        if total > 0 and count_S > 0:
            for e, c_se in count_S_e.items():
                c_e = count_e.get(e, 0)
                cond = c_se / max(count_S, 1)
                if c_se < 2 or cond < 0.1:
                    continue
                lift = (c_se / total) / (((count_S / total) * (c_e / total)) + 1e-12)
                score = lift * cond
                partners.append({
                    'element': e,
                    'score': float(score),
                    'count_s_e': int(c_se),
                    'count_s': int(count_S),
                    'count_e': int(c_e),
                    'lift': float(lift),
                    'cond': float(cond),
                })

            partners.sort(key=lambda x: x['score'], reverse=True)
            partners = partners[:10]

        return jsonify({
            'selected_elements': elements,
            'similar_elements': similar_elements[:10],
            'element_groups': {k: list(v) for k, v in group_matches.items()},
            'material_count': material_count,
            'partners': partners,
            'analysis': {
                'total_elements': len(elements),
                'has_metals': bool(set(elements) & chemical_parser.element_groups.get('transition_metals', set())),
                'has_nonmetals': bool(set(elements) & {'C', 'N', 'O', 'F', 'P', 'S', 'Cl', 'Se', 'Br', 'I'}),
            }
        })

    except Exception as e:
        current_app.logger.error(f"Element analysis error: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500


@search_api_bp.route('/band-config')
def get_band_config():
    """获取能带分析配置，供前端使用"""
    try:
        from ..services import BandAnalysisConfig
        config = {
            'fermiLevel': BandAnalysisConfig.DEFAULT_FERMI_LEVEL,
            'tolerance': BandAnalysisConfig.FERMI_TOLERANCE,
            'metalThreshold': BandAnalysisConfig.METAL_THRESHOLD,
            'semimetalThreshold': BandAnalysisConfig.SEMIMETAL_THRESHOLD,
            'semiconductorThreshold': BandAnalysisConfig.SEMICONDUCTOR_THRESHOLD,
            'energyPrecision': BandAnalysisConfig.ENERGY_PRECISION
        }
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get band config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 已废弃的API ====================

@search_api_bp.route('/materials/update-band-gap', methods=['POST'])
def update_band_gap():
    """[已废弃] 写操作端点已禁用"""
    return jsonify({
        'success': False,
        'error': 'Write operations are disabled (read-only mode).',
        'status': 410
    }), 410
