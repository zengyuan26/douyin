"""
公开内容生成平台 - API路由

蓝图前缀：/public
"""

import json
import datetime
import logging
import threading
import signal
import functools
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, current_app
from flask_login import current_user
from sqlalchemy import text
from models.public_models import PublicUser, PublicGeneration, PublicPricingPlan, SavedPortrait, TopicGenerationLink
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

# =============================================================================
# 请求超时装饰器
# =============================================================================

class RequestTimeout(Exception):
    """请求超时异常"""
    pass


def run_with_timeout(func, args, kwargs, timeout_seconds=90):
    """
    在子线程中运行函数并超时控制。

    Args:
        func: 要执行的函数（不能访问 request 等请求上下文对象）
        args, kwargs: 函数参数
        timeout_seconds: 超时秒数

    Returns:
        (result, timed_out)
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout_seconds)
            return result, False
        except FuturesTimeoutError:
            logger.warning(f"[{func.__name__}] 请求处理超时 ({timeout_seconds}秒)")
            return None, True

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


@public_bp.route('/produce')
def produce_page():
    """生成内容页 - 网易云播放列表风格"""
    return render_template('public/produce.html')


@public_bp.route('/content-detail')
def content_detail_page():
    """内容详情页"""
    return render_template('public/content_detail.html')


@public_bp.route('/content-versions')
def content_versions_page():
    """选题内容版本列表页"""
    return render_template('public/content_versions.html')


@public_bp.route('/portraits')
def portraits_page():
    """客户画像管理页"""
    return render_template('public/portraits.html')


@public_bp.route('/portraits/create')
def portraits_create_page():
    """生成画像独立页面（无客户画像/为你推荐）"""
    import logging, os, json
    logger = logging.getLogger('app')
    log_path = '/Volumes/增元/项目/douyin/.cursor/debug.log'
    try:
        rendered = render_template('public/portraits_create.html')
        # 验证渲染后的关键元素
        checks = {
            'topbar-auth': 'id="topbar-auth"' in rendered,
            'topbar-user': 'id="topbar-user"' in rendered,
            'portraitMineAndGenerate': 'portraitMineAndGenerate()' in rendered,
            'handleServiceScenarioChange': 'handleServiceScenarioChange()' in rendered,
            'loadUserAuth': 'loadUserAuth()' in rendered,
            'topbar-auth_before_user': rendered.find('id="topbar-auth"') < rendered.find('id="topbar-user"') if 'id="topbar-auth"' in rendered and 'id="topbar-user"' in rendered else False,
        }
        logger.info('HYPOTHESIS_CHECK|rendered_len=%d|checks=%s', len(rendered), json.dumps(checks))
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'render_ok', 'rendered_len': len(rendered), 'checks': checks, 'timestamp': 0}, ensure_ascii=False) + '\n')
        return rendered
    except Exception as e:
        logger.error('HYPOTHESIS_CHECK|render_failed|error=%s', str(e))
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'render_failed', 'error': str(e), 'timestamp': 0}, ensure_ascii=False) + '\n')
        raise


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
    keyword_library = params.get('keyword_library', None)  # 前端传递的关键词库
    problem_types = params.get('problem_types', [])       # 前端传递的问题类型
    
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
        portrait_name = f"画像_{datetime.datetime.now().strftime('%m%d_%H%M')}"

    seasonal_config = params.get('seasonal_config', None)
    # 插入新记录
    new_portrait = SavedPortrait(
        user_id=user.id,
        portrait_data=portrait_data,
        portrait_name=portrait_name,
        business_description=business_description,
        industry=industry,
        target_customer=target_customer,
        is_default=set_as_default,
        keyword_library=keyword_library,  # 保存前端传递的关键词库
        seasonal_config=seasonal_config,
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

    try:
        from services.portrait_library_task_service import generate_with_semaphore
        thread = threading.Thread(
            target=generate_with_semaphore,
            args=(portrait_id, user.id),
            daemon=True
        )
        thread.start()
        logger.info("[api_save_portrait] 已提交词库生成任务 portrait_id=%s", portrait_id)
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


@public_bp.route('/api/portraits/<int:portrait_id>', methods=['GET'])
def api_get_portrait_detail(portrait_id):
    """获取单个画像详情（用于轮询状态）"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import SavedPortrait
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    return jsonify({
        'success': True,
        'data': {
            'id': portrait.id,
            'portrait_name': portrait.portrait_name,
            'generation_status': portrait.generation_status or 'pending',
            'keyword_library': portrait.keyword_library,
            'topic_library': portrait.topic_library,
            'business_description': portrait.business_description or '',
            'industry': portrait.industry or '',
            'portrait_data': portrait.portrait_data or {},
            'session_id': portrait.session_id,
        }
    })


@public_bp.route('/api/portraits/<int:portrait_id>/status', methods=['GET'])
def api_portrait_status(portrait_id):
    """轻量化状态端点（轮询专用，仅返回生成状态字段）"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    # 从数据库直接获取 generation_status
    row = db.session.execute(
        text("SELECT generation_status, generation_error FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()

    gen_status = row[0] if row else 'pending'
    gen_error = row[1] if row else None

    return jsonify({
        'success': True,
        'data': {
            'id': portrait.id,
            'generation_status': gen_status,
            'generation_error': gen_error,
            'keyword_library': portrait.keyword_library,
            'topic_library': portrait.topic_library,
            'keyword_updated_at': portrait.keyword_updated_at.isoformat() if portrait.keyword_updated_at else None,
            'topic_updated_at': portrait.topic_updated_at.isoformat() if portrait.topic_updated_at else None,
        }
    })


@public_bp.route('/api/portraits/<int:portrait_id>/library/generate', methods=['POST'])
def api_trigger_library_generate(portrait_id):
    """触发关键词库和选题库生成"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import SavedPortrait
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    # 免费用户不支持生成
    if not user.is_paid_user():
        return jsonify({'success': False, 'message': '当前为免费用户，不支持此功能'}), 403

    # 更新状态为生成中
    db.session.execute(
        text("UPDATE saved_portraits SET generation_status = 'generating' WHERE id = :id"),
        {'id': portrait_id}
    )
    db.session.commit()

    # 启动后台线程生成词库
    import threading
    plan_type = user.premium_plan or 'basic'
    try:
        from services.portrait_library_task_service import generate_with_semaphore
        thread = threading.Thread(
            target=generate_with_semaphore,
            args=(portrait_id, user.id),
            daemon=True
        )
        thread.start()
        logger.info("[api_trigger_library_generate] 已提交词库生成任务 portrait_id=%s", portrait_id)
    except Exception as e:
        logger.error("[api_trigger_library_generate] 启动词库生成任务失败: %s", e)

    return jsonify({'success': True, 'message': '已启动生成'})


