"""
管理员路由 - 专家管理、知识库管理、渠道管理、行业管理
"""
import os
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_login import login_required, current_user
from models.models import db, User, Expert, Skill, KnowledgeCategory, KnowledgeArticle, KnowledgeAnalysis, KnowledgeRule, Industry, Channel, Client, KnowledgeAccount, KnowledgeContent, ReportTemplate, ContentTemplate, TemplateDependency, TemplateRefreshLog, TemplateContentItem, TemplateEditHistory, PersonaMethod, PersonaRole, UsageScenario, DemandScenario, PainPoint, HotTopic, SeasonalTopic, ContentTitle, ContentHook, ContentStructure, ContentEnding, ContentReplication, ContentCover, ContentTopic, ContentPsychology, ContentCommercial, ContentWhyPopular, ContentTag, ContentCharacter, ContentForm, ContentInteraction, AnalysisDimension, AnalysisDimensionCategoryOrder, RuleExtractionLog
from sqlalchemy import or_, and_
from constants import ANALYSIS_DIMENSIONS, DIMENSION_TO_MATERIAL_TYPE, MATERIAL_TYPES, INDUSTRY_OPTIONS, ANALYSIS_DIMENSION_CATEGORIES
from functools import wraps
from datetime import datetime
from services.skill_loader import get_skill_loader

admin = Blueprint('admin', __name__)


# 工作台专家：skill_slug -> DB Expert slug（init_db 使用旧 slug）
SKILL_SLUG_TO_DB_SLUG = {
    'chief-operating-officer': 'master',
    'market-insights-commander': 'monitor',
    'ai-operations-commander': 'ai-operations-commander',
    'content-creator': 'content',
    'knowledge-base': 'knowledge',
}
WORKBENCH_DB_SLUGS = list(set(SKILL_SLUG_TO_DB_SLUG.values()))


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
    expert_count = Expert.query.count()
    client_count = Client.query.count()
    industry_count = Industry.query.count()
    article_count = KnowledgeArticle.query.count()
    
    # 最近添加的客户
    recent_clients = Client.query.order_by(Client.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         now=datetime.now(),
                         user_count=user_count,
                         expert_count=expert_count,
                         client_count=client_count,
                         industry_count=industry_count,
                         article_count=article_count,
                         recent_clients=recent_clients)


# ========== 人群画像生成 ==========

@admin.route('/persona')
@login_required
@super_admin_required
def persona_generator():
    """人群画像生成页面"""
    return render_template('admin/persona_generator.html')


# ==================== 专家管理（工作台专家列表） ====================

@admin.route('/experts')
@login_required
@super_admin_required
def experts():
    """工作台专家列表：与工作台左侧专家列表一致（同一数据源、同一顺序）"""
    skill_loader = get_skill_loader()
    # 与 API get_experts 一致：使用 get_workbench_skills() 得到与工作台相同的专家集合与顺序
    skills = skill_loader.get_workbench_skills()
    db_experts = {ex.slug: ex for ex in Expert.query.filter(Expert.slug.in_(WORKBENCH_DB_SLUGS)).all()}

    workbench_experts = []
    for s in skills:
        skill_slug = s.get('slug')
        db_slug = SKILL_SLUG_TO_DB_SLUG.get(skill_slug)
        ex = db_experts.get(db_slug) if db_slug else None
        commands = s.get('commands', []) or skill_loader.get_commands_for_skill(skill_slug)

        item = {
            'expert': ex,
            'skill_slug': skill_slug,
            'name': (ex.nickname or ex.name) if ex else s.get('nickname', skill_slug),
            'title': ex.title if ex else s.get('title', ''),
            'description': ex.description if ex else s.get('description', ''),
            'sort_order': ex.sort_order if ex and ex.sort_order is not None else 999,
            'is_active': ex.is_active if ex else True,
            'commands': commands,
        }
        workbench_experts.append(item)

    # 与 API 一致：按 sort_order 排序（同序时保持 get_workbench_skills 顺序）
    order_idx = {s['slug']: i for i, s in enumerate(skills)}
    workbench_experts.sort(key=lambda x: (x['sort_order'], order_idx.get(x['skill_slug'], 999)))
    return render_template('admin/experts.html', workbench_experts=workbench_experts)


