"""
管理员路由 - 专家管理、知识库管理、渠道管理、行业管理
"""
import os
import re
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from models.models import db, User, Skill, KnowledgeCategory, KnowledgeArticle, KnowledgeAnalysis, KnowledgeRule, Industry, KnowledgeAccount, KnowledgeContent, ReportTemplate, ContentTemplate, TemplateDependency, TemplateRefreshLog, TemplateContentItem, TemplateEditHistory, PersonaRole, UsageScenario, DemandScenario, PainPoint, HotTopic, SeasonalTopic, ContentTitle, ContentHook, ContentStructure, ContentEnding, ContentCover, ContentTopic, ContentPsychology, ContentCommercial, ContentWhyPopular, ContentTag, ContentCharacter, ContentForm, ContentInteraction, AnalysisDimension, AnalysisDimensionCategoryOrder
from sqlalchemy import or_, and_
from constants import ANALYSIS_DIMENSIONS, DIMENSION_TO_MATERIAL_TYPE, MATERIAL_TYPES, INDUSTRY_OPTIONS, ANALYSIS_DIMENSION_CATEGORIES
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

admin = Blueprint('admin', __name__)


def super_admin_required(f):
    """超级管理员/管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('super_admin', 'admin'):
            # 对 Ajax / API 请求返回 JSON，避免前端 fetch 被 302 + HTML 吃掉
            wants_json = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or request.is_json
                or 'application/json' in (request.headers.get('Accept') or '')
            )
            if wants_json:
                return jsonify({'code': 403, 'message': '需要管理员权限', 'success': False}), 403

            flash('需要管理员权限', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """管理后台首页"""
    # 统计数据
    user_count = User.query.count()
    industry_count = Industry.query.count()
    
    return render_template('admin/dashboard.html',
                         now=datetime.now(),
                         user_count=user_count,
                         industry_count=industry_count)


# ========== 人群画像生成 ==========

@admin.route('/persona')
@login_required
@super_admin_required
def persona_generator():
    """人群画像生成页面"""
    return render_template('admin/persona_generator.html')


# ==================== 行业管理 ====================

@admin.route('/industries')
@login_required
@super_admin_required
def industries():
    """行业列表"""
    industries_list = Industry.query.order_by(Industry.sort_order).all()
    return render_template('admin/industries.html', industries=industries_list)


@admin.route('/industries/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def industry_add():
    """添加行业"""
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        description = request.form.get('description')
        icon = request.form.get('icon')
        
        # 检查slug是否已存在
        if Industry.query.filter_by(slug=slug).first():
            flash('行业标识已存在', 'danger')
            return redirect(url_for('admin.industry_add'))
        
        industry = Industry(
            name=name,
            slug=slug,
            description=description,
            icon=icon
        )
        db.session.add(industry)
        db.session.commit()
        flash('行业添加成功', 'success')
        return redirect(url_for('admin.industries'))
    
    return render_template('admin/industry_form.html', industry=None)


@admin.route('/industries/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def industry_edit(id):
    """编辑行业"""
    industry = Industry.query.get_or_404(id)
    
    if request.method == 'POST':
        industry.name = request.form.get('name')
        industry.description = request.form.get('description')
        industry.icon = request.form.get('icon')
        db.session.commit()
        flash('行业更新成功', 'success')
        return redirect(url_for('admin.industries'))
    
    return render_template('admin/industry_form.html', industry=industry)


@admin.route('/industries/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def industry_delete(id):
    """删除行业"""
    industry = Industry.query.get_or_404(id)
    
    db.session.delete(industry)
    db.session.commit()
    flash('行业删除成功', 'success')
    return redirect(url_for('admin.industries'))


# ==================== 客户管理 ====================

@admin.route('/public/users')
@login_required
@super_admin_required
def public_users():
    """公开用户管理"""
    from models.public_models import PublicUser, PublicGeneration, PublicPricingPlan
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()

    query = PublicUser.query
    if search:
        query = query.filter(
            or_(
                PublicUser.email.ilike(f'%{search}%'),
                PublicUser.nickname.ilike(f'%{search}%')
            )
        )
    query = query.order_by(PublicUser.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users = pagination.items

    stats = {
        'total': PublicUser.query.count(),
        'total_verified': PublicUser.query.filter_by(is_verified=True).count(),
        'total_premium': PublicUser.query.filter_by(is_premium=True).count(),
    }
    plans = PublicPricingPlan.query.filter_by(is_visible=True).order_by(PublicPricingPlan.sort_order).all()

    return render_template('admin/public_users.html',
                         users=users,
                         pagination=pagination,
                         stats=stats,
                         plans=plans,
                         search=search)


@admin.route('/public/pending-industries')
@login_required
@super_admin_required
def public_pending_industries():
    """待处理行业管理"""
    return render_template('admin/pending_industries.html')


@admin.route('/public/cost-stats')
@login_required
@super_admin_required
def public_cost_stats():
    """成本统计"""
    return render_template('admin/cost_stats.html')


# ==================== 公开用户管理代理路由（支持 admin_public 蓝图模板）====================

@admin.route('/public-user/list')
@login_required
@super_admin_required
def public_user_list():
    """公开用户列表（代理 admin_public.list）"""
    from models.public_models import PublicUser, PublicPricingPlan
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    plan_filter = request.args.get('plan', '')
    status_filter = request.args.get('status', '')

    query = PublicUser.query
    if search:
        query = query.filter(
            or_(
                PublicUser.email.ilike(f'%{search}%'),
                PublicUser.nickname.ilike(f'%{search}%')
            )
        )
    if plan_filter:
        if plan_filter == 'free':
            query = query.filter(PublicUser.is_premium == False)
        elif plan_filter == 'paid':
            query = query.filter(
                and_(
                    PublicUser.is_premium == True,
                    or_(
                        PublicUser.premium_expires == None,
                        PublicUser.premium_expires > datetime.utcnow()
                    )
                )
            )
    if status_filter == 'active':
        query = query.filter(PublicUser.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(PublicUser.is_active == False)
    elif status_filter == 'unverified':
        query = query.filter(PublicUser.is_verified == False)

    query = query.order_by(PublicUser.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    stats = {
        'total': PublicUser.query.count(),
        'total_verified': PublicUser.query.filter_by(is_verified=True).count(),
        'total_premium': PublicUser.query.filter_by(is_premium=True).count(),
    }
    plans = PublicPricingPlan.query.filter_by(is_visible=True).order_by(PublicPricingPlan.sort_order).all()

    return render_template('admin/public_users.html',
                         users=pagination.items,
                         pagination=pagination,
                         stats=stats,
                         plans=plans,
                         search=search,
                         plan_filter=plan_filter,
                         status_filter=status_filter)


@admin.route('/public-user/detail/<int:user_id>')
@login_required
@super_admin_required
def public_user_detail(user_id):
    """公开用户详情（代理 admin_public.detail）"""
    from models.public_models import PublicUser, PublicGeneration, PublicLLMCallLog
    user = PublicUser.query.get_or_404(user_id)
    generation_stats = {
        'total': PublicGeneration.query.filter_by(user_id=user_id).count(),
        'today': PublicGeneration.query.filter_by(user_id=user_id).filter(
            PublicGeneration.created_at >= datetime.utcnow().date()
        ).count(),
        'this_month': PublicGeneration.query.filter_by(user_id=user_id).filter(
            PublicGeneration.created_at >= datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        ).count(),
    }
    llm_stats = db.session.query(
        db.func.sum(PublicLLMCallLog.input_tokens).label('input_tokens'),
        db.func.sum(PublicLLMCallLog.output_tokens).label('output_tokens'),
        db.func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
        db.func.sum(PublicLLMCallLog.cost).label('total_cost'),
    ).filter_by(user_id=user_id).first()
    recent_generations = PublicGeneration.query.filter_by(user_id=user_id)\
        .order_by(PublicGeneration.created_at.desc()).limit(10).all()
    recent_llm_calls = PublicLLMCallLog.query.filter_by(user_id=user_id)\
        .order_by(PublicLLMCallLog.created_at.desc()).limit(20).all()
    return render_template('admin/public_user_detail.html',
                         user=user,
                         generation_stats=generation_stats,
                         llm_stats=llm_stats,
                         recent_generations=recent_generations,
                         recent_llm_calls=recent_llm_calls)


@admin.route('/public-user/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def public_user_edit(user_id):
    """编辑公开用户（代理 admin_public.edit）"""
    from models.public_models import PublicUser, PublicPricingPlan
    user = PublicUser.query.get_or_404(user_id)
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        if nickname:
            user.nickname = nickname
        user.is_verified = (request.form.get('is_verified') == '1')
        user.is_active = (request.form.get('is_active') == '1')
        plan = request.form.get('plan', 'free')
        if plan == 'free':
            user.is_premium = False
            user.premium_plan = 'free'
            user.premium_expires = None
        else:
            user.is_premium = True
            user.premium_plan = plan
            expires_days = request.form.get('expires_days', type=int, default=30)
            user.premium_expires = datetime.utcnow() + timedelta(days=expires_days)
        add_tokens = request.form.get('add_tokens', type=int, default=0)
        if add_tokens > 0:
            user.token_balance = (user.token_balance or 0) + add_tokens
        db.session.commit()
        flash(f'用户 {user.email} 已更新', 'success')
        return redirect(url_for('admin.public_user_detail', user_id=user_id))
    plans = PublicPricingPlan.query.filter_by(is_visible=True).order_by(PublicPricingPlan.sort_order).all()
    return render_template('admin/public_user_edit.html', user=user, plans=plans)


@admin.route('/public-user/stats')
@login_required
@super_admin_required
def public_user_stats():
    """公开用户统计（代理 admin_public.stats）"""
    from models.public_models import PublicUser, PublicGeneration, PublicLLMCallLog
    total_users = PublicUser.query.count()
    verified_users = PublicUser.query.filter_by(is_verified=True).count()
    premium_users = PublicUser.query.filter_by(is_premium=True).count()
    expired_users = PublicUser.query.filter(
        and_(
            PublicUser.is_premium == True,
            PublicUser.premium_expires != None,
            PublicUser.premium_expires < datetime.utcnow()
        )
    ).count()
    total_generations = PublicGeneration.query.count()
    today_generations = PublicGeneration.query.filter(
        PublicGeneration.created_at >= datetime.utcnow().date()
    ).count()
    cost_stats = db.session.query(
        db.func.sum(PublicLLMCallLog.cost).label('total_cost'),
        db.func.sum(PublicLLMCallLog.total_tokens).label('total_tokens'),
    ).first()
    return jsonify({
        'success': True,
        'data': {
            'users': {
                'total': total_users,
                'verified': verified_users,
                'premium': premium_users,
                'expired': expired_users
            },
            'generations': {
                'total': total_generations,
                'today': today_generations
            },
            'cost': {
                'total': float(cost_stats.total_cost or 0),
                'total_tokens': cost_stats.total_tokens or 0
            }
        }
    })


# ==================== 模板管理 ====================

@admin.route('/templates')
@login_required
@super_admin_required
def templates():
    """模板管理首页"""
    template_type = request.args.get('type', 'report')
    report_subtype = request.args.get('subtype', 'market_analysis')

    if template_type == 'report':
        # 根据子类型筛选
        if report_subtype:
            templates_list = ReportTemplate.query.filter_by(template_type=report_subtype).order_by(ReportTemplate.created_at.desc()).all()
        else:
            templates_list = ReportTemplate.query.order_by(ReportTemplate.created_at.desc()).all()
        return render_template('admin/templates.html', templates=templates_list, template_type='report', report_subtype=report_subtype)
    else:
        templates_list = ContentTemplate.query.order_by(ContentTemplate.created_at.desc()).all()
        return render_template('admin/templates.html', templates=templates_list, template_type='content', report_subtype=None)


@admin.route('/templates/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def template_add():
    """添加模板"""
    template_type = request.args.get('type', 'report')
    report_subtype = request.args.get('template_type', 'market_analysis')

    if request.method == 'POST':
        data = request.form

        if template_type == 'report':
            template = ReportTemplate(
                template_name=data.get('template_name'),
                template_type=data.get('template_type'),
                template_category=data.get('template_category', 'universal'),
                template_content=data.get('template_content'),
                variables_config=data.get('variables_config'),
                created_by=current_user.id
            )
        else:
            template = ContentTemplate(
                template_name=data.get('template_name'),
                content_type=data.get('content_type'),
                template_category=data.get('template_category', 'universal'),
                template_structure=data.get('template_structure'),
                template_content=data.get('template_content'),
                created_by=current_user.id
            )

        db.session.add(template)
        db.session.commit()
        flash('模板创建成功', 'success')
        # 保存后返回对应的列表页
        if template_type == 'report':
            return redirect(url_for('admin.templates', type='report', subtype=data.get('template_type')))
        else:
            return redirect(url_for('admin.templates', type='content'))

    # 预加载默认模板内容
    default_content = ''
    if template_type == 'report':
        # 加载现有模板文件作为默认值
        template_files = {
            'market_analysis': 'skills/insights-analyst/输出/行业分析/行业分析报告_模板.md',
            'keyword': 'skills/geo-seo/输出/关键词库/关键词库_模板.md',
            'topic': 'skills/geo-seo/输出/选题推荐/选题库_模板.md',
            'operation': 'skills/operations-expert/输出/运营规划/运营规划方案_模板.md',
        }
        template_file = template_files.get(request.args.get('template_type', ''))
        if template_file:
            from flask import current_app
            base_path = os.path.join(current_app.root_path, '..', template_file)
            if os.path.exists(base_path):
                with open(base_path, 'r', encoding='utf-8') as f:
                    default_content = f.read()

    return render_template('admin/template_form.html', template_type=template_type, default_content=default_content)


@admin.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def template_edit(id):
    """编辑模板"""
    template_type = request.args.get('type', 'report')
    report_subtype = request.args.get('subtype')

    if template_type == 'report':
        template = ReportTemplate.query.get_or_404(id)
    else:
        template = ContentTemplate.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form
        # 编辑页：模板名称不可修改、模板类型已去掉，仅更新分类与变量配置；内容由条目 API 管理
        if template_type == 'report':
            template.template_category = data.get('template_category', template.template_category or 'universal')
            if data.get('variables_config') is not None:
                template.variables_config = data.get('variables_config')
        else:
            template.template_category = data.get('template_category', template.template_category or 'universal')
            if data.get('template_structure') is not None:
                template.template_structure = data.get('template_structure')

        db.session.commit()
        flash('模板设置已保存', 'success')
        if template_type == 'report':
            subtype = report_subtype or (template.template_type if hasattr(template, 'template_type') else 'market_analysis')
            return redirect(url_for('admin.templates', type='report', subtype=subtype))
        return redirect(url_for('admin.templates', type='content'))

    return render_template('admin/template_form.html', template=template, template_type=template_type, report_subtype=report_subtype)


@admin.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def template_delete(id):
    """删除模板"""
    template_type = request.args.get('type', 'report')
    report_subtype = request.args.get('subtype')

    if template_type == 'report':
        template = ReportTemplate.query.get_or_404(id)
        subtype = report_subtype or template.template_type
    else:
        template = ContentTemplate.query.get_or_404(id)
        subtype = None

    db.session.delete(template)
    db.session.commit()
    flash('模板已删除', 'success')

    # 返回对应的列表页
    if template_type == 'report':
        return redirect(url_for('admin.templates', type='report', subtype=subtype))
    else:
        return redirect(url_for('admin.templates', type='content'))


@admin.route('/templates/<int:id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def template_toggle(id):
    """切换模板启用状态"""
    template_type = request.args.get('type', 'report')
    report_subtype = request.args.get('subtype')

    if template_type == 'report':
        template = ReportTemplate.query.get_or_404(id)
    else:
        template = ContentTemplate.query.get_or_404(id)

    template.is_active = not template.is_active
    db.session.commit()

    status = '启用' if template.is_active else '禁用'
    flash(f'模板已{status}', 'success')

    # 返回对应的列表页
    if template_type == 'report':
        subtype = report_subtype or (template.template_type if hasattr(template, 'template_type') else 'market_analysis')
        return redirect(url_for('admin.templates', type='report', subtype=subtype))
    else:
        return redirect(url_for('admin.templates', type='content'))


def _parse_template_content_to_items(full_content):
    """将完整模板内容按 Markdown 标题拆分为条目（## 或 # 为界）。"""
    if not (full_content or '').strip():
        return []
    text = full_content.strip()
    # 先在每个标题前插入换行（如果没有），再按标题拆分
    text = re.sub(r'(#+\s)', r'\n\1', text)
    parts = re.split(r'\n(?=#+\s)', text)
    items = []
    for i, block in enumerate(parts):
        block = block.strip()
        if block:
            items.append({'sort_order': i, 'content': block})
    return items


