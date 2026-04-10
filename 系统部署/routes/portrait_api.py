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
import datetime
from flask import Blueprint, request, jsonify, session
from functools import wraps
from services.portrait_save_service import portrait_save_service
from services.portrait_frequency_controller import portrait_frequency_controller
from services.portrait_library_task_service import generate_with_semaphore
from models.public_models import PublicUser, SavedPortrait, TopicGenerationLink, PublicGeneration
from models.models import db
from sqlalchemy import text

logger = logging.getLogger(__name__)




from services.galaxy_service import enrich_topics_with_scene_options

portrait_bp = Blueprint('portrait', __name__, url_prefix='/public/api/portraits')


def get_current_user():
    """获取当前登录用户"""
    user_id = session.get('public_user_id')
    if user_id:
        return PublicUser.query.get(user_id)
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
    
    # 调试日志
    current_app.logger.info("[save_portrait] business_description=%s, industry=%s, target_customer=%s",
        business_description, industry, target_customer)
    current_app.logger.info("[save_portrait] portrait_data keys=%s", list(portrait_data.keys()) if isinstance(portrait_data, dict) else type(portrait_data))

    success, message, saved = portrait_save_service.save_portrait(
        user_id=user.id,
        portrait_data=portrait_data,
        portrait_name=portrait_name,
        business_description=business_description,
        industry=industry,
        target_customer=target_customer,
        source_session_id=source_session_id,
        set_as_default=set_as_default
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

    # 付费用户：立即更新 generation_status = 'generating' 并启动后台线程
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
    
    print(f"[get_saved_portraits] 返回 {len(portraits)} 个画像")
    for p in portraits:
        print(f"  画像 {p['id']} {p['portrait_name']}: generation_status={p.get('generation_status')}, has_kw={p.get('keyword_library') is not None}, has_topic={p.get('topic_library') is not None}")
    
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
    per_page = int(request.args.get('per_page', 10))

    topic_library = portrait.get('topic_library')
    all_topics = []

    if topic_library and 'topics' in topic_library:
        all_topics = topic_library.get('topics', [])

    # 按 created_at 倒序排列
    def sort_key(t):
        created = t.get('created_at', '')
        return created if created else ''

    all_topics = sorted(all_topics, key=sort_key, reverse=True)

    # 分页
    total = len(all_topics)
    start = (page - 1) * per_page
    end = start + per_page
    page_topics = all_topics[start:end]

    # ── 星系增强：补充 scene_options 和 content_style ──
    page_topics = enrich_topics_with_scene_options(page_topics)

    # ── 补充 link 信息（版本数量、使用次数）──
    topic_ids = [t.get('id') for t in page_topics if t.get('id')]
    if topic_ids and portrait_id:
        links = TopicGenerationLink.query.filter_by(
            portrait_id=portrait_id, user_id=user.id
        ).filter(TopicGenerationLink.topic_id.in_(topic_ids)).all()
        link_map = {l.topic_id: l for l in links}
        for t in page_topics:
            tid = t.get('id')
            if tid in link_map:
                link = link_map[tid]
                t['_link_id'] = link.id
                t['_usage_count'] = link.usage_count or 0
                t['_generation_ids'] = link.generation_ids or []

    return jsonify({
        'success': True,
        'data': {
            'topics': page_topics,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page if per_page > 0 else 0,
            'portrait_id': portrait_id,
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

    if topic_library and 'topics' in topic_library:
        from services.topic_library_generator import topic_library_generator
        topics = topic_library_generator.select_topics(
            topic_library=topic_library,
            count=count,
        )
        from_portrait = True

    # 获取核心业务词（从关键词库的第一个分类中提取）
    core_business = ''
    keyword_library = portrait.get('keyword_library')
    if keyword_library and 'categories' in keyword_library:
        categories = keyword_library.get('categories', [])
        if categories and len(categories) > 0:
            first_cat = categories[0]
            keywords = first_cat.get('keywords', [])
            if keywords and len(keywords) > 0:
                # 取前3个关键词作为核心业务词展示
                core_business = '、'.join(keywords[:3])

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


@portrait_bp.route('/<int:portrait_id>/topics/regenerate', methods=['POST'])
@login_required
def regenerate_portrait_topics(user, portrait_id):
    """
    重新生成画像专属选题库（增量：保留原有选题，新增一批新选题）

    Body: {
        count: 新增数量，默认10
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
    extra_count = int(data.get('count', 10))

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

        # 生成新增选题
        from services.topic_library_generator import topic_library_generator
        result = topic_library_generator.generate(
            portrait_data=portrait_data,
            business_info=business_info,
            keyword_library=None,
            plan_type=plan_type,
            topic_count=extra_count,
            portrait_id=portrait_id,
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
    topics = topic_library.get('topics', [])

    for topic in topics:
        if topic.get('id') == topic_id:
            topic['generation_count'] = topic.get('generation_count', 0) + 1
            break
    else:
        return jsonify({'success': False, 'message': '选题不存在'}), 404

    topic_library['topics'] = topics
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

    categories = kw_lib.get('categories', [])
    if categories:
        lines.append("---")
        lines.append("")
        lines.append("## 关键词分类")
        lines.append("")

        for cat in categories:
            cat_name = cat.get('name', cat.get('key', '未知分类'))
            keywords = cat.get('keywords', [])
            count = cat.get('count', len(keywords))
            lines.append(f"### {cat_name}（{count}个）")
            if keywords:
                # 每行显示4个，用 | 分隔
                for i in range(0, len(keywords), 4):
                    row = keywords[i:i+4]
                    lines.append("| " + " | ".join(str(k) for k in row) + " |")
            else:
                lines.append("*（暂无关键词）*")
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
