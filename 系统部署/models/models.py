from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nickname = db.Column(db.String(80))  # 昵称
    gender = db.Column(db.String(10))  # 性别：male, female, other
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))  # 手机号
    password_hash = db.Column(db.String(256), nullable=False)
    id_card = db.Column(db.String(20))  # 身份证号（用于忘记密码验证）
    role = db.Column(db.String(20), default='user')  # super_admin, channel, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    channels = db.relationship('Channel', backref='owner', lazy='dynamic', overlaps="channel,channels")  # 渠道商（超级管理员创建的渠道账号）
    clients = db.relationship('Client', backref='owner', lazy='dynamic')  # 渠道商管理的客户
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_channel(self):
        return self.role == 'channel'


class Industry(db.Model):
    """行业分类表"""
    __tablename__ = 'industries'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 行业名称
    slug = db.Column(db.String(50), unique=True)  # 行业标识
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Industry {self.name}>'


class Channel(db.Model):
    """渠道商表"""
    __tablename__ = 'channels'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 渠道商名称
    company = db.Column(db.String(100))  # 公司名称
    contact = db.Column(db.String(50))  # 联系方式
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=False)  # 默认待审核
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('channel', overlaps="channels,owner"), overlaps="channels,owner")
    clients = db.relationship('Client', backref='channel', lazy='dynamic')
    experts = db.relationship('Expert', 
                              secondary='channel_experts',
                              backref='channels')
    
    def __repr__(self):
        return f'<Channel {self.name}>'


