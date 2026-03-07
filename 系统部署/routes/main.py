"""
主路由 - 用户首页、客户管理
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from flask_bcrypt import Bcrypt
from models.models import db, User, Expert, Client, Channel, Keyword, Topic, Content, Monitor, Industry
from datetime import datetime
import json

bcrypt = Bcrypt()

main = Blueprint('main', __name__)


@main.route('/')
def index():
    """首页 - 根据角色跳转"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    # 统一跳转到工作台
    return redirect(url_for('main.workspace'))


@main.route('/dashboard')
@login_required
def user_dashboard():
    """用户工作台 - 旧版"""
    if current_user.role == 'super_admin':
        return redirect(url_for('admin.dashboard'))
    
    # 获取当前用户的客户列表
    if current_user.role == 'channel':
        clients = Client.query.filter_by(channel_id=current_user.channels.first().id).all() if current_user.channels.first() else []
    else:
        clients = Client.query.filter_by(user_id=current_user.id).all()
    
    # 统计数据
    client_count = len(clients)
    keyword_count = sum([c.keywords.count() for c in clients])
    topic_count = sum([c.topics.count() for c in clients])
    content_count = sum([c.contents.count() for c in clients])
    
    return render_template('user/dashboard.html',
                         now=datetime.now(),
                         clients=clients,
                         client_count=client_count,
                         keyword_count=keyword_count,
                         topic_count=topic_count,
                         content_count=content_count)


@main.route('/workspace')
@login_required
def workspace():
    """工作台 - Cursor风格三栏布局"""
    # 获取当前用户的客户列表（按名称排序）
    # 超级管理员可以看到所有客户，渠道商只能看到自己渠道的客户
    if current_user.is_super_admin():
        clients = Client.query.order_by(Client.name).all()
    elif current_user.role == 'channel':
        channel = current_user.channels.first()
        clients = Client.query.filter_by(channel_id=channel.id).order_by(Client.name).all() if channel else []

        # 渠道用户：检查 session 中的当前客户是否属于该渠道
        current_client_id = session.get('current_client_id')
        if current_client_id:
            client = Client.query.get(current_client_id)
            if not client or (channel and client.channel_id != channel.id):
                # session 中的客户不属于该渠道，清空 session
                session.pop('current_client_id', None)
                session.pop('current_client_name', None)
                current_client_id = None
    else:
        clients = Client.query.filter_by(user_id=current_user.id).order_by(Client.name).all()
    
    # 获取当前客户状态
    current_client_id = session.get('current_client_id')
    current_client_status = None
    if current_client_id:
        current_client = Client.query.get(current_client_id)
        if current_client:
            current_client_status = current_client.status
    
    # 获取专家列表 - 根据客户状态决定显示哪些专家
    # 规则：
    # - 超级管理员：始终显示所有专家（方便管理）
    # - 有有效客户时（completed/servicing）：显示所有专家
    # - 没有有效客户且非超级管理员：只显示首席营销官
    
    # 判断是否有有效客户
    has_valid_client = False
    if current_client_id and current_client_status in ['completed', 'servicing']:
        has_valid_client = True
    
    # 超级管理员始终显示所有专家，非超级管理员根据客户状态决定
    is_super_admin = current_user.is_super_admin()
    
    if has_valid_client or is_super_admin or not clients:
        # 有有效客户、超级管理员、或没有任何客户时，显示所有专家
        experts = Expert.query.filter_by(is_visible=True).order_by(Expert.sort_order).all()
        experts.sort(key=lambda x: 0 if x.slug == 'master' else 1)
    else:
        # 没有有效客户，只显示首席营销官
        experts = Expert.query.filter_by(slug='master', is_visible=True).all()
    
    # 默认选择总控专家
    default_expert = Expert.query.filter_by(slug='master', is_visible=True).first()
    
    # 超级管理员额外统计
    stats = {}
    if current_user.is_super_admin():
        stats = {
            'total_clients': Client.query.count(),
            'total_channels': Channel.query.count(),
            'total_experts': Expert.query.count(),
            'total_industries': Industry.query.count()
        }
    
    return render_template('user/workspace.html',
                         clients=clients,
                         experts=experts,
                         default_expert=default_expert,
                         stats=stats,
                         user_role=current_user.role,
                         current_user=current_user,
                         current_client_id=session.get('current_client_id'),
                         current_client_name=session.get('current_client_name'),
                         current_client_status=current_client_status)


