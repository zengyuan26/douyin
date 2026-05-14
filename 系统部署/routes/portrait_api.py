"""
画像管理API路由

功能：
1. 保存/删除画像
2. 查看已保存画像
3. 切换画像（含频率控制）
4. 画像统计
"""

import json
import logging
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from flask_login import current_user
from functools import wraps
import re
from services.portrait_save_service import portrait_save_service
from services.scene_generator import scene_generator
from services.portrait_frequency_controller import portrait_frequency_controller
from services.portrait_library_task_service import generate_with_semaphore
from services.temperature_word_library import temperature_word_library
from models.public_models import PublicUser, SavedPortrait, TopicGenerationLink, PublicGeneration
from models.models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)





portrait_bp = Blueprint('portrait', __name__, url_prefix='/public/api/portraits')


def get_current_user():
    """获取当前登录用户，支持两种 session 路径"""
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


def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(user, *args, **kwargs)
    return decorated_function


@portrait_bp.route('/save', methods=['POST'])
@login_required
def save_portrait(user):
    """
    保存画像（立即返回，词库后台异步生成）

    返回体新增 generation_status 字段，前端可据此展示真实状态：
    - pending：待生成（免费用户）
    - generating：生成中（付费用户，后台线程正在生成）
    - completed：已完成（付费用户）
    - failed：失败（付费用户）
    """
    data = request.get_json() or {}

    portrait_data = data.get('portrait_data', {})
    portrait_name = data.get('portrait_name')
    business_description = data.get('business_description')
    industry = data.get('industry')
    target_customer = data.get('target_customer')
    source_session_id = data.get('source_session_id')
    set_as_default = data.get('set_as_default', False)
    customer_id = data.get('customer_id')  # 客户关联ID

    # 调试日志
    current_app.logger.info("[save_portrait] business_description=%s, industry=%s, target_customer=%s, customer_id=%s",
        business_description, industry, target_customer, customer_id)
    current_app.logger.info("[save_portrait] portrait_data keys=%s", list(portrait_data.keys()) if isinstance(portrait_data, dict) else type(portrait_data))

    # #region agent_debug_log
    try:
        _log_path = "/Volumes/增元/项目/douyin/.cursor/debug.log"
        _entry = {
            "hypothesisId": "H1_H2",
            "location": "portrait_api.py:75",
            "message": "save endpoint received portrait_data from frontend",
            "data": {
                "portrait_data_keys": list(portrait_data.keys()) if isinstance(portrait_data, dict) else str(type(portrait_data)),
                "pain_points": portrait_data.get('pain_points') if isinstance(portrait_data, dict) else None,
                "pain_scenarios": portrait_data.get('pain_scenarios') if isinstance(portrait_data, dict) else None,
                "barriers": portrait_data.get('barriers') if isinstance(portrait_data, dict) else None,
                "problem_type_description": portrait_data.get('problem_type_description') if isinstance(portrait_data, dict) else None,
                "identity": portrait_data.get('identity') if isinstance(portrait_data, dict) else None,
                "business_description": business_description,
                "target_customer": target_customer,
            },
            "timestamp": __import__("time").time(),
        }
        with open(_log_path, "a", encoding="utf-8") as _f:
            _f.write(__import__("json").dumps(_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

    success, message, saved = portrait_save_service.save_portrait(
        user_id=user.id,
        portrait_data=portrait_data,
        portrait_name=portrait_name,
        business_description=business_description,
        industry=industry,
        target_customer=target_customer,
        source_session_id=source_session_id,
        set_as_default=set_as_default,
        customer_id=customer_id,
    )

    if not success:
        return jsonify({
            'success': False,
            'message': message
        }), 400

    portrait_id = saved.get('id')

    # 免费用户：不需要生成词库
    if not user.is_paid_user():
        # 更新 generation_status = completed（无需生成）
        if portrait_id:
            db.session.execute(
                text("UPDATE saved_portraits SET generation_status = 'completed' WHERE id = :id"),
                {'id': portrait_id}
            )
            db.session.commit()
        return jsonify({
            'success': True,
            'message': message,
            'data': saved,
        })

    # 付费用户：始终启动后台生成关键词库和选题库
    if portrait_id:
        db.session.execute(
            text("UPDATE saved_portraits SET generation_status = 'generating' WHERE id = :id"),
            {'id': portrait_id}
        )
        db.session.commit()

        # 启动后台线程生成词库（通过 Semaphore 控制 LLM 并发数）
        plan_type = user.premium_plan or 'basic'
        thread = threading.Thread(
            target=generate_with_semaphore,
            args=(portrait_id, user.id, plan_type),
            daemon=True
        )
        thread.start()
        logger.info("[save_portrait] 已提交词库生成任务 portrait_id=%s plan_type=%s", portrait_id, plan_type)

    return jsonify({
        'success': True,
        'message': message,
        'data': saved,
    })


@portrait_bp.route('/saved', methods=['GET'])
@login_required
def get_saved_portraits(user):
    """获取已保存的画像列表"""
    include_data = request.args.get('include_data', 'true').lower() == 'true'
    
    portraits = portrait_save_service.get_user_portraits(
        user.id, include_data=include_data
    )

    return jsonify({
        'success': True,
        'data': portraits,
        'total': len(portraits)
    })


@portrait_bp.route('/<int:portrait_id>', methods=['GET'])
@login_required
def get_portrait_detail(user, portrait_id):
    """获取画像详情"""
    owned, portrait = _check_portrait_ownership(portrait_id, user)
    if not owned:
        if not portrait:
            return jsonify({'success': False, 'message': '画像不存在'}), 404
        return jsonify({'success': False, 'message': '无权访问该画像'}), 403

    # 添加 user_id 到返回数据
    portrait['user_id'] = user.id

    return jsonify({'success': True, 'data': portrait})


@portrait_bp.route('/<int:portrait_id>/status', methods=['GET'])
@login_required
def get_portrait_status(user, portrait_id):
    """
    轻量化状态端点（轮询专用，仅返回生成状态字段）

    返回 generation_status：
    - pending：待生成（免费用户或异常情况）
    - generating：生成中
    - completed：已完成（词库已就绪）
    - failed：失败（带 generation_error）
    """
    owned, portrait = _check_portrait_ownership(portrait_id, user)
    if not owned:
        if not portrait:
            return jsonify({'success': False, 'message': '画像不存在'}), 404
        return jsonify({'success': False, 'message': '无权访问该画像'}), 403

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
            'id': portrait['id'],
            'generation_status': gen_status,
            'generation_error': gen_error,
            'keyword_library': portrait.get('keyword_library'),
            'keyword_updated_at': portrait.get('keyword_updated_at'),
            'keyword_cache_expires_at': portrait.get('keyword_cache_expires_at'),
            'topic_library': portrait.get('topic_library'),
            'topic_updated_at': portrait.get('topic_updated_at'),
            'topic_cache_expires_at': portrait.get('topic_cache_expires_at'),
        }
    })


def _check_portrait_ownership(portrait_id, user):
    """检查画像归属，返回 (owned: bool, portrait: dict or None)"""
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return False, portrait
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return False, portrait
    return True, portrait


@portrait_bp.route('/<int:portrait_id>', methods=['DELETE'])
@login_required
def delete_portrait(user, portrait_id):
    """删除画像"""
    success, message = portrait_save_service.delete_portrait(user.id, portrait_id)
    
    return jsonify({
        'success': success,
        'message': message
    })


@portrait_bp.route('/<int:portrait_id>/set-default', methods=['POST'])
@login_required
def set_default(user, portrait_id):
    """设为默认画像"""
    success, message = portrait_save_service.set_default_portrait(user.id, portrait_id)
    
    return jsonify({
        'success': success,
        'message': message
    })


@portrait_bp.route('/default', methods=['GET'])
@login_required
def get_default(user):
    """获取默认画像"""
    portrait = portrait_save_service.get_default_portrait(user.id)
    
    return jsonify({
        'success': True,
        'data': portrait
    })


@portrait_bp.route('/check-change', methods=['POST'])
@login_required
def check_change(user):
    """检查更换画像权限"""
    data = request.get_json() or {}
    change_type = data.get('change_type', 'generate_new')
    
    allowed, reason, quota = portrait_frequency_controller.check_change_permission(
        user.id, change_type
    )
    
    return jsonify({
        'success': True,
        'data': {
            'allowed': allowed,
            'reason': reason,
            'quota': quota
        }
    })


