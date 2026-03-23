# -*- coding: utf-8 -*-
"""
公式要素 CRUD API - 独立 Blueprint
"""
import time
import re
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# 独立的 formula-elements blueprint
formula_elements_bp = Blueprint('formula_elements', __name__, url_prefix='/api/knowledge')

# ========== 缓存（与 knowledge_api.py 保持同步） ==========
_formula_elements_cache = {}
_formula_elements_cache_ttl = 0


def _invalidate_formula_elements_cache(sub_category=None):
    """清除公式要素缓存"""
    if sub_category:
        _formula_elements_cache.pop(sub_category, None)
    else:
        _formula_elements_cache.clear()


def _load_formula_elements_from_db(sub_category):
    """从数据库加载公式要素"""
    from models.models import FormulaElementType
    try:
        elements = FormulaElementType.query.filter_by(
            sub_category=sub_category,
            is_active=True
        ).order_by(FormulaElementType.priority.asc()).all()
        logger.info(f"[_load_formula_elements_from_db] 从DB加载 {sub_category}, 找到 {len(elements)} 个要素")
        _formula_elements_cache[sub_category] = {
            'elements': elements,
            'updated_at': time.time()
        }
        return elements
    except Exception as e:
        logger.warning(f"从数据库加载公式要素失败: {e}")
        return None


def _get_cached_formula_elements(sub_category):
    """从缓存获取公式要素"""
    now = time.time()
    if sub_category in _formula_elements_cache:
        cached = _formula_elements_cache[sub_category]
        if now - cached.get('updated_at', 0) < _formula_elements_cache_ttl:
            return cached.get('elements')
    return _load_formula_elements_from_db(sub_category)


# ========== 路由注册（必须在 blueprint 注册之前执行） ==========

@formula_elements_bp.route('/formula-elements/', methods=['GET'])
def get_formula_elements():
    """获取所有公式要素（可按 sub_category 过滤，支持分页）"""
    from models.models import FormulaElementType

    sub_category = request.args.get('sub_category')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = FormulaElementType.query
    if sub_category:
        query = query.filter_by(sub_category=sub_category)

    pagination = query.order_by(
        FormulaElementType.sub_category,
        FormulaElementType.priority
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'code': 0,
        'data': [{
            'id': e.id,
            'sub_category': e.sub_category,
            'name': e.name,
            'code': e.code,
            'description': e.description,
            'examples': e.examples,
            'priority': e.priority,
            'is_active': e.is_active,
            'usage_tips': e.usage_tips,
            'created_at': e.created_at.isoformat() if e.created_at else None,
            'updated_at': e.updated_at.isoformat() if e.updated_at else None,
        } for e in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
        'per_page': per_page
    })


@formula_elements_bp.route('/formula-elements/', methods=['POST'])
def create_formula_element():
    """创建公式要素"""
    from models.models import FormulaElementType
    from flask_login import current_user

    data = request.get_json()

    required = ['sub_category', 'name']
    for field in required:
        if not data.get(field):
            return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'}), 400

    # 自动生成编码
    code = data.get('code', '').strip()
    if not code:
        pinyin_map = {
            '产品': 'product', '身份': 'identity', '职业': 'occupation', '地域': 'region',
            '年龄': 'age', '性别': 'gender', '兴趣': 'interest', '行为': 'behavior',
            '消费': 'consumption', '品牌': 'brand', '品质': 'quality', '价格': 'price',
            '风格': 'style', '功效': 'effect', '成分': 'ingredient', '材质': 'material',
            '颜色': 'color', '大小': 'size', '数量': 'quantity', '频率': 'frequency'
        }
        name = data['name']
        code = None
        for cn, en in pinyin_map.items():
            if cn in name:
                code = f"{en}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                break
        if not code:
            code = f"elem_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        code = re.sub(r'[^a-z0-9_]', '', code.lower())

    existing = FormulaElementType.query.filter_by(
        sub_category=data['sub_category'],
        code=code
    ).first()
    if existing:
        return jsonify({'code': 400, 'message': '该要素编码已存在'}), 400

    element = FormulaElementType(
        sub_category=data['sub_category'],
        name=data['name'],
        code=code,
        description=data.get('description', ''),
        examples=data.get('examples', ''),
        priority=data.get('priority', 0),
        is_active=data.get('is_active', True),
        usage_tips=data.get('usage_tips', '')
    )

    from models.models import db
    db.session.add(element)
    db.session.commit()

    _invalidate_formula_elements_cache(data['sub_category'])

    return jsonify({
        'code': 0,
        'message': '创建成功',
        'data': {'id': element.id}
    })


