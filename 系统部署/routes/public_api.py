"""
公开内容生成平台 - API路由

蓝图前缀：/public
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_login import current_user
from models.public_models import PublicUser, PublicGeneration, PublicPricingPlan
from models.models import db, AnalysisDimension
from services.public_auth import auth_service
from services.public_content_generator import content_generator
from services.public_template_matcher import template_matcher
from services.public_quota_manager import quota_manager
from services.rate_limiter import (
    rate_limiter, get_client_ip, rate_limit_response,
    check_ip_register, check_ip_login, check_email_verify,
    check_user_generate, check_general
)

public_bp = Blueprint('public', __name__, url_prefix='/public')


def get_current_public_user():
    """统一获取当前登录的 PublicUser，支持两种 session 路径"""
    # 方式1：从 session['public_user_id'] 获取（PublicUser 直接登录）
    user_id = session.get('public_user_id')
    if user_id:
        user = PublicUser.query.get(user_id)
        if user:
            return user
    # 方式2：从 Flask-Login session['_user_id'] 获取（public_user 角色的 User）
    if session.get('_user_id') and current_user.is_authenticated and current_user.role == 'public_user':
        return PublicUser.query.filter_by(email=current_user.email).first()
    return None


# =============================================================================
# 页面路由
# =============================================================================

@public_bp.route('/')
def index():
    """首页/主页面"""
    return render_template('public/index.html')


@public_bp.route('/verify')
def verify_page():
    """邮箱验证页面"""
    return render_template('public/verify.html')


@public_bp.route('/pricing')
def pricing():
    """定价页面"""
    return render_template('public/pricing.html')


@public_bp.route('/register')
def register_page():
    """页脚、定价页等使用的 /public/register，统一到现有注册页"""
    return redirect(url_for('auth.public_register'))


# =============================================================================
# 认证相关 API
# =============================================================================

@public_bp.route('/api/register', methods=['POST'])
def api_register():
    """用户注册"""
    # 获取客户端 IP
    client_ip = get_client_ip(request)

    # 检查 IP 注册频率限制
    is_allowed, rate_info = check_ip_register(client_ip)
    if not is_allowed:
        return rate_limit_response(rate_info, '注册请求过于频繁，请稍后重试')

    # 获取请求数据
    data = request.get_json() or {}
    email = data.get('email', '').strip()

    # 检查邮箱注册频率限制
    if email:
        is_allowed, rate_info = rate_limiter.check(
            'email_register', email,
            3, 86400  # 每天最多注册3个账号
        )
        if not is_allowed:
            return rate_limit_response(rate_info, '该邮箱注册过于频繁，请更换邮箱或明天再试')

    password = data.get('password', '')
    nickname = data.get('nickname', '').strip()

    if not email or not password:
        return jsonify({'success': False, 'message': '请填写邮箱和密码'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': '密码至少6位'}), 400

    success, message, user = auth_service.register(email, password, nickname)

    if success:
        session['public_user_id'] = user.id
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'user_id': user.id,
                'email': user.email,
                'is_verified': user.is_verified,
            }
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


@public_bp.route('/api/login', methods=['POST'])
def api_login():
    """用户登录"""
    # 获取客户端 IP
    client_ip = get_client_ip(request)

    # 检查 IP 登录频率限制
    is_allowed, rate_info = check_ip_login(client_ip)
    if not is_allowed:
        return rate_limit_response(rate_info, '登录尝试过于频繁，请稍后重试')

    data = request.get_json() or {}

    email = data.get('email', '').strip()
    password = data.get('password', '')

    success, message, user = auth_service.login(email, password)

    if success:
        session['public_user_id'] = user.id
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'user_id': user.id,
                'email': user.email,
                'is_premium': user.is_premium,
                'is_verified': user.is_verified,
            }
        })
    else:
        return jsonify({'success': False, 'message': message}), 401


@public_bp.route('/api/logout', methods=['POST'])
def api_logout():
    """用户登出"""
    session.pop('public_user_id', None)
    return jsonify({'success': True, 'message': '已退出登录'})


@public_bp.route('/api/verify-email', methods=['POST'])
def api_verify_email():
    """验证邮箱"""
    # 获取客户端 IP
    client_ip = get_client_ip(request)

    # 检查 IP 频率限制
    is_allowed, rate_info = check_email_verify(client_ip)
    if not is_allowed:
        return rate_limit_response(rate_info, '验证请求过于频繁，请稍后重试')

    data = request.get_json() or {}

    email = data.get('email', '').strip()
    code = data.get('code', '').strip()

    success, message = auth_service.verify_email(email, code)
    return jsonify({'success': success, 'message': message})


@public_bp.route('/api/resend-verification', methods=['POST'])
def api_resend_verification():
    """重新发送验证邮件"""
    # 获取客户端 IP
    client_ip = get_client_ip(request)

    # 检查 IP 频率限制
    is_allowed, rate_info = check_email_verify(client_ip)
    if not is_allowed:
        return rate_limit_response(rate_info, '请求过于频繁，请稍后重试')

    data = request.get_json() or {}

    email = data.get('email', '').strip()
    success, message = auth_service.resend_verification(email)

    return jsonify({'success': success, 'message': message})


# =============================================================================
# 数据获取 API
# =============================================================================

@public_bp.route('/api/industries')
def api_get_industries():
    """获取行业列表"""
    industries = template_matcher.get_industries()
    return jsonify({'success': True, 'data': industries})


@public_bp.route('/api/customers/<industry>')
def api_get_customers(industry):
    """获取目标客户列表"""
    customers = template_matcher.get_target_customers(industry)
    return jsonify({'success': True, 'data': customers})


@public_bp.route('/api/customers/<industry>/batches')
def api_get_customers_by_batch(industry):
    """获取按批次分组的目标客户"""
    result = template_matcher.get_target_customers_by_batch(industry)
    return jsonify({'success': True, 'data': result})


@public_bp.route('/api/customers/match', methods=['POST'])
def api_match_customers():
    """根据业务信息匹配合适的目标客户批次"""
    params = request.get_json() or {}
    industry = params.get('industry', '')
    business_range = params.get('business_range', '')
    business_type = params.get('business_type', '')

    if not industry:
        return jsonify({'success': False, 'message': '请选择行业'}), 400

    result = template_matcher.match_customers_for_business(
        industry, business_range, business_type
    )
    return jsonify({'success': True, 'data': result})


@public_bp.route('/api/targets/identify', methods=['POST'])
def api_identify_targets():
    """阶段1：快速识别目标客户身份（可选登录，匿名用户也可使用）"""

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 调用身份识别
    result = content_generator.identify_customer_identities(params)

    return jsonify(result)


# ── 已废弃：Stage 0 问题渠道识别已合并到 mine_problems 内部 ──
# @public_bp.route('/api/targets/problem-channels', methods=['POST'])
# def api_identify_problem_channels():
#     """
#     Stage 0：问题渠道识别
#
#     在问题类型之前运行，挖掘「用户带着什么问题来搜索」。
#     输出用户真实搜索意图/问题句式。
#
#     请求格式：
#     {
#         "business_description": "...",
#         "business_range": "local/cross_region",
#         "business_type": "...",
#     }
#     """
#     from services.public_content_generator import mine_problem_channels
#
#     params = request.get_json() or {}
#
#     if not params.get('business_description'):
#         return jsonify({'success': False, 'message': '请描述您的业务'}), 400
#
#     if not params.get('business_range'):
#         return jsonify({'success': False, 'message': '请选择经营范围'}), 400
#
#     if not params.get('business_type'):
#         return jsonify({'success': False, 'message': '请选择经营类型'}), 400
#
#     result = mine_problem_channels(params)
#     return jsonify(result)


