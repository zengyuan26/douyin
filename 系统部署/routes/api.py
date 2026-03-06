"""
API路由 - 数据接口
"""
import json
import re
from urllib.parse import quote
from flask import Blueprint, jsonify, request, session, Response, stream_with_context
from flask_login import login_required, current_user
from models.models import db, Client, Channel, Keyword, Topic, Monitor, Expert, ChatSession, ChatMessage, Industry, ExpertOutput
from datetime import datetime, timedelta

api = Blueprint('api', __name__)


def _sanitize_filename(name):
    """文件名安全化：移除或替换非法字符"""
    if not name:
        return '报告'
    s = re.sub(r'[\\/:*?"<>|]', '_', str(name).strip())
    return s[:100] if len(s) > 100 else s or '报告'


@api.route('/industries', methods=['GET'])
@login_required
def get_industries():
    """获取行业列表"""
    industries = Industry.query.order_by(Industry.sort_order, Industry.name).all()
    data = [{'id': i.id, 'name': i.name} for i in industries]
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/current_client', methods=['GET'])
@login_required
def get_current_client():
    """获取当前客户"""
    current_client_id = session.get('current_client_id')
    if not current_client_id:
        return jsonify({'code': 404, 'message': '未选择客户', 'data': None})
    
    client = Client.query.get(current_client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在', 'data': None})
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'id': client.id,
            'name': client.name,
            'industry': client.industry.name if client.industry else '',
            'business_type': client.business_type
        }
    })


@api.route('/switch_client/<int:client_id>', methods=['POST'])
@login_required
def switch_client(client_id):
    """切换当前客户"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    # 权限检查
    if current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel or client.channel_id != channel.id:
            return jsonify({'code': 403, 'message': '没有权限'})
    elif current_user.role != 'super_admin' and client.user_id != current_user.id:
        return jsonify({'code': 403, 'message': '没有权限'})
    
    session['current_client_id'] = client.id
    session['current_client_name'] = client.name
    
    return jsonify({
        'code': 200,
        'message': f'已切换到客户: {client.name}',
        'data': {
            'id': client.id,
            'name': client.name
        }
    })


@api.route('/clients', methods=['GET'])
@login_required
def get_clients():
    """获取客户列表"""
    if current_user.role == 'super_admin':
        clients = Client.query.all()
    elif current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel:
            return jsonify({'code': 404, 'message': '渠道不存在', 'data': []})
        clients = Client.query.filter_by(channel_id=channel.id).all()
    else:
        # 普通用户只能看到自己录入的客户
        clients = Client.query.filter_by(user_id=current_user.id).all()
    
    data = []
    for c in clients:
        # 获取渠道名称
        if c.channel:
            channel_name = c.channel.name
        elif c.creator and c.creator.role == 'super_admin':
            channel_name = '管理员'
        else:
            channel_name = ''
        
        data.append({
            'id': c.id,
            'name': c.name,
            'industry': c.industry.name if c.industry else '',
            'business_type': c.business_type,
            'is_active': c.is_active,
            'channel_name': channel_name,
            'created_by': c.creator.username if c.creator else '管理员',
            'keyword_count': c.keywords.count() if c.keywords else 0,
            'monitor_count': c.monitors.count() if c.monitors else 0,
            'topic_count': c.topics.count() if c.topics else 0,
            'content_count': c.contents.count() if c.contents else 0
        })
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/clients/list', methods=['GET'])
@login_required
def get_clients_list():
    """获取客户列表（分页），用于工作台「查看全部」弹窗，与管理中心客户列表字段一致"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 50:
        per_page = 10

    if current_user.role == 'super_admin':
        q = Client.query
    elif current_user.role == 'channel':
        channel = Channel.query.filter_by(user_id=current_user.id).first()
        if not channel:
            return jsonify({'code': 404, 'message': '渠道不存在', 'data': {'items': [], 'total': 0, 'page': 1, 'per_page': per_page, 'pages': 0}})
        q = Client.query.filter_by(channel_id=channel.id)
    else:
        q = Client.query.filter_by(user_id=current_user.id)

    q = q.order_by(Client.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for c in pagination.items:
        if c.creator:
            if c.creator.role == 'super_admin':
                creator_name = '管理员'
            elif c.channel:
                creator_name = c.channel.name
            else:
                creator_name = c.creator.username
        else:
            creator_name = '管理员'
        items.append({
            'id': c.id,
            'name': c.name,
            'channel_name': creator_name,
            'industry_name': c.industry.name if c.industry else '',
            'business_type': c.business_type or '-',
            'created_at': c.created_at.strftime('%Y-%m-%d') if c.created_at else '-',
            'is_active': getattr(c, 'is_active', True)
        })
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'items': items,
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages
        }
    })


@api.route('/clients/<int:client_id>', methods=['GET'])
@login_required
def get_client(client_id):
    """获取单个客户信息"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    # 检查权限
    if current_user.role not in ['super_admin', 'channel'] and client.user_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权限'})
    
    data = {
        'id': client.id,
        'name': client.name,
        'industry': client.industry.name if client.industry else '',
        'contact': client.contact,
        'description': client.description,
        'business_type': client.business_type,
        'product_type': client.product_type,
        'service_type': client.service_type,
        'service_range': client.service_range,
        'target_area': client.target_area,
        'brand_type': client.brand_type,
        'brand_description': client.brand_description,
        'language_style': client.language_style,
        'dialect': client.dialect,
        # 录入表单扩展字段，供编辑弹框回填使用
        'main_product': client.main_product,
        'business_years': client.business_years,
        'other_info': client.other_info,
        'core_advantage': client.core_advantage,
        'project_goals': client.project_goals,
        'status': client.status,
        'is_active': client.is_active,
        'created_at': client.created_at.isoformat() if client.created_at else None
    }
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/clients/<int:client_id>', methods=['PUT'])
@login_required
def update_client(client_id):
    """更新客户信息"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    # 检查权限
    if current_user.role not in ['super_admin', 'channel'] and client.user_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权限'})
    
    data = request.get_json()
    
    # 更新字段
    if 'name' in data:
        client.name = data['name']
    if 'industry' in data:
        # industry 是字符串，需要查询对应的 Industry 对象
        from models.models import Industry
        if data['industry']:
            industry = Industry.query.filter_by(name=data['industry']).first()
            if industry:
                client.industry = industry
    if 'contact' in data:
        client.contact = data['contact']
    if 'description' in data:
        client.description = data['description']
    if 'business_type' in data:
        client.business_type = data['business_type']
    if 'product_type' in data:
        client.product_type = data['product_type']
    if 'service_type' in data:
        client.service_type = data['service_type']
    if 'service_range' in data:
        client.service_range = data['service_range']
    if 'target_area' in data:
        client.target_area = data['target_area']
    if 'brand_type' in data:
        client.brand_type = data['brand_type']
    if 'brand_description' in data:
        client.brand_description = data['brand_description']
    if 'language_style' in data:
        client.language_style = data['language_style']
    if 'dialect' in data:
        client.dialect = data['dialect']
    # 录入表单新增字段
    if 'main_product' in data:
        client.main_product = data['main_product']
    if 'business_years' in data:
        client.business_years = data['business_years']
    if 'other_info' in data:
        client.other_info = data['other_info']
    if 'core_advantage' in data:
        client.core_advantage = data['core_advantage']
    if 'project_goals' in data:
        client.project_goals = data['project_goals']
    if 'status' in data:
        client.status = data['status']
    
    db.session.commit()
    
    return jsonify({'code': 200, 'message': 'success', 'data': {'id': client.id}})


