"""
运营规划API接口

提供运营规划生成、查询、更新等接口
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

from models.public_models import db, SavedPortrait
from services.operations_planner import (
    OperationsPlanner,
    generate_operations_plan,
    get_stage_ratio,
    get_geo_modes_for_stage,
)

logger = logging.getLogger(__name__)

operations_bp = Blueprint('operations', __name__, url_prefix='/api/operations')


@operations_bp.route('/plan/generate', methods=['POST'])
def generate_operations_plan_api():
    """
    生成运营规划方案
    
    请求参数：
    {
        "portrait_id": 123,           # 画像ID（可选，与portraits二选一）
        "portraits": [...],            # 画像列表（可选，与portrait_id二选一）
        "business_info": {...},        # 业务信息
        "content_stage": "成长阶段",  # 账号内容阶段
        "target_topic_count": 30      # 目标选题数量
    }
    
    返回：
    {
        "success": true,
        "data": {
            "plan_id": "plan_xxx",
            "five_stage_plan": [...],
            "geo_mode_mapping": {...},
            ...
        }
    }
    """
    try:
        data = request.get_json() or {}
        
        portrait_id = data.get('portrait_id')
        portraits = data.get('portraits', [])
        business_info = data.get('business_info', {})
        content_stage = data.get('content_stage', '成长阶段')
        target_topic_count = data.get('target_topic_count', 30)
        
        # 优先级：直接传入的portraits > portrait_id获取 > 空
        if not portraits and portrait_id:
            portrait = db.session.get(SavedPortrait, portrait_id)
            if portrait:
                portraits = portrait.portraits or []
                # 尝试从画像中提取业务信息
                if portrait.business_info and not business_info:
                    business_info = portrait.business_info
                if portrait.industry and not business_info.get('industry'):
                    business_info['industry'] = portrait.industry
        
        if not portraits:
            return jsonify({
                'success': False,
                'error': '缺少画像数据'
            }), 400
        
        if not business_info:
            return jsonify({
                'success': False,
                'error': '缺少业务信息'
            }), 400
        
        # 生成运营规划
        plan = generate_operations_plan(
            portraits=portraits,
            business_info=business_info,
            content_stage=content_stage,
            target_topic_count=target_topic_count,
        )
        
        # 如果有portrait_id，保存到画像
        if portrait_id:
            portrait = db.session.get(SavedPortrait, portrait_id)
            if portrait:
                # 保存运营规划到画像的extra_data
                extra_data = portrait.extra_data or {}
                extra_data['operations_plan'] = plan
                extra_data['operations_plan_updated_at'] = datetime.utcnow().isoformat()
                portrait.extra_data = extra_data
                db.session.commit()
                logger.info(f"[OperationsAPI] 保存运营规划到画像: {portrait_id}")
        
        return jsonify({
            'success': True,
            'data': plan,
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 生成失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operations_bp.route('/plan/<int:portrait_id>', methods=['GET'])
def get_operations_plan_api(portrait_id):
    """
    获取画像的运营规划
    
    返回：
    {
        "success": true,
        "data": {...}  # 运营规划数据
    }
    """
    try:
        portrait = db.session.get(SavedPortrait, portrait_id)
        if not portrait:
            return jsonify({
                'success': False,
                'error': '画像不存在'
            }), 404
        
        extra_data = portrait.extra_data or {}
        operations_plan = extra_data.get('operations_plan')
        
        if not operations_plan:
            return jsonify({
                'success': False,
                'error': '该画像尚未生成运营规划'
            }), 404
        
        return jsonify({
            'success': True,
            'data': operations_plan,
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 查询失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operations_bp.route('/plan/<int:portrait_id>/regenerate', methods=['POST'])
def regenerate_operations_plan_api(portrait_id):
    """
    重新生成运营规划
    
    请求参数：
    {
        "content_stage": "成长阶段",  # 可选，指定新的账号阶段
        "target_topic_count": 30      # 可选，指定新的目标数量
    }
    """
    try:
        portrait = db.session.get(SavedPortrait, portrait_id)
        if not portrait:
            return jsonify({
                'success': False,
                'error': '画像不存在'
            }), 404
        
        data = request.get_json() or {}
        content_stage = data.get('content_stage', '成长阶段')
        target_topic_count = data.get('target_topic_count', 30)
        
        # 获取画像数据
        portraits = portrait.portraits or []
        business_info = portrait.business_info or {}
        if portrait.industry:
            business_info['industry'] = portrait.industry
        
        if not portraits:
            return jsonify({
                'success': False,
                'error': '画像数据为空'
            }), 400
        
        # 重新生成
        plan = generate_operations_plan(
            portraits=portraits,
            business_info=business_info,
            content_stage=content_stage,
            target_topic_count=target_topic_count,
        )
        
        # 保存
        extra_data = portrait.extra_data or {}
        extra_data['operations_plan'] = plan
        extra_data['operations_plan_updated_at'] = datetime.utcnow().isoformat()
        portrait.extra_data = extra_data
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': plan,
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 重新生成失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operations_bp.route('/stage/ratios', methods=['GET'])
def get_stage_ratios_api():
    """
    获取五段式阶段配比
    
    查询参数：
    - content_stage: 账号阶段（起号阶段/成长阶段/成熟阶段）
    
    返回：
    {
        "success": true,
        "data": {
            "audience": 0.15,
            "pain": 0.25,
            "compare": 0.30,
            "vision": 0.15,
            "hesitation": 0.15
        }
    }
    """
    try:
        content_stage = request.args.get('content_stage', '成长阶段')
        ratios = get_stage_ratio(content_stage)
        
        return jsonify({
            'success': True,
            'data': ratios,
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 获取配比失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operations_bp.route('/geo/modes', methods=['GET'])
def get_geo_modes_api():
    """
    获取五段式阶段对应的GEO模式
    
    查询参数：
    - stage_key: 五段式阶段key（audience/pain/compare/vision/hesitation）
    
    返回：
    {
        "success": true,
        "data": ["场景故事型", "情感共鸣型"]
    }
    """
    try:
        stage_key = request.args.get('stage_key', 'pain')
        geo_modes = get_geo_modes_for_stage(stage_key)
        
        return jsonify({
            'success': True,
            'data': geo_modes,
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 获取GEO模式失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operations_bp.route('/plan/export/markdown/<int:portrait_id>', methods=['GET'])
def export_plan_markdown_api(portrait_id):
    """
    导出运营规划为Markdown格式
    
    返回：
    Markdown文本
    """
    try:
        portrait = db.session.get(SavedPortrait, portrait_id)
        if not portrait:
            return jsonify({
                'success': False,
                'error': '画像不存在'
            }), 404
        
        extra_data = portrait.extra_data or {}
        operations_plan = extra_data.get('operations_plan')
        
        if not operations_plan:
            return jsonify({
                'success': False,
                'error': '该画像尚未生成运营规划'
            }), 404
        
        # 转换为Markdown
        planner = OperationsPlanner()
        
        # 重建Plan对象
        from services.operations_planner import StagePlan, OperationsPlan
        
        five_stage_plan = [
            StagePlan(
                stage_key=s['stage_key'],
                stage_name=s['stage_name'],
                ratio=s['ratio'],
                topic_count=s['topic_count'],
                content_types=s['content_types'],
                geo_modes=s['geo_modes'],
                description=s['description'],
            )
            for s in operations_plan.get('five_stage_plan', [])
        ]
        
        plan = OperationsPlan(
            plan_id=operations_plan.get('plan_id', ''),
            business_name=operations_plan.get('business_name', ''),
            industry=operations_plan.get('industry', ''),
            content_stage=operations_plan.get('content_stage', ''),
            account_positioning=operations_plan.get('account_positioning', ''),
            ip_persona=operations_plan.get('ip_persona', ''),
            content_style=operations_plan.get('content_style', ''),
            differentiation=operations_plan.get('differentiation', ''),
            five_stage_plan=five_stage_plan,
            total_topic_count=operations_plan.get('total_topic_count', 0),
            geo_mode_mapping=operations_plan.get('geo_mode_mapping', {}),
            content_ratio=operations_plan.get('content_ratio', {}),
            content_sequence=operations_plan.get('content_sequence', []),
            first_week_topics=operations_plan.get('first_week_topics', []),
            content_calendar=operations_plan.get('content_calendar', {}),
            created_at=operations_plan.get('created_at', ''),
            version=operations_plan.get('version', '1.0'),
        )
        
        markdown = planner.to_markdown(plan)
        
        return jsonify({
            'success': True,
            'data': {
                'markdown': markdown,
                'filename': f"{plan.business_name}_运营规划方案.md",
            }
        })
        
    except Exception as e:
        logger.exception(f"[OperationsAPI] 导出失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# 集成到内容生成的辅助函数
# =============================================================================

def get_operations_plan_for_content(portrait_id: int) -> dict:
    """
    获取运营规划，用于内容生成流程
    
    这个函数会在内容生成时被调用，传递五段式和GEO模式信息
    """
    try:
        portrait = db.session.get(SavedPortrait, portrait_id)
        if not portrait:
            return {}
        
        extra_data = portrait.extra_data or {}
        return extra_data.get('operations_plan', {})
        
    except Exception as e:
        logger.warning(f"[OperationsAPI] 获取内容生成上下文失败: {e}")
        return {}


def get_five_stage_for_topic(portrait_id: int, topic_stage_key: str) -> dict:
    """
    获取选题对应的五段式阶段规划
    
    Args:
        portrait_id: 画像ID
        topic_stage_key: 选题所属的五段式阶段key
    
    Returns:
        {
            "stage_name": "痛点放大",
            "ratio": 0.25,
            "topic_count": 8,
            "content_types": ["原因分析", "避坑指南"],
            "geo_modes": ["问题诊断型", "知识科普型"],
        }
    """
    plan = get_operations_plan_for_content(portrait_id)
    if not plan:
        return {}
    
    five_stage_plan = plan.get('five_stage_plan', [])
    for stage in five_stage_plan:
        if stage.get('stage_key') == topic_stage_key:
            return {
                'stage_name': stage.get('stage_name', ''),
                'ratio': stage.get('ratio', 0),
                'topic_count': stage.get('topic_count', 0),
                'content_types': stage.get('content_types', []),
                'geo_modes': stage.get('geo_modes', []),
            }
    
    return {}
