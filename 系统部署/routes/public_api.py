"""
公开内容生成平台 - API路由

蓝图前缀：/public
"""

import json
import datetime
import logging
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, current_app
from flask_login import current_user
from sqlalchemy import text
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

logger = logging.getLogger(__name__)

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


@public_bp.route('/galaxy')
def galaxy_page():
    """星系内容宇宙 - 可视化页面"""
    return render_template('public/galaxy.html')


@public_bp.route('/produce')
def produce_page():
    """生成内容页 - 网易云播放列表风格"""
    return render_template('public/produce.html')


@public_bp.route('/portraits')
def portraits_page():
    """客户画像管理页"""
    return render_template('public/portraits.html')


@public_bp.route('/portraits/create')
def portraits_create_page():
    """生成画像独立页面（无客户画像/为你推荐）"""
    return render_template('public/portraits_create.html')


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
    from services.public_content_generator import mine_problems
    import traceback as tb_module

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('business_range'):
        return jsonify({'success': False, 'message': '请选择经营范围'}), 400

    if not params.get('business_type'):
        return jsonify({'success': False, 'message': '请选择经营类型'}), 400

    # 获取用户是否付费（用 is_paid_user 含过期检查，不用 is_premium 列）
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user:
            logger.info("[identify_problems] user_id=%s is_premium_col=%s premium_plan=%s premium_expires=%s is_paid_user=%s",
                         user_id, user.is_premium, user.premium_plan, user.premium_expires, user.is_paid_user())
            is_premium = user.is_paid_user()

    params['_is_premium'] = is_premium

    # 调用问题挖掘函数（全量 try/except 确保返回友好 JSON 而非 500）
    try:
        result = mine_problems(params)
    except Exception as e:
        logger.error("[api_identify_problems] mine_problems 异常: %s\n%s", e, tb_module.format_exc())
        return jsonify({'success': False, 'message': f'服务异常: {str(e)}'}), 500

    # 确保返回的是标准 dict，且不含不可序列化字段
    if not isinstance(result, dict):
        logger.error("[api_identify_problems] mine_problems 返回类型异常: %s", type(result))
        return jsonify({'success': False, 'message': '服务返回格式异常，请稍后重试'}), 500

    # 添加用户标识并返回
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
            is_premium = user.is_paid_user()

    params['_is_premium'] = is_premium

    try:
        result = new_generate_portraits(params)
        if result is None:
            return jsonify({'success': False, 'message': '生成失败: 返回数据异常'}), 500
        result['is_premium'] = is_premium
        return jsonify(result)
    except Exception as e:
        import traceback
        logger.error("[api_generate_portraits] 异常: %s", str(e))
        logger.debug("[api_generate_portraits] 堆栈: %s", traceback.format_exc())
        return jsonify({'success': False, 'message': f'生成失败: {str(e)}'}), 500


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
            is_premium = user.is_paid_user()

    # 只有付费用户才能使用并行生成
    if not is_premium:
        return jsonify({
            'success': False,
            'message': '此功能仅对付费用户开放，请升级到高级版'
        }), 403

    problems = params.get('problems', [])
    business_desc = params.get('business_description', '')
    service_scenario = params.get('service_scenario', 'other')
    business_type = params.get('business_type', 'local_service')

    # 并行生成
    results = generate_portraits_parallel(problems, business_desc, is_premium=True,
                                          service_scenario=service_scenario, business_type=business_type)

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

    # 调用组合服务（带重试机制 + 全局异常捕获）
    from services.public_content_generator import mine_problems_and_generate_personas
    import traceback as tb_module
    try:
        max_retries = 2
        for attempt in range(max_retries + 1):
            result = mine_problems_and_generate_personas(params)
            if isinstance(result, dict) and result.get('success'):
                return jsonify(result)
            if attempt < max_retries:
                logger.info("[api_mine_and_generate] 第 %d 次失败，重试中...", attempt + 1)
        # 重试耗尽，返回最后一次结果（即使是失败）
        if not isinstance(result, dict):
            return jsonify({'success': False, 'message': '服务返回格式异常，请稍后重试'}), 500
        return jsonify(result)
    except Exception as e:
        logger.error("[api_mine_and_generate] mine_problems_and_generate_personas 异常: %s\n%s", e, tb_module.format_exc())
        return jsonify({'success': False, 'message': f'服务异常: {str(e)}'}), 500


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
    
    # 获取保存的画像数量
    from models.public_models import SavedPortrait
    saved_count = SavedPortrait.query.filter_by(user_id=user.id).count()

    return jsonify({
        'success': True,
        'data': {
            'email': user.email,
            'nickname': user.nickname or '',
            'avatar': user.avatar or '',
            'plan_type': user.premium_plan or 'free',
            'plan_name': quota_info.get('plan_name', '免费版'),
            'is_premium': user.is_premium,
            'can_save': feature_access.get('save_portraits', False),
            'max_saved': feature_access.get('max_saved_portraits', 0),
            'weekly_change_limit': feature_access.get('weekly_portrait_changes', 0),
            'weekly_changes_used': 0,  # TODO: 需要跟踪实际使用次数
            'saved_count': saved_count,
            'quota': quota_info,
            'features': feature_access
        }
    })