@api.route('/clients', methods=['POST'])
@login_required
def create_client():
    """创建新客户"""
    data = request.get_json()
    
    client_name = data.get('name')
    if not client_name:
        return jsonify({'code': 400, 'message': '客户名称不能为空'})
    
    # 客户名称查重校验
    existing_client = Client.query.filter(
        Client.name == client_name,
        Client.user_id == current_user.id
    ).first()
    if existing_client:
        return jsonify({
            'code': 409, 
            'message': f'客户"{client_name}"已存在，请勿重复提交',
            'data': {'client_id': existing_client.id}
        })
    
    # 查询或创建行业
    industry_name = data.get('industry', '')
    industry_id = None
    if industry_name:
        industry = Industry.query.filter_by(name=industry_name).first()
        if industry:
            industry_id = industry.id
    
    # 创建客户
    client = Client(
        name=client_name,
        industry_id=industry_id,
        user_id=current_user.id,
        business_type=data.get('business_type', ''),
        product_type=data.get('product_type', ''),
        service_type=data.get('service_type', ''),
        service_range=data.get('service_range', ''),
        target_area=data.get('target_area', ''),
        brand_type=data.get('brand_type', ''),
        brand_description=data.get('brand_description', ''),
        language_style=data.get('language_style', ''),
        dialect=data.get('dialect', ''),
        main_product=data.get('main_product', ''),
        business_years=data.get('business_years', ''),
        other_info=data.get('other_info', ''),
        status='active'
    )
    db.session.add(client)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': 'success', 'data': {'id': client.id, 'name': client.name}})


@api.route('/clients/<int:client_id>/keywords', methods=['GET'])
@login_required
def get_keywords(client_id):
    """获取客户关键词"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    keywords = client.keywords.all()
    data = [{
        'id': k.id,
        'keyword': k.keyword,
        'keyword_type': k.keyword_type,
        'search_intent': k.search_intent,
        'competition': k.competition,
        'is_monitored': k.is_monitored
    } for k in keywords]
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/clients/<int:client_id>/keywords', methods=['POST'])
@login_required
def add_keyword(client_id):
    """添加关键词"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    data = request.get_json()
    keyword = Keyword(
        client_id=client_id,
        keyword=data.get('keyword'),
        keyword_type=data.get('keyword_type'),
        search_intent=data.get('search_intent'),
        competition=data.get('competition')
    )
    db.session.add(keyword)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '关键词添加成功',
        'data': {'id': keyword.id}
    })


@api.route('/clients/<int:client_id>/topics', methods=['GET'])
@login_required
def get_topics(client_id):
    """获取客户选题"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    topics = client.topics.all()
    data = [{
        'id': t.id,
        'title': t.title,
        'topic_type': t.topic_type,
        'content_format': t.content_format,
        'priority': t.priority,
        'status': t.status
    } for t in topics]
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/clients/<int:client_id>/topics', methods=['POST'])
@login_required
def add_topic(client_id):
    """添加选题"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    data = request.get_json()
    topic = Topic(
        client_id=client_id,
        title=data.get('title'),
        topic_type=data.get('topic_type'),
        content_format=data.get('content_format'),
        target_audience=data.get('target_audience'),
        priority=data.get('priority', 0)
    )
    db.session.add(topic)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '选题添加成功',
        'data': {'id': topic.id}
    })