@public_bp.route('/api/targets/problems', methods=['POST'])
def api_identify_problems():
    """
    阶段1：挖掘使用方问题和付费方顾虑

    返回问题列表（使用方问题 + 付费方顾虑）。
    用户点击某个问题后，再调用 /api/targets/generate-portraits 生成画像。

    请求格式：
    {
        "business_description": "...",
        "business_range": "local/cross_region",
        "business_type": "local_service/product/personal/enterprise",
        "customer_who": "...",  // 可选
        "customer_why": "...",   // 可选
        "customer_problem": "...", // 可选
        "customer_story": "...", // 可选
    }
    """
    from services.public_content_generator import mine_problems as new_mine_problems

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 获取用户是否付费
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user:
            is_premium = user.is_premium

    params['_is_premium'] = is_premium

    # 调用新的问题挖掘函数
    result = new_mine_problems(params)

    # 添加用户标识
    result['is_premium'] = is_premium

    return jsonify(result)


@public_bp.route('/api/targets/generate-batch', methods=['POST'])
def api_generate_persona_batch():
    """
    阶段2：基于指定问题生成人群画像批次

    请求格式：
    {
        "business_description": "...",
        "business_range": "...",
        "business_type": "...",
        "problem_id": "问题ID（来自阶段1的问题列表）",
        "problem_type": "user_pain | buyer_concern",  // 问题类型
        "customer_who": "...",  // 可选
        "customer_why": "...",  // 可选
        "customer_problem": "...", // 可选
        "customer_story": "...", // 可选
    }
    """
    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    if not params.get('problem_id'):
        return jsonify({'success': False, 'message': '请选择问题类型'}), 400

    result = content_generator.generate_persona_batch_by_problem(params)

    return jsonify(result)