@public_bp.route('/api/portraits/<int:portrait_id>/keyword-library-md', methods=['GET'])
def api_get_keyword_library_md(portrait_id):
    """获取关键词库 Markdown 格式"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import SavedPortrait
    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=user.id).first()
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    keyword_library = portrait.keyword_library
    if not keyword_library:
        return jsonify({'success': False, 'message': '关键词库为空'}), 404

    # 生成 Markdown 格式
    md_lines = [f"# {portrait.portrait_name or '关键词库'}"]
    md_lines.append("")

    # 判断格式类型
    # 新模板格式（generate_template）：categories[].category_name + keywords
    # 旧蓝海格式（market_analyzer）：categories[].market_type 或 blue_ocean 字段
    # 旧画像格式（KeywordTopicGenerator）：problem_type_keywords 等扁平字段
    has_categories = bool(keyword_library.get('categories'))
    has_market_type = any(
        cat.get('market_type') for cat in keyword_library.get('categories', [])
        if isinstance(cat, dict)
    )
    has_blue_ocean = bool(keyword_library.get('blue_ocean'))
    has_flat_fields = bool(
        keyword_library.get('problem_type_keywords') or
        keyword_library.get('pain_point_keywords') or
        keyword_library.get('scene_keywords') or
        keyword_library.get('concern_keywords')
    )

    is_template_format = has_categories and not has_market_type and not has_blue_ocean
    is_old_market_format = has_market_type or has_blue_ocean

    if is_template_format:
        # === 模板格式（9大分类）：categories[].category_name + keywords ===
        md_lines.append("## 关键词库")
        md_lines.append("")
        total_count = 0
        for i, cat in enumerate(keyword_library['categories'], 1):
            cat_name = cat.get('category_name', cat.get('name', '未分类'))
            keywords = cat.get('keywords', [])
            total_count += len(keywords)
            md_lines.append(f"### {i}、{cat_name}（{len(keywords)}个）")
            md_lines.append("")
            for kw in keywords:
                md_lines.append(f"- {kw}")
            md_lines.append("")
        md_lines.append(f"*合计：{total_count}个关键词*")

    elif is_old_market_format:
        # === 旧格式（蓝海/红海分类）：market_type ===
        md_lines.append("## 一、关键词库")
        md_lines.append("")
        for cat in keyword_library['categories']:
            cat_name = cat.get('category_name', cat.get('name', '未分类'))
            cat_desc = cat.get('category_desc', '')
            market_type = cat.get('market_type', '')
            keywords = cat.get('keywords', [])

            market_icon = '🌊' if market_type == 'blue_ocean' else ('🔴' if market_type == 'red_ocean' else '⚪')
            md_lines.append(f"### {market_icon} {cat_name}")
            if cat_desc:
                md_lines.append(f"*{cat_desc}*")
            md_lines.append("")
            for kw in keywords:
                md_lines.append(f"- {kw}")
            md_lines.append("")

    elif has_flat_fields:
        # === 旧格式（KeywordTopicGenerator扁平字段）===
        def write_kw_section(title, keywords):
            if not keywords:
                return
            md_lines.append(f"## {title}")
            md_lines.append("")
            for kw in keywords:
                md_lines.append(f"- {kw}")
            md_lines.append("")

        write_kw_section("一、问题类型关键词", keyword_library.get('problem_type_keywords', []))
        write_kw_section("二、痛点关键词", keyword_library.get('pain_point_keywords', []))
        write_kw_section("三、场景关键词", keyword_library.get('scene_keywords', []))
        write_kw_section("四、顾虑关键词", keyword_library.get('concern_keywords', []))

        blue_ocean = keyword_library.get('blue_ocean', [])
        if blue_ocean:
            md_lines.append("## 五、蓝海关键词")
            md_lines.append("")
            for kw in blue_ocean:
                md_lines.append(f"- {kw}")
            md_lines.append("")

    return jsonify({
        'success': True,
        'data': {
            'markdown': '\n'.join(md_lines)
        }
    })


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
# 选题热力日历 API
# =============================================================================

# 内容类型分类（根据 content_type / content_style / geo_mode 推断）
_CONTENT_CATEGORY_WEIGHTS = {
    'short_video': 'seed',       # 短视频 → 种草型
    'graphic': 'convert',        # 图文 → 转化型（图文偏向成交）
    'long_text': 'persona',     # 长文 → 人设型
}
_STYLE_TO_CATEGORY = {
    '情绪共鸣': 'seed', '痛点放大': 'seed', '问题锁定': 'seed',
    '方案对比': 'seed', '对比型': 'seed',
    '产品种草': 'seed',
    '转化型': 'convert', '顾虑消除': 'convert', '促销催促': 'convert',
    '人设故事': 'persona', '情感故事': 'persona', '行业科普': 'persona',
    '实操技巧': 'persona', '技能分享': 'persona',
}


def _infer_content_category(gen, link):
    """根据 generation 和 link 推断内容类别：seed(种草)/convert(转化)/persona(人设)"""
    # 优先看 content_style
    style = (gen.content_style or '').strip()
    if style in _STYLE_TO_CATEGORY:
        return _STYLE_TO_CATEGORY[style]
    # 其次看 content_type
    ctype = (gen.content_type or '').strip()
    if ctype in _CONTENT_CATEGORY_WEIGHTS:
        return _CONTENT_CATEGORY_WEIGHTS[ctype]
    # 默认按 geo_mode 猜
    geo = (gen.geo_mode_used or '').strip()
    if '对比' in geo or '答案' in geo or '场景' in geo:
        return 'seed'
    if '顾虑' in geo or '促销' in geo:
        return 'convert'
    if '故事' in geo or '科普' in geo or '技巧' in geo:
        return 'persona'
    return 'seed'


def _get_stage_suggestion(stage, seed_pct, convert_pct, persona_pct,
                          seasonal_config=None, month=None):
    """根据阶段和近期内容配比，给出内容方向建议"""
    suggestions = []
    off_season_note = ''
    is_current_off_season = False

    if stage in ('起号阶段', '起号'):
        ideal = {'seed': 60, 'convert': 5, 'persona': 35}
    elif stage in ('成长阶段', '成长'):
        ideal = {'seed': 55, 'convert': 20, 'persona': 25}
    else:
        ideal = {'seed': 40, 'convert': 40, 'persona': 20}

    if seed_pct > ideal['seed'] + 15:
        suggestions.append('痛点内容偏多，可适当增加人设内容平衡')
    elif seed_pct < ideal['seed'] - 20:
        suggestions.append('建议增加痛点放大类内容，增强圈人效果')

    if convert_pct < ideal['convert'] - 10 and stage != '起号阶段':
        suggestions.append('转化型内容偏少，可适当增加顾虑消除内容')

    if persona_pct < ideal['persona'] - 15:
        suggestions.append('人设内容偏少，建议补充情感故事或行业科普内容')

    if not suggestions:
        suggestions.append('内容配比良好，继续保持')

    # 淡季提示
    if seasonal_config and seasonal_config.get('has_seasonality') and month is not None:
        peak = seasonal_config.get('peak_months', [])
        if month not in peak:
            is_current_off_season = True
            note = seasonal_config.get('off_season_note', '').strip()
            if note:
                off_season_note = note
                suggestions.insert(0, '⚠️ 当前为淡季月：' + note)
            else:
                suggestions.insert(0, '⚠️ 当前为淡季月，内容方向可偏向人设和行业科普')

    return {
        'stage': stage,
        'ideal_ratio': ideal,
        'current_ratio': {'seed': seed_pct, 'convert': convert_pct, 'persona': persona_pct},
        'suggestions': suggestions,
        'is_current_off_season': is_current_off_season,
        'off_season_note': off_season_note,
    }


def _is_peak_month(seasonal_config, month):
    """判断某月是否为旺季"""
    if not seasonal_config or not seasonal_config.get('has_seasonality'):
        return False
    peak = seasonal_config.get('peak_months', [])
    return month in peak


def _is_off_season_month(seasonal_config, month):
    """判断某月是否为淡季（旺月之外的其他月份视为淡季）"""
    if not seasonal_config or not seasonal_config.get('has_seasonality'):
        return False
    peak = seasonal_config.get('peak_months', [])
    return month not in peak

@public_bp.route('/api/produce/calendar', methods=['GET'])
def api_produce_calendar():
    """
    获取选题使用热力日历数据

    Query Params:
        portrait_id: 画像ID（必填）
        year: 年份，默认当前年
        month: 月份，默认当前月
    """
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    portrait_id = request.args.get('portrait_id', type=int)
    if not portrait_id:
        return jsonify({'success': False, 'message': 'portrait_id 为必填参数'}), 400

    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    now = datetime.datetime.now()
    if not year:
        year = now.year
    if not month:
        month = now.month

    from models.public_models import TopicGenerationLink, PublicGeneration

    month_start = datetime.datetime(year, month, 1)
    if month == 12:
        month_end = datetime.datetime(year + 1, 1, 1)
    else:
        month_end = datetime.datetime(year, month + 1, 1)

    links = (
        db.session.query(PublicGeneration, TopicGenerationLink)
        .join(TopicGenerationLink, PublicGeneration.link_id == TopicGenerationLink.id)
        .filter(
            PublicGeneration.user_id == user.id,
            PublicGeneration.portrait_id == portrait_id,
            PublicGeneration.created_at >= month_start,
            PublicGeneration.created_at < month_end,
        )
        .order_by(PublicGeneration.created_at.desc())
        .all()
    )

    # 取画像配置（淡旺季 + 阶段）
    portrait = db.session.get(SavedPortrait, portrait_id)
    seasonal_config = portrait.seasonal_config if portrait else None
    content_stage = (portrait.content_stage or '成长阶段') if portrait else '成长阶段'

    day_map = {}
    total_generations = 0
    all_topics = set()
    type_counts = {'seed': 0, 'convert': 0, 'persona': 0}

    for gen, link in links:
        day = gen.created_at.day
        cat = _infer_content_category(gen, link)
        if day not in day_map:
            day_map[day] = {'generations': [], 'topic_count': set(), 'topic_names': [], 'types': {'seed': 0, 'convert': 0, 'persona': 0}}
        day_map[day]['generations'].append(gen)
        day_map[day]['types'][cat] = day_map[day]['types'].get(cat, 0) + 1
        type_counts[cat] = type_counts.get(cat, 0) + 1
        if link.topic_id:
            day_map[day]['topic_count'].add(link.topic_id)
            all_topics.add(link.topic_id)
            if link.topic_title:
                day_map[day]['topic_names'].append(link.topic_title)
        total_generations += 1

    # 月度集中度
    concentration_score = 0.0
    if day_map:
        daily_scores = []
        for day, info in day_map.items():
            gc = len(info['generations'])
            tc = max(len(info['topic_count']), 1)
            daily_scores.append(gc / tc)
        concentration_score = min(1.0, (sum(daily_scores) / len(daily_scores)) / 5.0)

    # 上月集中度对比
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    prev_start = datetime.datetime(prev_year, prev_month, 1)
    prev_end = month_start  # current month's start

    prev_links = (
        db.session.query(PublicGeneration, TopicGenerationLink)
        .join(TopicGenerationLink, PublicGeneration.link_id == TopicGenerationLink.id)
        .filter(
            PublicGeneration.user_id == user.id,
            PublicGeneration.portrait_id == portrait_id,
            PublicGeneration.created_at >= prev_start,
            PublicGeneration.created_at < prev_end,
        )
        .all()
    )

    prev_day_map = {}
    for gen, link in prev_links:
        day = gen.created_at.day
        if day not in prev_day_map:
            prev_day_map[day] = {'generations': 0, 'topic_count': set()}
        prev_day_map[day]['generations'] += 1
        if link.topic_id:
            prev_day_map[day]['topic_count'].add(link.topic_id)

    prev_score = 0.0
    if prev_day_map:
        prev_scores = []
        for day, info in prev_day_map.items():
            gc = info['generations']
            tc = max(len(info['topic_count']), 1)
            prev_scores.append(gc / tc)
        prev_score = min(1.0, (sum(prev_scores) / len(prev_scores)) / 5.0)

    diff = concentration_score - prev_score
    if abs(diff) < 0.05:
        concentration_trend, trend_value = 'stable', '持平'
    elif diff > 0:
        concentration_trend, trend_value = 'up', f'+{int(diff * 100)}%'
    else:
        concentration_trend, trend_value = 'down', f'{int(diff * 100)}%'

    # 类型占比（用于阶段建议）
    seed_count = type_counts.get('seed', 0)
    convert_count = type_counts.get('convert', 0)
    persona_count = type_counts.get('persona', 0)
    total_cat = max(seed_count + convert_count + persona_count, 1)
    seed_pct = round(seed_count / total_cat * 100)
    convert_pct = round(convert_count / total_cat * 100)
    persona_pct = 100 - seed_pct - convert_pct

    # 每日格子数据（含类型分类 + 旺淡月标识）
    import calendar as cal_module
    days_in_month = cal_module.monthrange(year, month)[1]
    is_peak = _is_peak_month(seasonal_config, month)
    is_off_season = _is_off_season_month(seasonal_config, month)
    days_data = []
    for day in range(1, days_in_month + 1):
        if day in day_map:
            info = day_map[day]
            gc = len(info['generations'])
            tc = len(info['topic_count'])
            topic_names = list(dict.fromkeys(info['topic_names']))[:5]

            topic_gen_count = {}
            for gen in info['generations']:
                if gen.link and gen.link.topic_title:
                    t = gen.link.topic_title
                    topic_gen_count[t] = topic_gen_count.get(t, 0) + 1
            hottest = max(topic_gen_count, key=topic_gen_count.get) if topic_gen_count else ''
            hottest_count = max(topic_gen_count.values()) if topic_gen_count else 0

            ratio = gc / max(tc, 1)
            concentration = 'high' if ratio >= 3 else ('medium' if ratio >= 1.5 else 'low')

            # 当天主导类型
            day_types = info.get('types', {})
            dominant = max(day_types, key=day_types.get) if day_types else 'seed'
            dominant_count = day_types.get(dominant, 0) if day_types else 0

            days_data.append({
                'day': day,
                'date': f'{year}-{month:02d}-{day:02d}',
                'generation_count': gc,
                'topic_count': tc,
                'topic_names': topic_names,
                'topic_repeated': gc > tc,
                'concentration': concentration,
                'hottest_topic': hottest,
                'hottest_topic_count': hottest_count,
                'breakdown': day_types,
                'dominant_type': dominant if dominant_count > 0 else None,
                'is_peak': is_peak,
                'is_off_season': is_off_season,
            })
        else:
            days_data.append({
                'day': day,
                'date': f'{year}-{month:02d}-{day:02d}',
                'generation_count': 0,
                'topic_count': 0,
                'topic_names': [],
                'topic_repeated': False,
                'concentration': 'none',
                'hottest_topic': '',
                'hottest_topic_count': 0,
                'breakdown': {'seed': 0, 'convert': 0, 'persona': 0},
                'dominant_type': None,
                'is_peak': is_peak,
                'is_off_season': is_off_season,
            })

    # 阶段建议（含淡季提示）
    stage_suggestion = _get_stage_suggestion(content_stage, seed_pct, convert_pct, persona_pct,
                                             seasonal_config=seasonal_config, month=month)
    # 有内容的总天数
    days_with_content = sum(1 for d in days_data if d['generation_count'] > 0)

    return jsonify({
        'success': True,
        'data': {
            'year': year,
            'month': month,
            'portrait_id': portrait_id,
            'seasonal_config': seasonal_config,
            'total_generations': total_generations,
            'total_topics': len(all_topics),
            'concentration_score': round(concentration_score, 2),
            'concentration_trend': concentration_trend,
            'trend_value': trend_value,
            'days': days_data,
            'month_stats': {
                'total_generations': total_generations,
                'seed_count': seed_count,
                'convert_count': convert_count,
                'persona_count': persona_count,
                'days_with_content': days_with_content,
            },
            'stage_suggestion': stage_suggestion,
        }
    })


@public_bp.route('/api/portraits/<int:portrait_id>/calendar/day', methods=['GET'])
def api_portrait_calendar_day(portrait_id):
    """获取某一天的生成内容详情"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    date_str = request.args.get('date')  # YYYY-MM-DD
    if not date_str:
        return jsonify({'success': False, 'message': 'date 参数必填'}), 400

    try:
        target = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'success': False, 'message': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    day_start = target
    day_end = target + datetime.timedelta(days=1)

    generations = (
        db.session.query(PublicGeneration, TopicGenerationLink)
        .outerjoin(TopicGenerationLink, PublicGeneration.link_id == TopicGenerationLink.id)
        .filter(
            PublicGeneration.user_id == user.id,
            PublicGeneration.portrait_id == portrait_id,
            PublicGeneration.created_at >= day_start,
            PublicGeneration.created_at < day_end,
        )
        .order_by(PublicGeneration.created_at.desc())
        .all()
    )

    items = []
    for gen, link in generations:
        title = ''
        if gen.titles and isinstance(gen.titles, list) and len(gen.titles) > 0:
            title = gen.titles[0].get('title', '')
        elif gen.content_data:
            title = gen.content_data.get('title', '')

        cat = _infer_content_category(gen, link)
        stage_name_map = {
            'audience': '受众锁定', 'pain': '痛点放大', 'compare': '方案对比',
            'hesitation': '顾虑消除', 'upstream': '上游科普',
            'industry': '行业关联', 'emotional': '情感故事', 'skill': '实操技巧',
        }
        geo_mode = gen.geo_mode_used or (link.geo_mode if link else '')
        stage_key = ''
        for k in stage_name_map:
            if k in (geo_mode or ''):
                stage_key = k
                break

        # 推断内容方向
        dir_map = {'seed': '种草型', 'convert': '转化型', 'persona': '种草型'}
        direction = dir_map.get(cat, '种草型')

        items.append({
            'id': gen.id,
            'title': title,
            'content_type': gen.content_type or 'graphic',
            'content_style': gen.content_style or '',
            'geo_mode': geo_mode,
            'stage_key': stage_key,
            'stage_name': stage_name_map.get(stage_key, ''),
            'direction': direction,
            'category': cat,
            'created_at': gen.created_at.strftime('%Y-%m-%d %H:%M'),
        })

    # 摘要
    seed_n = sum(1 for i in items if i['category'] == 'seed')
    convert_n = sum(1 for i in items if i['category'] == 'convert')
    persona_n = sum(1 for i in items if i['category'] == 'persona')
    summary_parts = []
    if seed_n:
        summary_parts.append(f'{seed_n}篇种草型')
    if convert_n:
        summary_parts.append(f'{convert_n}篇转化型')
    if persona_n:
        summary_parts.append(f'{persona_n}篇人设型')
    day_summary = ('今天主要生成了 ' + '、'.join(summary_parts)) if summary_parts else '今天没有生成内容'

    return jsonify({
        'success': True,
        'data': {
            'date': date_str,
            'total_count': len(items),
            'generations': items,
            'day_summary': day_summary,
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
            'content_type': generation.content_type,
            'titles': generation.titles,
            'tags': generation.tags,
            'content': generation.content,
            'used_tokens': generation.used_tokens or 0,
            'portrait_id': generation.portrait_id,
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
    换一批选题（所有用户可用）

    请求格式：
    {
        "business_description": "...",
        "portraits": [...],
        "problem_keywords": [...]
    }
    """
    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None

    # 所有用户都可以换一批选题（无付费限制）
    is_premium = user and user.is_paid_user()

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
            is_premium=is_premium
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
# 后台生成内容（异步）
# =============================================================================
def _background_generate_content(generation_id, params, result_type, content_style, app_context):
    """后台生成内容并更新generation记录"""
    from models.models import db
    from services.content_generator import TopicContentGenerator
    from services.content_quality_scorer import content_scorer
    from services.content_quality_optimizer import content_optimizer

    with app_context:
        try:
            gen = PublicGeneration.query.get(generation_id)
            if not gen:
                logger.error(f"[后台生成] generation记录不存在: {generation_id}")
                return

            user = PublicUser.query.get(gen.user_id) if gen.user_id else None
            is_premium = user and user.is_paid_user()

            # 更新选题生成次数
            portrait_id = params.get('portrait_id')
            topic_id = params.get('topic_id')
            if portrait_id and topic_id:
                try:
                    portrait = SavedPortrait.query.filter_by(id=portrait_id, user_id=gen.user_id).first()
                    if portrait and portrait.topic_library:
                        topics = portrait.topic_library.get('topics', [])
                        for topic in topics:
                            if topic.get('id') == topic_id:
                                topic['generation_count'] = topic.get('generation_count', 0) + 1
                                break
                        db.session.commit()
                except Exception as e:
                    logger.warning(f"[后台生成] 更新选题生成次数失败: {e}")

            # 实际执行内容生成
            generator = TopicContentGenerator()
            result = generator.generate_content(
                topic_id=params.get('topic_id', ''),
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                topic_type_key=params.get('topic_type_key', ''),
                business_description=params.get('business_description', ''),
                business_range=params.get('business_range', ''),
                business_type=params.get('business_type', ''),
                portrait=params.get('portrait', {}),
                is_premium=is_premium,
                premium_plan=user.premium_plan if user else 'free',
                content_style=content_style,
                selected_scene=params.get('selected_scene'),
            )

            if not result.get('success'):
                gen.content_data = {'error': result.get('error', '生成失败')}
                db.session.commit()
                return

            content = result.get('content', {})
            brand_name = params.get('portrait', {}).get('brand_name', '') or params.get('business_description', '')[:10]

            # 质量评分与优化
            score_result = content_scorer.score(content, brand_name)
            quality_report = {
                'total_score': score_result.total_score,
                'grade': score_result.grade,
                'grade_label': score_result.grade_label,
                'passed': score_result.passed,
                'optimized': False,
                'items': content_scorer.to_dict(score_result)['items'],
                'summary': score_result.summary,
                'suggestions': score_result.suggestions,
            }

            if not score_result.passed:
                optimization_result = content_optimizer.optimize(
                    content=content,
                    failed_items=score_result.failed_items,
                    brand_name=brand_name,
                    business_desc=params.get('business_description', '')
                )
                if optimization_result.success and optimization_result.optimized_content:
                    content = optimization_result.optimized_content
                quality_report['optimized'] = optimization_result.success
                quality_report['final_score'] = optimization_result.score_after
                quality_report['optimized_items'] = optimization_result.optimized_items

            # 更新generation记录
            gen.titles = [content.get('title', '')]
            gen.tags = content.get('tags', [])
            gen.content_data = content
            gen.used_tokens = result.get('tokens_used', 0)
            gen.geo_mode_used = content.get('geo_mode', '')
            gen.quality_score = quality_report.get('final_score', score_result.total_score)
            gen.quality_report = quality_report

            db.session.commit()
            logger.info(f"[后台生成] 完成 generation_id={generation_id}")

        except Exception as e:
            logger.exception(f"[后台生成 Error] generation_id={generation_id}: %s", e)
            try:
                gen = PublicGeneration.query.get(generation_id)
                if gen:
                    gen.content_data = {'error': str(e)}
                    db.session.commit()
            except:
                pass


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
    logger.info(f"[ContentGenerate] 请求参数: {list(params.keys())}, topic_title={params.get('topic_title', '')[:50] if params.get('topic_title') else 'None'}")

    # 必填字段检查
    if not params.get('topic_title'):
        logger.warning(f"[ContentGenerate] 缺少选题标题，params keys: {list(params.keys())}")
        return jsonify({'success': False, 'message': '请选择选题'}), 400

    if not params.get('business_description'):
        logger.warning(f"[ContentGenerate] 缺少业务描述，portrait: {str(params.get('portrait', {}))[:100]}")
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

    # 声明 SavedPortrait 和 TopicGenerationLink 为局部引用（避免被函数内其他 import 语句误判为局部变量）
    import models.public_models as pm
    _SavedPortrait = pm.SavedPortrait
    _TopicGenerationLink = pm.TopicGenerationLink

    try:
        
        # ══ 场景自动轮换：同选题同内容类型时自动换场景（所有内容类型共用）══
        topic_id_str = params.get('topic_id', '') or ''
        content_type = params.get('content_type', 'graphic')
        content_style = params.get('content_style', '')
        raw_scene = params.get('selected_scene')  # 前端传来的第一个场景
        effective_scene = raw_scene  # 默认用前端指定的场景
        portrait_id_val = params.get('portrait_id')

        if topic_id_str and user:
            # 查询该选题 + 内容类型的历史生成记录
            history_gens = PublicGeneration.query.filter(
                PublicGeneration.topic_id == topic_id_str,
                PublicGeneration.content_type == content_type,
                PublicGeneration.user_id == user.id
            ).order_by(PublicGeneration.created_at.desc()).all()

            if history_gens:
                # 提取已用场景标识集合
                used_scene_keys = set()
                for gen in history_gens:
                    sel = gen.selected_scenes
                    if sel and isinstance(sel, dict):
                        key = sel.get('id') or sel.get('pain_name') or sel.get('label', '')
                        if key:
                            used_scene_keys.add(key)

                if used_scene_keys:
                    # 从选题库获取完整 scene_options
                    scene_options = []
                    if portrait_id_val:
                        portrait = _SavedPortrait.query.filter_by(
                            id=portrait_id_val, user_id=user.id
                        ).first()
                        if portrait and portrait.topic_library:
                            for t in portrait.topic_library.get('topics', []):
                                if t.get('id') == topic_id_str:
                                    scene_options = t.get('scene_options', [])
                                    break

                    # 找第一个未用过的场景
                    next_scene = None
                    for sc in scene_options:
                        key = sc.get('id') or sc.get('pain_name') or sc.get('label', '')
                        if key and key not in used_scene_keys:
                            next_scene = sc
                            break

                    if next_scene:
                        effective_scene = next_scene
                    else:
                        # 全部用过了，循环回第一个
                        effective_scene = scene_options[0] if scene_options else raw_scene

                    logger.info(f"[SceneRotation] topic={topic_id_str} type={content_type} "
                                f"used={used_scene_keys} next={effective_scene}")

            qs_int = 0
            bridge_data = {}
            keyword_library = params.get('keyword_library', {}) or {}

            # 根据内容类型调用不同的生成器
            if content_type == 'short_video':
                # 短视频脚本生成 —— SkillBridge v2
                from services.skill_bridge import SkillBridge
                bridge = SkillBridge()
                bridge_result = bridge.execute_video_script_generator(
                    topic_id=params.get('topic_id', ''),
                    topic_title=params.get('topic_title', ''),
                    topic_type=params.get('topic_type', ''),
                    topic_type_key=params.get('topic_type_key', ''),
                    business_description=params.get('business_description', ''),
                    business_range=params.get('business_range', ''),
                    business_type=params.get('business_type', ''),
                    portrait=params.get('portrait', {}),
                    keyword_library=keyword_library,
                    selected_scene=effective_scene,
                    content_style=content_style,
                    brand_context=params.get('brand_context'),
                )

                if not bridge_result.success:
                    return jsonify({
                        'success': False,
                        'message': f"短视频脚本生成失败: {bridge_result.errors[0] if bridge_result.errors else '未知错误'}"
                    }), 500

                fo = bridge_result.full_output
                bridge_data = _build_video_script_data_from_bridge(fo)

                # H-V-F 标题生成 + 金字塔标签
                (
                    extracted_title,
                    extracted_tags,
                    extracted_geo,
                    hvf_titles_output,
                    pyramid_tags_output,
                    hvf_report,
                    pyramid_tags_report,
                ) = _apply_hvf_and_tags(
                    result={'success': True, 'content': bridge_data['content_data']},
                    params=params,
                    result_type='short_video',
                    content_result=bridge_data['content_data'],
                )

                if extracted_title:
                    bridge_data['content_data']['title'] = extracted_title
                if extracted_tags:
                    bridge_data['content_data']['tags'] = extracted_tags

                qs_int = bridge_data['quality_score']
                quality_report = bridge_data['quality_report']
                content = _build_video_script_text(bridge_data['content_data'])
                result_type = 'short_video'

            elif content_type == 'long_text':
                # 长文生成 —— SkillBridge v2
                from services.skill_bridge import SkillBridge
                bridge = SkillBridge()
                bridge_result = bridge.execute_long_text_generator(
                    topic_id=params.get('topic_id', ''),
                    topic_title=params.get('topic_title', ''),
                    topic_type=params.get('topic_type', ''),
                    topic_type_key=params.get('topic_type_key', ''),
                    business_description=params.get('business_description', ''),
                    business_range=params.get('business_range', ''),
                    business_type=params.get('business_type', ''),
                    portrait=params.get('portrait', {}),
                    keyword_library=keyword_library,
                    selected_scene=effective_scene,
                    content_style=content_style,
                    brand_context=params.get('brand_context'),
                )

                if not bridge_result.success:
                    return jsonify({
                        'success': False,
                        'message': f"长文生成失败: {bridge_result.errors[0] if bridge_result.errors else '未知错误'}"
                    }), 500

                fo = bridge_result.full_output
                bridge_data = _build_long_text_data_from_bridge(fo)

                # H-V-F 标题生成 + 金字塔标签
                (
                    extracted_title,
                    extracted_tags,
                    extracted_geo,
                    hvf_titles_output,
                    pyramid_tags_output,
                    hvf_report,
                    pyramid_tags_report,
                ) = _apply_hvf_and_tags(
                    result={'success': True, 'content': bridge_data['content_data']},
                    params=params,
                    result_type='long_text',
                    content_result=bridge_data['content_data'],
                )

                if extracted_title:
                    bridge_data['content_data']['title'] = extracted_title
                if extracted_tags:
                    bridge_data['content_data']['tags'] = extracted_tags

                qs_int = bridge_data['quality_score']
                quality_report = bridge_data['quality_report']
                content = _build_long_text_text(bridge_data['content_data'])
                result_type = 'long_text'

            else:
                # 图文生成（默认）—— SkillBridge v2
                from services.skill_bridge import SkillBridge
                bridge = SkillBridge()
                logger.info(f"[GEO调试] selected_scene: {effective_scene}")

                bridge_result = bridge.execute_content_generator(
                    topic_id=params.get('topic_id', ''),
                    topic_title=params.get('topic_title', ''),
                    topic_type=params.get('topic_type', ''),
                    topic_type_key=params.get('topic_type_key', ''),
                    business_description=params.get('business_description', ''),
                    business_range=params.get('business_range', ''),
                    business_type=params.get('business_type', ''),
                    portrait=params.get('portrait', {}),
                    keyword_library=keyword_library,
                    selected_scene=effective_scene,
                    content_style=content_style,
                    brand_context=params.get('brand_context'),
                )

                if not bridge_result.success:
                    return jsonify({
                        'success': False,
                        'message': f"内容生成失败: {bridge_result.errors[0] if bridge_result.errors else '未知错误'}"
                    }), 500

                fo = bridge_result.full_output
                bridge_data = _build_content_data_from_bridge(fo)

                # 图文分支：H-V-F 标题 + 金字塔标签并行调用（复用 bridge 实例）
                from concurrent.futures import ThreadPoolExecutor
                raw_content = bridge_data['content_data']
                seo_kws = raw_content.get('seo_keywords', {}) if isinstance(raw_content, dict) else {}
                keywords = {
                    'core': seo_kws.get('core', []),
                    'long_tail': seo_kws.get('long_tail', []),
                    'scene': seo_kws.get('scene', []),
                    'problem': seo_kws.get('problem', []),
                }
                portrait = params.get('portrait', {})
                if not keywords.get('core') and portrait:
                    portrait_kws = portrait.get('keywords', [])
                    if isinstance(portrait_kws, list):
                        keywords['core'] = portrait_kws[:5]
                # 从 selected_scene 提取 geo_mode 兜底
                selected_scene = params.get('selected_scene', {})
                geo_from_scene = ''
                if selected_scene and isinstance(selected_scene, dict):
                    geo_from_scene = selected_scene.get('dim_value', '') or selected_scene.get('label', '') or ''
                    if geo_from_scene and ' - ' in geo_from_scene:
                        geo_from_scene = geo_from_scene.split(' - ', 1)[0].strip()
                geo_mode = raw_content.get('geo_mode', '') or params.get('geo_mode', '') or geo_from_scene
                industry = params.get('industry', '') or params.get('business_type', '')

                def call_title():
                    return bridge.execute_title_generator(
                        topic_title=params.get('topic_title', ''),
                        portrait=portrait,
                        keywords=keywords,
                        geo_mode=geo_mode,
                        industry=industry,
                        num_variants=4,
                    )

                def call_tag():
                    return bridge.execute_tag_generator(
                        topic_title=params.get('topic_title', ''),
                        industry=industry,
                        keywords=keywords,
                        portrait=portrait,
                        geo_mode=geo_mode,
                        max_tags=8,
                    )

                hvf_titles_output = {}
                pyramid_tags_output = {}
                try:
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        f_title = executor.submit(call_title)
                        f_tag = executor.submit(call_tag)
                        hvf_res = f_title.result(timeout=60)
                        if hvf_res.success:
                            hvf_titles_output = hvf_res.full_output
                        tag_res = f_tag.result(timeout=60)
                        if tag_res.success:
                            pyramid_tags_output = tag_res.full_output
                except Exception as e:
                    logger.warning(f"[H-V-F] 图文标题/标签生成异常: {e}")

                # 标题以 H-V-F 评分最高者覆盖
                extracted_title = raw_content.get('title', '') or ''
                extracted_tags = raw_content.get('tags', []) or []
                extracted_geo = raw_content.get('geo_mode', '') or ''
                if hvf_titles_output:
                    titles_data = hvf_titles_output.get('titles', []) or hvf_titles_output.get('step_title_generate', {}).get('titles', [])
                    def _title_score(t):
                        s = t.get('hvf_score', {})
                        total = s.get('total', 0)
                        if total:
                            return total
                        if isinstance(s, dict):
                            return s.get('hook', 0) + s.get('value', 0) + s.get('format', 0)
                        return 0
                    best_title_obj = max(titles_data, key=_title_score, default=None)
                    if best_title_obj and best_title_obj.get('main_title'):
                        extracted_title = best_title_obj['main_title']
                if pyramid_tags_output:
                    tags_data = pyramid_tags_output.get('hashtags', []) or pyramid_tags_output.get('step_tag_generate', {}).get('hashtags', [])
                    if tags_data:
                        extracted_tags = tags_data[:8]

                bridge_data['content_data']['title'] = extracted_title
                bridge_data['content_data']['tags'] = extracted_tags

                qs_int = bridge_data['quality_score']
                quality_report = bridge_data['quality_report']
                content = _build_content_text(bridge_data['content_data'])
                result_type = 'graphic'
                hvf_report = _build_hvf_report(hvf_titles_output) if hvf_titles_output else {}
                pyramid_tags_report = _build_pyramid_tags(pyramid_tags_output) if pyramid_tags_output else {}

            result = {
                'success': True,
                'content': content,
                'geo_report': bridge_data['geo_report'],
                'geo_score': qs_int,
                '_skill_bridge_output': fo,
                '_hvf_titles': hvf_titles_output,
                '_pyramid_tags': pyramid_tags_output,
            }

            # ═══════════════════════════════════════════════════════════════
            # 内容质量评分（由 SkillBridge 内部 step_quality_validate 完成）
            # ═══════════════════════════════════════════════════════════════
            topic_id_str = params.get('topic_id', '') or None
            portrait_id_val = params.get('portrait_id')
            link = None
            version_number = 1
            parent_version_id = None

            # ── 1:N 选题关系：创建/更新 link ──
            if user and topic_id_str and portrait_id_val:
                try:
                    # 查找或创建 link
                    link = _TopicGenerationLink.query.filter_by(
                        user_id=user.id,
                        portrait_id=portrait_id_val,
                        topic_id=topic_id_str
                    ).first()

                    if not link:
                        # 从选题库获取标题快照
                        topic_title = params.get('topic_title', '')
                        portrait = _SavedPortrait.query.filter_by(
                            id=portrait_id_val, user_id=user.id
                        ).first()
                        if portrait and portrait.topic_library:
                            for t in portrait.topic_library.get('topics', []):
                                if t.get('id') == topic_id_str:
                                    topic_title = t.get('title', topic_title)
                                    break

                        link = TopicGenerationLink(
                            user_id=user.id,
                            portrait_id=portrait_id_val,
                            problem_id=params.get('problem_id'),
                            topic_id=topic_id_str,
                            topic_title=topic_title,
                            usage_count=0,
                            generation_ids=[],
                            created_at=datetime.datetime.utcnow(),
                        )
                        db.session.add(link)
                        db.session.flush()
                    else:
                        # 有历史版本，记录父版本
                        version_number = link.usage_count + 1
                        if link.generation_ids:
                            parent_version_id = link.generation_ids[-1]

                except Exception as e:
                    logger.warning('创建/查找 link 失败: %s', e)

            # ── raw_content 统一从 bridge_data 提取 ──
            raw_content = bridge_data['content_data']

            # ── 保存 generation 记录 ──
            generation = PublicGeneration(
                user_id=user.id if user else None,
                industry=params.get('business_type', ''),
                target_customer=params.get('portrait', {}).get('identity', ''),
                content_type=result_type,
                titles=[extracted_title],
                tags=extracted_tags,
                content_data={
                    **(raw_content or {}),
                    '_hvf_report': _build_hvf_report(hvf_titles_output) if hvf_titles_output else {},
                    '_pyramid_tags_report': _build_pyramid_tags(pyramid_tags_output) if pyramid_tags_output else {},
                    '_hvf_titles': hvf_titles_output or {},
                    '_pyramid_tags': pyramid_tags_output or {},
                },
                used_tokens=result.get('tokens_used', 0),
                topic_id=topic_id_str,
                portrait_id=portrait_id_val,
                problem_id=params.get('problem_id'),
                selected_scenes=effective_scene,
                link_id=link.id if link else None,
                version_number=version_number,
                parent_version_id=parent_version_id,
                geo_mode_used=extracted_geo,
                content_style=content_style,
                quality_score=qs_int,
                quality_report=quality_report if quality_report else None,
            )
            db.session.add(generation)
            db.session.flush()

            # ── 更新 link ──
            if link:
                link.add_generation(generation.id)
                link.last_generated_at = datetime.datetime.utcnow()
                if link.first_generated_at is None:
                    link.first_generated_at = generation.created_at

            # ── 同步更新选题库 generation_count（保持画像选题库与 link 一致）──
            if link and portrait_id_val:
                from models.public_models import SavedPortrait
                sp = SavedPortrait.query.filter_by(id=portrait_id_val, user_id=user.id).first()
                if sp and sp.topic_library and 'topics' in sp.topic_library:
                    updated = False
                    # topic_id 在选题库中可能为 int/str，统一转为 str 比较
                    tid_str = str(topic_id_str) if topic_id_str else ''
                    for t in sp.topic_library['topics']:
                        t_id = t.get('id')
                        if t_id is not None and str(t_id) == tid_str:
                            t['generation_count'] = link.usage_count
                            updated = True
                            break
                    if updated:
                        logger.info(f"[GenerationCount] 更新 portrait_id={portrait_id_val} topic_id={topic_id_str} generation_count={link.usage_count}")

            # 扣减配额
            if user:
                quota_manager.use_quota(user, result.get('tokens_used', 0))
            db.session.commit()

            result_generation_id = generation.id
            result_link_id = link.id if link else None
            result_version = version_number

            # ── 直接返回结果（不阻塞） ──
            return jsonify({
                'success': True,
                'generation_id': result_generation_id,
                'link_id': result_link_id,
                'version_number': result_version,
                'quality_report': quality_report,
                'content': content,
                # H-V-F 标题报告
                'hvf_report': _build_hvf_report(hvf_titles_output) if hvf_titles_output else {},
                # 金字塔标签报告
                'pyramid_tags': _build_pyramid_tags(pyramid_tags_output) if pyramid_tags_output else {},
                # 提取的最佳标题（来自 H-V-F）
                'title': extracted_title,
                # 提取的标签（来自金字塔）
                'tags': extracted_tags,
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


@public_bp.route('/api/content/<int:generation_id>', methods=['GET'])
def api_content_detail(generation_id):
    """
    获取内容详情（支持版本切换）

    返回：内容 + 选题信息 + 同选题所有版本摘要
    """
    from models.public_models import PublicGeneration, TopicGenerationLink

    # 绕过 ORM session 缓存：使用原始 SQL 直接查询数据库
    # 解决 SSE 线程提交后主线程读取旧缓存的问题
    raw_result = db.session.execute(
        db.text('SELECT id, user_id, content_data, quality_score, quality_report, titles, tags, '
                 'content_type, content_style, geo_mode_used, industry, target_customer, '
                 'portrait_id, topic_id, selected_scenes, link_id, version_number, '
                 'created_at, used_tokens FROM public_generations WHERE id = :gen_id'),
        {'gen_id': generation_id}
    ).mappings().fetchone()

    if not raw_result:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    # 兼容处理：raw SQL 不会自动将 JSON 列反序列化为 dict，需要手动解析
    def _parse_json(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    raw_result = dict(raw_result)
    raw_result['content_data'] = _parse_json(raw_result.get('content_data'))
    raw_result['quality_report'] = _parse_json(raw_result.get('quality_report'))
    raw_result['selected_scenes'] = _parse_json(raw_result.get('selected_scenes'))
    raw_result['titles'] = _parse_json(raw_result.get('titles'))
    raw_result['tags'] = _parse_json(raw_result.get('tags'))

    if not raw_result:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    # 权限校验（使用 raw SQL 结果）
    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None
    gen_user_id = raw_result.get('user_id') if 'user_id' in raw_result.keys() else None
    if user and gen_user_id and gen_user_id != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    # 调试日志：对比 raw SQL 和已知数据
    raw_cd = raw_result.get('content_data') or {}
    logger.info(f"[ContentDetail] generation_id={generation_id}, raw quality_score={raw_result.get('quality_score')}, "
                f"raw quality_report type={type(raw_result.get('quality_report')).__name__ if raw_result.get('quality_report') else None}, "
                f"raw content_data keys={list(raw_cd.keys())}")

    # link 信息（使用 raw SQL 结果）
    link_info = None
    raw_link_id = raw_result.get('link_id')
    if raw_link_id:
        link = TopicGenerationLink.query.get(raw_link_id)
        if link:
            link_info = {
                'link_id': link.id,
                'topic_id': link.topic_id,
                'topic_title': link.topic_title or '',
                'geo_mode': link.geo_mode or '',
                'geo_mode_name': link.geo_mode_name or '',
                'usage_count': link.usage_count or 0,
            }

    # 获取内容展示区块配置（使用 raw SQL 的 content_type）
    content_type = raw_result.get('content_type') or 'graphic'
    from services.template_config_service import template_config_service
    section_display_config = template_config_service.get_section_display_config(content_type)

    # 构建质量报告数据（如果已有完整评分报告，直接使用；否则调用LLM评分）
    quality_report = None
    # 优先使用 raw SQL 查询的最新数据（绕过 ORM 缓存）
    if raw_result.get('quality_report'):
        quality_report = raw_result.get('quality_report')
    elif raw_result.get('content_data'):
        # 没有评分报告但有内容时，调用LLM评分（兼容旧数据）
        from services.content_quality_scorer import content_scorer
        brand_name = (raw_result.get('target_customer') or '')[:10]
        score_result = content_scorer.score(raw_result.get('content_data'), brand_name)
        quality_report = content_scorer.to_dict(score_result)
        quality_report['optimized'] = False
        quality_report['first_score'] = quality_report['total_score']
        quality_report['optimized_items'] = []
        quality_report['need_optimize'] = not score_result.passed
        # 保存评分报告以便后续使用
        gen = PublicGeneration.query.filter_by(id=generation_id).first()
        if gen:
            gen.quality_score = quality_report['total_score']
            gen.quality_report = quality_report
            db.session.commit()

    # 使用 raw SQL 的最新值构建返回数据（绕过 ORM 缓存）
    raw_content_data = raw_result.get('content_data')
    # created_at 可能是 datetime 对象（ORM）或字符串（raw SQL）
    raw_created_at = raw_result.get('created_at')
    if raw_created_at:
        if hasattr(raw_created_at, 'strftime'):
            created_at_str = raw_created_at.strftime('%Y-%m-%d %H:%M')
        else:
            created_at_str = str(raw_created_at)
    else:
        created_at_str = ''

    return jsonify({
        'success': True,
        'data': {
            'generation_id': generation_id,
            'link_id': raw_result.get('link_id'),
            'version_number': raw_result.get('version_number'),
            'content_type': content_type,
            'content_style': raw_result.get('content_style') or '',
            'geo_mode': raw_result.get('geo_mode_used') or '',
            'industry': raw_result.get('industry') or '',
            'target_customer': raw_result.get('target_customer') or '',
            'portrait_id': raw_result.get('portrait_id'),
            'topic_id': raw_result.get('topic_id'),
            'selected_scenes': raw_result.get('selected_scenes'),
            'titles': raw_result.get('titles') or [],
            'tags': raw_result.get('tags') or [],
            'content_data': raw_content_data or {},
            'content': (raw_content_data or {}).get('body', ''),
            'created_at': created_at_str,
            'used_tokens': raw_result.get('used_tokens') or 0,
            'quality_score': raw_result.get('quality_score'),
            'quality_report': quality_report,
            'link': link_info,
            'section_display_config': section_display_config,
        }
    })


@public_bp.route('/api/content/<int:generation_id>/optimize', methods=['POST'])
def api_optimize_content(generation_id):
    """
    递进式优化内容质量（手动触发）

    策略：
    - 组A（战略层）：标题吸引力、开篇直接性
    - 组B（结构层）：结构清晰度、模块化完整
    - 组C（信任层）：信任证据、品牌锚点、关键词密度
    - 组D（体验转化层）：可读性、行动号召、改造潜力

    - 初始分<60：从组A开始，执行全部4组
    - 初始分60~79：从第一个有不合格项的组开始
    - 达到80分自动停止

    返回：每轮优化结果和最终内容
    """
    from services.content_quality_optimizer import progressive_optimizer
    from services.content_quality_scorer import content_scorer

    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None

    gen = PublicGeneration.query.filter_by(id=generation_id).first()
    if not gen:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    # 权限校验
    if user and gen.user_id and gen.user_id != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    content = gen.content_data or {}
    # 兼容长文结构：标题可能在 article.title
    content_title = content.get('title') or (content.get('article') or {}).get('title') or ''
    if not content or not content_title:
        return jsonify({
            'success': False,
            'message': '内容不存在，无法优化'
        }), 400

    brand_name = content.get('brand_name', '') or gen.industry or '品牌'

    # 获取用户业务描述
    business_desc = ''
    if gen.user_id:
        user_obj = PublicUser.query.get(gen.user_id)
        if user_obj and user_obj.profile:
            business_desc = user_obj.profile.business_description or ''

    # 初始分数
    initial_score = gen.quality_score or 50.0

    # 分数已达80以上不允许继续优化
    if initial_score >= 80:
        return jsonify({
            'success': False,
            'message': '该内容分数已达80以上，无需继续优化'
        }), 400

    try:
        # 重新评分获取失败项
        score_result = content_scorer.score(content, brand_name)
        failed_items = list(score_result.failed_items) if hasattr(score_result, 'failed_items') else []

        logger.info(f"[递进优化] generation_id={generation_id}, 初始分={initial_score:.1f}, "
                    f"不合格项={len(failed_items)}: {[f.name for f in failed_items]}")

        # 执行递进式优化
        opt_result = progressive_optimizer.optimize(
            content=content,
            failed_items=failed_items,
            initial_score=initial_score,
            brand_name=brand_name,
            business_desc=business_desc,
            max_rounds=4
        )

        # 更新内容
        new_content = opt_result.optimized_content or content
        gen.content_data = new_content
        new_title = new_content.get('title') or (new_content.get('article') or {}).get('title') or ''
        gen.titles = [new_title]
        gen.tags = new_content.get('tags', [])

        # 构建最终报告
        final_report = opt_result.final_report
        if not final_report:
            final_report = content_scorer.to_dict(score_result)

        final_report['optimized'] = True
        final_report['total_rounds'] = opt_result.total_rounds
        final_report['stopped_early'] = opt_result.stopped_early
        final_report['message'] = opt_result.message

        # 轮次历史
        round_history = [
            {
                'round_num': r.round_num,
                'group_key': r.group_key,
                'group_label': r.group_label,
                'items_in_round': r.items_in_round,
                'items_fixed': r.items_fixed,
                'score_before': r.score_before,
                'score_after': r.score_after,
                'rollback': getattr(r, 'rollback', False),
                'stopped': r.stopped,
                'message': r.message,
            }
            for r in opt_result.round_history
        ]
        final_report['round_history'] = round_history

        # 更新数据库
        gen.quality_score = opt_result.final_score
        gen.quality_report = final_report

        db.session.commit()

        logger.info(f"[递进优化] 完成: generation_id={generation_id}, "
                    f"总轮次={opt_result.total_rounds}, "
                    f"分数={initial_score:.1f}→{opt_result.final_score:.1f}, "
                    f"提前停止={opt_result.stopped_early}")

        return jsonify({
            'success': True,
            'content': new_content,
            'quality_report': final_report,
            'message': opt_result.message,
            'total_rounds': opt_result.total_rounds,
            'final_score': opt_result.final_score,
            'first_score': initial_score,
            'stopped_early': opt_result.stopped_early,
            'round_history': round_history,
        })

    except Exception as e:
        logger.exception(f"[Optimize Error] generation_id={generation_id}: %s", e)
        return jsonify({
            'success': False,
            'message': f'优化失败: {str(e)}'
        }), 500


@public_bp.route('/api/content/<int:generation_id>/optimize/stream', methods=['GET'])
def api_optimize_content_stream(generation_id):
    """
    递进式优化内容质量（SSE流式版本）

    支持实时推送每轮优化进度到前端
    """
    from services.content_quality_optimizer import progressive_optimizer
    from services.content_quality_scorer import content_scorer
    import queue

    user_id = session.get('public_user_id')
    user = PublicUser.query.get(user_id) if user_id else None

    gen = PublicGeneration.query.filter_by(id=generation_id).first()
    if not gen:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    # 权限校验
    if user and gen.user_id and gen.user_id != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    content = gen.content_data or {}
    content_title = content.get('title') or (content.get('article') or {}).get('title') or ''
    if not content or not content_title:
        return jsonify({'success': False, 'message': '内容不存在，无法优化'}), 400

    brand_name = content.get('brand_name', '') or gen.industry or '品牌'

    business_desc = ''
    if gen.user_id:
        user_obj = PublicUser.query.get(gen.user_id)
        if user_obj and user_obj.profile:
            business_desc = user_obj.profile.business_description or ''

    # 获取首次分数（从已保存的报告中获取，保留首次优化前的原始分数）
    existing_report = gen.quality_report or {}
    first_score = existing_report.get('first_score') or gen.quality_score or 50.0
    # 获取首次分数（从已保存的报告中获取，保留首次优化前的原始分数）
    existing_report = gen.quality_report or {}
    first_score = existing_report.get('first_score') or gen.quality_score or 50.0
    initial_score = gen.quality_score or 50.0

    if initial_score >= 80:
        return jsonify({'success': False, 'message': '该内容分数已达80以上，无需继续优化'}), 400

    # 创建消息队列用于 SSE
    message_queue = queue.Queue()

    def progress_callback(event_type, data):
        """进度回调：将事件放入队列"""
        try:
            message = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            message_queue.put(message)
        except Exception:
            pass

    # 获取当前 app 实例，在线程中使用
    app = current_app._get_current_object()

    def run_optimization():
        """在新线程中执行优化"""
        # 在线程中使用获取的 app 实例创建上下文
        with app.app_context():
            try:
                # 重新查询 generation 记录，避免跨线程使用主请求线程中的 ORM 对象
                gen_thread = PublicGeneration.query.filter_by(id=generation_id).first()
                if not gen_thread:
                    logger.error(f"[递进优化-SSE] generation_id={generation_id} 在线程中未找到")
                    message_queue.put(f"event: error\ndata: {json.dumps({'success': False, 'message': '记录不存在'})}\n\n")
                    message_queue.put(None)
                    return

                # 重新评分获取失败项
                score_result = content_scorer.score(content, brand_name)
                failed_items = list(score_result.failed_items) if hasattr(score_result, 'failed_items') else []

                logger.info(f"[递进优化-SSE] generation_id={generation_id}, 初始分={initial_score:.1f}, "
                            f"不合格项={len(failed_items)}: {[f.name for f in failed_items]}")

                # 执行递进式优化（带进度回调）
                opt_result = progressive_optimizer.optimize(
                    content=content,
                    failed_items=failed_items,
                    initial_score=initial_score,
                    brand_name=brand_name,
                    business_desc=business_desc,
                    max_rounds=3,
                    progress_callback=progress_callback
                )

                # 更新数据库（使用线程内查询的 gen_thread 对象）
                new_content = opt_result.optimized_content or content
                gen_thread.content_data = new_content
                new_title = new_content.get('title') or (new_content.get('article') or {}).get('title') or ''
                gen_thread.titles = [new_title]
                gen_thread.tags = new_content.get('tags', [])

                # 构建最终报告
                final_report = opt_result.final_report
                if not final_report:
                    final_report = content_scorer.to_dict(score_result)

                final_report['optimized'] = True
                final_report['total_rounds'] = opt_result.total_rounds
                final_report['stopped_early'] = opt_result.stopped_early
                final_report['message'] = opt_result.message

                # 轮次历史（包含新字段：group_scope、rollback等）
                round_history = []
                for r in opt_result.round_history:
                    try:
                        round_history.append({
                            'round_num': r.round_num,
                            'group_key': r.group_key,
                            'group_label': r.group_label,
                            'group_scope': r.group_scope,
                            'items_in_round': r.items_in_round,
                            'items_fixed': r.items_fixed,
                            'score_before': r.score_before,
                            'score_after': r.score_after,
                            'rollback': r.rollback,
                            'stopped': r.stopped,
                            'message': r.message,
                        })
                    except Exception as e:
                        logger.warning(f"[递进优化-SSE] 轮次历史构建失败: {e}")
                        round_history.append({
                            'round_num': getattr(r, 'round_num', 0),
                            'group_key': getattr(r, 'group_key', ''),
                            'group_label': getattr(r, 'group_label', ''),
                            'score_before': getattr(r, 'score_before', 0),
                            'score_after': getattr(r, 'score_after', 0),
                            'message': getattr(r, 'message', ''),
                        })
                final_report['round_history'] = round_history
                final_report['rollback_count'] = opt_result.rollback_count

                logger.info(f"[递进优化-SSE] round_history 构建完成，共 {len(round_history)} 条记录")

                # 更新数据库
                gen_thread.quality_score = opt_result.final_score
                gen_thread.quality_report = final_report
                db.session.commit()
                
                logger.info(f"[递进优化-SSE] 数据库已更新: generation_id={generation_id}, quality_score={gen_thread.quality_score}, quality_report.optimized={final_report.get('optimized')}")

                # 发送最终结果
                final_data = {
                    'success': True,
                    'content': new_content,
                    'quality_report': final_report,
                    'message': opt_result.message,
                    'total_rounds': opt_result.total_rounds,
                    'rollback_count': opt_result.rollback_count,
                    'final_score': opt_result.final_score,
                    'first_score': initial_score,
                    'stopped_early': opt_result.stopped_early,
                    'round_history': round_history,
                }

                logger.info(f"[递进优化-SSE] final_report keys: {list(final_report.keys()) if final_report else 'None'}")
                logger.info(f"[递进优化-SSE] 准备发送 complete 事件，round_history 共 {len(round_history)} 轮")

                message_queue.put(f"event: complete\ndata: {json.dumps(final_data, ensure_ascii=False)}\n\n")

                logger.info(f"[递进优化-SSE] 完成: generation_id={generation_id}, "
                            f"总轮次={opt_result.total_rounds}, "
                            f"分数={initial_score:.1f}→{opt_result.final_score:.1f}")

            except Exception as e:
                logger.exception(f"[递进优化-SSE Error] generation_id={generation_id}: %s", e)
                error_data = {'success': False, 'message': f'优化失败: {str(e)}'}
                message_queue.put(f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n")
            finally:
                # 发送结束信号
                message_queue.put(None)

    # 启动优化线程
    thread = threading.Thread(target=run_optimization)
    thread.daemon = True
    thread.start()

    # 返回 SSE 响应
    def generate():
        # 发送初始连接成功消息
        yield f"event: connected\ndata: {json.dumps({'connected': True})}\n\n"

        while True:
            try:
                message = message_queue.get(timeout=120)
                if message is None:
                    break
                yield message
            except queue.Empty:
                # 超时发送心跳
                yield f": heartbeat\n\n"

    response = current_app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )
    return response


@public_bp.route('/api/content/generate-multi', methods=['POST'])
def api_generate_multi_version():
    """
    多版本生成：同一选题生成图文/短视频脚本/长文

    请求格式：
    {
        "topic_id": "1",
        "topic_title": "选题标题",
        "topic_type": "问题诊断",
        "business_description": "...",
        "business_range": "local/cross_region",
        "business_type": "...",
        "portrait": {...},
        "content_types": ["graphic", "short_video", "long_text"],  // 可选，默认全部
        "recommend": true  // 是否先推荐内容类型
    }
    """
    from services.content_generator import TopicContentGenerator
    from services.video_script_generator import VideoScriptGenerator
    from services.long_text_generator import LongTextGenerator
    from services.content_type_router import content_type_router
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

    # 确定要生成的内容类型
    content_types = params.get('content_types', ['graphic', 'short_video', 'long_text'])
    recommend_first = params.get('recommend', False)

    portrait = params.get('portrait', {})
    topic = {
        'title': params.get('topic_title', ''),
        'type': params.get('topic_type', ''),
        'content_direction': params.get('content_direction', '种草型')
    }

    # 如果需要推荐，先进行智能路由
    recommendation = None
    if recommend_first:
        business_info = {
            'content_direction': params.get('content_direction', '种草型'),
            'complexity': params.get('complexity', '中等复杂度'),
        }
        recommendation = content_type_router.route(topic, portrait, business_info)

    results = {}
    total_tokens = 0

    try:
        # 生成图文版本
        if 'graphic' in content_types:
            generator = TopicContentGenerator()
            graphic_result = generator.generate_content(
                topic_id=params.get('topic_id', ''),
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                business_description=params.get('business_description', ''),
                business_range=params.get('business_range', ''),
                business_type=params.get('business_type', ''),
                portrait=portrait,
                premium_plan=user.premium_plan if user else 'free'
            )
            if graphic_result.get('success'):
                results['graphic'] = graphic_result.get('content', {})
                total_tokens += graphic_result.get('tokens_used', 0)
            else:
                results['graphic'] = {'error': graphic_result.get('error', '生成失败')}

        # 生成短视频脚本
        if 'short_video' in content_types:
            video_generator = VideoScriptGenerator()
            video_result = video_generator.generate_content(
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                business_description=params.get('business_description', ''),
                portrait=portrait,
                content_style=params.get('content_style', '')
            )
            if video_result.get('success'):
                results['short_video'] = video_result.get('content', {})
                total_tokens += video_result.get('tokens_used', 0)
            else:
                results['short_video'] = {'error': video_result.get('error', '生成失败')}

        # 生成长文版本
        if 'long_text' in content_types:
            longtext_generator = LongTextGenerator()
            longtext_result = longtext_generator.generate_content(
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                business_description=params.get('business_description', ''),
                portrait=portrait,
                content_style=params.get('content_style', '')
            )
            if longtext_result.get('success'):
                results['long_text'] = longtext_result.get('content', {})
                total_tokens += longtext_result.get('tokens_used', 0)
            else:
                results['long_text'] = {'error': longtext_result.get('error', '生成失败')}

        # 保存生成记录
        if user:
            generation = PublicGeneration(
                user_id=user.id,
                industry=params.get('business_type', ''),
                target_customer=portrait.get('identity', ''),
                content_type='multi_version',
                titles=','.join([params.get('topic_title', '')]),
                tags=','.join(content_types),
                content=json.dumps(results, ensure_ascii=False),
                used_tokens=total_tokens,
                topic_id=params.get('topic_id', '') or None,
                portrait_id=params.get('portrait_id'),
                problem_id=params.get('problem_id'),
                # ── 星系增强：保存客户选择的场景组合 ──
                selected_scenes=effective_scene,
            )
            db.session.add(generation)
            # 扣减配额
            quota_manager.use_quota(user, total_tokens)
            db.session.commit()

        return jsonify({
            'success': True,
            'results': results,
            'total_tokens': total_tokens,
            'recommendation': recommendation
        })

    except Exception as e:
        logger.exception("[MultiVersionGenerator Error] %s", e)
        return jsonify({
            'success': False,
            'message': f'多版本生成失败: {str(e)}'
        }), 500


@public_bp.route('/api/content/route', methods=['POST'])
def api_content_route():
    """
    智能路由：根据选题+画像推荐最佳内容类型

    请求格式：
    {
        "topic": {
            "title": "选题标题",
            "type": "避坑指南",
            "content_direction": "种草型"
        },
        "portrait": {...},
        "business_info": {
            "complexity": "中等复杂度",
            "visual_needs": "需要展示效果"
        }
    }
    """
    from services.content_type_router import content_type_router

    params = request.get_json() or {}

    topic = params.get('topic', {})
    portrait = params.get('portrait', {})
    business_info = params.get('business_info', {})

    if not topic.get('title'):
        return jsonify({'success': False, 'message': '请提供选题信息'}), 400

    try:
        result = content_type_router.route(topic, portrait, business_info)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.exception("[ContentRoute Error] %s", e)
        return jsonify({
            'success': False,
            'message': f'路由分析失败: {str(e)}'
        }), 500


@public_bp.route('/api/content/structures', methods=['GET'])
def api_get_content_structures():
    """
    获取所有内容类型和结构
    """
    from services.content_generator import TopicContentGenerator
    from services.video_script_generator import VideoScriptGenerator
    from services.long_text_generator import LongTextGenerator

    graphic_gen = TopicContentGenerator()
    video_gen = VideoScriptGenerator()
    longtext_gen = LongTextGenerator()

    return jsonify({
        'success': True,
        'data': {
            'graphic': {
                'name': '图文',
                'icon': '🖼️',
                'description': '适合展示对比、步骤、清单类内容，用户可快速浏览和收藏',
                'structures': graphic_gen.get_all_structures()
            },
            'short_video': {
                'name': '短视频',
                'icon': '🎬',
                'description': '适合故事讲述、场景演示，真人出镜，内容生动直观',
                'structures': video_gen.get_structures()
            },
            'long_text': {
                'name': '长文',
                'icon': '📝',
                'description': '适合深度分析，专业知识讲解，需要用户静下心来阅读',
                'structures': longtext_gen.get_templates()
            }
        }
    })


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
                   selected_problem_id, selected_portrait_index, opp_portraits_data, created_at, updated_at
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
    for field in ['form_data', 'problems_data', 'portraits_data', 'opp_portraits_data']:
        if row_dict.get(field):
            try:
                row_dict[field] = json.loads(row_dict[field])
            except Exception:
                pass

    return jsonify({'success': True, 'snapshot': row_dict})


@public_bp.route('/api/snapshots/current', methods=['DELETE'])
def api_delete_current_snapshot():
    """
    删除当前用户的最新超级定位快照（用于手动刷新页面时清空状态）

    DELETE /public/api/snapshots/current
    """
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    db.session.execute(
        db.text("DELETE FROM super_snapshots WHERE user_id = :user_id"),
        {'user_id': user.id}
    )
    db.session.commit()
    return jsonify({'success': True})


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
    opp_portraits_data = params.get('opp_portraits_data', {})

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
                    opp_portraits_data = :opp_portraits_data,
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
                'opp_portraits_data': json.dumps(opp_portraits_data, ensure_ascii=False),
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
                     selected_problem_id, selected_portrait_index, opp_portraits_data, created_at, updated_at)
                VALUES
                    (:uid, :sid, 1, :form_data, :problems_data, :portraits_data,
                     :selected_problem_id, :selected_portrait_index, :opp_portraits_data, :now, :now)
            """),
            {
                'uid': user.id,
                'sid': session_id,
                'form_data': json.dumps(form_data, ensure_ascii=False),
                'problems_data': json.dumps(problems_data, ensure_ascii=False),
                'portraits_data': json.dumps(portraits_data, ensure_ascii=False),
                'selected_problem_id': selected_problem_id,
                'selected_portrait_index': selected_portrait_index,
                'opp_portraits_data': json.dumps(opp_portraits_data, ensure_ascii=False),
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
# 超级定位 - 一键分析 API
# =============================================================================

@public_bp.route('/api/super-position/analyze', methods=['POST'])
def api_super_position_analyze():
    """
    超级定位一键分析 API

    流程：市场蓝海分析 → 关键词库生成 → 画像生成

    POST /public/api/super-position/analyze
    Body: {
        business_description: str,    # 业务描述（必填）
        industry: str,                # 行业（可选，自动推断）
        business_type: str,           # 业务类型 product/service
        service_scenario: str,        # 服务场景
        portraits_per_type: int,      # 每个问题类型生成画像数（默认3）
    }

    返回: {
        success: bool,
        data: {
            market_analysis: {...},       # 市场分析结果
            keyword_library: {...},         # 关键词库
            problem_types: [...],          # 问题类型列表
            portraits: [...],              # 画像列表（按问题类型分组）
            portraits_by_type: {...},      # 按问题类型分组的画像
        }
    }
    """
    import traceback as tb_module
    from services.market_analyzer import MarketAnalyzer
    from services.portrait_generator import (
        PortraitGenerator,
        PortraitGenerationContext,
        group_portraits_by_problem_type,
    )

    logger = logging.getLogger(__name__)

    # 获取请求数据
    data = request.get_json() or {}

    business_description = data.get('business_description', '').strip()
    if not business_description:
        return jsonify({
            'success': False,
            'message': '请输入业务描述'
        }), 400

    # 参数提取
    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    service_scenario = data.get('service_scenario', 'other')
    portraits_per_type = data.get('portraits_per_type', 3)

    # 构建业务信息
    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
        'service_scenario': service_scenario,
        'keywords': data.get('keywords', []),
    }

    logger.info(f"[api_super_position_analyze] 开始分析: {business_description[:50]}")

    try:
        # Step 1: 市场蓝海分析 + 关键词库生成
        analyzer = MarketAnalyzer()
        analysis_result = analyzer.analyze(
            business_info=business_info,
            max_opportunities=5,
            max_keywords=200,
        )

        if not analysis_result.success:
            return jsonify({
                'success': False,
                'message': f"市场分析失败: {analysis_result.error_message}"
            }), 500

        # Step 2: 画像生成（基于关键词库）
        generator = PortraitGenerator()

        # 转换数据格式
        keyword_library = analysis_result.keyword_library or {}

        # 从蓝海机会中提取问题类型和场景
        market_opportunities = []

        for o in analysis_result.market_opportunities:
            opp_dict = {
                'opportunity_name': o.opportunity_name,
                'target_audience': o.target_audience,
                'pain_points': o.pain_points,
                'keywords': o.keywords,
                'content_direction': o.content_direction,
                'market_type': o.market_type,
                'confidence': o.confidence,
                'differentiation': getattr(o, 'differentiation', ''),
                'problem_types': [],
            }

            # 转换 ProblemType 对象 → dict（scenes 现在是 List[Dict]）
            problem_types_for_opp = []
            for pt in o.problem_types:
                pt_dict = {
                    'name': pt.name,
                    'description': pt.description,
                    'keywords': pt.keywords,
                    'scenes': pt.scenes,  # 已是 List[Dict]
                    'target_audience': getattr(pt, 'target_audience', ''),
                    'category': getattr(pt, 'category', ''),
                }
                problem_types_for_opp.append(pt_dict)

            opp_dict['problem_types'] = problem_types_for_opp
            market_opportunities.append(opp_dict)

        # ── 合并所有蓝海机会的问题类型并去重 ────────────────────────
        # 修复：之前只用第一个机会，现在用所有机会
        all_problem_types = []   # 全量（含重复，用于画像生成）
        unique_problem_types = []  # 去重（用于前端展示）
        seen_pt_keys = set()  # (name, category) 去重键

        for opp_dict in market_opportunities:
            for pt in opp_dict.get('problem_types', []):
                all_problem_types.append(pt)
                key = (pt.get('name', ''), pt.get('category', ''))
                if key not in seen_pt_keys:
                    seen_pt_keys.add(key)
                    unique_problem_types.append(pt)

        # 构建画像生成上下文 — 使用所有机会的问题类型
        context = PortraitGenerationContext(
            keyword_library=keyword_library,
            problem_types=[],  # 已合并到 selected_opportunity 中
            business_info=business_info,
            market_opportunities=market_opportunities,
            selected_opportunity={},  # 清空，使用 all_problem_types
            problem_scenes=[
                {'scene_name': scene['name'], '_problem_type_name': pt['name'], '_category': pt.get('category', '')}
                for pt in all_problem_types
                for scene in pt.get('scenes', [])
            ],  # 所有机会的所有场景
            portraits_per_type=portraits_per_type,
        )

        # 生成画像
        portraits = generator.generate_portraits(context)

        # 转换画像为字典格式
        portraits_data = [
            {
                'portrait_id': p.portrait_id,
                'problem_type': p.problem_type,
                'problem_type_description': p.problem_type_description,
                'identity': p.identity,
                'identity_description': p.identity_description,
                'portrait_summary': p.portrait_summary,
                'pain_points': p.pain_points,
                'pain_scenarios': p.pain_scenarios,
                'psychology': p.psychology,
                'barriers': p.barriers,
                'search_keywords': p.search_keywords,
                'content_preferences': p.content_preferences,
                'market_type': p.market_type,
                'differentiation': p.differentiation,
                'scene_tags': p.scene_tags,
                'behavior_tags': p.behavior_tags,
                'content_direction': p.content_direction,
            }
            for p in portraits
        ]

        # 按问题类型分组（使用字典列表）
        portraits_by_type = group_portraits_by_problem_type(portraits_data)

        # 统计信息
        blue_ocean_count = analysis_result.blue_ocean_keywords
        red_ocean_count = analysis_result.red_ocean_keywords

        logger.info(
            f"[api_super_position_analyze] 分析完成: "
            f"蓝海机会={len(market_opportunities)}, 唯一问题类型={len(unique_problem_types)}, "
            f"全量问题类型(含重复)={len(all_problem_types)}, 画像={len(portraits_data)}, "
            f"蓝海词={blue_ocean_count}, 红海词={red_ocean_count}"
        )

        return jsonify({
            'success': True,
            'data': {
                'market_analysis': {
                    'opportunities': market_opportunities,
                    'subdivision_insights': analysis_result.subdivision_insights,
                    'keyword_stats': {
                        'total': analysis_result.total_keywords,
                        'blue_ocean': blue_ocean_count,
                        'red_ocean': red_ocean_count,
                        'blue_ratio': blue_ocean_count / max(analysis_result.total_keywords, 1),
                    },
                },
                'keyword_library': keyword_library,
                'problem_types': unique_problem_types,  # 修复：返回从所有蓝海机会提取并去重的问题类型
                'portraits': portraits_data,
                'portraits_by_type': portraits_by_type,
            }
        })

    except Exception as e:
        logger.error(f"[api_super_position_analyze] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'分析异常: {str(e)}'
        }), 500


# =============================================================================
# Skill Bridge 结果适配器
# 将 SkillBridge 的 JSON 配置驱动输出，适配成旧 Service 的返回格式，
# 确保前端拿到的是完全一致的数据结构，实现无感知切换。
# =============================================================================

def _adapt_market_analyzer_result(bridge_result) -> dict:
    """
    将 SkillBridge execute_market_analyzer 的结果适配成旧 MarketAnalyzer.analyze() 的格式。
    SkillBridge 输出：{step1_industry_overview, step2_blue_ocean, step3_audience_segment, ...}
    旧 API 期望：{market_opportunities, subdivision_insights, keyword_stats}
    """
    fo = bridge_result.full_output
    opportunities = []
    keyword_stats = {}

    # step2_blue_ocean → market_opportunities
    step2 = fo.get('step2_blue_ocean', {})
    blue_opps = step2.get('blue_ocean_opportunities', [])
    for i, opp in enumerate(blue_opps):
        opportunities.append({
            'opportunity_name': opp.get('direction', f'蓝海机会{i+1}'),
            'target_audience': opp.get('direction', ''),
            'pain_points': [],
            'keywords': [],
            'content_direction': '',
            'market_type': 'blue_ocean',
            'confidence': 0.8,
            'differentiation': opp.get('why_blue_ocean', ''),
            'logic_chain': '',
            'problem_types': [],
        })

    # step3_audience_segment → subdivision_insights
    step3 = fo.get('step3_audience_segment', {})
    subdivision_insights = {
        'paying_user': step3.get('paying_user', {}),
        'using_user': step3.get('using_user', {}),
        'paying_equals_using': step3.get('paying_equals_using', True),
        'audience_priority': step3.get('audience_priority', []),
        'separation_point': step3.get('separation_point', ''),
    }

    # step1_industry_overview → keyword_stats
    step1 = fo.get('step1_industry_overview', {})
    keyword_stats = {
        'market_size': step1.get('market_size', ''),
        'growth_rate': step1.get('growth_rate', ''),
        'market_structure': step1.get('market_structure', ''),
        'key_players': step1.get('key_players', []),
        'seasonal_features': step1.get('seasonal_features', ''),
        'product_type': step1.get('product_type', ''),
        'barriers_to_entry': step1.get('barriers_to_entry', ''),
    }

    return {
        'market_opportunities': opportunities,
        'subdivision_insights': subdivision_insights,
        'keyword_stats': keyword_stats,
    }


def _adapt_keyword_library_result(bridge_result) -> dict:
    """
    将 SkillBridge execute_keyword_library 的结果适配成旧 KeywordLibraryGenerator 的格式。
    SkillBridge 输出：{bc_separation_analysis, b2b_keywords, b2c_keywords, blue_ocean_matrix, ...}
    旧 API 期望：{keyword_library, problem_types, portrait_keywords, keyword_stats}
    """
    fo = bridge_result.full_output

    # 收集所有关键词
    all_kw = []
    for step_key in ['bc_separation_analysis', 'b2b_keywords', 'b2c_keywords',
                     'blue_ocean_matrix', 'upstream_downstream_keywords', 'keyword_library_summary']:
        step_data = fo.get(step_key, {})
        if isinstance(step_data, dict):
            for v in step_data.values():
                if isinstance(v, list):
                    all_kw.extend(v)
        elif isinstance(step_data, list):
            all_kw.extend(step_data)

    # 适配 keyword_library 格式
    kw_lib = {
        'problem_type_keywords': [],
        'pain_point_keywords': [],
        'scene_keywords': [],
        'concern_keywords': [],
        'direct_demand_keywords': [],
    }

    blue_matrix = fo.get('blue_ocean_matrix', {})
    if isinstance(blue_matrix, dict):
        for layer, kws in blue_matrix.items():
            if isinstance(kws, list):
                if layer == 'L1_core':
                    kw_lib['problem_type_keywords'].extend(kws)
                elif layer == 'L2_long_tail':
                    kw_lib['pain_point_keywords'].extend(kws)
                elif layer == 'L3_regional':
                    kw_lib['scene_keywords'].extend(kws)
                elif layer == 'L4_seasonal':
                    kw_lib['direct_demand_keywords'].extend(kws)

    b2c = fo.get('b2c_keywords', {})
    if isinstance(b2c, dict):
        for kws in b2c.values():
            if isinstance(kws, list):
                kw_lib['concern_keywords'].extend(kws)

    # keyword_stats
    summary = fo.get('keyword_library_summary', {})
    if isinstance(summary, dict):
        kw_stats = summary.get('summary', {}) if isinstance(summary.get('summary'), dict) else summary
    else:
        kw_stats = {}

    keyword_stats = {
        'total': kw_stats.get('total_count', len(all_kw)),
        'common': kw_stats.get('b2c_count', 0),
        'portrait': kw_stats.get('b2b_count', 0),
        'blue_ocean': len(kw_lib.get('pain_point_keywords', [])),
        'red_ocean': len(kw_lib.get('problem_type_keywords', [])),
    }

    return {
        'keyword_library': kw_lib,
        'problem_types': [],
        'portrait_keywords': [],
        'keyword_stats': keyword_stats,
    }


def _build_geo_report(bridge_full_output: dict) -> dict:
    """
    将 SkillBridge content_generator 的输出适配成旧 quality_report 格式。
    注意：full_output 的 key 是 step_id（如 step_final_output），不是字段名。
    根据日志，quality_score 和 grade 在 step_final_output 中。
    """
    # quality_score 和 grade 来自 step_final_output
    step_final = bridge_full_output.get('step_final_output', {})
    # 处理 LLM 有时多包一层 {"final_output": {...}}，或降级返回 list
    if isinstance(step_final, list):
        step_final = {}
    elif isinstance(step_final, dict) and 'final_output' in step_final and len(step_final) == 1:
        step_final = step_final['final_output']
    if not isinstance(step_final, dict):
        step_final = {}
    quality_score_raw = step_final.get('quality_score', 0)
    try:
        quality_score = int(float(quality_score_raw)) if quality_score_raw else 0
    except (ValueError, TypeError):
        quality_score = 0

    grade = step_final.get('grade', 'D')
    if quality_score >= 90:
        grade = 'A'
    elif quality_score >= 80:
        grade = 'B'
    elif quality_score >= 70:
        grade = 'C'
    elif quality_score >= 60:
        grade = 'D'
    else:
        grade = 'F'

    # 维度评分项：来自 step_quality_validate
    items = []
    failed_items = []
    qv_wrapper = bridge_full_output.get('step_quality_validate', {})
    qv = qv_wrapper.get('quality_validation', qv_wrapper) if isinstance(qv_wrapper, dict) else {}
    ds = qv.get('dimension_scores', {}) if isinstance(qv, dict) else {}
    for dim, score_info in ds.items():
        if isinstance(score_info, dict):
            score_raw = score_info.get('score', 10)
            try:
                score_val = int(float(score_raw)) if score_raw else 0
            except (ValueError, TypeError):
                score_val = 0
            passed_raw = score_info.get('passed')
            if passed_raw is None:
                passed = score_val >= 8
            else:
                passed = bool(passed_raw)
            items.append({
                'dimension': dim,
                'score': score_val,
                'passed': passed,
            })
            if not passed:
                failed_items.append(dim)

    return {
        'total_score': quality_score,
        'grade': grade,
        'items': items,
        'failed_items': failed_items,
        'summary': '',
    }


def _safe_get(data: dict, key: str, default=None):
    """安全获取嵌套字段，支持 key.key2.key3 格式"""
    if not isinstance(data, dict):
        return default
    parts = key.split('.')
    val = data
    for p in parts:
        if not isinstance(val, dict):
            return default
        val = val.get(p)
    return val if val is not None else default


def _build_extension_from_slides(slides: list, geo_mode: str = '') -> str:
    """
    根据 slides 数据生成内容延伸建议区块文本。
    参考 content_generator.py 的 _slides_to_extension 实现。
    """
    if not slides:
        return ''

    lines = []
    lines.append('## 内容延伸建议')
    lines.append('')
    lines.append('### 系列化选题')
    lines.append('')
    lines.append('> 可围绕同一主题，从不同角度或不同受众切入，形成系列化内容')
    lines.append('')
    lines.append('| 系列名称 | 说明 |')
    lines.append('| --- | --- |')
    lines.append('| 入门指南 | 从零开始的基础教程 |')
    lines.append('| 进阶技巧 | 深入讲解核心知识点 |')
    lines.append('| 避坑指南 | 常见误区和解决方案 |')
    lines.append('')

    # 生成延伸选题
    lines.append('### 延伸选题')
    lines.append('')
    lines.append('| 序号 | 类型 | 选题方向 | 目的 |')
    lines.append('| --- | --- | --- | --- |')

    topics = [
        (1, '对比型', 'XX vs XX：哪个更适合你？', '帮助选择'),
        (2, '实操型', '手把手教你XX（详细步骤）', '提升实用性'),
        (3, '案例型', '真实案例：XX是如何做到的', '增强信任'),
        (4, '科普型', '关于XX，你可能不知道的事', '拓展认知'),
    ]

    for seq, t_type, t_title, t_purpose in topics:
        lines.append(f'| {seq} | {t_type} | {t_title} | {t_purpose} |')

    return '\n'.join(lines)


def _build_content_data_from_bridge(fo: dict) -> dict:
    """
    重构版内容数据构建器 —— 单一可信来源。

    数据源优先级：
    1. step_generate_content：核心图文内容（slides, title, tags 等）
    2. step_quality_validate：质量评分
    3. step_geo_mode_match：GEO模式信息

    字段名统一映射：
      - content_plan   ← publish_strategy（来自 step_generate_content）
      - comment        ← first_comment
      - publish        ← publish_strategy
      - first_comment ← first_comment

    不再依赖 step_final_output，因为它的 LLM 输出格式不稳定。
    """
    gen = fo.get('step_generate_content', {}) or {}
    qv = fo.get('step_quality_validate', {}) or {}
    geo = fo.get('step_geo_mode_match', {}) or {}

    # 质量评分（来自 step_quality_validate）
    qv_inner = qv.get('quality_validation', {}) if isinstance(qv, dict) else {}
    if isinstance(qv, dict) and 'quality_validation' not in qv and isinstance(qv, dict):
        qv_inner = qv  # 直接就是评分对象（降级情况）
    qs_raw = _safe_get(qv_inner, 'quality_score', 0)
    try:
        quality_score = int(float(qs_raw)) if qs_raw else 0
    except (ValueError, TypeError):
        quality_score = 0

    # 维度评分项
    items = []
    failed_items = []
    ds = _safe_get(qv_inner, 'dimension_scores', {}) or {}
    for dim, score_info in (ds.items() if isinstance(ds, dict) else []):
        if isinstance(score_info, dict):
            sr = score_info.get('score', 10)
            try:
                sv = int(float(sr)) if sr else 0
            except (ValueError, TypeError):
                sv = 0
            pr = score_info.get('passed')
            passed = bool(pr) if pr is not None else sv >= 8
            items.append({'dimension': dim, 'score': sv, 'passed': passed})
            if not passed:
                failed_items.append(dim)

    # 评分等级
    grade = 'F'
    if quality_score >= 90:
        grade = 'A'
    elif quality_score >= 80:
        grade = 'B'
    elif quality_score >= 70:
        grade = 'C'
    elif quality_score >= 60:
        grade = 'D'

    # 断言：检查数据完整性
    if not gen:
        logger.error(f"[ContentData] step_generate_content 输出为空! "
                     f"full_output keys={list(fo.keys())}, "
                     f"raw_preview={str(fo)[:300]}")
    missing = [f for f in ['slides', 'title'] if not gen.get(f)]
    if missing:
        logger.warning(f"[ContentData] 数据丢失: {missing}, gen_keys={list(gen.keys())}, "
                       f"raw_output_preview={str(fo.get('step_generate_content', {}))[:200]}")

    # 副标题（从 gen 取，兼容 subtitle/subtitle_text）
    subtitle = _safe_get(gen, 'subtitle') or _safe_get(gen, 'subtitle_text') or ''

    # 兜底：字段名变体兼容
    # LLM 可能返回 main_title / tag_list / content 等变体
    # 兼容两种格式：1) content 是 dict 列表  2) content 是 JSON 字符串列表
    content_val = gen.get('content')
    if not gen.get('slides') and content_val and isinstance(content_val, list):
        # 尝试解析 content 中的每一项（可能是 JSON 字符串）
        parsed_slides = []
        any_parsed = False
        for item in content_val:
            if isinstance(item, dict):
                parsed_slides.append(item)
                any_parsed = True
            elif isinstance(item, str):
                # 尝试将字符串解析为 JSON
                try:
                    import json as _json
                    parsed = _json.loads(item)
                    if isinstance(parsed, dict):
                        parsed_slides.append(parsed)
                        any_parsed = True
                    else:
                        # 字符串是有效 JSON 但不是对象，保留原值
                        parsed_slides.append(item)
                except Exception:
                    # 字符串不是 JSON，保留原值
                    parsed_slides.append(item)
        # 只要有任何一个成功解析为 dict，就使用解析结果
        if any_parsed:
            gen['slides'] = parsed_slides

    # 标题（优先从 gen 取，兜底变体）
    title = gen.get('title') or ''
    if not title:
        title = _safe_get(gen, 'main_title') or _safe_get(gen, 'basic.title') or ''

    # 标签
    tags = _safe_get(gen, 'tags') or _safe_get(gen, 'tag_list') or []

    # 话题标签
    hashtags = _safe_get(gen, 'hashtags') or []

    # 发布策略相关字段（统一映射到 section_key 名称）
    _publish_strategy = _safe_get(gen, 'publish_strategy') or ''
    _first_comment = _safe_get(gen, 'first_comment') or ''
    content_plan = _safe_get(gen, 'content_plan') or _publish_strategy
    comment = _safe_get(gen, 'comment') or _first_comment
    publish = _safe_get(gen, 'publish') or _publish_strategy

    # slides：使用 gen['slides']（已包含 content 解析结果）
    # 如果 slides 是 dict 列表，直接使用；否则降级
    gen_slides = gen.get('slides', [])
    if isinstance(gen_slides, list) and gen_slides:
        # 检查是否有任何 dict 项（优先使用 dict）
        dict_items = [s for s in gen_slides if isinstance(s, dict)]
        str_items = [s for s in gen_slides if isinstance(s, str)]
        if dict_items:
            slides = dict_items
            if str_items:
                logger.warning(f"[ContentData] slides 混有 {len(str_items)} 个非 dict 项，已过滤")
        else:
            # 全是字符串，降级为空并记录
            slides = []
            logger.warning(
                f"[ContentData] slides 不是 dict 列表（是字符串列表，长度={len(str_items)}），"
                f"无法解析，slides 置空"
            )
    else:
        slides = []

    # trust_evidence
    trust_evidence = _safe_get(gen, 'trust_evidence') or []

    # cta
    cta = _safe_get(gen, 'cta') or ''

    # GEO 模式
    geo_mode = _safe_get(gen, 'geo_mode') or _safe_get(geo, 'geo_mode') or ''

    # [DEBUG] 验证 subtitle 字段状态
    slides_type = 'dict_list' if slides else 'empty'
    logger.info(f"[ContentData] subtitle={subtitle!r}, title={title!r}, hashtags_count={len(hashtags)}, slides_count={len(slides)}, slides_type={slides_type}")

    return {
        # 内容数据（保存到 content_data 字段）
        'content_data': {
            'structure': _safe_get(gen, 'structure') or '',
            'geo_mode': geo_mode,
            'slides_count': len(slides),
            'title': title,
            'subtitle': subtitle,
            'tags': tags,
            'slides': slides,
            'hashtags': hashtags,
            'first_comment': _first_comment,
            'publish_strategy': _publish_strategy,
            'content_plan': content_plan,
            'comment': comment,
            'publish': publish,
            'color_scheme': _safe_get(gen, 'color_scheme') or [],
            'production_specs': _safe_get(gen, 'production_specs') or '',
            'seo_keywords': _safe_get(gen, 'seo_keywords') or {},
            'cover_suggestion': _safe_get(gen, 'cover_suggestion') or {},
            'opening': _safe_get(gen, 'opening') or '',
            'trust_evidence': trust_evidence,
            'cta': cta,
            # 区块内容（从前端区块服务获取）
            'extension': _safe_get(gen, 'extension') or _build_extension_from_slides(slides, geo_mode),
            'basic_info': _safe_get(gen, 'basic_info') or '',
            'compliance': _safe_get(gen, 'compliance') or '',
        },
        # 质量报告
        'quality_score': quality_score,
        'quality_report': {
            'total_score': quality_score,
            'grade': grade,
            'grade_label': '',
            'passed': quality_score >= 80,
            'optimized': False,
            'first_score': quality_score,
            'final_score': quality_score,
            'optimized_items': [],
            'items': items,
            'summary': '',
            'suggestions': [],
            'failed_items': failed_items,
            'need_optimize': quality_score < 80,
        },
        # GEO 评分报告（兼容旧代码）
        'geo_report': {
            'total_score': quality_score,
            'grade': grade,
            'items': items,
            'failed_items': failed_items,
            'summary': '',
        },
        # 提取的字段（用于保存到 generation 表）
        'extracted_title': title,
        'extracted_tags': tags or hashtags,
        'extracted_geo': geo_mode,
        'slides_count': len(slides),
    }


def _build_video_script_data_from_bridge(fo: dict) -> dict:
    """
    从 SkillBridge video_script_generator 的输出构建内容数据。

    数据源优先级：
    1. step_generate_content：核心脚本内容（scenes, title, structure_name 等）
    2. step_quality_validate：质量评分
    3. step_geo_mode_match：GEO模式和结构信息
    """
    gen = fo.get('step_generate_content', {}) or {}
    qv = fo.get('step_quality_validate', {}) or {}
    geo = fo.get('step_geo_mode_match', {}) or {}

    # 质量评分
    qv_inner = qv.get('quality_validation', {}) if isinstance(qv, dict) else {}
    if isinstance(qv, dict) and 'quality_validation' not in qv:
        qv_inner = qv
    qs_raw = _safe_get(qv_inner, 'quality_score', 0)
    try:
        quality_score = int(float(qs_raw)) if qs_raw else 0
    except (ValueError, TypeError):
        quality_score = 0

    # 维度评分项
    items = []
    failed_items = []
    ds = _safe_get(qv_inner, 'dimension_scores', {}) or {}
    for dim, score_info in (ds.items() if isinstance(ds, dict) else []):
        if isinstance(score_info, dict):
            sr = score_info.get('score', 10)
            try:
                sv = int(float(sr)) if sr else 0
            except (ValueError, TypeError):
                sv = 0
            pr = score_info.get('passed')
            passed = bool(pr) if pr is not None else sv >= 8
            items.append({'dimension': dim, 'score': sv, 'passed': passed})
            if not passed:
                failed_items.append(dim)

    # 评分等级
    grade = 'F'
    if quality_score >= 90:
        grade = 'A'
    elif quality_score >= 80:
        grade = 'B'
    elif quality_score >= 70:
        grade = 'C'
    elif quality_score >= 60:
        grade = 'D'

    # 标题
    title = _safe_get(gen, 'title') or ''
    # 标签
    tags = _safe_get(gen, 'tags') or []
    hashtags = _safe_get(gen, 'hashtags') or []
    # scenes
    scenes = _safe_get(gen, 'scenes') or []
    # 结构
    structure_name = _safe_get(gen, 'structure_name') or _safe_get(gen, 'structure') or ''
    # trust_evidence
    trust_evidence = _safe_get(gen, 'trust_evidence') or []
    # cta
    cta = _safe_get(gen, 'cta') or ''
    # GEO 模式
    geo_mode = _safe_get(gen, 'geo_mode') or _safe_get(geo, 'geo_mode') or ''

    return {
        'content_data': {
            'structure': _safe_get(gen, 'structure') or '',
            'structure_name': structure_name,
            'geo_mode': geo_mode,
            'scenes_count': len(scenes),
            'title': title,
            'subtitle': '',
            'tags': tags,
            'scenes': scenes,
            'hashtags': hashtags,
            'duration': _safe_get(gen, 'duration') or '',
            'aspect_ratio': _safe_get(gen, 'aspect_ratio') or '9:16',
            'opening': _safe_get(gen, 'opening') or '',
            'first_comment': _safe_get(gen, 'first_comment') or '',
            'publish_strategy': _safe_get(gen, 'publish_strategy') or '',
            'bgm_suggestion': _safe_get(gen, 'bgm_suggestion') or '',
            'shooting_tips': _safe_get(gen, 'shooting_tips') or '',
            'visual_report': _safe_get(gen, 'visual_report') or {},
            'trust_evidence': trust_evidence,
            'cta': cta,
        },
        'quality_score': quality_score,
        'quality_report': {
            'total_score': quality_score,
            'grade': grade,
            'grade_label': '',
            'passed': quality_score >= 80,
            'optimized': False,
            'first_score': quality_score,
            'final_score': quality_score,
            'optimized_items': [],
            'items': items,
            'summary': '',
            'suggestions': [],
            'failed_items': failed_items,
            'need_optimize': quality_score < 80,
        },
        'geo_report': {
            'total_score': quality_score,
            'grade': grade,
            'items': items,
            'failed_items': failed_items,
            'summary': '',
        },
        'extracted_title': title,
        'extracted_tags': tags or hashtags,
        'extracted_geo': geo_mode,
        'scenes_count': len(scenes),
    }


def _build_long_text_data_from_bridge(fo: dict) -> dict:
    """
    从 SkillBridge long_text_generator 的输出构建内容数据。

    数据源优先级：
    1. step_generate_content：核心长文内容（sections, title, structure_name 等）
    2. step_quality_validate：质量评分
    3. step_geo_mode_match：GEO模式和模板信息
    """
    gen = fo.get('step_generate_content', {}) or {}
    qv = fo.get('step_quality_validate', {}) or {}
    geo = fo.get('step_geo_mode_match', {}) or {}

    # 质量评分
    qv_inner = qv.get('quality_validation', {}) if isinstance(qv, dict) else {}
    if isinstance(qv, dict) and 'quality_validation' not in qv:
        qv_inner = qv
    qs_raw = _safe_get(qv_inner, 'quality_score', 0)
    try:
        quality_score = int(float(qs_raw)) if qs_raw else 0
    except (ValueError, TypeError):
        quality_score = 0

    # 维度评分项
    items = []
    failed_items = []
    ds = _safe_get(qv_inner, 'dimension_scores', {}) or {}
    for dim, score_info in (ds.items() if isinstance(ds, dict) else []):
        if isinstance(score_info, dict):
            sr = score_info.get('score', 10)
            try:
                sv = int(float(sr)) if sr else 0
            except (ValueError, TypeError):
                sv = 0
            pr = score_info.get('passed')
            passed = bool(pr) if pr is not None else sv >= 8
            items.append({'dimension': dim, 'score': sv, 'passed': passed})
            if not passed:
                failed_items.append(dim)

    # 评分等级
    grade = 'F'
    if quality_score >= 90:
        grade = 'A'
    elif quality_score >= 80:
        grade = 'B'
    elif quality_score >= 70:
        grade = 'C'
    elif quality_score >= 60:
        grade = 'D'

    # 标题
    title = _safe_get(gen, 'title') or ''
    subtitle = _safe_get(gen, 'subtitle') or ''
    # 标签
    tags = _safe_get(gen, 'tags') or []
    hashtags = _safe_get(gen, 'hashtags') or []
    # sections
    sections = _safe_get(gen, 'sections') or []
    # 结构
    structure_name = _safe_get(gen, 'structure_name') or _safe_get(gen, 'structure') or ''
    # trust_evidence
    trust_evidence = _safe_get(gen, 'trust_evidence') or []
    # cta
    cta = _safe_get(gen, 'cta') or ''
    # opening_hooks
    opening_hooks = _safe_get(gen, 'opening_hooks') or ''
    # summary
    summary = _safe_get(gen, 'summary') or ''
    # reading_report
    reading_report = _safe_get(gen, 'reading_report') or {}
    # GEO 模式
    geo_mode = _safe_get(gen, 'geo_mode') or _safe_get(geo, 'geo_mode') or ''

    # ── 4维度方法论字段 ──
    visual_identity = _safe_get(gen, 'visual_identity') or {}
    four_dimension_summary = _safe_get(gen, 'four_dimension_summary') or {}
    # 4维度推荐（来自GEO步骤）
    four_dimension_guide = _safe_get(geo, 'four_dimension_guide') or {}

    # 每个章节的4维度信息（从sections中提取用于汇总）
    section_4d_summary = []
    for sec in sections:
        # 新格式：design_reference 嵌套对象
        dr = sec.get('design_reference', {}) or {}
        gq = dr.get('golden_quote_block', {}) or {}
        section_4d_summary.append({
            'section_index': sec.get('section_index', 0),
            'section_name': sec.get('section_name', ''),
            'article_content': sec.get('article_content') or sec.get('content') or '',
            'open_hook': sec.get('open_hook', ''),
            'emotion_phase': dr.get('emotion_phase', ''),
            'layout_type': dr.get('layout_type', ''),
            'color_tone': dr.get('color_tone', ''),
            'ui_components': dr.get('ui_components', []),
            'golden_quote_block': gq,
            'information_modules': dr.get('information_modules', []),
            'visual_style': dr.get('visual_style', ''),
            'image_prompt': sec.get('image_prompt', ''),
        })

    return {
        'content_data': {
            'structure': _safe_get(gen, 'structure') or '',
            'structure_name': structure_name,
            'geo_mode': geo_mode,
            'sections_count': len(sections),
            'title': title,
            'subtitle': subtitle,
            'tags': tags,
            'sections': sections,
            'hashtags': hashtags,
            'reading_time': _safe_get(gen, 'reading_time') or '',
            'word_count_estimate': _safe_get(gen, 'word_count_estimate') or '',
            'opening_hooks': opening_hooks,
            'summary': summary,
            'reading_report': reading_report,
            'first_comment': _safe_get(gen, 'first_comment') or '',
            'publish_strategy': _safe_get(gen, 'publish_strategy') or '',
            'trust_evidence': trust_evidence,
            'cta': cta,
            # ── 4维度方法论字段 ──
            'visual_identity': visual_identity,
            'four_dimension_summary': four_dimension_summary,
            'four_dimension_guide': four_dimension_guide,
            'section_4d_summary': section_4d_summary,
        },
        'quality_score': quality_score,
        'quality_report': {
            'total_score': quality_score,
            'grade': grade,
            'grade_label': '',
            'passed': quality_score >= 80,
            'optimized': False,
            'first_score': quality_score,
            'final_score': quality_score,
            'optimized_items': [],
            'items': items,
            'summary': '',
            'suggestions': [],
            'failed_items': failed_items,
            'need_optimize': quality_score < 80,
        },
        'geo_report': {
            'total_score': quality_score,
            'grade': grade,
            'items': items,
            'failed_items': failed_items,
            'summary': '',
        },
        'extracted_title': title,
        'extracted_tags': tags or hashtags,
        'extracted_geo': geo_mode,
        'sections_count': len(sections),
    }


def _build_video_script_text(content_result: dict) -> str:
    """
    将 SkillBridge 输出的短视频脚本渲染成文本内容。
    """
    scenes = content_result.get('scenes', [])
    if not scenes:
        return content_result.get('title', '')

    lines = []
    basic = content_result.get('basic', {})
    title = content_result.get('title', basic.get('title', ''))
    if title:
        lines.append(f"【{title}】")
    structure_name = content_result.get('structure_name', '')
    if structure_name:
        lines.append(f"结构：{structure_name}")
    duration = content_result.get('duration', '')
    if duration:
        lines.append(f"时长：{duration}")
    opening = content_result.get('opening', '')
    if opening:
        lines.append(f"\n前3秒钩子：{opening}")
    lines.append("")

    for scene in scenes:
        idx = scene.get('scene_index', 0)
        name = scene.get('scene_name', '')
        time_range = scene.get('time_range', '')
        emotion = scene.get('emotion_stage', '')
        color_tone = scene.get('color_tone', '')
        narration = scene.get('narration', scene.get('narrration', ''))
        subtitle_text = scene.get('subtitle_text', '')
        visual_dir = scene.get('visual_direction', {})
        shot_type = _safe_get(visual_dir, 'shot_type', '')
        camera = _safe_get(visual_dir, 'camera_movement', '')
        lighting = _safe_get(visual_dir, 'lighting', '')
        broll = _safe_get(visual_dir, 'broll_suggestion', '')
        key_point = scene.get('key_point', '')

        header = f"第{idx}场 | {name}"
        if time_range:
            header += f" ({time_range})"
        lines.append(header)
        if emotion:
            lines.append(f"  情绪：{emotion} | 色调：{color_tone}")
        if subtitle_text:
            lines.append(f"  字幕：{subtitle_text}")
        if narration:
            lines.append(f"  口播：{narration}")
        if shot_type or camera:
            lines.append(f"  镜头：{shot_type} / {camera} | 光：{lighting}")
        if broll:
            lines.append(f"  B-roll：{broll}")
        if key_point:
            lines.append(f"  要点：{key_point}")
        lines.append("")

    cta = content_result.get('cta', '')
    if cta:
        lines.append(f"CTA：{cta}")
    hashtags = content_result.get('hashtags', [])
    if hashtags:
        lines.append(" ".join(hashtags))

    return "\n".join(lines)


def _build_long_text_text(content_result: dict) -> str:
    """
    将 SkillBridge 输出的长文渲染成 Markdown 文本。
    """
    sections = content_result.get('sections', [])
    if not sections:
        return content_result.get('title', '')

    lines = []
    title = content_result.get('title', '')
    subtitle = content_result.get('subtitle', '')
    if title:
        lines.append(f"# {title}")
    if subtitle:
        lines.append(f"## {subtitle}")
    lines.append("")

    reading_time = content_result.get('reading_time', '')
    word_count = content_result.get('word_count_estimate', '')
    if reading_time or word_count:
        meta = []
        if reading_time:
            meta.append(f"阅读时间：{reading_time}")
        if word_count:
            meta.append(f"预估字数：{word_count}")
        lines.append(f"**{' | '.join(meta)}**")
        lines.append("")

    opening_hooks = content_result.get('opening_hooks', '')
    if opening_hooks:
        lines.append(f"> {opening_hooks}")
        lines.append("")

    for section in sections:
        idx = section.get('section_index', 0)
        name = section.get('section_name', '')
        # 纯正文字段（可复制发布）
        article_content = section.get('article_content') or section.get('content') or ''
        open_hook = section.get('open_hook', '')

        # 制作参考字段
        design_ref = section.get('design_reference', {}) or {}
        if isinstance(design_ref, dict):
            emotion_phase = design_ref.get('emotion_phase', '')
            layout_type = design_ref.get('layout_type', '')
            color_tone = design_ref.get('color_tone', '')
            ui_components = design_ref.get('ui_components', [])
            golden_quote = design_ref.get('golden_quote_block', {})
            info_modules = design_ref.get('information_modules', [])
            visual_style = design_ref.get('visual_style', '')
        else:
            emotion_phase = layout_type = color_tone = visual_style = ''
            ui_components = info_modules = []
            golden_quote = {}

        image_prompt = section.get('image_prompt', '')

        # ── 正文部分（可一键复制发布）──
        lines.append(f"## {idx}. {name}")
        if open_hook:
            lines.append(f"> {open_hook}")
        if article_content:
            lines.append("")
            lines.append(article_content)
        lines.append("")

    # ── 制作参考区块（末尾，供设计师参考，不影响正文复制）──
    visual_identity = content_result.get('visual_identity', {})
    four_dim_summary = content_result.get('four_dimension_summary', {})
    vi_light = visual_identity.get('light_style', '') if isinstance(visual_identity, dict) else ''
    vi_color = visual_identity.get('color_gradient_strategy', '') if isinstance(visual_identity, dict) else ''
    vi_primary = visual_identity.get('primary_colors', []) if isinstance(visual_identity, dict) else []
    vi_accent = visual_identity.get('accent_colors', []) if isinstance(visual_identity, dict) else []
    ef_summary = four_dim_summary.get('emotion_flow', '') if isinstance(four_dim_summary, dict) else ''
    lu_summary = four_dim_summary.get('layout_usage', '') if isinstance(four_dim_summary, dict) else ''

    # 只有在有制作参考内容时才追加区块
    has_design_ref = any(
        (section.get('design_reference') or section.get('image_prompt'))
        for section in sections
    ) or vi_light or ef_summary

    if has_design_ref:
        lines.append("---")
        lines.append("## 制作参考")
        lines.append("")
        if ef_summary:
            lines.append(f"**情绪动线**：{ef_summary}")
        if lu_summary:
            lines.append(f"**排版总览**：{lu_summary}")
        if vi_light:
            lines.append(f"**光影风格**：{vi_light}")
        if vi_color:
            lines.append(f"**色彩递进**：{vi_color}")
        if vi_primary:
            lines.append(f"**主色调**：{' / '.join(vi_primary)}")
        if vi_accent:
            lines.append(f"**强调色**：{' / '.join(vi_accent)}")
        lines.append("")

        for section in sections:
            s_idx = section.get('section_index', 0)
            s_name = section.get('section_name', '')
            dr = section.get('design_reference', {}) or {}
            if isinstance(dr, dict):
                ep = dr.get('emotion_phase', '')
                lt = dr.get('layout_type', '')
                ct = dr.get('color_tone', '')
                uic = dr.get('ui_components', [])
                gq = dr.get('golden_quote_block', {})
                vs = dr.get('visual_style', '')
                ims = dr.get('information_modules', [])
            else:
                ep = lt = ct = vs = ''
                uic = ims = []
                gq = {}
            ip = section.get('image_prompt', '')

            gq_text = gq.get('text') if isinstance(gq, dict) else ''
            gq_color = gq.get('bg_color') if isinstance(gq, dict) else ''
            tone_map = {'cold': '冷色', 'warm': '暖色', 'brand': '品牌色'}
            layout_map = {'billboard': '封面版式', 'problem_solver': '痛点对比版式', 'matrix': '干货矩阵版式', 'trust_builder': '品牌收尾版式'}

            sec_lines = [f"### {s_idx}. {s_name}"]
            if ep:
                sec_lines.append(f"- 情绪阶段：{ep}")
            if lt:
                sec_lines.append(f"- 排版类型：{layout_map.get(lt, lt)}")
            if ct:
                sec_lines.append(f"- 色调：{tone_map.get(ct, ct)}")
            if gq_text:
                sec_lines.append(f"- 金句：{gq_text}" + (f"（背景:{gq_color}）" if gq_color else ""))
            if uic:
                sec_lines.append(f"- UI组件：{'、'.join(uic)}")
            if ims:
                sec_lines.append(f"- 信息模块：{'、'.join(ims)}")
            if vs:
                sec_lines.append(f"- 视觉风格：{vs}")
            if ip:
                sec_lines.append(f"- **生图提示词**：{ip}")
            lines.extend(sec_lines)
        lines.append("")

    summary = content_result.get('summary', '')
    if summary:
        lines.append("---")
        lines.append("## 核心要点")
        lines.append(summary)
        lines.append("")

    cta = content_result.get('cta', '')
    if cta:
        lines.append(f"**行动号召：{cta}**")
        lines.append("")

    hashtags = content_result.get('hashtags', [])
    if hashtags:
        lines.append(" ".join(hashtags))

    return "\n".join(lines)


def _build_content_text(content_result: dict) -> str:
    """
    将 SkillBridge 输出的 slides 数组渲染成文本内容。
    """
    slides = content_result.get('slides', [])
    if not slides:
        return content_result.get('title', '')

    lines = []
    basic = content_result.get('basic', {})
    if basic:
        title = basic.get('title', '')
        subtitle = basic.get('subtitle', '')
        if title:
            lines.append(f"【{title}】")
        if subtitle:
            lines.append(subtitle)
        lines.append("")

    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            lines.append(f"第{i+1}页：{slide}")
            continue
        role = slide.get('role', '')
        main_title = slide.get('main_title', '')
        big_slogan = slide.get('big_slogan', '')
        sub_points = slide.get('sub_points', [])

        if main_title or big_slogan:
            lines.append(f"第{i+1}页{'【' + role + '】' if role else ''}")
            if big_slogan:
                lines.append(f"  {big_slogan}")
            if main_title:
                lines.append(f"  {main_title}")
        if sub_points:
            for sp in sub_points:
                lines.append(f"  · {sp}")
        lines.append("")

    basic_blocks = content_result.get('blocks', {})
    if isinstance(basic_blocks, dict):
        comment = basic_blocks.get('comment', '') or basic_blocks.get('first_comment', '')
        if comment:
            lines.append(f"首评：{comment}")
        ext = basic_blocks.get('extension', '') or basic_blocks.get('content_plan', '')
        if ext:
            lines.append(ext)

    hashtags = content_result.get('hashtags', [])
    if hashtags:
        lines.append(" ".join(hashtags))

    return "\n".join(lines)


def _build_hvf_report(hvf_output: dict) -> dict:
    """
    将 SkillBridge title_generator 的输出适配成审核报告格式。
    """
    # 取标题列表（可能在 step_title_generate 或顶层）
    titles_data = hvf_output.get('titles', [])
    if not titles_data:
        titles_data = hvf_output.get('step_title_generate', {}).get('titles', [])
    if not titles_data:
        titles_data = hvf_output.get('step_title_review', {}).get('title_reviews', [])

    # 取审核结果
    review_data = hvf_output.get('step_title_review', {}) or hvf_output.get('title_review', {})

    best = review_data.get('best_title', '')
    best_pattern = review_data.get('best_pattern', '')

    # 找评分最高的标题
    if not best and titles_data:
        best_score = -1
        for t in titles_data:
            hvf = t.get('hvf_score', {})
            total = hvf.get('total', hvf.get('hook', 0) + hvf.get('value', 0) + hvf.get('format', 0))
            if isinstance(total, str):
                total = 0
            if total > best_score:
                best_score = total
                best = t.get('main_title', '')
                best_pattern = t.get('pattern', '')

    return {
        'titles': titles_data,
        'best_title': best,
        'best_pattern': best_pattern,
        'review': review_data,
        'total_generated': len(titles_data),
    }


def _build_pyramid_tags(pyramid_output: dict) -> dict:
    """
    将 SkillBridge tag_generator 的输出适配成标签报告格式。
    """
    # 取标签数据（可能在 step_tag_generate 或顶层）
    tags_data = pyramid_output.get('hashtags', [])
    if not tags_data:
        tags_data = pyramid_output.get('step_tag_generate', {}).get('hashtags', [])

    # 取审核结果
    review_data = pyramid_output.get('step_tag_review', {}) or pyramid_output.get('tag_review', {})

    # 优先使用审核后的最终标签
    final_tags = review_data.get('final_hashtags', tags_data)
    if not final_tags:
        final_tags = tags_data

    return {
        'hashtags': final_tags,
        'tier1': pyramid_output.get('tier1_common', pyramid_output.get('step_tag_generate', {}).get('tier1_common', [])),
        'tier2': pyramid_output.get('tier2_vertical', pyramid_output.get('step_tag_generate', {}).get('tier2_vertical', [])),
        'tier3': pyramid_output.get('tier3_longtail', pyramid_output.get('step_tag_generate', {}).get('tier3_longtail', [])),
        'search_keywords': pyramid_output.get('search_keywords', pyramid_output.get('step_tag_generate', {}).get('search_keywords', [])),
        'review': review_data,
    }


def _apply_hvf_and_tags(
    result: dict,
    params: dict,
    result_type: str,
    content_result: dict = None,
) -> tuple:
    """
    公共函数：为所有内容类型（图文/长文/短视频）生成 H-V-F 标题和金字塔标签。

    标题和标签生成并行执行，减少等待时间。

    Args:
        result: 原始内容生成结果 dict
        params: 请求参数 dict
        result_type: 内容类型 'graphic' / 'long_text' / 'short_video'
        content_result: 可选，预解析的 content dict

    Returns:
        (extracted_title, extracted_tags, extracted_geo,
         hvf_titles_output, pyramid_tags_output, hvf_report, pyramid_tags_report)
    """
    import logging
    from concurrent.futures import ThreadPoolExecutor, as_completed
    logger = logging.getLogger(__name__)

    # ── 提取原始标题/标签/GEO ──────────────────────────────────
    raw_content = content_result if content_result else (result.get('content') if isinstance(result.get('content'), dict) else {})
    if not raw_content:
        raw_content = {}

    if result_type == 'graphic':
        extracted_title = raw_content.get('title', '') or ''
        extracted_tags = raw_content.get('tags', []) or []
        extracted_geo = raw_content.get('geo_mode', '')
    elif result_type == 'long_text':
        article = raw_content.get('article', {})
        extracted_title = article.get('title', '') or ''
        extracted_tags = article.get('hashtags', []) or []
        extracted_geo = ''
    elif result_type == 'short_video':
        extracted_title = raw_content.get('title', '') or ''
        extracted_tags = raw_content.get('tags', []) or []
        extracted_geo = raw_content.get('geo_mode', '')
    else:
        extracted_title = ''
        extracted_tags = []
        extracted_geo = ''

    # ── 调用 SkillBridge 生成 H-V-F 标题 + 金字塔标签（并行） ─
    hvf_titles_output = {}
    pyramid_tags_output = {}

    try:
        from services.skill_bridge import SkillBridge
        bridge = SkillBridge()

        seo_kws = raw_content.get('seo_keywords', {}) if isinstance(raw_content, dict) else {}
        keywords = {
            'core': seo_kws.get('core', []),
            'long_tail': seo_kws.get('long_tail', []),
            'scene': seo_kws.get('scene', []),
            'problem': seo_kws.get('problem', []),
        }

        portrait = params.get('portrait', {})
        if not keywords.get('core') and portrait:
            portrait_kws = portrait.get('keywords', [])
            if isinstance(portrait_kws, list):
                keywords['core'] = portrait_kws[:5]

        # ── 从 selected_scene 提取 geo_mode兜底 ──
        selected_scene = params.get('selected_scene', {})
        geo_from_scene = ''
        if selected_scene and isinstance(selected_scene, dict):
            geo_from_scene = selected_scene.get('dim_value', '') or selected_scene.get('label', '') or ''
            if geo_from_scene and ' - ' in geo_from_scene:
                geo_from_scene = geo_from_scene.split(' - ', 1)[0].strip()

        geo_mode = extracted_geo or params.get('geo_mode', '') or geo_from_scene
        industry = params.get('industry', '') or params.get('business_type', '')

        logger.info(f"[H-V-F] {result_type} 并行生成标题和标签: topic={params.get('topic_title', '')[:20]}")

        def call_title():
            return bridge.execute_title_generator(
                topic_title=params.get('topic_title', ''),
                portrait=portrait,
                keywords=keywords,
                geo_mode=geo_mode,
                industry=industry,
                num_variants=4,
            )

        def call_tag():
            return bridge.execute_tag_generator(
                topic_title=params.get('topic_title', ''),
                industry=industry,
                keywords=keywords,
                portrait=portrait,
                geo_mode=geo_mode,
                max_tags=8,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            title_future = executor.submit(call_title)
            tag_future = executor.submit(call_tag)

            try:
                hvf_res = title_future.result(timeout=60)
                if hvf_res.success:
                    hvf_titles_output = hvf_res.full_output
            except Exception as e:
                logger.warning(f"[H-V-F] 标题生成异常: {e}")

            try:
                tag_res = tag_future.result(timeout=60)
                if tag_res.success:
                    pyramid_tags_output = tag_res.full_output
            except Exception as e:
                logger.warning(f"[H-V-F] 标签生成异常: {e}")

        logger.info(f"[H-V-F] 标题: {'成功' if hvf_titles_output else '失败'} | 标签: {'成功' if pyramid_tags_output else '失败'}")

    except Exception as e:
        logger.warning(f"[H-V-F] 生成异常: {e}，不影响内容返回")

    # ── H-V-F 标题覆盖（取评分最高的）───────────────────────────
    if hvf_titles_output:
        titles_data = hvf_titles_output.get('titles', [])
        if not titles_data:
            titles_data = hvf_titles_output.get('step_title_generate', {}).get('titles', [])

        if titles_data:
            best_title_obj = None
            best_score = -1
            for t in titles_data:
                score = t.get('hvf_score', {})
                total = score.get('total', 0)
                if isinstance(total, str):
                    total = 0
                if total <= 0:
                    total = score.get('hook', 0) + score.get('value', 0) + score.get('format', 0)
                if total > best_score:
                    best_score = total
                    best_title_obj = t
            if best_title_obj and best_title_obj.get('main_title'):
                extracted_title = best_title_obj['main_title']

    # ── 金字塔标签覆盖 ─────────────────────────────────────────
    if pyramid_tags_output:
        tags_data = pyramid_tags_output.get('hashtags', [])
        if not tags_data:
            tags_data = pyramid_tags_output.get('step_tag_generate', {}).get('hashtags', [])
        if tags_data:
            extracted_tags = tags_data[:8]

    # ── 构建报告 ───────────────────────────────────────────────
    hvf_report = _build_hvf_report(hvf_titles_output) if hvf_titles_output else {}
    pyramid_tags_report = _build_pyramid_tags(pyramid_tags_output) if pyramid_tags_output else {}

    return (
        extracted_title,
        extracted_tags,
        extracted_geo,
        hvf_titles_output,
        pyramid_tags_output,
        hvf_report,
        pyramid_tags_report,
    )


def _adapt_topic_library_result(bridge_result) -> dict:
    """
    将 SkillBridge execute_topic_library 的结果适配成旧 TopicLibraryGenerator 的格式。
    """
    fo = bridge_result.full_output

    # 合并所有步骤的选题
    all_topics = []
    for step_key in ['context_analysis', 'public_topics', 'portrait_topics',
                     'keyword_topics', 'topic_library_summary']:
        step_data = fo.get(step_key, {})
        if isinstance(step_data, dict):
            for k, v in step_data.items():
                if isinstance(v, list):
                    all_topics.extend(v)

    # 按五段式分类
    audience = []
    pain = []
    compare = []
    vision = []
    hesitation = []

    for step_key in ['portrait_topics', 'public_topics', 'keyword_topics']:
        step_data = fo.get(step_key, {})
        if isinstance(step_data, dict):
            topics = step_data.get('portrait_topics') or step_data.get('public_topics') or step_data.get('keyword_topics', [])
            if isinstance(topics, list):
                for t in topics:
                    stage = t.get('stage', '') if isinstance(t, dict) else ''
                    item = t if isinstance(t, dict) else {}
                    if stage == 'audience':
                        audience.append(item)
                    elif stage == 'pain':
                        pain.append(item)
                    elif stage == 'compare':
                        compare.append(item)
                    elif stage == 'vision':
                        vision.append(item)
                    elif stage == 'hesitation':
                        hesitation.append(item)

    summary = fo.get('topic_library_summary', {})
    if isinstance(summary, dict):
        s = summary.get('summary', {}) if isinstance(summary.get('summary'), dict) else summary
    else:
        s = {}

    return {
        'topics': all_topics,
        'audience_lock_topics': audience,
        'pain_amplify_topics': pain,
        'solution_compare_topics': compare,
        'vision_topics': vision,
        'barrier_remove_topics': hesitation,
        'summary': s,
    }


def _adapt_portrait_generator_result(bridge_result) -> dict:
    """
    将 SkillBridge execute_portrait_generator 的结果适配成旧 PortraitGenerator 的格式。

    注意：full_output 的 key 是 step_id（如 step_extract_problem_types），
    不是字段名。字段数据在 step_output['output'] 中。
    """
    fo = bridge_result.full_output
    portraits = []
    problem_types = []

    # step_extract_problem_types → output.problem_types
    step_prob = fo.get('step_extract_problem_types', {})
    if isinstance(step_prob, dict):
        step_output = step_prob.get('output', step_prob)  # 兼容两种格式
        pts = step_output.get('problem_types', [])
        for pt in pts:
            if isinstance(pt, dict):
                problem_types.append({
                    'type_name': pt.get('type_name', ''),
                    'description': pt.get('description', ''),
                    'target_audience': pt.get('target_audience', ''),
                    'keywords': pt.get('keywords', []),
                })

    # step_generate_portraits → output.portraits
    step_port = fo.get('step_generate_portraits', {})
    if isinstance(step_port, dict):
        step_output = step_port.get('output', step_port)
        pts_list = step_output.get('portraits', [])
        for p in pts_list:
            if isinstance(p, dict):
                portraits.append({
                    'portrait_id': p.get('portrait_id', ''),
                    'problem_type': p.get('problem_type', ''),
                    'identity': p.get('identity', ''),
                    'pain_points': p.get('pain_points', []),
                    'psychology': p.get('psychology', {}),
                    'portrait_summary': p.get('portrait_summary', ''),
                    'content_direction': p.get('content_direction', '种草型'),
                })

    return {
        'portraits': portraits,
        'problem_types': problem_types,
    }


# =============================================================================
# 市场分析 API（仅分析，返回蓝海机会供用户选择）
# =============================================================================

@public_bp.route('/api/market/analyze', methods=['POST'])
def api_market_analyze():
    """
    市场分析 API - 仅做市场分析，返回蓝海机会供用户选择

    POST /public/api/market/analyze
    Body: {
        business_description: str,   # 业务描述
        industry: str,              # 行业（可选）
        business_type: str,         # 经营类型
    }

    Response: {
        success: True,
        data: {
            opportunities: [...],     # 蓝海机会列表
            subdivision_insights: {}, # 细分洞察
            keyword_stats: {...},     # 关键词统计
        }
    }
    """
    from services.market_analyzer import MarketAnalyzer

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    business_description = data.get('business_description', '').strip()
    if not business_description:
        return jsonify({
            'success': False,
            'message': '请输入业务描述'
        }), 400

    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    business_range = data.get('business_range', '')
    local_city = data.get('local_city', '').strip()
    service_scenario = data.get('service_scenario', '')

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
        'business_range': business_range,
        'local_city': local_city,
        'service_scenario': service_scenario,
    }

    logger.info(f"[api_market_analyze] 开始市场分析: {business_description[:50]}，经营范围={business_range}，服务场景={service_scenario}")

    try:
        # 切换到 SkillBridge
        from services.skill_bridge import SkillBridge
        bridge = SkillBridge()
        result = bridge.execute_market_analyzer(
            business_description=business_description,
            industry=industry,
            business_type=business_type,
            service_scenario=service_scenario,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"市场分析失败: {result.errors[0] if result.errors else '未知错误'}"
            }), 500

        adapted = _adapt_market_analyzer_result(result)

        logger.info(f"[api_market_analyze] SkillBridge 分析完成: {len(adapted['market_opportunities'])} 个蓝海机会")

        return jsonify({
            'success': True,
            'data': {
                'opportunities': adapted['market_opportunities'],
                'subdivision_insights': adapted['subdivision_insights'],
                'keyword_stats': adapted['keyword_stats'],
                # 兼容旧字段名
                '_analysis_result': {
                    'step1_industry_overview': result.full_output.get('step1_industry_overview', {}),
                    'step2_blue_ocean': result.full_output.get('step2_blue_ocean', {}),
                    'step3_audience_segment': result.full_output.get('step3_audience_segment', {}),
                    'step4_long_tail_needs': result.full_output.get('step4_long_tail_needs', {}),
                    'step6_search_journey': result.full_output.get('step6_search_journey', {}),
                    'step7_upstream_downstream': result.full_output.get('step7_upstream_downstream', {}),
                    'step8_trust_and_advantage': result.full_output.get('step8_trust_and_advantage', {}),
                }
            }
        })

    except Exception as e:
        logger.error(f"[api_market_analyze] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'分析异常: {str(e)}'
        }), 500