# =============================================================================
# 画像管理 API
# =============================================================================

@public_bp.route('/api/portraits/saved', methods=['GET'])
def api_get_saved_portraits():
    """获取已保存的画像列表"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    include_data = request.args.get('include_data', 'false').lower() == 'true'
    
    from models.public_models import SavedPortrait
    query = SavedPortrait.query.filter_by(user_id=user.id).order_by(SavedPortrait.created_at.desc())
    portraits = query.all()
    
    result = []
    for p in portraits:
        item = {
            'id': p.id,
            'portrait_name': p.portrait_name,
            'is_default': p.is_default,
            'used_count': p.used_count,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None
        }
        if include_data:
            item['portrait_data'] = p.portrait_data
            item['business_description'] = p.business_description
            item['industry'] = p.industry
            item['generation_status'] = p.generation_status or 'pending'
            item['keyword_library'] = p.keyword_library
            item['topic_library'] = p.topic_library
            item['keyword_updated_at'] = p.keyword_updated_at.isoformat() if p.keyword_updated_at else None
            item['topic_updated_at'] = p.topic_updated_at.isoformat() if p.topic_updated_at else None
        result.append(item)
    
    return jsonify({'success': True, 'data': result})


@public_bp.route('/api/portraits/save', methods=['POST'])
def api_save_portrait():
    """保存当前画像"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    params = request.get_json() or {}
    portrait_data = params.get('portrait_data')
    portrait_name = params.get('portrait_name', '未命名')
    business_description = params.get('business_description', '')
    industry = params.get('industry', '')
    target_customer = params.get('target_customer', '')
    set_as_default = params.get('set_as_default', False)
    
    if not portrait_data:
        return jsonify({'success': False, 'message': '画像数据不能为空'}), 400
    
    from models.public_models import SavedPortrait
    
    # 检查保存数量限制
    current_count = SavedPortrait.query.filter_by(user_id=user.id).count()
    quota_info = quota_manager.get_user_quota_info(user)
    max_saved = quota_info.get('max_saved_portraits', 0)
    
    if max_saved > 0 and current_count >= max_saved:
        # 先删旧数据再插新数据（替换模式）
        SavedPortrait.query.filter_by(user_id=user.id).delete()
        db.session.commit()

    # 如果设为默认，先取消其他默认（替换模式下无其他数据，无需处理）
    if set_as_default:
        pass

    # 生成画像名称
    if not portrait_name:
        portrait_name = f"画像_{datetime.now().strftime('%m%d_%H%M')}"

    # 插入新记录
    new_portrait = SavedPortrait(
        user_id=user.id,
        portrait_data=portrait_data,
        portrait_name=portrait_name,
        business_description=business_description,
        industry=industry,
        target_customer=target_customer,
        is_default=set_as_default
    )
    db.session.add(new_portrait)
    db.session.commit()

    # 保存成功后立即获取 ID
    portrait_id = new_portrait.id

    # 免费用户：不需要生成词库，直接标记完成
    if not user.is_paid_user():
        db.session.execute(
            text("UPDATE saved_portraits SET generation_status = 'completed' WHERE id = :id"),
            {'id': portrait_id}
        )
        db.session.commit()
        return jsonify({
            'success': True,
            'data': {
                'id': portrait_id,
                'portrait_name': portrait_name,
                'is_default': set_as_default
            },
            'auto_generated': None
        })

    # 付费用户：更新状态为生成中，启动后台线程生成词库
    db.session.execute(
        text("UPDATE saved_portraits SET generation_status = 'generating' WHERE id = :id"),
        {'id': portrait_id}
    )
    db.session.commit()

    # 启动后台线程生成词库（通过 Semaphore 控制 LLM 并发数）
    import threading
    plan_type = user.premium_plan or 'basic'
    try:
        from services.portrait_library_task_service import generate_with_semaphore
        thread = threading.Thread(
            target=generate_with_semaphore,
            args=(portrait_id, user.id, plan_type),
            daemon=True
        )
        thread.start()
        logger.info("[api_save_portrait] 已提交词库生成任务 portrait_id=%s plan_type=%s", portrait_id, plan_type)
    except Exception as e:
        logger.error("[api_save_portrait] 启动词库生成任务失败: %s", e)
        # 任务启动失败不影响保存成功返回

    # 先立即返回成功，不阻塞响应
    return jsonify({
        'success': True,
        'data': {
            'id': portrait_id,
            'portrait_name': portrait_name,
            'is_default': set_as_default
        },
        'auto_generated': None
    })


