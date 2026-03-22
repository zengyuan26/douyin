# -*- coding: utf-8 -*-
"""
内容分析 API

独立的 API 模块，处理内容相关的分析接口。
与账号分析 API 解耦，便于维护和扩展。
"""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required

logger = logging.getLogger(__name__)

# 创建 Blueprint
content_analysis_api = Blueprint('content_analysis_api', __name__, url_prefix='/api/knowledge')


@content_analysis_api.route('/contents', methods=['GET'])
@login_required
def get_contents():
    """获取内容列表（支持分页、按账号、搜索）"""
    try:
        from models.models import KnowledgeContent, db

        # 获取查询参数
        account_id = request.args.get('account_id', type=int)
        content_type = request.args.get('content_type')
        source_type = request.args.get('source_type')
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 4, type=int)
        page_size = min(max(page_size, 1), 100)

        # 构建查询
        query = KnowledgeContent.query
        if account_id:
            query = query.filter(KnowledgeContent.account_id == account_id)
        if content_type:
            query = query.filter(KnowledgeContent.content_type == content_type)
        if source_type:
            query = query.filter(KnowledgeContent.source_type == source_type)
        if search:
            query = query.filter(
                db.or_(
                    KnowledgeContent.title.ilike(f'%{search}%'),
                    db.cast(KnowledgeContent.content_data, db.String).ilike(f'%{search}%')
                )
            )

        query = query.order_by(KnowledgeContent.updated_at.desc())
        total = query.count()
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)
        contents = pagination.items

        if page < 1:
            page = 1
            page_size = max(total, 1)
            contents = query.limit(1000).all()
            total_pages = 1
        else:
            total_pages = max(1, (total + page_size - 1) // page_size)

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'items': [{
                    'id': c.id,
                    'account_id': c.account_id,
                    'title': c.title,
                    'content_url': c.content_url,
                    'content_type': c.content_type,
                    'source_type': c.source_type,
                    'content_data': c.content_data,
                    'analysis_result': c.analysis_result,
                    'created_at': c.created_at.isoformat() if c.created_at else None,
                    'updated_at': c.updated_at.isoformat() if c.updated_at else None
                } for c in contents],
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages
            }
        })

    except Exception as e:
        logger.error(f"获取内容列表失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@content_analysis_api.route('/contents/<int:content_id>', methods=['GET'])
@login_required
def get_content(content_id):
    """获取单个内容详情"""
    try:
        from models.models import KnowledgeContent

        content = KnowledgeContent.query.get(content_id)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type,
                'content_data': content.content_data,
                'analysis_result': content.analysis_result,
                'created_at': content.created_at.isoformat() if content.created_at else None,
                'updated_at': content.updated_at.isoformat() if content.updated_at else None
            }
        })

    except Exception as e:
        logger.error(f"获取内容详情失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@content_analysis_api.route('/contents', methods=['POST'])
@login_required
def create_content():
    """创建内容"""
    try:
        from models.models import KnowledgeContent, db

        data = request.get_json()

        account_id = data.get('account_id')
        title = data.get('title', '').strip()
        content_url = data.get('content_url', '').strip()
        content_type = data.get('content_type', 'video')
        source_type = data.get('source_type', 'manual')
        content_data = data.get('content_data', {})

        if not title:
            return jsonify({'code': 400, 'message': '请输入内容标题'})

        content = KnowledgeContent(
            account_id=account_id,
            title=title,
            content_url=content_url,
            content_type=content_type,
            source_type=source_type,
            content_data=content_data
        )
        db.session.add(content)
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '创建成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"创建内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'})


@content_analysis_api.route('/contents/<int:content_id>', methods=['PUT'])
@login_required
def update_content(content_id):
    """更新内容"""
    try:
        from models.models import KnowledgeContent, db

        data = request.get_json()
        content = KnowledgeContent.query.get(content_id)

        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})

        if 'account_id' in data:
            content.account_id = data['account_id']
        if 'title' in data:
            content.title = data['title'].strip()
        if 'content_url' in data:
            content.content_url = data['content_url'].strip()
        if 'content_type' in data:
            content.content_type = data['content_type']
        if 'source_type' in data:
            content.source_type = data['source_type']
        if 'content_data' in data:
            content.content_data = data['content_data']
        if 'analysis_result' in data:
            content.analysis_result = data['analysis_result']

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '更新成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"更新内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'})


@content_analysis_api.route('/contents/<int:content_id>', methods=['DELETE'])
@login_required
def delete_content(content_id):
    """删除内容"""
    try:
        from models.models import KnowledgeContent, db

        content = KnowledgeContent.query.get(content_id)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})

        db.session.delete(content)
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '删除成功'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"删除内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'})


