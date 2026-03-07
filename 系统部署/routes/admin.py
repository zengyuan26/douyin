"""
管理员路由 - 专家管理、知识库管理、渠道管理、行业管理
"""
import os
import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models.models import db, User, Expert, Skill, KnowledgeCategory, KnowledgeArticle, KnowledgeAnalysis, KnowledgeRule, Industry, Channel, Client
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
    """超级管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            # 对 Ajax / API 请求返回 JSON，避免前端 fetch 被 302 + HTML 吃掉
            wants_json = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or request.is_json
                or 'application/json' in (request.headers.get('Accept') or '')
            )
            if wants_json:
                return jsonify({'code': 403, 'message': '需要超级管理员权限', 'success': False}), 403

            flash('需要超级管理员权限', 'danger')
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
    channel_count = Channel.query.count()
    industry_count = Industry.query.count()
    article_count = KnowledgeArticle.query.count()
    
    # 最近添加的客户
    recent_clients = Client.query.order_by(Client.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html',
                         now=datetime.now(),
                         user_count=user_count,
                         expert_count=expert_count,
                         client_count=client_count,
                         channel_count=channel_count,
                         industry_count=industry_count,
                         article_count=article_count,
                         recent_clients=recent_clients)


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


@admin.route('/knowledge/ebook')
@login_required
@super_admin_required
def knowledge_ebook():
    """电子书分析页面"""
    return render_template('admin/knowledge_ebook.html')


@admin.route('/knowledge/account/analyze')
@login_required
@super_admin_required
def knowledge_account_analysis():
    """账号分析页面"""
    return render_template('admin/knowledge_account_analysis.html')


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


# ==================== 渠道管理 ====================

@admin.route('/channels')
@login_required
@super_admin_required
def channels():
    """渠道列表"""
    channels_list = Channel.query.order_by(Channel.created_at.desc()).all()
    return render_template('admin/channels.html', channels=channels_list)


@admin.route('/channels/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def channel_add():
    """添加渠道"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        channel_name = request.form.get('channel_name')
        company = request.form.get('company')
        contact = request.form.get('contact')
        description = request.form.get('description')
        
        # 检查用户名和邮箱
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return redirect(url_for('admin.channel_add'))
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'danger')
            return redirect(url_for('admin.channel_add'))
        
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt()
        
        # 创建渠道用户
        user = User(
            username=username,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            role='channel',
            is_active=True
        )
        db.session.add(user)
        db.session.flush()
        
        # 创建渠道
        channel = Channel(
            user_id=user.id,
            name=channel_name,
            company=company,
            contact=contact,
            description=description
        )
        db.session.add(channel)
        db.session.flush()
        
        # 默认只分配总控专家
        master_expert = Expert.query.filter_by(slug='master').first()
        if master_expert:
            channel.experts.append(master_expert)
        
        db.session.commit()
        
        flash('渠道添加成功', 'success')
        return redirect(url_for('admin.channels'))
    
    return render_template('admin/channel_form.html', channel=None)