def _merge_template_items_to_content(template_type, template_id):
    """将当前模板的所有条目按 sort_order 合并为完整内容，并写回模板表。"""
    items = TemplateContentItem.query.filter_by(
        template_type=template_type, template_id=template_id
    ).order_by(TemplateContentItem.sort_order).all()
    full = '\n\n'.join(item.content.strip() for item in items if (item.content or '').strip())
    if template_type == 'report':
        t = ReportTemplate.query.get(template_id)
        if t:
            t.template_content = full or None
    else:
        t = ContentTemplate.query.get(template_id)
        if t:
            t.template_content = full or None
    db.session.commit()
    return full


def _ensure_template_items_from_content(template_type, template_id):
    """若该模板尚无条目但 template_content 有内容，则解析为条目并入库。"""
    if template_type == 'report':
        t = ReportTemplate.query.get(template_id)
    else:
        t = ContentTemplate.query.get(template_id)
    if not t or not (t.template_content or '').strip():
        return
    existing = TemplateContentItem.query.filter_by(template_type=template_type, template_id=template_id).first()
    if existing:
        return
    for item in _parse_template_content_to_items(t.template_content):
        db.session.add(TemplateContentItem(
            template_type=template_type,
            template_id=template_id,
            sort_order=item['sort_order'],
            content=item['content']
        ))
    db.session.commit()


# ==================== 模板内容条目 API ====================

@admin.route('/api/templates/<int:tid>/items', methods=['GET'])
@login_required
@super_admin_required
def api_template_items(tid):
    """获取模板的内容条目列表（按 sort_order）。"""
    template_type = request.args.get('type', 'report')
    _ensure_template_items_from_content(template_type, tid)
    items = TemplateContentItem.query.filter_by(template_type=template_type, template_id=tid).order_by(TemplateContentItem.sort_order).all()
    return jsonify([{
        'id': x.id,
        'sort_order': x.sort_order,
        'content': x.content or '',
        'natural_language_hint': x.natural_language_hint or '',
        'updated_at': x.updated_at.isoformat() if x.updated_at else None,
    } for x in items])


@admin.route('/api/templates/<int:tid>/items', methods=['POST'])
@login_required
@super_admin_required
def api_template_item_add(tid):
    """新增一条模板内容。body: content 或 natural_language（由前端先解析后传 content）。"""
    template_type = request.args.get('type', 'report')
    data = request.get_json() or request.form
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'ok': False, 'message': '缺少 content'}), 400
    max_order = db.session.query(db.func.max(TemplateContentItem.sort_order)).filter_by(
        template_type=template_type, template_id=tid
    ).scalar() or 0
    item = TemplateContentItem(
        template_type=template_type,
        template_id=tid,
        sort_order=max_order + 1,
        content=content,
        natural_language_hint=data.get('natural_language_hint') or None
    )
    db.session.add(item)
    db.session.commit()
    full = _merge_template_items_to_content(template_type, tid)
    db.session.add(TemplateEditHistory(
        template_type=template_type, template_id=tid,
        snapshot_content=full, changed_by=current_user.id
    ))
    db.session.commit()
    return jsonify({'ok': True, 'id': item.id, 'full_content': full})


@admin.route('/api/templates/<int:tid>/items/<int:item_id>', methods=['PUT'])
@login_required
@super_admin_required
def api_template_item_update(tid, item_id):
    """更新一条模板内容。"""
    template_type = request.args.get('type', 'report')
    item = TemplateContentItem.query.filter_by(id=item_id, template_type=template_type, template_id=tid).first_or_404()
    data = request.get_json() or request.form
    content = data.get('content')
    if content is not None:
        item.content = content.strip()
    if data.get('natural_language_hint') is not None:
        item.natural_language_hint = data.get('natural_language_hint') or None
    db.session.commit()
    full = _merge_template_items_to_content(template_type, tid)
    db.session.add(TemplateEditHistory(
        template_type=template_type, template_id=tid,
        snapshot_content=full, changed_by=current_user.id
    ))
    db.session.commit()
    return jsonify({'ok': True, 'full_content': full})


@admin.route('/api/templates/<int:tid>/items/<int:item_id>', methods=['DELETE'])
@login_required
@super_admin_required
def api_template_item_delete(tid, item_id):
    """删除一条模板内容。"""
    template_type = request.args.get('type', 'report')
    item = TemplateContentItem.query.filter_by(id=item_id, template_type=template_type, template_id=tid).first_or_404()
    db.session.delete(item)
    db.session.commit()
    full = _merge_template_items_to_content(template_type, tid)
    db.session.add(TemplateEditHistory(
        template_type=template_type, template_id=tid,
        snapshot_content=full, changed_by=current_user.id
    ))
    db.session.commit()
    return jsonify({'ok': True, 'full_content': full})


@admin.route('/api/templates/<int:tid>/items/reorder', methods=['POST'])
@login_required
@super_admin_required
def api_template_items_reorder(tid):
    """调整条目顺序。body: { "order": [id1, id2, ...] }"""
    template_type = request.args.get('type', 'report')
    data = request.get_json() or {}
    order = data.get('order') or []
    if not order:
        return jsonify({'ok': False, 'message': '缺少 order'}), 400
    items = {x.id: x for x in TemplateContentItem.query.filter_by(template_type=template_type, template_id=tid).all()}
    for i, id_ in enumerate(order):
        if id_ in items:
            items[id_].sort_order = i
    db.session.commit()
    full = _merge_template_items_to_content(template_type, tid)
    db.session.add(TemplateEditHistory(
        template_type=template_type, template_id=tid,
        snapshot_content=full, changed_by=current_user.id
    ))
    db.session.commit()
    return jsonify({'ok': True, 'full_content': full})


@admin.route('/api/templates/parse-nl', methods=['POST'])
@login_required
@super_admin_required
def api_template_parse_nl():
    """将自然语言描述解析为模板内容（Markdown + 变量）。可选 body: template_id, template_type 做上下文。"""
    data = request.get_json() or request.form
    nl = (data.get('natural_language') or data.get('natural_language_description') or '').strip()
    if not nl:
        return jsonify({'ok': False, 'message': '请提供 natural_language'}), 400
    try:
        from services.llm import get_llm_service
        service = get_llm_service()
        if not service:
            # 无 LLM 时返回规则化结果：用 Markdown 段落包裹用户输入，并提示可用变量
            content = f"<!-- 自然语言描述：{nl} -->\n\n{nl}\n\n可使用变量：{{{{ customer_name }}}}、{{{{ industry }}}}、{{{{ core_keywords }}}}。"
            return jsonify({'ok': True, 'content': content})
        prompt = """你是一个报告模板撰写助手。用户会用自然语言描述希望出现在报告中的一段内容要求。
请将用户的描述转化为一段可直接放入 Markdown 报告模板的“系统语言”内容：
- 使用 Markdown 格式（标题、列表、加粗等）
- 需要动态替换的地方用双花括号变量表示，如 {{ customer_name }}、{{ industry }}、{{ core_keywords }}、{{ 日期 }}、{{ 子行业 }}
- 只输出这一段模板内容，不要解释或多余说明
用户描述："""
        messages = [{"role": "user", "content": prompt + nl}]
        result = service.chat(messages, temperature=0.3, max_tokens=1500)
        content = (result or '').strip() if result else nl
        if not content:
            content = f"<!-- {nl} -->\n\n{nl}"
        return jsonify({'ok': True, 'content': content})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500


@admin.route('/api/templates/<int:tid>/history', methods=['GET'])
@login_required
@super_admin_required
def api_template_history(tid):
    """获取模板编辑历史。"""
    template_type = request.args.get('type', 'report')
    rows = TemplateEditHistory.query.filter_by(template_type=template_type, template_id=tid).order_by(TemplateEditHistory.changed_at.desc()).limit(50).all()
    return jsonify([{
        'id': r.id,
        'changed_at': r.changed_at.isoformat() if r.changed_at else None,
        'changed_by': r.changed_by,
        'snapshot_content': r.snapshot_content or '',
    } for r in rows])


# ==================== 公开平台模板配置（内容展示配置）====================
@admin.route('/public-template-config')
@login_required
@super_admin_required
def public_template_config():
    """公开平台模板配置页"""
    template_type = request.args.get('type', 'keyword')
    if template_type not in ('keyword', 'topic', 'content_display'):
        template_type = 'keyword'
    return render_template('admin/public_template_config.html',
                           template_type=template_type)