# ==================== 客户管理（渠道） ====================

@main.route('/clients')
@login_required
def clients():
    """客户列表"""
    if current_user.role == 'super_admin':
        return redirect(url_for('admin.clients'))
    
    # 获取当前用户的渠道
    channel = Channel.query.filter_by(user_id=current_user.id).first()
    if not channel:
        flash('您还没有渠道信息', 'warning')
        return redirect(url_for('main.user_dashboard'))
    
    # 获取该渠道的所有客户
    clients_list = Client.query.filter_by(channel_id=channel.id).all()
    industries = Industry.query.all()
    
    # 获取当前选择的客户ID
    selected_client_id = session.get('current_client_id')
    
    return render_template('user/clients.html', 
                         clients=clients_list, 
                         industries=industries,
                         selected_client_id=selected_client_id)


@main.route('/clients/add', methods=['GET', 'POST'])
@login_required
def client_add():
    """添加客户（超级管理员和渠道都可以添加客户）"""
    # 超级管理员使用独立的管理员页面添加
    if current_user.role == 'super_admin':
        return redirect(url_for('admin.client_add'))
    
    channel = Channel.query.filter_by(user_id=current_user.id).first()
    if not channel:
        flash('您还没有渠道信息', 'warning')
        return redirect(url_for('main.user_dashboard'))
    
    industries = Industry.query.all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        industry = request.form.get('industry')
        business_type = request.form.get('business_type')
        contact = request.form.get('contact')
        description = request.form.get('description')
        industry_id = request.form.get('industry_id')
        
        client = Client(
            channel_id=channel.id,
            user_id=current_user.id,
            name=name,
            industry=industry,
            business_type=business_type,
            contact=contact,
            description=description,
            industry_id=industry_id if industry_id else None,
            is_active=True
        )
        db.session.add(client)
        db.session.commit()
        
        flash(f'客户 {name} 添加成功', 'success')
        return redirect(url_for('main.clients'))
    
    return render_template('user/client_form.html', client=None, industries=industries)


@main.route('/api/clients/add', methods=['POST'])
@login_required
def api_client_add():
    """API: AJAX 添加客户"""
    from flask import jsonify
    
    data = request.get_json()
    name = data.get('name')
    industry_id = data.get('industry_id')
    
    if not name:
        return jsonify({'success': False, 'message': '请输入客户名称'})
    
    # 获取渠道
    if current_user.role == 'channel':
        channel = current_user.channels.first()
    else:
        # 超级管理员
        channel = None
        # 如果是超级管理员，需要检查是否有渠道
        if not channel:
            # 创建默认渠道
            channel = Channel.query.first()
    
    if not channel:
        return jsonify({'success': False, 'message': '没有渠道信息'})
    
    # 创建客户
    client = Client(
        channel_id=channel.id,
        user_id=current_user.id,
        name=name,
        industry_id=industry_id if industry_id else None,
        is_active=True
    )
    db.session.add(client)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '客户添加成功',
        'client_id': client.id,
        'client': {'id': client.id, 'name': client.name}
    })


@main.route('/api/industries')
@login_required
def api_industries():
    """API: 获取行业列表"""
    from flask import jsonify
    
    industries = Industry.query.all()
    return jsonify([
        {'id': i.id, 'name': i.name} 
        for i in industries
    ])


@main.route('/api/user/profile', methods=['POST'])
@login_required
def api_user_profile():
    """API: 更新用户资料"""
    from flask import jsonify
    
    data = request.get_json()
    nickname = data.get('nickname')
    gender = data.get('gender')
    phone = data.get('phone')
    email = data.get('email')
    
    current_user.nickname = nickname
    current_user.gender = gender
    current_user.phone = phone if phone else None
    current_user.email = email if email else None
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '资料已更新'
    })