@content_analysis_api.route('/contents/<int:content_id>/analyze', methods=['POST'])
@login_required
def analyze_content(content_id):
    """分析内容并写回结果

    参数:
        async: 是否异步执行（使用队列），默认 false 同步执行
    """
    try:
        from flask import current_app
        from models.models import db
        from services.content_analyzer import get_content_analyzer
        from services.analysis_task_queue import get_task_queue

        # 检查内容是否存在
        content_service = get_content_analyzer()
        content, _ = content_service.get_content_with_account(content_id, db)

        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})

        # 检查是否使用异步队列
        use_async = request.args.get('async', 'false').lower() == 'true'

        if use_async:
            # 使用队列异步执行
            task_queue = get_task_queue()
            task = task_queue.add_content_task(
                content_id=content_id,
                app=current_app._get_current_object()
            )

            if task is None:
                return jsonify({
                    'code': 202,
                    'message': '该内容已在分析队列中，请稍后刷新查看',
                    'data': {
                        'content_id': content_id,
                        'queued': True
                    }
                })

            return jsonify({
                'code': 202,
                'message': '已加入分析队列',
                'data': {
                    'content_id': content_id,
                    'queued': True,
                    'task_id': str(id(task))
                }
            })
        else:
            # 同步执行
            result = content_service.analyze(content_id, db)
            return jsonify(result)

    except ValueError as e:
        return jsonify({'code': 404, 'message': str(e)})
    except Exception as e:
        logger.error(f"内容分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})


@content_analysis_api.route('/contents/<int:content_id>/analyze-status', methods=['GET'])
@login_required
def get_content_analyze_status(content_id):
    """获取内容分析状态（支持队列查询）"""
    try:
        from services.analysis_task_queue import get_task_queue

        task_queue = get_task_queue()
        status = task_queue.get_task_status(str(content_id))
        return jsonify({'code': 200, 'data': status})
    except Exception as e:
        logger.error(f"获取分析状态失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': str(e)})


@content_analysis_api.route('/contents/<int:content_id>/analyze-dimension', methods=['POST'])
@login_required
def analyze_content_dimension(content_id):
    """分析单个维度

    参数:
        dimension: 维度编码（如 title, cover, topic）
    """
    try:
        from flask import request
        from models.models import db
        from services.content_analyzer import get_content_analyzer
        from routes.knowledge_api import analyze_modules_with_account

        dimension = request.json.get('dimension') if request.is_json else None
        if not dimension:
            return jsonify({'code': 400, 'message': '缺少 dimension 参数'})

        content_service = get_content_analyzer()
        content, account_info = content_service.get_content_with_account(content_id, db)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})

        content_info = content_service.build_content_info(content)
        url = content_service.get_analysis_url(content)

        result = analyze_modules_with_account(
            url, content.content_type or 'video', '', [dimension], account_info, content_info
        )

        if hasattr(result, 'get_json'):
            result = result.get_json()

        if result.get('code') == 200:
            data = result.get('data', {})
            dim_result = data.get(dimension, {})
            if dim_result:
                existing = content.analysis_result or {}
                existing[dimension] = dim_result
                content.analysis_result = existing
                db.session.commit()
                result['data'] = {dimension: dim_result}
        return jsonify(result)

    except Exception as e:
        logger.error(f"维度分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})
    """获取内容分析状态（支持队列查询）"""
    try:
        from services.analysis_task_queue import get_task_queue

        task_queue = get_task_queue()
        status = task_queue.get_task_status(str(content_id))

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'content_id': content_id,
                'task_status': status
            }
        })

    except Exception as e:
        logger.error(f"获取分析状态失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@content_analysis_api.route('/contents/batch-analyze', methods=['POST'])
@login_required
def batch_analyze_contents():
    """批量分析内容（使用队列）"""
    try:
        from flask import current_app
        from models.models import KnowledgeContent, db
        from services.analysis_task_queue import get_task_queue

        data = request.get_json()
        content_ids = data.get('content_ids', [])

        if not content_ids:
            return jsonify({'code': 400, 'message': '请提供要分析的内容ID列表'})

        if not isinstance(content_ids, list):
            return jsonify({'code': 400, 'message': 'content_ids 必须是数组'})

        # 限制批量数量
        max_batch = 20
        if len(content_ids) > max_batch:
            return jsonify({'code': 400, 'message': f'单次批量分析最多 {max_batch} 条'})

        task_queue = get_task_queue()
        queued = []
        skipped = []

        for content_id in content_ids:
            # 检查内容是否存在
            content = db.session.get(KnowledgeContent, content_id)
            if not content:
                skipped.append({'content_id': content_id, 'reason': '内容不存在'})
                continue

            # 添加到队列
            task = task_queue.add_content_task(
                content_id=content_id,
                app=current_app._get_current_object()
            )

            if task:
                queued.append(content_id)
            else:
                skipped.append({'content_id': content_id, 'reason': '已在队列中'})

        return jsonify({
            'code': 200,
            'message': f'已加入 {len(queued)} 条到分析队列',
            'data': {
                'queued': queued,
                'skipped': skipped,
                'total': len(content_ids)
            }
        })

    except Exception as e:
        logger.error(f"批量分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'批量分析失败: {str(e)}'})


@content_analysis_api.route('/contents/batch-delete', methods=['POST'])
@login_required
def batch_delete_contents():
    """批量删除内容"""
    try:
        from models.models import KnowledgeContent, db

        data = request.get_json()
        content_ids = data.get('content_ids', [])

        if not content_ids:
            return jsonify({'code': 400, 'message': '请提供要删除的内容ID列表'})

        if not isinstance(content_ids, list):
            return jsonify({'code': 400, 'message': 'content_ids 必须是数组'})

        deleted = []
        skipped = []

        for content_id in content_ids:
            content = db.session.get(KnowledgeContent, content_id)
            if content:
                db.session.delete(content)
                deleted.append(content_id)
            else:
                skipped.append({'content_id': content_id, 'reason': '内容不存在'})

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': f'已删除 {len(deleted)} 条内容',
            'data': {
                'deleted': deleted,
                'skipped': skipped,
                'total': len(content_ids)
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量删除失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'批量删除失败: {str(e)}'})


@content_analysis_api.route('/contents/queue-status', methods=['GET'])
@login_required
def get_content_queue_status():
    """获取内容分析队列状态"""
    try:
        from services.analysis_task_queue import get_task_queue

        task_queue = get_task_queue()
        status = task_queue.get_queue_status()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'content_queue': status
            }
        })

    except Exception as e:
        logger.error(f"获取队列状态失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})