@api.route('/clients/<int:client_id>/monitors', methods=['GET'])
@login_required
def get_monitors(client_id):
    """获取客户监控"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    monitors = client.monitors.all()
    data = [{
        'id': m.id,
        'monitor_type': m.monitor_type,
        'link_type': m.link_type,
        'value': m.value,
        'theme': m.theme,
        'status': m.status
    } for m in monitors]
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/clients/<int:client_id>/monitors', methods=['POST'])
@login_required
def add_monitor(client_id):
    """添加监控"""
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    data = request.get_json()
    monitor = Monitor(
        client_id=client_id,
        monitor_type=data.get('monitor_type'),
        link_type=data.get('link_type'),
        value=data.get('value'),
        theme=data.get('theme'),
        status='monitoring'
    )
    db.session.add(monitor)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '监控添加成功',
        'data': {'id': monitor.id}
    })


# ==================== 舆情监控定时任务API ====================

@api.route('/cron/monitor', methods=['POST'])
def run_monitor_cron():
    """定时任务：执行舆情监控"""
    # 注意：生产环境需要添加认证
    # 获取所有监控中的客户
    clients = Client.query.filter_by(is_active=True).all()
    
    results = []
    for client in clients:
        monitors = client.monitors.filter_by(status='monitoring').all()
        if monitors:
            # 这里可以调用实际的监控逻辑
            results.append({
                'client_id': client.id,
                'client_name': client.name,
                'monitor_count': len(monitors),
                'status': 'pending'  # 待实现
            })
    
    return jsonify({
        'code': 200,
        'message': '监控任务执行完成',
        'data': results
    })


# ==================== 专家分配API ====================

@api.route('/channel/experts', methods=['GET'])
@login_required
def get_channel_experts():
    """获取渠道的专家列表"""
    if not current_user.is_channel():
        return jsonify({'code': 403, 'message': '需要渠道权限', 'data': []})
    
    channel = current_user.channels.first()
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在', 'data': []})
    
    # 获取已分配的专家
    experts = channel.experts.all()
    if not experts:
        # 默认返回总控专家
        master = Expert.query.filter_by(slug='master').first()
        if master:
            experts = [master]
    
    data = [{
        'id': e.id,
        'name': e.name,
        'slug': e.slug,
        'description': e.description,
        'icon': e.icon
    } for e in experts]
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


# ==================== 对话历史 API ====================

@api.route('/chat/sessions', methods=['GET'])
@login_required
def get_chat_sessions():
    """获取对话会话列表"""
    client_id = request.args.get('client_id', type=int)
    expert_id = request.args.get('expert_id', type=int)
    
    query = ChatSession.query.filter_by(user_id=current_user.id, is_active=True)
    
    if client_id:
        query = query.filter_by(client_id=client_id)
    if expert_id:
        query = query.filter_by(expert_id=expert_id)
    
    sessions = query.order_by(ChatSession.updated_at.desc()).limit(20).all()
    
    data = [{
        'id': s.id,
        'title': s.title or '新对话',
        'expert_name': s.expert.name if s.expert else '专家',
        'expert_icon': s.expert.icon if s.expert else '🤖',
        'expert_slug': s.expert.slug if s.expert else None,
        'client_name': s.client.name if s.client else None,
        'message_count': s.messages.count(),
        'updated_at': s.updated_at.isoformat() if s.updated_at else None
    } for s in sessions]
    
    return jsonify({'code': 200, 'message': 'success', 'data': {'sessions': data}})


@api.route('/chat/sessions/<int:session_id>/messages', methods=['GET'])
@login_required
def get_session_messages(session_id):
    """获取会话的消息历史"""
    session_obj = ChatSession.query.get(session_id)
    if not session_obj:
        return jsonify({'code': 404, 'message': '会话不存在'})
    
    # 权限检查
    if session_obj.user_id != current_user.id:
        return jsonify({'code': 403, 'message': '无权限访问'})
    
    messages = session_obj.messages.order_by(ChatMessage.created_at.asc()).all()
    
    data = [{
        'id': m.id,
        'role': m.role,
        'content': m.content,
        'expert_name': m.expert.name if m.expert else None,
        'expert_icon': m.expert.icon if m.expert else None,
        'created_at': m.created_at.isoformat() if m.created_at else None
    } for m in messages]
    
    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/chat/current', methods=['GET'])
@login_required
def get_current_chat():
    """获取当前客户的当前会话（用于页面加载时）"""
    client_id = session.get('current_client_id')
    expert_slug = request.args.get('expert', 'master')
    session_id = request.args.get('session_id')  # 可选，指定加载某个会话

    if not client_id:
        return jsonify({'code': 200, 'message': '无当前客户', 'data': {'messages': [], 'session_id': None}})

    # 先尝试从数据库 Expert 表查找
    expert = Expert.query.filter_by(slug=expert_slug).first()

    # 如果数据库中没有，从 SkillLoader 获取专家信息
    if not expert:
        from services.skill_loader import get_skill_loader
        skill_loader = get_skill_loader()
        skill_info = skill_loader.get_skill_info(expert_slug)

        if skill_info:
            # 使用 SkillLoader 中的信息构建虚拟专家数据
            expert_data = {
                'id': 0,  # 虚拟 ID
                'name': skill_info.get('name', expert_slug),
                'nickname': skill_info.get('nickname', skill_info.get('name', expert_slug)),
                'title': skill_info.get('title', ''),
                'description': skill_info.get('description', ''),
                'capabilities': [skill_info.get('description', '')],
                'icon': '<i class="bi bi-robot"></i>',
                'from_skill': True  # 标记来自 SkillLoader
            }

            # 查找最近一个会话
            # 注意：SkillLoader 的专家可能没有对应的 ChatSession，暂时返回空消息
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'session_id': None,
                    'expert': expert_data,
                    'messages': []
                }
            })
        else:
            return jsonify({'code': 404, 'message': '专家不存在'})

    # 查找指定会话或最近一个会话
    chat_session = None
    if session_id:
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=current_user.id,
            client_id=client_id
        ).first()

    if not chat_session:
        chat_session = ChatSession.query.filter_by(
            user_id=current_user.id,
            client_id=client_id,
            expert_id=expert.id,
            is_active=True
        ).order_by(ChatSession.updated_at.desc()).first()

    if not chat_session:
        # 返回专家欢迎语（返回空消息数组，让前端显示欢迎语）
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'session_id': None,
                'expert': {
                    'id': expert.id,
                    'name': expert.name,
                    'nickname': expert.nickname,
                    'title': expert.title,
                    'description': expert.description,
                    'capabilities': expert.capabilities,
                    'icon': expert.icon
                },
                'messages': []
            }
        })

    # 获取消息历史
    messages = chat_session.messages.order_by(ChatMessage.created_at.asc()).all()

    data = {
        'session_id': chat_session.id,
        'expert': {
            'id': expert.id,
            'name': expert.name,
            'nickname': expert.nickname,
            'title': expert.title,
            'description': expert.description,
            'capabilities': expert.capabilities,
            'icon': expert.icon
        },
        'messages': [{
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'expert_name': m.expert.name if m.expert else None,
            'expert_icon': m.expert.icon if m.expert else None,
            'created_at': m.created_at.isoformat() if m.created_at else None
        } for m in messages]
    }

    return jsonify({'code': 200, 'message': 'success', 'data': data})


@api.route('/chat/sessions/client', methods=['GET'])
@login_required
def get_client_chat_sessions():
    client_id = session.get('current_client_id')

    if not client_id:
        return jsonify({'code': 200, 'message': '无当前客户', 'data': {'sessions': []}})

    # 获取当前客户的所有会话，按更新时间倒序
    sessions = ChatSession.query.filter_by(
        user_id=current_user.id,
        client_id=client_id,
        is_active=True
    ).order_by(ChatSession.updated_at.desc()).limit(50).all()

    # 构建会话列表数据
    session_list = []
    for s in sessions:
        # 获取该会话的专家信息
        expert_info = None
        if s.expert:
            expert_info = {
                'id': s.expert.id,
                'name': s.expert.name,
                'nickname': s.expert.nickname,
                'title': s.expert.title,
                'icon': s.expert.icon,
                'slug': s.expert.slug
            }
        else:
            # 尝试从 SkillLoader 获取
            from services.skill_loader import get_skill_loader
            skill_loader = get_skill_loader()
            # 通过 expert_id 尝试映射到 skill
            skill_info = skill_loader.get_skill_info(str(s.expert_id))
            if skill_info:
                expert_info = {
                    'id': s.expert_id,
                    'name': skill_info.get('name', '未知专家'),
                    'nickname': skill_info.get('nickname', skill_info.get('name', '未知')),
                    'title': skill_info.get('title', ''),
                    'icon': '<i class="bi bi-robot"></i>',
                    'slug': str(s.expert_id)
                }

        # 获取消息数量和最后一条消息
        message_count = s.messages.count()
        last_message = s.messages.order_by(ChatMessage.created_at.desc()).first()

        session_list.append({
            'id': s.id,
            'title': s.title,
            'expert': expert_info,
            'message_count': message_count,
            'last_message': last_message.content[:100] if last_message else None,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None,
            'created_at': s.created_at.isoformat() if s.created_at else None
        })

    return jsonify({'code': 200, 'message': 'success', 'data': {'sessions': session_list}})


@api.route('/chat/switch-expert', methods=['POST'])
@login_required
def switch_expert():
    """切换专家（但不创建新会话，保留当前对话历史）"""
    data = request.get_json()
    expert_slug = data.get('expert_slug', 'master')
    
    expert = Expert.query.filter_by(slug=expert_slug).first()
    if not expert:
        return jsonify({'code': 404, 'message': '专家不存在'})
    
    client_id = session.get('current_client_id')
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'expert': {
                'id': expert.id,
                'name': expert.name,
                'slug': expert.slug,
                'nickname': expert.nickname,
                'title': expert.title,
                'description': expert.description,
                'capabilities': expert.capabilities,
                'icon': expert.icon
            }
        }
    })


@api.route('/channel/experts/assign', methods=['POST'])
@login_required
def assign_channel_experts():
    """分配专家给渠道"""
    if not current_user.is_super_admin():
        return jsonify({'code': 403, 'message': '需要超级管理员权限'})
    
    data = request.get_json()
    channel_id = data.get('channel_id')
    expert_ids = data.get('expert_ids', [])
    
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'})
    
    # 清除旧关联，重新分配
    channel.experts = []
    
    for expert_id in expert_ids:
        expert = Expert.query.get(expert_id)
        if expert:
            channel.experts.append(expert)
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '专家分配成功',
        'data': {'channel_id': channel_id, 'expert_count': len(expert_ids)}
    })


@api.route('/channel/experts/default', methods=['POST'])
@login_required
def assign_default_experts():
    """为渠道分配默认专家（总控、内容创作、运营）"""
    if not current_user.is_channel():
        return jsonify({'code': 403, 'message': '需要渠道权限'})
    
    channel = current_user.channels.first()
    if not channel:
        return jsonify({'code': 404, 'message': '渠道不存在'})
    
    # 分配的专家slug列表
    default_slugs = ['master', 'content', 'seo']
    
    channel.experts = []
    for slug in default_slugs:
        expert = Expert.query.filter_by(slug=slug).first()
        if expert:
            channel.experts.append(expert)
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '默认专家分配成功',
        'data': {'expert_slugs': default_slugs}
    })


# ==================== AI 对话 API ====================

@api.route('/chat', methods=['POST'])
@login_required
def chat_with_expert():
    """与专家 AI 对话"""
    from services.llm import chat_with_llm
    from services.skill_loader import get_skill_loader

    data = request.get_json()
    expert_slug = data.get('expert_slug', 'master')
    message = data.get('message', '')
    client_id = data.get('client_id') or session.get('current_client_id')
    session_id = data.get('session_id')  # 传入 session_id 表示继续当前会话

    if not message:
        return jsonify({'code': 400, 'message': '消息不能为空'})

    # 获取用户角色
    user_role = current_user.role if current_user.is_authenticated else 'user'

    # 安全检查 - 拦截修改 skill 的请求
    skill_loader = get_skill_loader()
    is_dangerous, danger_response = skill_loader.is_skill_modification_request(message, user_role)
    if is_dangerous:
        return jsonify({
            'code': 403,
            'message': danger_response,
            'data': None
        })
    
    # 获取专家信息
    expert = Expert.query.filter_by(slug=expert_slug).first()
    if not expert:
        return jsonify({'code': 404, 'message': '专家不存在'})
    
    # 获取或创建会话
    chat_session = None
    if session_id:
        chat_session = ChatSession.query.get(session_id)
    
    if not chat_session:
        # 创建新会话
        chat_session = ChatSession(
            user_id=current_user.id,
            client_id=client_id,
            expert_id=expert.id,
            title=message[:50] + ('...' if len(message) > 50 else ''),
            is_active=True
        )
        db.session.add(chat_session)
        db.session.commit()
    
    # 保存用户消息
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role='user',
        content=message,
        expert_id=expert.id,
        extra_data={'expert_slug': expert_slug}
    )
    db.session.add(user_msg)
    
    # 构建系统提示词
    system_prompt = _build_expert_prompt(expert, client_id, user_role)
    
    # 获取历史消息（最近10条）
    history_messages = chat_session.messages.order_by(ChatMessage.created_at.desc()).limit(10).all()
    history_messages = list(reversed(history_messages))
    
    # 构建消息列表（排除 system 角色，因为我们在 prompt 中构建）
    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in history_messages:
        if msg.role != 'system':
            messages_for_llm.append({
                "role": msg.role,
                "content": msg.content
            })
    # 添加当前消息
    messages_for_llm.append({"role": "user", "content": message})
    
    # 调用 LLM
    response = chat_with_llm(messages_for_llm, temperature=0.7)
    
    if response:
        # 保存助手回复
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role='assistant',
            content=response,
            expert_id=expert.id,
            extra_data={'expert_slug': expert_slug}
        )
        db.session.add(assistant_msg)
        
        # 更新会话时间
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        # 检查是否是首席营销官收集客户资料后的确认
        should_create_client = False
        new_client_id = None
        client_profile_completed = False
        
        if expert_slug == 'master' and '✅ 档案已建立' in response:
            # 尝试从回复中提取客户名称并创建客户
            import re
            name_match = re.search(r'客户名称[：:]\s*(.+)', response)
            if name_match:
                client_name = name_match.group(1).strip()
                # 创建客户
                try:
                    new_client_id = _create_client_from_chat(client_name, current_user)
                    should_create_client = True
                    client_profile_completed = True
                    print(f"✅ 自动创建客户成功: {client_name} (ID: {new_client_id})")
                except Exception as e:
                    print(f"❌ 自动创建客户失败: {e}")
            else:
                # 可能是已有客户，标记资料收集完成
                if client_id:
                    client = Client.query.get(client_id)
                    if client and client.status == 'collecting':
                        client.status = 'completed'
                        db.session.commit()
                        client_profile_completed = True
        
        # 首席营销官收集完客户资料后，标记需要调度其他专家
        dispatch_experts = False
        if expert_slug == 'master' and '✅ 档案已建立' in response:
            dispatch_experts = True
            
            # 更新客户状态为已完成资料收集
            if new_client_id:
                client = Client.query.get(new_client_id)
                if client:
                    client.status = 'completed'
                    db.session.commit()
            elif client_id:
                client = Client.query.get(client_id)
                if client and client.status == 'collecting':
                    client.status = 'completed'
                    db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'reply': response,
                'session_id': chat_session.id,
                'expert': {
                    'id': expert.id,
                    'name': expert.name,
                    'icon': expert.icon
                },
                'client_created': should_create_client,
                'new_client_id': new_client_id,
                'dispatch_experts': dispatch_experts,
                'client_profile_completed': client_profile_completed
            }
        })
    else:
        return jsonify({
            'code': 500,
            'message': 'AI 响应失败，请稍后重试'
        })


@api.route('/chat/stream', methods=['POST'])
@login_required
def chat_with_expert_stream():
    """与专家 AI 对话 - 流式输出"""
    from services.llm import LLMService, get_llm_service
    from services.skill_loader import get_skill_loader
    import re

    data = request.get_json()
    expert_slug = data.get('expert_slug', 'master')
    message = data.get('message', '')
    client_id = data.get('client_id') or session.get('current_client_id')
    session_id = data.get('session_id')

    if not message:
        return jsonify({'code': 400, 'message': '消息不能为空'})

    # 获取用户角色
    user_role = current_user.role if current_user.is_authenticated else 'user'

    # 安全检查 - 拦截修改 skill 的请求
    skill_loader = get_skill_loader()
    is_dangerous, danger_response = skill_loader.is_skill_modification_request(message, user_role)
    if is_dangerous:
        return jsonify({
            'code': 403,
            'message': danger_response,
            'data': None
        })
    
    # 获取专家信息
    expert = Expert.query.filter_by(slug=expert_slug).first()
    if not expert:
        return jsonify({'code': 404, 'message': '专家不存在'})
    
    # 获取或创建会话
    chat_session = None
    if session_id:
        chat_session = ChatSession.query.get(session_id)
    
    if not chat_session:
        chat_session = ChatSession(
            user_id=current_user.id,
            client_id=client_id,
            expert_id=expert.id,
            title=message[:50] + ('...' if len(message) > 50 else ''),
            is_active=True
        )
        db.session.add(chat_session)
        db.session.commit()
    
    # 保存用户消息
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role='user',
        content=message,
        expert_id=expert.id,
        extra_data={'expert_slug': expert_slug}
    )
    db.session.add(user_msg)
    db.session.commit()
    
    # 构建系统提示词
    system_prompt = _build_expert_prompt(expert, client_id, user_role)
    
    # 获取历史消息
    history_messages = chat_session.messages.order_by(ChatMessage.created_at.desc()).limit(10).all()
    history_messages = list(reversed(history_messages))
    
    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in history_messages:
        if msg.role != 'system':
            messages_for_llm.append({
                "role": msg.role,
                "content": msg.content
            })
    messages_for_llm.append({"role": "user", "content": message})
    
    # 流式输出
    def generate():
        service = get_llm_service()
        full_response = ""
        
        try:
            for chunk in service.chat_stream(messages_for_llm, temperature=0.7):
                full_response += chunk
                # 发送 SSE 格式的数据
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            # 保存完整回复到数据库
            if full_response:
                assistant_msg = ChatMessage(
                    session_id=chat_session.id,
                    role='assistant',
                    content=full_response,
                    expert_id=expert.id,
                    extra_data={'expert_slug': expert_slug}
                )
                db.session.add(assistant_msg)
                
                # 更新会话时间
                chat_session.updated_at = datetime.utcnow()
                
                # 检查是否需要创建客户
                should_create_client = False
                new_client_id = None
                dispatch_experts = False
                
                if expert_slug == 'master' and '✅ 档案已建立' in full_response:
                    name_match = re.search(r'客户名称[：:]\s*(.+)', full_response)
                    if name_match:
                        client_name = name_match.group(1).strip()
                        try:
                            new_client_id = _create_client_from_chat(client_name, current_user)
                            should_create_client = True
                            if new_client_id:
                                client = Client.query.get(new_client_id)
                                if client:
                                    client.status = 'completed'
                                    db.session.commit()
                                    dispatch_experts = True
                        except Exception as e:
                            print(f"❌ 自动创建客户失败: {e}")
                    elif client_id:
                        client = Client.query.get(client_id)
                        if client and client.status == 'collecting':
                            client.status = 'completed'
                            db.session.commit()
                            dispatch_experts = True
                
                db.session.commit()
                
                # 发送会话结束信息
                end_data = {
                    'done': True,
                    'session_id': chat_session.id,
                    'expert': {
                        'id': expert.id,
                        'name': expert.name,
                        'icon': expert.icon
                    },
                    'client_created': should_create_client,
                    'new_client_id': new_client_id,
                    'dispatch_experts': dispatch_experts
                }
                yield f"data: {json.dumps(end_data)}\n\n"
            
        except Exception as e:
            error_data = {'error': str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@api.route('/dispatch-experts', methods=['POST'])
@login_required
def dispatch_experts():
    """调度其他专家生成报告 - 根据客户类型智能调度"""
    from services.llm import chat_with_llm
    
    data = request.get_json()
    client_id = data.get('client_id')
    client_name = data.get('client_name', '客户')
    
    if not client_id:
        return jsonify({'code': 400, 'message': '缺少客户ID'})
    
    # 获取客户完整信息
    client = Client.query.get(client_id)
    if not client:
        return jsonify({'code': 404, 'message': '客户不存在'})
    
    # 构建客户信息摘要
    client_info = _build_client_summary(client)
    
    # 根据客户类型智能确定需要调度的专家
    experts_to_dispatch = _get_experts_by_client_type(client)
    
    results = []
    
    for expert_info in experts_to_dispatch:
        expert = Expert.query.filter_by(slug=expert_info['slug']).first()
        if not expert:
            results.append({'expert': expert_info['name'], 'status': 'failed', 'reason': '专家不存在'})
            continue
        
        # 构建智能调度提示词
        dispatch_prompt = _build_dispatch_prompt(client, client_info, expert_info)
        
        messages = [
            {"role": "system", "content": _build_expert_prompt(expert, client_id, 'super_admin')},
            {"role": "user", "content": dispatch_prompt}
        ]
        
        try:
            response = chat_with_llm(messages, temperature=0.7)
            if response:
                # 保存输出到数据库
                output = ExpertOutput(
                    expert_id=expert.id,
                    client_id=client_id,
                    output_type=expert_info['task'],
                    title=f"{client.name} - {expert_info['task']}",
                    content=response,
                    created_at=datetime.utcnow()
                )
                db.session.add(output)
                db.session.commit()
                results.append({'expert': expert_info['name'], 'status': 'success', 'task': expert_info['task']})
            else:
                results.append({'expert': expert_info['name'], 'status': 'failed', 'reason': 'AI响应失败'})
        except Exception as e:
            results.append({'expert': expert_info['name'], 'status': 'failed', 'reason': str(e)})
    
    return jsonify({
        'code': 200,
        'message': '专家调度完成',
        'data': {
            'results': results
        }
    })


def _build_client_summary(client):
    """构建客户信息摘要"""
    summary = []
    
    if client.name:
        summary.append(f"客户名称：{client.name}")
    if client.business_type:
        summary.append(f"客户类型：{client.business_type}")
    if client.product_type:
        summary.append(f"产品类型：{client.product_type}")
    if client.service_type:
        summary.append(f"服务类型：{client.service_type}")
    if client.service_range:
        summary.append(f"地域范围：{client.service_range}")
    if client.target_area:
        summary.append(f"目标区域：{client.target_area}")
    if client.brand_type:
        summary.append(f"品牌定位：{client.brand_type}")
    if client.brand_description:
        summary.append(f"品牌描述：{client.brand_description}")
    if client.language_style:
        summary.append(f"语言风格：{client.language_style}")
    if client.dialect:
        summary.append(f"方言：{client.dialect}")
    if client.core_advantage:
        summary.append(f"核心优势：{client.core_advantage}")
    if client.project_goals:
        summary.append(f"项目目标：{client.project_goals}")
    if client.description:
        summary.append(f"业务描述：{client.description}")
    
    return "\n".join(summary) if summary else "暂无详细信息"


def _get_experts_by_client_type(client):
    """根据客户类型确定需要调度的专家"""
    experts = []
    
    # 基础专家：所有客户都需要
    base_experts = [
        {'slug': 'seo', 'name': 'Geo SEO 策略师', 'task': '关键词库与选题推荐'}
    ]
    
    # 运营专家：新客户首合作必选
    operations_expert = {'slug': 'operation', 'name': '运营专家', 'task': '运营规划方案'}
    
    # 内容专家：所有客户都需要，合并了消费心理学和视觉设计能力
    content_expert = {'slug': 'content', 'name': '内容创作师·墨菲·库珀', 'task': '内容脚本规划', 'nickname': '墨菲·库珀'}
    
    # 市场洞察专家：根据需要
    insights_expert = {'slug': 'monitor', 'name': '市场洞察分析师', 'task': '行业分析报告'}
    
    # 舆情监控专家：本地业务或需要监控的客户
    monitor_expert = {'slug': 'monitor', 'name': '社交舆情监控专家', 'task': '舆情监控配置'}
    
    
    # 根据业务类型添加专家
    business_type = client.business_type or ''
    
    # 卖货类：需要舆情监控
    if '卖货' in business_type or '商品' in business_type:
        experts.append(monitor_expert)
    
    # 服务类：本地服务需要舆情监控
    if '服务' in business_type:
        if client.service_range == '本地' or client.service_range == '本地服务':
            experts.append(monitor_expert)
    
    # 跨区域/全国：需要市场洞察
    if client.service_range in ['跨区域', '跨区域服务', '全球', '全球/海外']:
        experts.append(insights_expert)
    
    # 添加基础专家
    experts.extend(base_experts)
    
    # 添加运营专家（新客户首合作）
    experts.append(operations_expert)
    
    # 添加内容专家（已合并消费心理学和视觉设计能力）
    experts.append(content_expert)
    
    # 去重（根据slug）
    seen = set()
    unique_experts = []
    for exp in experts:
        if exp['slug'] not in seen:
            seen.add(exp['slug'])
            unique_experts.append(exp)
    
    return unique_experts


def _build_dispatch_prompt(client, client_info, expert_info):
    """构建调度提示词"""
    task = expert_info['task']
    expert_name = expert_info['name']
    
    prompt = f"""请为客户"{client.name}"生成{expert_info['task']}。