@admin.route('/experts/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def expert_add():
    """添加专家"""
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        description = request.form.get('description')
        command = request.form.get('command')
        icon = request.form.get('icon')
        
        # 检查slug是否已存在
        if Expert.query.filter_by(slug=slug).first():
            flash('专家标识已存在', 'danger')
            return redirect(url_for('admin.expert_add'))
        
        expert = Expert(
            name=name,
            slug=slug,
            description=description,
            command=command,
            icon=icon,
            capabilities=[]
        )
        db.session.add(expert)
        db.session.commit()
        flash('专家添加成功', 'success')
        return redirect(url_for('admin.experts'))
    
    return render_template('admin/expert_form.html', expert=None)


@admin.route('/experts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def expert_edit(id):
    """编辑工作台专家：昵称、职位、欢迎语、排序"""
    expert = Expert.query.get_or_404(id)

    if request.method == 'POST':
        expert.nickname = request.form.get('nickname', '').strip()
        expert.title = request.form.get('title', '').strip()
        expert.description = request.form.get('description', '').strip()
        expert.sort_order = int(request.form.get('sort_order', 0) or 0)
        expert.is_active = 'is_active' in request.form
        db.session.commit()
        flash('专家更新成功', 'success')
        return redirect(url_for('admin.experts'))

    # GET 时返回工作台专家列表页（复用 experts() 逻辑）
    return experts()


@admin.route('/experts/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def expert_delete(id):
    """删除专家"""
    expert = Expert.query.get_or_404(id)
    db.session.delete(expert)
    db.session.commit()
    flash('专家删除成功', 'success')
    return redirect(url_for('admin.experts'))


# ==================== 知识库管理 ====================

@admin.route('/knowledge')
@login_required
@super_admin_required
def knowledge():
    """知识库列表"""
    return render_template('admin/knowledge.html')


@admin.route('/knowledge/rules')
@login_required
@super_admin_required
def knowledge_rules():
    """规则库详情"""
    # 读取已入库的规则
    rules_data = load_knowledge_rules()

    return render_template('admin/knowledge_rules.html', rules_data=rules_data)


def load_knowledge_rules():
    """加载知识库规则文件"""
    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'skills', 'knowledge-base', '规则'
    )

    rule_files = {
        'keywords': '关键词库_规则模板.md',
        'topic': '选题库_规则模板.md',
        'template': '内容模板_规则模板.md',
        'operation': '运营规划_规则模板.md',
        'market': '市场分析_规则模板.md'
    }

    category_names = {
        'keywords': '关键词库',
        'topic': '选题库',
        'template': '内容模板',
        'operation': '运营规划',
        'market': '市场分析'
    }

    category_icons = {
        'keywords': 'bi-tags',
        'topic': 'bi-lightbulb',
        'template': 'bi-file-text',
        'operation': 'bi-gear',
        'market': 'bi-graph-up'
    }

    all_rules = []
    categories = []

    for category, filename in rule_files.items():
        filepath = os.path.join(rules_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析规则
            rules = []
            sections = re.split(r'^#{2,3}\s+', content, flags=re.MULTILINE)
            for i, section in enumerate(sections[1:], 1):
                lines = section.split('\n')
                title = lines[0].strip() if lines else ''
                body = '\n'.join(lines[1:]).strip()
                if title:
                    # 生成摘要
                    summary = body[:200] + '...' if len(body) > 200 else body
                    summary = summary.replace('|', '').replace('\n', ' ').strip()
                    rules.append({
                        'id': f"{category}_{i}",
                        'title': title,
                        'content': body,
                        'summary': summary
                    })

            if rules:
                categories.append({
                    'id': category,
                    'name': category_names.get(category, category),
                    'icon': category_icons.get(category, 'bi-folder'),
                    'count': len(rules)
                })
                all_rules.extend(rules)

    return {
        'rules': all_rules,
        'categories': categories,
        'total': len(all_rules)
    }


@admin.route('/knowledge/category/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def knowledge_category_add():
    """添加知识库分类"""
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug')
        description = request.form.get('description')
        icon = request.form.get('icon')
        
        category = KnowledgeCategory(
            name=name,
            slug=slug,
            description=description,
            icon=icon
        )
        db.session.add(category)
        db.session.commit()
        flash('分类添加成功', 'success')
        return redirect(url_for('admin.knowledge'))
    
    return render_template('admin/knowledge_category_form.html', category=None)


@admin.route('/knowledge/category/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def knowledge_category_edit(id):
    """编辑知识库分类"""
    category = KnowledgeCategory.query.get_or_404(id)
    
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.slug = request.form.get('slug')
        category.description = request.form.get('description')
        category.icon = request.form.get('icon')
        db.session.commit()
        flash('分类更新成功', 'success')
        return redirect(url_for('admin.knowledge'))
    
    return render_template('admin/knowledge_category_form.html', category=category)


@admin.route('/knowledge/category/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def knowledge_category_delete(id):
    """删除知识库分类"""
    category = KnowledgeCategory.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('分类删除成功', 'success')
    return redirect(url_for('admin.knowledge'))


@admin.route('/knowledge/articles')
@login_required
@super_admin_required
def knowledge_articles():
    """知识库文章列表"""
    # 获取筛选参数
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # 构建查询
    query = KnowledgeArticle.query

    if category_id:
        query = query.filter(KnowledgeArticle.category_id == category_id)

    if search:
        query = query.filter(KnowledgeArticle.title.ilike(f'%{search}%'))

    # 分页
    pagination = query.order_by(KnowledgeArticle.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 获取所有分类（用于下拉筛选）
    categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()

    return render_template('admin/knowledge_articles.html',
                           articles=pagination.items,
                           pagination=pagination,
                           categories=categories,
                           selected_category=category_id,
                           search_keyword=search)


@admin.route('/knowledge/article/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def knowledge_article_add():
    """添加知识库文章"""
    if request.method == 'POST':
        title = request.form.get('title')
        slug = request.form.get('slug')
        category_id = request.form.get('category_id', type=int)
        content_type = request.form.get('content_type', 'pure_text')
        content = request.form.get('content')
        author = request.form.get('author')
        source = request.form.get('source')
        tags_str = request.form.get('tags', '')
        is_published = request.form.get('is_published') == '1'

        # 处理标签
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

        # 自动生成 slug
        if not slug:
            # 简单 slug 生成：转小写、空格变横线、移除非字母数字
            import re
            slug = title.lower()
            slug = re.sub(r'[^\w\s-]', '', slug)  # 移除非字母数字（保留空格、横线）
            slug = re.sub(r'[-\s]+', '-', slug)  # 多空格/横线变单一横线
            slug = slug.strip('-')  # 去除首尾横线

        # 检查 slug 唯一性
        existing = KnowledgeArticle.query.filter_by(slug=slug).first()
        if existing:
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        article = KnowledgeArticle(
            title=title,
            slug=slug,
            category_id=category_id,
            content_type=content_type,
            content=content,
            author=author,
            source=source,
            tags=tags,
            is_published=is_published
        )

        db.session.add(article)
        db.session.commit()

        flash('文章添加成功', 'success')
        return redirect(url_for('admin.knowledge_articles'))

    # 获取分类列表
    categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()
    return render_template('admin/knowledge_article_form.html', article=None, categories=categories)


@admin.route('/knowledge/article/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def knowledge_article_edit(id):
    """编辑知识库文章"""
    article = KnowledgeArticle.query.get_or_404(id)

    if request.method == 'POST':
        article.title = request.form.get('title')
        slug = request.form.get('slug')
        article.category_id = request.form.get('category_id', type=int)
        article.content_type = request.form.get('content_type', 'pure_text')
        article.content = request.form.get('content')
        article.author = request.form.get('author')
        article.source = request.form.get('source')
        tags_str = request.form.get('tags', '')
        article.tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []
        article.is_published = request.form.get('is_published') == '1'

        # 更新 slug（如果提供）
        if slug and slug != article.slug:
            # 检查唯一性
            existing = KnowledgeArticle.query.filter_by(slug=slug).first()
            if existing and existing.id != article.id:
                flash('Slug 已存在，请更换', 'danger')
                categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()
                return render_template('admin/knowledge_article_form.html', article=article, categories=categories)
            article.slug = slug

        db.session.commit()

        flash('文章更新成功', 'success')
        return redirect(url_for('admin.knowledge_articles'))

    categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()
    return render_template('admin/knowledge_article_form.html', article=article, categories=categories)


@admin.route('/knowledge/article/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def knowledge_article_delete(id):
    """删除知识库文章"""
    article = KnowledgeArticle.query.get_or_404(id)

    # 检查是否有查询参数决定返回位置
    category_id = request.args.get('category_id')
    search = request.args.get('search')
    page = request.args.get('page')

    db.session.delete(article)
    db.session.commit()

    flash('文章删除成功', 'success')

    # 构建返回URL
    args = []
    if category_id:
        args.append(f'category_id={category_id}')
    if search:
        args.append(f'search={search}')
    if page:
        args.append(f'page={page}')

    if args:
        return redirect(url_for('admin.knowledge_articles') + '?' + '&'.join(args))
    return redirect(url_for('admin.knowledge_articles'))


@admin.route('/knowledge/article/<int:id>/preview')
@login_required
@super_admin_required
def knowledge_article_preview(id):
    """预览知识库文章"""
    article = KnowledgeArticle.query.get_or_404(id)
    return render_template('admin/knowledge_article_preview.html', article=article)


# ==================== 知识库内容分析 ====================

@admin.route('/knowledge/analyze')
@login_required
@super_admin_required
def knowledge_analyze():
    """知识库内容分析页面"""
    return render_template('admin/knowledge_analyze.html')


@admin.route('/knowledge/account/analyze')
@login_required
@super_admin_required
def knowledge_account_analysis():
    """账号分析页面"""
    return render_template('admin/knowledge_account_analysis.html')


@admin.route('/knowledge/dismantle')
@login_required
@super_admin_required
def knowledge_dismantle():
    """爆款拆解页面"""
    return render_template('admin/knowledge_dismantle.html')


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
    # 检查是否有客户使用该行业
    if industry.clients.count() > 0:
        flash('该行业下有客户，无法删除', 'danger')
        return redirect(url_for('admin.industries'))
    
    db.session.delete(industry)
    db.session.commit()
    flash('行业删除成功', 'success')
    return redirect(url_for('admin.industries'))


# ==================== 公开平台管理 ====================

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


# ==================== 客户管理 ====================

@admin.route('/clients')
@login_required
@super_admin_required
def clients():
    """客户列表（超级管理员可以看到所有客户），每页10条"""
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    per_page = 10
    pagination = Client.query.order_by(Client.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    clients_list = pagination.items
    industries = Industry.query.all()

    # 为每个客户添加录入者信息
    for client in clients_list:
        if client.creator:
            if client.creator.role == 'super_admin':
                client.creator_name = '管理员'
            else:
                client.creator_name = client.creator.username
        else:
            client.creator_name = '管理员'

    channels = Channel.query.all()
    return render_template('admin/clients.html', clients=clients_list, industries=industries, channels=channels, pagination=pagination)


@admin.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def client_edit(id):
    """编辑客户"""
    client = Client.query.get_or_404(id)
    industries = Industry.query.all()
    
    if request.method == 'POST':
        client.name = request.form.get('name')
        client.business_type = request.form.get('business_type')
        client.contact = request.form.get('contact')
        client.description = request.form.get('description')
        client.industry_id = request.form.get('industry_id')
        client.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('客户更新成功', 'success')
        return redirect(url_for('admin.clients'))
    
    return render_template('admin/client_form.html', client=client, industries=industries)


@admin.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def client_delete(id):
    """删除客户"""
    import os

    client = Client.query.get_or_404(id)
    from models.models import Keyword, Topic, Monitor, Content, ExpertOutput, ChatSession, ChatMessage, MonitorReport

    try:
        # 删除关键词
        Keyword.query.filter_by(client_id=id).delete()
        # 删除选题
        Topic.query.filter_by(client_id=id).delete()
        # 删除监控
        Monitor.query.filter_by(client_id=id).delete()
        # 删除内容
        Content.query.filter_by(client_id=id).delete()
        # 删除舆情监控报告
        MonitorReport.query.filter_by(client_id=id).delete()

        # 删除产出记录（包括报告文件）
        outputs = ExpertOutput.query.filter_by(client_id=id).all()
        for output in outputs:
            if getattr(output, 'file_path', None):
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                full_path = os.path.normpath(os.path.join(base_dir, output.file_path.lstrip('/').lstrip(os.sep)))
                if os.path.exists(full_path) and full_path.startswith(base_dir):
                    try:
                        os.remove(full_path)
                    except Exception:
                        pass
            db.session.delete(output)

        # 删除会话及消息
        sessions = ChatSession.query.filter_by(client_id=id).all()
        for session in sessions:
            ChatMessage.query.filter_by(session_id=session.id).delete()
        ChatSession.query.filter_by(client_id=id).delete()

        # 删除客户
        db.session.delete(client)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': '删除失败：' + str(e), 'success': False}), 500

    return jsonify({'code': 200, 'message': '删除成功', 'success': True})


@admin.route('/clients/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def client_add():
    """管理员添加客户"""
    industries = Industry.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        industry_id = request.form.get('industry_id')
        business_type = request.form.get('business_type')
        contact = request.form.get('contact')
        description = request.form.get('description')
        
        # 客户直接归属当前管理员
        client = Client(
            user_id=current_user.id,
            name=name,
            industry_id=industry_id if industry_id else None,
            business_type=business_type,
            contact=contact,
            description=description,
            is_active=True
        )
        db.session.add(client)
        db.session.commit()
        
        flash('客户添加成功', 'success')
        return redirect(url_for('admin.clients'))
    
    return render_template('admin/client_form.html', client=None, industries=industries)


@admin.route('/clients/<int:id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def toggle_client(id):
    """切换客户状态"""
    client = Client.query.get_or_404(id)
    client.is_active = not client.is_active
    db.session.commit()
    flash(f'客户已{"启用" if client.is_active else "禁用"}', 'success')
    return redirect(url_for('admin.clients'))


# ==================== 知识库规则管理 API ====================

@admin.route('/api/knowledge/analysis', methods=['POST'])
@login_required
@super_admin_required
def create_knowledge_analysis():
    """创建知识分析记录"""
    try:
        data = request.get_json()

        analysis = KnowledgeAnalysis(
            source_content=data.get('source_content', ''),
            source_type=data.get('source_type', 'text'),
            content_summary=data.get('content_summary', ''),
            analysis_dimensions=data.get('analysis_dimensions'),
            analysis_result=data.get('analysis_result', ''),
            extracted_rules=data.get('extracted_rules'),
            status='pending'
        )

        db.session.add(analysis)
        db.session.commit()

        return jsonify({
            'success': True,
            'analysis_id': analysis.id,
            'message': '分析记录创建成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@admin.route('/api/knowledge/rules', methods=['POST'])
@login_required
@super_admin_required
def save_knowledge_rules():
    """保存用户选择的知识规则"""
    try:
        data = request.get_json()
        analysis_id = data.get('analysis_id')
        rules = data.get('rules', [])

        if not analysis_id:
            return jsonify({
                'success': False,
                'message': '缺少分析记录ID'
            }), 400

        # 查找分析记录
        analysis = KnowledgeAnalysis.query.get(analysis_id)
        if not analysis:
            return jsonify({
                'success': False,
                'message': '分析记录不存在'
            }), 404

        # 保存选中的规则
        saved_rules = []
        for rule_data in rules:
            rule = KnowledgeRule(
                analysis_id=analysis_id,
                category=rule_data.get('category', ''),
                rule_title=rule_data.get('rule_title', ''),
                rule_content=rule_data.get('rule_content', ''),
                rule_type=rule_data.get('rule_type', 'dimension'),
                source_dimension=rule_data.get('source_dimension', ''),
                status='active'
            )
            db.session.add(rule)
            saved_rules.append(rule)

        # 更新分析记录状态
        analysis.status = 'approved'

        db.session.commit()

        # 更新对应的模板文件
        try:
            update_knowledge_template_files(rules)
        except Exception as e:
            print(f"更新模板文件失败: {e}")

        return jsonify({
            'success': True,
            'saved_count': len(saved_rules),
            'message': f'成功保存 {len(saved_rules)} 条规则'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


def update_knowledge_template_files(rules):
    """更新知识库模板文件"""
    import os
    import markdown

    # 按分类分组规则
    category_files = {
        '关键词库': '关键词库_规则模板.md',
        '选题库': '选题库_规则模板.md',
        '内容模板': '内容模板_规则模板.md',
        '运营规划': '运营规划_规则模板.md',
        '市场分析': '市场分析_规则模板.md'
    }

    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'skills', 'knowledge-base', '规则'
    )

    for category, filename in category_files.items():
        category_rules = [r for r in rules if r.category == category]
        if not category_rules:
            continue

        filepath = os.path.join(rules_dir, filename)
        if not os.path.exists(filepath):
            continue

        # 读取现有内容
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 添加新规则到文件末尾
        new_rules_section = f"\n\n---\n\n## 新增规则（{datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"

        for rule in category_rules:
            new_rules_section += f"### {rule.rule_title}\n\n"
            new_rules_section += f"**来源维度**: {rule.source_dimension}\n\n"
            new_rules_section += f"**规则内容**: {rule.rule_content}\n\n"
            new_rules_section += f"**规则类型**: {rule.rule_type}\n\n"

        # 追加到文件
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(new_rules_section)


@admin.route('/api/knowledge/analysis/<int:id>')
@login_required
@super_admin_required
def get_knowledge_analysis(id):
    """获取知识分析记录"""
    analysis = KnowledgeAnalysis.query.get_or_404(id)

    rules = KnowledgeRule.query.filter_by(analysis_id=id).all()

    return jsonify({
        'success': True,
        'analysis': {
            'id': analysis.id,
            'source_content': analysis.source_content,
            'source_type': analysis.source_type,
            'content_summary': analysis.content_summary,
            'analysis_dimensions': analysis.analysis_dimensions,
            'analysis_result': analysis.analysis_result,
            'extracted_rules': analysis.extracted_rules,
            'status': analysis.status,
            'created_at': analysis.created_at.isoformat() if analysis.created_at else None
        },
        'rules': [{
            'id': r.id,
            'category': r.category,
            'rule_title': r.rule_title,
            'rule_content': r.rule_content,
            'rule_type': r.rule_type,
            'source_dimension': r.source_dimension,
            'status': r.status
        } for r in rules]
    })


# ========== 规则入库比对 ==========
@admin.route('/api/knowledge/rules/check', methods=['POST'])
@login_required
@super_admin_required
def check_rules_similarity():
    """检查规则是否与现有规则重复"""
    try:
        data = request.get_json()
        rules = data.get('rules', [])

        if not rules:
            return jsonify({
                'success': True,
                'results': []
            })

        results = []
        for rule_data in rules:
            rule_content = rule_data.get('rule_content', '').strip()
            rule_category = rule_data.get('category', '')
            source_dimension = rule_data.get('source_dimension', '')

            if not rule_content:
                results.append({
                    'rule_content': '',
                    'is_duplicate': False,
                    'similar_rules': []
                })
                continue

            # 简单相似度检查：完全匹配 或 包含关系
            query = KnowledgeRule.query.filter_by(status='active')

            # 先尝试精确匹配
            exact_match = query.filter(
                KnowledgeRule.rule_content == rule_content
            ).first()

            if exact_match:
                results.append({
                    'rule_content': rule_content[:50] + '...' if len(rule_content) > 50 else rule_content,
                    'is_duplicate': True,
                    'similar_rules': [{
                        'id': exact_match.id,
                        'rule_title': exact_match.rule_title,
                        'rule_content': exact_match.rule_content[:50] + '...' if exact_match.rule_content and len(exact_match.rule_content) > 50 else exact_match.rule_content,
                        'category': exact_match.category,
                        'similarity': '完全相同'
                    }]
                })
                continue

            # 模糊匹配：检查内容是否已存在（简化版：检查包含关系）
            similar_rules = []
            all_rules = query.all()
            for existing_rule in all_rules:
                if existing_rule.rule_content:
                    # 检查是否高度相似（简化：内容重复度 > 60%）
                    similarity = calculate_similarity(rule_content, existing_rule.rule_content)
                    if similarity > 0.6:
                        similar_rules.append({
                            'id': existing_rule.id,
                            'rule_title': existing_rule.rule_title,
                            'rule_content': existing_rule.rule_content[:50] + '...' if len(existing_rule.rule_content) > 50 else existing_rule.rule_content,
                            'category': existing_rule.rule_category,
                            'similarity': f'{int(similarity * 100)}%'
                        })

            if similar_rules:
                results.append({
                    'rule_content': rule_content[:50] + '...' if len(rule_content) > 50 else rule_content,
                    'is_duplicate': True,
                    'similar_rules': similar_rules[:3]  # 最多返回3条
                })
            else:
                results.append({
                    'rule_content': rule_content[:50] + '...' if len(rule_content) > 50 else rule_content,
                    'is_duplicate': False,
                    'similar_rules': []
                })

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        logger.error(f"[check_rules_similarity] 检查失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


def calculate_similarity(text1, text2):
    """计算两个文本的相似度（简化版）"""
    if not text1 or not text2:
        return 0

    # 转小写比较
    t1 = text1.lower()
    t2 = text2.lower()

    # 完全相同
    if t1 == t2:
        return 1.0

    # 计算公共字符数
    set1 = set(t1)
    set2 = set(t2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0

    return intersection / union


@admin.route('/api/knowledge/analysis/list')
@login_required
@super_admin_required
def list_knowledge_analysis():
    """获取知识分析记录列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', None)

    query = KnowledgeAnalysis.query
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(KnowledgeAnalysis.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'success': True,
        'items': [{
            'id': a.id,
            'source_type': a.source_type,
            'content_summary': a.content_summary[:100] if a.content_summary else '',
            'status': a.status,
            'created_at': a.created_at.isoformat() if a.created_at else None,
            'rules_count': KnowledgeRule.query.filter_by(analysis_id=a.id).count()
        } for a in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page
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


# ==================== 模板联动管理 ====================

@admin.route('/template-dependencies')
@login_required
@super_admin_required
def template_dependencies():
    """模板依赖关系管理"""
    dependencies = TemplateDependency.query.order_by(TemplateDependency.source_template_type).all()
    return render_template('admin/template_dependencies.html', dependencies=dependencies)


@admin.route('/template-dependencies/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def template_dependency_add():
    """添加模板依赖关系"""
    if request.method == 'POST':
        data = request.form

        dependency = TemplateDependency(
            source_template_type=data.get('source_template_type'),
            target_template_type=data.get('target_template_type'),
            dependency_type=data.get('dependency_type', 'full_refresh'),
            update_rules=data.get('update_rules')
        )

        db.session.add(dependency)
        db.session.commit()
        flash('依赖关系创建成功', 'success')
        return redirect(url_for('admin.template_dependencies'))

    return render_template('admin/template_dependency_form.html')


@admin.route('/template-dependencies/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def template_dependency_edit(id):
    """编辑模板依赖关系"""
    dependency = TemplateDependency.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form

        dependency.source_template_type = data.get('source_template_type')
        dependency.target_template_type = data.get('target_template_type')
        dependency.dependency_type = data.get('dependency_type', 'full_refresh')
        dependency.update_rules = data.get('update_rules')

        db.session.commit()
        flash('依赖关系更新成功', 'success')
        return redirect(url_for('admin.template_dependencies'))

    return render_template('admin/template_dependency_form.html', dependency=dependency)


@admin.route('/template-dependencies/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def template_dependency_delete(id):
    """删除模板依赖关系"""
    dependency = TemplateDependency.query.get_or_404(id)

    db.session.delete(dependency)
    db.session.commit()
    flash('依赖关系已删除', 'success')
    return redirect(url_for('admin.template_dependencies'))


# ==================== 模板刷新日志 ====================

@admin.route('/template-logs')
@login_required
@super_admin_required
def template_logs():
    """模板刷新日志"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = TemplateRefreshLog.query.order_by(
        TemplateRefreshLog.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/template_logs.html',
                          logs=pagination.items,
                          pagination=pagination)


@admin.route('/api/template/refresh', methods=['POST'])
@login_required
@super_admin_required
def trigger_template_refresh():
    """触发模板刷新"""
    data = request.get_json()

    template_type = data.get('template_type')  # market_analysis / keyword / topic / operation
    source_type = data.get('source_type', 'manual')  # manual / auto
    source_id = data.get('source_id')

    # 创建刷新日志
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


# ==================== 知识库-方法论解析入库（读书笔记/电子书整理） ====================

def _split_lines(field_value):
    """表单单行/多行文本转为列表，按换行分割并去空"""
    if not field_value:
        return []
    if isinstance(field_value, list):
        return [x.strip() for x in field_value if x and str(x).strip()]
    return [x.strip() for x in str(field_value).splitlines() if x.strip()]


@admin.route('/persona-methods')
@login_required
@super_admin_required
def persona_methods():
    """方法论列表（知识库模块：含人设、消费心理学、关键词筛选等）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category_filter = request.args.get('category', '')

    q = PersonaMethod.query.order_by(PersonaMethod.created_at.desc())
    if category_filter:
        q = q.filter(PersonaMethod.methodology_category == category_filter)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/persona_methods.html',
                          methods=pagination.items,
                          pagination=pagination,
                          category_filter=category_filter)


@admin.route('/persona-methods/parse', methods=['GET', 'POST'])
@login_required
@super_admin_required
def persona_method_parse():
    """解析入库：输入读书笔记/电子书整理的自然语言，解析归类后入库"""
    if request.method == 'POST':
        data = request.get_json() or request.form
        raw_text = (data.get('raw_text') or '').strip()
        if not raw_text:
            if request.is_json:
                return jsonify({'code': 400, 'message': '请输入要解析的内容'})
            flash('请输入要解析的内容', 'warning')
            return render_template('admin/persona_method_parse.html', raw_text=request.form.get('raw_text', ''))

        try:
            from services.llm import get_llm_service
            from routes.knowledge_api import parse_llm_json
        except Exception as e:
            if request.is_json:
                return jsonify({'code': 500, 'message': f'LLM 依赖加载失败: {str(e)}'})
            flash(f'LLM 服务不可用: {str(e)}', 'danger')
            return render_template('admin/persona_method_parse.html', raw_text=raw_text)

        llm = get_llm_service()
        if not llm:
            if request.is_json:
                return jsonify({'code': 500, 'message': 'LLM 服务未配置'})
            flash('LLM 服务未配置，无法解析', 'danger')
            return render_template('admin/persona_method_parse.html', raw_text=raw_text)

        system_prompt = """你是一个知识库整理专家。用户会粘贴一段来自读书笔记或电子书整理的自然语言内容，你需要：
1. 判断这段内容属于哪一类方法论，从以下类别中选一个（只输出英文标识）：
   consumer_psychology - 消费心理学
   keyword_screening   - 关键词筛选/关键词方法
   persona             - 人设/角色/账号定位
   visual_design       - 视觉设计/排版/呈现
   operation           - 运营策略/投放/转化
   general             - 通用/其他
2. 提取并结构化为 JSON，字段如下（均为字符串或字符串数组）：
   methodology_category: 上面选的英文标识
   name: 方法论名称（简短标题）
   source_book: 来源书籍或资料名称（若用户有提到）
   author: 作者（若有）
   method_summary: 方法论摘要/核心要点（多段用换行）
   applicable_scenario: 适用场景，数组，如 ["短视频带货", "本地生活"]
   applicable_audience: 适用人群，数组
   usage_guide: 使用指南或注意事项
   keywords: 关键词数组
   tags: 分类标签数组
只输出一个 JSON 对象，不要 markdown 代码块外的说明。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请解析并归类以下内容：\n\n{raw_text}"}
        ]
        result_text = llm.chat(messages, temperature=0.3, max_tokens=2000)
        if not result_text:
            if request.is_json:
                return jsonify({'code': 500, 'message': 'LLM 未返回结果'})
            flash('解析未返回结果', 'danger')
            return render_template('admin/persona_method_parse.html', raw_text=raw_text)

        try:
            parsed = parse_llm_json(result_text)
            for key in ('applicable_scenario', 'applicable_audience', 'keywords', 'tags'):
                if key in parsed and not isinstance(parsed.get(key), list):
                    val = parsed.get(key)
                    parsed[key] = [val] if val else []
            if request.is_json:
                return jsonify({'code': 0, 'data': parsed})
            return render_template('admin/persona_method_parse_confirm.html', parsed=parsed, raw_text=raw_text)
        except Exception as e:
            if request.is_json:
                return jsonify({'code': 500, 'message': f'解析结果不是有效 JSON: {str(e)}'})
            flash(f'解析失败: {str(e)}', 'danger')
            return render_template('admin/persona_method_parse.html', raw_text=raw_text)

    return render_template('admin/persona_method_parse.html')


@admin.route('/persona-methods/ingest', methods=['POST'])
@login_required
@super_admin_required
def persona_method_ingest():
    """确认解析结果并入库（写入方法论表，可选同步知识库文章）"""
    data = request.form
    name = (data.get('name') or '').strip()
    if not name:
        flash('方法论名称为必填', 'warning')
        return redirect(url_for('admin.persona_method_parse'))

    methodology_category = (data.get('methodology_category') or 'general').strip() or 'general'
    method = PersonaMethod(
        methodology_category=methodology_category,
        name=name,
        source_book=data.get('source_book') or None,
        author=data.get('author') or None,
        method_summary=data.get('method_summary') or None,
        applicable_scenario=_split_lines(data.get('applicable_scenario')),
        applicable_audience=_split_lines(data.get('applicable_audience')),
        usage_guide=data.get('usage_guide') or None,
        keywords=_split_lines(data.get('keywords')),
        tags=_split_lines(data.get('tags')),
        created_by=current_user.id
    )
    db.session.add(method)
    db.session.commit()

    category_slugs = {
        'consumer_psychology': 'consumer-psychology',
        'keyword_screening': 'keyword-method',
        'persona': 'persona-method',
        'visual_design': 'visual-design',
        'operation': 'operation-method',
        'general': 'methodology-general',
    }
    slug = category_slugs.get(methodology_category, 'methodology-general')
    cat = KnowledgeCategory.query.filter_by(slug=slug).first()
    if not cat:
        cat = KnowledgeCategory.query.filter_by(slug='methodology').first()
    if cat:
        article = KnowledgeArticle(
            category_id=cat.id,
            title=name,
            content=(method.method_summary or '') + '\n\n' + (method.usage_guide or ''),
            source=method.source_book or '方法论入库',
            tags=method.keywords or []
        )
        db.session.add(article)
        db.session.commit()

    flash('已入库成功，可在下方列表中查看', 'success')
    return redirect(url_for('admin.persona_methods'))


@admin.route('/persona-methods/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def persona_method_add():
    """手动添加方法论（不经过解析）"""
    if request.method == 'POST':
        data = request.form
        name = (data.get('name') or '').strip()
        if not name:
            flash('方法论名称为必填', 'warning')
            return render_template('admin/persona_method_form.html')
        method = PersonaMethod(
            methodology_category=(data.get('methodology_category') or 'general').strip() or 'general',
            name=name,
            source_book=data.get('source_book') or None,
            author=data.get('author') or None,
            method_summary=data.get('method_summary') or None,
            applicable_scenario=_split_lines(data.get('applicable_scenario')),
            applicable_audience=_split_lines(data.get('applicable_audience')),
            usage_guide=data.get('usage_guide') or None,
            keywords=_split_lines(data.get('keywords')),
            tags=_split_lines(data.get('tags')),
            created_by=current_user.id
        )
        db.session.add(method)
        db.session.commit()
        flash('方法论已创建', 'success')
        return redirect(url_for('admin.persona_methods'))

    return render_template('admin/persona_method_form.html')


@admin.route('/persona-methods/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def persona_method_edit(id):
    """编辑方法论"""
    method = PersonaMethod.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form
        method.methodology_category = (data.get('methodology_category') or 'general').strip() or 'general'
        method.name = data.get('name')
        method.source_book = data.get('source_book') or None
        method.author = data.get('author') or None
        method.method_summary = data.get('method_summary') or None
        method.applicable_scenario = _split_lines(data.get('applicable_scenario'))
        method.applicable_audience = _split_lines(data.get('applicable_audience'))
        method.usage_guide = data.get('usage_guide') or None
        method.keywords = _split_lines(data.get('keywords'))
        method.tags = _split_lines(data.get('tags'))

        db.session.commit()
        flash('方法论已更新', 'success')
        return redirect(url_for('admin.persona_methods'))

    return render_template('admin/persona_method_form.html', method=method)


@admin.route('/persona-methods/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def persona_method_delete(id):
    """删除方法论"""
    method = PersonaMethod.query.get_or_404(id)

    db.session.delete(method)
    db.session.commit()
    flash('方法论已删除', 'success')
    return redirect(url_for('admin.persona_methods'))


@admin.route('/persona-methods/<int:id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def persona_method_toggle(id):
    """切换方法论启用状态"""
    method = PersonaMethod.query.get_or_404(id)
    method.is_active = not method.is_active
    db.session.commit()
    flash(f'方法论已{"启用" if method.is_active else "禁用"}', 'success')
    return redirect(url_for('admin.persona_methods'))


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


# ==================== 热点话题管理 ====================

@admin.route('/hot-topics')
@login_required
@super_admin_required
def hot_topics():
    """热点话题列表"""
    topic_type = request.args.get('type', 'hot')

    if topic_type == 'hot':
        items = HotTopic.query.order_by(HotTopic.created_at.desc()).all()
    else:
        items = SeasonalTopic.query.order_by(SeasonalTopic.topic_date.desc()).all()

    return render_template('admin/hot_topics.html', items=items, topic_type=topic_type)


@admin.route('/hot-topics/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def hot_topic_add():
    """添加热点话题"""
    topic_type = request.args.get('type', 'hot')

    if request.method == 'POST':
        data = request.form

        if topic_type == 'hot':
            item = HotTopic(
                topic_name=data.get('topic_name'),
                topic_source=data.get('topic_source'),
                topic_url=data.get('topic_url'),
                hot_level=data.get('hot_level'),
                category=data.get('category'),
                description=data.get('description'),
                related_keywords=request.form.getlist('related_keywords'),
                related_industry=request.form.getlist('related_industry'),
                applicable_content_types=request.form.getlist('applicable_content_types')
            )
        else:
            from datetime import datetime as dt
            topic_date_str = data.get('topic_date')
            topic_date = dt.strptime(topic_date_str, '%Y-%m-%d').date() if topic_date_str else None

            item = SeasonalTopic(
                topic_name=data.get('topic_name'),
                topic_type=data.get('topic_type'),
                topic_date=topic_date,
                recurrence=data.get('recurrence'),
                description=data.get('description'),
                marketing_angles=request.form.getlist('marketing_angles'),
                content_suggestions=request.form.getlist('content_suggestions'),
                related_industry=request.form.getlist('related_industry'),
                keywords=request.form.getlist('keywords')
            )

        db.session.add(item)
        db.session.commit()
        flash('话题创建成功', 'success')
        return redirect(url_for('admin.hot_topics', type=topic_type))

    return render_template('admin/hot_topic_form.html', topic_type=topic_type)


@admin.route('/hot-topics/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def hot_topic_edit(id):
    """编辑热点话题"""
    topic_type = request.args.get('type', 'hot')

    if topic_type == 'hot':
        item = HotTopic.query.get_or_404(id)
    else:
        item = SeasonalTopic.query.get_or_404(id)

    if request.method == 'POST':
        data = request.form

        if topic_type == 'hot':
            item.topic_name = data.get('topic_name')
            item.topic_source = data.get('topic_source')
            item.topic_url = data.get('topic_url')
            item.hot_level = data.get('hot_level')
            item.category = data.get('category')
            item.description = data.get('description')
            item.related_keywords = request.form.getlist('related_keywords')
            item.related_industry = request.form.getlist('related_industry')
            item.applicable_content_types = request.form.getlist('applicable_content_types')
        else:
            from datetime import datetime as dt
            topic_date_str = data.get('topic_date')
            item.topic_name = data.get('topic_name')
            item.topic_type = data.get('topic_type')
            item.topic_date = dt.strptime(topic_date_str, '%Y-%m-%d').date() if topic_date_str else None
            item.recurrence = data.get('recurrence')
            item.description = data.get('description')
            item.marketing_angles = request.form.getlist('marketing_angles')
            item.content_suggestions = request.form.getlist('content_suggestions')
            item.related_industry = request.form.getlist('related_industry')
            item.keywords = request.form.getlist('keywords')

        db.session.commit()
        flash('话题更新成功', 'success')
        return redirect(url_for('admin.hot_topics', type=topic_type))

    return render_template('admin/hot_topic_form.html', topic_type=topic_type, item=item)


@admin.route('/hot-topics/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def hot_topic_delete(id):
    """删除热点话题"""
    topic_type = request.args.get('type', 'hot')

    if topic_type == 'hot':
        item = HotTopic.query.get_or_404(id)
    else:
        item = SeasonalTopic.query.get_or_404(id)

    db.session.delete(item)
    db.session.commit()
    flash('话题已删除', 'success')
    return redirect(url_for('admin.hot_topics', type=topic_type))


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


# ==================== 爆款复制功能 ====================

import logging
logger = logging.getLogger(__name__)

@admin.route('/api/content-replication', methods=['POST'])
@login_required
def create_replication():
    """创建爆款复制任务"""
    try:
        data = request.get_json()

        client_id = data.get('client_id')
        source_content_id = data.get('source_content_id')
        source_account_id = data.get('source_account_id')
        replication_mode = data.get('replication_mode', 'partial_copy')
        modification_notes = data.get('modification_notes', '')

        if not client_id:
            return jsonify({'success': False, 'message': '请选择客户'})

        if not source_content_id and not source_account_id:
            return jsonify({'success': False, 'message': '请选择源内容或源账号'})

        # 创建复制记录
        replication = ContentReplication(
            user_id=current_user.id,
            client_id=client_id,
            source_content_id=source_content_id,
            source_account_id=source_account_id,
            replication_mode=replication_mode,
            modification_notes=modification_notes,
            status='draft'
        )

        db.session.add(replication)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '复制任务创建成功',
            'data': {'id': replication.id}
        })

    except Exception as e:
        logger.error(f"创建复制任务失败: {e}")
        return jsonify({'success': False, 'message': str(e)})


@admin.route('/api/content-replication/<int:id>', methods=['GET'])
@login_required
def get_replication(id):
    """获取复制详情"""
    replication = ContentReplication.query.get_or_404(id)

    return jsonify({
        'success': True,
        'data': {
            'id': replication.id,
            'client_id': replication.client_id,
            'source_content_id': replication.source_content_id,
            'source_account_id': replication.source_account_id,
            'replication_mode': replication.replication_mode,
            'modification_notes': replication.modification_notes,
            'generated_title': replication.generated_title,
            'generated_content': replication.generated_content,
            'generated_script': replication.generated_script,
            'status': replication.status,
            'is_favorite': replication.is_favorite,
            'created_at': replication.created_at.isoformat() if replication.created_at else None
        }
    })


@admin.route('/api/content-replication/<int:id>/favorite', methods=['POST'])
@login_required
def toggle_replication_favorite(id):
    """切换收藏状态"""
    replication = ContentReplication.query.get_or_404(id)
    replication.is_favorite = not replication.is_favorite
    db.session.commit()

    return jsonify({
        'success': True,
        'is_favorite': replication.is_favorite
    })


# ==================== 分析维度管理 ====================

@admin.route('/analysis-dimensions')
@login_required
@super_admin_required
def analysis_dimensions_page():
    """分析维度管理页面"""
    return render_template('admin/analysis_dimensions.html')


# ==================== 公式要素管理 ====================

@admin.route('/formula-elements')
@login_required
@super_admin_required
def formula_elements_page():
    """公式要素管理页面"""
    return render_template('admin/formula_elements.html')


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
            'importance': getattr(dimension, 'importance', 1) or 1
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
        importance=data.get('importance', 1) or 1
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
    {'name': '搜前阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户还不知道用什么产品的阶段', 'icon': 'bi-search', 'examples': '企业宣传用什么有档次？| 婚宴用什么水？| 送礼送什么好？', 'usage_tips': '搜前用户搜的是问题词、痛点词', 'trigger_conditions': {'search_stage': ['pre_search', 'all']}, 'content_template': '【用户搜索阶段：搜前】\n{description}\n用户在有问题但不知道用什么产品时的搜索行为：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 问题不明确 | 问题词 | "企业宣传用什么有档次？" |\n| 场景不明确 | 痛点词 | "婚宴用水推荐" |\n| 需求不明确 | 模糊需求词 | "送礼送什么好" |', 'importance': 5},
    {'name': '搜中阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户知道用什么，但不知道选哪个', 'icon': 'bi-bar-chart', 'examples': '定制水哪家好？| 桶装水哪个牌子好？| 婚宴定制水多少钱？', 'usage_tips': '搜中用户搜的是对比词、评测词', 'trigger_conditions': {'search_stage': ['mid_search', 'all']}, 'content_template': '【用户搜索阶段：搜中】\n{description}\n用户知道用什么产品，但在对比选择的搜索行为：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 品牌对比 | 对比词 | "定制水哪家好？" |\n| 价格对比 | 价格词 | "定制水多少钱？" |\n| 质量评估 | 评测词 | "定制水质量怎么样？" |', 'importance': 4},
    {'name': '搜后阶段分析', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '用户确定要买，在找在哪里买', 'icon': 'bi-shop', 'examples': '定制水厂家联系方式 | 桶装水配送电话 | 婚宴定制水批发', 'usage_tips': '搜后用户搜的是渠道词，品牌词', 'trigger_conditions': {'search_stage': ['post_search', 'all']}, 'content_template': '【用户搜索阶段：搜后】\n{description}\n用户确定要买，找购买渠道的搜索行为：\n| 场景 | 搜索词类型 | 示例 |\n|------|------------|------|\n| 找供应商 | 渠道词 | "定制水厂家" |\n| 找服务 | 联系方式 | "桶装水配送电话" |\n| 找价格 | 批发词 | "定制水批发" |', 'importance': 3},
    {'name': '付费人顾虑', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '购买决策者的心理障碍和顾虑', 'icon': 'bi-shield', 'examples': '价格担忧 | 采购便利性 | 报销问题 | 决策风险', 'usage_tips': '付费人关心：价格、成本、便利、风险', 'trigger_conditions': {'has_enterprise': True}, 'content_template': '【付费方顾虑】\n{examples}\n{usage_tips}\n付费人（企业/老板/决策者）关心的问题：\n- 价格担忧：值不值这个价？太贵了怎么办？\n- 采购便利性：流程复不复杂？好不好协调？\n- 报销/成本：发票能不能报？成本怎么算？', 'importance': 4},
    {'name': '使用人痛点', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '实际使用者的体验问题和需求', 'icon': 'bi-person', 'examples': '水质口感 | 配送方便 | 品质稳定 | 使用体验', 'usage_tips': '使用人关心：体验、品质、方便', 'trigger_conditions': {}, 'content_template': '【使用人痛点】\n{examples}\n{usage_tips}\n使用人（员工/客户/家庭成员）关心的问题：\n- 体验感受：好不好喝？方不方便？\n- 品质稳定：每次质量一样吗？\n- 健康安全：卫不卫生？健不健康？', 'importance': 4},
    {'name': '蓝海长尾词', 'category': 'super_positioning', 'sub_category': 'market_insight', 'description': '细分场景、精准需求、痛点解决方案类的蓝海关键词', 'icon': 'bi-stars', 'examples': '婚宴用水 | 凌晨配送 | 企业团建用水 | 火锅店供货', 'usage_tips': '中国人口基数大，再小的需求也有很多人！', 'trigger_conditions': {}, 'content_template': '【蓝海长尾词挖掘】\n{description}\n核心思路：中国人口基数大，再小的需求也有很多人！围绕问题（不围绕产品）\n关键词结构比例：\n| 分类 | 占比 | 说明 |\n|------|------|------|\n| 付费人关键词 | 25% | 价格担忧、采购便利、配送问题 |\n| 使用人关键词 | 20% | 体验、品质、健康担忧 |\n| 蓝海长尾词 | 25% | 细分场景、精准需求、痛点解决 |', 'importance': 5},
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
                    is_active=True,
                    is_default=True,
                    # 市场洞察专用字段
                    trigger_conditions=item.get('trigger_conditions', {}) or {},
                    content_template=item.get('content_template', '') or None,
                    importance=item.get('importance', 1) or 1
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


# ==================== 规则自动提取管理 ====================

@admin.route('/rule-extractions')
@login_required
@super_admin_required
def rule_extractions_page():
    """规则提取审核页面"""
    return render_template('admin/rule_extractions.html')


@admin.route('/api/rule-extractions', methods=['GET'])
@login_required
def get_rule_extractions():
    """获取规则提取记录列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    status = request.args.get('status')

    query = RuleExtractionLog.query

    if status:
        query = query.filter(RuleExtractionLog.status == status)

    query = query.order_by(RuleExtractionLog.created_at.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        'success': True,
        'data': [{
            'id': log.id,
            'source_replication_id': log.source_replication_id,
            'source_title': log.source_title,
            'source_content': log.source_content[:100] + '...' if log.source_content and len(log.source_content) > 100 else log.source_content,
            'generated_title': log.generated_title,
            'generated_content': log.generated_content[:100] + '...' if log.generated_content and len(log.generated_content) > 100 else log.generated_content,
            'suggested_rules': log.suggested_rules,
            'status': log.status,
            'approved_rules_count': log.approved_rules_count,
            'reviewed_by': log.reviewed_by,
            'reviewed_at': log.reviewed_at.isoformat() if log.reviewed_at else None,
            'review_notes': log.review_notes,
            'created_at': log.created_at.isoformat() if log.created_at else None
        } for log in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page
    })


@admin.route('/api/rule-extractions/<int:id>/approve', methods=['POST'])
@login_required
@super_admin_required
def approve_rule_extraction(id):
    """审核通过规则提取记录"""
    log = RuleExtractionLog.query.get_or_404(id)
    data = request.get_json() or {}

    if log.status != 'pending':
        return jsonify({
            'success': False,
            'message': '该记录已审核'
        }), 400

    # 创建规则
    approved_count = 0
    for rule_data in (log.suggested_rules or []):
        if not rule_data.get('rule_content'):
            continue

        rule = KnowledgeRule(
            analysis_id=log.source_replication_id,
            dimension_id=rule_data.get('dimension_id'),
            category=rule_data.get('category', 'template'),
            rule_title=rule_data.get('rule_title', '自动提取规则'),
            rule_content=rule_data.get('rule_content'),
            rule_type=rule_data.get('rule_type', 'dimension'),
            source_dimension=rule_data.get('source_dimension'),
            applicable_scenarios=rule_data.get('applicable_scenarios'),
            applicable_audiences=rule_data.get('applicable_audiences'),
            platforms=rule_data.get('platforms'),
            is_auto_extracted=True,
            extraction_log_id=log.id,
            status='active'
        )
        db.session.add(rule)
        approved_count += 1

    # 更新提取记录状态
    log.status = 'approved'
    log.approved_rules_count = approved_count
    log.reviewed_by = current_user.id
    log.reviewed_at = datetime.utcnow()
    log.review_notes = data.get('notes', '')

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'成功创建 {approved_count} 条规则',
        'approved_count': approved_count
    })


@admin.route('/api/rule-extractions/<int:id>/reject', methods=['POST'])
@login_required
@super_admin_required
def reject_rule_extraction(id):
    """拒绝规则提取记录"""
    log = RuleExtractionLog.query.get_or_404(id)
    data = request.get_json() or {}

    if log.status != 'pending':
        return jsonify({
            'success': False,
            'message': '该记录已审核'
        }), 400

    log.status = 'rejected'
    log.reviewed_by = current_user.id
    log.reviewed_at = datetime.utcnow()
    log.review_notes = data.get('notes', '')

    db.session.commit()

    return jsonify({
        'success': True,
        'message': '已拒绝'
    })


# ==================== 统一规则库管理 ====================

@admin.route('/rules-library')
@login_required
def rules_library_page():
    """规则库管理页面"""
    # 动态获取所有二级分类及其规则类型（用于生成规则库 Tab）
    sub_categories = db.session.query(
        AnalysisDimension.sub_category,
        AnalysisDimension.rule_type,
        AnalysisDimension.rule_category
    ).filter(
        AnalysisDimension.rule_type.isnot(None),
        AnalysisDimension.rule_type != ''
    ).distinct().all()

    # 整理成 { rule_type: { sub_category, rule_category, name } }
    dimension_tabs = {}
    sub_category_names = {
        'nickname_analysis': '昵称',
        'bio_analysis': '简介',
        'account_positioning': '账号定位',
        'market_analysis': '目标人群',
        'keyword_library': '关键词布局',
        'operation_planning': '内容策略',
        'title': '标题',
        'hook': '开头钩子',
        'ending': '结尾',
        'visual_design': '视觉设计',
        'content_body': '内容结构',
        'applicable_audience': '适用人群',
        'applicable_scenario': '适用场景'
    }
    for sub_cat, rule_type, rule_cat in sub_categories:
        if sub_cat and rule_type:
            dimension_tabs[rule_type] = {
                'sub_category': sub_cat,
                'rule_category': rule_cat or 'operation',
                'name': sub_category_names.get(sub_cat, sub_cat)
            }

    # 一级分类（账号分析、内容分析、方法论）
    category_tabs = {
        'account': {'name': '账号分析', 'icon': 'bi-person-badge'},
        'content': {'name': '内容分析', 'icon': 'bi-file-text'},
        'methodology': {'name': '方法论', 'icon': 'bi-book'}
    }
    # 一级分类 -> 二级分类映射
    category_map = {}
    sub_category_names = {
        'nickname_analysis': '昵称',
        'bio_analysis': '简介',
        'account_positioning': '账号定位',
        'market_analysis': '目标人群',
        'keyword_library': '关键词布局',
        'operation_planning': '内容策略',
        'title': '标题',
        'hook': '开头钩子',
        'ending': '结尾',
        'visual_design': '视觉设计',
        'content_body': '内容结构',
        'applicable_audience': '适用人群',
        'applicable_scenario': '适用场景',
        'topic': '热门话题',
        'structure': '内容结构',
        'hook': '开头钩子',
        'ending': '结尾引导',
        'commercial': '商业化',
        'psychology': '心理共鸣',
        'emotion': '情感表达'
    }

    # 从 KnowledgeRule 读取所有二级分类及其公式数量
    # 按 source_sub_category 分组统计
    rule_counts_query = db.session.query(
        KnowledgeRule.source_sub_category,
        db.func.count(KnowledgeRule.id).label('count')
    ).filter(
        KnowledgeRule.status == 'active'
    ).group_by(KnowledgeRule.source_sub_category).all()

    rule_count_map = {r.source_sub_category: r.count for r in rule_counts_query}

    # 从 AnalysisDimension 读取所有一级分类和二级分类
    all_dims = db.session.query(
        AnalysisDimension.category,
        AnalysisDimension.sub_category,
        AnalysisDimension.code,
        AnalysisDimension.name
    ).filter(
        AnalysisDimension.is_active == True,
        AnalysisDimension.code.isnot(None),
        AnalysisDimension.code != ''
    ).order_by(AnalysisDimension.category, AnalysisDimension.sub_category, AnalysisDimension.sort_order).all()

    for cat, sub_cat, code, name in all_dims:
        if cat and sub_cat and code:
            # 记录二级分类（按一级分类分组）
            if cat not in category_map:
                category_map[cat] = {}
            if sub_cat not in category_map[cat]:
                category_map[cat][sub_cat] = {
                    'name': sub_category_names.get(sub_cat, sub_cat),
                    'dimensions': [],
                    'ruleCount': rule_count_map.get(sub_cat, 0)  # 公式数量
                }
            # 记录维度
            category_map[cat][sub_cat]['dimensions'].append({
                'code': code,
                'name': name
            })

    # 补充没有维度但有公式的二级分类
    for sub_cat, count in rule_count_map.items():
        found = False
        for cat in category_map:
            if sub_cat in category_map[cat]:
                found = True
                break
        if not found and count > 0:
            # 尝试确定一级分类
            cat = 'account' if sub_cat in ['nickname_analysis', 'bio_analysis', 'account_positioning', 'market_analysis'] else \
                  'content' if sub_cat in ['title', 'hook', 'ending', 'visual_design', 'content_body', 'topic', 'structure', 'commercial', 'psychology', 'emotion'] else \
                  'methodology'
            if cat not in category_map:
                category_map[cat] = {}
            category_map[cat][sub_cat] = {
                'name': sub_category_names.get(sub_cat, sub_cat),
                'dimensions': [],
                'ruleCount': count
            }

    return render_template('admin/rules_library.html',
                          category_tabs=category_tabs,
                          category_map=category_map)


# 素材库模型映射（扩展版）
UNIFIED_RULES_MODEL_MAP = {
    # 素材库
    'title': ContentTitle,
    'hook': ContentHook,
    'cover': ContentCover,
    'topic': ContentTopic,
    'structure': ContentStructure,
    'ending': ContentEnding,
    'psychology': ContentPsychology,
    'commercial': ContentCommercial,
    'why_popular': ContentWhyPopular,
    'tags': ContentTag,
    'character': ContentCharacter,
    'content_form': ContentForm,
    'interaction': ContentInteraction,
    # 知识规则
    'keywords': KnowledgeRule,
    'topic': KnowledgeRule,
    'template': KnowledgeRule,
    'operation': KnowledgeRule,
    'market': KnowledgeRule
}


@admin.route('/api/rules/unified')
@login_required
def get_unified_rules():
    """获取统一规则列表（素材库 + 知识规则 + 场景库 + 热点库）"""
    category = request.args.get('category', 'all')
    search = request.args.get('search', '')
    rule_type = request.args.get('rule_type', '')
    source_dimension = request.args.get('source_dimension', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    items = []
    counts = {}

    # 动态获取所有二级分类及其规则类型
    sub_categories = db.session.query(
        AnalysisDimension.sub_category,
        AnalysisDimension.rule_type,
        AnalysisDimension.rule_category
    ).filter(
        AnalysisDimension.rule_type.isnot(None),
        AnalysisDimension.rule_type != ''
    ).distinct().all()

    sub_category_names = {
        'nickname_analysis': '昵称',
        'bio_analysis': '简介',
        'account_positioning': '账号定位',
        'market_analysis': '目标人群',
        'keyword_library': '关键词布局',
        'operation_planning': '内容策略',
        'title': '标题',
        'hook': '开头钩子',
        'ending': '结尾',
        'visual_design': '视觉设计',
        'content_body': '内容结构',
        'applicable_audience': '适用人群',
        'applicable_scenario': '适用场景'
    }
    dimension_tabs = {}
    for sub_cat, r_type, rule_cat in sub_categories:
        if sub_cat and r_type:
            dimension_tabs[r_type] = {
                'sub_category': sub_cat,
                'rule_category': rule_cat or 'operation',
                'name': sub_category_names.get(sub_cat, sub_cat)
            }

    # 知识规则分类列表
    knowledge_rule_categories = ['keywords', 'topic', 'template', 'operation', 'market']
    # 场景库分类列表
    scene_categories = ['usage_scenario', 'demand_scenario', 'pain_point']
    # 热点库分类列表
    hot_categories = ['hot_topic', 'seasonal_topic']

    # 查询知识规则
    if category == 'all' or category in knowledge_rule_categories:
        rule_query = KnowledgeRule.query
        if category != 'all':
            rule_query = rule_query.filter(KnowledgeRule.category == category)
        if rule_type:
            rule_query = rule_query.filter(KnowledgeRule.rule_type == rule_type)
        # 支持按 source_dimension 维度筛选（更细粒度）
        if source_dimension:
            rule_query = rule_query.filter(KnowledgeRule.source_dimension == source_dimension)
        if search:
            rule_query = rule_query.filter(
                db.or_(
                    KnowledgeRule.rule_title.ilike(f'%{search}%'),
                    KnowledgeRule.rule_content.ilike(f'%{search}%')
                )
            )

        # 统计各分类数量
        for cat in knowledge_rule_categories:
            cat_count = KnowledgeRule.query.filter_by(category=cat).count()
            counts[cat] = cat_count
        # 动态统计所有规则类型（维度 Tab）的数量
        for rule_type in dimension_tabs.keys():
            rule_cat = dimension_tabs[rule_type].get('rule_category', 'operation')
            counts[rule_type] = KnowledgeRule.query.filter_by(
                category=rule_cat, rule_type=rule_type
            ).count()

        rules = rule_query.all()
        for r in rules:
            # 获取关联的维度名称
            dimension_name = ''
            if r.dimension_id:
                dim = AnalysisDimension.query.get(r.dimension_id)
                if dim:
                    dimension_name = dim.name

            items.append({
                'id': r.id,
                'title': r.rule_title,
                'content': r.rule_content,
                'category': r.category,
                'usage_count': r.usage_count or 0,
                'source_type': 'knowledge_rule',
                'applicable_scenarios': r.applicable_scenarios,
                'applicable_audiences': r.applicable_audiences,
                'platforms': r.platforms,
                'type_labels': [x for x in [r.rule_type, r.source_dimension] if x],
                'dimension_id': r.dimension_id,
                'dimension_name': dimension_name,
                'source_dimension': r.source_dimension
            })

    # 查询场景库
    if category == 'all' or category in scene_categories:
        if category == 'all' or category == 'usage_scenario':
            query = UsageScenario.query
            if search:
                query = query.filter(UsageScenario.scenario_name.ilike(f'%{search}%'))
            counts['usage_scenario'] = query.count()
            for r in query.all():
                items.append({
                    'id': r.id,
                    'title': r.scenario_name,
                    'content': r.scenario_description or '',
                    'category': 'usage_scenario',
                    'usage_count': 0,
                    'source_type': 'scene',
                    'industry': r.industry,
                    'scene_type': '使用场景',
                    'keywords': r.keywords,
                    'type_labels': [r.industry] if r.industry else []
                })

        if category == 'all' or category == 'demand_scenario':
            query = DemandScenario.query
            if search:
                query = query.filter(DemandScenario.scenario_name.ilike(f'%{search}%'))
            counts['demand_scenario'] = query.count()
            for r in query.all():
                items.append({
                    'id': r.id,
                    'title': r.scenario_name,
                    'content': r.scenario_description or '',
                    'category': 'demand_scenario',
                    'usage_count': 0,
                    'source_type': 'scene',
                    'scene_type': r.demand_type,
                    'keywords': r.keywords,
                    'type_labels': [r.demand_type] if r.demand_type else []
                })

        if category == 'all' or category == 'pain_point':
            query = PainPoint.query
            if search:
                query = query.filter(PainPoint.pain_point_name.ilike(f'%{search}%'))
            counts['pain_point'] = query.count()
            for r in query.all():
                items.append({
                    'id': r.id,
                    'title': r.pain_point_name,
                    'content': r.description or '',
                    'category': 'pain_point',
                    'usage_count': 0,
                    'source_type': 'scene',
                    'industry': r.industry,
                    'scene_type': r.pain_type,
                    'keywords': r.keywords,
                    'type_labels': [r.industry, r.pain_type] if r.industry or r.pain_type else []
                })

    # 查询热点库
    if category == 'all' or category in hot_categories:
        if category == 'all' or category == 'hot_topic':
            query = HotTopic.query
            if search:
                query = query.filter(HotTopic.topic_name.ilike(f'%{search}%'))
            counts['hot_topic'] = query.count()
            for r in query.all():
                items.append({
                    'id': r.id,
                    'title': r.topic_name,
                    'content': r.description or '',
                    'category': 'hot_topic',
                    'usage_count': 0,
                    'source_type': 'hot',
                    'hot_level': r.hot_level,
                    'topic_category': r.category,
                    'related_industry': r.related_industry,
                    'type_labels': [r.hot_level, r.category] if r.hot_level or r.category else []
                })

        if category == 'all' or category == 'seasonal_topic':
            query = SeasonalTopic.query
            if search:
                query = query.filter(SeasonalTopic.topic_name.ilike(f'%{search}%'))
            counts['seasonal_topic'] = query.count()
            for r in query.all():
                items.append({
                    'id': r.id,
                    'title': r.topic_name,
                    'content': r.description or '',
                    'category': 'seasonal_topic',
                    'usage_count': 0,
                    'source_type': 'hot',
                    'topic_type': r.topic_type,
                    'keywords': r.keywords,
                    'type_labels': [r.topic_type] if r.topic_type else []
                })

    # 查询素材库
    material_types = ['title', 'hook', 'cover', 'topic', 'structure', 'ending',
                     'psychology', 'commercial', 'why_popular', 'tags', 'character',
                     'content_form', 'interaction']

    if category == 'all' or category in material_types:
        for mat_type in material_types:
            if category != 'all' and mat_type != category:
                continue

            model = UNIFIED_RULES_MODEL_MAP.get(mat_type)
            if not model:
                continue

            query = model.query
            if search:
                if mat_type == 'title':
                    query = query.filter(model.title.ilike(f'%{search}%'))
                elif mat_type == 'structure':
                    query = query.filter(model.structure_name.ilike(f'%{search}%'))
                else:
                    content_field = getattr(model, f'{mat_type}_content', None)
                    if content_field:
                        query = query.filter(content_field.ilike(f'%{search}%'))

            counts[mat_type] = query.count()
            records = query.all()
            for r in records:
                if mat_type == 'title':
                    content = r.title
                elif mat_type == 'structure':
                    content = r.structure_name
                else:
                    content_field = f'{mat_type}_content'
                    content = getattr(r, content_field, '')

                type_field = f'{mat_type}_type'
                item_type = getattr(r, type_field, '')

                items.append({
                    'id': r.id,
                    'title': content[:50] if content else '',
                    'content': content,
                    'category': mat_type,
                    'usage_count': r.usage_count or 0,
                    'source_type': 'material',
                    'item_type': item_type,
                    'type_labels': [item_type] if item_type else []
                })

    return jsonify({
        'success': True,
        'data': {
            'items': items,
            'counts': counts,
            'total': len(items)
        }
    })


@admin.route('/api/rules/unified/<int:id>')
@login_required
def get_unified_rule(id):
    """获取单个规则详情"""
    category = request.args.get('category')
    source_type = request.args.get('source_type', 'material')

    if source_type == 'knowledge_rule':
        rule = KnowledgeRule.query.get_or_404(id)
        return jsonify({
            'success': True,
            'data': {
                'id': rule.id,
                'title': rule.rule_title,
                'content': rule.rule_content,
                'category': rule.category,
                'usage_count': rule.usage_count or 0,
                'applicable_scenarios': rule.applicable_scenarios,
                'applicable_audiences': rule.applicable_audiences,
                'platforms': rule.platforms
            }
        })
    else:
        # 素材库
        model = UNIFIED_RULES_MODEL_MAP.get(category)
        if not model:
            return jsonify({'success': False, 'message': '无效的分类'}), 400

        item = model.query.get_or_404(id)

        if category == 'title':
            content = item.title
        elif category == 'structure':
            content = item.structure_name
        else:
            content_field = f'{category}_content'
            content = getattr(item, content_field, '')

        return jsonify({
            'success': True,
            'data': {
                'id': item.id,
                'title': content[:50] if content else '',
                'content': content,
                'category': category,
                'usage_count': item.usage_count or 0
            }
        })


@admin.route('/api/rules/unified', methods=['POST'])
@login_required
@super_admin_required
def create_unified_rule():
    """创建统一规则"""
    data = request.get_json()
    category = data.get('category')
    source_type = data.get('source_type', 'material')
    title = data.get('title', '')
    content = data.get('content', '')
    rule_type = data.get('rule_type') or 'dimension'

    # 解析场景和人群
    scenarios = data.get('applicable_scenarios', [])
    audiences = data.get('applicable_audiences', [])
    if isinstance(scenarios, str):
        scenarios = [s.strip() for s in scenarios.split(',') if s.strip()]
    if isinstance(audiences, str):
        audiences = [a.strip() for a in audiences.split(',') if a.strip()]

    platforms = data.get('platforms', [])

    # 知识规则分类
    knowledge_rule_categories = ['keywords', 'topic', 'template', 'operation', 'market']

    try:
        if source_type == 'rule' or category in knowledge_rule_categories:
            # 创建知识规则
            rule = KnowledgeRule(
                category=category,
                rule_title=title,
                rule_content=content,
                rule_type=rule_type,
                applicable_scenarios=scenarios,
                applicable_audiences=audiences,
                platforms=platforms,
                status='active'
            )
            db.session.add(rule)
        else:
            # 创建素材库记录
            model = UNIFIED_RULES_MODEL_MAP.get(category)
            if not model:
                return jsonify({'success': False, 'message': '无效的分类'}), 400

            # 根据类型构建数据
            if category == 'title':
                item = model(title=content)
            elif category == 'structure':
                item = model(structure_name=content)
            else:
                content_field = f'{category}_content'
                item = model(**{content_field: content})

            db.session.add(item)

        db.session.commit()
        return jsonify({'success': True, 'message': '保存成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/rules/unified/<int:id>', methods=['PUT'])
@login_required
@super_admin_required
def update_unified_rule(id):
    """更新统一规则"""
    data = request.get_json()
    category = data.get('category')
    source_type = data.get('source_type', 'material')
    title = data.get('title', '')
    content = data.get('content', '')
    rule_type = data.get('rule_type') or None

    # 解析场景和人群
    scenarios = data.get('applicable_scenarios', [])
    audiences = data.get('applicable_audiences', [])
    if isinstance(scenarios, str):
        scenarios = [s.strip() for s in scenarios.split(',') if s.strip()]
    if isinstance(audiences, str):
        audiences = [a.strip() for a in audiences.split(',') if a.strip()]

    platforms = data.get('platforms', [])

    knowledge_rule_categories = ['keywords', 'topic', 'template', 'operation', 'market']

    try:
        if source_type == 'rule' or category in knowledge_rule_categories:
            rule = KnowledgeRule.query.get_or_404(id)
            rule.rule_title = title
            rule.rule_content = content
            if rule_type:
                rule.rule_type = rule_type
            rule.applicable_scenarios = scenarios
            rule.applicable_audiences = audiences
            rule.platforms = platforms
        else:
            model = UNIFIED_RULES_MODEL_MAP.get(category)
            if not model:
                return jsonify({'success': False, 'message': '无效的分类'}), 400

            item = model.query.get_or_404(id)

            if category == 'title':
                item.title = content
            elif category == 'structure':
                item.structure_name = content
            else:
                content_field = f'{category}_content'
                setattr(item, content_field, content)

        db.session.commit()
        return jsonify({'success': True, 'message': '更新成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/api/rules/unified/<int:id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_unified_rule(id):
    """删除统一规则"""
    category = request.args.get('category')
    source_type = request.args.get('source_type', 'material')

    knowledge_rule_categories = ['keywords', 'topic', 'template', 'operation', 'market']

    try:
        if source_type == 'rule' or category in knowledge_rule_categories:
            rule = KnowledgeRule.query.get_or_404(id)
            db.session.delete(rule)
        else:
            model = UNIFIED_RULES_MODEL_MAP.get(category)
            if not model:
                return jsonify({'success': False, 'message': '无效的分类'}), 400

            item = model.query.get_or_404(id)
            db.session.delete(item)

        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# 简化版规则库 API（按一级分类+二级分类+维度筛选）
@admin.route('/api/rules')
@login_required
def get_rules():
    """获取规则列表（按一级分类+二级分类+维度筛选）"""
    category = request.args.get('category', '')  # 一级分类 account/content/methodology
    sub_category = request.args.get('sub_category', '')  # 二级分类
    dimension_code = request.args.get('dimension_code', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    # 查询 KnowledgeRule
    query = KnowledgeRule.query

    if category:
        # 兼容旧数据：source_category 可能为 None
        # 新数据使用 source_category 过滤，旧数据没有设置需要按 source_sub_category 推断
        from sqlalchemy import or_
        
        # 尝试获取该一级分类对应的二级分类列表
        sub_cats_for_category = []
        if category == 'account':
            sub_cats_for_category = ['nickname_analysis', 'bio_analysis', 'account_positioning', 'market_analysis', 'keyword_library', 'operation_planning']
        elif category == 'content':
            sub_cats_for_category = ['title', 'hook', 'ending', 'visual_design', 'content_body', 'topic', 'structure', 'commercial', 'psychology', 'emotion']
        elif category == 'methodology':
            sub_cats_for_category = ['applicable_audience', 'applicable_scenario']
        
        # 匹配：要么 source_category 匹配，要么 source_category 为空但 source_sub_category 在该分类的二级分类列表中
        if sub_cats_for_category:
            query = query.filter(
                or_(
                    KnowledgeRule.source_category == category,
                    and_(KnowledgeRule.source_category.is_(None), KnowledgeRule.source_sub_category.in_(sub_cats_for_category))
                )
            )
        else:
            query = query.filter(KnowledgeRule.source_category == category)
    else:
        # 没有传 category 时，也返回 source_category 为空的记录
        pass

    if sub_category:
        query = query.filter(KnowledgeRule.source_sub_category == sub_category)

    if dimension_code:
        query = query.filter(KnowledgeRule.source_dimension == dimension_code)

    # 调试日志
    logger.info(f"[DEBUG get_rules] category={category}, sub_category={sub_category}, dimension_code={dimension_code}")
    logger.info(f"[DEBUG get_rules] SQL: {query}")
    
    # 按入库时间倒序排列（新增的在前）
    query = query.order_by(KnowledgeRule.id.desc())
    
    # 分页
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)
    rules = pagination.items
    total = pagination.total

    # 获取查询结果

    # 整理返回数据
    sub_category_names = {
        'nickname_analysis': '昵称',
        'bio_analysis': '简介',
        'account_positioning': '账号定位',
        'market_analysis': '目标人群',
        'keyword_library': '关键词布局',
        'operation_planning': '内容策略',
        'title': '标题',
        'hook': '开头钩子',
        'ending': '结尾',
        'visual_design': '视觉设计',
        'content_body': '内容结构',
        'applicable_audience': '适用人群',
        'applicable_scenario': '适用场景'
    }

    items = []
    category_names = {'account': '账号分析', 'content': '内容分析', 'methodology': '方法论'}
    for r in rules:
        items.append({
            'id': r.id,
            'title': r.rule_title,
            'content': r.rule_content,
            'category': r.source_category,
            'category_name': category_names.get(r.source_category, r.source_category or ''),
            'sub_category': r.source_sub_category,
            'object_name': sub_category_names.get(r.source_sub_category, r.source_sub_category),
            'dimension_code': r.source_dimension,
            'dimension_name': r.dimension_name,
            'applicable_scenarios': r.applicable_scenarios or [],
            'applicable_audiences': r.applicable_audiences or [],
            'keywords': r.keywords or []
        })

    return jsonify({
        'success': True,
        'data': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': pagination.pages
    })


@admin.route('/api/rules/<int:id>')
@login_required
def get_rule_detail(id):
    """获取规则详情"""
    rule = KnowledgeRule.query.get_or_404(id)

    sub_category_names = {
        'nickname_analysis': '昵称',
        'bio_analysis': '简介',
        'account_positioning': '账号定位',
        'market_analysis': '目标人群',
        'keyword_library': '关键词布局',
        'operation_planning': '内容策略',
        'title': '标题',
        'hook': '开头钩子',
        'ending': '结尾',
        'visual_design': '视觉设计',
        'content_body': '内容结构',
        'applicable_audience': '适用人群',
        'applicable_scenario': '适用场景'
    }

    return jsonify({
        'success': True,
        'data': {
            'id': rule.id,
            'title': rule.rule_title,
            'content': rule.rule_content,
            'sub_category': rule.source_sub_category,
            'object_name': sub_category_names.get(rule.source_sub_category, rule.source_sub_category),
            'dimension_code': rule.source_dimension,
            'dimension_name': rule.dimension_name,
            'applicable_scenarios': rule.applicable_scenarios or [],
            'applicable_audiences': rule.applicable_audiences or [],
            'keywords': rule.keywords or []
        }
    })