# =============================================================================
# 两阶段市场分析 API - Step 1: 挖掘蓝海机会
# =============================================================================

@public_bp.route('/api/market/analyze_opportunities', methods=['POST'])
def api_market_analyze_opportunities():
    """
    两阶段市场分析 - Step 1: 仅挖掘蓝海机会

    POST /public/api/market/analyze_opportunities
    Body: {
        business_description: str,   # 业务描述
        industry: str,              # 行业（可选）
        business_type: str,         # 经营类型
        use_search: bool,           # 是否启用搜索增强（默认 True）
    }

    Response: {
        success: True,
        data: {
            opportunities: [...],     # 蓝海机会列表
            subdivision_insights: {}, # 细分洞察
        }
    }
    """
    from services.market_analyzer import MarketAnalyzer

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    business_description = data.get('business_description', '').strip()
    if not business_description:
        return jsonify({
            'success': False,
            'message': '请输入业务描述'
        }), 400

    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    business_range = data.get('business_range', '')
    local_city = data.get('local_city', '').strip()
    service_scenario = data.get('service_scenario', '')

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
        'business_range': business_range,
        'local_city': local_city,
        'service_scenario': service_scenario,
    }
    use_search = data.get('use_search', True)  # 默认开启搜索增强

    logger.info(f"[api_market_analyze_opportunities] Step 1: 挖掘蓝海机会（搜索增强={use_search}）: {business_description[:50]}，经营范围={business_range}，服务场景={service_scenario}")

    try:
        analyzer = MarketAnalyzer()
        result = analyzer.analyze_opportunities(
            business_info=business_info,
            max_opportunities=5,
            use_search_verification=use_search,
        )

        if not result.get('success'):
            return jsonify({
                'success': False,
                'message': f"分析失败: {result.get('error_message')}"
            }), 500

        logger.info(f"[api_market_analyze_opportunities] Step 1 完成: 发现 {len(result['market_opportunities'])} 个蓝海机会")

        return jsonify({
            'success': True,
            'data': {
                'opportunities': result['market_opportunities'],
                'subdivision_insights': result.get('subdivision_insights', {}),
            }
        })

    except Exception as e:
        logger.error(f"[api_market_analyze_opportunities] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'分析异常: {str(e)}'
        }), 500