【客户详细信息】
{client_info}

【任务要求】
请根据上述客户信息，生成专业、个性化的{expert_info['task']}。

"""
    
    # 根据任务类型添加特定要求
    if '关键词库' in task:
        # 读取关键词库模板
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'geo-seo', '输出', '关键词库', '关键词库_模板.md'
        )
        template_content = ""
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        prompt += f"""
【关键词库生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成关键词库
2. **数量要求**：关键词库必须生成 **至少100个** 关键词
3. **分类要求**：必须包含以下分类
   - 一、直接需求关键词（≥20个）
   - 二、痛点关键词（≥15个）
   - 三、搜索关键词（≥15个）
   - 四、场景关键词（≥15个）
   - 五、地域关键词（≥10个）
   - 六、季节/时间关键词（≥10个）
   - 七、技巧/干货关键词（≥10个）
   - 八、认知颠覆/反向关键词（≥5个）
   - 九、节日/节气关键词（≥15个）
4. **关键词配比**：蓝海长尾词50%+，问题词35%，红海词≤15%
5. **痛点原则**：所有关键词必须遵循"真实想要+痛点+紧急"原则

## 关键词库模板
{template_content}

请生成完整的关键词库。
"""
    
    elif '选题' in task:
        # 读取选题库模板
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'geo-seo', '输出', '选题推荐', '选题库_模板.md'
        )
        template_content = ""
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        prompt += f"""
【选题库生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成选题库
2. **数量要求**：选题库必须生成 **至少200条** 选题
3. **分类要求**：必须包含以下分类
   - 1.1 问题解决类（来自评论区挖痛点）
   - 1.2 认知颠覆类（来自颠覆常识）
   - 1.3 知识教程类（来自搜索框挖需求）
   - 1.4 经验分享类（来自传统经验）
   - 1.5 季节营销类（来自季节节点）
   - 1.6 案例展示类
   - 1.7 行业揭秘类
