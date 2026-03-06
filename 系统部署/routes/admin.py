"""
管理员路由 - 专家管理、知识库管理、渠道管理、行业管理
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models.models import db, User, Expert, Skill, KnowledgeCategory, KnowledgeArticle, Industry, Channel, Client
from functools import wraps
from datetime import datetime

admin = Blueprint('admin', __name__)


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


# ==================== 专家管理 ====================

@admin.route('/experts')
@login_required
@super_admin_required
def experts():
    """专家列表"""
    experts_list = Expert.query.all()
    return render_template('admin/experts.html', experts=experts_list)


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
    """编辑专家"""
    expert = Expert.query.get_or_404(id)
    
    if request.method == 'POST':
        # 保留原 name，更新其他字段
        expert.nickname = request.form.get('nickname', '').strip()
        expert.title = request.form.get('title', '').strip()
        expert.description = request.form.get('description', '').strip()
        expert.command = request.form.get('command', '').strip()
        # icon、avatar_url 由 init_db 等脚本维护，编辑页不再提供修改入口
        expert.sort_order = int(request.form.get('sort_order', 0) or 0)
        expert.is_active = 'is_active' in request.form
        db.session.commit()
        flash('专家更新成功', 'success')
        return redirect(url_for('admin.experts'))
    
    # GET 请求时返回专家列表页面
    experts = Expert.query.all()
    return render_template('admin/experts.html', experts=experts)


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
    categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()
    return render_template('admin/knowledge.html', categories=categories)


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
    articles = KnowledgeArticle.query.order_by(KnowledgeArticle.created_at.desc()).all()
    return render_template('admin/knowledge_articles.html', articles=articles)


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