@admin.route('/channels/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def channel_edit(id):
    """编辑渠道"""
    channel = Channel.query.get_or_404(id)
    user = channel.owner
    
    if request.method == 'POST':
        channel.name = request.form.get('channel_name')
        channel.company = request.form.get('company')
        channel.contact = request.form.get('contact')
        channel.description = request.form.get('description')
        channel.is_active = request.form.get('is_active') == 'on'
        
        # 如果提供了新密码，则更新密码
        new_password = request.form.get('password')
        if new_password:
            from flask_bcrypt import Bcrypt
            bcrypt = Bcrypt()
            user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        db.session.commit()
        flash('渠道更新成功', 'success')
        return redirect(url_for('admin.channels'))
    
    return render_template('admin/channel_form.html', channel=channel)


@admin.route('/channels/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def channel_delete(id):
    """删除渠道"""
    channel = Channel.query.get_or_404(id)
    
    # 删除渠道下的所有客户
    for client in channel.clients.all():
        db.session.delete(client)
    
    # 删除用户
    user = channel.owner
    db.session.delete(channel)
    db.session.delete(user)
    db.session.commit()
    
    flash('渠道删除成功', 'success')
    return redirect(url_for('admin.channels'))


@admin.route('/channels/<int:id>/toggle')
@login_required
@super_admin_required
def toggle_channel(id):
    """切换渠道状态"""
    channel = Channel.query.get_or_404(id)
    channel.is_active = not channel.is_active
    # 同时切换用户账号状态
    if channel.user:
        channel.user.is_active = channel.is_active
    db.session.commit()
    flash(f'渠道已{"启用" if channel.is_active else "禁用"}', 'success')
    return redirect(url_for('admin.channels'))


@admin.route('/channels/<int:id>/approve', methods=['POST'])
@login_required
@super_admin_required
def approve_channel(id):
    """审核通过渠道"""
    channel = Channel.query.get_or_404(id)
    channel.is_active = True
    # 同时激活关联的用户账号
    if channel.user:
        channel.user.is_active = True
    db.session.commit()
    flash(f'渠道 "{channel.name}" 已通过审核', 'success')
    return redirect(url_for('admin.channels'))


@admin.route('/users/<int:id>/activate', methods=['POST'])
@login_required
@super_admin_required
def activate_user(id):
    """手动激活用户"""
    user = User.query.get_or_404(id)
    user.is_active = True
    db.session.commit()
    flash(f'用户 "{user.username}" 已激活', 'success')
    return redirect(request.referrer or url_for('admin.dashboard'))


@admin.route('/channels/<int:id>/reject', methods=['POST'])
@login_required
@super_admin_required
def reject_channel(id):
    """拒绝渠道申请"""
    channel = Channel.query.get_or_404(id)
    channel.is_active = False
    # 同时停用关联的用户账号
    if channel.user:
        channel.user.is_active = False
    db.session.commit()
    flash(f'渠道 "{channel.name}" 已拒绝', 'warning')
    return redirect(url_for('admin.channels'))


@admin.route('/channels/<int:id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def channel_reset_password(id):
    """重置渠道账号密码"""
    channel = Channel.query.get_or_404(id)
    user = channel.owner
    
    # 重置密码为默认密码
    from flask_bcrypt import Bcrypt
    bcrypt = Bcrypt()
    user.password_hash = bcrypt.generate_password_hash('aaa111').decode('utf-8')
    db.session.commit()
    
    flash(f'密码已重置为: aaa111', 'success')
    return redirect(url_for('admin.channels'))


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
    channels = Channel.query.all()
    industries = Industry.query.all()

    # 为每个客户添加录入者信息
    for client in clients_list:
        if client.creator:
            if client.creator.role == 'super_admin':
                client.creator_name = '管理员'
            elif client.channel:
                client.creator_name = client.channel.name
            else:
                client.creator_name = client.creator.username
        else:
            client.creator_name = '管理员'

    return render_template('admin/clients.html', clients=clients_list, channels=channels, industries=industries, pagination=pagination)


@admin.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def client_edit(id):
    """编辑客户"""
    client = Client.query.get_or_404(id)
    channels = Channel.query.all()
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
    
    return render_template('admin/client_form.html', client=client, channels=channels, industries=industries)


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
    channels = Channel.query.all()
    industries = Industry.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        channel_id = request.form.get('channel_id')
        industry_id = request.form.get('industry_id')
        business_type = request.form.get('business_type')
        contact = request.form.get('contact')
        description = request.form.get('description')
        
        # 获取渠道
        channel = Channel.query.get(channel_id)
        if not channel:
            flash('请选择所属渠道', 'warning')
            return redirect(url_for('admin.client_add'))
        
        # 获取渠道对应的用户
        user_id = channel.user_id
        
        client = Client(
            channel_id=channel_id,
            user_id=user_id,
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
    
    return render_template('admin/client_form.html', client=None, channels=channels, industries=industries)


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