4. **选题来源**：必须遵循"选题关键词方法论"的5大选题来源
5. **痛点原则**：所有选题必须遵循"真实想要+痛点+紧急"原则

## 选题库模板
{template_content}

请生成完整的选题库。
"""
    
    elif '运营规划' in task:
        # 读取运营规划模板
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'operations-expert', '输出', '运营规划', '运营规划方案_模板.md'
        )
        template_content = ""
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        prompt += f"""
【运营规划方案生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成运营规划方案
2. **核心思维流程**：必须按以下7步顺序进行
   - 1️⃣ 行业分析 → 2️⃣ 找蓝海 → 3️⃣ 人群细分 → 4️⃣ 长尾需求 → 5️⃣ 知识技能解决 → 6️⃣ 搜前搜后 → 7️⃣ 行业关联
3. **内容配比规则**：信任佐证+竞争优势内容占比 **15%**，其他内容占比 **85%**
4. **高权重内容**：
   - "信任佐证4大方向"必须有（专业知识技能、环境、过程、案例）
   - "竞争优势4大维度"必须有（vs同行、vs自己动手）
5. **搜前搜后分析**：必须覆盖直接需求、关联需求、潜在需求、决策顾虑

## 运营规划模板
{template_content}

请生成完整的运营规划方案。
"""
    
    elif '内容脚本' in task:
        # 读取内容脚本模板
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'content-creator', '输出', '脚本', '图文内容模板.md'
        )
        template_content = ""
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        prompt += f"""
【内容脚本生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成内容脚本
2. **内容规格**：图文 | 图片数量：5张 | 比例：9:16竖版 1080×1920px
3. **封面优先**：首页决定图文的生死，封面必须重点设计
4. **标题设计**：必须包含主标题、副标题、封面建议
5. **内容结构**：必须包含钩子引入、核心内容、信任佐证、行动引导