@portrait_bp.route('/change', methods=['POST'])
@login_required
def change_portrait(user):
    """更换画像"""
    data = request.get_json() or {}
    
    old_portrait_id = data.get('old_portrait_id')
    new_portrait_id = data.get('new_portrait_id')
    new_portrait_data = data.get('new_portrait_data')
    portrait_name = data.get('portrait_name')
    business_description = data.get('business_description')
    change_type = data.get('change_type', 'generate_new')
    
    success, message, portrait = portrait_save_service.switch_portrait(
        user_id=user.id,
        old_portrait_id=old_portrait_id,
        new_portrait_id=new_portrait_id,
        new_portrait_data=new_portrait_data,
        portrait_name=portrait_name,
        business_description=business_description,
        change_type=change_type
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'data': portrait
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


@portrait_bp.route('/stats', methods=['GET'])
@login_required
def get_stats(user):
    """获取画像统计"""
    stats = portrait_save_service.get_portrait_stats(user.id)
    
    return jsonify({
        'success': True,
        'data': stats
    })


@portrait_bp.route('/quota', methods=['GET'])
@login_required
def get_quota(user):
    """获取用户配额"""
    quota = portrait_frequency_controller.get_user_quota(user.id)

    return jsonify({
        'success': True,
        'data': quota
    })


# =============================================================================
# 画像专属库 API（关键词库 + 选题库）
# =============================================================================

@portrait_bp.route('/<int:portrait_id>/library', methods=['GET'])
@login_required
def get_portrait_library(user, portrait_id):
    """
    获取画像的专属关键词库和选题库
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    return jsonify({
        'success': True,
        'data': {
            'keyword_library': portrait.get('keyword_library'),
            'keyword_updated_at': portrait.get('keyword_updated_at'),
            'keyword_update_count': portrait.get('keyword_update_count', 0),
            'keyword_expired': _is_expired(portrait.get('keyword_cache_expires_at')),
            'topic_library': portrait.get('topic_library'),
            'topic_updated_at': portrait.get('topic_updated_at'),
            'topic_update_count': portrait.get('topic_update_count', 0),
            'topic_expired': _is_expired(portrait.get('topic_cache_expires_at')),
        }
    })


@portrait_bp.route('/<int:portrait_id>/library/generate', methods=['POST'])
@login_required
def generate_portrait_library(user, portrait_id):
    """
    生成/更新画像专属关键词库和选题库（受配额限制）
    """
    from sqlalchemy import text
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    # 检查 user_id（get_saved_portrait 返回的字典不含此字段，直接查数据库）
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    data = request.get_json() or {}
    library_type = data.get('library_type', 'all')  # keyword / topic / all

    # 检查付费状态
    if not user.is_paid_user():
        return jsonify({
            'success': False,
            'message': '此功能仅对付费用户开放'
        }), 403

    plan_type = user.premium_plan or 'basic'

    # 检查配额（关键词库+选题库合并为一次，用关键词库配额）
    results = {'keyword': None, 'topic': None}

    # 合并逻辑：只需检查关键词库配额，一次配额生成两个库
    allowed, reason, quota = portrait_frequency_controller.check_library_update_permission(
        user.id, 'keyword'
    )
    if not allowed:
        return jsonify({'success': False, 'message': reason, 'quota_info': quota}), 403

    # 构建业务信息
    portrait_data = portrait.get('portrait_data', {})
    business_info = {
        'business_description': portrait.get('business_description', ''),
        'industry': portrait.get('industry', ''),
        'products': [],
        'region': '',
        'target_customer': portrait.get('target_customer', ''),
    }

    try:
        # 生成关键词库（带缓存检查）
        if library_type in ('keyword', 'all'):
            from services.keyword_library_generator import keyword_library_generator
            kw_result = keyword_library_generator.generate(
                portrait_data=portrait_data,
                business_info=business_info,
                plan_type=plan_type,
                portrait_id=portrait_id,
            )
            if kw_result.get('success') and not kw_result.get('_meta', {}).get('from_cache'):
                keyword_library_generator.save_to_portrait(
                    portrait_id=portrait_id,
                    keyword_library=kw_result['keyword_library'],
                    user_id=user.id,
                    plan_type=plan_type,
                )
                # 合并模式：关键词库和选题库只扣一次关键词库配额
                portrait_frequency_controller.record_library_update(user.id, 'keyword')
            results['keyword'] = kw_result.get('keyword_library') or {}

        # 生成选题库（带缓存检查）
        if library_type in ('topic', 'all'):
            from services.topic_library_generator import topic_library_generator
            kw_library = results.get('keyword') or (keyword_library_generator.get_from_portrait(portrait_id) if library_type == 'topic' else {})
            topic_result = topic_library_generator.generate(
                portrait_data=portrait_data,
                business_info=business_info,
                keyword_library=kw_library,
                plan_type=plan_type,
                portrait_id=portrait_id,
                user_id=user.id,
            )
            if topic_result.get('success') and not topic_result.get('_meta', {}).get('from_cache'):
                topic_library_generator.save_to_portrait(
                    portrait_id=portrait_id,
                    topic_library=topic_result['topic_library'],
                    user_id=user.id,
                    plan_type=plan_type,
                )
                # 合并模式：选题库不单独扣配额，已在生成关键词库时扣过一次
                results['topic'] = topic_result['topic_library']

        # 获取更新后配额
        keyword_quota = portrait_frequency_controller.get_library_quota(user.id, 'keyword')
        topic_quota = portrait_frequency_controller.get_library_quota(user.id, 'topic')

        return jsonify({
            'success': True,
            'data': results,
            'quota': {
                'keyword': keyword_quota,
                'topic': topic_quota,
            }
        })

    except Exception as e:
        import traceback
        logger.error("[portrait_api] 生成失败: %s", e)
        logger.debug("[portrait_api] 堆栈: %s", traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/topics', methods=['GET'])
@login_required
def get_portrait_topics(user, portrait_id):
    """
    从专属选题库获取选题列表（分页版本）

    Query params:
        page: 页码，默认1
        per_page: 每页数量，默认10
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 5))
    stage_key_filter = request.args.get('stage_key', '')  # 五段式阶段筛选

    topic_library = portrait.get('topic_library')
    all_topics = []

    # 兼容新旧两种格式
    # 旧格式：topics 数组（每个元素是 dict，带 id/title/type 等字段）
    if topic_library and 'topics' in topic_library:
        all_topics = topic_library.get('topics', [])

    # 新格式：扁平字段（audience_lock_topics, pain_amplify_topics, ...）
    # 每个 section 里的元素可能是 dict{{}} 或字符串，需要统一转成带 id/title 的 dict
    if topic_library:
        sections = [
            topic_library.get('audience_lock_topics', []),
            topic_library.get('pain_amplify_topics', []),
            topic_library.get('solution_compare_topics', []),
            topic_library.get('vision_topics', []),
            topic_library.get('barrier_remove_topics', []),
            topic_library.get('direct_need_topics', []),
            topic_library.get('skill_tutorial_topics', []),
        ]
        new_format_topics = []
        for sec in sections:
            if isinstance(sec, list):
                for item in sec:
                    # dict：直接使用
                    if isinstance(item, dict):
                        new_format_topics.append(item)
                    # 字符串：转成带 id/title 的标准化 dict
                    elif isinstance(item, str):
                        topic_id = str(hash(item))  # 用内容 hash 做稳定 id
                        new_format_topics.append({
                            'id': topic_id,
                            'title': item,
                            'created_at': None,
                        })
        # 旧格式为空时才用新格式兜底
        if not all_topics and new_format_topics:
            all_topics = new_format_topics
        # 新格式始终补充（即使是 dict 格式也追加，避免遗漏）
        elif new_format_topics:
            existing_ids = {t.get('id') for t in all_topics if isinstance(t, dict) and t.get('id')}
            for t in new_format_topics:
                if t.get('id') not in existing_ids:
                    all_topics.append(t)

    logger.info("[get_portrait_topics] portrait_id=%s, 原始选题数量=%d", portrait_id, len(all_topics))

    # 按 created_at 倒序排列
    def sort_key(t):
        if isinstance(t, dict):
            created = t.get('created_at', '')
        else:
            created = ''
        return created if created else ''

    all_topics = sorted(all_topics, key=sort_key, reverse=True)

    # ── 五段式阶段筛选 ──
    if stage_key_filter:
        all_topics = [t for t in all_topics if isinstance(t, dict) and t.get('stage_key') == stage_key_filter]

    # 分页
    total = len(all_topics)
    start = (page - 1) * per_page
    end = start + per_page
    page_topics = all_topics[start:end]

    # ── 获取账号信息用于场景推荐 ──
    # 从运营规划中获取账号定位
    account_info = {}
    operation_plan = portrait.get('operation_plan') or {}
    extra_data = portrait.get('extra_data') or {}
    if not operation_plan and extra_data:
        operation_plan = extra_data.get('operations_plan', {})

    if operation_plan:
        account_info = {
            'account_positioning': operation_plan.get('account_positioning', ''),
            'brand_name': portrait.get('business_description', ''),
            'industry': portrait.get('industry', ''),
            'target_customer': portrait.get('target_customer', ''),
        }

    # ── 星系增强：补充 scene_options 和 content_style ──
    page_topics = scene_generator.enrich_topics_with_scene_options(page_topics, account_info=account_info)

    # ── 补充 link 信息（版本数量、使用次数）──
    topic_ids = [str(t.get('id')) for t in page_topics if isinstance(t, dict) and t.get('id')]
    if topic_ids and portrait_id:
        links = TopicGenerationLink.query.filter_by(
            portrait_id=portrait_id, user_id=user.id
        ).filter(TopicGenerationLink.topic_id.in_(topic_ids)).all()
        # topic_id 统一为字符串建 map，防止类型不一致导致匹配失败
        link_map = {str(l.topic_id): l for l in links}
        for t in page_topics:
            tid = str(t.get('id')) if isinstance(t, dict) and t.get('id') is not None else ''
            if tid and tid in link_map:
                link = link_map[tid]
                t['_link_id'] = link.id
                t['_usage_count'] = link.usage_count or 0
                t['_generation_ids'] = link.generation_ids or []
                # ── 同步 generation_count（取自 link usage_count）──
                t['generation_count'] = link.usage_count or 0

    # ── 补充业务名称（直接取超级定位中描述业务里的核心业务值）──
    business_name = (portrait.get('business_description') or '').strip()

    # 调试日志：检查 business_description 的实际值
    logger.info("[get_portrait_topics] portrait_id=%s, business_description=%r, business_name=%r",
        portrait_id, portrait.get('business_description'), business_name)
    logger.info("[get_portrait_topics] portrait_id=%s, 返回 topics=%d, total=%d",
        portrait_id, len(page_topics), total)
    if page_topics:
        for t in page_topics[:3]:
            logger.info("[get_portrait_topics]   topic: id=%r, title=%r",
                t.get('id'), t.get('title')[:30] if t.get('title') else None)

    for t in page_topics:
        if isinstance(t, dict):
            t['_business_name'] = business_name

    return jsonify({
        'success': True,
        'data': {
            'topics': page_topics,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page if per_page > 0 else 0,
            'portrait_id': portrait_id,
            'stage_key_filter': stage_key_filter,
            'by_stage': topic_library.get('by_stage') if topic_library else None,
        }
    })