# =============================================================================
# 蓝海机会快照 API - 收藏功能
# =============================================================================

@public_bp.route('/api/opportunities/snapshots', methods=['GET'])
def api_get_opportunity_snapshots():
    """获取用户收藏的蓝海机会快照列表"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import OpportunitySnapshot

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    page_size = min(page_size, 50)

    query = OpportunitySnapshot.query.filter_by(user_id=user.id).order_by(
        OpportunitySnapshot.created_at.desc()
    )

    total = query.count()
    snapshots = query.offset((page - 1) * page_size).limit(page_size).all()

    return jsonify({
        'success': True,
        'data': {
            'total': total,
            'page': page,
            'page_size': page_size,
            'snapshots': [_serialize_snapshot(s) for s in snapshots]
        }
    })


@public_bp.route('/api/opportunities/snapshots', methods=['POST'])
def api_create_opportunity_snapshot():
    """收藏一个蓝海机会"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    data = request.get_json() or {}
    snapshot_data = data.get('snapshot_data')

    if not snapshot_data:
        return jsonify({'success': False, 'message': '快照数据不能为空'}), 400

    from models.public_models import OpportunitySnapshot
    current_count = OpportunitySnapshot.query.filter_by(user_id=user.id).count()
    if current_count >= 20:
        return jsonify({
            'success': False,
            'message': '收藏已达上限（20个），请先删除不需要的快照'
        }), 400

    source_analyzed_at = None
    if data.get('source_analyzed_at'):
        try:
            source_analyzed_at = datetime.datetime.fromisoformat(
                data['source_analyzed_at'].replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            source_analyzed_at = datetime.datetime.utcnow()

    new_snapshot = OpportunitySnapshot(
        user_id=user.id,
        snapshot_data=snapshot_data,
        note=data.get('note', ''),
        source_business_desc=data.get('source_business_desc', ''),
        source_business_type=data.get('source_business_type', ''),
        source_analyzed_at=source_analyzed_at or datetime.datetime.utcnow(),
    )
    db.session.add(new_snapshot)
    db.session.commit()

    logger.info(f"[api_create_opportunity_snapshot] 用户 {user.id} 收藏了蓝海机会: {snapshot_data.get('opportunity_name', 'unknown')}")

    return jsonify({
        'success': True,
        'data': _serialize_snapshot(new_snapshot),
        'message': '收藏成功'
    }), 201


@public_bp.route('/api/opportunities/snapshots/<int:snapshot_id>', methods=['PUT'])
def api_update_opportunity_snapshot(snapshot_id):
    """更新快照备注"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import OpportunitySnapshot
    snapshot = OpportunitySnapshot.query.filter_by(
        id=snapshot_id, user_id=user.id
    ).first()

    if not snapshot:
        return jsonify({'success': False, 'message': '快照不存在'}), 404

    data = request.get_json() or {}
    snapshot.note = data.get('note', '')
    db.session.commit()

    return jsonify({
        'success': True,
        'data': _serialize_snapshot(snapshot),
        'message': '更新成功'
    })


@public_bp.route('/api/opportunities/snapshots/<int:snapshot_id>', methods=['DELETE'])
def api_delete_opportunity_snapshot(snapshot_id):
    """删除快照"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import OpportunitySnapshot
    snapshot = OpportunitySnapshot.query.filter_by(
        id=snapshot_id, user_id=user.id
    ).first()

    if not snapshot:
        return jsonify({'success': False, 'message': '快照不存在'}), 404

    db.session.delete(snapshot)
    db.session.commit()

    return jsonify({'success': True, 'message': '已删除'})


@public_bp.route('/api/opportunities/snapshots/clear', methods=['POST'])
def api_clear_all_snapshots():
    """清空当前用户所有快照（业务描述重置时调用）"""
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    from models.public_models import OpportunitySnapshot
    deleted = OpportunitySnapshot.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    logger.info(f"[api_clear_all_snapshots] 用户 {user.id} 清空了 {deleted} 个快照")

    return jsonify({
        'success': True,
        'message': f'已清空 {deleted} 个快照'
    })


def _serialize_snapshot(snapshot):
    """序列化快照对象"""
    return {
        'id': snapshot.id,
        'snapshot_data': snapshot.snapshot_data,
        'note': snapshot.note,
        'source_business_desc': snapshot.source_business_desc,
        'source_business_type': snapshot.source_business_type,
        'source_analyzed_at': (
            snapshot.source_analyzed_at.isoformat() if snapshot.source_analyzed_at else None
        ),
        'used_for_portrait_id': snapshot.used_for_portrait_id,
        'created_at': snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


# =============================================================================
# 两阶段市场分析 API - Step 2: 基于业务方向生成关键词库
# =============================================================================

@public_bp.route('/api/market/generate_keyword_library', methods=['POST'])
def api_generate_keyword_library():
    """
    两阶段市场分析 - Step 2: 基于用户选择的业务方向，生成精准关键词库

    POST /public/api/market/generate_keyword_library
    Body: {
        business_description: str,   # 原始业务描述
        industry: str,              # 行业（可选）
        business_type: str,         # 经营类型
        core_business: str,        # 核心业务词（可选，默认从业务描述提取）
        blue_ocean_opportunity: str, # 蓝海机会描述（可选，用于指导关键词生成方向）
        portraits: [                # 画像列表（可选，用于生成个性化关键词）
            {portrait_id: str, name: str, problem_type: str},
            ...
        ]
    }

    Response: {
        success: True,
        data: {
            keyword_library: {...},   # 关键词库（包含 common_keywords 和 portrait_keywords）
            problem_types: [...],     # 问题类型（画像）
            portrait_keywords: [...],  # 画像专属关键词（新增）
            keyword_stats: {          # 关键词统计
                total: int,
                common: int,          # 公用关键词数量（新增）
                portrait: int,        # 个性化关键词数量（新增）
                blue_ocean: int,
                red_ocean: int,
            }
        }
    }
    """
    from services.skill_bridge import SkillBridge

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    business_description = data.get('business_description', '').strip()
    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    core_business = data.get('core_business', '').strip()
    blue_ocean_opportunity = data.get('blue_ocean_opportunity', '').strip()
    portraits = data.get('portraits', [])
    portrait_data = data.get('portrait_data', {})

    if not business_description:
        return jsonify({
            'success': False,
            'message': '请输入业务描述'
        }), 400

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
    }

    logger.info(f"[api_generate_keyword_library] Step 2: 生成关键词库 (蓝海机会={blue_ocean_opportunity}, 画像数={len(portraits)})")

    try:
        # 切换到 SkillBridge
        bridge = SkillBridge()
        market_output = data.get('market_analyzer_output', {})
        if not market_output:
            market_output = data.get('analysis_result', {})

        result = bridge.execute_keyword_library(
            business_description=business_description,
            industry=industry,
            business_type=business_type,
            market_analyzer_output=market_output,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"生成失败: {result.errors[0] if result.errors else '未知错误'}"
            }), 500

        adapted = _adapt_keyword_library_result(result)
        total_kw = adapted['keyword_stats'].get('total', 0)

        logger.info(f"[api_generate_keyword_library] Step 2 完成: 关键词={total_kw}")

        return jsonify({
            'success': True,
            'data': {
                'keyword_library': adapted['keyword_library'],
                'problem_types': adapted.get('problem_types', []),
                'portrait_keywords': adapted.get('portrait_keywords', []),
                'keyword_stats': adapted['keyword_stats'],
                # 附加 SkillBridge 原始输出供调试
                '_skill_bridge_output': result.full_output,
            }
        })

    except Exception as e:
        import traceback
        logger.error(f"[api_generate_keyword_library] 异常: {e}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'生成异常: {str(e)}'
        }), 500