@public_bp.route('/api/targets/generate-portraits', methods=['POST'])
def api_generate_portraits():
    """
    阶段2：基于指定问题生成人群画像

    请求格式：
    {
        "business_description": "...",
        "problem": {
            "id": "问题ID",
            "identity": "客户身份",
            "problem_type": "问题类型",
            "display_name": "展示名称",
            "description": "问题描述",
            "scenario": "场景"
        }
    }
    """
    from services.public_content_generator import generate_portraits as new_generate_portraits

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('problem'):
        return jsonify({'success': False, 'message': '请选择要生成画像的问题'}), 400

    # 获取用户是否付费
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user:
            is_premium = user.is_premium

    params['_is_premium'] = is_premium

    result = new_generate_portraits(params)
    result['is_premium'] = is_premium

    return jsonify(result)


@public_bp.route('/api/targets/generate-all-portraits', methods=['POST'])
def api_generate_all_portraits():
    """
    阶段2（付费专用）：并行生成所有问题的画像

    请求格式：
    {
        "business_description": "...",
        "problems": [
            {
                "id": "问题ID",
                "identity": "客户身份",
                "problem_type": "问题类型",
                "display_name": "展示名称",
                "description": "问题描述",
                "scenario": "场景"
            }
        ]
    }
    """
    from services.public_content_generator import generate_portraits_parallel

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('problems'):
        return jsonify({'success': False, 'message': '请选择要生成画像的问题'}), 400

    # 获取用户是否付费
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user:
            is_premium = user.is_premium

    # 只有付费用户才能使用并行生成
    if not is_premium:
        return jsonify({
            'success': False,
            'message': '此功能仅对付费用户开放，请升级到高级版'
        }), 403

    problems = params.get('problems', [])
    business_desc = params.get('business_description', '')

    # 并行生成
    results = generate_portraits_parallel(problems, business_desc, is_premium=True)

    return jsonify({
        'success': True,
        'is_premium': True,
        'results': results
    })


# =============================================================================
# 问题挖掘 + 画像生成 组合 API
# =============================================================================