@main.route('/api/profile', methods=['POST'])
@login_required
def api_profile():
    """API: 更新个人资料"""
    from flask import jsonify
    
    data = request.get_json()
    nickname = data.get('nickname', '').strip()
    gender = data.get('gender', '')
    
    current_user.nickname = nickname if nickname else None
    current_user.gender = gender if gender else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '保存成功'
    })


@main.route('/api/user/change-password', methods=['POST'])
@login_required
def api_change_password():
    """API: 修改密码"""
    from flask import jsonify
    from models.models import User
    
    data = request.get_json()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    
    if not current_password:
        return jsonify({'success': False, 'message': '请输入当前密码'})
    
    if not new_password:
        return jsonify({'success': False, 'message': '请输入新密码'})
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'message': '密码长度至少6位'})
    
    # 验证当前密码
    if not bcrypt.check_password_hash(current_user.password_hash, current_password):
        return jsonify({'success': False, 'message': '当前密码错误'})
    
    # 更新密码
    current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '密码修改成功'
    })


@main.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def client_edit(id):
    """编辑客户"""
    client = Client.query.get_or_404(id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限编辑此客户', 'danger')
            return redirect(url_for('main.clients'))
    
    industries = Industry.query.all()
    
    if request.method == 'POST':
        client.name = request.form.get('name')
        client.business_type = request.form.get('business_type')
        client.contact = request.form.get('contact')
        client.description = request.form.get('description')
        client.industry_id = request.form.get('industry_id')
        
        db.session.commit()
        flash('客户更新成功', 'success')
        
        if current_user.role == 'super_admin':
            return redirect(url_for('admin.clients'))
        return redirect(url_for('main.clients'))
    
    return render_template('user/client_form.html', client=client, industries=industries)


@main.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def client_delete(id):
    """删除客户"""
    client = Client.query.get_or_404(id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限删除此客户', 'danger')
            return redirect(url_for('main.clients'))
    
    db.session.delete(client)
    db.session.commit()
    flash('客户删除成功', 'success')
    
    if current_user.role == 'super_admin':
        return redirect(url_for('admin.clients'))
    return redirect(url_for('main.clients'))


@main.route('/clients/<int:id>/select')
@login_required
def client_select(id):
    """选择当前客户"""
    client = Client.query.get_or_404(id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限选择此客户', 'danger')
            return redirect(url_for('main.clients'))
    
    # 设置当前客户
    session['current_client_id'] = client.id
    session['current_client_name'] = client.name
    
    flash(f'当前客户已切换为: {client.name}', 'success')
    return redirect(url_for('main.client_detail', id=id))


@main.route('/clients/<int:id>')
@login_required
def client_detail(id):
    """客户详情"""
    client = Client.query.get_or_404(id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限查看此客户', 'danger')
            return redirect(url_for('main.clients'))
    
    keywords = client.keywords.all()
    topics = client.topics.all()
    contents = client.contents.all()
    monitors = client.monitors.all()
    
    return render_template('user/client_detail.html',
                         client=client,
                         keywords=keywords,
                         topics=topics,
                         contents=contents,
                         monitors=monitors,
                         industries=Industry.query.order_by(Industry.sort_order).all(),
                         hide_client_switcher=True)


# ==================== 关键词管理 ====================

@main.route('/clients/<int:client_id>/keywords/add', methods=['GET', 'POST'])
@login_required
def keyword_add(client_id):
    """添加关键词"""
    client = Client.query.get_or_404(client_id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    if request.method == 'POST':
        keyword = request.form.get('keyword')
        keyword_type = request.form.get('keyword_type')
        search_intent = request.form.get('search_intent')
        competition = request.form.get('competition')
        
        kw = Keyword(
            client_id=client_id,
            keyword=keyword,
            keyword_type=keyword_type,
            search_intent=search_intent,
            competition=competition
        )
        db.session.add(kw)
        db.session.commit()
        
        flash('关键词添加成功', 'success')
        return redirect(url_for('main.client_detail', id=client_id))
    
    return render_template('user/keyword_form.html', client_id=client_id, keyword=None)


@main.route('/keywords/<int:id>/delete', methods=['POST'])
@login_required
def keyword_delete(id):
    """删除关键词"""
    keyword = Keyword.query.get_or_404(id)
    client_id = keyword.client_id
    
    # 权限检查
    client = keyword.client
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    db.session.delete(keyword)
    db.session.commit()
    flash('关键词删除成功', 'success')
    return redirect(url_for('main.client_detail', id=client_id))


# ==================== 选题管理 ====================

@main.route('/clients/<int:client_id>/topics/add', methods=['GET', 'POST'])
@login_required
def topic_add(client_id):
    """添加选题"""
    client = Client.query.get_or_404(client_id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        topic_type = request.form.get('topic_type')
        content_format = request.form.get('content_format')
        target_audience = request.form.get('target_audience')
        priority = request.form.get('priority')
        
        topic = Topic(
            client_id=client_id,
            title=title,
            topic_type=topic_type,
            content_format=content_format,
            target_audience=target_audience,
            priority=int(priority) if priority else 0
        )
        db.session.add(topic)
        db.session.commit()
        
        flash('选题添加成功', 'success')
        return redirect(url_for('main.client_detail', id=client_id))
    
    return render_template('user/topic_form.html', client_id=client_id, topic=None)


@main.route('/topics/<int:id>/delete', methods=['POST'])
@login_required
def topic_delete(id):
    """删除选题"""
    topic = Topic.query.get_or_404(id)
    client_id = topic.client_id
    
    # 权限检查
    client = topic.client
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    db.session.delete(topic)
    db.session.commit()
    flash('选题删除成功', 'success')
    return redirect(url_for('main.client_detail', id=client_id))


# ==================== 舆情监控 ====================

@main.route('/clients/<int:client_id>/monitors/add', methods=['GET', 'POST'])
@login_required
def monitor_add(client_id):
    """添加监控"""
    client = Client.query.get_or_404(client_id)
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    if request.method == 'POST':
        monitor_type = request.form.get('monitor_type')
        link_type = request.form.get('link_type')
        value = request.form.get('value')
        theme = request.form.get('theme')
        
        monitor = Monitor(
            client_id=client_id,
            monitor_type=monitor_type,
            link_type=link_type,
            value=value,
            theme=theme,
            status='monitoring'
        )
        db.session.add(monitor)
        db.session.commit()
        
        flash('监控添加成功', 'success')
        return redirect(url_for('main.client_detail', id=client_id))
    
    return render_template('user/monitor_form.html', client_id=client_id, monitor=None)


@main.route('/monitors/<int:id>/delete', methods=['POST'])
@login_required
def monitor_delete(id):
    """删除监控"""
    monitor = Monitor.query.get_or_404(id)
    client_id = monitor.client_id
    
    # 权限检查
    client = monitor.client
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            flash('您没有权限', 'danger')
            return redirect(url_for('main.clients'))
    
    db.session.delete(monitor)
    db.session.commit()
    flash('监控删除成功', 'success')
    return redirect(url_for('main.client_detail', id=client_id))


# ==================== 专家系统入口 ====================

@main.route('/experts')
@login_required
def experts():
    """专家系统入口 - 重定向到工作台"""
    return redirect(url_for('main.workspace'))


@main.route('/experts/<slug>')
@login_required
def expert_detail(slug):
    """专家详情"""
    expert = Expert.query.filter_by(slug=slug).first_or_404()
    
    # 获取当前客户
    current_client_id = session.get('current_client_id')
    current_client = None
    if current_client_id:
        current_client = Client.query.get(current_client_id)
    
    return render_template('user/expert.html',
                         expert=expert,
                         current_client=current_client)