# =============================================================================
# 画像生成 API（基于用户选择的蓝海机会）
# =============================================================================

@public_bp.route('/api/portraits/generate', methods=['POST'])
def api_portraits_generate():
    """
    画像生成 API - 基于选定的蓝海机会生成画像

    POST /public/api/portraits/generate
    Body: {
        core_business: str,              # 核心业务（用户选择/输入的蓝海方向）
        original_business: str,          # 原始业务描述
        industry: str,                   # 行业
        business_type: str,              # 经营类型
        service_scenario: str,           # 服务场景
        analysis_result: {},             # 市场分析结果（从 market/analyze 获取）
        portraits_per_type: int,         # 每个问题类型生成的画像数
        selected_opportunity: {}        # 用户选中的蓝海机会（含 problem_types → scenes）
    }
    """
    from services.skill_bridge import SkillBridge

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    core_business = data.get('core_business', '').strip()
    original_business = data.get('original_business', '').strip()
    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    service_scenario = data.get('service_scenario', 'other')
    analysis_result = data.get('analysis_result', {})
    portraits_per_type = data.get('portraits_per_type', 3)
    selected_opportunity = data.get('selected_opportunity', {})

    if not core_business:
        return jsonify({
            'success': False,
            'message': '请选择或输入核心业务'
        }), 400

    business_info = {
        'business_description': core_business,
        'industry': industry,
        'business_type': business_type,
        'service_scenario': service_scenario,
    }

    logger.info(f"[api_portraits_generate] 开始生成画像: {core_business}")

    try:
        # 切换到 SkillBridge
        bridge = SkillBridge()

        # 从 analysis_result 中提取数据
        # 前端传来的 analysis_result = { problem_types, market_opportunities }
        # 构造 market_analyzer_output 供 portrait_generator 使用
        market_output = {
            'step2_blue_ocean': {
                'opportunities': analysis_result.get('market_opportunities', []),
            },
            'step_extract_problem_types': {
                'problem_types': analysis_result.get('problem_types', []),
            },
        }

        # keyword_library 可能为空，从 analysis_result 中尝试提取
        keyword_library = analysis_result.get('keyword_library', {})
        if not keyword_library:
            keyword_library = analysis_result.get('keywords', {})

        result = bridge.execute_portrait_generator(
            industry=industry,
            business_description=core_business,
            business_type=business_type,
            keyword_library=keyword_library,
            market_analyzer_output=market_output,
            portraits_per_type=portraits_per_type,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"画像生成失败: {result.errors[0] if result.errors else '未知错误'}"
            }), 500

        adapted = _adapt_portrait_generator_result(result)
        portraits_data = adapted['portraits']

        # 兼容旧字段名，复制一份 portrait_data
        for p in portraits_data:
            p['portrait_data'] = {
                'pain_points': p.get('pain_points', []),
                'pain_scenarios': p.get('pain_scenarios', []),
                'barriers': p.get('barriers', []),
            }

        # 按问题类型分组（简单实现）
        portraits_by_type = {}
        for p in portraits_data:
            pt = p.get('problem_type', '其他')
            if pt not in portraits_by_type:
                portraits_by_type[pt] = []
            portraits_by_type[pt].append(p)

        logger.info(f"[api_portraits_generate] 生成完成: {len(portraits_data)} 个画像")

        return jsonify({
            'success': True,
            'data': {
                'core_business': core_business,
                'portraits': portraits_data,
                'portraits_by_type': portraits_by_type,
            }
        })

    except Exception as e:
        logger.error(f"[api_portraits_generate] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'生成异常: {str(e)}'
        }), 500