# 渠道商-专家关联表
channel_experts = db.Table('channel_experts',
    db.Column('channel_id', db.Integer, db.ForeignKey('channels.id'), primary_key=True),
    db.Column('expert_id', db.Integer, db.ForeignKey('experts.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)


class Expert(db.Model):
    """专家表"""
    __tablename__ = 'experts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 专家名称
    slug = db.Column(db.String(50), unique=True, nullable=False)  # 简称
    nickname = db.Column(db.String(50))  # 昵称
    title = db.Column(db.String(50))  # 职位
    description = db.Column(db.Text)
    capabilities = db.Column(db.JSON)  # 能力列表
    command = db.Column(db.String(50))  # 呼出命令
    icon = db.Column(db.String(50))  # 图标（emoji）
    avatar_url = db.Column(db.String(255))  # 自定义头像URL
    sort_order = db.Column(db.Integer, default=0)  # 显示顺序
    is_visible = db.Column(db.Boolean, default=True)  # 是否在列表中可见
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skills = db.relationship('Skill', backref='expert', lazy='dynamic')
    outputs = db.relationship('ExpertOutput', backref='expert', lazy='dynamic')
    
    def __repr__(self):
        return f'<Expert {self.name}>'


class Skill(db.Model):
    """专家技能表"""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey('experts.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    examples = db.Column(db.JSON)  # 示例列表
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Skill {self.name}>'


class KnowledgeCategory(db.Model):
    """知识库分类表"""
    __tablename__ = 'knowledge_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 分类名称
    slug = db.Column(db.String(50), unique=True)  # 分类标识
    parent_id = db.Column(db.Integer, db.ForeignKey('knowledge_categories.id'))
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    articles = db.relationship('KnowledgeArticle', backref='category', lazy='dynamic')
    children = db.relationship('KnowledgeCategory', 
                               backref=db.backref('parent', remote_side=[id]),
                               lazy='dynamic')
    
    def __repr__(self):
        return f'<KnowledgeCategory {self.name}>'


class KnowledgeArticle(db.Model):
    """知识库文章表"""
    __tablename__ = 'knowledge_articles'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('knowledge_categories.id'))
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200))
    content = db.Column(db.Text)
    content_type = db.Column(db.String(20))  # pure_text, graphic, video
    tags = db.Column(db.JSON)  # 标签列表
    author = db.Column(db.String(50))
    source = db.Column(db.String(200))  # 来源
    is_published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<KnowledgeArticle {self.title}>'


class KnowledgeAnalysis(db.Model):
    """知识分析表 - 存储用户输入的分析内容"""
    __tablename__ = 'knowledge_analysis'

    id = db.Column(db.Integer, primary_key=True)
    source_content = db.Column(db.Text, nullable=False)  # 用户输入的原始内容
    source_type = db.Column(db.String(50))  # 来源类型：账号主页/视频文案/图文内容/纯文本
    content_summary = db.Column(db.Text)  # 内容摘要

    # 分析结果（JSON格式存储）
    analysis_dimensions = db.Column(db.JSON)  # 分析用了哪些维度
    analysis_result = db.Column(db.Text)  # 完整分析结果
    extracted_rules = db.Column(db.JSON)  # 提取的规则（按分类存储）

    # 状态
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rules = db.relationship('KnowledgeRule', backref='analysis', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<KnowledgeAnalysis {self.id}>'


class KnowledgeRule(db.Model):
    """知识规则表 - 存储从分析中提取的规则"""
    __tablename__ = 'knowledge_rules'

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('knowledge_analysis.id'))  # 关联的分析ID

    # 分类：关键词库/选题库/内容模板/运营规划/市场分析
    category = db.Column(db.String(50), nullable=False)

    # 规则内容
    rule_title = db.Column(db.String(200))  # 规则标题
    rule_content = db.Column(db.Text)  # 规则详情
    rule_type = db.Column(db.String(50))  # 规则类型：dimension(维度)/logic(逻辑)/structure(结构)/methodology(方法论)
    source_dimension = db.Column(db.String(100))  # 来源的分析维度

    # 状态
    status = db.Column(db.String(20), default='pending')  # pending/active/archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<KnowledgeRule {self.category} {self.rule_title}>'


class Client(db.Model):
    """客户表"""
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'))  # 所属渠道商
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'))  # 所属行业
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 所属用户（渠道商或超级管理员）
    name = db.Column(db.String(100), nullable=False)  # 客户名称
    
    # 业务类型：卖货类/服务类/两者都有
    business_type = db.Column(db.String(50))  
    # 产品类型：实物商品/批发供应链/其他
    product_type = db.Column(db.String(50))
    # 服务类型：本地生活/线上专业/知识付费/其他
    service_type = db.Column(db.String(50))
    
    # 地域范围：本地/跨区域/全球
    service_range = db.Column(db.String(50))
    # 具体城市/区域
    target_area = db.Column(db.String(100))
    
    # 品牌定位：个人IP/企业品牌/两者兼顾
    brand_type = db.Column(db.String(50))
    # 品牌/核心人物描述
    brand_description = db.Column(db.Text)
    
    # 语言风格：普通话/方言
    language_style = db.Column(db.String(50))
    # 具体方言
    dialect = db.Column(db.String(50))
    
    # 核心优势/卖点
    core_advantage = db.Column(db.Text)
    
    # 项目目标：流量/品牌/转化
    project_goals = db.Column(db.String(100))
    
    # 客户来源
    source = db.Column(db.String(50))
    
    # 客户档案（JSON格式存储完整信息）
    profile_data = db.Column(db.JSON)
    
    # 新增字段：主营业务、经营年限、其他补充
    main_product = db.Column(db.String(200))  # 主营业务（含占比）
    business_years = db.Column(db.String(20))  # 已经营年限
    other_info = db.Column(db.Text)  # 其他补充
    
    # 状态：收集中/已完善/服务中
    status = db.Column(db.String(20), default='collecting')
    
    contact = db.Column(db.String(100))  # 联系方式
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    keywords = db.relationship('Keyword', backref='client', lazy='dynamic')
    topics = db.relationship('Topic', backref='client', lazy='dynamic')
    contents = db.relationship('Content', backref='client', lazy='dynamic')
    monitors = db.relationship('Monitor', backref='client', lazy='dynamic')
    expert_outputs = db.relationship('ExpertOutput', backref='client', lazy='dynamic')
    industry = db.relationship('Industry', backref='clients')
    # 使用不同的 backref 名称避免冲突
    creator = db.relationship('User', backref=db.backref('created_clients', lazy='dynamic'), foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<Client {self.name}>'


class Keyword(db.Model):
    """关键词库表"""
    __tablename__ = 'keywords'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    keyword_type = db.Column(db.String(50))  # 核心词, 痛点词, 场景词, 地域词, etc.
    search_intent = db.Column(db.String(50))  # 搜索意图
    competition = db.Column(db.String(20))  # 竞争度
    is_monitored = db.Column(db.Boolean, default=False)  # 是否在监控中
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Keyword {self.keyword}>'


class Topic(db.Model):
    """选题库表"""
    __tablename__ = 'topics'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    topic_type = db.Column(db.String(50))  # 问题解决类, 认知颠覆类, etc.
    content_format = db.Column(db.String(50))  # 图文, 短视频
    target_audience = db.Column(db.String(100))
    priority = db.Column(db.Integer, default=0)  # 优先级
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Topic {self.title}>'


class Content(db.Model):
    """内容输出表"""
    __tablename__ = 'contents'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'))
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(db.String(20))  # graphic, video
    content = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='draft')  # draft, published
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Content {self.title}>'


class Monitor(db.Model):
    """舆情监控配置表"""
    __tablename__ = 'monitors'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    monitor_type = db.Column(db.String(20))  # link, keyword
    link_type = db.Column(db.String(20))  # 话题, 视频, 商品 (仅link类型)
    value = db.Column(db.String(500))  # 链接地址 or 关键词
    theme = db.Column(db.String(100))  # 监控主题
    status = db.Column(db.String(20), default='pending')  # pending, monitoring, paused
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Monitor {self.monitor_type}:{self.value}>'


class MonitorReport(db.Model):
    """舆情监控报告表"""
    __tablename__ = 'monitor_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    report_date = db.Column(db.Date, nullable=False)
    content = db.Column(db.Text)
    keywords_data = db.Column(db.JSON)  # 关键词热度数据
    links_data = db.Column(db.JSON)  # 链接数据
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<MonitorReport {self.client_id}:{self.report_date}>'


class ExpertOutput(db.Model):
    """专家输出记录表"""
    __tablename__ = 'expert_outputs'
    
    id = db.Column(db.Integer, primary_key=True)
    expert_id = db.Column(db.Integer, db.ForeignKey('experts.id'))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    output_type = db.Column(db.String(50))  # keyword, topic, content, analysis
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ExpertOutput {self.output_type}:{self.title}>'


class ChatSession(db.Model):
    """对话会话表"""
    __tablename__ = 'chat_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # 会话所属用户
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))  # 关联客户
    expert_id = db.Column(db.Integer, db.ForeignKey('experts.id'))  # 当前专家
    title = db.Column(db.String(200))  # 会话标题（首条消息摘要）
    is_active = db.Column(db.Boolean, default=True)  # 是否活跃
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='chat_sessions')
    client = db.relationship('Client', backref='chat_sessions')
    expert = db.relationship('Expert', backref='chat_sessions')
    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic', 
                              order_by='ChatMessage.created_at')
    
    def __repr__(self):
        return f'<ChatSession {self.id}:{self.title}>'


class ChatMessage(db.Model):
    """对话消息表"""
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # system, user, assistant
    content = db.Column(db.Text, nullable=False)  # 消息内容
    expert_id = db.Column(db.Integer, db.ForeignKey('experts.id'))  # 回复的专家
    extra_data = db.Column(db.JSON)  # 额外信息（如专家名称、命令等）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    expert = db.relationship('Expert', backref='chat_messages')
    
    def __repr__(self):
        return f'<ChatMessage {self.id}:{self.role}>'
