"""
画像管理API路由

功能：
1. 保存/删除画像
2. 查看已保存画像
3. 切换画像（含频率控制）
4. 画像统计
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from services.portrait_save_service import portrait_save_service
from services.portrait_frequency_controller import portrait_frequency_controller
from models.public_models import PublicUser
from models.models import db
from sqlalchemy import text


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
    """保存画像"""
    data = request.get_json() or {}
    
    portrait_data = data.get('portrait_data', {})
    portrait_name = data.get('portrait_name')
    business_description = data.get('business_description')
    industry = data.get('industry')
    target_customer = data.get('target_customer')
    source_session_id = data.get('source_session_id')
    set_as_default = data.get('set_as_default', False)
    
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
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'data': saved
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400


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

    return jsonify({'success': True, 'data': portrait})


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
        # 生成关键词库
        if library_type in ('keyword', 'all'):
            from services.keyword_library_generator import keyword_library_generator
            kw_result = keyword_library_generator.generate(
                portrait_data=portrait_data,
                business_info=business_info,
                plan_type=plan_type,
            )
            if kw_result.get('success'):
                keyword_library_generator.save_to_portrait(
                    portrait_id=portrait_id,
                    keyword_library=kw_result['keyword_library'],
                    user_id=user.id,
                    plan_type=plan_type,
                )
                # 合并模式：关键词库和选题库只扣一次关键词库配额
                portrait_frequency_controller.record_library_update(user.id, 'keyword')
                results['keyword'] = kw_result['keyword_library']

        # 生成选题库（合并模式：依赖关键词库，一次生成）
        if library_type in ('topic', 'all'):
            from services.topic_library_generator import topic_library_generator
            kw_library = results['keyword'] or keyword_library_generator.get_from_portrait(portrait_id)
            topic_result = topic_library_generator.generate(
                portrait_data=portrait_data,
                business_info=business_info,
                keyword_library=kw_library,
                plan_type=plan_type,
            )
            if topic_result.get('success'):
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
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@portrait_bp.route('/<int:portrait_id>/topics', methods=['GET'])
@login_required
def get_portrait_topics(user, portrait_id):
    """
    从专属选题库获取选题列表（用于选题选择）

    Query params:
        count: 数量，默认5
        type: 选题类型筛选
        keyword_hint: 关键词筛选
        source: 选题来源 'library' / 'realtime' / 'mixed'
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

    count = int(request.args.get('count', 5))
    topic_type = request.args.get('type')
    keyword_hint = request.args.get('keyword_hint', '')
    source = request.args.get('source', 'mixed')  # mixed=混合

    topics = []
    from_portrait = False

    # 优先从专属选题库取
    topic_library = portrait.get('topic_library')
    if topic_library and source in ('library', 'mixed'):
        from services.topic_library_generator import topic_library_generator
        topics = topic_library_generator.select_topics(
            topic_library=topic_library,
            count=count,
            topic_type=topic_type,
            keyword_hint=keyword_hint,
        )
        from_portrait = True

    # 如果专属库为空或要求实时，实时生成
    if not topics or source == 'realtime':
        from services.topic_generator import TopicGenerator
        portrait_data = portrait.get('portrait_data', {})
        generator = TopicGenerator()
        result = generator.generate_topics(
            business_description=portrait.get('business_description', ''),
            business_range='',
            business_type=portrait.get('industry', ''),
            portraits=[portrait_data],
            problem_keywords=[],
            is_premium=user.is_paid_user(),
        )
        if result.get('success'):
            realtime_topics = result.get('topics', [])
            if topics:
                # 混合：实时选题放后面
                topics = (topics + realtime_topics)[:count]
            else:
                topics = realtime_topics[:count]

    return jsonify({
        'success': True,
        'data': {
            'topics': topics,
            'from_portrait_library': from_portrait,
            'portrait_id': portrait_id,
        }
    })


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
