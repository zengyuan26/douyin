"""
内容计划 API 路由

提供选题库和内容计划的 REST API

接口列表：
- POST /api/v1/topics/generate     - 创建选题生成任务
- GET  /api/v1/topics              - 获取选题列表
- GET  /api/v1/topics/:id          - 获取单个选题
- PUT  /api/v1/topics/:id         - 更新选题
- DELETE /api/v1/topics/:id        - 删除选题

- GET  /api/v1/content-plans/:topic_id  - 获取内容计划
- POST /api/v1/content-plans/generate   - 生成内容计划

- POST   /api/v1/tasks               - 创建任务
- GET    /api/v1/tasks/:id          - 获取任务状态
- GET    /api/v1/tasks/:id/stream   - SSE进度推送
- POST   /api/v1/tasks/:id/cancel    - 取消任务
- POST   /api/v1/tasks/:id/retry     - 重试任务
"""

import logging
from flask import Blueprint, request, jsonify, Response, session
from functools import wraps

from app import db
from models.public_models import PublicUser
from models.content_plan_models import Task, TaskStep, TopicLibrary, ContentPlan

logger = logging.getLogger(__name__)

# 创建蓝图
content_plan_api = Blueprint('content_plan_api', __name__, url_prefix='/api/v1')


def get_task_service():
    """延迟导入，避免循环依赖"""
    from services.content_plan_task_service import content_plan_task_service
    return content_plan_task_service


# =============================================================================
# 认证装饰器
# =============================================================================

def require_auth(f):
    """需要认证"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = None

        # 方式1：从 session['public_user_id'] 获取
        user_id = session.get('public_user_id')
        if user_id:
            user = db.session.get(PublicUser, user_id)

        # 方式2：从 Flask-Login session 获取
        if not user and session.get('_user_id'):
            from models.user import User
            user = User.query.get(session.get('_user_id'))

        # 方式3：从 header 获取 X-User-Id
        if not user:
            user_id = request.headers.get('X-User-Id')
            if user_id:
                user = db.session.get(PublicUser, int(user_id))

        # 方式4：从 Bearer token 获取（临时用第一个用户）
        if not user:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                user = PublicUser.query.first()

        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(user, *args, **kwargs)
    return decorated


# =============================================================================
# 选题相关 API
# =============================================================================

@content_plan_api.route('/topics/generate', methods=['POST'])
@require_auth
def create_topic_generation_task(user):
    """
    创建选题生成任务 或 内容计划生成任务

    请求体（选题生成）：
    {
        "industry": "母婴/奶粉",
        "business_description": "特殊宝宝奶粉专科",
        "audience_segment": {...},
        "content_types": ["graphic", "long_text", "short_video"],
        "topic_count": 50,
        "keywords": [...]
    }

    请求体（内容计划生成）：
    {
        "portrait_id": 123,
        "industry": "...",
        "business_description": "...",
        "topics": [...],  // 选题库数据
        "content_types": ["graphic"]
    }

    响应：
    {
        "task_id": 123,
        "status": "queued",
        "estimated_time": 60,
        "created_at": "2026-04-29T20:53:00Z"
    }
    """
    data = request.get_json()

    # 判断是选题生成还是内容计划生成
    topics = data.get('topics', [])
    portrait_id = data.get('portrait_id')

    if topics and portrait_id:
        # 内容计划生成模式：复用已有选题库
        task_type = 'content_plan_generation'
        input_data = {
            'portrait_id': portrait_id,
            'industry': data.get('industry', ''),
            'business_description': data.get('business_description', ''),
            'topics': topics,
            'content_types': data.get('content_types', ['graphic']),
        }
    else:
        # 选题生成模式：生成新选题
        task_type = 'topic_generation'
        required_fields = ['industry', 'business_description']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400

        input_data = {
            'industry': data.get('industry'),
            'business_description': data.get('business_description'),
            'audience_segment': data.get('audience_segment', {}),
            'content_types': data.get('content_types', ['graphic']),
            'topic_count': data.get('topic_count', 50),
            'keywords': data.get('keywords', []),
            'content_stage': data.get('content_stage', '成长阶段'),
        }

    # 创建任务
    task = get_task_service().create_task(
        user_id=user.id,
        task_type=task_type,
        input_data=input_data
    )

    return jsonify({
        'task_id': task.id,
        'status': task.status,
        'estimated_time': task.estimated_time,
        'created_at': task.created_at.isoformat() if task.created_at else None
    }), 201


@content_plan_api.route('/topics', methods=['GET'])
@require_auth
def get_topics(user):
    """
    获取选题列表

    查询参数：
    - page: 页码（默认1）
    - page_size: 每页数量（默认20）
    - portrait_id: 画像ID（可选）
    - content_type: 内容类型（可选）
    - priority: 优先级（可选）
    - status: 状态（可选）
    - keyword: 搜索关键词（可选）
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    portrait_id = request.args.get('portrait_id', type=int)
    content_type = request.args.get('content_type')
    priority = request.args.get('priority')
    status = request.args.get('status')
    keyword = request.args.get('keyword')

    # 构建查询
    query = TopicLibrary.query.filter(
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    )

    # 筛选条件
    if portrait_id:
        query = query.filter(TopicLibrary.portrait_id == portrait_id)
    if content_type:
        query = query.filter(TopicLibrary.content_type == content_type)
    if priority:
        query = query.filter(TopicLibrary.priority == priority)
    if status:
        query = query.filter(TopicLibrary.status == status)
    if keyword:
        query = query.filter(TopicLibrary.title.contains(keyword))

    # 排序和分页
    query = query.order_by(TopicLibrary.sort_order, TopicLibrary.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    # 构建响应
    topics = []
    for topic in pagination.items:
        topic_dict = topic.to_dict()
        # 附加内容计划预览
        plans = ContentPlan.query.filter(
            ContentPlan.topic_id == topic.id,
            ContentPlan.deleted_at.is_(None)
        ).all()
        topic_dict['content_plans'] = [p.to_dict() for p in plans]
        topics.append(topic_dict)

    return jsonify({
        'topics': topics,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': pagination.total,
            'pages': pagination.pages
        }
    })