@formula_elements_bp.route('/formula-elements/<int:element_id>', methods=['PUT'])
def update_formula_element(element_id):
    """更新公式要素"""
    from models.models import FormulaElementType, db

    element = FormulaElementType.query.get(element_id)
    if not element:
        return jsonify({'code': 404, 'message': '要素不存在'}), 404

    data = request.get_json()

    if 'name' in data:
        element.name = data['name']
    if 'description' in data:
        element.description = data['description']
    if 'examples' in data:
        element.examples = data['examples']
    if 'priority' in data:
        element.priority = data['priority']
    if 'is_active' in data:
        element.is_active = data['is_active']
    if 'usage_tips' in data:
        element.usage_tips = data['usage_tips']

    db.session.commit()

    _invalidate_formula_elements_cache(element.sub_category)

    return jsonify({
        'code': 0,
        'message': '更新成功'
    })


@formula_elements_bp.route('/formula-elements/<int:element_id>', methods=['DELETE'])
def delete_formula_element(element_id):
    """删除公式要素"""
    from models.models import FormulaElementType, db

    element = FormulaElementType.query.get(element_id)
    if not element:
        return jsonify({'code': 404, 'message': '要素不存在'}), 404

    sub_category = element.sub_category

    db.session.delete(element)
    db.session.commit()

    _invalidate_formula_elements_cache(sub_category)

    return jsonify({
        'code': 0,
        'message': '删除成功'
    })


