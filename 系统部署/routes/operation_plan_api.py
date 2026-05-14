"""
运营规划 API 路由
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models.models import db, OperationPlan, BlueOceanAnalysis
from services.operation_plan_generator import OperationPlanGenerator

operation_plan_bp = Blueprint('operation_plan', __name__, url_prefix='/public/api/operation-plan')


@operation_plan_bp.route('/generate', methods=['POST'])
@login_required
def generate_operation_plan():
    """生成运营规划方案"""
    data = request.get_json()
    blue_ocean_id = data.get('blue_ocean_id')

    if not blue_ocean_id:
        return jsonify({'success': False, 'message': '缺少蓝海分析ID'}), 400

    # 获取蓝海分析
    analysis = BlueOceanAnalysis.query.filter_by(
        id=blue_ocean_id,
        user_id=current_user.id
    ).first()

    if not analysis:
        return jsonify({'success': False, 'message': '蓝海分析不存在'}), 404

    if analysis.status != 'completed':
        return jsonify({'success': False, 'message': '蓝海分析尚未完成'}), 400

    # 检查是否已存在运营规划
    existing = OperationPlan.query.filter_by(
        blue_ocean_id=blue_ocean_id
    ).first()

    if existing:
        return jsonify({
            'success': True,
            'message': '运营规划已存在',
            'data': {
                'id': existing.id,
                'account_name': existing.account_name,
                'status': existing.status
            }
        })

    # 生成运营规划
    try:
        generator = OperationPlanGenerator()
        plan_data = generator.generate(analysis)

        # 保存
        plan = OperationPlan(
            user_id=current_user.id,
            blue_ocean_id=analysis.id,
            account_name=plan_data.get('account_name'),
            account_bio=plan_data.get('account_bio'),
            avatar_suggestion=plan_data.get('avatar_suggestion'),
            content_tags=plan_data.get('content_tags'),
            content_ratio=plan_data.get('content_ratio'),
            plan_content=plan_data.get('plan_content'),
            status='completed'
        )
        db.session.add(plan)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '运营规划生成成功',
            'data': {
                'id': plan.id,
                'account_name': plan.account_name,
                'status': plan.status
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'生成失败: {str(e)}'
        }), 500


@operation_plan_bp.route('/<int:plan_id>', methods=['GET'])
@login_required
def get_operation_plan(plan_id):
    """获取运营规划方案"""
    plan = OperationPlan.query.filter_by(
        id=plan_id,
        user_id=current_user.id
    ).first_or_404()

    return jsonify({
        'success': True,
        'data': {
            'id': plan.id,
            'blue_ocean_id': plan.blue_ocean_id,
            'account_name': plan.account_name,
            'account_bio': plan.account_bio,
            'avatar_suggestion': plan.avatar_suggestion,
            'content_tags': plan.content_tags,
            'content_ratio': plan.content_ratio,
            'plan_content': plan.plan_content,
            'status': plan.status,
            'created_at': plan.created_at.isoformat() if plan.created_at else None,
            'updated_at': plan.updated_at.isoformat() if plan.updated_at else None
        }
    })


@operation_plan_bp.route('/by-analysis/<int:blue_ocean_id>', methods=['GET'])
@login_required
def get_operation_plan_by_analysis(blue_ocean_id):
    """根据蓝海分析ID获取运营规划"""
    plan = OperationPlan.query.filter_by(
        blue_ocean_id=blue_ocean_id,
        user_id=current_user.id
    ).first()

    if not plan:
        return jsonify({
            'success': False,
            'message': '运营规划不存在'
        }), 404

    return jsonify({
        'success': True,
        'data': {
            'id': plan.id,
            'account_name': plan.account_name,
            'account_bio': plan.account_bio,
            'status': plan.status
        }
    })


@operation_plan_bp.route('/<int:plan_id>', methods=['PUT'])
@login_required
def update_operation_plan(plan_id):
    """更新运营规划"""
    plan = OperationPlan.query.filter_by(
        id=plan_id,
        user_id=current_user.id
    ).first_or_404()

    data = request.get_json()

    # 更新字段
    if 'account_name' in data:
        plan.account_name = data['account_name']
    if 'account_bio' in data:
        plan.account_bio = data['account_bio']
    if 'avatar_suggestion' in data:
        plan.avatar_suggestion = data['avatar_suggestion']
    if 'content_tags' in data:
        plan.content_tags = data['content_tags']
    if 'content_ratio' in data:
        plan.content_ratio = data['content_ratio']
    if 'plan_content' in data:
        plan.plan_content = data['plan_content']

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '更新成功',
        'data': {'id': plan.id}
    })


@operation_plan_bp.route('/<int:plan_id>', methods=['DELETE'])
@login_required
def delete_operation_plan(plan_id):
    """删除运营规划"""
    plan = OperationPlan.query.filter_by(
        id=plan_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(plan)
    db.session.commit()

    return jsonify({'success': True, 'message': '删除成功'})


@operation_plan_bp.route('/list', methods=['GET'])
@login_required
def list_operation_plans():
    """获取运营规划列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    plans = OperationPlan.query.filter_by(
        user_id=current_user.id
    ).order_by(
        OperationPlan.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'data': {
            'items': [{
                'id': p.id,
                'blue_ocean_id': p.blue_ocean_id,
                'account_name': p.account_name,
                'status': p.status,
                'created_at': p.created_at.isoformat() if p.created_at else None
            } for p in plans.items],
            'total': plans.total,
            'page': plans.page,
            'pages': plans.pages,
            'has_next': plans.has_next,
            'has_prev': plans.has_prev
        }
    })


