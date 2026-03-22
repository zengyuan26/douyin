# -*- coding: utf-8 -*-
"""
待处理行业管理 API

路由前缀：/admin/api/public
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.models import db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# 创建 Blueprint
admin_pending_industries_bp = Blueprint('admin_pending_industries', __name__, url_prefix='/admin/api/public')


def init_pending_industry_model():
    """延迟导入待处理行业模型"""
    try:
        from models.public_models import PendingIndustry
        return True
    except ImportError:
        return False


# =============================================================================
# 待处理行业 API
# =============================================================================

@admin_pending_industries_bp.route('/pending-industries', methods=['GET'])
@login_required
def get_pending_industries():
    """获取待处理行业列表"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化，请先运行数据库迁移'
            })

        from models.public_models import PendingIndustry

        # 获取查询参数
        status = request.args.get('status', 'pending')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(max(per_page, 1), 100)

        # 构建查询
        query = PendingIndustry.query

        if status and status != 'all':
            query = query.filter_by(status=status)

        query = query.order_by(PendingIndustry.priority.desc(), PendingIndustry.created_at.desc())

        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'items': [{
                    'id': item.id,
                    'industry_name': item.industry_name,
                    'matched_industry': item.matched_industry,
                    'source_count': item.source_count,
                    'profile_summary': item.profile_summary,
                    'status': item.status,
                    'priority': item.priority,
                    'created_at': item.created_at.isoformat() if item.created_at else None,
                    'approved_at': item.approved_at.isoformat() if item.approved_at else None,
                    'processed_at': item.processed_at.isoformat() if item.processed_at else None,
                } for item in items],
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        logger.error(f"获取待处理行业失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/<int:item_id>', methods=['GET'])
@login_required
def get_pending_industry_detail(item_id):
    """获取待处理行业详情"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        item = PendingIndustry.query.get(item_id)
        if not item:
            return jsonify({'code': 404, 'message': '记录不存在'})

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'id': item.id,
                'industry_name': item.industry_name,
                'matched_industry': item.matched_industry,
                'source_count': item.source_count,
                'profile_summary': item.profile_summary,
                'sample_descriptions': item.sample_descriptions,
                'status': item.status,
                'priority': item.priority,
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'approved_at': item.approved_at.isoformat() if item.approved_at else None,
                'processed_at': item.processed_at.isoformat() if item.processed_at else None,
            }
        })

    except Exception as e:
        logger.error(f"获取详情失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/<int:item_id>/approve', methods=['POST'])
@login_required
def approve_pending_industry(item_id):
    """批准待处理行业"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        item = PendingIndustry.query.get(item_id)
        if not item:
            return jsonify({'code': 404, 'message': '记录不存在'})

        data = request.get_json() or {}
        target_industry = data.get('target_industry', item.matched_industry)

        # 更新状态
        item.status = 'approved'
        item.matched_industry = target_industry
        item.approved_at = datetime.utcnow()
        item.approved_by = current_user.id

        db.session.commit()

        # TODO: 触发后台任务生成关键词和选题

        return jsonify({
            'code': 200,
            'message': '已批准，等待后台处理',
            'data': {
                'id': item.id,
                'status': item.status
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"批准失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'批准失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/<int:item_id>/reject', methods=['POST'])
@login_required
def reject_pending_industry(item_id):
    """拒绝待处理行业"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        item = PendingIndustry.query.get(item_id)
        if not item:
            return jsonify({'code': 404, 'message': '记录不存在'})

        data = request.get_json() or {}
        reason = data.get('reason', '')

        # 更新状态
        item.status = 'rejected'
        item.reject_reason = reason
        item.approved_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '已拒绝',
            'data': {
                'id': item.id,
                'status': item.status
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"拒绝失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'拒绝失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/<int:item_id>/merge', methods=['POST'])
@login_required
def merge_pending_industry(item_id):
    """合并待处理行业到现有行业"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        item = PendingIndustry.query.get(item_id)
        if not item:
            return jsonify({'code': 404, 'message': '记录不存在'})

        data = request.get_json() or {}
        target_industry = data.get('target_industry')

        if not target_industry:
            return jsonify({'code': 400, 'message': '请指定目标行业'})

        # 更新状态
        item.status = 'merged'
        item.matched_industry = target_industry
        item.approved_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': f'已合并到 {target_industry}',
            'data': {
                'id': item.id,
                'status': item.status,
                'matched_industry': target_industry
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"合并失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'合并失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/<int:item_id>/process', methods=['POST'])
@login_required
def process_pending_industry(item_id):
    """手动触发处理待处理行业"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        item = PendingIndustry.query.get(item_id)
        if not item:
            return jsonify({'code': 404, 'message': '记录不存在'})

        if item.status != 'approved':
            return jsonify({'code': 400, 'message': '只有已批准的行业才能处理'})

        # 更新状态为处理中
        item.status = 'processing'
        db.session.commit()

        # TODO: 触发后台任务

        return jsonify({
            'code': 200,
            'message': '已加入处理队列',
            'data': {
                'id': item.id,
                'status': 'processing'
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"处理失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'处理失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/batch-action', methods=['POST'])
@login_required
def batch_action_pending_industries():
    """批量操作待处理行业"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 404,
                'message': '待处理行业模块未初始化'
            })

        from models.public_models import PendingIndustry

        data = request.get_json() or {}
        action = data.get('action')
        item_ids = data.get('item_ids', [])

        if not action or not item_ids:
            return jsonify({'code': 400, 'message': '缺少必要参数'})

        target_industry = data.get('target_industry')

        success_count = 0
        for item_id in item_ids:
            item = PendingIndustry.query.get(item_id)
            if not item:
                continue

            if action == 'approve':
                item.status = 'approved'
                if target_industry:
                    item.matched_industry = target_industry
                item.approved_at = datetime.utcnow()
                success_count += 1

            elif action == 'reject':
                item.status = 'rejected'
                item.approved_at = datetime.utcnow()
                success_count += 1

            elif action == 'process':
                if item.status == 'approved':
                    item.status = 'processing'
                    success_count += 1

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': f'成功处理 {success_count} 条记录',
            'data': {
                'success_count': success_count,
                'total': len(item_ids)
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量操作失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'批量操作失败: {str(e)}'})


@admin_pending_industries_bp.route('/pending-industries/stats', methods=['GET'])
@login_required
def get_pending_industries_stats():
    """获取待处理行业统计"""
    try:
        if not init_pending_industry_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': {
                    'total': 0,
                    'pending': 0,
                    'approved': 0,
                    'processing': 0,
                    'completed': 0,
                    'rejected': 0
                }
            })

        from models.public_models import PendingIndustry

        # 统计各状态数量
        stats = {
            'total': PendingIndustry.query.count(),
            'pending': PendingIndustry.query.filter_by(status='pending').count(),
            'approved': PendingIndustry.query.filter_by(status='approved').count(),
            'processing': PendingIndustry.query.filter_by(status='processing').count(),
            'completed': PendingIndustry.query.filter_by(status='completed').count(),
            'rejected': PendingIndustry.query.filter_by(status='rejected').count(),
        }

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取统计失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})