@public_bp.route('/api/portraits/<int:portrait_id>', methods=['DELETE'])
def api_delete_portrait(portrait_id):
    """删除画像"""
    logger.info("[DELETE] 请求删除画像 ID: %s", portrait_id)
    user = get_current_public_user()
    if not user:
        logger.debug("[DELETE] 用户未登录")
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import SavedPortrait
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()

    if not portrait:
        logger.debug("[DELETE] 画像不存在 ID=%s, user_id=%s", portrait_id, user.id)
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    db.session.delete(portrait)
    db.session.commit()
    logger.info("[DELETE] 画像已删除 ID: %s", portrait_id)

    return jsonify({'success': True, 'message': '已删除'})


@public_bp.route('/api/portraits/<int:portrait_id>/set-default', methods=['POST'])
def api_set_default_portrait(portrait_id):
    """设为默认画像"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    from models.public_models import SavedPortrait
    
    # 取消其他默认
    SavedPortrait.query.filter_by(user_id=user.id, is_default=True).update({'is_default': False})
    
    # 设置新的默认
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    
    portrait.is_default = True
    db.session.commit()
    
    return jsonify({'success': True})


@public_bp.route('/api/portraits/default', methods=['GET'])
def api_get_default_portrait():
    """获取默认画像"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    from models.public_models import SavedPortrait
    portrait = SavedPortrait.query.filter_by(user_id=user.id, is_default=True).first()
    
    if not portrait:
        return jsonify({'success': False, 'message': '没有默认画像'}), 404
    
    return jsonify({
        'success': True,
        'data': {
            'id': portrait.id,
            'portrait_name': portrait.portrait_name,
            'portrait_data': portrait.portrait_data,
            'business_description': portrait.business_description,
            'industry': portrait.industry,
            'used_count': portrait.used_count
        }
    })


