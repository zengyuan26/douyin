"""
客户管理 API 路由

提供客户的 CRUD 操作，以及客户与画像、生成记录的关联管理。
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.models import db, User
from models.customer_models import Customer
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# 统一使用 /api/admin/customers 前缀
customer_bp = Blueprint('customer_api', __name__, url_prefix='/api/admin/customers')


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('super_admin', 'admin'):
            return jsonify({'code': 403, 'message': '需要管理员权限', 'success': False}), 403
        return f(*args, **kwargs)
    return decorated_function


def get_customers_query():
    """获取客户查询基础 query，支持权限过滤"""
    query = Customer.query

    # 管理员只能查看自己创建的客户，超级管理员可以查看所有客户
    if current_user.role == 'admin':
        query = query.filter(Customer.admin_id == current_user.id)

    return query


# =============================================================================
# 客户管理 API
# =============================================================================

@customer_bp.route('', methods=['GET'])
@admin_required
def list_customers():
    """
    获取客户列表

    Query Parameters:
        - page: 页码 (default: 1)
        - per_page: 每页数量 (default: 20)
        - search: 搜索关键词
        - industry: 行业筛选
        - status: 状态筛选 (active/inactive)
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    industry = request.args.get('industry', '').strip()
    status = request.args.get('status', '').strip()

    query = get_customers_query()

    # 搜索过滤
    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Customer.customer_name.ilike(search_pattern),
                Customer.brand_name.ilike(search_pattern),
                Customer.contact_person.ilike(search_pattern),
                Customer.contact_phone.ilike(search_pattern),
                Customer.business_description.ilike(search_pattern)
            )
        )

    # 行业筛选
    if industry:
        query = query.filter(Customer.industry == industry)

    # 状态筛选
    if status:
        query = query.filter(Customer.status == status)

    # 按更新时间倒序
    query = query.order_by(Customer.updated_at.desc())

    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    customers = pagination.items

    return jsonify({
        'code': 200,
        'message': 'success',
        'success': True,
        'data': {
            'items': [c.to_dict() for c in customers],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@customer_bp.route('', methods=['POST'])
@admin_required
def create_customer():
    """
    创建客户

    Request Body (JSON):
        - customer_name: 客户名称 (必填)
        - industry: 行业
        - business_description: 业务描述
        - ... 其他字段
    """
    data = request.get_json()

    if not data:
        return jsonify({'code': 400, 'message': '请求数据不能为空', 'success': False}), 400

    customer_name = data.get('customer_name', '').strip()
    if not customer_name:
        return jsonify({'code': 400, 'message': '客户名称不能为空', 'success': False}), 400

    # 生成客户编码
    import uuid
    customer_code = f"C{uuid.uuid4().hex[:8].upper()}"

    # 创建客户
    customer = Customer(
        customer_name=customer_name,
        customer_code=customer_code,
        admin_id=current_user.id,
        client_type=data.get('client_type'),
        client_type_detail=data.get('client_type_detail'),
        industry=data.get('industry'),
        business_description=data.get('business_description'),
        geographic_scope=data.get('geographic_scope'),
        scope_detail=data.get('scope_detail'),
        target_cities=data.get('target_cities'),
        local_focus=data.get('local_focus', False),
        brand_name=data.get('brand_name'),
        personal_brand=data.get('personal_brand', False),
        company_brand=data.get('company_brand', False),
        brand_priority=data.get('brand_priority'),
        primary_language=data.get('primary_language'),
        dialect_ratio=data.get('dialect_ratio'),
        dialect_detail=data.get('dialect_detail'),
        product_type=data.get('product_type'),
        price_range=data.get('price_range'),
        seasonal=data.get('seasonal', False),
        delivery_mode=data.get('delivery_mode'),
        delivery_frequency=data.get('delivery_frequency'),
        unit_price=data.get('unit_price'),
        primary_goal=data.get('primary_goal'),
        secondary_goals=data.get('secondary_goals'),
        timeline=data.get('timeline'),
        budget_level=data.get('budget_level'),
        has_team=data.get('has_team'),
        team_size=data.get('team_size'),
        content_frequency=data.get('content_frequency'),
        content_style=data.get('content_style'),
        reference_accounts=data.get('reference_accounts'),
        contact_person=data.get('contact_person'),
        contact_phone=data.get('contact_phone'),
        contact_email=data.get('contact_email'),
        remarks=data.get('remarks'),
        status=data.get('status', 'active')
    )

    db.session.add(customer)
    db.session.commit()

    logger.info(f"[Customer] 创建客户成功: id={customer.id}, name={customer.customer_name}")

    return jsonify({
        'code': 200,
        'message': '客户创建成功',
        'success': True,
        'data': customer.to_dict()
    })


@customer_bp.route('/<int:customer_id>', methods=['GET'])
@admin_required
def get_customer(customer_id):
    """获取客户详情"""
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在', 'success': False}), 404

    # 权限检查
    if current_user.role == 'admin' and customer.admin_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权访问此客户', 'success': False}), 403

    return jsonify({
        'code': 200,
        'message': 'success',
        'success': True,
        'data': customer.to_dict()
    })


@customer_bp.route('/<int:customer_id>', methods=['PUT'])
@admin_required
def update_customer(customer_id):
    """
    更新客户信息

    Request Body (JSON): 任意客户字段
    """
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在', 'success': False}), 404

    # 权限检查
    if current_user.role == 'admin' and customer.admin_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权修改此客户', 'success': False}), 403

    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据不能为空', 'success': False}), 400

    # 可更新的字段
    updatable_fields = [
        'customer_name', 'industry', 'business_description', 'client_type',
        'client_type_detail', 'geographic_scope', 'scope_detail', 'target_cities',
        'local_focus', 'brand_name', 'personal_brand', 'company_brand',
        'brand_priority', 'primary_language', 'dialect_ratio', 'dialect_detail',
        'product_type', 'price_range', 'seasonal', 'delivery_mode',
        'delivery_frequency', 'unit_price', 'primary_goal', 'secondary_goals',
        'timeline', 'budget_level', 'has_team', 'team_size', 'content_frequency',
        'content_style', 'reference_accounts', 'contact_person', 'contact_phone',
        'contact_email', 'remarks', 'status'
    ]

    for field in updatable_fields:
        if field in data:
            setattr(customer, field, data[field])

    db.session.commit()

    logger.info(f"[Customer] 更新客户: id={customer.id}, name={customer.customer_name}")

    return jsonify({
        'code': 200,
        'message': '客户更新成功',
        'success': True,
        'data': customer.to_dict()
    })


@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
@admin_required
def delete_customer(customer_id):
    """删除客户"""
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在', 'success': False}), 404

    # 权限检查
    if current_user.role == 'admin' and customer.admin_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权删除此客户', 'success': False}), 403

    customer_name = customer.customer_name

    # 检查是否有关联的画像
    portrait_count = customer.portraits.count()
    if portrait_count > 0:
        return jsonify({
            'code': 400,
            'message': f'该客户下有 {portrait_count} 个画像，请先删除或转移画像',
            'success': False
        }), 400

    # 检查是否有生成记录
    generation_count = customer.generations.count()
    if generation_count > 0:
        return jsonify({
            'code': 400,
            'message': f'该客户下有 {generation_count} 条生成记录，请先处理',
            'success': False
        }), 400

    db.session.delete(customer)
    db.session.commit()

    logger.info(f"[Customer] 删除客户: id={customer_id}, name={customer_name}")

    return jsonify({
        'code': 200,
        'message': '客户删除成功',
        'success': True
    })


# =============================================================================
# 客户关联资源查询
# =============================================================================

@customer_bp.route('/<int:customer_id>/portraits', methods=['GET'])
@admin_required
def get_customer_portraits(customer_id):
    """
    获取客户下的所有画像

    Query Parameters:
        - page: 页码
        - per_page: 每页数量
    """
    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在', 'success': False}), 404

    # 权限检查
    if current_user.role == 'admin' and customer.admin_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权访问此客户', 'success': False}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    portraits_query = customer.portraits.order_by(db.desc('created_at'))
    pagination = portraits_query.paginate(page=page, per_page=per_page, error_out=False)

    portraits_data = []
    for portrait in pagination.items:
        portraits_data.append({
            'id': portrait.id,
            'portrait_name': portrait.portrait_name,
            'industry': portrait.industry,
            'target_customer': portrait.target_customer,
            'used_count': portrait.used_count,
            'is_default': portrait.is_default,
            'generation_status': portrait.generation_status,
            'has_keyword_library': portrait.has_keyword_library,
            'has_topic_library': portrait.has_topic_library,
            'has_operation_plan': portrait.has_operation_plan,
            'created_at': portrait.created_at.isoformat() if portrait.created_at else None,
            'updated_at': portrait.updated_at.isoformat() if portrait.updated_at else None,
        })

    return jsonify({
        'code': 200,
        'message': 'success',
        'success': True,
        'data': {
            'items': portraits_data,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@customer_bp.route('/<int:customer_id>/generations', methods=['GET'])
@admin_required
def get_customer_generations(customer_id):
    """
    获取客户下的所有生成记录

    Query Parameters:
        - page: 页码
        - per_page: 每页数量
        - content_type: 内容类型筛选
    """
    from models.public_models import PublicGeneration

    customer = Customer.query.get(customer_id)

    if not customer:
        return jsonify({'code': 404, 'message': '客户不存在', 'success': False}), 404

    # 权限检查
    if current_user.role == 'admin' and customer.admin_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权访问此客户', 'success': False}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    content_type = request.args.get('content_type', '').strip()

    generations_query = customer.generations.order_by(db.desc('created_at'))

    if content_type:
        generations_query = generations_query.filter(
            PublicGeneration.content_type == content_type
        )

    pagination = generations_query.paginate(page=page, per_page=per_page, error_out=False)

    generations_data = []
    for gen in pagination.items:
        generations_data.append({
            'id': gen.id,
            'industry': gen.industry,
            'target_customer': gen.target_customer,
            'content_type': gen.content_type,
            'geo_mode_used': gen.geo_mode_used,
            'quality_score': gen.quality_score,
            'temperature_score': gen.temperature_score,
            'used_tokens': gen.used_tokens,
            'created_at': gen.created_at.isoformat() if gen.created_at else None,
        })

    return jsonify({
        'code': 200,
        'message': 'success',
        'success': True,
        'data': {
            'items': generations_data,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


# =============================================================================
# 行业选项
# =============================================================================

@customer_bp.route('/industries', methods=['GET'])
@admin_required
def get_industry_options():
    """获取所有可用的行业列表"""
    from models.models import Industry

    industries = Industry.query.filter_by(is_active=True).order_by(Industry.sort_order).all()

    return jsonify({
        'code': 200,
        'message': 'success',
        'success': True,
        'data': [
            {'value': i.slug or i.name, 'label': i.name}
            for i in industries
        ]
    })
