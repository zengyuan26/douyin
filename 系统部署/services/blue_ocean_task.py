"""
蓝海分析异步任务
使用 Celery 执行后台任务
"""

import asyncio
from celery import Celery
from models.models import db, BlueOceanAnalysis

# Celery 配置
celery_app = Celery('blue_ocean_tasks',
                     broker='redis://localhost:6379/0',
                     backend='redis://localhost:6379/0')


@celery_app.task(bind=True, max_retries=3)
def run_blue_ocean_analysis(self, analysis_id: int, description: str, business_type: str, industry: str = None):
    """
    后台执行蓝海分析任务

    Args:
        analysis_id: 分析记录ID
        description: 业务描述
        business_type: 业务类型
        industry: 行业
    """
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 执行分析
        analyzer = None
        try:
            from services.blue_ocean_analyzer import BlueOceanAnalyzer
            analyzer = BlueOceanAnalyzer()

            # 执行异步分析
            result = loop.run_until_complete(
                analyzer.analyze(description, business_type, industry)
            )

            # 更新数据库
            update_analysis_result(analysis_id, result)

        finally:
            loop.close()

        return {'status': 'completed', 'analysis_id': analysis_id}

    except Exception as e:
        # 更新状态为失败
        update_analysis_status(analysis_id, 'failed', str(e))

        # 如果有重试次数，重试
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)

        return {'status': 'failed', 'error': str(e)}


def update_analysis_result(analysis_id: int, result: dict):
    """更新分析结果"""
    from flask import current_app
    from app import create_app

    app = current_app._get_current_object() if current_app else create_app()

    with app.app_context():
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            analysis.industry_report = result.get('industry_report')
            analysis.blue_ocean_opportunities = result.get('blue_ocean_opportunities')
            analysis.target_personas = result.get('target_personas')
            analysis.time_insights = result.get('time_insights')
            analysis.keyword_library = result.get('keyword_library')
            analysis.topic_library = result.get('topic_library')
            analysis.status = 'completed'
            db.session.commit()


def update_analysis_status(analysis_id: int, status: str, error: str = None):
    """更新分析状态"""
    from flask import current_app
    from app import create_app

    app = current_app._get_current_object() if current_app else create_app()

    with app.app_context():
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            analysis.status = status
            if error:
                analysis.error_message = error
            db.session.commit()


@celery_app.task
def poll_analysis_status(analysis_id: int):
    """轮询分析状态（用于前端轮询）"""
    from flask import current_app
    from app import create_app

    app = current_app._get_current_object() if current_app else create_app()

    with app.app_context():
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            return {
                'id': analysis.id,
                'status': analysis.status
            }
        return None