@public_bp.route('/api/portraits/stats', methods=['GET'])
def api_get_portrait_stats():
    """获取画像统计"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    from models.public_models import SavedPortrait
    total = SavedPortrait.query.filter_by(user_id=user.id).count()
    default_count = SavedPortrait.query.filter_by(user_id=user.id, is_default=True).count()
    
    # 使用次数统计
    from sqlalchemy import func
    total_uses = db.session.query(func.sum(SavedPortrait.used_count)).filter_by(user_id=user.id).scalar() or 0
    
    return jsonify({
        'success': True,
        'data': {
            'total_portraits': total,
            'default_portraits': default_count,
            'total_uses': total_uses
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
        logger.exception("[MarketOpportunity Error] %s", e)
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


# =============================================================================
# 选题生成 API
# =============================================================================

@public_bp.route('/api/topics/generate', methods=['POST'])
def api_generate_topics():
    """
    基于用户画像和问题关键词生成选题

    请求格式：
    {
        "business_description": "...",
        "business_range": "local/cross_region",
        "business_type": "local_service/product/personal/enterprise",
        "portraits": [...],  // 用户画像列表
        "problem_keywords": [...]  // 问题关键词列表
    }

    返回格式：
    {
        "success": true,
        "topics": [
            {"id": "1", "title": "选题标题", "type": "问题诊断", "target": "目标人群", "reason": "推荐理由"},
            ...
        ]
    }
    """
    from services.topic_generator import TopicGenerator

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    if not params.get('portraits') or len(params.get('portraits', [])) == 0:
        return jsonify({'success': False, 'message': '请先生成用户画像'}), 400

    # 获取用户是否付费
    user_id = session.get('public_user_id')
    is_premium = False
    if user_id:
        user = PublicUser.query.get(user_id)
        if user and user.is_paid_user():
            is_premium = True

    try:
        generator = TopicGenerator()
        result = generator.generate_topics(
            business_description=params.get('business_description', ''),
            business_range=params.get('business_range', ''),
            business_type=params.get('business_type', ''),
            portraits=params.get('portraits', []),
            problem_keywords=params.get('problem_keywords', []),
            is_premium=is_premium
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'is_premium': is_premium,
                'topics': result.get('topics', [])
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', '选题生成失败')
            }), 500
    except Exception as e:
        logger.exception("[TopicGenerator Error] %s", e)
        return jsonify({
            'success': False,
            'message': f'选题生成失败: {str(e)}'
        }), 500


@public_bp.route('/api/topics/regenerate', methods=['POST'])
def api_regenerate_topics():
    """
    换一批选题（付费用户专用）

    请求格式：
    {
        "business_description": "...",
        "portraits": [...],
        "problem_keywords": [...]
    }
    """
    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None

    # 检查付费状态
    if not user or not user.is_paid_user():
        return jsonify({
            'success': False,
            'message': '此功能仅对付费用户开放'
        }), 403

    params = request.get_json() or {}

    try:
        from services.topic_generator import TopicGenerator
        generator = TopicGenerator()
        result = generator.generate_topics(
            business_description=params.get('business_description', ''),
            business_range=params.get('business_range', ''),
            business_type=params.get('business_type', ''),
            portraits=params.get('portraits', []),
            problem_keywords=params.get('problem_keywords', []),
            is_premium=True
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'topics': result.get('topics', [])
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', '选题生成失败')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'选题生成失败: {str(e)}'
        }), 500


# =============================================================================
# 内容生成 API（基于选题）
# =============================================================================

@public_bp.route('/api/content/generate', methods=['POST'])
def api_generate_content_from_topic():
    """
    基于选题生成图文内容

    请求格式：
    {
        "topic_id": "1",
        "topic_title": "选题标题",
        "topic_type": "问题诊断",
        "business_description": "...",
        "business_range": "local/cross_region",
        "business_type": "...",
        "portrait": {...}  // 选中的用户画像
    }
    """
    from services.content_generator import TopicContentGenerator
    from models.public_models import PublicGeneration

    params = request.get_json() or {}

    # 必填字段检查
    if not params.get('topic_title'):
        return jsonify({'success': False, 'message': '请选择选题'}), 400

    if not params.get('business_description'):
        return jsonify({'success': False, 'message': '请描述您的业务'}), 400

    # 获取用户
    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None
    is_premium = user and user.is_paid_user()

    # 检查配额
    can_generate, reason, quota_info = quota_manager.check_quota(user) if user else (True, 'anonymous', {})
    if not can_generate:
        return jsonify({
            'success': False,
            'message': quota_manager.get_user_quota_info(user).get('reason', '已达生成上限'),
            'quota_info': quota_info,
            'upgrade_url': '/pricing'
        }), 403

    try:
        generator = TopicContentGenerator()
        result = generator.generate_content(
            topic_id=params.get('topic_id', ''),
            topic_title=params.get('topic_title', ''),
            topic_type=params.get('topic_type', ''),
            business_description=params.get('business_description', ''),
            business_range=params.get('business_range', ''),
            business_type=params.get('business_type', ''),
            portrait=params.get('portrait', {}),
            is_premium=is_premium,
            premium_plan=user.premium_plan if user else 'free'
        )

        if result.get('success'):
            # 保存生成记录（所有用户都记录）
            if user:
                generation = PublicGeneration(
                    user_id=user.id,
                    industry=params.get('business_type', ''),
                    target_customer=params.get('portrait', {}).get('identity', ''),
                    content_type='graphic',
                    titles=result['content'].get('title', ''),
                    tags=','.join(result['content'].get('tags', [])),
                    content=result['content'].get('body', ''),
                    used_tokens=result.get('tokens_used', 0),
                    topic_id=params.get('topic_id', '') or None,
                    portrait_id=params.get('portrait_id'),
                    problem_id=params.get('problem_id'),
                )
                db.session.add(generation)
                # 扣减配额
                quota_manager.use_quota(user, result.get('tokens_used', 0))
                db.session.commit()

                # 回写 generation_count（选题被使用次数 +1）
                portrait_id = params.get('portrait_id')
                topic_id_str = params.get('topic_id', '')
                if portrait_id and topic_id_str:
                    try:
                        portrait = SavedPortrait.query.filter_by(
                            id=portrait_id, user_id=user.id
                        ).first()
                        if portrait and portrait.topic_library:
                            topics = portrait.topic_library.get('topics', [])
                            updated = False
                            for t in topics:
                                if t.get('id') == topic_id_str:
                                    t['generation_count'] = t.get('generation_count', 0) + 1
                                    updated = True
                                    break
                            if updated:
                                portrait.topic_library = portrait.topic_library
                                db.session.commit()
                    except Exception as e:
                        app.logger.warning('回写 generation_count 失败: %s', e)

            return jsonify({
                'success': True,
                'content': result.get('content', {})
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('error', '内容生成失败')
            }), 500
    except Exception as e:
        logger.exception("[ContentGenerator Error] %s", e)
        return jsonify({
            'success': False,
            'message': f'内容生成失败: {str(e)}'
        }), 500


# =============================================================================
# 内容类型推荐 API
# =============================================================================

@public_bp.route('/api/topics/recommend-type', methods=['POST'])
def api_recommend_content_type():
    """
    基于选题推荐内容类型（图文/长文/短视频）

    请求格式：
    {
        "topic": {
            "title": "选题标题",
            "type": "避坑指南"
        },
        "portrait": {
            "age_range": "25-35岁"
        },
        "business_info": {
            "is_hot_topic": false,
            "is_professional": true
        }
    }
    """
    from services.content_type_recommender import content_type_recommender

    params = request.get_json() or {}

    topic = params.get('topic', {})
    portrait = params.get('portrait', {})
    business_info = params.get('business_info', {})

    recommendation = content_type_recommender.recommend(topic, portrait, business_info)

    return jsonify({
        'success': True,
        'recommendation': recommendation
    })


@public_bp.route('/api/feedback/content-type', methods=['POST'])
def api_feedback_content_type():
    """
    用户对内容类型选择的反馈
    """
    params = request.get_json() or {}

    # TODO: 保存反馈到数据库用于优化推荐算法

    return jsonify({
        'success': True,
        'message': '感谢反馈'
    })


# =============================================================================
# 超级定位快照 API
# =============================================================================

@public_bp.route('/api/snapshots/current', methods=['GET'])
def api_get_current_snapshot():
    """
    获取当前用户的最新超级定位快照

    GET /public/api/snapshots/current
    返回: { success, snapshot }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    # 获取该用户最新的快照
    row = db.session.execute(
        db.text("""
            SELECT id, session_id, version, form_data, problems_data, portraits_data,
                   selected_problem_id, selected_portrait_index, created_at, updated_at
            FROM super_snapshots
            WHERE user_id = :user_id
            ORDER BY updated_at DESC
            LIMIT 1
        """),
        {'user_id': user.id}
    ).fetchone()

    if not row:
        return jsonify({'success': True, 'snapshot': None})

    # 解析 JSON 字段
    row_dict = dict(row._mapping)
    for field in ['form_data', 'problems_data', 'portraits_data']:
        if row_dict.get(field):
            try:
                row_dict[field] = json.loads(row_dict[field])
            except Exception:
                pass

    return jsonify({'success': True, 'snapshot': row_dict})


