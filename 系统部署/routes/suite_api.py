"""
全链路营销套件 API

整合蓝海分析、运营规划、内容创作，提供一站式解决方案。

使用方式：
1. 完整流程：POST /api/suite/complete
2. 单项服务：
   - POST /api/blue-ocean/analyze
   - POST /api/operations/plan
   - POST /api/content/create
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

from app import db
from models.blue_ocean_models import BlueOceanAnalysis
from services.blue_ocean_analyzer import BlueOceanAnalyzer
from services.operation_plan_generator import OperationPlanGenerator

logger = logging.getLogger(__name__)

suite_bp = Blueprint('suite', __name__, url_prefix='/api/suite')


@suite_bp.route('/complete', methods=['POST'])
def complete_marketing_solution():
    """
    一键生成完整营销解决方案

    请求参数：
    {
        "business_description": "业务描述",
        "business_type": "toc/tob/both",
        "industry": "行业名称",
        "options": {
            "include_content": true,
            "content_count": 10
        }
    }

    返回：
    {
        "success": true,
        "data": {
            "analysis_id": 123,
            "plan_id": 456,
            "status": "completed"
        }
    }
    """
    try:
        data = request.get_json() or {}

        business_description = data.get('business_description')
        business_type = data.get('business_type', 'toc')
        industry = data.get('industry')
        options = data.get('options', {})

        if not business_description:
            return jsonify({
                'success': False,
                'error': '缺少业务描述'
            }), 400

        # Step 1: 蓝海分析
        logger.info("[Suite] Step 1: 开始蓝海分析...")
        analysis = BlueOceanAnalysis(
            user_id=1,  # TODO: 从 session 获取
            name=f"蓝海分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            industry=industry,
            business_type=business_type,
            status='processing'
        )
        db.session.add(analysis)
        db.session.commit()

        # 异步执行分析（简化版，同步执行）
        _run_analysis_sync(analysis.id, business_description, business_type, industry)

        # Step 2: 运营规划（如果需要）
        plan_data = None
        if options.get('include_planning', True):
            logger.info("[Suite] Step 2: 开始运营规划...")
            # 提取分析结果
            analysis_obj = BlueOceanAnalysis.query.get(analysis.id)
            if analysis_obj and analysis_obj.status == 'completed':
                generator = OperationPlanGenerator()
                plan_data = generator.generate(analysis_obj)

        # Step 3: 内容创作（如果需要）
        content_data = None
        if options.get('include_content', False):
            logger.info("[Suite] Step 3: 开始内容创作...")
            # TODO: 调用内容创作服务

        return jsonify({
            'success': True,
            'data': {
                'analysis_id': analysis.id,
                'analysis_status': analysis.status,
                'plan_data': plan_data,
                'content_data': content_data,
                'created_at': analysis.created_at.isoformat() if analysis.created_at else None
            }
        })

    except Exception as e:
        logger.error(f"[Suite] 生成解决方案失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _run_analysis_sync(analysis_id: int, description: str, business_type: str, industry: str = None):
    """同步执行蓝海分析"""
    try:
        analyzer = BlueOceanAnalyzer()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                analyzer.analyze(description, business_type, industry)
            )
        finally:
            loop.close()

        # 更新数据库
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            analysis.industry_report = result.get('industry_report')
            analysis.blue_ocean_opportunities = result.get('blue_ocean_opportunities')
            analysis.target_personas = result.get('target_personas')
            analysis.keyword_library = result.get('keyword_library')
            analysis.topic_library = result.get('topic_library')
            analysis.time_insights = result.get('time_insights')
            analysis.status = 'completed'
            db.session.commit()
            logger.info(f"[Suite] 蓝海分析完成: {analysis_id}")

    except Exception as e:
        logger.error(f"[Suite] 蓝海分析失败: {e}")
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            analysis.status = 'failed'
            db.session.commit()


@suite_bp.route('/analysis/<int:analysis_id>', methods=['GET'])
def get_suite_analysis(analysis_id):
    """获取蓝海分析结果"""
    analysis = BlueOceanAnalysis.query.get_or_404(analysis_id)

    return jsonify({
        'success': True,
        'data': {
            'id': analysis.id,
            'name': analysis.name,
            'industry': analysis.industry,
            'business_type': analysis.business_type,
            'status': analysis.status,
            'industry_report': analysis.industry_report,
            'blue_ocean_opportunities': analysis.blue_ocean_opportunities,
            'target_personas': analysis.target_personas,
            'keyword_library': analysis.keyword_library,
            'topic_library': analysis.topic_library,
            'time_insights': analysis.time_insights,
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
            'updated_at': analysis.updated_at.isoformat() if analysis.updated_at else None
        }
    })


@suite_bp.route('/skill-info', methods=['GET'])
def get_skill_info():
    """获取 Skill 索引信息"""
    return jsonify({
        'success': True,
        'data': {
            'skills': [
                {
                    'name': 'blue-ocean-expert',
                    'description': '蓝海分析专家',
                    'path': '.cursor/skills/blue-ocean-expert/',
                    'capabilities': [
                        '行业分析',
                        '蓝海机会发现',
                        '人群画像',
                        '关键词库生成',
                        '选题库生成',
                        '时间洞察'
                    ]
                },
                {
                    'name': 'operations-expert',
                    'description': '运营规划专家',
                    'path': '.cursor/skills/operations-expert/',
                    'capabilities': [
                        '账号设计',
                        '内容矩阵规划',
                        '五阶段运营规划',
                        '变现路径设计'
                    ]
                },
                {
                    'name': 'content-creator',
                    'description': '内容创作专家',
                    'path': '.cursor/skills/content-creator/',
                    'capabilities': [
                        '短视频脚本创作',
                        '图文内容生成',
                        '选题优化'
                    ]
                },
                {
                    'name': 'douyin-marketing-suite',
                    'description': '全链路营销套件',
                    'path': '.cursor/skills/douyin-marketing-suite/',
                    'capabilities': [
                        '一键生成完整方案',
                        '全链路整合'
                    ]
                }
            ],
            'flow': [
                'business_description',
                'blue_ocean_analysis',
                'operations_planning',
                'content_creation'
            ]
        }
    })