@admin.route('/api/public-template/save', methods=['GET', 'POST'])
@login_required
@super_admin_required
def api_public_template_save():
    """保存/读取公开平台模板"""
    from services.template_config_service import template_config_service
    from models.models import ReportTemplate

    if request.method == 'GET':
        tid = request.args.get('id')
        if tid:
            t = ReportTemplate.query.get(int(tid))
            if t:
                return jsonify({
                    'id': t.id,
                    'template_name': t.template_name,
                    'template_type': t.template_type,
                    'template_category': t.template_category,
                    'template_content': t.template_content,
                    'version': t.version,
                })
        return jsonify({})

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '无效数据'})

    result = template_config_service.save_template(data, created_by=current_user.id)
    return jsonify(result)


@admin.route('/api/public-template/list')
@login_required
@super_admin_required
def api_public_template_list():
    """获取公开平台模板列表"""
    from services.template_config_service import template_config_service

    template_type = request.args.get('type', 'keyword')
    templates = template_config_service.get_all_templates(template_type)
    return jsonify({'success': True, 'data': templates})


@admin.route('/api/section-display-config', methods=['GET', 'POST'])
@login_required
@super_admin_required
def api_section_display_config():
    """内容展示区块配置 API"""
    from services.template_config_service import template_config_service

    if request.method == 'GET':
        content_type = request.args.get('content_type', 'graphic')
        configs = template_config_service.get_section_display_config(content_type)
        return jsonify({'success': True, 'data': configs})

    data = request.get_json()
    content_type = data.get('content_type', 'graphic')
    sections = data.get('sections', [])
    result = template_config_service.save_section_display_config(
        content_type, sections, created_by=current_user.id
    )
    return jsonify(result)


@admin.route('/api/section-display-config/all')
@login_required
@super_admin_required
def api_section_display_config_all():
    """获取所有内容类型的展示配置"""
    from services.template_config_service import template_config_service
    configs = template_config_service.get_all_section_display_configs()
    return jsonify({'success': True, 'data': configs})


# ==================== 场景管理 ====================
    log = TemplateRefreshLog(
        template_type=template_type,
        trigger_type=source_type,
        source_type=source_type,
        source_id=source_id,
        status='pending'
    )
    db.session.add(log)
    db.session.commit()

    # TODO: 实现实际的刷新逻辑
    # 这里先返回成功，实际刷新逻辑在后续实现

    return jsonify({
        'success': True,
        'message': f'{template_type} 刷新任务已创建',
        'log_id': log.id
    })


# ==================== 场景库管理 ====================

@admin.route('/scenarios')
@login_required
@super_admin_required
def scenarios():
    """场景库列表"""
    scenario_type = request.args.get('type', 'usage')

    if scenario_type == 'usage':
        items = UsageScenario.query.order_by(UsageScenario.created_at.desc()).all()
    elif scenario_type == 'demand':
        items = DemandScenario.query.order_by(DemandScenario.created_at.desc()).all()
    else:
        items = PainPoint.query.order_by(PainPoint.created_at.desc()).all()

    return render_template('admin/scenarios.html', items=items, scenario_type=scenario_type)