@operation_plan_bp.route('/<int:plan_id>/export', methods=['GET'])
@login_required
def export_operation_plan(plan_id):
    """导出运营规划方案"""
    plan = OperationPlan.query.filter_by(
        id=plan_id,
        user_id=current_user.id
    ).first_or_404()

    # 生成 Markdown 格式的报告
    report = _generate_markdown_report(plan)

    return jsonify({
        'success': True,
        'data': {
            'report': report,
            'filename': f"运营规划_{plan.account_name}.md"
        }
    })


def _generate_markdown_report(plan: OperationPlan) -> str:
    """生成 Markdown 格式的运营规划"""
    plan_content = plan.plan_content or {}

    # 月度计划
    monthly_plan = plan_content.get('monthly_plan', {})
    monthly_md = []
    for week, content in monthly_plan.items():
        monthly_md.append(f"### {week}")
        monthly_md.append(f"- 主题: {content.get('theme', '')}")
        monthly_md.append(f"- 内容: {', '.join(content.get('content', []))}")
    monthly_md = "\n".join(monthly_md) if monthly_md else "暂无"

    # 变现方案
    monetization = plan_content.get('monetization', {})
    monetization_md = f"""- 主要变现: {monetization.get('primary', '')}
- 次要变现: {', '.join(monetization.get('secondary', []))}
- 转化路径: {monetization.get('conversion_path', '')}"""

    # 内容配比
    content_ratio = plan.content_ratio or {}
    ratio_md = []
    for key, value in content_ratio.items():
        ratio_md.append(f"- {key}: {value}%")
    ratio_md = "\n".join(ratio_md) if ratio_md else "暂无"

    report = f"""# {plan.account_name} - 运营规划方案

生成时间：{plan.created_at.strftime('%Y-%m-%d %H:%M:%S') if plan.created_at else '未知'}

---

## 一、账号设计

### 1.1 账号昵称
{plan.account_name}

### 1.2 账号简介
{plan.account_bio}

### 1.3 头像建议
{plan.avatar_suggestion}

### 1.4 内容标签
{', '.join(plan.content_tags or [])}

---

## 二、内容配比

{ratio_md}

---

## 三、目标人群

### 3.1 主要人群
{_format_persona(plan_content.get('target_audience', {}).get('main_persona', {}))}

### 3.2 其他人群
{_format_persona_list(plan_content.get('target_audience', {}).get('personas', []))}

---

## 四、蓝海机会

{_format_opportunities(plan_content.get('market_opportunity', {}).get('opportunities', []))}

---

## 五、变现方案

{monetization_md}

---

## 六、月度计划

{monthly_md}

---

## 七、时间维度洞察

{_format_time_insights(plan_content.get('time_insights', {}))}
"""
    return report


def _format_persona(persona: dict) -> str:
    """格式化单个画像"""
    if not persona:
        return "暂无数据"
    return f"""- 问题类型: {persona.get('problem_type', '')}
- 目标人群: {persona.get('target_audience', '')}
- 核心场景: {', '.join(persona.get('core_scenarios', []))}
- 具体痛点: {', '.join(persona.get('specific_pain_points', []))}"""


def _format_persona_list(personas: list) -> str:
    """格式化画像列表"""
    if not personas:
        return "暂无数据"
    result = []
    for i, p in enumerate(personas, 1):
        result.append(f"{i}. {p.get('name', '未命名')}: {p.get('target_audience', '')}")
    return "\n".join(result)


def _format_opportunities(opportunities: list) -> str:
    """格式化机会列表"""
    if not opportunities:
        return "暂无数据"
    result = []
    for i, opp in enumerate(opportunities, 1):
        result.append(f"### 机会{i}: {opp.get('name', '')}")
        result.append(f"- 未满足问题: {opp.get('unmet_problem', '')}")
        result.append(f"- 严重程度: {opp.get('severity_level', '')}")
        result.append(f"- 紧急程度: {opp.get('urgency_level', '')}")
        result.append(f"- 切入角度: {opp.get('entry_angle', '')}")
        result.append("")
    return "\n".join(result)


def _format_time_insights(insights: dict) -> str:
    """格式化时间洞察"""
    if not insights:
        return "暂无数据"
    return f"""- 当前时间: {insights.get('current_date', '')}
- 季节: {insights.get('season', '')}
- 内容方向: {insights.get('content_direction', '')}"""