@formula_elements_bp.route('/formula-elements/init', methods=['POST'])
def init_formula_elements():
    """初始化默认公式要素"""
    from models.models import FormulaElementType, db

    import traceback

    try:
        nickname_elements = [
            {'code': 'identity_tag', 'name': '身份 / 人设词', 'description': '身份/职业/人设（如：哥、姐、老师、医生、创始人、魔女、西施）', 'examples': '哥|姐|老师|医生|创始人|黄姐|王老师|魔女|西施|侠客|公主|罗胖', 'priority': 1, 'usage_tips': '回答"你是谁"——职业、身份、人设。哥/姐（亲切称呼）、老师/医生（职业）、创始人（创业）、魔女/西施（虚拟人设）'},
            {'code': 'style_word', 'name': '风格 / 记忆词', 'description': '外观/气质/体型描述（如：红发、高冷、胖、瘦）', 'examples': '红发|高冷|胖|瘦|金丝雀', 'priority': 2, 'usage_tips': '【外观描述】只能描述外观/气质，不能回答"你是谁"。例如：红发（外观）、高冷（气质）、胖（体型）'},
            {'code': 'industry_word', 'name': '领域 / 垂类词', 'description': '行业/技术/领域（如：数码、美食、旅游、母婴）', 'examples': '数码|美食|旅游|母婴|奶粉|美妆|穿搭', 'priority': 3, 'usage_tips': '行业/领域名称。例如：数码（科技）、美食（餐饮）、母婴（育儿）、奶粉（婴幼儿食品）'},
            {'code': 'region_word', 'name': '地域词', 'description': '地区名称（如：南漳、北京、上海）', 'examples': '南漳|北京|上海|纽约|江浙沪', 'priority': 4, 'usage_tips': '地名/区域名，突出地域特色。例如：南漳（县城）、北京（城市）、江浙沪（区域）'},
            {'code': 'attribute_word', 'name': '属性关键词', 'description': '品质/特点/属性（如：手工、野生、正宗、进口）', 'examples': '手工|野生|正宗|进口|有机|纯天然', 'priority': 5, 'usage_tips': '品质/工艺/属性描述。例如：手工（工艺）、野生（来源）、进口（渠道）、有机（品质）'},
            {'code': 'number_word', 'name': '数字 / 字母符号', 'description': '年份/数量/字母（如：20年、10年、90年、AI）', 'examples': '20年|10年|90年|20年老师傅|AI|XX', 'priority': 6, 'usage_tips': '数字+年/月/天等单位，或字母组合，强调资历或技术。例如：20年（从业年限）、AI（人工智能）'},
            {'code': 'action_word', 'name': '行动 / 价值词', 'description': '动作/行为/价值词（如：吃、玩、学、干货、避坑）', 'examples': '吃|玩|学|吃遍|玩转|干货|避坑|指南|严选', 'priority': 7, 'usage_tips': '动词/价值词。例如：吃（吃播）、学（教学）、干货（知识价值）、避坑（防骗）'},
        ]

        bio_elements = [
            {'code': 'identity_tag', 'name': '身份标签', 'description': '职业背景、学历、职称、专业身份、资历实力', 'examples': '10年大厂PM|XX创始人|XX专家|9年行业|自有门面|20年老师傅', 'priority': 1, 'usage_tips': '回答"你是谁"——职业、学历、职称、身份、资历、实力。例如：创始人（创业身份）、专家（专业身份）、老师（职业身份）、9年行业（行业经验）、自有门面（实体实力）、20年老师傅（资历）'},
            {'code': 'value_proposition', 'name': '价值主张', 'description': '我提供什么价值，粉丝能得到什么', 'examples': '每天一个职场技巧|分享平价护肤|教你拍照变好看|干货分享|避坑指南|快乐成长', 'priority': 2, 'usage_tips': '【粉丝利益】回答"粉丝关注你能得到什么"——干货/技巧/避坑/快乐/成长。例如：每天一个职场技巧（职场成长）、分享平价护肤（省钱技巧）、教你拍照变好看（技能提升）、干货分享（知识价值）'},
            {'code': 'differentiation', 'name': '差异化标签', 'description': '为什么关注你，你和别人不一样在哪', 'examples': '只讲真话|不割韭菜|0基础也能学|话狠人老实人', 'priority': 3, 'usage_tips': '回答"为什么选你"——与竞品差异点。例如：话狠（实在不套路）、老实人（真诚）、不割韭菜（诚信）、0基础也能学（易上手）'},
            {'code': 'cta', 'name': '行动号召', 'description': '让粉丝做什么、关注后做什么', 'examples': '关注送XX|扫码领取|私信咨询|到店试吃|关注我先送一罐', 'priority': 4, 'usage_tips': '回答"让你做什么"——CTA指令。例如：关注我、+V、扫码、私信、到店'},
            {'code': 'price_info', 'name': '价格信息', 'description': '具体的价格/报价', 'examples': '2.5元/斤|99元/盒', 'priority': 5, 'usage_tips': '具体数字+价格单位。例如：XX元/斤、XX元/盒'},
            {'code': 'contact', 'name': '联系方式', 'description': '联系方式', 'examples': '微信号|电话|地址', 'priority': 6, 'usage_tips': '可直接联系的方式。例如：微信号、电话、地址'},
            {'code': 'content_element', 'name': '内容要素', 'description': '其他内容要素（如品牌slogan、创始人故事等）', 'examples': '奶粉我是认真的|品牌故事', 'priority': 7, 'usage_tips': '【兜底类型】只有当内容无法归入以上6种类型时才使用。例如：品牌slogan（如"奶粉我是认真的"）、品牌故事等'},
        ]

        created_count = 0

        for item in nickname_elements:
            exists = FormulaElementType.query.filter_by(
                sub_category='nickname_analysis',
                code=item['code']
            ).first()
            if not exists:
                element = FormulaElementType(
                    sub_category='nickname_analysis',
                    **item,
                    is_active=True
                )
                db.session.add(element)
                created_count += 1

        for item in bio_elements:
            exists = FormulaElementType.query.filter_by(
                sub_category='bio_analysis',
                code=item['code']
            ).first()
            if not exists:
                element = FormulaElementType(
                    sub_category='bio_analysis',
                    **item,
                    is_active=True
                )
                db.session.add(element)
                created_count += 1

        db.session.commit()

        _invalidate_formula_elements_cache()

        return jsonify({
            'code': 0,
            'message': f'初始化成功，共创建 {created_count} 个要素'
        })
    except Exception as e:
        db.session.rollback()
        logging.getLogger(__name__).error(f"初始化公式要素失败: {e}\n{traceback.format_exc()}")
        return jsonify({'code': 500, 'message': f'初始化失败: {str(e)}'}), 500


@formula_elements_bp.route('/formula-elements/export', methods=['GET'])
def export_formula_elements():
    """导出公式要素（JSON格式）"""
    from models.models import FormulaElementType

    sub_category = request.args.get('sub_category')

    query = FormulaElementType.query
    if sub_category:
        query = query.filter_by(sub_category=sub_category)

    elements = query.order_by(
        FormulaElementType.sub_category,
        FormulaElementType.priority
    ).all()

    export_data = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'elements': [{
            'sub_category': e.sub_category,
            'name': e.name,
            'code': e.code,
            'description': e.description,
            'examples': e.examples,
            'priority': e.priority,
            'is_active': e.is_active,
            'usage_tips': e.usage_tips,
        } for e in elements]
    }

    return jsonify({
        'code': 0,
        'data': export_data
    })