@public_bp.route('/api/snapshots/save', methods=['POST'])
def api_save_snapshot():
    """
    保存超级定位快照（每次问题挖掘+画像生成后调用）

    POST /public/api/snapshots/save
    Body: {
        session_id: str,
        form_data: object,    # 表单数据
        problems_data: array,  # 问题列表
        portraits_data: object,# 画像字典 {typeKey: [...]}
        selected_problem_id: int,
        selected_portrait_index: int
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    params = request.get_json() or {}
    session_id = params.get('session_id', 'default')
    form_data = params.get('form_data', {})
    problems_data = params.get('problems_data', [])
    portraits_data = params.get('portraits_data', {})
    selected_problem_id = params.get('selected_problem_id')
    selected_portrait_index = params.get('selected_portrait_index')

    # 检查是否已存在同 session 的快照，有则更新，无则插入
    existing = db.session.execute(
        db.text("SELECT id, version FROM super_snapshots WHERE user_id = :uid AND session_id = :sid"),
        {'uid': user.id, 'sid': session_id}
    ).fetchone()

    now = datetime.datetime.utcnow()

    if existing:
        # 更新
        db.session.execute(
            db.text("""
                UPDATE super_snapshots
                SET version = version + 1,
                    form_data = :form_data,
                    problems_data = :problems_data,
                    portraits_data = :portraits_data,
                    selected_problem_id = :selected_problem_id,
                    selected_portrait_index = :selected_portrait_index,
                    updated_at = :now
                WHERE id = :id
            """),
            {
                'id': existing.id,
                'form_data': json.dumps(form_data, ensure_ascii=False),
                'problems_data': json.dumps(problems_data, ensure_ascii=False),
                'portraits_data': json.dumps(portraits_data, ensure_ascii=False),
                'selected_problem_id': selected_problem_id,
                'selected_portrait_index': selected_portrait_index,
                'now': now
            }
        )
        snapshot_id = existing.id
        version = existing.version + 1
    else:
        # 新建
        result = db.session.execute(
            db.text("""
                INSERT INTO super_snapshots
                    (user_id, session_id, version, form_data, problems_data, portraits_data,
                     selected_problem_id, selected_portrait_index, created_at, updated_at)
                VALUES
                    (:uid, :sid, 1, :form_data, :problems_data, :portraits_data,
                     :selected_problem_id, :selected_portrait_index, :now, :now)
            """),
            {
                'uid': user.id,
                'sid': session_id,
                'form_data': json.dumps(form_data, ensure_ascii=False),
                'problems_data': json.dumps(problems_data, ensure_ascii=False),
                'portraits_data': json.dumps(portraits_data, ensure_ascii=False),
                'selected_problem_id': selected_problem_id,
                'selected_portrait_index': selected_portrait_index,
                'now': now
            }
        )
        snapshot_id = result.lastrowid
        version = 1

    db.session.commit()

    return jsonify({
        'success': True,
        'snapshot_id': snapshot_id,
        'version': version
    })


# =============================================================================
# 统一关键词库+选题库生成 API
# =============================================================================

@public_bp.route('/api/library/generate', methods=['POST'])
def generate_unified_library():
    """
    统一生成关键词库 + 选题库

    POST /public/api/library/generate
    Body: {
        business_desc: str,        # 核心业务描述
        service_scenario: str,     # 7大标准场景
        business_type: str,        # 经营类型（product/personal/local_service/enterprise）
        problem_list: Dict,        # {user_problem_types, buyer_concern_types}
        portraits: List,          # 5个精准画像
        scenario_base_personas: Dict,  # 三层主干人群
        force_refresh: bool,       # 是否强制刷新（跳过缓存）
    }
    """
    from services.unified_library_generator import unified_library_generator
    from services.rate_limiter import check_user_generate

    # 获取用户
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    # 检查生成频率限制
    is_allowed, rate_info = check_user_generate(user.id)
    if not is_allowed:
        return jsonify({
            'success': False,
            'error': 'rate_limit',
            'message': f'今日生成次数已用完（{rate_info.get("limit", 0)}次/天）',
            'quota_info': rate_info,
        }), 429

    # 获取参数
    data = request.get_json() or {}
    params = {
        'user_id': user.id,
        'business_desc': data.get('business_desc', ''),
        'service_scenario': data.get('service_scenario', ''),
        'business_type': data.get('business_type', 'local_service'),
        'problem_list': data.get('problem_list', {}),
        'portraits': data.get('portraits', []),
        'scenario_base_personas': data.get('scenario_base_personas', {}),
    }
    force_refresh = data.get('force_refresh', False)

    # 调用生成器
    result = unified_library_generator.generate(params, force_refresh)

    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 500


# =============================================================================
# 账号设置 API
# =============================================================================

@public_bp.route('/api/account/profile', methods=['GET'])
def api_get_profile():
    """获取当前用户资料"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    return jsonify({
        'success': True,
        'data': {
            'id': user.id,
            'email': user.email,
            'nickname': user.nickname or '',
            'avatar': user.avatar or '',
            'is_verified': user.is_verified,
            'is_premium': user.is_paid_user(),
            'premium_plan': user.premium_plan or 'free',
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    })