@portrait_bp.route('/<int:portrait_id>/topics/quick', methods=['GET'])
@login_required
def get_portrait_topics_quick(user, portrait_id):
    """
    快速随机抽取选题（用于卡片悬停展示，抽取3条）

    Query params:
        count: 数量，默认3
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    count = int(request.args.get('count', 3))
    topic_library = portrait.get('topic_library')

    topics = []
    from_portrait = False

    # 兼容新旧两种格式
    # 旧格式：topics 数组
    if topic_library and 'topics' in topic_library:
        from services.topic_library_generator import topic_library_generator
        topics = topic_library_generator.select_topics(
            topic_library=topic_library,
            count=count,
        )
        from_portrait = True
    else:
        # 新格式：扁平字段（audience_lock_topics, pain_amplify_topics, ...）
        sections = [
            topic_library.get('audience_lock_topics', []) if topic_library else [],
            topic_library.get('pain_amplify_topics', []) if topic_library else [],
            topic_library.get('solution_compare_topics', []) if topic_library else [],
            topic_library.get('vision_topics', []) if topic_library else [],
            topic_library.get('barrier_remove_topics', []) if topic_library else [],
            topic_library.get('direct_need_topics', []) if topic_library else [],
            topic_library.get('skill_tutorial_topics', []) if topic_library else [],
        ]
        all_topics = []
        for sec in sections:
            if isinstance(sec, list):
                for item in sec:
                    # dict：直接使用
                    if isinstance(item, dict):
                        all_topics.append(item)
                    # 字符串：转成带 id/title 的标准化 dict
                    elif isinstance(item, str):
                        all_topics.append({
                            'id': str(hash(item)),
                            'title': item,
                        })
        import random
        topics = random.sample(all_topics, min(count, len(all_topics))) if all_topics else []
        from_portrait = bool(topics)

    # 获取核心业务词
    core_business = portrait.get('business_description', '').strip()
    keyword_library = portrait.get('keyword_library')
    if not core_business and keyword_library:
        # 兼容旧格式：categories
        if 'categories' in keyword_library:
            categories = keyword_library.get('categories', [])
            if categories and len(categories) > 0:
                first_cat = categories[0]
                keywords = first_cat.get('keywords', [])
                if keywords and len(keywords) > 0:
                    core_business = '、'.join(keywords[:3])
        # 兼容新格式：扁平字段
        if not core_business:
            for field in ['problem_type_keywords', 'pain_point_keywords', 'scene_keywords']:
                kws = keyword_library.get(field, [])
                if isinstance(kws, list) and len(kws) > 0:
                    core_business = '、'.join(kws[:3])
                    break

    return jsonify({
        'success': True,
        'data': {
            'topics': topics,
            'from_portrait_library': from_portrait,
            'has_topics': bool(topics),
            'portrait_id': portrait_id,
            'core_business': core_business,
        }
    })


@portrait_bp.route('/<int:portrait_id>/topics/<topic_id>/versions', methods=['GET'])
@login_required
def get_topic_versions(user, portrait_id, topic_id):
    """
    查询选题的所有内容版本

    Returns:
        选题基本信息 + 所有版本列表
    """
    # 权限校验
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    # 查找 link
    link = TopicGenerationLink.query.filter_by(
        portrait_id=portrait_id,
        topic_id=topic_id
    ).filter(
        TopicGenerationLink.user_id == user.id
    ).first()

    if not link:
        return jsonify({'success': True, 'data': {
            'topic_id': topic_id,
            'topic_title': None,
            'usage_count': 0,
            'versions': []
        }})

    # 查询所有版本
    gens = PublicGeneration.query.filter(
        PublicGeneration.link_id == link.id,
        PublicGeneration.user_id == user.id
    ).order_by(PublicGeneration.version_number.asc()).all()

    versions = [{
        'generation_id': g.id,
        'version_number': g.version_number,
        'content_type': g.content_type or 'graphic',
        'content_style': g.content_style or '',
        'geo_mode': g.geo_mode_used or '',
        'selected_scenes': g.selected_scenes,
        'title': (g.titles[0] if g.titles and isinstance(g.titles, list) else str(g.titles or '')),
        'tags': g.tags or [],
        'created_at': g.created_at.strftime('%Y-%m-%d %H:%M') if g.created_at else '',
    } for g in gens]

    return jsonify({'success': True, 'data': {
        'link_id': link.id,
        'topic_id': topic_id,
        'topic_title': link.topic_title or '',
        'geo_mode': link.geo_mode or '',
        'geo_mode_name': link.geo_mode_name or '',
        'usage_count': link.usage_count or 0,
        'first_generated_at': link.first_generated_at.strftime('%Y-%m-%d %H:%M') if link.first_generated_at else '',
        'last_generated_at': link.last_generated_at.strftime('%Y-%m-%d %H:%M') if link.last_generated_at else '',
        'versions': versions,
    }})


@portrait_bp.route('/<int:portrait_id>/topics/<topic_id>/generations', methods=['GET'])
@login_required
def get_topic_generations(user, portrait_id, topic_id):
    """
    查询选题已生成的内容列表（分页）

    Query params:
        page: 页码，默认1
        per_page: 每页数量，默认10

    Returns:
        分页内容列表
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    page = max(1, page)
    per_page = min(max(1, per_page), 50)

    # 权限校验
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    # 查找 link
    link = TopicGenerationLink.query.filter_by(
        portrait_id=portrait_id,
        topic_id=topic_id
    ).filter(
        TopicGenerationLink.user_id == user.id
    ).first()

    if not link:
        return jsonify({'success': True, 'data': {
            'generations': [],
            'total': 0,
            'pages': 0,
            'page': page,
        }})

    # 分页查询
    query = PublicGeneration.query.filter(
        PublicGeneration.link_id == link.id,
        PublicGeneration.user_id == user.id
    ).order_by(PublicGeneration.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    generations = [{
        'id': g.id,
        'content_type': g.content_type or 'graphic',
        'content_style': g.content_style or '',
        'title': (g.titles[0] if g.titles and isinstance(g.titles, list) else str(g.titles or '')),
        'tags': g.tags or [],
        'created_at': g.created_at.isoformat() if g.created_at else None,
    } for g in pagination.items]

    return jsonify({'success': True, 'data': {
        'generations': generations,
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    }})


@portrait_bp.route('/<int:portrait_id>/topics/regenerate', methods=['POST'])
@login_required
def regenerate_portrait_topics(user, portrait_id):
    """
    重新生成画像专属选题库（增量：保留原有选题，新增一批新选题）

    Body: {
        count: 新增数量，默认10
        content_stage: 内容阶段（起号阶段/成长阶段/成熟阶段），默认成长阶段
    }
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    data = request.get_json() or {}
    extra_count = int(data.get('count', 5))
    content_stage = data.get('content_stage', '成长阶段')

    # 所有用户都可以重新生成选题（无付费限制）

    portrait_data = portrait.get('portrait_data', {})
    business_info = {
        'business_description': portrait.get('business_description', ''),
        'industry': portrait.get('industry', ''),
        'products': [],
        'region': '',
        'target_customer': portrait.get('target_customer', ''),
    }
    plan_type = user.premium_plan or 'basic'

    try:
        # 获取现有选题库
        topic_library = portrait.get('topic_library') or {}
        existing_topics = topic_library.get('topics', [])

        # 获取关键词库（用于选题生成参考）
        keyword_library = portrait.get('keyword_library')

        # 生成新增选题（传入内容阶段）
        from services.topic_library_generator import topic_library_generator
        result = topic_library_generator.generate(
            portrait_data=portrait_data,
            business_info=business_info,
            keyword_library=keyword_library,
            plan_type=plan_type,
            topic_count=extra_count,
            portrait_id=portrait_id,
            content_stage=content_stage,
            user_id=user.id,
        )

        if not result.get('success'):
            return jsonify({
                'success': False,
                'message': result.get('error', '选题生成失败')
            }), 500

        new_topics = result.get('topic_library', {}).get('topics', [])

        # 合并：保留原有 + 新增
        merged_topics = existing_topics + new_topics
        topic_library['topics'] = merged_topics
        topic_library['generated_at'] = datetime.utcnow().isoformat()

        # 更新 by_stage 统计
        topic_library['by_stage'] = topic_library_generator._count_by_stage(merged_topics)

        # 保存
        topic_library_generator.save_to_portrait(
            portrait_id=portrait_id,
            topic_library=topic_library,
            user_id=user.id,
            plan_type=plan_type,
        )

        return jsonify({
            'success': True,
            'data': {
                'total': len(merged_topics),
                'new_count': len(new_topics),
                'existing_count': len(existing_topics),
                'by_stage': topic_library.get('by_stage', {}),
            }
        })

    except Exception as e:
        import traceback
        logger.error("[regenerate_topics] 异常: %s", e)
        logger.debug("[regenerate_topics] 堆栈: %s", traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/topics/increment', methods=['POST'])
@login_required
def increment_topic_generation_count(user, portrait_id):
    """
    选题生成次数+1（当内容生成完成后调用）

    Body: {
        topic_id: 选题UUID字符串
    }
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    data = request.get_json() or {}
    topic_id = data.get('topic_id')

    if not topic_id:
        return jsonify({'success': False, 'message': '缺少 topic_id'}), 400

    topic_library = portrait.get('topic_library') or {}

    # 从旧格式 topics 数组中查找
    topics = topic_library.get('topics', [])
    found = False
    for topic in topics:
        if topic.get('id') == topic_id:
            topic['generation_count'] = topic.get('generation_count', 0) + 1
            found = True
            break

    # 从新格式扁平字段中查找
    if not found:
        flat_sections = [
            'audience_lock_topics', 'pain_amplify_topics', 'solution_compare_topics',
            'vision_topics', 'barrier_remove_topics', 'direct_need_topics', 'skill_tutorial_topics',
        ]
        for section_key in flat_sections:
            section = topic_library.get(section_key, [])
            for topic in section:
                if isinstance(topic, dict) and topic.get('id') == topic_id:
                    topic['generation_count'] = topic.get('generation_count', 0) + 1
                    found = True
                    break
            if found:
                break

    if not found:
        return jsonify({'success': False, 'message': '选题不存在'}), 404

    portrait_model = SavedPortrait.query.get(portrait_id)
    if portrait_model:
        portrait_model.topic_library = topic_library
        db.session.commit()

    return jsonify({'success': True})


@portrait_bp.route('/library/quota', methods=['GET'])
@login_required
def get_library_quota(user):
    """
    获取关键词库/选题库的配额信息
    """
    keyword_quota = portrait_frequency_controller.get_library_quota(user.id, 'keyword')
    topic_quota = portrait_frequency_controller.get_library_quota(user.id, 'topic')

    return jsonify({
        'success': True,
        'data': {
            'keyword': keyword_quota,
            'topic': topic_quota,
        }
    })


# =============================================================================
# 运营规划 API
# =============================================================================

@portrait_bp.route('/<int:portrait_id>/client-profile', methods=['GET'])
@login_required
def get_client_profile(user, portrait_id):
    """
    获取画像的客户自定义信息
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 403

    return jsonify({
        'success': True,
        'data': {
            'client_profile': portrait.get('client_profile'),
            'has_client_profile': bool(portrait.get('client_profile')),
        }
    })


@portrait_bp.route('/<int:portrait_id>/client-profile', methods=['POST'])
@login_required
def save_client_profile(user, portrait_id):
    """
    保存画像的客户自定义信息
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 403

    data = request.get_json() or {}
    client_profile = data.get('client_profile', {})

    # 验证必填字段
    if not client_profile.get('brand_name'):
        return jsonify({
            'success': False,
            'message': '请填写品牌名称'
        }), 400

    success = portrait_save_service.save_client_profile(portrait_id, client_profile)
    if not success:
        return jsonify({
            'success': False,
            'message': '保存失败'
        }), 500

    return jsonify({
        'success': True,
        'message': '客户信息保存成功',
        'data': {
            'client_profile': client_profile
        }
    })


@portrait_bp.route('/<int:portrait_id>/generate-operations', methods=['POST'])
@login_required
def generate_operations_from_client_info(user, portrait_id):
    """
    从客户信息页触发生成运营规划（基于新的 operations_planner）
    流程：画像数据 + 客户录入信息 → 运营规划
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 403

    try:
        from services.operations_planner import generate_operations_plan

        # 获取画像数据
        business_description = portrait.get('business_description', '')
        portrait_name = portrait.get('portrait_name', '') or portrait.get('industry', '')
        industry = portrait.get('industry', '')
        target_customer = portrait.get('target_customer', '')

        # 获取画像列表
        portraits_data = portrait.get('portraits', []) or []
        if not portraits_data and portrait.get('portrait_data'):
            portraits_data = [portrait.get('portrait_data')]

        # 获取客户自定义信息
        client_profile = portrait.get('client_profile') or {}

        # 构建业务信息
        business_info = {
            'business_name': client_profile.get('brand_name', '') or portrait_name,
            'business_description': business_description,
            'industry': industry,
            'target_customer': client_profile.get('target_audience', '') or target_customer,
        }

        # 生成运营规划
        operation_plan = generate_operations_plan(
            portraits=portraits_data,
            business_info=business_info,
            content_stage='起号阶段',
            target_topic_count=5,
            client_profile=client_profile,
        )

        # 保存到画像
        portrait_model = SavedPortrait.query.get(portrait_id)
        if portrait_model:
            portrait_model.operation_plan = operation_plan
            portrait_model.operation_plan_updated_at = datetime.utcnow()
            db.session.commit()

        logger.info("[generate_operations] portrait_id=%s, 生成成功", portrait_id)

        return jsonify({
            'success': True,
            'message': '运营规划生成成功',
            'data': {
                'operation_plan': operation_plan,
                'operation_plan_updated_at': datetime.utcnow().isoformat(),
            }
        })

    except Exception as e:
        logger.exception("[generate_operations] portrait_id=%s, 生成失败: %s", portrait_id, str(e))
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/operation-plan', methods=['GET'])
@login_required
def get_operation_plan(user, portrait_id):
    """
    获取画像的运营规划方案
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    # 优先从 extra_data 读取（新版存储位置），回退到 operation_plan 字段（旧版兼容）
    operation_plan = portrait.get('operation_plan')
    updated_at = portrait.get('operation_plan_updated_at')
    extra_data = portrait.get('extra_data') or {}
    if not operation_plan and extra_data:
        operation_plan = extra_data.get('operations_plan', {})
        updated_at = extra_data.get('operations_plan_updated_at', None)

    return jsonify({
        'success': True,
        'data': {
            'operation_plan': operation_plan,
            'operation_plan_updated_at': updated_at,
            'has_operation_plan': bool(operation_plan),
        }
    })


@portrait_bp.route('/<int:portrait_id>/operation-plan/generate', methods=['POST'])
@login_required
def generate_operation_plan(user, portrait_id):
    """
    生成/更新画像的运营规划方案
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    try:
        from services.skill_bridge import SkillBridge
        bridge = SkillBridge()

        # 获取画像数据
        business_description = portrait.get('business_description', '')
        industry = portrait.get('industry', '')

        # 判断业务类型（简化：从业务描述推断）
        business_type = 'b2c'
        if any(kw in business_description.lower() for kw in ['企业', '批发', '代理', '加盟', 'B端', 'B2B']):
            business_type = 'b2b'
        elif any(kw in business_description.lower() for kw in ['零售', 'to c', 'toc', '个人', '家庭']):
            business_type = 'b2c'
        else:
            business_type = 'both'

        # 获取前端传来的客户资料（运营规划补充信息）
        request_data = request.get_json() or {}
        client_info = {
            'brand_name': request_data.get('brand_name', portrait.get('client_name', '')),
            'brand_type': request_data.get('brand_type', 'personal'),
            'operating_years': request_data.get('operating_years', ''),
            'core_advantages': request_data.get('core_advantages', ''),
            'target_audience': request_data.get('target_audience', ''),
            'competitors': request_data.get('competitors', ''),
            'blue_ocean': request_data.get('blue_ocean', ''),
            'contact_info': request_data.get('contact_info', ''),
            'credentials': request_data.get('credentials', ''),
            'service_guarantee': request_data.get('service_guarantee', ''),
            'case_data': request_data.get('case_data', ''),
        }

        # 调用运营规划 skill，传入完整上下文
        result = bridge.execute(
            skill_name='operations_expert',
            manual_inputs={
                'business_description': business_description,
                'industry': industry,
                'business_type': business_type,
                'market_analyzer_output': market_analyzer_output,
                # 画像数据
                'portrait_data': portrait.get('portrait_data'),
                # 选定的蓝海机会
                'selected_opportunity': portrait.get('selected_opportunity'),
                # 客户补充信息
                'client_profile': portrait.get('client_profile') or client_info,
                # 关键词库和选题库
                'keyword_library': keyword_library,
                'topic_library': portrait.get('topic_library'),
            },
        )

        if not result.success:
            return jsonify({
                'success': False,
                'message': f"运营规划生成失败: {result.errors[0] if result.errors else '未知错误'}"
            }), 500

        operation_plan = result.full_output

        # 保存到画像
        portrait_model = SavedPortrait.query.get(portrait_id)
        if portrait_model:
            portrait_model.operation_plan = operation_plan
            portrait_model.operation_plan_updated_at = datetime.utcnow()
            db.session.commit()

        logger.info("[generate_operation_plan] portrait_id=%s, 生成成功", portrait_id)

        return jsonify({
            'success': True,
            'data': {
                'operation_plan': operation_plan,
                'operation_plan_updated_at': datetime.utcnow().isoformat(),
            }
        })

    except Exception as e:
        import traceback
        logger.error("[generate_operation_plan] 异常: %s", e)
        logger.debug("[generate_operation_plan] 堆栈: %s", traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/operation-plan/markdown', methods=['GET'])
@login_required
def get_operation_plan_markdown(user, portrait_id):
    """
    获取运营规划方案的 Markdown 格式（用于预览）
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    plan = portrait.get('operation_plan')
    if not plan:
        return jsonify({'success': False, 'message': '运营规划为空，请先生成'}), 404

    portrait_name = portrait.get('portrait_name', '未命名')
    updated_at = portrait.get('operation_plan_updated_at')
    updated_str = updated_at.strftime('%Y-%m-%d %H:%M') if hasattr(updated_at, 'strftime') else str(updated_at or '未知')

    md = _build_operation_plan_markdown(plan, portrait_name, updated_str)
    return jsonify({'success': True, 'data': {'markdown': md}})


def _build_operation_plan_markdown(plan: dict, portrait_name: str, updated_at: str) -> str:
    """将运营规划字典渲染为 Markdown 文本"""
    lines = [
        f"# 📊 {portrait_name} - 运营规划方案",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 画像名称 | {portrait_name} |",
        f"| 生成时间 | {updated_at} |",
        "",
    ]

    # 蓝海机会
    blue_ocean = plan.get('step_blue_ocean_opportunity', {})
    if blue_ocean:
        lines.append("---")
        lines.append("")
        lines.append("## 🎯 蓝海机会")
        lines.append("")
        rec = blue_ocean.get('recommended_blue_ocean', '')
        if rec:
            lines.append(f"**推荐方向**：{rec}")
            lines.append("")
        core_problem = blue_ocean.get('core_problem', '')
        if core_problem:
            lines.append(f"**核心问题**：{core_problem}")
            lines.append("")

        opportunities = blue_ocean.get('blue_ocean_opportunities', [])
        if opportunities:
            lines.append("### 备选蓝海方向")
            for i, opp in enumerate(opportunities, 1):
                lines.append(f"**{i}. {opp.get('direction', '')}**")
                lines.append(f"- 问题：{opp.get('problem', '')}")
                lines.append(f"- 人群：{opp.get('target_audience', '')}")
                lines.append(f"- 原因：{opp.get('why_blue_ocean', '')}")
                lines.append("")

    # 账号设计
    account_design = plan.get('step_account_design', {})
    if account_design:
        lines.append("---")
        lines.append("")
        lines.append("## 👤 账号设计")
        lines.append("")

        nicknames = account_design.get('nickname_options', [])
        if nicknames:
            lines.append("### 昵称方案")
            for i, nick in enumerate(nicknames, 1):
                lines.append(f"{i}. **{nick.get('nickname', '')}** ({nick.get('style', '')})")
                lines.append(f"   - {nick.get('reason', '')}")
            lines.append("")

        bio = account_design.get('bio', '')
        if bio:
            lines.append("### 简介")
            lines.append("```")
            lines.append(bio)
            lines.append("```")
            lines.append("")

        tags = account_design.get('content_tags', [])
        if tags:
            lines.append(f"**内容标签**：{' '.join(f'#{t}' for t in tags)}")
            lines.append("")

    # 信任佐证
    trust_evidence = plan.get('step_trust_evidence', {})
    if trust_evidence:
        lines.append("---")
        lines.append("")
        lines.append("## ✅ 信任佐证与竞争优势")
        lines.append("")

        advantages = trust_evidence.get('core_advantages', [])
        if advantages:
            lines.append("### 核心优势")
            for adv in advantages:
                lines.append(f"- **{adv.get('advantage', '')}**：{adv.get('evidence', '')}")
            lines.append("")

        case_data = trust_evidence.get('case_data', '')
        if case_data:
            lines.append(f"**案例数据**：{case_data}")
            lines.append("")

        key_messages = trust_evidence.get('key_messages', [])
        if key_messages:
            lines.append("**核心传播信息**：")
            for msg in key_messages:
                lines.append(f"- {msg}")
            lines.append("")

    # 风格定位
    style_guide = plan.get('step_style_guide', {})
    if style_guide:
        lines.append("---")
        lines.append("")
        lines.append("## 🎨 风格定位")
        lines.append("")

        tone = style_guide.get('tone', '')
        if tone:
            lines.append(f"**整体风格**：{tone}")
            lines.append("")

        principles = style_guide.get('principles', [])
        if principles:
            lines.append("**内容原则**：")
            for p in principles:
                lines.append(f"- {p}")
            lines.append("")

        taboo = style_guide.get('taboo', [])
        if taboo:
            lines.append("**禁忌内容**：")
            for t in taboo:
                lines.append(f"- ~~{t}~~")
            lines.append("")

        content_ratio = style_guide.get('content_ratio', {})
        if content_ratio:
            lines.append("### 内容配比")
            for ratio_type, ratio_val in content_ratio.items():
                lines.append(f"- {ratio_type}：{ratio_val}")
            lines.append("")

    return "\n".join(lines)


def _is_expired(expires_at) -> bool:
    """判断是否过期"""
    if not expires_at:
        return True
    from datetime import datetime
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except:
            return True
    return expires_at < datetime.utcnow()


# =============================================================================
# 画像库 Markdown 查看 API
# =============================================================================

@portrait_bp.route('/<int:portrait_id>/keyword-library/markdown', methods=['GET'])
@login_required
def get_keyword_library_markdown(user, portrait_id):
    """
    获取画像关键词库的 Markdown 格式（用于预览和检查结果）
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    kw_lib = portrait.get('keyword_library')
    if not kw_lib:
        return jsonify({'success': False, 'message': '关键词库为空，请先生成'}), 404

    portrait_name = portrait.get('portrait_name', '未命名')
    industry = portrait.get('industry', '')
    business_desc = portrait.get('business_description', '')
    updated_at = portrait.get('keyword_updated_at')
    
    if isinstance(updated_at, str):
        updated_str = updated_at
    elif hasattr(updated_at, 'strftime'):
        updated_str = updated_at.strftime('%Y-%m-%d %H:%M')
    else:
        updated_str = '未知'

    md = _build_keyword_library_markdown(
        kw_lib, portrait_name, industry, business_desc, updated_str
    )
    return jsonify({'success': True, 'data': {'markdown': md}})


def _build_keyword_library_markdown(kw_lib: dict, portrait_name: str,
                                     industry: str, business_desc: str,
                                     updated_at: str) -> str:
    """将关键词库字典渲染为 Markdown 文本"""
    import logging
    _logger = logging.getLogger('werkzeug')
    _logger.info(f"[keyword_md] kw_lib type={type(kw_lib)}, keys={list(kw_lib.keys()) if isinstance(kw_lib, dict) else 'NOT_DICT'}")
    _logger.info(f"[keyword_md] common_keywords={bool(kw_lib.get('common_keywords') if isinstance(kw_lib, dict) else None)}, personas={bool(kw_lib.get('personas') if isinstance(kw_lib, dict) else None)}")
    lines = [
        f"# 📚 {portrait_name} - 关键词库",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 行业 | {industry} |",
        f"| 业务描述 | {business_desc} |",
        f"| 生成时间 | {updated_at} |",
        "",
    ]

    # 新格式扁平结构（KeywordTopicGenerator）
    flat_kw_sections = [
        ('problem_type_keywords', '🔍 问题类型词'),
        ('pain_point_keywords', '😣 痛点关键词'),
        ('scene_keywords', '🎬 场景关键词'),
        ('concern_keywords', '❓ 顾虑关键词'),
    ]
    flat_found = False
    for kw_key, kw_label in flat_kw_sections:
        kws = kw_lib.get(kw_key, [])
        if kws:
            if not flat_found:
                lines.append("---")
                lines.append("")
                lines.append("## 关键词分类（新格式）")
                lines.append("")
                flat_found = True
            lines.append(f"### {kw_label}（{len(kws)}个）")
            for i in range(0, len(kws), 4):
                row = kws[i:i+4]
                lines.append("| " + " | ".join(str(k) for k in row) + " |")
            lines.append("")

    # ── 新格式：KeywordLibraryGenerator 产出的市场关键词库 ──────────────────
    # 结构：common_keywords, personas, upstream_keywords, downstream_keywords,
    #       supporting_tools_keywords, technique_keywords
    if kw_lib.get('common_keywords'):
        lines.append("---")
        lines.append("")
        lines.append("## 市场公用关键词库（KeywordLibraryGenerator）")
        lines.append("")
        common = kw_lib.get('common_keywords', {})
        if isinstance(common, dict):
            for cat_name, kws in common.items():
                if kws and isinstance(kws, list):
                    lines.append(f"### {cat_name}（{len(kws)}个）")
                    for i in range(0, len(kws), 4):
                        row = kws[i:i+4]
                        lines.append("| " + " | ".join(str(k) if not isinstance(k, dict) else k.get('keyword', k.get('name', '')) for k in row) + " |")
                    lines.append("")
        elif isinstance(common, list):
            lines.append(f"共 {len(common)} 个")
            for i in range(0, len(common), 4):
                row = common[i:i+4]
                lines.append("| " + " | ".join(str(k) for k in row) + " |")
            lines.append("")

    if kw_lib.get('personas'):
        lines.append("---")
        lines.append("")
        lines.append("## 画像专属关键词库")
        lines.append("")
        personas = kw_lib.get('personas', [])
        if isinstance(personas, list):
            for i, p in enumerate(personas):
                if not isinstance(p, dict):
                    continue
                p_name = p.get('portrait_name', p.get('persona_problem_type', f'画像{i+1}'))
                lines.append(f"### {p_name}")
                for field, label in [
                    ('pain_points', '痛点关键词'),
                    ('scene_keywords', '场景关键词'),
                    ('concerns', '顾虑关键词'),
                ]:
                    kws = p.get(field, [])
                    if kws:
                        lines.append(f"**{label}（{len(kws)}个）**：")
                        kw_strs = [k.get('keyword', k.get('name', '')) if isinstance(k, dict) else str(k) for k in kws]
                        for j in range(0, len(kw_strs), 4):
                            lines.append("| " + " | ".join(kw_strs[j:j+4]) + " |")
                lines.append("")

    upstream = kw_lib.get('upstream_keywords', [])
    downstream = kw_lib.get('downstream_keywords', [])
    tools_kw = kw_lib.get('supporting_tools_keywords', [])
    tech_kw = kw_lib.get('technique_keywords', [])

    if upstream or downstream or tools_kw or tech_kw:
        lines.append("---")
        lines.append("")
        lines.append("## 行业上下游关键词库")
        lines.append("")
        for field, label in [
            ('upstream_keywords', '上游原材料'),
            ('downstream_keywords', '下游配套服务'),
            ('supporting_tools_keywords', '配套工具'),
            ('technique_keywords', '技艺工艺'),
        ]:
            kws = kw_lib.get(field, [])
            if kws and isinstance(kws, list):
                lines.append(f"### {label}（{len(kws)}个）")
                kw_strs = [k.get('keyword', k.get('name', '')) if isinstance(k, dict) else str(k) for k in kws]
                for i in range(0, len(kw_strs), 4):
                    lines.append("| " + " | ".join(kw_strs[i:i+4]) + " |")
                lines.append("")

    # categories 结构（generate_template 新格式 & 旧格式兼容）
    categories = kw_lib.get('categories', [])
    if categories:
        # 过滤掉空分类
        non_empty = [c for c in categories if (c.get('keywords') or [])]
        if non_empty:
            lines.append("---")
            lines.append("")
            lines.append("## 关键词分类")
            lines.append("")

            for cat in non_empty:
                # 优先用 category_name（新格式），兼容 name/key（旧格式）
                cat_name = cat.get('category_name') or cat.get('name') or cat.get('key') or '未知分类'
                keywords = cat.get('keywords', [])
                count = len(keywords)
                lines.append(f"### {cat_name}（{count}个）")
                # 每行显示4个，用 | 分隔
                for i in range(0, len(keywords), 4):
                    row = keywords[i:i+4]
                    lines.append("| " + " | ".join(str(k) for k in row) + " |")
                lines.append("")

    # 蓝海长尾词
    blue_ocean = kw_lib.get('blue_ocean', [])
    if blue_ocean:
        lines.append("---")
        lines.append("")
        lines.append("## 🔱 蓝海长尾词")
        lines.append("")
        lines.append("| 核心词 | 修饰词 | 完整关键词 | 类型 |")
        lines.append("|--------|--------|-----------|------|")
        for item in blue_ocean:
            if isinstance(item, dict):
                core = item.get('core_word', '')
                modifier = item.get('modifier', '')
                full_kw = item.get('full_keyword', '')
                kw_type = item.get('type', '')
                lines.append(f"| {core} | {modifier} | {full_kw} | {kw_type} |")
            else:
                lines.append(f"| - | - | {item} | - |")
        lines.append("")

    # 热点词
    hot_keywords = kw_lib.get('hot_keywords', [])
    if hot_keywords:
        lines.append("---")
        lines.append("")
        lines.append("## 🔥 近期热点关键词")
        lines.append("")
        lines.append("| " + " | ".join(str(k) for k in hot_keywords) + " |")
        lines.append("")

    # 配比策略
    ratio = kw_lib.get('ratio_strategy', {})
    if ratio:
        lines.append("---")
        lines.append("")
        lines.append("## 📊 关键词配比策略")
        lines.append("")
        stage = ratio.get('stage', '')
        long_tail = ratio.get('long_tail_ratio', 0)
        region = ratio.get('region_ratio', 0)
        core = ratio.get('core_ratio', 0)
        lines.append(f"**账号阶段**：{stage}")
        lines.append("")
        lines.append(f"- 🔹 长尾词占比：{int(long_tail*100)}%")
        lines.append(f"- 🔹 地域词占比：{int(region*100)}%")
        lines.append(f"- 🔹 核心词占比：{int(core*100)}%")
        lines.append("")

    return "\n".join(lines)


@portrait_bp.route('/<int:portrait_id>/topic-library/markdown', methods=['GET'])
@login_required
def get_topic_library_markdown(user, portrait_id):
    """
    获取画像选题库的 Markdown 格式（用于预览和检查结果）
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    topic_lib = portrait.get('topic_library')
    if not topic_lib:
        return jsonify({'success': False, 'message': '选题库为空，请先生成'}), 404

    portrait_name = portrait.get('portrait_name', '未命名')
    industry = portrait.get('industry', '')
    updated_at = portrait.get('topic_updated_at')
    
    if isinstance(updated_at, str):
        updated_str = updated_at
    elif hasattr(updated_at, 'strftime'):
        updated_str = updated_at.strftime('%Y-%m-%d %H:%M')
    else:
        updated_str = '未知'

    md = _build_topic_library_markdown(topic_lib, portrait_name, industry, updated_str)
    return jsonify({'success': True, 'data': {'markdown': md}})


def _build_topic_library_markdown(topic_lib: dict, portrait_name: str,
                                    industry: str, updated_at: str) -> str:
    """将选题库字典渲染为 Markdown 文本"""
    lines = [
        f"# 📋 {portrait_name} - 选题库",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 行业 | {industry} |",
        f"| 生成时间 | {updated_at} |",
        "",
    ]

    # 新格式扁平结构（KeywordTopicGenerator）
    flat_topic_sections = [
        ('audience_lock_topics', '🎯 受众锁定'),
        ('pain_amplify_topics', '😣 痛点放大'),
        ('solution_compare_topics', '⚖️ 方案对比'),
        ('vision_topics', '✨ 愿景勾画'),
        ('barrier_remove_topics', '💡 顾虑消除'),
    ]
    flat_found = False
    for topic_key, topic_label in flat_topic_sections:
        topics = topic_lib.get(topic_key, [])
        if topics:
            if not flat_found:
                lines.append("---")
                lines.append("")
                lines.append("## 选题列表（新格式）")
                lines.append("")
                flat_found = True
            lines.append(f"### {topic_label}（{len(topics)}个）")
            for t in topics:
                if isinstance(t, dict):
                    title = t.get('title', str(t))[:40]
                    lines.append(f"- {title}")
                else:
                    lines.append(f"- {str(t)}")
            lines.append("")

    # 旧格式 topics 数组
    topics = topic_lib.get('topics', [])
    if topics:
        lines.append("---")
        lines.append("")
        lines.append(f"## 选题列表（共 {len(topics)} 条）")
        lines.append("")
        lines.append("| # | 标题 | 类型 | 优先级 | 来源 | 推荐理由 |")
        lines.append("|---|------|------|--------|------|----------|")

        for i, topic in enumerate(topics, 1):
            if not isinstance(topic, dict):
                continue
            title = topic.get('title', '')[:30]
            type_name = topic.get('type_name', topic.get('type', ''))
            priority = topic.get('priority', 'P2')
            source = topic.get('source', '')
            reason = topic.get('reason', '')[:40]
            lines.append(
                f"| {i} | {title} | {type_name} | {priority} | {source} | {reason} |"
            )
        lines.append("")

    # 按类型统计
    by_type = topic_lib.get('by_type', {})
    if by_type:
        lines.append("---")
        lines.append("")
        lines.append("## 按类型分布")
        lines.append("")
        for type_key, cnt in by_type.items():
            lines.append(f"- **{type_key}**：{cnt} 条")
        lines.append("")

    # 按优先级统计
    priorities = topic_lib.get('priorities', {})
    if priorities:
        lines.append("---")
        lines.append("")
        lines.append("## 按优先级分布")
        lines.append("")
        for p in ['P0', 'P1', 'P2', 'P3']:
            cnt = priorities.get(p, 0)
            emoji = '🔴' if p == 'P0' else '🟠' if p == 'P1' else '🟡' if p == 'P2' else '⚪'
            lines.append(f"{emoji} **{p}**：{cnt} 条")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# 行业分析报告 API
# =============================================================================

@portrait_bp.route('/<int:portrait_id>/industry-analysis', methods=['GET'])
@login_required
def get_industry_analysis(user, portrait_id):
    """
    获取画像的行业分析报告
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    result = portrait_save_service.get_industry_analysis_report(portrait_id)

    return jsonify({
        'success': True,
        'data': result or {
            'report': None,
            'updated_at': None,
            'has_report': False
        }
    })


@portrait_bp.route('/<int:portrait_id>/industry-analysis/generate', methods=['POST'])
@login_required
def generate_industry_analysis(user, portrait_id):
    """
    触发生成行业分析报告

    Body: {
        // 可选，覆盖默认值
    }
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '画像不存在或无权访问'}), 404

    try:
        from services.llm import get_llm_service
        llm = get_llm_service()

        # 构建输入参数
        business_description = portrait.get('business_description', '') or ''
        industry = portrait.get('industry', '') or ''
        target_customer = portrait.get('target_customer', '') or ''
        portrait_name = portrait.get('portrait_name', '未命名')

        # 构建 prompt - 使用固定模板生成报告
        # 读取模板文件
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md'
        )
        
        # 尝试多个可能的模板路径
        possible_paths = [
            template_path,
            os.path.join(os.getcwd(), 'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md'),
            '/Volumes/增元/项目/douyin/系统部署/skills/insights-analyst/输出/行业分析/行业分析报告_模板.md'
        ]
        
        template_content = None
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                break
        
        if not template_content:
            # 模板不存在，使用内嵌模板
            template_content = """# {客户名称} 行业分析报告

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 {客户名称} 行业分析报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
报告日期：{日期}
客户：{客户名称}
行业：{行业}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ⭐⭐⭐ 第一步：核心思维流程（必须按顺序）

> 💡 **行业分析报告必须按以下7步顺序进行：**
> 1️⃣ 行业分析 → 2️⃣ 找蓝海 → 3️⃣ 人群细分 → 4️⃣ 长尾需求 → 5️⃣ 知识技能解决 → 6️⃣ 搜前搜后 → 7️⃣ 行业关联

> ✅ 完成以上7步后，才进入第二步：信任佐证 + 竞争优势

> ⚠️ **内容配比规则**：信任佐证+竞争优势内容占比 **15%**，其他内容占比 **85%**

### 一、行业分析
[根据「{业务描述}」分析：行业规模、发展趋势、季节性特征、产品类型]

### 二、找蓝海（竞争分析）
[分析竞争对手、蓝海机会矩阵、红海vs蓝海业务分布]

### 三、人群细分
[分析：付费人vs使用人、客群痛点挖掘、客群优先级]

### 四、长尾需求
[分析：不同人群的独特需求、细分场景需求、蓝海需求发现]

### 五、知识技能解决
[分析：专业知识技能、服务解决方案、定制化能力]

### 六、搜前搜后
[分析搜索前后的用户问题]

### 七、行业关联
[分析：上游关联、下游需求、关联行业矩阵]

---

## ⭐⭐⭐ 第二步：信任佐证与竞争优势

### 信任佐证4大方向
| 信任方向 | 客户问题 | 佐证内容 |
|----------|----------|----------|
| **专业知识技能** | 能不能帮我做好？ | 经验、技术、配方 |
| **环境** | 卫生吗？干净吗？ | 制作条件、现场 |
| **过程** | 怎么做的？ | 制作流程、步骤 |
| **案例** | 别人做得好不好？ | 客户反馈、口碑 |

### 竞争优势4大维度
| 竞争优势 | vs同行 | vs自己动手 |
|----------|--------|------------|
| **省心** | 做得更专业 | 不用自己动手 |
| **省事** | 一站式服务 | 不用准备材料工具 |
| **省钱** | 品质好价格合理 | 避免失败浪费 |
| **放心** | 品质有保障 | 卫生看得见 |

---

## 一、行业概况

### 1.1 行业定义与定位
[具体描述{行业}的定义、业务类型、产品类型、核心价值]

### 1.2 市场现状
[分析市场态势、进入门槛、竞争程度、地域特点]

---

## 二、目标客户分析

### 2.1 客群痛点挖掘
[从「{业务描述}」中挖掘核心问题：客户搜索时在想什么？]

### 2.2 客群优先级
[按优先级排列目标客群及开发策略]

---

## 三、行业生态分析

### 3.1 产业链结构
[分析上游、中游、下游关系]

### 3.2 上游关联（客户从哪来）
[分析客户可能从哪些关联需求中找过来]

### 3.3 下游需求（客户到哪去）
[分析客户的延伸需求]

### 3.4 消费习惯
[分析采购频率、价格敏感度、决策因素、淡旺季]

---

## 四、用户失败经历分析 🔥

> 💡 **核心洞察**：{行业}的爆款内容来自用户真实的失败经历

### 4.1 失败经历类型
[挖掘用户制作/使用过程中容易犯的错误]

### 4.2 选题转化公式
```
💡 失败经历 → 爆款选题

公式：为什么你[{动词}]{产品}总是[{失败}]，3招教你解决
```

---

## 五、竞争格局与蓝海机会

### 5.1 竞争对手分析
[分析本地竞争对手的优劣势]

### 5.2 蓝海机会矩阵
[发现蓝海机会：痛点→解决方案→差异化优势]

---

## 六、总结

### 6.1 核心优势
[总结本业务的差异化优势]

### 6.2 蓝海机会总结
```
🎯 {客户名称} 蓝海机会

【核心机会】[核心机会描述]

差异化定位：
→ [定位1]
→ [定位2]
→ [定位3]
```

---

**报告版本**：v2.0

**生成日期**：{日期}

---

*本报告采用"专科医生"思维，从问题出发寻找蓝海机会*
"""
        
        from datetime import datetime
        
        # 替换模板变量 - 使用安全的替换方式
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 客户名称：优先使用业务描述，如果没有才用画像名称
        if not business_description or business_description.strip() == '':
            customer_name = portrait_name  # 画像名称作为客户名称
            inferred_business = portrait_name  # 从名称推断业务
            inferred_industry = industry if industry else '服务业'
        else:
            customer_name = business_description  # 业务描述作为客户名称
            inferred_business = business_description
            inferred_industry = industry if industry else '服务业'
        
        # 安全替换模板变量（避免 KeyError）
        safe_template = template_content
        safe_template = safe_template.replace('{客户名称}', customer_name)
        safe_template = safe_template.replace('{日期}', current_date)
        safe_template = safe_template.replace('{行业}', inferred_industry)
        safe_template = safe_template.replace('{业务描述}', inferred_business)
        # 处理可选变量
        safe_template = safe_template.replace('{子行业}', '')
        safe_template = safe_template.replace('{版本}', 'v2.0')
        
        # 移除内嵌模板中的未替换占位符提示
        safe_template = safe_template.replace('[根据「{业务描述}」分析', '[根据业务分析')
        safe_template = safe_template.replace('[具体描述{行业}的定义', '[具体描述行业的定义')
        safe_template = safe_template.replace('从「{业务描述}」中挖掘', '从业务中挖掘')
        safe_template = safe_template.replace('{行业}的爆款内容', '行业的爆款内容')
        safe_template = safe_template.replace('[{动词}]{产品}', '')
        safe_template = safe_template.replace('[{失败}]', '')
        
        prompt = f"""你是一位市场洞察专家。请根据以下业务信息，生成一份完整的行业分析报告。

## 业务信息
- 客户名称：{customer_name}
- 业务描述：{inferred_business}
- 所属行业：{inferred_industry}
- 目标客户：{target_customer}

## 重要提示
如果业务描述为空或不明确（如"家庭主妇"），请先推断出具体业务，然后基于具体业务生成报告。

## 输出要求
请直接生成 Markdown 格式的行业分析报告。每个板块都要有具体的、可落地的内容。

参考以下结构生成报告：

{safe_template}

只返回完整的 Markdown 格式报告。"""

        # 调用 LLM
        response = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        # LLM 直接返回 Markdown 格式
        report_markdown = response.strip()

        # 保存 Markdown 格式的报告
        report_data = {
            "markdown": report_markdown,
            "format": "markdown"
        }
        success = portrait_save_service.save_industry_analysis_report(portrait_id, report_data)
        if not success:
            return jsonify({
                'success': False,
                'message': '报告保存失败'
            }), 500

        logger.info("[generate_industry_analysis] portrait_id=%s, 生成成功", portrait_id)

        return jsonify({
            'success': True,
            'message': '行业分析报告生成成功',
            'data': {
                'markdown': report_markdown,
                'updated_at': datetime.utcnow().isoformat(),
            }
        })

    except Exception as e:
        import traceback
        logger.error("[generate_industry_analysis] portrait_id=%s, 异常: %s", portrait_id, str(e))
        logger.debug("[generate_industry_analysis] 堆栈: %s", traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/industry-analysis/generate-from-opportunity', methods=['POST'])
@login_required
def generate_industry_analysis_from_opportunity(user):
    """
    从超级定位阶段触发生成行业分析报告（使用表单业务描述，不需要画像）

    Body: {
        business_name: str,        # 业务名称（用于报告标题）
        business_description: str,  # 业务描述
        industry: str,             # 行业
        target_customer: str,      # 目标客户
        business_type: str,        # 业务类型
        business_range: str,      # 经营范围
        service_scenario: str,     # 服务场景
    }
    """
    try:
        from services.llm import get_llm_service
        llm = get_llm_service()

        data = request.get_json() or {}

        # 构建输入参数
        portrait_name = data.get('business_name', '未知业务')
        business_description = data.get('business_description', '') or ''
        industry = data.get('industry', '') or ''
        target_customer = data.get('target_customer', '') or ''

        # 客户名称：优先使用业务描述
        if business_description and business_description.strip():
            customer_name = business_description
        else:
            customer_name = portrait_name

        # 读取模板
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md'
        )

        possible_paths = [
            template_path,
            os.path.join(os.getcwd(), 'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md'),
            '/Volumes/增元/项目/douyin/系统部署/skills/insights-analyst/输出/行业分析/行业分析报告_模板.md'
        ]

        template_content = None
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    template_content = f.read()
                break

        if not template_content:
            return jsonify({'success': False, 'message': '模板文件不存在'}), 500

        # 替换模板变量
        current_date = datetime.now().strftime('%Y-%m-%d')

        safe_template = template_content
        safe_template = safe_template.replace('{客户名称}', customer_name)
        safe_template = safe_template.replace('{日期}', current_date)
        safe_template = safe_template.replace('{行业}', industry or '服务业')
        safe_template = safe_template.replace('{业务描述}', business_description)
        safe_template = safe_template.replace('{子行业}', '')
        safe_template = safe_template.replace('{版本}', 'v2.0')

        # 清理占位符
        safe_template = safe_template.replace('[根据「{业务描述}」分析', '[根据业务分析')
        safe_template = safe_template.replace('[具体描述{行业}的定义', '[具体描述行业的定义')
        safe_template = safe_template.replace('从「{业务描述}」中挖掘', '从业务中挖掘')
        safe_template = safe_template.replace('{行业}的爆款内容', '行业的爆款内容')
        safe_template = safe_template.replace('[{动词}]{产品}', '')
        safe_template = safe_template.replace('[{失败}]', '')

        prompt = f"""你是一位市场洞察专家。请根据以下业务信息，生成一份完整的行业分析报告。

## 业务信息
- 客户名称：{customer_name}
- 业务描述：{business_description}
- 所属行业：{industry or '服务业'}
- 目标客户：{target_customer}

## 输出要求
请直接生成 Markdown 格式的行业分析报告。每个板块都要有具体的、可落地的内容。

参考以下结构生成报告：

{safe_template}

只返回完整的 Markdown 格式报告。"""

        # 调用 LLM
        response = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        report_markdown = response.strip()

        logger.info("[generate_industry_analysis_from_opportunity] 用户 %s, 业务=%s, 生成成功", user.id, customer_name)

        return jsonify({
            'success': True,
            'message': '行业分析报告生成成功',
            'data': {
                'markdown': report_markdown,
                'updated_at': datetime.utcnow().isoformat(),
            }
        })

    except Exception as e:
        import traceback
        logger.error("[generate_industry_analysis_from_opportunity] 用户 %s, 异常: %s", user.id, str(e))
        logger.debug("[generate_industry_analysis_from_opportunity] 堆栈: %s", traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/industry-analysis/markdown', methods=['GET'])
@login_required
def get_industry_analysis_markdown(user, portrait_id):
    """
    获取行业分析报告的 Markdown 格式（用于预览）
    """
    portrait = portrait_save_service.get_saved_portrait(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404
    row = db.session.execute(
        text("SELECT user_id FROM saved_portraits WHERE id = :id"),
        {'id': portrait_id}
    ).fetchone()
    if not row or row[0] != user.id:
        return jsonify({'success': False, 'message': '无权访问'}), 403

    result = portrait_save_service.get_industry_analysis_report(portrait_id)
    report = result.get('report') if result else None
    updated_at = result.get('updated_at') if result else None

    if not report:
        return jsonify({'success': False, 'message': '行业分析报告为空，请先生成'}), 404

    # 直接返回保存的 Markdown 格式
    if isinstance(report, dict) and report.get('markdown'):
        return jsonify({'success': True, 'data': {'markdown': report['markdown']}})

    # 兼容旧格式，尝试渲染
    portrait_name = portrait.get('portrait_name', '未命名')
    industry = portrait.get('industry', '')
    updated_str = updated_at or '未知'

    md = _build_industry_analysis_markdown(report, portrait_name, industry, updated_str)
    return jsonify({'success': True, 'data': {'markdown': md}})


def _build_industry_analysis_markdown(report: dict, portrait_name: str,
                                      industry: str, updated_at: str) -> str:
    """将行业分析报告字典渲染为 Markdown 文本"""
    lines = [
        f"# 📊 {portrait_name} - 行业分析报告",
        "",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 行业 | {industry} |",
        f"| 生成时间 | {updated_at} |",
        "",
    ]

    # 行业消费习惯
    consumption = report.get('consumption_habits', {})
    if consumption:
        lines.append("---")
        lines.append("")
        lines.append("## 🛒 行业消费习惯")
        lines.append("")
        decision_flow = consumption.get('decision_flow', '')
        if decision_flow:
            lines.append(f"**决策流程**：{decision_flow}")
            lines.append("")
        info_channels = consumption.get('info_channels', [])
        if info_channels:
            lines.append(f"**信息获取渠道**：{'、'.join(info_channels)}")
            lines.append("")
        decision_points = consumption.get('decision_points', [])
        if decision_points:
            lines.append(f"**关键决策点**：{'、'.join(decision_points)}")
            lines.append("")

    # 淡旺季特征
    seasonal = report.get('seasonal_features', {})
    if seasonal:
        lines.append("---")
        lines.append("")
        lines.append("## 📅 淡旺季特征")
        lines.append("")
        peak = seasonal.get('peak_season', '')
        if peak:
            lines.append(f"**旺季**：{peak}")
            lines.append("")
        low = seasonal.get('low_season', '')
        if low:
            lines.append(f"**淡季**：{low}")
            lines.append("")
        peak_reason = seasonal.get('peak_reason', '')
        if peak_reason:
            lines.append(f"**旺季原因**：{peak_reason}")
            lines.append("")

    # 行业上下游关联
    upstream_downstream = report.get('upstream_downstream', {})
    if upstream_downstream:
        lines.append("---")
        lines.append("")
        lines.append("## 🔗 行业上下游关联")
        lines.append("")
        upstream = upstream_downstream.get('upstream', [])
        if upstream:
            lines.append("**上游（客户从哪来）**：")
            for u in upstream:
                lines.append(f"- {u}")
            lines.append("")
        downstream = upstream_downstream.get('downstream', [])
        if downstream:
            lines.append("**下游（客户到哪去）**：")
            for d in downstream:
                lines.append(f"- {d}")
            lines.append("")

    # 消费者痛点
    pain_points = report.get('consumer_pain_points', {})
    if pain_points:
        lines.append("---")
        lines.append("")
        lines.append("## 😣 消费者痛点")
        lines.append("")
        before = pain_points.get('before_decision', [])
        if before:
            lines.append("**决策前顾虑**：")
            for p in before:
                lines.append(f"- {p}")
            lines.append("")
        after = pain_points.get('after_decision', [])
        if after:
            lines.append("**决策后担忧**：")
            for p in after:
                lines.append(f"- {p}")
            lines.append("")

    # 蓝海机会
    blue_ocean = report.get('blue_ocean_opportunities', [])
    if blue_ocean:
        lines.append("---")
        lines.append("")
        lines.append("## 🎯 蓝海机会")
        lines.append("")
        for i, opp in enumerate(blue_ocean, 1):
            direction = opp.get('direction', '')
            reason = opp.get('reason', '')
            lines.append(f"**{i}. {direction}**")
            if reason:
                lines.append(f"- 原因：{reason}")
            lines.append("")

    # 长尾需求
    long_tail = report.get('long_tail_needs', [])
    if long_tail:
        lines.append("---")
        lines.append("")
        lines.append("## 🔍 长尾需求")
        lines.append("")
        for need in long_tail:
            if isinstance(need, dict):
                lines.append(f"- **{need.get('audience', '')}**：{need.get('need', '')}")
            else:
                lines.append(f"- {need}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# 温度配置相关API
# =============================================================================

@portrait_bp.route('/temperature/persona-options', methods=['GET'])
@login_required
def get_temperature_persona_options(user):
    """
    获取可选人设定居列表

    返回：
    - success: bool
    - data: list 人设选项
    """
    personas = temperature_word_library.get_all_persona_types()
    return jsonify({
        'success': True,
        'data': personas
    })


@portrait_bp.route('/temperature/element-options', methods=['GET'])
@login_required
def get_temperature_element_options(user):
    """
    获取可选三要素类型列表

    返回：
    - success: bool
    - data: list 三要素选项
    """
    elements = temperature_word_library.get_all_element_types()
    return jsonify({
        'success': True,
        'data': elements
    })


@portrait_bp.route('/<int:portrait_id>/temperature-profile', methods=['GET'])
@login_required
def get_portrait_temperature_profile(user, portrait_id):
    """
    获取画像的默认温度配置

    返回：
    - success: bool
    - data: {
        "persona_type": str,
        "target_elements": list,
        "temperature_profile_count": int
      }
    """
    portrait = SavedPortrait.query.filter_by(
        id=portrait_id,
        user_id=user.id
    ).first()

    if not portrait:
        return jsonify({
            'success': False,
            'message': '画像不存在'
        }), 404

    return jsonify({
        'success': True,
        'data': {
            'persona_type': portrait.temperature_persona or '陪伴者',
            'target_elements': portrait.temperature_elements or ['有用', '有共鸣'],
            'temperature_profile_count': portrait.temperature_profile_count or 0
        }
    })


@portrait_bp.route('/<int:portrait_id>/temperature-profile', methods=['PUT'])
@login_required
def update_portrait_temperature_profile(user, portrait_id):
    """
    更新画像的默认温度配置

    请求体：
    {
        "persona_type": "陪伴者",
        "target_elements": ["有用", "有共鸣"]
    }

    返回：
    - success: bool
    - message: str
    """
    portrait = SavedPortrait.query.filter_by(
        id=portrait_id,
        user_id=user.id
    ).first()

    if not portrait:
        return jsonify({
            'success': False,
            'message': '画像不存在'
        }), 404

    data = request.get_json() or {}

    # 更新温度配置
    persona_type = data.get('persona_type')
    if persona_type:
        # 验证人设类型
        valid_personas = [p['key'] for p in temperature_word_library.get_all_persona_types()]
        if persona_type not in valid_personas:
            return jsonify({
                'success': False,
                'message': f'无效的人设类型，可选：{", ".join(valid_personas)}'
            }), 400
        portrait.temperature_persona = persona_type

    target_elements = data.get('target_elements')
    if target_elements:
        # 验证三要素组合
        valid_elements = [e['key'] for e in temperature_word_library.get_all_element_types()]
        if not isinstance(target_elements, list):
            return jsonify({
                'success': False,
                'message': 'target_elements 必须是数组'
            }), 400
        for element in target_elements:
            if element not in valid_elements:
                return jsonify({
                    'success': False,
                    'message': f'无效的三要素类型，可选：{", ".join(valid_elements)}'
                }), 400
        # 至少需要2个要素
        if len(target_elements) < 2:
            return jsonify({
                'success': False,
                'message': '至少需要选择2个三要素'
            }), 400
        portrait.temperature_elements = target_elements

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '温度配置已更新',
        'data': {
            'persona_type': portrait.temperature_persona,
            'target_elements': portrait.temperature_elements
        }
    })


@portrait_bp.route('/temperature/word-library', methods=['GET'])
@login_required
def get_temperature_word_library(user):
    """
    获取温度词库（供前端使用）

    查询参数：
    - persona: 人设类型（可选）
    - element: 三要素类型（可选）

    返回：
    - success: bool
    - data: {
        "keywords": list,
        "phrases": list,
        "emotion_words": list
      }
    """
    persona = request.args.get('persona')
    element = request.args.get('element')

    result = {}

    if persona:
        result['keywords'] = temperature_word_library.get_persona_keywords(persona)
        result['phrases'] = temperature_word_library.get_persona_phrases(persona)
        result['angles'] = temperature_word_library.get_persona_angles(persona)
        result['quotes'] = temperature_word_library.get_golden_quotes(persona)

    if element:
        result['element_words'] = temperature_word_library.get_element_words(element)

    if not persona and not element:
        result['emotion_words'] = {
            'high': temperature_word_library.HIGH_EMOTION,
            'medium': temperature_word_library.MEDIUM_EMOTION,
            'low': temperature_word_library.LOW_EMOTION
        }
        result['opening_hooks'] = temperature_word_library.get_opening_hooks()
        result['cta_templates'] = {
            'strong': temperature_word_library.get_cta_templates('strong'),
            'medium': temperature_word_library.get_cta_templates('medium'),
            'soft': temperature_word_library.get_cta_templates('soft')
        }

    return jsonify({
        'success': True,
        'data': result
    })


@portrait_bp.route('/temperature/build-context', methods=['POST'])
@login_required
def build_temperature_context(user):
    """
    构建温度Prompt上下文（供前端预览）

    请求体：
    {
        "persona_type": "陪伴者",
        "target_elements": ["有用", "有共鸣"],
        "intensity": "high"
    }

    返回：
    - success: bool
    - data: { "context": str }
    """
    data = request.get_json() or {}

    persona_type = data.get('persona_type', '陪伴者')
    target_elements = data.get('target_elements', ['有用', '有共鸣'])
    intensity = data.get('intensity', 'high')

    context = temperature_word_library.build_temperature_prompt_context(
        persona_type=persona_type,
        target_elements=target_elements,
        intensity=intensity
    )

    return jsonify({
        'success': True,
        'data': {
            'context': context
        }
    })