# =============================================================================
# 画像专属关键词库+选题库生成 API
# =============================================================================

@public_bp.route('/api/portraits/generate_keywords_topics', methods=['POST'])
def api_portrait_keywords_topics_generate():
    """
    画像专属关键词库+选题库生成
    触发时机：画像保存时或画像列表页点击"生成关键词/选题"

    POST /public/api/portraits/generate_keywords_topics
    Body: {
        core_business: str,         # 核心业务（如"农村考生志愿辅导"）
        industry: str,                # 行业
        business_type: str,          # 经营类型
        portrait: {},                # 单个画像对象
    }

    Response: {
        success: True,
        data: {
            portrait_id: str,
            keyword_library: {
                problem_type_keywords: [...],  # 问题类型关键词（10个）
                pain_point_keywords: [...],    # 痛点关键词（10个）
                scene_keywords: [...],       # 场景关键词（5个）
                concern_keywords: [...],     # 顾虑关键词（5个）
            },
            topic_library: {
                audience_lock_topics: [...],   # 受众锁定类（8个）
                pain_amplify_topics: [...],     # 痛点放大类（10个）
                solution_compare_topics: [...],  # 方案对比类（8个）
                vision_topics: [...],          # 愿景勾画类（8个）
                barrier_remove_topics: [...],   # 顾虑消除类（8个）
            }
        }
    }
    """
    from services.skill_bridge import SkillBridge

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    core_business = data.get('core_business', '').strip()
    industry = data.get('industry', '').strip()
    portrait = data.get('portrait', {})
    business_type = data.get('business_type', 'product')
    content_stage = data.get('content_stage', '成长阶段')

    if not core_business:
        return jsonify({
            'success': False,
            'message': '请提供核心业务'
        }), 400

    if not portrait:
        return jsonify({
            'success': False,
            'message': '请提供画像数据'
        }), 400

    logger.info(f"[api_portrait_keywords_topics_generate] 生成关键词选题: 画像={portrait.get('portrait_id', 'N/A')}, 业务={core_business}")

    try:
        bridge = SkillBridge()

        # Step 1: 关键词库
        kw_result = bridge.execute_keyword_library(
            business_description=core_business,
            industry=industry,
            business_type=business_type,
        )

        # Step 2: 选题库
        topic_result = bridge.execute_topic_library(
            industry=industry,
            business_description=core_business,
            content_stage=content_stage,
        )

        kw_adapted = _adapt_keyword_library_result(kw_result) if kw_result.success else {'keyword_library': {}, 'keyword_stats': {}}
        topic_adapted = _adapt_topic_library_result(topic_result) if topic_result.success else {}

        logger.info(f"[api_portrait_keywords_topics_generate] 生成完成: 画像={portrait.get('portrait_id', 'N/A')}")

        return jsonify({
            'success': True,
            'data': {
                'portrait_id': portrait.get('portrait_id', ''),
                'keyword_library': kw_adapted.get('keyword_library', {}),
                'topic_library': topic_adapted,
            }
        })

    except Exception as e:
        logger.error(f"[api_portrait_keywords_topics_generate] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'生成异常: {str(e)}'
        }), 500