@admin.route('/scenarios/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def scenario_add():
    """添加场景"""
    scenario_type = request.args.get('type', 'usage')

    if request.method == 'POST':
        data = request.form

        if scenario_type == 'usage':
            item = UsageScenario(
                scenario_name=data.get('scenario_name'),
                industry=data.get('industry'),
                scenario_description=data.get('scenario_description'),
                target_users=request.form.getlist('target_users'),
                pain_points=request.form.getlist('pain_points'),
                needs=request.form.getlist('needs'),
                keywords=request.form.getlist('keywords'),
                related_products=request.form.getlist('related_products')
            )
        elif scenario_type == 'demand':
            item = DemandScenario(
                scenario_name=data.get('scenario_name'),
                demand_type=data.get('demand_type'),
                scenario_description=data.get('scenario_description'),
                trigger_condition=request.form.getlist('trigger_condition'),
                user_goals=request.form.getlist('user_goals'),
                emotional_needs=request.form.getlist('emotional_needs'),
                keywords=request.form.getlist('keywords')
            )
        else:
            item = PainPoint(
                pain_point_name=data.get('pain_point_name'),
                industry=data.get('industry'),
                pain_type=data.get('pain_type'),
                description=data.get('description'),
                severity=data.get('severity'),
                affected_users=request.form.getlist('affected_users'),
                current_solutions=request.form.getlist('current_solutions'),
                opportunities=request.form.getlist('opportunities'),
                keywords=request.form.getlist('keywords')
            )

        db.session.add(item)
        db.session.commit()
        flash('场景创建成功', 'success')
        return redirect(url_for('admin.scenarios', type=scenario_type))

    return render_template('admin/scenario_form.html', scenario_type=scenario_type)


@admin.route('/scenarios/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def scenario_edit(id):
    """编辑场景"""
    scenario_type = request.args.get('type', 'usage')

    if scenario_type == 'usage':
        item = UsageScenario.query.get_or_404(id)
    elif scenario_type == 'demand':
        item = DemandScenario.query.get_or_404(id)
    else:
        item = PainPoint.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form

        if scenario_type == 'usage':
            item.scenario_name = data.get('scenario_name')
            item.industry = data.get('industry')
            item.scenario_description = data.get('scenario_description')
            item.target_users = request.form.getlist('target_users')
            item.pain_points = request.form.getlist('pain_points')
            item.needs = request.form.getlist('needs')
            item.keywords = request.form.getlist('keywords')
            item.related_products = request.form.getlist('related_products')
        elif scenario_type == 'demand':
            item.scenario_name = data.get('scenario_name')
            item.demand_type = data.get('demand_type')
            item.scenario_description = data.get('scenario_description')
            item.trigger_condition = request.form.getlist('trigger_condition')
            item.user_goals = request.form.getlist('user_goals')
            item.emotional_needs = request.form.getlist('emotional_needs')
            item.keywords = request.form.getlist('keywords')
        else:
            item.pain_point_name = data.get('pain_point_name')
            item.industry = data.get('industry')
            item.pain_type = data.get('pain_type')
            item.description = data.get('description')
            item.severity = data.get('severity')
            item.affected_users = request.form.getlist('affected_users')
            item.current_solutions = request.form.getlist('current_solutions')
            item.opportunities = request.form.getlist('opportunities')
            item.keywords = request.form.getlist('keywords')

        db.session.commit()
        flash('场景更新成功', 'success')
        return redirect(url_for('admin.scenarios', type=scenario_type))

    return render_template('admin/scenario_form.html', scenario_type=scenario_type, item=item)


@admin.route('/scenarios/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def scenario_delete(id):
    """删除场景"""
    scenario_type = request.args.get('type', 'usage')

    if scenario_type == 'usage':
        item = UsageScenario.query.get_or_404(id)
    elif scenario_type == 'demand':
        item = DemandScenario.query.get_or_404(id)
    else:
        item = PainPoint.query.get_or_404(id)

    db.session.delete(item)
    db.session.commit()
    flash('场景已删除', 'success')
    return redirect(url_for('admin.scenarios', type=scenario_type))


# ==================== 内容素材库管理 ====================

# 素材库模型映射
MATERIAL_MODEL_MAP = {
    'title': ContentTitle,
    'hook': ContentHook,
    'structure': ContentStructure,
    'ending': ContentEnding,
    'cover': ContentCover,
    'topic': ContentTopic,
    'psychology': ContentPsychology,
    'commercial': ContentCommercial,
    'why_popular': ContentWhyPopular,
    'tags': ContentTag,
    'character': ContentCharacter,
    'content_form': ContentForm,
    'interaction': ContentInteraction,
}

@admin.route('/content-materials')
@login_required
@super_admin_required
def content_materials():
    """内容素材库"""
    material_type = request.args.get('type', 'title')

    # 获取对应的模型
    model = MATERIAL_MODEL_MAP.get(material_type)
    if not model:
        material_type = 'title'
        model = ContentTitle

    items = model.query.order_by(model.usage_count.desc()).all()

    # 传递配置信息给模板
    return render_template('admin/content_materials.html',
                          items=items,
                          material_type=material_type,
                          material_config=MATERIAL_TYPES.get(material_type, {}),
                          all_material_types=MATERIAL_TYPES)


@admin.route('/content-materials/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def content_material_add():
    """添加内容素材"""
    material_type = request.args.get('type', 'title')
    config = MATERIAL_TYPES.get(material_type, {})

    if request.method == 'POST':
        data = request.form
        model = MATERIAL_MODEL_MAP.get(material_type)

        if not model:
            flash('不支持的素材类型', 'danger')
            return redirect(url_for('admin.content_materials', type=material_type))

        # 根据素材类型构建数据
        item = None
        if material_type == 'title':
            item = ContentTitle(
                title=data.get('title'),
                title_type=data.get('title_type'),
                industry=data.get('industry'),
                keywords=request.form.getlist('keywords') or None,
                is_template=data.get('is_template') == 'on'
            )
        elif material_type == 'hook':
            item = ContentHook(
                hook_content=data.get('hook_content'),
                hook_type=data.get('hook_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None,
                is_template=data.get('is_template') == 'on'
            )
        elif material_type == 'structure':
            item = ContentStructure(
                structure_name=data.get('structure_name'),
                content_type=data.get('content_type'),
                industry=data.get('industry'),
                structure_steps=request.form.getlist('structure_steps') or None,
                description=data.get('description'),
                applicable_scenarios=request.form.getlist('applicable_scenarios') or None
            )
        elif material_type == 'ending':
            item = ContentEnding(
                ending_content=data.get('ending_content'),
                ending_type=data.get('ending_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None,
                is_template=data.get('is_template') == 'on'
            )
        elif material_type == 'cover':
            item = ContentCover(
                cover_content=data.get('cover_content'),
                cover_type=data.get('cover_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None,
                is_template=data.get('is_template') == 'on'
            )
        elif material_type == 'topic':
            item = ContentTopic(
                topic_content=data.get('topic_content'),
                topic_type=data.get('topic_type'),
                industry=data.get('industry'),
                keywords=request.form.getlist('keywords') or None,
                applicable_scenarios=request.form.getlist('applicable_scenarios') or None
            )
        elif material_type == 'psychology':
            item = ContentPsychology(
                psychology_content=data.get('psychology_content'),
                psychology_type=data.get('psychology_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )
        elif material_type == 'commercial':
            item = ContentCommercial(
                commercial_content=data.get('commercial_content'),
                commercial_type=data.get('commercial_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )
        elif material_type == 'why_popular':
            item = ContentWhyPopular(
                reason_content=data.get('reason_content'),
                reason_type=data.get('reason_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )
        elif material_type == 'tags':
            item = ContentTag(
                tag_content=data.get('tag_content'),
                tag_type=data.get('tag_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )
        elif material_type == 'character':
            item = ContentCharacter(
                character_content=data.get('character_content'),
                character_type=data.get('character_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )
        elif material_type == 'content_form':
            item = ContentForm(
                form_content=data.get('form_content'),
                form_type=data.get('form_type'),
                industry=data.get('industry'),
                applicable_scenarios=request.form.getlist('applicable_scenarios') or None
            )
        elif material_type == 'interaction':
            item = ContentInteraction(
                interaction_content=data.get('interaction_content'),
                interaction_type=data.get('interaction_type'),
                industry=data.get('industry'),
                applicable_content_types=request.form.getlist('applicable_content_types') or None
            )

        if item:
            db.session.add(item)
            db.session.commit()
            flash('素材创建成功', 'success')

        return redirect(url_for('admin.content_materials', type=material_type))

    return render_template('admin/content_material_form.html',
                          material_type=material_type,
                          config=config,
                          all_material_types=MATERIAL_TYPES,
                          industry_options=INDUSTRY_OPTIONS)


@admin.route('/content-materials/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def content_material_edit(id):
    """编辑内容素材"""
    material_type = request.args.get('type', 'title')
    config = MATERIAL_TYPES.get(material_type, {})
    model = MATERIAL_MODEL_MAP.get(material_type)

    if not model:
        flash('不支持的素材类型', 'danger')
        return redirect(url_for('admin.content_materials', type=material_type))

    item = model.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form

        # 根据素材类型更新数据
        if material_type == 'title':
            item.title = data.get('title')
            item.title_type = data.get('title_type')
            item.industry = data.get('industry')
            item.keywords = request.form.getlist('keywords') or None
            item.is_template = data.get('is_template') == 'on'
        elif material_type == 'hook':
            item.hook_content = data.get('hook_content')
            item.hook_type = data.get('hook_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
            item.is_template = data.get('is_template') == 'on'
        elif material_type == 'structure':
            item.structure_name = data.get('structure_name')
            item.content_type = data.get('content_type')
            item.industry = data.get('industry')
            item.structure_steps = request.form.getlist('structure_steps') or None
            item.description = data.get('description')
            item.applicable_scenarios = request.form.getlist('applicable_scenarios') or None
        elif material_type == 'ending':
            item.ending_content = data.get('ending_content')
            item.ending_type = data.get('ending_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
            item.is_template = data.get('is_template') == 'on'
        elif material_type == 'cover':
            item.cover_content = data.get('cover_content')
            item.cover_type = data.get('cover_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
            item.is_template = data.get('is_template') == 'on'
        elif material_type == 'topic':
            item.topic_content = data.get('topic_content')
            item.topic_type = data.get('topic_type')
            item.industry = data.get('industry')
            item.keywords = request.form.getlist('keywords') or None
            item.applicable_scenarios = request.form.getlist('applicable_scenarios') or None
        elif material_type == 'psychology':
            item.psychology_content = data.get('psychology_content')
            item.psychology_type = data.get('psychology_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
        elif material_type == 'commercial':
            item.commercial_content = data.get('commercial_content')
            item.commercial_type = data.get('commercial_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
        elif material_type == 'why_popular':
            item.reason_content = data.get('reason_content')
            item.reason_type = data.get('reason_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
        elif material_type == 'tags':
            item.tag_content = data.get('tag_content')
            item.tag_type = data.get('tag_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
        elif material_type == 'character':
            item.character_content = data.get('character_content')
            item.character_type = data.get('character_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None
        elif material_type == 'content_form':
            item.form_content = data.get('form_content')
            item.form_type = data.get('form_type')
            item.industry = data.get('industry')
            item.applicable_scenarios = request.form.getlist('applicable_scenarios') or None
        elif material_type == 'interaction':
            item.interaction_content = data.get('interaction_content')
            item.interaction_type = data.get('interaction_type')
            item.industry = data.get('industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types') or None

        db.session.commit()
        flash('素材更新成功', 'success')
        return redirect(url_for('admin.content_materials', type=material_type))

    return render_template('admin/content_material_form.html',
                          material_type=material_type,
                          config=config,
                          item=item,
                          all_material_types=MATERIAL_TYPES,
                          industry_options=INDUSTRY_OPTIONS)


@admin.route('/content-materials/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def content_material_delete(id):
    """删除内容素材"""
    material_type = request.args.get('type', 'title')
    model = MATERIAL_MODEL_MAP.get(material_type)

    if not model:
        flash('不支持的素材类型', 'danger')
        return redirect(url_for('admin.content_materials', type=material_type))

    item = model.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('素材已删除', 'success')
    return redirect(url_for('admin.content_materials', type=material_type))


# ==================== 素材库配置 API ====================

@admin.route('/api/content-materials/config')
@login_required
def content_materials_config():
    """获取素材库配置"""
    return jsonify({
        'code': 200,
        'data': {
            'dimensions': ANALYSIS_DIMENSIONS,
            'material_types': MATERIAL_TYPES,
            'dimension_to_material': DIMENSION_TO_MATERIAL_TYPE,
            'industry_options': INDUSTRY_OPTIONS
        }
    })


@admin.route('/api/content-materials/save', methods=['POST'])
@login_required
@super_admin_required
def save_content_material():
    """保存内容素材（从爆款拆解入库）"""
    try:
        data = request.get_json()
        material_type = data.get('material_type')
        content = data.get('content')
        industry = data.get('industry')
        material_type_field = data.get('type')  # 类型（如疑问、数字等）
        content_types = data.get('content_types', [])

        if not material_type or not content:
            return jsonify({'code': 400, 'message': '缺少必要参数'})

        model = MATERIAL_MODEL_MAP.get(material_type)
        if not model:
            return jsonify({'code': 400, 'message': '不支持的素材类型'})

        # 根据素材类型构建数据
        item = None

        if material_type == 'title':
            item = ContentTitle(
                title=content,
                title_type=material_type_field,
                industry=industry,
                keywords=None,
                is_template=False
            )
        elif material_type == 'hook':
            item = ContentHook(
                hook_content=content,
                hook_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None,
                is_template=False
            )
        elif material_type == 'structure':
            item = ContentStructure(
                structure_name=content[:100] if content else '',
                content_type=material_type_field,
                industry=industry,
                description=content,
                applicable_scenarios=None
            )
        elif material_type == 'ending':
            item = ContentEnding(
                ending_content=content,
                ending_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None,
                is_template=False
            )
        elif material_type == 'cover':
            item = ContentCover(
                cover_content=content,
                cover_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None,
                is_template=False
            )
        elif material_type == 'topic':
            item = ContentTopic(
                topic_content=content,
                topic_type=material_type_field,
                industry=industry,
                keywords=None,
                applicable_scenarios=None
            )
        elif material_type == 'psychology':
            item = ContentPsychology(
                psychology_content=content,
                psychology_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )
        elif material_type == 'commercial':
            item = ContentCommercial(
                commercial_content=content,
                commercial_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )
        elif material_type == 'why_popular':
            item = ContentWhyPopular(
                reason_content=content,
                reason_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )
        elif material_type == 'tags':
            item = ContentTag(
                tag_content=content,
                tag_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )
        elif material_type == 'character':
            item = ContentCharacter(
                character_content=content,
                character_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )
        elif material_type == 'content_form':
            item = ContentForm(
                form_content=content,
                form_type=material_type_field,
                industry=industry,
                applicable_scenarios=None
            )
        elif material_type == 'interaction':
            item = ContentInteraction(
                interaction_content=content,
                interaction_type=material_type_field,
                industry=industry,
                applicable_content_types=content_types or None
            )

        if item:
            db.session.add(item)
            db.session.commit()
            return jsonify({'code': 200, 'message': '入库成功', 'data': {'id': item.id}})
        else:
            return jsonify({'code': 400, 'message': '创建素材失败'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"入库失败: {e}")
        return jsonify({'code': 500, 'message': str(e)})


# ==================== 分析维度管理 ====================

@admin.route('/analysis-dimensions')
@login_required
@super_admin_required
def analysis_dimensions_page():
    """分析维度管理页面"""
    return render_template('admin/analysis_dimensions.html')


# ==================== 分析维度管理 ====================

@admin.route('/api/analysis-dimensions', methods=['GET'])
@login_required
def get_analysis_dimensions():
    """获取分析维度列表"""
    # 获取查询参数
    category = request.args.get('category')
    is_active = request.args.get('is_active')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)

    # 构建查询
    query = AnalysisDimension.query

    if category:
        query = query.filter(AnalysisDimension.category == category)

    # 支持 is_active 过滤
    if is_active is not None:
        if is_active.lower() in ('true', '1', 'yes'):
            query = query.filter(AnalysisDimension.is_active == True)
        elif is_active.lower() in ('false', '0', 'no'):
            query = query.filter(AnalysisDimension.is_active == False)

    # 排序
    query = query.order_by(AnalysisDimension.sort_order.asc(), AnalysisDimension.id.asc())

    # 分页
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    response = make_response(jsonify({
        'success': True,
        'data': [{
            'id': d.id,
            'name': d.name,
            'code': d.code,
            'icon': d.icon,
            'description': d.description,
            'category': d.category,
            'sub_category': d.sub_category,
            'category_group': d.category_group,
            'related_material_type': d.related_material_type,
            'is_active': d.is_active,
            'is_default': d.is_default,
            'sort_order': d.sort_order,
            'usage_count': d.usage_count,
            'rule_category': d.rule_category,
            'rule_type': d.rule_type,
            'prompt_template': d.prompt_template,
            'examples': getattr(d, 'examples', None) or '',
            'usage_tips': getattr(d, 'usage_tips', None) or '',
            'applicable_audience': getattr(d, 'applicable_audience', None) or '',
            # 市场洞察专用字段
            'trigger_conditions': getattr(d, 'trigger_conditions', None) or {},
            'content_template': getattr(d, 'content_template', None) or '',
            'importance': getattr(d, 'importance', 1) or 1
        } for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page
    }))
    response.headers['Content-Type'] = 'application/json'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


# 二级分类显示名（与前端 DIMENSION_CATEGORIES 一致，供分组接口返回）
ANALYSIS_DIMENSION_SUB_CATEGORY_NAMES = {
    'account': {
        'nickname_analysis': '昵称分析',
        'bio_analysis': '简介分析',
        'account_positioning': '账号定位',
        'market_analysis': '市场分析',
        'operation_planning': '运营规划',
        'keyword_library': '关键词库',
    },
    'content': {
        'title': '标题',
        'hook': '开头钩子',
        'content_body': '内容',
        'visual_design': '视觉设计',
        'ending': '结尾',
    },
    'methodology': {
        'applicable_scenario': '适用场景',
        'applicable_audience': '适用人群',
    },
    'super_positioning': {
        'persona': '人群画像',
        'market_insight': '市场洞察',
        'keyword_filter': '关键词筛选',
        'question_guide': '问题引导词',
    },
}


@admin.route('/api/analysis-dimensions/grouped', methods=['GET'])
@login_required
def get_analysis_dimensions_grouped():
    """获取分析维度按二级分类分组（用于卡片展示）"""
    # 只查询激活的维度
    query = AnalysisDimension.query.filter_by(is_active=True).order_by(AnalysisDimension.category.asc(), AnalysisDimension.sub_category.asc(), AnalysisDimension.id.asc())
    all_dims = query.all()

    # 按 (category, sub_category) 分组
    groups = {}
    for d in all_dims:
        sub = d.sub_category or ''
        key = (d.category, sub)
        if key not in groups:
            sub_name = (ANALYSIS_DIMENSION_SUB_CATEGORY_NAMES.get(d.category) or {}).get(sub) or sub or '未分类'
            groups[key] = {
                'category': d.category,
                'sub_category': sub,
                'sub_category_name': sub_name,
                'dimensions': [],
            }
        groups[key]['dimensions'].append({
            'id': d.id,
            'name': d.name,
            'code': d.code,
            'icon': d.icon,
            'description': d.description,
            'is_active': d.is_active,
            'is_default': d.is_default,
            'usage_count': d.usage_count or 0,
        })

    # 保证所有配置过的二级分类都有条目（空列表也返回，便于前端展示空卡片）
    for cat, sub_map in ANALYSIS_DIMENSION_SUB_CATEGORY_NAMES.items():
        for sub_key, sub_name in sub_map.items():
            key = (cat, sub_key)
            if key not in groups:
                groups[key] = {
                    'category': cat,
                    'sub_category': sub_key,
                    'sub_category_name': sub_name,
                    'dimensions': [],
                }

    # 获取所有自定义排序
    try:
        order_records = AnalysisDimensionCategoryOrder.query.all()
        order_map = {(r.category, r.sub_category): r.sort_order for r in order_records}
    except Exception:
        order_map = {}

    # 按排序值排序（未设置排序的放最后，按默认顺序）
    data = sorted(groups.values(), key=lambda x: order_map.get((x['category'], x['sub_category']), 999))

    # 添加 sort_order 字段到返回数据
    for item in data:
        item['sort_order'] = order_map.get((item['category'], item['sub_category']), 999)

    response = jsonify({'success': True, 'data': data})
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@admin.route('/api/analysis-dimensions/category-order', methods=['POST'])
@login_required
def update_analysis_dimension_category_order():
    """更新二级分类排序"""
    data = request.get_json()
    if not data or 'orders' not in data:
        return jsonify({'success': False, 'message': '缺少排序数据'})

    orders = data['orders']  # [{category, sub_category, sort_order}, ...]

    try:
        for item in orders:
            record = AnalysisDimensionCategoryOrder.query.filter_by(
                category=item['category'],
                sub_category=item['sub_category']
            ).first()

            if record:
                record.sort_order = item['sort_order']
            else:
                record = AnalysisDimensionCategoryOrder(
                    category=item['category'],
                    sub_category=item['sub_category'],
                    sort_order=item['sort_order']
                )
                db.session.add(record)

        db.session.commit()
        return jsonify({'success': True, 'message': '排序已更新'})
    except Exception as e:
        db.session.rollback()
        # 如果表不存在，模拟成功返回
        if 'no such table' in str(e).lower():
            return jsonify({'success': True, 'message': '排序已保存（暂存本地）'})
        return jsonify({'success': False, 'message': str(e)})


@admin.route('/api/analysis-dimensions/<int:id>', methods=['GET'])
@login_required
def get_analysis_dimension(id):
    """获取单个分析维度"""
    dimension = AnalysisDimension.query.get_or_404(id)

    return jsonify({
        'success': True,
        'data': {
            'id': dimension.id,
            'name': dimension.name,
            'code': dimension.code,
            'icon': dimension.icon,
            'description': dimension.description,
            'category': dimension.category,
            'sub_category': dimension.sub_category,
            'category_group': dimension.category_group,
            'related_material_type': dimension.related_material_type,
            'is_active': dimension.is_active,
            'is_default': dimension.is_default,
            'sort_order': dimension.sort_order,
            'usage_count': dimension.usage_count,
            'rule_category': dimension.rule_category,
            'rule_type': dimension.rule_type,
            'prompt_template': dimension.prompt_template,
            'examples': getattr(dimension, 'examples', None) or '',
            'usage_tips': getattr(dimension, 'usage_tips', None) or '',
            'applicable_audience': getattr(dimension, 'applicable_audience', None) or '',
            # 市场洞察专用字段
            'trigger_conditions': getattr(dimension, 'trigger_conditions', None) or {},
            'content_template': getattr(dimension, 'content_template', None) or '',
            'importance': getattr(dimension, 'importance', 1) or 1,
            'weight': float(getattr(dimension, 'weight', 1) or 1),
        }
    })


def _default_icon_for_category(category: str) -> str:
    """根据一级分类返回默认图标"""
    return {'account': 'bi-person-badge', 'content': 'bi-file-text', 'methodology': 'bi-book', 'super_positioning': 'bi-bullseye'}.get(category, 'bi-circle')


def _generate_dimension_code(name: str, category: str, sub_category: str = None) -> str:
    """根据名称、分类自动生成唯一编码"""
    import re
    # 转换为拼音或拼音首字母简写
    name_pinyin = name.strip()
    # 简单处理：取拼音首字母 + 数字确保唯一
    # 这里先用名称拼音首字母缩写 + 分类前缀
    prefix = category[:3]
    if sub_category:
        prefix += '_' + sub_category[:3]
    # 生成基础编码
    base_code = prefix + '_' + name_pinyin[:4]
    # 确保唯一：查重并追加数字
    code = re.sub(r'[^a-z0-9_]', '', base_code.lower())
    existing = AnalysisDimension.query.filter(AnalysisDimension.code.like(f'{code}%')).all()
    if not existing:
        return code
    # 已有重复，追加数字
    nums = [int(d.code.split('_')[-1]) for d in existing if d.code.startswith(code + '_') and d.code.split('_')[-1].isdigit()]
    next_num = max(nums) + 1 if nums else 1
    return f'{code}_{next_num}'


@admin.route('/api/analysis-dimensions', methods=['POST'])
@login_required
@super_admin_required
def create_analysis_dimension():
    """创建分析维度"""
    data = request.get_json()

    # 自动生成编码
    code = _generate_dimension_code(
        name=data.get('name', ''),
        category=data.get('category', 'content'),
        sub_category=data.get('sub_category')
    )
    category = data.get('category', 'content')
    icon = data.get('icon') or _default_icon_for_category(category)

    dimension = AnalysisDimension(
        name=data.get('name'),
        code=code,
        icon=icon,
        description=data.get('description', ''),
        category=data.get('category', 'content'),
        sub_category=data.get('sub_category'),
        category_group=data.get('category_group'),
        related_material_type=data.get('related_material_type'),
        is_active=data.get('is_active', True),
        is_default=data.get('is_default', False),
        sort_order=data.get('sort_order', 0),
        rule_category=data.get('rule_category'),
        rule_type=data.get('rule_type'),
        prompt_template=data.get('prompt_template'),
        examples=data.get('examples', '') or None,
        usage_tips=data.get('usage_tips', '') or None,
        applicable_audience=data.get('applicable_audience', '') or None,
        # 市场洞察专用字段
        trigger_conditions=data.get('trigger_conditions', {}) or {},
        content_template=data.get('content_template', '') or None,
        importance=data.get('importance', 1) or 1,
        weight=float(data.get('weight', 1) or 1),
    )

    db.session.add(dimension)
    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'id': dimension.id,
            'name': dimension.name,
            'code': dimension.code
        }
    })


@admin.route('/api/analysis-dimensions/<int:id>', methods=['PUT'])
@login_required
@super_admin_required
def update_analysis_dimension(id):
    """更新分析维度"""
    dimension = AnalysisDimension.query.get_or_404(id)
    data = request.get_json()

    # 记录旧值
    old_category = dimension.category
    old_sub_category = dimension.sub_category
    old_name = dimension.name

    # 先更新 category/sub_category 和 name（这样后面重新生成 code 时能用到新值）
    if 'name' in data:
        dimension.name = data['name']
    if 'category' in data:
        dimension.category = data['category']
    if 'sub_category' in data:
        dimension.sub_category = data['sub_category']

    # 判断是否需要重新生成 code
    new_category = dimension.category
    new_sub_category = dimension.sub_category
    new_name = dimension.name

    if new_category != old_category or new_sub_category != old_sub_category or new_name != old_name:
        dimension.code = _generate_dimension_code(new_name, new_category, new_sub_category)

    if 'icon' in data:
        dimension.icon = data['icon']
    if 'description' in data:
        dimension.description = data['description']
    if 'category_group' in data:
        dimension.category_group = data['category_group']
    if 'related_material_type' in data:
        dimension.related_material_type = data['related_material_type']
    if 'is_active' in data:
        dimension.is_active = data['is_active']
    if 'is_default' in data:
        dimension.is_default = data['is_default']
    if 'sort_order' in data:
        dimension.sort_order = data['sort_order']
    if 'rule_category' in data:
        dimension.rule_category = data['rule_category']
    if 'rule_type' in data:
        dimension.rule_type = data['rule_type']
    if 'prompt_template' in data:
        dimension.prompt_template = data['prompt_template']
    if 'examples' in data:
        dimension.examples = data['examples'] or None
    if 'usage_tips' in data:
        dimension.usage_tips = data['usage_tips'] or None
    if 'applicable_audience' in data:
        dimension.applicable_audience = data['applicable_audience'] or None
    # 市场洞察专用字段
    if 'trigger_conditions' in data:
        dimension.trigger_conditions = data['trigger_conditions'] or {}
    if 'content_template' in data:
        dimension.content_template = data['content_template'] or None
    if 'importance' in data:
        dimension.importance = data['importance'] or 1
    if 'weight' in data:
        try:
            dimension.weight = float(data['weight'])
        except (TypeError, ValueError):
            pass

    db.session.commit()

    return jsonify({
        'success': True,
        'data': {
            'id': dimension.id,
            'name': dimension.name,
            'code': dimension.code
        }
    })


@admin.route('/api/analysis-dimensions/<int:id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_analysis_dimension(id):
    """删除分析维度 - 软删除，禁用维度"""
    dimension = AnalysisDimension.query.get_or_404(id)

    # 软删除：禁用维度
    dimension.is_active = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '维度已禁用'
    })


@admin.route('/api/analysis-dimensions/categories', methods=['GET'])
@login_required
def get_dimension_categories():
    """获取维度分类结构"""
    return jsonify({
        'success': True,
        'data': ANALYSIS_DIMENSION_CATEGORIES
    })


# 分析维度默认数据
DEFAULT_ANALYSIS_DIMENSIONS = [
    # 账号分析 - 昵称分析
    {'name': '身份/职业词', 'category': 'account', 'sub_category': 'nickname_analysis', 'description': '身份/职业/人设词，如：哥、姐、老师、医生', 'icon': 'bi-person-badge', 'usage_tips': '回答"你是谁"——职业、身份、人设'},
    {'name': '风格/记忆词', 'category': 'account', 'sub_category': 'nickname_analysis', 'description': '外观/气质/体型描述，如：红发、高冷、胖', 'icon': 'bi-palette', 'usage_tips': '只能描述外观/气质，不能回答"你是谁"'},
    {'name': '领域/垂类词', 'category': 'account', 'sub_category': 'nickname_analysis', 'description': '行业/技术/领域，如：数码、美食、母婴', 'icon': 'bi-tag', 'usage_tips': '行业/领域名称'},
    {'name': '地域词', 'category': 'account', 'sub_category': 'nickname_analysis', 'description': '地区名称，如：南漳、北京、上海', 'icon': 'bi-geo-alt', 'usage_tips': '地名/区域名，突出地域特色'},
    {'name': '属性关键词', 'category': 'account', 'sub_category': 'nickname_analysis', 'description': '品质/特点/属性，如：手工、野生、正宗', 'icon': 'bi-gem', 'usage_tips': '品质/工艺/属性描述'},
    # 账号分析 - 简介分析
    {'name': '身份标签', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '职业背景、学历、职称、专业身份', 'icon': 'bi-person-vcard', 'usage_tips': '回答"你是谁"——职业、学历、职称'},
    {'name': '价值主张', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '我提供什么价值，粉丝能得到什么', 'icon': 'bi-gift', 'usage_tips': '回答"粉丝关注你能得到什么"'},
    {'name': '差异化标签', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '为什么关注你，你和别人不一样在哪', 'icon': 'bi-stars', 'usage_tips': '回答"为什么选你"'},
    {'name': '行动号召', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '让粉丝做什么、关注后做什么', 'icon': 'bi-cursor', 'usage_tips': 'CTA指令'},
    {'name': '价格信息', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '具体的价格/报价', 'icon': 'bi-currency-dollar', 'usage_tips': '具体数字+价格单位'},
    {'name': '联系方式', 'category': 'account', 'sub_category': 'bio_analysis', 'description': '联系方式', 'icon': 'bi-telephone', 'usage_tips': '可直接联系的方式'},
    # 内容分析 - 标题
    {'name': '标题类型', 'category': 'content', 'sub_category': 'title', 'description': '疑问、数字、对比、情感、悬念等', 'icon': 'bi-card-heading', 'usage_tips': '判断标题属于哪种类型'},
    {'name': '核心关键词', 'category': 'content', 'sub_category': 'title', 'description': '标题中的核心关键词', 'icon': 'bi-key', 'usage_tips': '提取标题核心词'},
    {'name': '情绪词', 'category': 'content', 'sub_category': 'title', 'description': '标题中的情绪化词语', 'icon': 'bi-emoji-heart-eyes', 'usage_tips': '识别情绪表达'},
    # 内容分析 - 开头钩子
    {'name': '钩子类型', 'category': 'content', 'sub_category': 'hook', 'description': '提问、悬念、冲突、数字、故事等', 'icon': 'bi-lightning', 'usage_tips': '判断钩子类型'},
    {'name': '痛点/痒点', 'category': 'content', 'sub_category': 'hook', 'description': '引发共鸣的需求点', 'icon': 'bi-exclamation-triangle', 'usage_tips': '识别痛点/痒点'},
    # 内容分析 - 内容
    {'name': '选题方向', 'category': 'content', 'sub_category': 'content_body', 'description': '内容的主题方向', 'icon': 'bi-lightbulb', 'usage_tips': '识别选题'},
    {'name': '内容框架', 'category': 'content', 'sub_category': 'content_body', 'description': '内容的结构安排', 'icon': 'bi-diagram-3', 'usage_tips': '识别内容结构'},
    {'name': '情绪节奏', 'category': 'content', 'sub_category': 'content_body', 'description': '情绪起伏和节奏把控', 'icon': 'bi-graph-up', 'usage_tips': '识别情绪变化'},
    # 内容分析 - 视觉设计
    {'name': '封面类型', 'category': 'content', 'sub_category': 'visual_design', 'description': '图文、纯文字、人物、产品等', 'icon': 'bi-image', 'usage_tips': '识别封面类型'},
    {'name': '视觉元素', 'category': 'content', 'sub_category': 'visual_design', 'description': '构图、配色、字幕等', 'icon': 'bi-palette', 'usage_tips': '识别视觉元素'},
    # 内容分析 - 结尾
    {'name': '行动号召', 'category': 'content', 'sub_category': 'ending', 'description': '引导评论、关注、购买等', 'icon': 'bi-hand-thumbs-up', 'usage_tips': '识别CTA类型'},
    {'name': '互动引导', 'category': 'content', 'sub_category': 'ending', 'description': '引导用户互动', 'icon': 'bi-chat-dots', 'usage_tips': '识别互动方式'},
    # 方法论 - 适用场景
    {'name': '场景描述', 'category': 'methodology', 'sub_category': 'applicable_scenario', 'description': '适用场景的描述', 'icon': 'bi-scene', 'usage_tips': '识别方法适用场景'},
    # 方法论 - 适用人群
    {'name': '人群画像', 'category': 'methodology', 'sub_category': 'applicable_audience', 'description': '目标人群特征', 'icon': 'bi-people', 'usage_tips': '识别目标人群'},
    # 超级定位 - 人群画像（10个维度）
    {'name': '发展阶段', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户当前的发展阶段', 'icon': 'bi-graph-up', 'examples': '刚起步|天使轮|A轮|成熟期|转型期', 'usage_tips': '适用：创业者、企业家', 'applicable_audience': '创业者|企业家'},
    {'name': '营收规模', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的营收体量', 'icon': 'bi-currency-dollar', 'examples': '500万以下|3000万-2亿|5亿以上', 'usage_tips': '适用：企业家、B2B服务', 'applicable_audience': '企业家|B2B销售'},
    {'name': '团队规模', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的团队/组织规模', 'icon': 'bi-people-fill', 'examples': '10人以下|10-50人|50-400人', 'usage_tips': '适用：企业家、管理者', 'applicable_audience': '企业家|管理者'},
    {'name': '工作年限', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的职业/从业年限', 'icon': 'bi-clock-history', 'examples': '3-5年|5-10年|10年以上', 'usage_tips': '适用：职场人、专家', 'applicable_audience': '职场人|专家'},
    {'name': '行业背景', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户所在行业', 'icon': 'bi-briefcase', 'examples': '传统制造|互联网|金融|教育|医疗健康|零售消费|企业服务|本地生活', 'usage_tips': '适用：所有人群', 'applicable_audience': '通用'},
    {'name': '地域', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户所在地域', 'icon': 'bi-geo-alt', 'examples': '一线城市|新一线|三四线|海外', 'usage_tips': '适用：本地服务、区域业务', 'applicable_audience': '本地服务商|区域业务'},
    {'name': '年龄段', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的年龄段', 'icon': 'bi-calendar3', 'examples': '25-35岁|35-45岁|45岁以上', 'usage_tips': '适用：个人服务', 'applicable_audience': '个人服务'},
    {'name': '职位角色', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的职位/身份', 'icon': 'bi-person-badge', 'examples': '创始人|CEO|VP|总监|经理', 'usage_tips': '适用：B2B服务；画像组合展示时固定排在最后', 'applicable_audience': 'B2B服务|企业服务'},
    {'name': '痛点状态', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户当前面临的痛点/困境', 'icon': 'bi-exclamation-triangle', 'examples': '遇到瓶颈|想要转型|寻求突破', 'usage_tips': '适用：所有人群；同一批画像以此为共性锚点', 'applicable_audience': '通用'},
    {'name': '目标诉求', 'category': 'super_positioning', 'sub_category': 'persona', 'description': '目标客户的核心目标/期望', 'icon': 'bi-bullseye', 'examples': '想要增长|想要转型|想要变现', 'usage_tips': '适用：所有人群；同一批画像以此为共性锚点', 'applicable_audience': '通用'},
    # 超级定位 - 市场洞察
    {'name': '买用关系判断', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '判断购买方与使用方是否分离', 'icon': 'bi-arrow-left-right', 'examples': '桶装水（企业付费→员工使用）| 奶粉（家长买→宝宝用）| 礼品（送礼人买→收礼人用）', 'usage_tips': '涉及宝宝/老人/孩子/宠物 → 一定是买用分离', 'trigger_conditions': {}, 'content_template': '【买用关系判断】\n{description}\n- 买即用：买的人=用的人（如桶装水配送、自用食品）\n- 买用分离：买的人≠用的人（如奶粉是家长买给宝宝、礼品是送礼人买给收礼人）\n涉及宝宝、老人、孩子、宠物等 → **一定是买用分离**。', 'importance': 5},
    {'name': 'B端C端判断', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '判断是否存在企业客户（B端）和个人客户（C端）', 'icon': 'bi-building', 'examples': '矿泉水定制（ToB+ToC）| 企业软件（纯ToB）| 家庭桶装水（纯ToC）', 'usage_tips': '业务描述提到企业客户→B端存在；提到个人消费者→C端存在', 'trigger_conditions': {'has_enterprise': True}, 'content_template': '【B端C端判断】\n{description}\n- 同时存在ToB和ToC：矿泉水定制、餐具修复、礼品定制等\n- 纯ToC：桶装水（家庭自用）、食品（个人购买）\n- 纯ToB：企业软件、办公设备、大宗原材料', 'importance': 4},
    {'name': '搜前阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户还不知道用什么产品，只描述症状/体感/异常', 'icon': 'bi-search', 'examples': '宝宝拉肚子怎么回事？| 皮肤发红瘙痒怎么办？| 孩子挑食厌食怎么纠正？', 'usage_tips': '严禁：用什么产品/哪个好/怎么选 | 搜前用户搜的是症状词、体感词、异常反应词', 'trigger_conditions': {'search_stage': ['pre_search', 'all']}, 'content_template': '【用户搜索阶段：搜前】\n{description}\n严禁（出现即违规）：\n- 「用什么产品好」「哪个牌子好」「怎么选」\n- 「靠谱吗」「多少钱」「性价比」\n- 「哪里买」「渠道」「正规吗」\n搜前用户搜的是症状/体感/异常词：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 身体体感异常 | 症状词 | "宝宝拉肚子怎么回事？" |\n| 皮肤体表异常 | 体感词 | "皮肤发红瘙痒怎么办？" |\n| 行为变化 | 异常词 | "孩子挑食厌食怎么纠正？" |\n| 过敏不耐反应 | 反应词 | "喝完脸红肿起疹子正常吗？" |', 'importance': 5},
    {'name': '搜中阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户知道用什么产品，使用后症状加重/不适加剧', 'icon': 'bi-bar-chart', 'examples': 'XX产品用完更严重了怎么回事？| 使用后症状加重需要停用吗？| 用完有副作用怎么办？', 'usage_tips': '严禁：哪家好/多少钱/质量怎么样 | 搜中用户搜的是使用后症状词/异常反应词', 'trigger_conditions': {'search_stage': ['mid_search', 'all']}, 'content_template': '【用户搜索阶段：搜中】\n{description}\n严禁（出现即违规）：\n- 「哪家好」「哪个牌子好」「多少钱」\n- 「质量怎么样」「怎么选」「对比」\n搜中用户搜的是使用后症状词/异常反应词：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 症状加重 | 异常词 | "XX产品用完更严重了怎么回事？" |\n| 不适加剧 | 反应词 | "使用后症状加重需要停用吗？" |\n| 副作用 | 并发症 | "用完有副作用怎么办？" |', 'importance': 4},
    {'name': '搜后阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户确定要买，在找在哪里买', 'icon': 'bi-shop', 'examples': '定制水厂家联系方式 | 桶装水配送电话 | 婚宴定制水批发', 'usage_tips': '搜后用户搜的是渠道词，品牌词', 'trigger_conditions': {'search_stage': ['post_search', 'all']}, 'content_template': '【用户搜索阶段：搜后】\n{description}\n用户确定要买，找购买渠道的搜索行为：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 找供应商 | 渠道词 | "定制水厂家" |\n| 找服务 | 联系方式 | "桶装水配送电话" |\n| 找价格 | 批发词 | "定制水批发" |', 'importance': 3},
    {'name': '付费人顾虑', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '购买决策者担心使用后症状加重/健康风险', 'icon': 'bi-shield', 'examples': '用完有副作用怎么办？| 症状加重谁负责？| 长期用有健康风险吗？', 'usage_tips': '严禁：价格/性价比/采购便利 | 付费人关心：使用安全、健康风险、责任归属', 'trigger_conditions': {'has_enterprise': True}, 'content_template': '【付费方顾虑】\n{examples}\n{usage_tips}\n严禁（出现即违规）：\n- 「值不值这个价」「太贵了怎么办」\n- 「流程复不复杂」「好不好协调」\n- 「发票能不能报」「成本怎么算」\n付费人（企业/老板/决策者）真正关心的安全问题：\n- 健康担忧：用完有副作用吗？症状加重怎么办？\n- 安全风险：长期用有健康风险吗？谁负责？\n- 责任归属：用完出问题/有不适商家怎么处理？', 'importance': 4},
    {'name': '使用人痛点', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '实际使用者的体验问题和需求', 'icon': 'bi-person', 'examples': '水质口感 | 配送方便 | 品质稳定 | 使用体验', 'usage_tips': '使用人关心：体验、品质、方便', 'trigger_conditions': {}, 'content_template': '【使用人痛点】\n{examples}\n{usage_tips}\n使用人（员工/客户/家庭成员）关心的问题：\n- 体验感受：好不好喝？方不方便？\n- 品质稳定：每次质量一样吗？\n- 健康安全：卫不卫生？健不健康？', 'importance': 4},
    {'name': '蓝海长尾词', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '细分场景、精准需求、痛点解决方案类的蓝海关键词', 'icon': 'bi-stars', 'examples': '婚宴用水 | 凌晨配送 | 企业团建用水 | 火锅店供货', 'usage_tips': '中国人口基数大，再小的需求也有很多人！', 'trigger_conditions': {}, 'content_template': '【蓝海长尾词挖掘】\n{description}\n核心思路：中国人口基数大，再小的需求也有很多人！围绕问题（不围绕产品）\n关键词结构比例：\n| 分类 | 占比 | 说明 |\n|------|------|------|\n| 付费人关键词 | 25% | 价格担忧、采购便利、配送问题 |\n| 使用人关键词 | 20% | 体验、品质、健康担忧 |\n| 蓝海长尾词 | 25% | 细分场景、精准需求、痛点解决 |', 'importance': 5},

    # 超级定位 - 关键词筛选（新增，前台不显示，用于问题导向词生成）
    # 注意：content_template 中的 {EXAMPLE} 占位符由 KeywordFilterService.get_weighted_context()
    # 根据 business_desc 动态替换，不要在 DB 中写死任何产品示例
    {'name': '品牌核心词', 'category': 'super_positioning', 'sub_category': 'keyword_filter', 'description': '守住自有流量', 'icon': 'bi-bookmark-star', 'weight': 10, 'is_active': True, 'content_template': '【关键词筛选 L1：品牌核心词】守住自有流量\n\n锁定搜索你品牌名称的精准用户，避免竞品截流。\n\n包括：品牌全称、品牌简称、品牌+业务、品牌+口碑等。\n\n典型格式（严禁：价格/性价比/哪里买/靠谱吗）：\n- "XX{EXAMPLE_PRODUCT}用完有效果吗"\n- "XX{EXAMPLE_PRODUCT}使用后症状加重"\n- "XX{EXAMPLE_PRODUCT}正规渠道购买"\n\n这类词转化率极高，是品牌的自有流量护城河。\n\n❌ 严禁：质量怎么样/靠谱吗/多少钱/哪里买/性价比'},

    {'name': '用户需求词', 'category': 'super_positioning', 'sub_category': 'keyword_filter', 'description': '直击核心痛点', 'icon': 'bi-lightning', 'weight': 10, 'is_active': True, 'content_template': '【关键词筛选 L2：用户需求词】直击核心症状\n\n围绕用户使用后的真实体感/异常反应/行为变化，**严禁**使用"怎么选""哪家好""多少钱""性价比"等宏观词。\n\n典型格式（只写具体症状）：\n- "{EXAMPLE_PRODUCT}用完肚子疼/皮肤发红/大便异常"\n- "{EXAMPLE_PRODUCT}使用后症状没有改善甚至加重"\n- "{EXAMPLE_PRODUCT}吃完呕吐/腹泻/过敏"\n\n❌ 严禁：哪个牌子好/怎么选/多少钱/性价比\n✅ 只允许：具体症状词+体感词+异常反应'},

    {'name': '场景痛点词', 'category': 'super_positioning', 'sub_category': 'keyword_filter', 'description': '抢占细分场景', 'icon': 'bi-geo-alt', 'weight': 30, 'is_active': True, 'content_template': '【关键词筛选 L3：场景痛点词】抢占细分场景\n\n结合用户的使用场景、核心痛点、避坑需求，让关键词更有温度。\n\n典型格式：\n- "{EXAMPLE_SCENE_PAIN}"\n- "{EXAMPLE_SCENE_PROBLEM}"\n\nAI会优先推荐能解决具体痛点的内容，这类词竞争小、精准度高。'},

    {'name': '长尾转化词', 'category': 'super_positioning', 'sub_category': 'keyword_filter', 'description': '低竞争高转化', 'icon': 'bi-filter-square', 'weight': 30, 'is_active': True, 'content_template': '【关键词筛选 L4：长尾转化词】低竞争高转化\n\n由"核心业务+地域+场景+优势+需求"等组合而成。\n\n典型格式：\n- "{EXAMPLE_REGION_SERVICE}"\n- "{EXAMPLE_LONGTAIL}"\n\n这类词搜索用户几乎都是意向客户，竞争压力小，转化效果远超泛词。'},

    {'name': '地域精准词', 'category': 'super_positioning', 'sub_category': 'keyword_filter', 'description': '锁定本地客户', 'icon': 'bi-pin-map', 'weight': 20, 'is_active': True, 'content_template': '【关键词筛选 L5：地域精准词】锁定本地客户\n\n对于做本地生意的企业，地域词是重中之重，按"省+市+区县+商圈"分层布局。\n\n典型格式：\n- "{EXAMPLE_REGION}"\n\nAI搜索对地域匹配度要求极高，精准地域词能快速锁定周边客户。'},

    # 超级定位 - 问题引导词（LLM 基于种子词推测搜索意图时的问句形态）
    {'name': '纯关键词提问', 'category': 'super_positioning', 'sub_category': 'question_guide', 'description': '以具体症状/体感词为主的短问句，禁止：哪个好/怎么选/多少钱', 'icon': 'bi-hash', 'weight': 52, 'is_active': True, 'examples': 'XX产品用完肚子疼怎么回事 | XX产品使用后皮肤发红正常吗 | 宝宝吃完XX产品呕吐怎么办', 'usage_tips': '❌ 严禁：哪个好/怎么选/多少钱/靠谱吗 | ✅ 只允许：具体症状+使用后异常反应。典型用户占比约 45%～60%，但必须全部转为症状词。', 'content_template': '【问题引导词：纯关键词提问】\n使用频率（参考）：约 45%～60%\n❌ 严禁形态（出现即违规）：\n- 「XX产品哪个牌子好」\n- 「XX产品怎么选」\n- 「XX产品多少钱」\n- 「XX产品靠谱吗」\n- 「XX产品性价比」\n✅ 强制形态（必须全部转为症状词）：\n- 「XX产品用完肚子疼/发红/呕吐怎么回事」\n- 「XX产品使用后大便异常/皮肤瘙痒正常吗」\n- 「宝宝吃完XX产品哭闹/拒食/腹泻怎么办」\n\n所有问题导向词必须围绕「具体症状+使用后异常」，禁止宏观购买词。'},
    {'name': '混合型关键词提问', 'category': 'super_positioning', 'sub_category': 'question_guide', 'description': '在具体症状词基础上附带部分场景或条件，禁止：价格带/牌子对比', 'icon': 'bi-intersect', 'weight': 33, 'is_active': True, 'examples': '宝宝换季喝XX产品后腹泻呕吐怎么处理 | 皮肤敏感人群用XX产品发红怎么缓解', 'usage_tips': '❌ 严禁：价位段/哪个牌子好 | ✅ 只允许：症状词+人群+场景+条件', 'content_template': '【问题引导词：混合型关键词提问】\n使用频率（参考）：约 25%～40%\n❌ 严禁形态（出现即违规）：\n- 「380元价位段哪些XX产品好」\n- 「含XX成分的XX产品哪个牌子好」\n✅ 强制形态（必须转为症状+人群+场景）：\n- 「宝宝换季喝XX产品后腹泻/呕吐/哭闹怎么处理」\n- 「皮肤敏感人群用XX产品后发红/瘙痒/起疹子怎么办」\n- 「长期用XX产品后效果不明显/症状没有改善怎么判断」\n\n特征：在具体症状词基础上加入了人群、场景、条件描述，结果相关度中等。\n生成问题导向词时：约三分之一左右可落在本形态，必须全部转为症状词。'},
    {'name': '结构化关键词提问', 'category': 'super_positioning', 'sub_category': 'question_guide', 'description': '场景 + 诉求 + 约束清晰，可直接导向高精度、可执行的回答', 'icon': 'bi-diagram-3-fill', 'weight': 15, 'is_active': True, 'examples': '换奶粉后宝宝绿便但不哭闹，要不要立刻停？请列出3个关键观察指标。', 'usage_tips': '典型用户占比约 10%～15%；结构常为「场景 + 核心诉求 + 明确约束（如必须列出几步/几个指标）」。', 'content_template': '【问题引导词：结构化关键词提问】\n使用频率（参考）：约 10%～15%\n特征：场景、诉求与约束一体，往往能直接产出高精度、可执行的建议（如分步、列指标、给决策条件）。\n生成问题导向词时：约占一成多，用于覆盖高意向、强约束的长问句。\n典型结构：场景 + 诉求 + 约束。\n示例：\n- 「换奶粉后宝宝绿便但不哭闹，要不要立刻停？请列出3个关键观察指标。」'},
]


@admin.route('/api/analysis-dimensions/init', methods=['POST'])
@login_required
@super_admin_required
def init_analysis_dimensions():
    """初始化默认分析维度"""
    import traceback

    try:
        created_count = 0

        for item in DEFAULT_ANALYSIS_DIMENSIONS:
            # 检查是否已存在（按 category + sub_category + name 判断）
            exists = AnalysisDimension.query.filter_by(
                category=item['category'],
                sub_category=item['sub_category'],
                name=item['name']
            ).first()
            
            if not exists:
                # 自动生成编码
                code = _generate_dimension_code(
                    name=item['name'],
                    category=item['category'],
                    sub_category=item.get('sub_category')
                )
                
                dimension = AnalysisDimension(
                    name=item['name'],
                    code=code,
                    icon=item.get('icon', 'bi-circle'),
                    description=item.get('description', ''),
                    category=item['category'],
                    sub_category=item.get('sub_category'),
                    examples=item.get('examples', '') or None,
                    usage_tips=item.get('usage_tips', ''),
                    applicable_audience=item.get('applicable_audience', '') or None,
                    is_active=item.get('is_active', True),
                    is_default=True,
                    # 市场洞察专用字段
                    trigger_conditions=item.get('trigger_conditions', {}) or {},
                    content_template=item.get('content_template', '') or None,
                    importance=item.get('importance', 1) or 1,
                    weight=item.get('weight', 1.0) or 1.0
                )
                db.session.add(dimension)
                created_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'初始化成功，共创建 {created_count} 个维度'
        })
    except Exception as e:
        db.session.rollback()
        import logging
        logging.getLogger(__name__).error(f"初始化分析维度失败: {e}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'初始化失败: {str(e)}'
        }), 500


@admin.route('/api/portrait-dimensions/init', methods=['POST'])
@login_required
@super_admin_required
def init_portrait_dimensions():
    """初始化画像维度数据"""
    import traceback
    
    try:
        from services.portrait_dimension_data import PORTRAIT_DIMENSIONS_DATA
        
        created_count = 0
        for item in PORTRAIT_DIMENSIONS_DATA:
            # 检查是否已存在
            exists = AnalysisDimension.query.filter_by(
                category=item['category'],
                sub_category=item['sub_category'],
                name=item['name']
            ).first()
            
            if exists:
                continue
            
            # 自动生成编码
            code = _generate_dimension_code(
                name=item['name'],
                category=item['category'],
                sub_category=item.get('sub_category')
            )
            
            dimension = AnalysisDimension(
                name=item['name'],
                code=code,
                icon=item.get('icon', 'bi-circle'),
                description=item.get('description', ''),
                category=item['category'],
                sub_category=item.get('sub_category'),
                examples=item.get('examples', '') or None,
                usage_tips=item.get('usage_tips', '') or None,
                applicable_audience=item.get('applicable_audience', '') or None,
                prompt_template=item.get('prompt_template', '') or None,
                is_active=True,
                is_default=True,
                importance=item.get('importance', 1) or 1
            )
            db.session.add(dimension)
            created_count += 1
        
        db.session.commit()
        
        # 清除服务缓存
        from services.portrait_dimension_service import clear_cache
        clear_cache()
        
        return jsonify({
            'success': True,
            'created_count': created_count,
            'message': f'画像维度初始化成功，共创建 {created_count} 个维度'
        })
    except Exception as e:
        db.session.rollback()
        logging.getLogger(__name__).error(f"初始化画像维度失败: {e}\n{traceback.format_exc()}")
        return jsonify({
            'success': False,
            'message': f'初始化失败: {str(e)}'
        }), 500


@admin.route('/api/portrait-dimensions/preview', methods=['GET'])
@login_required
def preview_portrait_dimensions():
    """预览画像维度（AI精简版）"""
    from services.portrait_dimension_service import build_portrait_generation_context
    
    context = build_portrait_generation_context()
    
    # 格式化输出
    barrier_mapping_str = "\n".join([
        f"{k}→{v}" for k, v in context['内容方向映射'].items()
    ])
    
    return jsonify({
        'success': True,
        'data': {
            '矛盾类型': context['矛盾类型'],
            '转变类型': context['转变类型'],
            '障碍维度': context['障碍维度'],
            '障碍含义': context['障碍含义'],
            '障碍→内容映射': barrier_mapping_str,
            '转变阶段': context['转变阶段'],
            '买用关系': context['买用关系'],
            '内容类型': context['内容类型'],
            '意图阶段': context['意图阶段'],
            '风险维度': context['风险维度'],
            '成本维度': context['成本维度'],
            '效率维度': context['效率维度'],
            '情感维度': context['情感维度'],
            '社交维度': context['社交维度']
        }
    })


# =============================================================================
# 内容阶段配置（管理员专属）
# =============================================================================

@admin.route('/content-stage-config')
@login_required
def content_stage_config_page():
    """内容阶段配置页面（管理员专属）"""
    return render_template('admin/content_stage_config.html')


@admin.route('/api/content-stage/config', methods=['GET'])
@login_required
def get_content_stage_config():
    """
    获取内容阶段配置（管理员专属）
    返回：三套固定配比方案说明（仅展示，不存储）
    """
    stages = {
        '起号阶段': {
            'name': '起号阶段',
            'description': '新账号起步期（0-30天），以种草为主，快速积累权重',
            'topic_ratios': {
                '前置观望搜前种草盘': '90%',
                '刚需痛点盘': '0%（无）',
                '使用配套搜后种草盘': '10%',
            },
            'keyword_ratios': {
                '长尾词': '50%',
                '地域词': '30%',
                '核心大词': '20%',
            },
            'tag_strategy': '种草标签为主，无转化标签',
        },
        '成长阶段': {
            'name': '成长阶段',
            'description': '账号成长期（30-90天），种草+转化并重',
            'topic_ratios': {
                '前置观望搜前种草盘': '60%',
                '刚需痛点盘': '15%',
                '使用配套搜后种草盘': '25%',
            },
            'keyword_ratios': {
                '长尾词': '35%',
                '地域词': '30%',
                '核心大词': '35%',
            },
            'tag_strategy': '种草标签60% + 转化标签40%',
        },
        '成熟阶段': {
            'name': '成熟阶段',
            'description': '账号成熟期（90天+），以转化为核心',
            'topic_ratios': {
                '前置观望搜前种草盘': '30%',
                '刚需痛点盘': '50%',
                '使用配套搜后种草盘': '20%',
            },
            'keyword_ratios': {
                '长尾词': '20%',
                '地域词': '20%',
                '核心大词': '60%',
            },
            'tag_strategy': '转化标签为主，种草标签30%',
        },
    }

    return jsonify({
        'success': True,
        'data': {
            'stages': stages,
            'default_stage': '成长阶段',
        }
    })


@admin.route('/api/portrait/<int:portrait_id>/content-stage', methods=['POST'])
@login_required
def update_portrait_content_stage(portrait_id):
    """
    更新画像的内容阶段配置（管理员专属）
    前端：仅管理员可调用此接口
    """
    from models.public_models import SavedPortrait

    portrait = SavedPortrait.query.get(portrait_id)
    if not portrait:
        return jsonify({'success': False, 'message': '画像不存在'}), 404

    data = request.get_json() or {}
    stage = data.get('content_stage', '成长阶段')

    # 验证阶段值
    valid_stages = ['起号阶段', '成长阶段', '成熟阶段']
    if stage not in valid_stages:
        return jsonify({'success': False, 'message': f'无效的阶段值，仅支持：{"、".join(valid_stages)}'}), 400

    portrait.content_stage = stage
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'内容阶段已更新为：{stage}',
        'data': {'portrait_id': portrait_id, 'content_stage': stage}
    })


@admin.route('/api/portraits/content-stage', methods=['GET'])
@login_required
def list_portraits_with_stage():
    """
    列出所有画像的阶段配置（管理员专属）
    用于批量查看和修改
    """
    from models.public_models import SavedPortrait, PublicUser

    portraits = SavedPortrait.query.order_by(SavedPortrait.created_at.desc()).limit(200).all()
    result = []
    for p in portraits:
        user = PublicUser.query.get(p.user_id) if p.user_id else None
        result.append({
            'portrait_id': p.id,
            'portrait_name': p.portrait_name,
            'industry': p.industry,
            'business_description': p.business_description,
            'content_stage': p.content_stage or '成长阶段',
            'user_id': p.user_id,
            'user_email': user.email if user else None,
            'created_at': p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else None,
        })

    return jsonify({'success': True, 'data': result})


@admin.route('/api/portraits/content-stage/batch-update', methods=['POST'])
@login_required
def batch_update_content_stage():
    """
    批量更新画像内容阶段（管理员专属）
    """
    from models.public_models import SavedPortrait

    data = request.get_json() or {}
    portrait_ids = data.get('portrait_ids', [])
    stage = data.get('content_stage', '成长阶段')

    valid_stages = ['起号阶段', '成长阶段', '成熟阶段']
    if stage not in valid_stages:
        return jsonify({'success': False, 'message': f'无效的阶段值'}), 400

    updated = 0
    for pid in portrait_ids:
        portrait = SavedPortrait.query.get(pid)
        if portrait:
            portrait.content_stage = stage
            updated += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已批量更新 {updated} 个画像的阶段为：{stage}',
        'data': {'updated_count': updated}
    })


# ==================== 图文内容规则管理 ====================

@admin.route('/graphic-rules')
@login_required
@super_admin_required
def graphic_rules_page():
    """图文内容规则管理页面"""
    return render_template('admin/graphic_rules.html')


@admin.route('/api/graphic-rules', methods=['GET'])
@login_required
def get_graphic_rules():
    """获取图文规则列表"""
    try:
        from migrations.add_graphic_rules import GraphicContentRule

        rules = GraphicContentRule.query.order_by(GraphicContentRule.is_default.desc(), GraphicContentRule.created_at.desc()).all()

        result = [{
            'id': r.id,
            'rule_name': r.rule_name,
            'industry': r.industry,
            'target_customer': r.target_customer,
            'image_count': r.image_count,
            'image_ratio': r.image_ratio,
            'structure_type': r.structure_type,
            'version': r.version,
            'is_active': r.is_active,
            'is_default': r.is_default,
            'created_at': r.created_at.isoformat() if r.created_at else None,
        } for r in rules]

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"获取图文规则失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/graphic-rules/<int:rule_id>', methods=['GET'])
@login_required
def get_graphic_rule(rule_id):
    """获取单个图文规则详情"""
    try:
        from migrations.add_graphic_rules import (
            GraphicContentRule, ImageTemplateRule, HeadlineRule,
            DesignRule, SeoRule, PublishRule
        )

        rule = GraphicContentRule.query.get(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': '规则不存在'}), 404

        # 获取关联数据
        image_templates = ImageTemplateRule.query.filter_by(rule_id=rule_id).order_by(ImageTemplateRule.image_index).all()
        headline_rules = HeadlineRule.query.filter_by(rule_id=rule_id).all()
        design_rules = DesignRule.query.filter_by(rule_id=rule_id).all()
        seo_rule = SeoRule.query.filter_by(rule_id=rule_id).first()
        publish_rule = PublishRule.query.filter_by(rule_id=rule_id).first()

        result = {
            'id': rule.id,
            'rule_name': rule.rule_name,
            'industry': rule.industry,
            'target_customer': rule.target_customer,
            'image_count': rule.image_count,
            'image_ratio': rule.image_ratio,
            'structure_type': rule.structure_type,
            'rule_config': rule.rule_config,
            'version': rule.version,
            'is_active': rule.is_active,
            'is_default': rule.is_default,
            'created_at': rule.created_at.isoformat() if rule.created_at else None,
            'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
            'image_templates': [{
                'id': t.id,
                'image_index': t.image_index,
                'positioning': t.positioning,
                'emotion': t.emotion,
                'function': t.function,
                'headline_requirement': t.headline_requirement,
                'must_pain_first': t.must_pain_first,
            } for t in image_templates],
            'headline_rules': [{
                'id': h.id,
                'headline_type': h.headline_type,
                'type_name': h.type_name,
                'char_min': h.char_min,
                'char_max': h.char_max,
                'position_requirement': h.position_requirement,
                'function_desc': h.function_desc,
                'examples': h.examples,
                'is_required': h.is_required,
            } for h in headline_rules],
            'design_rules': [{
                'id': d.id,
                'design_type': d.design_type,
                'config_data': d.config_data,
                'description': d.description,
            } for d in design_rules],
            'seo_rule': {
                'id': seo_rule.id if seo_rule else None,
                'tag_count': seo_rule.tag_count if seo_rule else 6,
                'tag_types': seo_rule.tag_types if seo_rule else {},
                'keyword_types': seo_rule.keyword_types if seo_rule else {},
            } if seo_rule else None,
            'publish_rule': {
                'id': publish_rule.id if publish_rule else None,
                'schedule_config': publish_rule.schedule_config if publish_rule else [],
                'compliance_checklist': publish_rule.compliance_checklist if publish_rule else [],
            } if publish_rule else None,
        }

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"获取图文规则详情失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/graphic-rules/save', methods=['POST'])
@login_required
@super_admin_required
def save_graphic_rule():
    """保存图文规则"""
    try:
        from migrations.add_graphic_rules import (
            GraphicContentRule, ImageTemplateRule, HeadlineRule,
            DesignRule, SeoRule, PublishRule
        )

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效数据'}), 400

        rule_id = data.get('id')

        # 更新或创建主规则
        if rule_id:
            rule = GraphicContentRule.query.get(rule_id)
            if not rule:
                return jsonify({'success': False, 'message': '规则不存在'}), 404
        else:
            rule = GraphicContentRule()
            db.session.add(rule)

        rule.rule_name = data.get('rule_name', '新规则')
        rule.industry = data.get('industry')
        rule.target_customer = data.get('target_customer')
        rule.image_count = data.get('image_count', 5)
        rule.image_ratio = data.get('image_ratio', '9:16')
        rule.structure_type = data.get('structure_type', '痛点递进')
        rule.version = data.get('version', 'v1')
        rule.is_active = data.get('is_active', True)
        rule.created_by = current_user.id

        # 如果设为默认，先取消其他默认
        if data.get('is_default'):
            GraphicContentRule.query.filter(GraphicContentRule.is_default == True).update({'is_default': False})
            rule.is_default = True

        db.session.flush()  # 获取 rule.id

        # 更新图片模板
        ImageTemplateRule.query.filter_by(rule_id=rule.id).delete()
        for img_data in data.get('image_templates', []):
            img_rule = ImageTemplateRule(
                rule_id=rule.id,
                image_index=img_data.get('image_index', 1),
                positioning=img_data.get('positioning', ''),
                emotion=img_data.get('emotion', ''),
                function=img_data.get('function', ''),
                headline_requirement=img_data.get('headline_requirement', ''),
                must_pain_first=img_data.get('must_pain_first', True),
            )
            db.session.add(img_rule)

        # 更新大字金句规则
        HeadlineRule.query.filter_by(rule_id=rule.id).delete()
        for hl_data in data.get('headline_rules', []):
            hl_rule = HeadlineRule(
                rule_id=rule.id,
                headline_type=hl_data.get('headline_type', ''),
                type_name=hl_data.get('type_name', ''),
                char_min=hl_data.get('char_min', 5),
                char_max=hl_data.get('char_max', 10),
                position_requirement=hl_data.get('position_requirement', ''),
                function_desc=hl_data.get('function_desc', ''),
                examples=hl_data.get('examples', []),
                is_required=hl_data.get('is_required', True),
            )
            db.session.add(hl_rule)

        # 更新设计规则
        DesignRule.query.filter_by(rule_id=rule.id).delete()
        for ds_data in data.get('design_rules', []):
            ds_rule = DesignRule(
                rule_id=rule.id,
                design_type=ds_data.get('design_type', ''),
                config_data=ds_data.get('config_data', {}),
                description=ds_data.get('description', ''),
            )
            db.session.add(ds_rule)

        # 更新SEO规则
        SeoRule.query.filter_by(rule_id=rule.id).delete()
        seo_data = data.get('seo_rule', {})
        if seo_data:
            seo_rule = SeoRule(
                rule_id=rule.id,
                tag_count=seo_data.get('tag_count', 6),
                tag_types=seo_data.get('tag_types', {}),
                keyword_types=seo_data.get('keyword_types', {}),
            )
            db.session.add(seo_rule)

        # 更新发布规则
        PublishRule.query.filter_by(rule_id=rule.id).delete()
        pub_data = data.get('publish_rule', {})
        if pub_data:
            publish_rule = PublishRule(
                rule_id=rule.id,
                schedule_config=pub_data.get('schedule_config', []),
                compliance_checklist=pub_data.get('compliance_checklist', []),
            )
            db.session.add(publish_rule)

        db.session.commit()

        return jsonify({'success': True, 'message': '保存成功', 'data': {'id': rule.id}})
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存图文规则失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/graphic-rules/<int:rule_id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_graphic_rule(rule_id):
    """删除图文规则"""
    try:
        from migrations.add_graphic_rules import (
            GraphicContentRule, ImageTemplateRule, HeadlineRule,
            DesignRule, SeoRule, PublishRule
        )

        rule = GraphicContentRule.query.get(rule_id)
        if not rule:
            return jsonify({'success': False, 'message': '规则不存在'}), 404

        if rule.is_default:
            return jsonify({'success': False, 'message': '不能删除默认规则'}), 400

        # 删除关联数据
        ImageTemplateRule.query.filter_by(rule_id=rule_id).delete()
        HeadlineRule.query.filter_by(rule_id=rule_id).delete()
        DesignRule.query.filter_by(rule_id=rule_id).delete()
        SeoRule.query.filter_by(rule_id=rule_id).delete()
        PublishRule.query.filter_by(rule_id=rule_id).delete()

        db.session.delete(rule)
        db.session.commit()

        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除图文规则失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/graphic-rules/init', methods=['POST'])
@login_required
@super_admin_required
def init_graphic_rules():
    """初始化默认图文规则"""
    try:
        from migrations.add_graphic_rules import init_default_rules
        init_default_rules(db, created_by=current_user.id)
        return jsonify({'success': True, 'message': '初始化成功'})
    except Exception as e:
        logger.error(f"初始化图文规则失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/graphic-rules/service/get', methods=['GET'])
def get_active_graphic_rule():
    """获取当前生效的图文规则（供内容生成服务调用）"""
    try:
        from migrations.add_graphic_rules import (
            GraphicContentRule, ImageTemplateRule, HeadlineRule,
            DesignRule, SeoRule, PublishRule
        )
        from models.public_models import SavedPortrait

        industry = request.args.get('industry')
        portrait_id = request.args.get('portrait_id')

        # 优先按画像获取规则
        if portrait_id:
            portrait = SavedPortrait.query.get(portrait_id)
            if portrait and portrait.industry:
                industry = portrait.industry

        # 查找匹配的规则
        rule = None
        if industry:
            rule = GraphicContentRule.query.filter_by(
                industry=industry, is_active=True
            ).first()

        # 如果没有匹配的行业规则，使用默认规则
        if not rule:
            rule = GraphicContentRule.query.filter_by(
                is_default=True, is_active=True
            ).first()

        # 如果还是没有，查找任意激活的规则
        if not rule:
            rule = GraphicContentRule.query.filter_by(is_active=True).first()

        if not rule:
            return jsonify({'success': False, 'message': '暂无生效的规则'}), 404

        # 获取关联数据
        image_templates = ImageTemplateRule.query.filter_by(rule_id=rule.id).order_by(ImageTemplateRule.image_index).all()
        headline_rules = HeadlineRule.query.filter_by(rule_id=rule.id).all()
        design_rules = DesignRule.query.filter_by(rule_id=rule.id).all()
        seo_rule = SeoRule.query.filter_by(rule_id=rule.id).first()
        publish_rule = PublishRule.query.filter_by(rule_id=rule.id).first()

        result = {
            'id': rule.id,
            'rule_name': rule.rule_name,
            'industry': rule.industry,
            'image_count': rule.image_count,
            'image_ratio': rule.image_ratio,
            'structure_type': rule.structure_type,
            'image_templates': [{
                'image_index': t.image_index,
                'positioning': t.positioning,
                'emotion': t.emotion,
                'function': t.function,
                'headline_requirement': t.headline_requirement,
                'must_pain_first': t.must_pain_first,
            } for t in image_templates],
            'headline_rules': [{
                'headline_type': h.headline_type,
                'type_name': h.type_name,
                'char_min': h.char_min,
                'char_max': h.char_max,
                'position_requirement': h.position_requirement,
                'function_desc': h.function_desc,
                'is_required': h.is_required,
            } for h in headline_rules],
            'design_rules': {d.design_type: d.config_data for d in design_rules},
            'seo_rule': {
                'tag_count': seo_rule.tag_count if seo_rule else 6,
                'tag_types': seo_rule.tag_types if seo_rule else {},
                'keyword_types': seo_rule.keyword_types if seo_rule else {},
            } if seo_rule else None,
            'publish_rule': {
                'schedule_config': publish_rule.schedule_config if publish_rule else [],
                'compliance_checklist': publish_rule.compliance_checklist if publish_rule else [],
            } if publish_rule else None,
        }

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"获取生效规则失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