@public_bp.route('/api/account/profile', methods=['PUT'])
def api_update_profile():
    """更新用户资料"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    data = request.get_json() or {}

    # 更新昵称
    if 'nickname' in data:
        nickname = data.get('nickname', '').strip()
        if len(nickname) > 80:
            return jsonify({'success': False, 'message': '昵称最多80个字符'}), 400
        user.nickname = nickname

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '资料更新成功',
        'data': {
            'id': user.id,
            'email': user.email,
            'nickname': user.nickname or '',
            'avatar': user.avatar or ''
        }
    })


@public_bp.route('/api/account/password', methods=['PUT'])
def api_change_password():
    """修改密码"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not old_password:
        return jsonify({'success': False, 'message': '请输入原密码'}), 400

    if not new_password:
        return jsonify({'success': False, 'message': '请输入新密码'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '新密码至少6位'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': '两次输入的新密码不一致'}), 400

    success, message = auth_service.change_password(user, old_password, new_password)

    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@public_bp.route('/api/account/avatar', methods=['POST'])
def api_upload_avatar():
    """上传头像"""
    import base64
    import uuid
    import os

    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    # 检查是否有文件上传
    if 'avatar' not in request.files and 'avatar_base64' not in request.form:
        return jsonify({'success': False, 'message': '请选择头像图片'}), 400

    try:
        avatar_url = ''

        # 处理 base64 上传
        if 'avatar_base64' in request.form:
            base64_data = request.form.get('avatar_base64', '')
            if base64_data.startswith('data:image'):
                # 去掉 data:image/xxx;base64, 前缀
                base64_data = base64_data.split(',')[1]

            # 解码并保存
            image_data = base64.b64decode(base64_data)

            # 生成唯一文件名
            ext = 'png'
            if 'image/jpeg' in request.form.get('avatar_type', 'png'):
                ext = 'jpg'
            elif 'image/png' in request.form.get('avatar_type', 'png'):
                ext = 'png'
            elif 'image/gif' in request.form.get('avatar_type', 'png'):
                ext = 'gif'

            filename = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}.{ext}"

            # 保存到 static/uploads/avatars/
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'static', 'uploads', 'avatars'
            )
            os.makedirs(upload_dir, exist_ok=True)

            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(image_data)

            avatar_url = f'/static/uploads/avatars/{filename}'

        # 处理文件上传
        elif 'avatar' in request.files:
            file = request.files['avatar']
            if file.filename == '':
                return jsonify({'success': False, 'message': '请选择头像图片'}), 400

            # 检查文件类型
            allowed_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in allowed_exts:
                return jsonify({'success': False, 'message': '只支持 PNG、JPG、GIF、WebP 格式'}), 400

            # 生成唯一文件名
            filename = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}.{ext}"

            # 保存到 static/uploads/avatars/
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'static', 'uploads', 'avatars'
            )
            os.makedirs(upload_dir, exist_ok=True)

            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)

            avatar_url = f'/static/uploads/avatars/{filename}'

        # 更新数据库
        user.avatar = avatar_url
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '头像上传成功',
            'data': {
                'avatar': avatar_url
            }
        })

    except Exception as e:
        logger.error(f"[UploadAvatar] 上传头像失败: {e}")
        return jsonify({'success': False, 'message': '头像上传失败，请重试'}), 500