# =============================================================================
# 批量画像专属关键词库+选题库生成 API
# =============================================================================

@public_bp.route('/api/portraits/generate_keywords_topics_batch', methods=['POST'])
def api_portrait_keywords_topics_generate_batch():
    """
    批量生成画像专属关键词库+选题库（含市场关键词库）

    POST /public/api/portraits/generate_keywords_topics_batch
    Body: {
        core_business: str,
        industry: str,
        business_type: str,
        portraits: [],  # 画像列表
    }
    """
    from services.keyword_topic_generator import KeywordTopicGenerator
    from services.keyword_library_generator import KeywordLibraryGenerator

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    core_business = data.get('core_business', '').strip()
    industry = data.get('industry', '').strip()
    portraits = data.get('portraits', [])
    # 取第一个画像的 portrait_data 用于市场关键词库生成（所有画像共享）
    first_portrait_data = (portraits[0].get('portrait_data', {}) or {}) if portraits else {}

    if not core_business:
        return jsonify({'success': False, 'message': '请提供核心业务'}), 400

    if not portraits:
        return jsonify({'success': False, 'message': '请提供画像数据'}), 400

    logger.info(f"[api_portrait_keywords_topics_batch] 批量生成: 业务={core_business}, 画像数={len(portraits)}")

    try:
        # 先生成市场关键词库（100+），所有画像共享
        market_kw_lib = {}
        market_kw_stats = {}
        try:
            kl_gen = KeywordLibraryGenerator()
            kl_result = kl_gen.generate(
                business_info={
                    'business_description': core_business,
                    'industry': industry,
                    'business_type': data.get('business_type', 'product'),
                },
                core_business=None,
                max_keywords=200,
                blue_ocean_opportunity=None,
                portraits=None,
                portrait_data=first_portrait_data,
            )
            if kl_result.success:
                market_kw_lib = kl_result.keyword_library or {}
                market_kw_stats = {
                    'total': kl_result.total_keywords,
                    'blue_ocean': kl_result.blue_ocean_keywords,
                    'red_ocean': kl_result.red_ocean_keywords,
                }
                logger.info(f"[api_portrait_keywords_topics_batch] 市场关键词库生成完成: {kl_result.total_keywords} 个")
            else:
                logger.warning(f"[api_portrait_keywords_topics_batch] 市场关键词库生成失败: {kl_result.error_message}")
        except Exception as e:
            logger.warning(f"[api_portrait_keywords_topics_batch] 市场关键词库生成异常: {e}")

        # 批量生成画像专属关键词库+选题库
        generator = KeywordTopicGenerator()
        results = generator.generate_batch(
            core_business=core_business,
            portraits=portraits,
        )

        # 合并市场关键词库到每个结果
        results_data = []
        for r in results:
            rd = r.to_dict()
            # 合并 market_keywords 到 keyword_library 字段
            if 'keyword_library' in rd:
                merged_kl = {**market_kw_lib, **rd['keyword_library']}
                rd['keyword_library'] = merged_kl
            rd['market_kw_stats'] = market_kw_stats
            results_data.append(rd)

        logger.info(f"[api_portrait_keywords_topics_batch] 批量生成完成: {len(results_data)} 个画像")

        return jsonify({
            'success': True,
            'data': {
                'portraits': results_data,
            }
        })

    except Exception as e:
        logger.error(f"[api_portrait_keywords_topics_batch] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'生成异常: {str(e)}'
        }), 500


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