@public_bp.route('/api/targets/mine-and-generate', methods=['POST'])
def api_mine_and_generate():
    """
    一次性完成问题挖掘 + 所有类型的画像生成

    请求格式：
    {
        "business_description": "...",
        "business_range": "local/cross_region",
        "business_type": "local_service/product/personal/enterprise",
        "customer_who": "...",  // 可选
        "customer_why": "...",   // 可选
        "customer_problem": "...", // 可选
        "customer_story": "...", // 可选
    }

    返回格式：
    {
        "success": true,
        "data": {
            "problem_types": [...],  // 问题类型列表
            "user_problems": [...],  // 使用方问题
            "buyer_concerns": [...], // 付费方顾虑
            "portraits_by_type": {   // 按问题类型分组的画像
                "肠道问题": [...],
                "喂养习惯": [...],
                ...
            }
        }
    }
    """
    import logging
    logger = logging.getLogger(__name__)

    params = request.get_json() or {}
    logger.info(f"[api_mine_problems] 接收参数: {params}")

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 检查用户是否付费，决定使用哪种模型
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user and user.is_paid_user():
            is_premium = True
    params['_is_premium'] = is_premium

    # 调用组合服务（带重试机制）
    from services.public_content_generator import mine_problems_and_generate_personas
    max_retries = 2
    for attempt in range(max_retries + 1):
        result = mine_problems_and_generate_personas(params)
        if result.get('success'):
            return jsonify(result)
        if attempt < max_retries:
            print(f"[api_mine_and_generate] 第 {attempt + 1} 次失败，重试中...")

    return jsonify(result)


@public_bp.route('/api/targets/generate', methods=['POST'])
def api_generate_targets():
    """生成目标用户画像（可选登录，登录后支持AI增强）"""
    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None

    # AI增强：仅登录用户可用（检查套餐配置）
    use_ai_enhancement = False
    if user:
        plan_config = quota_manager.get_plan_config(user.premium_plan or 'free')
        use_ai_enhancement = plan_config.get('ai_target_enhancement', False)

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 生成目标用户画像（user 为 None 时走匿名路径，仍可正常使用LLM直出）
    result = content_generator.generate_target_customers(
        user, params, use_ai_enhancement=use_ai_enhancement
    )

    # 付费套餐 AI 或 生成器内 LLM 直出画像，任一成立即标为 AI
    if result.get('success') and result.get('data'):
        result['data']['ai_enhanced'] = bool(
            use_ai_enhancement or result['data'].get('ai_enhanced')
        )

    return jsonify(result)


# =============================================================================
# 维度定义 API
# =============================================================================