## 内容脚本模板
{template_content}

请生成完整的内容脚本。
"""
    
    elif '行业分析' in task:
        # 读取行业分析报告模板
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md'
        )
        template_content = ""
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        
        prompt += f"""
【行业分析报告生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成报告
2. **核心思维流程**：必须按以下7步顺序进行
   - 1️⃣ 行业分析 → 2️⃣ 找蓝海 → 3️⃣ 人群细分 → 4️⃣ 长尾需求 → 5️⃣ 知识技能解决 → 6️⃣ 搜前搜后 → 7️⃣ 行业关联
3. **内容配比规则**：信任佐证+竞争优势内容占比 15%，其他内容占比 85%
4. **高权重章节**："用户失败经历分析"是必有的高权重内容

## 报告模板
{template_content}

## 报告生成规则
- 使用模板中的6大章节结构：一、行业概况；二、目标客户分析；三、行业生态分析；四、用户失败经历分析；五、竞争格局与蓝海机会；六、总结
- 必须包含"用户失败经历分析"章节，这是高权重内容
- 搜索意图分析（搜前搜后）应融入相应章节
- 信任佐证与竞争优势应融入各章节，而非独立章节

请生成完整的行业分析报告。
"""
    
    elif '舆情监控' in task:
        prompt += """
【舆情监控配置要求】
1. 关键词监控列表
2. 竞品监控链接
3. 监控频率建议
4. 预警阈值设置
"""
    
    elif '心理' in task:
        prompt += """