@public_bp.route('/api/super-position/save-batch', methods=['POST'])
def api_save_portrait_batch():
    """
    保存一键分析结果（批量保存画像）

    POST /public/api/super-position/save-batch
    Body: {
        analysis_data: {           # 一键分析返回的完整数据
            market_analysis: {...},
            keyword_library: {...},
            problem_types: [...],
            portraits: [...],
            portraits_by_type: {...},
        },
        portrait_name: str,       # 画像名称（可选）
        set_as_default: bool,      # 是否设为默认（可选）
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    params = request.get_json() or {}
    analysis_data = params.get('analysis_data', {})
    portrait_name = params.get('portrait_name', '')
    set_as_default = params.get('set_as_default', False)

    if not analysis_data or not analysis_data.get('portraits'):
        return jsonify({
            'success': False,
            'message': '画像数据不能为空'
        }), 400

    from models.public_models import SavedPortrait

    # 检查保存数量限制
    current_count = SavedPortrait.query.filter_by(user_id=user.id).count()
    quota_info = quota_manager.get_user_quota_info(user)
    max_saved = quota_info.get('max_saved_portraits', 0)

    if max_saved > 0 and current_count >= max_saved:
        # 先删旧数据再插新数据（替换模式）
        SavedPortrait.query.filter_by(user_id=user.id).delete()
        db.session.commit()

    # 提取数据
    portraits = analysis_data.get('portraits', [])
    keyword_library = analysis_data.get('keyword_library', {})
    market_analysis = analysis_data.get('market_analysis', {})
    business_desc = ''

    # 如果只有一个画像，直接保存
    saved_portraits = []
    if len(portraits) == 1:
        portrait = portraits[0]

        # 生成画像名称
        if not portrait_name:
            portrait_name = f"{portrait.get('problem_type', '画像')}_{datetime.datetime.now().strftime('%m%d_%H%M')}"

        # 构建画像数据
        portrait_data = {
            'problem_type': portrait.get('problem_type', ''),
            'problem_type_description': portrait.get('problem_type_description', ''),
            'identity': portrait.get('identity', ''),
            'identity_description': portrait.get('identity_description', ''),
            'pain_points': portrait.get('pain_points', []),
            'pain_scenarios': portrait.get('pain_scenarios', []),
            'psychology': portrait.get('psychology', {}),
            'barriers': portrait.get('barriers', []),
            'search_keywords': portrait.get('search_keywords', []),
            'content_preferences': portrait.get('content_preferences', []),
            'market_type': portrait.get('market_type', 'blue_ocean'),
            'differentiation': portrait.get('differentiation', ''),
        }

        # 插入新记录
        new_portrait = SavedPortrait(
            user_id=user.id,
            portrait_data=portrait_data,
            portrait_name=portrait_name,
            keyword_library=keyword_library,
            business_description=business_desc,
            industry=market_analysis.get('subdivision_insights', {}).get('main_subdivision', ''),
            is_default=set_as_default,
        )
        db.session.add(new_portrait)
        db.session.commit()

        saved_portraits.append({
            'id': new_portrait.id,
            'portrait_name': portrait_name,
            'problem_type': portrait.get('problem_type', ''),
        })

    # 多个画像：按问题类型分组保存
    else:
        portraits_by_type = analysis_data.get('portraits_by_type', {})

        for problem_type, type_portraits in portraits_by_type.items():
            for i, portrait in enumerate(type_portraits):
                # 生成画像名称
                p_name = f"{problem_type}_{i+1}" if len(type_portraits) > 1 else problem_type

                # 构建画像数据
                portrait_data = {
                    'problem_type': portrait.get('problem_type', problem_type),
                    'problem_type_description': portrait.get('problem_type_description', ''),
                    'identity': portrait.get('identity', ''),
                    'identity_description': portrait.get('identity_description', ''),
                    'pain_points': portrait.get('pain_points', []),
                    'pain_scenarios': portrait.get('pain_scenarios', []),
                    'psychology': portrait.get('psychology', {}),
                    'barriers': portrait.get('barriers', []),
                    'search_keywords': portrait.get('search_keywords', []),
                    'content_preferences': portrait.get('content_preferences', []),
                    'market_type': portrait.get('market_type', 'blue_ocean'),
                    'differentiation': portrait.get('differentiation', ''),
                }

                # 插入新记录（只给第一个设默认）
                new_portrait = SavedPortrait(
                    user_id=user.id,
                    portrait_data=portrait_data,
                    portrait_name=p_name,
                    keyword_library=keyword_library,  # 关键词库共享
                    business_description=business_desc,
                    industry=market_analysis.get('subdivision_insights', {}).get('main_subdivision', ''),
                    is_default=(set_as_default and i == 0),
                )
                db.session.add(new_portrait)
                db.session.commit()

                saved_portraits.append({
                    'id': new_portrait.id,
                    'portrait_name': p_name,
                    'problem_type': problem_type,
                })

    logger.info(
        "[api_save_portrait_batch] 保存成功: user_id=%s, portraits_count=%d",
        user.id, len(saved_portraits)
    )

    return jsonify({
        'success': True,
        'data': {
            'saved_count': len(saved_portraits),
            'portraits': saved_portraits,
            'keyword_library': keyword_library,
        },
        'message': f'成功保存 {len(saved_portraits)} 个画像'
    })


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


# =============================================================================
# Skill Bridge API（测试接口）
# =============================================================================

@public_bp.route('/api/skill-bridge/info', methods=['GET'])
def skill_bridge_info():
    """列出所有已加载的 Skill"""
    try:
        from services.skill_bridge import SkillBridge
        bridge = SkillBridge()
        skills = bridge.list_skills()
        info = {}
        for s in skills:
            info[s] = bridge.get_skill_info(s)
        return jsonify({'success': True, 'data': {'skills': info}})
    except Exception as e:
        logger.error(f"[SkillBridge] info 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/steps/<skill_name>', methods=['GET'])
def skill_bridge_steps(skill_name):
    """查看某个 Skill 的步骤列表"""
    try:
        from services.skill_bridge import SkillBridge
        bridge = SkillBridge()
        steps = bridge.get_skill_steps(skill_name)
        return jsonify({
            'success': True,
            'data': {
                'skill_name': skill_name,
                'steps': [{'id': s['id'], 'name': s['name'], 'order': s.get('order')} for s in steps]
            }
        })
    except Exception as e:
        logger.error(f"[SkillBridge] steps 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/execute/market-analyzer', methods=['POST'])
def skill_bridge_market_analyzer():
    """执行市场分析 Skill（行业7步诊断法）"""
    try:
        from services.skill_bridge import SkillBridge

        data = request.get_json() or {}
        business_description = data.get('business_description', '')
        industry = data.get('industry', '')
        business_type = data.get('business_type', 'b2c')
        service_scenario = data.get('service_scenario')
        max_steps = data.get('max_steps')
        skip_steps = data.get('skip_steps', [])

        if not industry:
            return jsonify({'success': False, 'message': 'industry 参数必填'}), 400

        def _execute():
            bridge = SkillBridge()
            return bridge.execute_market_analyzer(
                business_description=business_description,
                industry=industry,
                business_type=business_type,
                service_scenario=service_scenario,
                max_steps=max_steps,
                skip_steps=skip_steps,
            )

        result, timed_out = run_with_timeout(_execute, (), {}, timeout_seconds=120)

        if timed_out:
            return jsonify({'success': False, 'message': '处理超时，请减少步骤或稍后重试'}), 504

        return jsonify({
            'success': result.success,
            'data': {
                'skill_name': result.skill_name,
                'full_output': result.full_output,
                'steps': [
                    {
                        'step_id': s.step_id,
                        'success': s.success,
                        'duration_ms': s.duration_ms,
                        'warnings': s.validation_warnings,
                    }
                    for s in result.step_results
                ],
                'errors': result.errors,
                'total_duration_ms': result.total_duration_ms,
            }
        })

    except Exception as e:
        logger.error(f"[SkillBridge] market_analyzer 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/execute/keyword-library', methods=['POST'])
def skill_bridge_keyword_library():
    """执行关键词库生成 Skill"""
    try:
        from services.skill_bridge import SkillBridge

        data = request.get_json() or {}
        business_description = data.get('business_description', '')
        industry = data.get('industry', '')
        business_type = data.get('business_type', 'b2c')
        market_analyzer_output = data.get('market_analyzer_output', {})

        if not industry:
            return jsonify({'success': False, 'message': 'industry 参数必填'}), 400

        def _execute():
            bridge = SkillBridge()
            return bridge.execute_keyword_library(
                business_description=business_description,
                industry=industry,
                business_type=business_type,
                market_analyzer_output=market_analyzer_output if market_analyzer_output else None,
            )

        result, timed_out = run_with_timeout(_execute, (), {}, timeout_seconds=120)

        if timed_out:
            return jsonify({'success': False, 'message': '处理超时，请稍后重试'}), 504

        return jsonify({
            'success': result.success,
            'data': {
                'skill_name': result.skill_name,
                'full_output': result.full_output,
                'steps': [
                    {
                        'step_id': s.step_id,
                        'success': s.success,
                        'duration_ms': s.duration_ms,
                    }
                    for s in result.step_results
                ],
                'errors': result.errors,
                'total_duration_ms': result.total_duration_ms,
            }
        })

    except Exception as e:
        logger.error(f"[SkillBridge] keyword_library 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/reload', methods=['POST'])
def skill_bridge_reload():
    """热重载 Skill 配置"""
    try:
        from services.skill_bridge import SkillBridge

        data = request.get_json() or {}
        skill_name = data.get('skill_name')

        bridge = SkillBridge()
        bridge.reload(skill_name)

        return jsonify({
            'success': True,
            'message': f'配置已重载: {skill_name or "全部"}'
        })
    except Exception as e:
        logger.error(f"[SkillBridge] reload 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/content-quality-optimize', methods=['POST'])
def skill_bridge_content_quality_optimize():
    """
    手动触发图文内容质量评估与优化。

    请求格式：
    {
        "generation_id": 123,   // 可选，有则更新已有记录
        "content_data": {...}   // 图文内容数据（来自 step_generate_content 的 content）
    }

    触发 SkillBridge 的 step_quality_validate 进行质量评分，
    返回评分结果和优化建议。
    """
    from services.skill_bridge import SkillBridge
    from models.public_models import PublicGeneration

    params = request.get_json() or {}
    content_data = params.get('content_data', {})
    generation_id = params.get('generation_id')

    if not content_data:
        return jsonify({'success': False, 'message': '缺少 content_data'}), 400

    try:
        bridge = SkillBridge()

        # 手动触发 quality_validate：
        # 1. 把 content_data 伪装成 step_generate_content 的输出（跳过内容生成）
        # 2. 只跑 step_quality_validate
        fo_fake = {'step_generate_content': content_data}
        result = bridge._executor.execute_skill(
            'content_generator',
            manual_inputs={},
            skip_steps=['step_generate_content'],
            _full_output_preset=fo_fake,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f'质量评估失败: {result.errors[0] if result.errors else "未知错误"}'
            }), 500

        qv_output = result.full_output.get('step_quality_validate', {})
        qv_inner = qv_output.get('quality_validation', qv_output)

        quality_score = qv_inner.get('quality_score', 0)
        dimension_scores = qv_inner.get('dimension_scores', {})
        failed_dims = qv_inner.get('failed_dimensions', [])
        suggestions = qv_inner.get('improvement_suggestions', [])

        # 构建报告
        items = []
        failed_items = []
        for dim, score_info in (dimension_scores.items() if isinstance(dimension_scores, dict) else []):
            if isinstance(score_info, dict):
                sr = score_info.get('score', 10)
                sv = int(float(sr)) if sr else 0
                pr = score_info.get('passed')
                passed = bool(pr) if pr is not None else sv >= 8
                items.append({'dimension': dim, 'score': sv, 'passed': passed})
                if not passed:
                    failed_items.append(dim)

        grade = 'F'
        if quality_score >= 90:
            grade = 'A'
        elif quality_score >= 80:
            grade = 'B'
        elif quality_score >= 70:
            grade = 'C'
        elif quality_score >= 60:
            grade = 'D'

        quality_report = {
            'total_score': quality_score,
            'grade': grade,
            'grade_label': '',
            'passed': quality_score >= 80,
            'optimized': True,
            'first_score': quality_score,
            'final_score': quality_score,
            'optimized_items': [],
            'items': items,
            'summary': '',
            'suggestions': suggestions,
            'failed_items': failed_items,
            'need_optimize': quality_score < 80,
        }

        # 如果有 generation_id，更新数据库记录
        if generation_id:
            try:
                gen = PublicGeneration.query.get(generation_id)
                if gen:
                    gen.quality_score = quality_score
                    gen.quality_report = quality_report
                    db.session.commit()
            except Exception as db_err:
                logger.warning(f"[QualityOptimize] 更新记录失败: {db_err}")

        return jsonify({
            'success': True,
            'quality_report': quality_report,
            'quality_score': quality_score,
            'grade': grade,
            'failed_items': failed_items,
            'suggestions': suggestions,
            'items': items,
        })

    except Exception as e:
        logger.error(f"[SkillBridge] content_quality_optimize 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500



@public_bp.route('/api/skill-bridge/execute/topic-library', methods=['POST'])
def skill_bridge_topic_library():
    """执行选题库生成 Skill"""
    try:
        from services.skill_bridge import SkillBridge

        data = request.get_json() or {}
        industry = data.get('industry', '')
        business_description = data.get('business_description', '')
        content_stage = data.get('content_stage', '成长阶段')
        keyword_library_output = data.get('keyword_library_output', {})
        market_analyzer_output = data.get('market_analyzer_output', {})

        if not industry:
            return jsonify({'success': False, 'message': 'industry 参数必填'}), 400

        def _execute():
            bridge = SkillBridge()
            return bridge.execute_topic_library(
                industry=industry,
                business_description=business_description,
                keyword_library_output=keyword_library_output if keyword_library_output else None,
                market_analyzer_output=market_analyzer_output if market_analyzer_output else None,
                content_stage=content_stage,
            )

        result, timed_out = run_with_timeout(_execute, (), {}, timeout_seconds=180)

        if timed_out:
            return jsonify({'success': False, 'message': '处理超时，请减少步骤或稍后重试'}), 504

        return jsonify({
            'success': result.success,
            'data': {
                'skill_name': result.skill_name,
                'full_output': result.full_output,
                'steps': [
                    {
                        'step_id': s.step_id,
                        'success': s.success,
                        'duration_ms': s.duration_ms,
                    }
                    for s in result.step_results
                ],
                'errors': result.errors,
                'total_duration_ms': result.total_duration_ms,
            }
        })

    except Exception as e:
        logger.error(f"[SkillBridge] topic_library 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@public_bp.route('/api/skill-bridge/execute/full-pipeline', methods=['POST'])
def skill_bridge_full_pipeline():
    """执行完整流水线：市场分析 → 关键词库 → 选题库"""
    try:
        from services.skill_bridge import SkillBridge

        data = request.get_json() or {}
        industry = data.get('industry', '')
        business_description = data.get('business_description', '')
        business_type = data.get('business_type', 'b2c')
        service_scenario = data.get('service_scenario')
        content_stage = data.get('content_stage', '成长阶段')

        if not industry:
            return jsonify({'success': False, 'message': 'industry 参数必填'}), 400

        def _execute():
            bridge = SkillBridge()
            return bridge.execute_full_pipeline(
                industry=industry,
                business_description=business_description,
                business_type=business_type,
                service_scenario=service_scenario,
                content_stage=content_stage,
            )

        result, timed_out = run_with_timeout(_execute, (), {}, timeout_seconds=300)

        if timed_out:
            return jsonify({'success': False, 'message': '流水线执行超时，请减少步骤或分步执行'}), 504

        return jsonify({
            'success': True,
            'data': {
                'market_analyzer': {
                    'success': result['market_analyzer'].success,
                    'full_output': result['market_analyzer'].full_output,
                    'errors': result['market_analyzer'].errors,
                },
                'keyword_library': {
                    'success': result['keyword_library'].success,
                    'full_output': result['keyword_library'].full_output,
                    'errors': result['keyword_library'].errors,
                },
                'topic_library': {
                    'success': result['topic_library'].success,
                    'full_output': result['topic_library'].full_output,
                    'errors': result['topic_library'].errors,
                },
            }
        })

    except Exception as e:
        logger.error(f"[SkillBridge] full_pipeline 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
