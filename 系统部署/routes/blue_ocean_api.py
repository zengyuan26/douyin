"""
蓝海分析 API 路由
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models.models import db, BlueOceanAnalysis
from services.blue_ocean_analyzer import BlueOceanAnalyzer
import asyncio

blue_ocean_bp = Blueprint('blue_ocean', __name__, url_prefix='/public/api/blue-ocean')


@blue_ocean_bp.route('/analyze', methods=['POST'])
@login_required
def create_blue_ocean_analysis():
    """
    一次性生成蓝海分析报告
    包含：行业分析 + 蓝海机会 + 画像 + 关键词库 + 选题库 + 时间洞察
    """
    data = request.get_json()
    description = data.get('description')
    business_type = data.get('business_type', 'toc')
    industry = data.get('industry')

    if not description:
        return jsonify({'success': False, 'message': '请描述你的业务'}), 400

    # 创建分析记录
    analysis = BlueOceanAnalysis(
        user_id=current_user.id,
        name=f"蓝海分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        industry=industry,
        business_type=business_type,
        status='processing'
    )
    db.session.add(analysis)
    db.session.commit()

    # 后台执行分析（异步）
    try:
        from services.blue_ocean_task import run_blue_ocean_analysis
        run_blue_ocean_analysis.delay(analysis.id, description, business_type, industry)
    except Exception as e:
        # 如果 Celery 不可用，同步执行
        print(f"Celery 不可用，同步执行: {e}")
        _run_analysis_sync(analysis.id, description, business_type, industry)

    return jsonify({
        'success': True,
        'message': '分析已启动，请稍后刷新查看结果',
        'data': {
            'id': analysis.id,
            'status': 'processing'
        }
    })


def _run_analysis_sync(analysis_id: int, description: str, business_type: str, industry: str = None):
    """同步执行分析（Celery 不可用时使用）"""
    try:
        analyzer = BlueOceanAnalyzer()
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
            analysis.time_insights = result.get('time_insights')
            analysis.keyword_library = result.get('keyword_library')
            analysis.topic_library = result.get('topic_library')
            analysis.status = 'completed'
            db.session.commit()

            # 自动保存报告到 docs 目录
            try:
                _save_report_to_docs(analysis, result)
            except Exception as save_err:
                print(f"保存报告到docs目录失败: {save_err}")

    except Exception as e:
        print(f"同步分析失败: {e}")
        analysis = BlueOceanAnalysis.query.get(analysis_id)
        if analysis:
            analysis.status = 'failed'
            db.session.commit()


def _save_report_to_docs(analysis, result):
    """保存报告到 docs 目录"""
    import os
    from datetime import datetime

    # docs 目录路径
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')
    if not os.path.exists(docs_dir):
        return

    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in (analysis.name or '蓝海分析'))
    filename = f"{safe_name}_{timestamp}.md"
    filepath = os.path.join(docs_dir, filename)

    # 生成报告内容
    report_content = _generate_markdown_report(analysis)

    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"报告已保存到: {filepath}")


@blue_ocean_bp.route('/<int:analysis_id>', methods=['GET'])
@login_required
def get_blue_ocean_analysis(analysis_id):
    """获取蓝海分析报告"""
    analysis = BlueOceanAnalysis.query.filter_by(
        id=analysis_id,
        user_id=current_user.id
    ).first_or_404()

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
            'time_insights': analysis.time_insights,
            'keyword_library': analysis.keyword_library,
            'topic_library': analysis.topic_library,
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None,
            'updated_at': analysis.updated_at.isoformat() if analysis.updated_at else None
        }
    })


@blue_ocean_bp.route('/list', methods=['GET'])
@login_required
def list_blue_ocean_analyses():
    """获取蓝海分析列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    analyses = BlueOceanAnalysis.query.filter_by(
        user_id=current_user.id
    ).order_by(
        BlueOceanAnalysis.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'data': {
            'items': [{
                'id': a.id,
                'name': a.name,
                'industry': a.industry,
                'business_type': a.business_type,
                'status': a.status,
                'created_at': a.created_at.isoformat() if a.created_at else None
            } for a in analyses.items],
            'total': analyses.total,
            'page': analyses.page,
            'pages': analyses.pages,
            'has_next': analyses.has_next,
            'has_prev': analyses.has_prev
        }
    })


