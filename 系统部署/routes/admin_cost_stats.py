# -*- coding: utf-8 -*-
"""
LLM 成本统计 API

路由前缀：/admin/api/public
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required
from models.models import db
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

# 创建 Blueprint
admin_cost_stats_bp = Blueprint('admin_cost_stats', __name__, url_prefix='/admin/api/public')


def init_llm_log_model():
    """延迟导入LLM日志模型"""
    try:
        from models.public_models import PublicLLMCallLog
        return True
    except ImportError:
        return False


# =============================================================================
# 成本统计 API
# =============================================================================

@admin_cost_stats_bp.route('/cost-stats', methods=['GET'])
@login_required
def get_cost_stats():
    """获取成本统计概览"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': {
                    'today': {'total_cost': 0, 'total_tokens': 0, 'call_count': 0},
                    'week': {'total_cost': 0, 'total_tokens': 0, 'call_count': 0},
                    'month': {'total_cost': 0, 'total_tokens': 0, 'call_count': 0},
                    'total': {'total_cost': 0, 'total_tokens': 0, 'call_count': 0}
                }
            })

        from models.public_models import PublicLLMCallLog

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)

        # 今日统计
        today_stats = db.session.query(
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= today_start,
            PublicLLMCallLog.status == 'success'
        ).first()

        # 本周统计
        week_stats = db.session.query(
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= week_start,
            PublicLLMCallLog.status == 'success'
        ).first()

        # 本月统计
        month_stats = db.session.query(
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= month_start,
            PublicLLMCallLog.status == 'success'
        ).first()

        # 总计统计
        total_stats = db.session.query(
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.status == 'success'
        ).first()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'today': {
                    'total_cost': float(today_stats.total_cost or 0),
                    'total_tokens': int(today_stats.total_tokens or 0),
                    'call_count': int(today_stats.call_count or 0)
                },
                'week': {
                    'total_cost': float(week_stats.total_cost or 0),
                    'total_tokens': int(week_stats.total_tokens or 0),
                    'call_count': int(week_stats.call_count or 0)
                },
                'month': {
                    'total_cost': float(month_stats.total_cost or 0),
                    'total_tokens': int(month_stats.total_tokens or 0),
                    'call_count': int(month_stats.call_count or 0)
                },
                'total': {
                    'total_cost': float(total_stats.total_cost or 0),
                    'total_tokens': int(total_stats.total_tokens or 0),
                    'call_count': int(total_stats.call_count or 0)
                }
            }
        })

    except Exception as e:
        logger.error(f"获取成本统计失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/cost-stats/by-model', methods=['GET'])
@login_required
def get_cost_by_model():
    """按模型统计成本"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': []
            })

        from models.public_models import PublicLLMCallLog

        now = datetime.utcnow()
        days = request.args.get('days', 30, type=int)
        start_date = now - timedelta(days=days)

        results = db.session.query(
            PublicLLMCallLog.model,
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.input_tokens).label('input_tokens'),
            func.sum(PublicLLMCallLog.output_tokens).label('output_tokens'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count'),
            func.avg(PublicLLMCallLog.duration_ms).label('avg_duration')
        ).filter(
            PublicLLMCallLog.created_at >= start_date,
            PublicLLMCallLog.status == 'success'
        ).group_by(
            PublicLLMCallLog.model
        ).order_by(
            func.sum(PublicLLMCallLog.cost).desc()
        ).all()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'model': r.model or 'unknown',
                'total_cost': float(r.total_cost or 0),
                'input_tokens': int(r.input_tokens or 0),
                'output_tokens': int(r.output_tokens or 0),
                'total_tokens': int(r.total_tokens or 0),
                'call_count': int(r.call_count or 0),
                'avg_duration': float(r.avg_duration or 0)
            } for r in results]
        })

    except Exception as e:
        logger.error(f"获取模型统计失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/cost-stats/by-type', methods=['GET'])
@login_required
def get_cost_by_type():
    """按调用类型统计成本"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': []
            })

        from models.public_models import PublicLLMCallLog

        now = datetime.utcnow()
        days = request.args.get('days', 30, type=int)
        start_date = now - timedelta(days=days)

        results = db.session.query(
            PublicLLMCallLog.call_type,
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= start_date,
            PublicLLMCallLog.status == 'success'
        ).group_by(
            PublicLLMCallLog.call_type
        ).order_by(
            func.sum(PublicLLMCallLog.cost).desc()
        ).all()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'call_type': r.call_type or 'unknown',
                'total_cost': float(r.total_cost or 0),
                'total_tokens': int(r.total_tokens or 0),
                'call_count': int(r.call_count or 0)
            } for r in results]
        })

    except Exception as e:
        logger.error(f"获取类型统计失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/cost-stats/by-user', methods=['GET'])
@login_required
def get_cost_by_user():
    """按用户统计成本"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': []
            })

        from models.public_models import PublicLLMCallLog, PublicUser

        now = datetime.utcnow()
        days = request.args.get('days', 30, type=int)
        start_date = now - timedelta(days=days)
        limit = request.args.get('limit', 10, type=int)

        results = db.session.query(
            PublicLLMCallLog.user_id,
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= start_date,
            PublicLLMCallLog.status == 'success',
            PublicLLMCallLog.user_id.isnot(None)
        ).group_by(
            PublicLLMCallLog.user_id
        ).order_by(
            func.sum(PublicLLMCallLog.cost).desc()
        ).limit(limit).all()

        # 获取用户信息
        user_ids = [r.user_id for r in results]
        users = {u.id: u.email for u in PublicUser.query.filter(PublicUser.id.in_(user_ids)).all()}

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'user_id': r.user_id,
                'email': users.get(r.user_id, 'Unknown'),
                'total_cost': float(r.total_cost or 0),
                'total_tokens': int(r.total_tokens or 0),
                'call_count': int(r.call_count or 0)
            } for r in results]
        })

    except Exception as e:
        logger.error(f"获取用户统计失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/cost-stats/daily', methods=['GET'])
@login_required
def get_cost_daily():
    """获取每日成本趋势"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': []
            })

        from models.public_models import PublicLLMCallLog

        now = datetime.utcnow()
        days = request.args.get('days', 7, type=int)
        start_date = now - timedelta(days=days)

        results = db.session.query(
            func.date(PublicLLMCallLog.created_at).label('date'),
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= start_date,
            PublicLLMCallLog.status == 'success'
        ).group_by(
            func.date(PublicLLMCallLog.created_at)
        ).order_by(
            func.date(PublicLLMCallLog.created_at)
        ).all()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'date': str(r.date),
                'total_cost': float(r.total_cost or 0),
                'total_tokens': int(r.total_tokens or 0),
                'call_count': int(r.call_count or 0)
            } for r in results]
        })

    except Exception as e:
        logger.error(f"获取每日趋势失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/cost-stats/hourly', methods=['GET'])
@login_required
def get_cost_hourly():
    """获取每小时成本趋势（今日）"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': []
            })

        from models.public_models import PublicLLMCallLog
        from sqlalchemy import extract

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        results = db.session.query(
            extract('hour', PublicLLMCallLog.created_at).label('hour'),
            func.sum(PublicLLMCallLog.cost).label('total_cost'),
            func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
            func.count(PublicLLMCallLog.id).label('call_count')
        ).filter(
            PublicLLMCallLog.created_at >= today_start,
            PublicLLMCallLog.status == 'success'
        ).group_by(
            extract('hour', PublicLLMCallLog.created_at)
        ).order_by(
            extract('hour', PublicLLMCallLog.created_at)
        ).all()

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'hour': int(r.hour),
                'total_cost': float(r.total_cost or 0),
                'total_tokens': int(r.total_tokens or 0),
                'call_count': int(r.call_count or 0)
            } for r in results]
        })

    except Exception as e:
        logger.error(f"获取小时趋势失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@admin_cost_stats_bp.route('/llm-logs', methods=['GET'])
@login_required
def get_llm_logs():
    """获取LLM调用日志"""
    try:
        if not init_llm_log_model():
            return jsonify({
                'code': 200,
                'message': '模块未初始化',
                'data': {'items': [], 'total': 0}
            })

        from models.public_models import PublicLLMCallLog, PublicUser

        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(max(per_page, 1), 100)

        status = request.args.get('status')
        model = request.args.get('model')
        call_type = request.args.get('call_type')
        user_id = request.args.get('user_id', type=int)

        # 构建查询
        query = PublicLLMCallLog.query

        if status:
            query = query.filter(PublicLLMCallLog.status == status)
        if model:
            query = query.filter(PublicLLMCallLog.model == model)
        if call_type:
            query = query.filter(PublicLLMCallLog.call_type == call_type)
        if user_id:
            query = query.filter(PublicLLMCallLog.user_id == user_id)

        query = query.order_by(PublicLLMCallLog.created_at.desc())

        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # 获取用户信息
        user_ids = set(log.user_id for log in pagination.items if log.user_id)
        users = {u.id: u.email for u in PublicUser.query.filter(PublicUser.id.in_(user_ids)).all()} if user_ids else {}

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'items': [{
                    'id': log.id,
                    'user_id': log.user_id,
                    'user_email': users.get(log.user_id, 'Unknown') if log.user_id else None,
                    'call_type': log.call_type,
                    'model': log.model,
                    'input_tokens': log.input_tokens,
                    'output_tokens': log.output_tokens,
                    'total_tokens': log.total_tokens,
                    'cost': float(log.cost or 0),
                    'duration_ms': log.duration_ms,
                    'status': log.status,
                    'error_message': log.error_message,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                } for log in pagination.items],
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        logger.error(f"获取日志失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})