@content_plan_api.route('/topics/<int:topic_id>', methods=['GET'])
@require_auth
def get_topic(user, topic_id):
    """获取单个选题"""
    topic = TopicLibrary.query.filter(
        TopicLibrary.id == topic_id,
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    ).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    topic_dict = topic.to_dict(include_plans=True)
    return jsonify(topic_dict)


@content_plan_api.route('/topics/<int:topic_id>', methods=['PUT'])
@require_auth
def update_topic(user, topic_id):
    """更新选题"""
    topic = TopicLibrary.query.filter(
        TopicLibrary.id == topic_id,
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    ).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    data = request.get_json()

    # 可更新字段
    updatable_fields = ['title', 'priority', 'status', 'sort_order', 'extra_data']
    for field in updatable_fields:
        if field in data:
            setattr(topic, field, data[field])

    db.session.commit()

    return jsonify(topic.to_dict())


@content_plan_api.route('/topics/<int:topic_id>', methods=['DELETE'])
@require_auth
def delete_topic(user, topic_id):
    """删除选题（软删除）"""
    topic = TopicLibrary.query.filter(
        TopicLibrary.id == topic_id,
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    ).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    topic.deleted_at = db.func.now()
    db.session.commit()

    return jsonify({'message': 'Topic deleted'}), 200


@content_plan_api.route('/topics/batch', methods=['DELETE'])
@require_auth
def batch_delete_topics(user):
    """批量删除选题"""
    data = request.get_json()
    topic_ids = data.get('topic_ids', [])

    if not topic_ids:
        return jsonify({'error': 'No topic_ids provided'}), 400

    TopicLibrary.query.filter(
        TopicLibrary.id.in_(topic_ids),
        TopicLibrary.user_id == user.id
    ).update({TopicLibrary.deleted_at: db.func.now()}, synchronize_session=False)

    db.session.commit()

    return jsonify({'message': f'{len(topic_ids)} topics deleted'}), 200


# =============================================================================
# 内容计划相关 API
# =============================================================================

@content_plan_api.route('/content-plans/<int:topic_id>', methods=['GET'])
@require_auth
def get_content_plan(user, topic_id):
    """
    获取选题的内容计划

    查询参数：
    - content_type: 内容类型（默认graphic）
    """
    content_type = request.args.get('content_type', 'graphic')

    # 验证选题归属
    topic = TopicLibrary.query.filter(
        TopicLibrary.id == topic_id,
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    ).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    # 获取内容计划
    plan = ContentPlan.query.filter(
        ContentPlan.topic_id == topic_id,
        ContentPlan.content_type == content_type,
        ContentPlan.deleted_at.is_(None)
    ).first()

    if not plan:
        return jsonify({'error': 'Content plan not found'}), 404

    return jsonify(plan.to_dict())