【内容心理优化要求】
1. 目标用户心理分析
2. 心理钩子设计
3. 信任构建策略
4. 转化路径优化
"""
    
    elif '视觉' in task:
        prompt += """
【视觉设计评审要求】
1. 9:16 比例检查
2. 封面设计建议
3. 场景图适配建议
4. 排版优化建议
"""
    
    prompt += """
请生成完整、可执行的方案，包含具体的内容和操作步骤。
"""
    
    return prompt


def _create_client_from_chat(client_name, user):
    """从对话中创建客户"""
    from models.models import Client, Channel, db
    
    # 获取用户的渠道
    if user.role == 'channel':
        channel = user.channels.first()
    else:
        # 超级管理员 - 获取第一个渠道或创建
        channel = Channel.query.first()
        if not channel:
            channel = Channel(
                name='默认渠道',
                slug='default',
                user_id=user.id,
                is_active=True
            )
            db.session.add(channel)
            db.session.commit()
    
    if not channel:
        return None
    
    # 创建客户
    client = Client(
        channel_id=channel.id,
        user_id=user.id,
        name=client_name,
        is_active=True
    )
    db.session.add(client)
    db.session.commit()
    
    return client.id


def _build_expert_prompt(expert, client_id=None, user_role='user'):
    """构建专家角色提示词"""
    # 获取安全指令
    skill_loader = get_skill_loader()
    security_instruction = skill_loader._get_security_instruction(user_role)

    # 基础提示词
    base_prompt = f"""你是一个专业的AI营销顾问，名为{expert.name}。
你的职责是帮助用户解决营销相关的问题。

{security_instruction}
"""
    
    # 专家特定提示词
    expert_prompts = {
        'master': """你是"首席营销官"，是AI内容营销系统的核心负责人。

【核心任务】当用户说"新建客户"、"添加客户"、"收集客户资料"或首次为新客户咨询时，你需要进行客户资料收集。

## 客户资料收集（一次性完成）

请直接向用户展示以下完整的客户信息收集表，要求用户填写/选择每一项：

---

### 📋 客户基础信息表

**1. 客户名称**：_____（必填）

**2. 客户类型**（必填，单选）：
A. 卖货类 - 有具体产品需要销售（电商、零售、直播带货等）
B. 服务类 - 提供服务而非实体商品（咨询、培训、本地服务等）
C. 两者都有 - 同时销售产品和服务

**2.1 产品类型**（如果选A或C）：
① 实物商品（自有品牌/代理/白牌）
② 批发/供应链
③ 其他：_____

**2.2 服务类型**（如果选B或C）：
① 本地生活服务（餐饮、美业、家政等，需到店/上门）
② 线上专业服务（咨询、培训、设计、财税、法律等）
③ 知识付费（课程、社群、付费内容等）
④ 其他：_____

**3. 地域范围**（必填，单选）：
A. 本地服务 - 仅服务特定城市/区域
   - 目标城市是？_____
B. 跨区域服务 - 可服务全国/多省客户
   - 重点覆盖区域？_____
C. 全球/海外 - 服务海外华人或国际市场

**4. 品牌定位**（必填，单选）：
A. 个人IP - 以创始人/专家/达人为核心
   - 以谁为核心？_____
B. 企业品牌 - 以公司/机构形象为核心
   - 公司规模？_____
C. 两者兼顾 - 个人IP + 企业品牌双轨运营
   - 哪个权重更高？_____

**5. 业务描述**（必填）：
请用一句话描述您的业务：您在做什么？解决客户什么问题？
_____

**6. 项目目标**（必填，可多选，按优先级排序）：
A. 流量获取 - 获取精准潜在客户线索
B. 品牌曝光 - 提升知名度和专业形象
C. 转化成交 - 直接带动销售/订单
D. 客户教育 - 科普行业知识，建立信任

**7. 语言风格**（建议填写）：
您的目标客户主要使用什么语言/方言？
- 普通话 / 粤语 / 四川话 / 东北话 / 上海话 / 其他方言：_____

**8. 运营资源**（选填）：
- 是否有抖音运营团队？_____
- 内容生产能力？_____
- 预算范围？_____

---

【工作原则】
1. 一次性展示完整的客户资料收集表，用清晰的格式呈现
2. 用户回复后，提取用户填写的每一项信息
3. 如果用户遗漏必填项，明确提醒用户补充
4. 收集完所有必填信息后，生成标准化客户档案并总结

【输出格式】
收集完成后，生成以下格式的客户档案：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 客户档案
━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ 客户名称：xxx
📦 类型：卖货类/服务类/两者都有
🌍 地域：本地/跨区域/海外
👤 品牌：个人IP/企业品牌/兼顾
📝 业务：xxx
🎯 目标：流量/品牌/转化/教育
🗣️ 语言：xxx
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 档案已建立，可为您提供个性化营销建议！
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 重要：生成客户档案提示词
当用户完成所有信息填写后，你需要：
1. 生成标准的客户档案格式（见上方）
2. 在档案结尾追加以下格式的"专家调度提示词"：