@public_bp.route('/api/persona/dimensions')
def api_get_dimensions():
    """
    获取 persona 子分类下的维度定义列表。
    从数据库 AnalysisDimension 实时读取，
    examples 用管道符分隔解析为列表；
    local_service/product/personal 业务类型下会替换为 C 端生活化选项。
    """
    # 维度池映射（key → 本地生活化选项）
    local_overrides = content_generator._LOCAL_CONSUMER_DIM_OPTIONS

    dims_db = AnalysisDimension.query.filter_by(
        category='super_positioning',
        sub_category='persona',
        is_active=True
    ).order_by(AnalysisDimension.sort_order).all()

    dimensions = []
    for dim in dims_db:
        raw = (dim.examples or '').strip()
        # 默认用 DB 原始 examples
        examples = [e.strip() for e in raw.split('|') if e.strip()]

        # C 端业务：development_stage / revenue_scale / team_size / work_years
        # 用生活化语义覆盖（与 _build_llm_dimension_pool 保持一致）
        if dim.code in local_overrides:
            local_opts = local_overrides[dim.code]
            if isinstance(local_opts, list):
                examples = local_opts

        dimensions.append({
            'key': dim.code,
            'name': dim.name,
            'description': dim.description or dim.usage_tips or '',
            'weight': 0.85 if dim.code != 'job_role' else 1.0,
            'options': [
                {'key': 'default', 'name': '限定词', 'examples': examples},
            ],
        })

    # 若数据库为空，退回默认列表
    if not dimensions:
        dimensions = [
            {
                'key': 'development_stage', 'name': '发展阶段', 'description': '',
                'weight': 0.85,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['刚起步', '天使轮', 'A轮', '成熟期', '转型期']}],
            },
            {
                'key': 'revenue_scale', 'name': '营收规模', 'description': '',
                'weight': 0.8,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['500万以下', '3000万-2亿', '5亿以上']}],
            },
            {
                'key': 'team_size', 'name': '团队规模', 'description': '',
                'weight': 0.82,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['10人以下', '10-50人', '50-400人']}],
            },
            {
                'key': 'work_years', 'name': '工作年限', 'description': '',
                'weight': 0.75,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['3-5年', '5-10年', '10年以上']}],
            },
            {
                'key': 'industry_background', 'name': '行业背景', 'description': '',
                'weight': 0.9,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['传统制造', '互联网', '金融', '教育', '医疗健康', '零售消费', '企业服务', '本地生活']}],
            },
            {
                'key': 'region', 'name': '地域', 'description': '',
                'weight': 0.78,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['一线城市', '新一线', '三四线', '海外']}],
            },
            {
                'key': 'age_group', 'name': '年龄段', 'description': '',
                'weight': 0.7,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['25-35岁', '35-45岁', '45岁以上']}],
            },
            {
                'key': 'job_role', 'name': '职位角色', 'description': '',
                'weight': 1.0,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['创始人', 'CEO', 'VP', '总监', '经理']}],
            },
            {
                'key': 'pain_status', 'name': '痛点状态', 'description': '',
                'weight': 0.95,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['遇到瓶颈', '想要转型', '寻求突破']}],
            },
            {
                'key': 'goal', 'name': '目标诉求', 'description': '',
                'weight': 0.95,
                'options': [{'key': 'default', 'name': '限定词', 'examples': ['想要增长', '想要转型', '想要变现']}],
            },
        ]

    return jsonify({
        'success': True,
        'data': {
            'dimensions': dimensions,
            'total': len(dimensions)
        }
    })


@public_bp.route('/api/quota')
def api_get_quota():
    """获取用户配额信息"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    quota_info = quota_manager.get_user_quota_info(user)
    feature_access = quota_manager.get_feature_access(user)

    return jsonify({
        'success': True,
        'data': {
            'email': user.email,
            'quota': quota_info,
            'features': feature_access
        }
    })


# =============================================================================
# 内容生成 API
# =============================================================================

@public_bp.route('/api/generate', methods=['POST'])
def api_generate():
    """生成内容"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    # 检查用户生成频率限制
    is_allowed, rate_info = check_user_generate(user.id)
    if not is_allowed:
        return rate_limit_response(rate_info, '内容生成过于频繁，请稍后重试')

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 从业务描述中推断行业（兼容旧接口）
    if not params.get('industry'):
        industry = infer_industry_from_description(params.get('business_description', ''))
        params['industry'] = industry

    result = content_generator.generate(user, params)

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


def infer_industry_from_description(description: str) -> str:
    """
    从业务描述中推断行业

    Args:
        description: 业务描述文本

    Returns:
        推断的行业代码
    """
    # 关键词映射
    keyword_to_industry = {
        '桶装水': 'tongzhuangshui',
        '矿泉水': 'tongzhuangshui',
        '饮用水': 'tongzhuangshui',
        '纯净水': 'tongzhuangshui',
        '送水': 'tongzhuangshui',
        '餐厅': 'meishi',
        '美食': 'meishi',
        '餐饮': 'meishi',
        '小吃': 'meishi',
        '外卖': 'meishi',
        '咖啡': 'meishi',
        '服装': 'fuzhuang',
        '衣服': 'fuzhuang',
        '鞋子': 'fuzhuang',
        '包包': 'fuzhuang',
        '美容': 'meirong',
        '护肤': 'meirong',
        '化妆': 'meirong',
        '美妆': 'meirong',
        '家电': 'jiadian',
        '电器': 'jiadian',
        '手机': 'jiadian',
        '电脑': 'jiadian',
        '家具': 'jiaju',
        '家居': 'jiaju',
        '装修': 'jiaju',
        '培训': 'jiaoyu',
        '教育': 'jiaoyu',
        '课程': 'jiaoyu',
        '美发': 'liren',
        '美甲': 'liren',
    }

    description_lower = description.lower()

    for keyword, industry in keyword_to_industry.items():
        if keyword in description_lower:
            return industry

    # 默认返回桶装水（最常见的场景）
    return 'tongzhuangshui'