@content_plan_api.route('/content-plans/generate', methods=['POST'])
@require_auth
def generate_content_plan(user):
    """
    为选题生成内容计划

    请求体：
    {
        "topic_ids": [1, 2, 3],  // 要生成内容计划的选题ID列表
        "content_types": ["graphic", "long_text", "short_video"]
    }
    """
    data = request.get_json()
    topic_ids = data.get('topic_ids', [])
    content_types = data.get('content_types', ['graphic'])

    if not topic_ids:
        return jsonify({'error': 'No topic_ids provided'}), 400

    # 验证选题归属
    topics = TopicLibrary.query.filter(
        TopicLibrary.id.in_(topic_ids),
        TopicLibrary.user_id == user.id,
        TopicLibrary.deleted_at.is_(None)
    ).all()

    if len(topics) != len(topic_ids):
        return jsonify({'error': 'Some topics not found'}), 404

    # 创建内容计划生成任务
    task = get_task_service().create_task(
        user_id=user.id,
        task_type='content_plan_generation',
        input_data={
            'topic_ids': topic_ids,
            'content_types': content_types,
            'topics': [t.to_dict() for t in topics]
        }
    )

    return jsonify({
        'task_id': task.id,
        'status': task.status,
        'estimated_time': task.estimated_time,
        'created_at': task.created_at.isoformat() if task.created_at else None
    }), 201


@content_plan_api.route('/content-plans/<int:plan_id>', methods=['PUT'])
@require_auth
def update_content_plan(user, plan_id):
    """更新内容计划"""
    plan = ContentPlan.query.filter(
        ContentPlan.id == plan_id,
        ContentPlan.deleted_at.is_(None)
    ).first()

    if not plan:
        return jsonify({'error': 'Content plan not found'}), 404

    # 验证归属
    topic = TopicLibrary.query.get(plan.topic_id)
    if not topic or topic.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()

    # 可更新字段
    updatable_fields = [
        'recommended_title', 'title_options', 'title_pattern', 'hvf_analysis',
        'l1_tags', 'l2_tags', 'l3_tags', 'final_tags',
        'emotional_curve', 'topic_type',
        'layouts', 'colors', 'visual_requirements',
        'article_structure', 'writing_style',
        'hook', 'script_outline', 'visual_notes',
        'status'
    ]

    for field in updatable_fields:
        if field in data:
            setattr(plan, field, data[field])

    plan.version += 1
    db.session.commit()

    return jsonify(plan.to_dict())


# =============================================================================
# 任务相关 API
# =============================================================================

@content_plan_api.route('/tasks', methods=['POST'])
@require_auth
def create_task(user):
    """创建任务"""
    data = request.get_json()

    task_type = data.get('task_type')
    if not task_type:
        return jsonify({'error': 'task_type is required'}), 400

    task = get_task_service().create_task(
        user_id=user.id,
        task_type=task_type,
        input_data=data
    )

    return jsonify({
        'task_id': task.id,
        'status': task.status,
        'estimated_time': task.estimated_time,
        'created_at': task.created_at.isoformat() if task.created_at else None
    }), 201


@content_plan_api.route('/tasks/<int:task_id>', methods=['GET'])
@require_auth
def get_task(user, task_id):
    """获取任务状态"""
    task = db.session.get(Task, task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # 验证归属
    if task.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify(get_task_service().get_task_with_steps(task_id))


@content_plan_api.route('/tasks/<int:task_id>/stream', methods=['GET'])
@require_auth
def stream_task_progress(user, task_id):
    """SSE进度推送"""
    task = db.session.get(Task, task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # 验证归属
    if task.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    return get_task_service().create_sse_response(task_id)


@content_plan_api.route('/tasks/<int:task_id>/cancel', methods=['POST'])
@require_auth
def cancel_task(user, task_id):
    """取消任务"""
    task = db.session.get(Task, task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    success = get_task_service().cancel_task(task_id)

    if success:
        return jsonify({'message': 'Task cancelled'})
    else:
        return jsonify({'error': 'Cannot cancel task'}), 400


@content_plan_api.route('/tasks/<int:task_id>/retry', methods=['POST'])
@require_auth
def retry_task(user, task_id):
    """重试失败任务"""
    task = db.session.get(Task, task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    if task.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 401

    new_task = get_task_service().retry_task(task_id)

    if new_task:
        return jsonify({
            'task_id': new_task.id,
            'status': new_task.status
        })
    else:
        return jsonify({'error': 'Cannot retry task'}), 400


@content_plan_api.route('/tasks/running', methods=['GET'])
@require_auth
def get_running_tasks(user):
    """获取当前用户运行中的任务"""
    tasks = get_task_service().get_running_tasks()

    # 过滤只返回属于当前用户的任务
    user_tasks = [t for t in tasks if t.get('user_id') == user.id]

    return jsonify({'tasks': user_tasks})
