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


@public_bp.route('/galaxy')
def galaxy_page():
    """星系内容宇宙 - 可视化页面"""
    return render_template('public/galaxy.html')


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
        portrait_name = f"画像_{datetime.now().strftime('%m%d_%H%M')}"

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
            args=(portrait_id, user.id, plan_type),
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

    # 类别关键词
    if keyword_library.get('categories'):
        for cat in keyword_library['categories']:
            cat_name = cat.get('name', '未分类')
            keywords = cat.get('keywords', [])
            md_lines.append(f"## {cat_name}")
            md_lines.append("")
            for kw in keywords:
                md_lines.append(f"- {kw}")
            md_lines.append("")

    # 蓝海词
    if keyword_library.get('blue_ocean'):
        md_lines.append("## 蓝海关键词")
        md_lines.append("")
        for kw in keyword_library['blue_ocean']:
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
        raw_scene = params.get('selected_scene')  # 前端传来的第一个场景
        effective_scene = raw_scene  # 默认用前端指定的场景

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
                    portrait_id_val = params.get('portrait_id')
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

        # 获取内容类型和风格参数
        content_style = params.get('content_style', '')

        # 根据内容类型调用不同的生成器
        if content_type == 'short_video':
            # 短视频脚本生成
            from services.video_script_generator import VideoScriptGenerator
            video_gen = VideoScriptGenerator()
            result = video_gen.generate_content(
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                business_description=params.get('business_description', ''),
                portrait=params.get('portrait', {}),
                content_style=content_style,
            )
            result_type = 'short_video'
        elif content_type == 'long_text':
            # 长文生成
            from services.long_text_generator import LongTextGenerator
            longtext_gen = LongTextGenerator()
            result = longtext_gen.generate_content(
                topic_title=params.get('topic_title', ''),
                topic_type=params.get('topic_type', ''),
                business_description=params.get('business_description', ''),
                portrait=params.get('portrait', {}),
                content_style=content_style,
            )
            result_type = 'long_text'
        else:
            # 图文生成（默认）
            generator = TopicContentGenerator()
            logger.info(f"[GEO调试] selected_scene: {effective_scene}")
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
                selected_scene=effective_scene,
            )
            result_type = 'graphic'

        if result.get('success'):
            # ═══════════════════════════════════════════════════════════════
            # 内容质量评分（首次评分，不优化）
            # ═══════════════════════════════════════════════════════════════
            content = result.get('content', '')
            brand_name = params.get('portrait', {}).get('brand_name', '') or params.get('business_description', '')[:10]
            business_desc = params.get('business_description', '')

            # 首次评分（content 可能是 str 或 dict）
            from services.content_quality_scorer import content_scorer
            if isinstance(content, str):
                score_result = content_scorer.score_text(content, brand_name, content_type=result_type)
            else:
                score_result = content_scorer.score(content, brand_name)
            first_score = score_result.total_score

            quality_report = {
                'total_score': first_score,
                'grade': score_result.grade,
                'grade_label': score_result.grade_label,
                'passed': score_result.passed,
                'optimized': False,
                'first_score': first_score,
                'final_score': first_score,
                'optimized_items': [],
                'items': content_scorer.to_dict(score_result)['items'],
                'summary': score_result.summary,
                'suggestions': score_result.suggestions,
                'failed_items': [item.name for item in score_result.failed_items] if hasattr(score_result, 'failed_items') else [],
                'need_optimize': not score_result.passed,
            }

            # ═══════════════════════════════════════════════════════════════
            # 后续逻辑保持不变...
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

            # ── 从 content 中提取标题（兼容图文和长文两种结构）──
            # 图文内容：title 在 content 顶层
            # 长文内容：title 在 content.article 中，body 为 markdown 文本
            raw_content = result.get('content') if isinstance(result.get('content'), dict) else {}
            if isinstance(raw_content, dict):
                extracted_title = raw_content.get('title', '') or (raw_content.get('article', {}) or {}).get('title', '') or ''
                # 长文的标签在 article.hashtags
                extracted_tags = raw_content.get('tags', []) or (raw_content.get('article', {}) or {}).get('hashtags', []) or []
                extracted_geo = raw_content.get('geo_mode', '')
            else:
                extracted_title = ''
                extracted_tags = []
                extracted_geo = ''

            # ── 保存 generation 记录 ──
            generation = PublicGeneration(
                user_id=user.id if user else None,
                industry=params.get('business_type', ''),
                target_customer=params.get('portrait', {}).get('identity', ''),
                content_type=result_type,
                titles=[extracted_title],
                tags=extracted_tags,
                content_data=raw_content,
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
                quality_score=quality_report.get('final_score', 0) if quality_report else 0,
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
    logger.info(f"[ContentDetail] generation_id={generation_id}, raw quality_score={raw_result.get('quality_score')}, "
                f"raw quality_report type={type(raw_result.get('quality_report')).__name__ if raw_result.get('quality_report') else None}, "
                f"raw content_data keys={list((raw_result.get('content_data') or {}).keys()) if raw_result.get('content_data') else None}")

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
        problem_types = [
            {
                'type_name': p.type_name,
                'description': p.description,
                'target_audience': p.target_audience,
                'keywords': p.keywords,
            }
            for p in analysis_result.problem_types
        ]
        market_opportunities = [
            {
                'opportunity_name': o.opportunity_name,
                'business_direction': getattr(o, 'business_direction', ''),
                'target_audience': o.target_audience,
                'pain_points': o.pain_points,
                'keywords': o.keywords,
                'content_direction': o.content_direction,
                'market_type': o.market_type,
                'confidence': o.confidence,
                'differentiation': getattr(o, 'differentiation', ''),
            }
            for o in analysis_result.market_opportunities
        ]

        # 构建画像生成上下文
        context = PortraitGenerationContext(
            keyword_library=keyword_library,
            problem_types=problem_types,
            business_info=business_info,
            market_opportunities=market_opportunities,
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
            f"问题类型={len(problem_types)}, 画像={len(portraits_data)}, "
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
                'problem_types': problem_types,
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

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
    }

    logger.info(f"[api_market_analyze] 开始市场分析: {business_description[:50]}")

    try:
        analyzer = MarketAnalyzer()
        result = analyzer.analyze(
            business_info=business_info,
            max_opportunities=5,
            max_keywords=200,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"市场分析失败: {result.error_message}"
            }), 500

        # 转换蓝海机会格式
        market_opportunities = [
            {
                'opportunity_name': o.opportunity_name,
                'business_direction': getattr(o, 'business_direction', ''),
                'target_audience': o.target_audience,
                'pain_points': o.pain_points,
                'keywords': o.keywords,
                'content_direction': o.content_direction,
                'market_type': o.market_type,
                'confidence': o.confidence,
                'differentiation': getattr(o, 'differentiation', ''),
            }
            for o in result.market_opportunities
        ]

        # 关键词统计
        blue_count = result.blue_ocean_keywords
        red_count = result.red_ocean_keywords
        total = result.total_keywords
        blue_ratio = (blue_count / total * 100) if total > 0 else 0

        logger.info(f"[api_market_analyze] 分析完成: 发现 {len(market_opportunities)} 个蓝海机会")

        return jsonify({
            'success': True,
            'data': {
                'opportunities': market_opportunities,
                'subdivision_insights': result.subdivision_insights,
                'keyword_stats': {
                    'total': total,
                    'blue_ocean': blue_count,
                    'red_ocean': red_count,
                    'blue_ratio': round(blue_ratio, 1),
                },
                # 保存分析结果用于后续画像生成
                '_analysis_result': {
                    'keyword_library': result.keyword_library,
                    'problem_types': [
                        {
                            'type_name': p.type_name,
                            'description': p.description,
                            'target_audience': p.target_audience,
                            'keywords': p.keywords,
                        }
                        for p in result.problem_types
                    ],
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

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
    }

    logger.info(f"[api_market_analyze_opportunities] Step 1: 挖掘蓝海机会: {business_description[:50]}")

    try:
        analyzer = MarketAnalyzer()
        result = analyzer.analyze_opportunities(
            business_info=business_info,
            max_opportunities=5,
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
                'subdivision_insights': result['subdivision_insights'],
            }
        })

    except Exception as e:
        logger.error(f"[api_market_analyze_opportunities] 异常: {e}\n{tb_module.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'分析异常: {str(e)}'
        }), 500


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
        business_direction: str,    # 用户选择的蓝海业务方向
    }

    Response: {
        success: True,
        data: {
            keyword_library: {...},   # 关键词库
            problem_types: [...],     # 问题类型
            keyword_stats: {...},     # 关键词统计
        }
    }
    """
    from services.keyword_library_generator import KeywordLibraryGenerator

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    business_description = data.get('business_description', '').strip()
    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    business_direction = data.get('business_direction', '').strip()

    if not business_description:
        return jsonify({
            'success': False,
            'message': '请输入业务描述'
        }), 400

    if not business_direction:
        return jsonify({
            'success': False,
            'message': '请选择或输入业务方向'
        }), 400

    business_info = {
        'business_description': business_description,
        'industry': industry,
        'business_type': business_type,
    }

    logger.info(f"[api_generate_keyword_library] Step 2: 生成关键词库: {business_direction}")

    try:
        generator = KeywordLibraryGenerator()
        result = generator.generate(
            business_info=business_info,
            business_direction=business_direction,
            max_keywords=200,
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"生成失败: {result.error_message}"
            }), 500

        logger.info(f"[api_generate_keyword_library] Step 2 完成: {result.total_keywords} 个关键词")

        return jsonify({
            'success': True,
            'data': {
                'keyword_library': result.keyword_library,
                'problem_types': [
                    {
                        'type_name': p.type_name,
                        'description': p.description,
                        'target_audience': p.target_audience,
                        'keywords': p.keywords,
                        'scene_keywords': p.scene_keywords,  # 场景关键词，用于选题扩展
                    }
                    for p in result.problem_types
                ],
                'keyword_stats': {
                    'total': result.total_keywords,
                    'blue_ocean': result.blue_ocean_keywords,
                    'red_ocean': result.red_ocean_keywords,
                    'blue_ratio': round(result.blue_ocean_keywords / result.total_keywords * 100, 1) if result.total_keywords > 0 else 0,
                }
            }
        })

    except Exception as e:
        logger.error(f"[api_generate_keyword_library] 异常: {e}\n{tb_module.format_exc()}")
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
        portraits_per_type: int,          # 每个问题类型生成的画像数
    }
    """
    from services.portrait_generator import (
        PortraitGenerator,
        PortraitGenerationContext,
        group_portraits_by_problem_type,
    )

    logger = logging.getLogger(__name__)

    data = request.get_json() or {}
    core_business = data.get('core_business', '').strip()
    original_business = data.get('original_business', '').strip()
    industry = data.get('industry', '')
    business_type = data.get('business_type', 'product')
    service_scenario = data.get('service_scenario', 'other')
    analysis_result = data.get('analysis_result', {})
    portraits_per_type = data.get('portraits_per_type', 3)

    if not core_business:
        return jsonify({
            'success': False,
            'message': '请选择或输入核心业务'
        }), 400

    # 构建业务信息
    business_info = {
        'business_description': core_business,  # 使用用户选择的蓝海方向
        'industry': industry,
        'business_type': business_type,
        'service_scenario': service_scenario,
    }

    logger.info(f"[api_portraits_generate] 开始生成画像: {core_business}")

    try:
        generator = PortraitGenerator()

        # 获取分析结果数据
        keyword_library = analysis_result.get('keyword_library', {})
        problem_types = analysis_result.get('problem_types', [])
        market_opportunities = analysis_result.get('market_opportunities', [])

        # 如果没有传入 market_opportunities，从 analysis_result 的顶层获取
        if not market_opportunities:
            # 从 _analysis_result 中获取
            internal_result = analysis_result.get('_analysis_result', {})
            problem_types = internal_result.get('problem_types', problem_types)

        context = PortraitGenerationContext(
            keyword_library=keyword_library,
            problem_types=problem_types,
            business_info=business_info,
            market_opportunities=market_opportunities,
            portraits_per_type=portraits_per_type,
        )

        # 生成画像
        portraits = generator.generate_portraits(context)

        # 转换画像格式
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

        # 按问题类型分组
        portraits_by_type = group_portraits_by_problem_type(portraits_data)

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
            portrait_name = f"{portrait.get('problem_type', '画像')}_{datetime.now().strftime('%m%d_%H%M')}"

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