@public_bp.route('/api/history')
def api_get_history():
    """获取生成历史"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    history = content_generator.get_generation_history(user, page, per_page)
    return jsonify({'success': True, 'data': history})


@public_bp.route('/api/history/<int:generation_id>')
def api_get_generation_detail(generation_id):
    """获取生成详情"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    generation = PublicGeneration.query.filter_by(
        id=generation_id, user_id=user.id
    ).first()

    if not generation:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    return jsonify({
        'success': True,
        'data': {
            'id': generation.id,
            'industry': generation.industry,
            'target_customer': generation.target_customer,
            'titles': generation.titles,
            'tags': generation.tags,
            'content': generation.content,
            'created_at': generation.created_at.isoformat()
        }
    })


# =============================================================================
# 辅助函数
# =============================================================================

def get_current_user():
    """获取当前登录用户（兼容旧代码）"""
    return get_current_public_user()


def login_required(f):
    """登录装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_public_user():
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# 市场机会分析 API
# =============================================================================

@public_bp.route('/api/market-opportunity/generate', methods=['POST'])
def api_generate_market_opportunity():
    """
    生成市场机会分析

    基于用户画像数据，挖掘差异化蓝海市场机会

    请求格式：
    {
        "business_description": "...",    // 业务描述
        "business_range": "...",        // 经营范围
        "business_type": "...",        // 业务类型
        "portraits": [...]              // 用户画像列表
    }
    """
    from services.public_market_opportunity import get_public_market_opportunity_service

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请先填写业务描述'}), 400

    if not params.get('portraits') or len(params.get('portraits', [])) == 0:
        return jsonify({'success': False, 'message': '请先生成用户画像'}), 400

    # 构建业务信息
    business_info = {
        'business_description': params.get('business_description', ''),
        'business_range': params.get('business_range', ''),
        'business_type': params.get('business_type', ''),
    }

    # 获取画像数据
    portraits_data = params.get('portraits', [])

    # 调用服务生成市场机会
    try:
        service = get_public_market_opportunity_service()
        result = service.generate_opportunity(business_info, portraits_data)

        if result.get('success'):
            # 返回Markdown格式方便前端展示
            markdown = service.format_markdown(result)
            return jsonify({
                'success': True,
                'data': result.get('data', {}),
                'markdown': markdown
            })
        else:
            error_msg = result.get('error', '生成失败')
            # 如果有原始响应，也返回方便调试
            if result.get('raw_response'):
                return jsonify({
                    'success': False,
                    'message': f'{error_msg}，原始响应：{result.get("raw_response")[:200]}'
                }), 500
            return jsonify({
                'success': False,
                'message': error_msg
            }), 500
    except Exception as e:
        import traceback
        import sys
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[MarketOpportunity Error] {e}\n{tb_str}", file=sys.stderr)
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }), 500


@public_bp.route('/api/market-opportunity/dimensions', methods=['GET'])
def api_get_market_opportunity_dimensions():
    """获取市场机会分析维度配置"""
    from services.public_market_opportunity import get_public_market_opportunity_service

    service = get_public_market_opportunity_service()
    dimensions = service.get_differentiation_dimensions()

    return jsonify({
        'success': True,
        'data': dimensions
    })