```
━━━ 专家调度提示词 ━━━
【客户档案摘要】
- 客户名称：xxx
- 行业类型：xxx
- 业务模式：xxx
- 核心卖点：xxx
- 目标受众：xxx
- 营销目标：xxx
【已收集信息】
[列出用户已提供的所有详细信息]
【需要专家解决的问题】
[根据客户类型和目标，提出2-3个专家需要重点分析的问题]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

这个提示词将帮助后续的专家快速了解客户情况，提供更有针对性的建议。

当用户不是新建客户时，你应该：
- 首先了解用户的基本情况
- 提供专业、全面的分析
- 用清晰易懂的语言解释复杂的营销概念
- 主动询问以获取更多信息来提供更精准的建议""",
        
        'content': """你是"内容创作师·墨菲·库珀"，昵称"墨菲"，兼具消费心理学和视觉设计专业能力的内容创作专家。

你负责：
1. 图文规划、短视频脚本创作
2. 消费心理分析 - 分析目标用户心理特征，优化文案和创意策略
3. 视觉设计评审 - 9:16比例检查、场景图适配、排版优化
4. 内容优化 - 从心理学和视觉角度提升内容转化效果

【专业能力】
- 消费心理学：用户决策心理、痛点挖掘、文案说服技巧、行动引导
- 视觉设计：封面设计、构图法则、色彩搭配、排版布局

当用户咨询时，你应该：
- 提供具体的、可操作的内容建议
- 给出实际的内容案例
- 关注内容质量和转化效果
- 从消费心理角度分析用户行为
- 确保视觉设计符合平台规范""",
        
        'monitor': """你是"社交监控和市场洞察分析师"，专注于品牌声誉管理和市场洞察。
你负责：
1. 监控品牌舆情动态
2. 分析舆论趋势和风险
3. 提供市场洞察和趋势分析
4. 指导正面口碑建设
5. 竞品分析

当用户咨询时，你应该：
- 及时提醒潜在的负面舆情
- 提供具体的应对方案
- 帮助建立舆情预警机制
- 提供市场洞察和趋势分析""",
        
        'seo': """你是"Geo SEO 策略师"墨菲，专注于AI搜索优化和账号运营。

你负责：
1. AI搜索优化 - 关键词研究和优化、内容SEO策略制定
2. 内容发现 - 关键词库生成、选题库生成
3. 运营策划 - 市场机会发现、差异化定位、账号设计、运营方案

当用户咨询时，你应该：
- 提供具体的关键词建议和SEO方案
- 关注长期和短期排名效果
- 提供市场分析和运营建议
- 帮助进行账号定位和差异化竞争""",
        
        'psychology': """你是"用户心理"专家，专注于消费者心理分析。
你负责：
1. 分析目标用户心理特征
2. 提供用户洞察和画像
3. 优化文案和创意策略
4. 指导用户互动策略

当用户咨询时，你应该：
- 用心理学原理分析用户行为
- 提供有深度的用户洞察
- 给出基于心理学的营销建议""",
        
        'visual': """你是"视觉设计"专家，专注于短视频视觉呈现。
你负责：
1. 提供视觉风格定位
2. 指导视频剪辑和包装
3. 设计封面和配图
4. 优化视觉体验

当用户咨询时，你应该：
- 提供具体的视觉建议
- 给出实际的设计案例
- 关注视觉吸引力和信息传达"""
    }
    
    # 添加专家特定提示词
    specific_prompt = expert_prompts.get(expert.slug, expert_prompts['master'])
    
    # 获取客户信息（如果提供）
    client_info = ""
    if client_id:
        client = Client.query.get(client_id)
        if client:
            client_info = f"""
当前客户信息：
- 客户名称：{client.name}
- 行业：{client.industry or '未知'}
- 业务类型：{client.business_type or '未知'}
- 描述：{client.description or '暂无'}
"""
    
    return base_prompt + specific_prompt + client_info


# ==================== 产出记录API ====================

@api.route('/outputs', methods=['GET'])
@login_required
def get_outputs():
    """获取产出历史记录"""
    client_id = request.args.get('client_id', type=int)
    
    query = ExpertOutput.query
    
    # 超级管理员可以看到所有，其他用户只能看到自己客户的
    if not current_user.is_super_admin():
        # 获取用户关联的客户
        if current_user.channel_id:
            clients = Client.query.filter_by(channel_id=current_user.channel_id).all()
            client_ids = [c.id for c in clients]
            query = query.filter(ExpertOutput.client_id.in_(client_ids))
        else:
            # 普通用户只能看到自己创建的
            query = query.filter_by(user_id=current_user.id)
    
    if client_id:
        query = query.filter_by(client_id=client_id)
    
    outputs = query.order_by(ExpertOutput.created_at.desc()).limit(50).all()
    
    data = []
    for o in outputs:
        expert = Expert.query.get(o.expert_id) if o.expert_id else None
        client = Client.query.get(o.client_id) if o.client_id else None
        client_name = client.name if client else '客户'
        title = o.title or '报告'
        report_type = title.split(' - ')[0].strip() if ' - ' in title else title
        report_type = _sanitize_filename(report_type)
        download_filename = _sanitize_filename(client_name) + '_' + report_type + '.md'
        data.append({
            'id': o.id,
            'expert_name': expert.name if expert else '专家',
            'expert_icon': expert.icon if expert else '',
            'client_name': client_name,
            'output_type': o.output_type,
            'title': o.title,
            'content': o.content,
            # 转换为北京时间 (UTC+8)
            'created_at': (o.created_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') if o.created_at else '',
            'download_filename': download_filename
        })
    
    return jsonify({'code': 200, 'data': data})


@api.route('/outputs/<int:output_id>', methods=['GET'])
@login_required
def get_output_detail(output_id):
    """获取单个产出记录详情"""
    output = ExpertOutput.query.get(output_id)
    
    if not output:
        return jsonify({'code': 404, 'message': '记录不存在'})
    
    # 检查权限
    if not current_user.is_super_admin():
        if output.user_id != current_user.id:
            # 检查是否是自己客户的
            if output.client_id:
                client = Client.query.get(output.client_id)
                if not client or (client.user_id != current_user.id and 
                    (not current_user.channel_id or client.channel_id != current_user.channel_id)):
                    return jsonify({'code': 403, 'message': '无权限'})
            else:
                return jsonify({'code': 403, 'message': '无权限'})
    
    expert = Expert.query.get(output.expert_id) if output.expert_id else None
    client = Client.query.get(output.client_id) if output.client_id else None
    
    data = {
        'id': output.id,
        'expert_name': expert.name if expert else '专家',
        'expert_title': expert.title if expert else '',
        'client_name': client.name if client else '客户',
        'output_type': output.output_type,
        'title': output.title,
        'content': output.content,
        # 转换为北京时间 (UTC+8)
        'created_at': (output.created_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S') if output.created_at else ''
    }
    
    return jsonify({'code': 200, 'data': data})


@api.route('/outputs/<int:output_id>/download', methods=['GET'])
@login_required
def download_output(output_id):
    """下载报告为 .md 文件，文件名：客户姓名_报告类型.md"""
    output = ExpertOutput.query.get(output_id)
    if not output:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    if not current_user.is_super_admin():
        if output.user_id != current_user.id:
            if output.client_id:
                client = Client.query.get(output.client_id)
                if not client or (client.user_id != current_user.id and
                    (not current_user.channel_id or client.channel_id != current_user.channel_id)):
                    return jsonify({'code': 403, 'message': '无权限'}), 403
            else:
                return jsonify({'code': 403, 'message': '无权限'}), 403
    client = Client.query.get(output.client_id) if output.client_id else None
    client_name = client.name if client else '客户'
    title = output.title or '报告'
    report_type = title.split(' - ')[0].strip() if ' - ' in title else title
    report_type = _sanitize_filename(report_type)
    filename = _sanitize_filename(client_name) + '_' + report_type + '.md'
    content = output.content or ''
    resp = Response(content, mimetype='text/markdown; charset=utf-8')
    resp.headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(filename)
    return resp


@api.route('/save_output', methods=['POST'])
@login_required
def save_output():
    """保存产出记录"""
    data = request.get_json()
    
    expert_name = data.get('expert', '专家')
    client_name = data.get('client', '客户')
    messages = data.get('messages', [])
    
    # 获取或创建客户
    client = None
    if client_name and client_name != '客户':
        client = Client.query.filter_by(name=client_name).first()
    
    # 获取或创建专家
    expert = Expert.query.filter_by(name=expert_name).first()
    
    # 构建内容
    content = ''
    for msg in messages:
        role = '用户' if msg.get('role') == 'user' else expert_name
        content += f"【{role}】{msg.get('content', '')}\n\n"
    
    # 保存到数据库
    output = ExpertOutput(
        expert_id=expert.id if expert else None,
        client_id=client.id if client else None,
        user_id=current_user.id,
        output_type='chat',
        title=f'{expert_name} - {client_name}',
        content=content[:5000] if len(content) > 5000 else content
    )
    db.session.add(output)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '保存成功', 'data': {'id': output.id}})