@blue_ocean_bp.route('/<int:analysis_id>', methods=['DELETE'])
@login_required
def delete_blue_ocean_analysis(analysis_id):
    """删除蓝海分析"""
    analysis = BlueOceanAnalysis.query.filter_by(
        id=analysis_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(analysis)
    db.session.commit()

    return jsonify({'success': True, 'message': '删除成功'})


@blue_ocean_bp.route('/<int:analysis_id>/regenerate', methods=['POST'])
@login_required
def regenerate_analysis(analysis_id):
    """重新生成蓝海分析"""
    analysis = BlueOceanAnalysis.query.filter_by(
        id=analysis_id,
        user_id=current_user.id
    ).first_or_404()

    # 更新状态
    analysis.status = 'processing'
    db.session.commit()

    # 重新执行分析
    description = request.get_json().get('description') if request.get_json() else None

    try:
        from services.blue_ocean_task import run_blue_ocean_analysis
        run_blue_ocean_analysis.delay(
            analysis.id,
            description or f"{analysis.industry or ''}业务",
            analysis.business_type,
            analysis.industry
        )
    except Exception as e:
        print(f"Celery 不可用，同步执行: {e}")
        _run_analysis_sync(
            analysis.id,
            description or f"{analysis.industry or ''}业务",
            analysis.business_type,
            analysis.industry
        )

    return jsonify({
        'success': True,
        'message': '重新生成中',
        'data': {'id': analysis.id, 'status': 'processing'}
    })


@blue_ocean_bp.route('/<int:analysis_id>/export', methods=['GET'])
@login_required
def export_analysis(analysis_id):
    """导出蓝海分析报告"""
    analysis = BlueOceanAnalysis.query.filter_by(
        id=analysis_id,
        user_id=current_user.id
    ).first_or_404()

    # 生成 Markdown 格式的报告
    report = _generate_markdown_report(analysis)

    return jsonify({
        'success': True,
        'data': {
            'report': report,
            'filename': f"{analysis.name}.md"
        }
    })


def _generate_markdown_report(analysis: BlueOceanAnalysis) -> str:
    """生成 Markdown 格式的报告"""
    report = f"""# {analysis.name}

生成时间：{analysis.created_at.strftime('%Y-%m-%d %H:%M:%S') if analysis.created_at else '未知'}

---

## 一、行业分析报告

{_format_json_to_markdown(analysis.industry_report)}

---

## 二、蓝海机会列表

{_format_list_to_markdown(analysis.blue_ocean_opportunities)}

---

## 三、目标人群画像

{_format_list_to_markdown(analysis.target_personas)}

---

## 四、时间维度洞察

{_format_json_to_markdown(analysis.time_insights)}

---

## 五、关键词库

{_format_keyword_library(analysis.keyword_library)}

---

## 六、选题库

{_format_topic_library(analysis.topic_library)}

---

## 七、数据统计

| 项目 | 数量 |
|------|------|
| 蓝海机会 | {len(analysis.blue_ocean_opportunities) if analysis.blue_ocean_opportunities else 0} |
| 目标人群 | {len(analysis.target_personas) if analysis.target_personas else 0} |
| 关键词 | {analysis.keyword_library.get('total_count', 0) if analysis.keyword_library else 0} |
| 选题 | {analysis.topic_library.get('total_count', 0) if analysis.topic_library else 0} |
"""
    return report


def _format_json_to_markdown(data) -> str:
    """将 JSON 格式化为 Markdown"""
    if not data:
        return "暂无数据"
    if isinstance(data, str):
        return data
    if isinstance(data, (list, dict)):
        import json
        return f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
    return str(data)


def _format_list_to_markdown(data) -> str:
    """将列表格式化为 Markdown"""
    if not data:
        return "暂无数据"
    if isinstance(data, list):
        result = []
        for i, item in enumerate(data, 1):
            if isinstance(item, dict):
                result.append(f"### {i}. {item.get('name', '未命名')}")
                for key, value in item.items():
                    if key not in ['name']:
                        result.append(f"- **{key}**: {value}")
            else:
                result.append(f"{i}. {item}")
        return "\n".join(result)
    return str(data)


def _format_keyword_library(data) -> str:
    """格式化关键词库"""
    if not data:
        return "暂无数据"

    result = []

    # 公用关键词
    public = data.get('public_keywords', [])
    if public:
        result.append("### 公用关键词")
        result.append(f"共 {len(public)} 个")
        for kw in public[:20]:  # 只显示前20个
            if isinstance(kw, dict):
                result.append(f"- {kw.get('keyword', '')} ({kw.get('type', '')})")
            else:
                result.append(f"- {kw}")
        if len(public) > 20:
            result.append(f"- ... 还有 {len(public) - 20} 个")

    # 画像专属关键词
    persona = data.get('persona_keywords', {})
    if persona:
        result.append("\n### 画像专属关键词")
        for persona_name, keywords in persona.items():
            result.append(f"\n#### {persona_name}")
            if isinstance(keywords, dict):
                for key, items in keywords.items():
                    if isinstance(items, list) and items:
                        result.append(f"- **{key}**: {', '.join(items[:10])}")
                        if len(items) > 10:
                            result.append(f"  ... 还有 {len(items) - 10} 个")
            elif isinstance(keywords, list):
                result.append(", ".join(keywords[:20]))

    result.append(f"\n\n**总计**: {data.get('total_count', 0)} 个关键词")
    return "\n".join(result)


def _format_topic_library(data) -> str:
    """格式化选题库"""
    if not data:
        return "暂无数据"

    result = []

    # 公用选题
    public = data.get('public_topics', [])
    if public:
        result.append("### 公用选题")
        result.append(f"共 {len(public)} 个")
        for tp in public[:20]:  # 只显示前20个
            if isinstance(tp, dict):
                result.append(f"- {tp.get('topic', '')} [{tp.get('type', '')}]")
            else:
                result.append(f"- {tp}")
        if len(public) > 20:
            result.append(f"- ... 还有 {len(public) - 20} 个")

    # 画像专属选题
    persona = data.get('persona_topics', {})
    if persona:
        result.append("\n### 画像专属选题")
        for persona_name, topics in persona.items():
            result.append(f"\n#### {persona_name}")
            if isinstance(topics, dict):
                for key, items in topics.items():
                    if isinstance(items, list) and items:
                        result.append(f"\n**{key}**:")
                        for item in items[:5]:
                            result.append(f"- {item}")
                        if len(items) > 5:
                            result.append(f"- ... 还有 {len(items) - 5} 个")

    result.append(f"\n\n**总计**: {data.get('total_count', 0)} 个选题")
    return "\n".join(result)