@formula_elements_bp.route('/formula-elements/import', methods=['POST'])
def import_formula_elements():
    """导入公式要素（JSON格式）"""
    from models.models import FormulaElementType, db

    data = request.get_json()

    if not data or 'elements' not in data:
        return jsonify({'code': 400, 'message': '无效的导入数据'}), 400

    imported_count = 0
    skipped_count = 0

    for item in data['elements']:
        exists = FormulaElementType.query.filter_by(
            sub_category=item.get('sub_category'),
            code=item.get('code')
        ).first()

        if exists:
            exists.name = item.get('name', exists.name)
            exists.description = item.get('description', exists.description)
            exists.examples = item.get('examples', exists.examples)
            exists.priority = item.get('priority', exists.priority)
            exists.is_active = item.get('is_active', exists.is_active)
            exists.usage_tips = item.get('usage_tips', exists.usage_tips)
            skipped_count += 1
        else:
            element = FormulaElementType(
                sub_category=item.get('sub_category'),
                name=item.get('name'),
                code=item.get('code'),
                description=item.get('description', ''),
                examples=item.get('examples', ''),
                priority=item.get('priority', 0),
                is_active=item.get('is_active', True),
                usage_tips=item.get('usage_tips', '')
            )
            db.session.add(element)
            imported_count += 1

    db.session.commit()

    _invalidate_formula_elements_cache()

    return jsonify({
        'code': 0,
        'message': f'导入成功：新增 {imported_count} 个，更新 {skipped_count} 个'
    })


@formula_elements_bp.route('/formula-elements/suggestions', methods=['GET'])
def get_formula_element_suggestions():
    """获取待审核的要素建议"""
    from models.models import FormulaElementSuggestion

    status = request.args.get('status', 'pending')

    query = FormulaElementSuggestion.query
    if status:
        query = query.filter_by(status=status)

    suggestions = query.order_by(
        FormulaElementSuggestion.created_at.desc()
    ).all()

    return jsonify({
        'code': 0,
        'data': [{
            'id': s.id,
            'sub_category': s.sub_category,
            'name': s.name,
            'code': s.code,
            'description': s.description,
            'example': s.example,
            'source_nickname': s.source_nickname,
            'source_formula': s.source_formula,
            'status': s.status,
            'created_at': s.created_at.isoformat() if s.created_at else None,
        } for s in suggestions]
    })


@formula_elements_bp.route('/formula-elements/suggestions/<int:suggestion_id>/approve', methods=['POST'])
def approve_formula_element_suggestion(suggestion_id):
    """审核通过要素建议，添加到要素库"""
    from models.models import FormulaElementSuggestion, FormulaElementType, db

    suggestion = FormulaElementSuggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({'code': 404, 'message': '建议不存在'}), 404

    if suggestion.status != 'pending':
        return jsonify({'code': 400, 'message': '该建议已处理'}), 400

    existing = FormulaElementType.query.filter_by(
        sub_category=suggestion.sub_category,
        code=suggestion.code
    ).first()

    if existing:
        existing.name = suggestion.name
        existing.description = suggestion.description
        existing.examples = suggestion.example
        message = '要素已更新'
    else:
        element = FormulaElementType(
            sub_category=suggestion.sub_category,
            name=suggestion.name,
            code=suggestion.code,
            description=suggestion.description,
            examples=suggestion.example,
            priority=99,
            is_active=True
        )
        db.session.add(element)
        message = '要素已添加'

    suggestion.status = 'approved'
    suggestion.reviewed_at = datetime.utcnow()
    suggestion.reviewer_id = None

    note = request.json.get('note', '') if request.json else ''
    suggestion.review_note = note

    db.session.commit()

    _invalidate_formula_elements_cache(suggestion.sub_category)

    return jsonify({
        'code': 0,
        'message': message
    })


@formula_elements_bp.route('/formula-elements/suggestions/<int:suggestion_id>/reject', methods=['POST'])
def reject_formula_element_suggestion(suggestion_id):
    """拒绝要素建议"""
    from models.models import FormulaElementSuggestion, db

    suggestion = FormulaElementSuggestion.query.get(suggestion_id)
    if not suggestion:
        return jsonify({'code': 404, 'message': '建议不存在'}), 404

    if suggestion.status != 'pending':
        return jsonify({'code': 400, 'message': '该建议已处理'}), 400

    suggestion.status = 'rejected'
    suggestion.reviewed_at = datetime.utcnow()
    suggestion.reviewer_id = None

    note = request.json.get('note', '') if request.json else ''
    suggestion.review_note = note

    db.session.commit()

    return jsonify({
        'code': 0,
        'message': '已拒绝'
    })

