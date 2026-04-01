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
    role = db.Column(db.String(20), default='user')  # super_admin, admin, public_user, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def is_super_admin(self):
        return self.role == 'super_admin'


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
    dimension_id = db.Column(db.Integer, db.ForeignKey('analysis_dimensions.id'))  # 关联的分析维度

    # 分类：关键词库/选题库/内容模板/运营规划/市场分析
    category = db.Column(db.String(50), nullable=False)

    # 规则内容
    rule_title = db.Column(db.String(200))  # 规则标题
    rule_content = db.Column(db.Text)  # 规则详情
    rule_type = db.Column(db.String(50))  # 规则类型：dimension(维度)/logic(逻辑)/structure(结构)/methodology(方法论)
    source_dimension = db.Column(db.String(100))  # 来源的分析维度
    source_category = db.Column(db.String(50))  # 来源的一级分类（account/content/methodology）
    source_sub_category = db.Column(db.String(100))  # 来源的二级分类
    dimension_name = db.Column(db.String(100))  # 维度名称

    # 适用场景和人群
    applicable_scenarios = db.Column(db.JSON)  # 适用场景列表 ['种草', '带货', '品牌宣传']
    applicable_audiences = db.Column(db.JSON)  # 适用人群列表 ['年轻女性', '白领', '宝爸']
    keywords = db.Column(db.JSON)  # 关键词标签

    # 适用平台
    platforms = db.Column(db.JSON)  # 适用平台 ['douyin', 'xhs', 'bilibili']

    # 效果数据
    usage_count = db.Column(db.Integer, default=0)  # 使用次数
    success_rate = db.Column(db.Float)  # 成功率

    # 状态
    status = db.Column(db.String(20), default='pending')  # pending/active/archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dimension = db.relationship('AnalysisDimension', backref='knowledge_rules')

    def __repr__(self):
        return f'<KnowledgeRule {self.category} {self.rule_title}>'


class KnowledgeAccount(db.Model):
    """账号主表 - 手动录入的账号信息"""
    __tablename__ = 'knowledge_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 账号名称
    platform = db.Column(db.String(50))  # 平台（douyin, xhs, bilibili等）
    url = db.Column(db.String(500))  # 主页链接
    current_data = db.Column(db.JSON)  # 最新账号数据（粉丝数、简介、视频数等）
    status = db.Column(db.String(20), default='active')  # 状态（active/inactive）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 详细信息（与客户表对应）
    business_type = db.Column(db.String(50))  # 业务类型：卖货类/服务类/两者都有
    product_type = db.Column(db.String(50))  # 产品类型：实物商品/批发供应链/其他
    service_type = db.Column(db.String(50))  # 服务类型：本地生活/线上专业/知识付费/其他
    service_range = db.Column(db.String(50))  # 地域范围：本地/跨区域/全球
    target_area = db.Column(db.String(100))  # 具体城市/区域
    brand_type = db.Column(db.String(50))  # 品牌定位：个人IP/企业品牌/两者兼顾
    language_style = db.Column(db.String(50))  # 语言风格：普通话/方言
    main_product = db.Column(db.String(200))  # 主营业务（含占比）
    target_user = db.Column(db.String(50))  # 目标用户：付费者/使用者

    # ========== 账号分析增强字段 ==========
    # 核心业务描述
    core_business = db.Column(db.String(200))  # 核心业务（如：桶装水配送、灌香肠加工）
    # 核心关键词（1-3个最主要的流量/转化关键词）
    core_keywords = db.Column(db.JSON)  # ['桶装水', '定制水', '矿泉水']
    # 关键词类型（品类词/痛点词/场景词）
    keyword_types = db.Column(db.JSON)  # {'core': '品类词', 'secondary': ['痛点词', '场景词']}
    # 账号定位
    account_positioning = db.Column(db.String(200))  # 人设+业务+目标人群
    # 内容策略（流量型/转化型/信任型占比）
    content_strategy = db.Column(db.JSON)  # {'流量型': '60%', '转化型': '30%', '信任型': '10%'}
    # 目标人群画像
    target_audience = db.Column(db.JSON)  # [{'人群': '餐饮老板', '需求': '便宜'}]
    # 完整分析结果（JSON）
    analysis_result = db.Column(db.JSON)

    # ========== 增量分析控制字段 ==========
    # 昵称分析缓存
    last_nickname = db.Column(db.String(100))  # 上次分析的昵称
    nickname_analyzed_at = db.Column(db.DateTime)  # 昵称分析时间
    # 简介分析缓存
    last_bio = db.Column(db.Text)  # 上次分析的简介
    bio_analyzed_at = db.Column(db.DateTime)  # 简介分析时间
    # 其他分析缓存（账号定位、市场分析、运营规划）
    other_analyzed_at = db.Column(db.DateTime)  # 其他分析时间

    # ========== 自动分析配置字段 ==========
    # 控制创建/更新账号时是否自动触发特定分析
    # 默认全部关闭，需要用户手动触发分析
    auto_analysis_config = db.Column(db.JSON, default=lambda: {
        'on_create': {
            'profile': False,           # 账号画像分析（目标人群、关键词等）
            'nickname': False,          # 昵称分析
            'bio': False,              # 简介分析
            'account_positioning': False,  # 账号定位分析
            'keyword_library': False,   # 关键词库分析
            'market_analysis': False,  # 市场分析
            'operation_planning': False   # 运营规划分析
        },
        'on_update': {
            'profile': False,           # 账号画像分析
            'nickname': False,          # 昵称分析
            'bio': False,              # 简介分析
            'account_positioning': False,  # 账号定位分析
            'keyword_library': False,  # 关键词库分析
            'market_analysis': False,  # 市场分析
            'operation_planning': False   # 运营规划分析
        }
    })

    # 人设定位（陪伴者/教导者/崇拜者/陪衬者/搞笑者）
    persona_role = db.Column(db.String(50))  # 陪伴者-我懂你/教导者-我教你/崇拜者-秀自己/陪衬者-不如你/搞笑者-逗笑你
    # 商业定位（引流/卖货）
    commercial_positioning = db.Column(db.String(50))  # 引流/卖货
    # 变现类型（单品/赛道级）- 根据主营业务判断
    monetization_type = db.Column(db.String(50))  # 单品/赛道级

    # ========== 内容布局字段 ==========
    content_persona = db.Column(db.Integer, default=0)  # 人设IP类内容数量
    content_topic = db.Column(db.Integer, default=0)  # 主题内容数量
    content_daily = db.Column(db.Integer, default=0)  # 日常运营数量
    # 内容布局（文本描述）
    persona_type = db.Column(db.Text)  # 人设IP类描述
    topic_content = db.Column(db.Text)  # 主题内容描述
    daily_operation = db.Column(db.Text)  # 日常运营描述

    # Relationships
    history = db.relationship('KnowledgeAccountHistory', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    contents = db.relationship('KnowledgeContent', backref='account', lazy='dynamic')

    def __repr__(self):
        return f'<KnowledgeAccount {self.name}>'


class KnowledgeAccountHistory(db.Model):
    """账号历史表 - 记录账号信息变更历史"""
    __tablename__ = 'knowledge_account_history'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('knowledge_accounts.id'), nullable=False)
    data = db.Column(db.JSON)  # 历史数据（粉丝数、简介等）
    change_note = db.Column(db.String(200))  # 变更说明
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<KnowledgeAccountHistory {self.id}:{self.account_id}>'


class KnowledgeContent(db.Model):
    """内容表 - 手动录入或图片识别的内容"""
    __tablename__ = 'knowledge_contents'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('knowledge_accounts.id'), nullable=True)  # 关联账号ID
    title = db.Column(db.String(200))  # 内容标题
    content_url = db.Column(db.String(500))  # 内容链接
    content_type = db.Column(db.String(50))  # 内容类型（video, image_text, plain_text）
    source_type = db.Column(db.String(50))  # 来源类型（link手动录入/image图片识别/manual手动录入）
    content_data = db.Column(db.JSON)  # 内容详细数据（JSON）
    analysis_result = db.Column(db.JSON)  # 分析结果（JSON）

    # ========== 内容关键词分析字段 ==========
    # 标题关键词列表
    title_keywords = db.Column(db.JSON)  # ['定制水', '婚宴', '厂家直销']
    # 内容正文关键词列表
    content_keywords = db.Column(db.JSON)  # ['矿泉水', '桶装水', '配送']
    # 每个关键词的用途分析
    # {'定制水': '流量词-品类词', '婚宴': '精准流量词-场景词', '厂家直销': '转化词'}
    keyword_usages = db.Column(db.JSON)
    # 选题逻辑 - 为什么要做这个选题
    topic_logic = db.Column(db.Text)  # 这个内容是为了获取哪个关键词的流量
    # 对应的账号核心关键词（用于建立关联）
    related_core_keywords = db.Column(db.JSON)  # 关联的核心关键词

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<KnowledgeContent {self.title}>'


# ========== 模板管理相关表 ==========

class ReportTemplate(db.Model):
    """报告模板表"""
    __tablename__ = 'report_templates'

    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(100), nullable=False)  # 模板名称
    # 模板类型：market_analysis(市场分析) / keyword(关键词库) / topic(选题库) / operation(运营规划)
    template_type = db.Column(db.String(50), nullable=False)
    # 模板分类：universal(通用) / industry(行业) / custom(自定义)
    template_category = db.Column(db.String(50), default='universal')
    template_content = db.Column(db.Text)  # 模板内容（Markdown + 变量）
    variables_config = db.Column(db.JSON)  # 变量配置
    version = db.Column(db.String(20), default='1.0')  # 版本号
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='created_templates')

    def __repr__(self):
        return f'<ReportTemplate {self.template_name}>'


class ContentTemplate(db.Model):
    """内容模板表"""
    __tablename__ = 'content_templates'

    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(100), nullable=False)  # 模板名称
    # 内容类型：graphic(图文) / video(短视频) / long_text(长文字)
    content_type = db.Column(db.String(50), nullable=False)
    template_category = db.Column(db.String(50), default='universal')  # 模板分类
    template_structure = db.Column(db.JSON)  # 模板结构
    template_content = db.Column(db.Text)  # 示例内容
    version = db.Column(db.String(20), default='1.0')
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='created_content_templates')

    def __repr__(self):
        return f'<ContentTemplate {self.template_name}>'


class TemplateDependency(db.Model):
    """模板依赖关系表 - 记录模板之间的联动关系"""
    __tablename__ = 'template_dependencies'

    id = db.Column(db.Integer, primary_key=True)
    # 源模板类型：market_analysis / keyword / topic / operation / knowledge
    source_template_type = db.Column(db.String(50), nullable=False)
    # 目标模板类型
    target_template_type = db.Column(db.String(50), nullable=False)
    # 依赖类型：full_refresh(完全刷新) / partial_update(部分更新)
    dependency_type = db.Column(db.String(50), default='full_refresh')
    update_rules = db.Column(db.JSON)  # 更新规则
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TemplateDependency {self.source_template_type} -> {self.target_template_type}>'


class TemplateRefreshLog(db.Model):
    """模板刷新日志表"""
    __tablename__ = 'template_refresh_logs'

    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50))  # 被刷新的模板类型
    trigger_type = db.Column(db.String(50))  # 触发类型：manual(手动) / auto(自动)
    source_type = db.Column(db.String(50))  # 触发来源
    source_id = db.Column(db.Integer)  # 触发来源ID
    status = db.Column(db.String(20), default='pending')  # pending/running/success/failed
    result = db.Column(db.Text)  # 执行结果
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f'<TemplateRefreshLog {self.template_type} {self.status}>'


class TemplateContentItem(db.Model):
    """模板内容条目表 - 按条管理的模板内容块，可排序"""
    __tablename__ = 'template_content_items'

    id = db.Column(db.Integer, primary_key=True)
    # 关联模板：template_type = report | content，template_id 对应 report_templates.id 或 content_templates.id
    template_type = db.Column(db.String(20), nullable=False)
    template_id = db.Column(db.Integer, nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    content = db.Column(db.Text, nullable=False)  # 该条目的 Markdown + 变量内容
    natural_language_hint = db.Column(db.Text)  # 可选：创建/编辑时的自然语言描述
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<TemplateContentItem {self.template_type}#{self.template_id} order={self.sort_order}>'


class TemplateEditHistory(db.Model):
    """模板编辑历史表 - 每次保存时记录完整内容快照"""
    __tablename__ = 'template_edit_histories'

    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(20), nullable=False)
    template_id = db.Column(db.Integer, nullable=False)
    snapshot_content = db.Column(db.Text)  # 保存时的完整模板内容
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='template_edit_histories')

    def __repr__(self):
        return f'<TemplateEditHistory {self.template_type}#{self.template_id} at {self.changed_at}>'


# ========== 知识库-方法论相关表（读书笔记/电子书整理解析入库） ==========
# methodology_category: 消费心理学/关键词筛选/人设方法论/视觉设计/运营策略/通用 等

class PersonaMethod(db.Model):
    """知识库方法论表 - 存储从读书笔记、电子书中解析并入库的方法论（不限于人设）"""
    __tablename__ = 'persona_methods'

    id = db.Column(db.Integer, primary_key=True)
    methodology_category = db.Column(db.String(50), default='general')  # 归类：consumer_psychology/keyword_screening/persona/visual_design/operation/general
    name = db.Column(db.String(100), nullable=False)  # 方法论名称
    source_book = db.Column(db.String(200))  # 来源书籍/资料
    author = db.Column(db.String(100))  # 作者
    method_summary = db.Column(db.Text)  # 方法论摘要
    applicable_scenario = db.Column(db.JSON)  # 适用场景列表
    applicable_audience = db.Column(db.JSON)  # 适用人群列表
    related_dimensions = db.Column(db.JSON)  # 关联的分析维度ID列表
    usage_guide = db.Column(db.Text)  # 使用指南
    keywords = db.Column(db.JSON)  # 关键词标签
    tags = db.Column(db.JSON)  # 分类标签
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='persona_methods')

    def __repr__(self):
        return f'<PersonaMethod {self.name}>'


class PersonaRole(db.Model):
    """人设角色表 - 存储具体的人设角色模板"""
    __tablename__ = 'persona_roles'

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(100), nullable=False)  # 角色名称
    role_type = db.Column(db.String(50))  # 角色类型：专家/创业者/普通人/等
    description = db.Column(db.Text)  # 角色描述
    personality_traits = db.Column(db.JSON)  # 人格特征
    speech_style = db.Column(db.JSON)  # 说话风格
    background_story = db.Column(db.Text)  # 背景故事
    applicable_industry = db.Column(db.JSON)  # 适用行业
    case_examples = db.Column(db.JSON)  # 案例示例
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='persona_roles')

    def __repr__(self):
        return f'<PersonaRole {self.role_name}>'


# ========== 场景库相关表 ==========

class UsageScenario(db.Model):
    """使用场景表 - 产品的使用场景"""
    __tablename__ = 'usage_scenarios'

    id = db.Column(db.Integer, primary_key=True)
    scenario_name = db.Column(db.String(100), nullable=False)  # 场景名称
    industry = db.Column(db.String(50))  # 所属行业
    scenario_description = db.Column(db.Text)  # 场景描述
    target_users = db.Column(db.JSON)  # 目标用户群体
    pain_points = db.Column(db.JSON)  # 痛点
    needs = db.Column(db.JSON)  # 需求
    keywords = db.Column(db.JSON)  # 场景关键词
    related_products = db.Column(db.JSON)  # 相关产品
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<UsageScenario {self.scenario_name}>'


class DemandScenario(db.Model):
    """需求场景表 - 用户需求的场景"""
    __tablename__ = 'demand_scenarios'

    id = db.Column(db.Integer, primary_key=True)
    scenario_name = db.Column(db.String(100), nullable=False)  # 场景名称
    demand_type = db.Column(db.String(50))  # 需求类型：功能/情感/社交
    scenario_description = db.Column(db.Text)  # 场景描述
    trigger_condition = db.Column(db.JSON)  # 触发条件
    user_goals = db.Column(db.JSON)  # 用户目标
    emotional_needs = db.Column(db.JSON)  # 情感需求
    keywords = db.Column(db.JSON)  # 关键词
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<DemandScenario {self.scenario_name}>'


class PainPoint(db.Model):
    """痛点表 - 用户痛点"""
    __tablename__ = 'pain_points'

    id = db.Column(db.Integer, primary_key=True)
    pain_point_name = db.Column(db.String(100), nullable=False)  # 痛点名称
    industry = db.Column(db.String(50))  # 所属行业
    pain_type = db.Column(db.String(50))  # 痛点类型：功能/体验/情感/成本
    description = db.Column(db.Text)  # 痛点描述
    severity = db.Column(db.String(20))  # 严重程度：高/中/低
    affected_users = db.Column(db.JSON)  # 受影响用户
    current_solutions = db.Column(db.JSON)  # 现有解决方案
    opportunities = db.Column(db.JSON)  # 机会点
    keywords = db.Column(db.JSON)  # 关键词
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PainPoint {self.pain_point_name}>'


# ========== 热点库相关表 ==========

class HotTopic(db.Model):
    """热点话题表 - 实时热点"""
    __tablename__ = 'hot_topics'

    id = db.Column(db.Integer, primary_key=True)
    topic_name = db.Column(db.String(200), nullable=False)  # 话题名称
    topic_source = db.Column(db.String(50))  # 来源：douyin/xhs/weibo/zhihu
    topic_url = db.Column(db.String(500))  # 话题链接
    hot_level = db.Column(db.String(20))  # 热度等级：高/中/低
    category = db.Column(db.String(50))  # 分类
    description = db.Column(db.Text)  # 描述
    related_keywords = db.Column(db.JSON)  # 相关关键词
    related_industry = db.Column(db.JSON)  # 相关行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    start_date = db.Column(db.Date)  # 开始日期
    end_date = db.Column(db.Date)  # 结束日期
    status = db.Column(db.String(20), default='active')  # active/expired
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<HotTopic {self.topic_name}>'


class SeasonalTopic(db.Model):
    """季节性话题表 - 节气、节日等周期性话题"""
    __tablename__ = 'seasonal_topics'

    id = db.Column(db.Integer, primary_key=True)
    topic_name = db.Column(db.String(100), nullable=False)  # 话题名称
    topic_type = db.Column(db.String(50))  # 类型：节日/节气/电商节/行业日
    topic_date = db.Column(db.Date)  # 日期
    recurrence = db.Column(db.String(20))  # 循环类型： yearly/monthly/one-time
    description = db.Column(db.Text)  # 描述
    marketing_angles = db.Column(db.JSON)  # 营销角度
    content_suggestions = db.Column(db.JSON)  # 内容建议
    related_industry = db.Column(db.JSON)  # 相关行业
    keywords = db.Column(db.JSON)  # 关键词
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SeasonalTopic {self.topic_name}>'


# ========== 内容素材库相关表 ==========

class ContentTitle(db.Model):
    """标题库表"""
    __tablename__ = 'content_titles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # 标题内容
    title_type = db.Column(db.String(50))  # 标题类型：疑问/数字/对比/情感
    industry = db.Column(db.String(50))  # 所属行业
    keywords = db.Column(db.JSON)  # 包含关键词
    performance = db.Column(db.JSON)  # 表现数据
    is_template = db.Column(db.Boolean, default=False)  # 是否为模板
    template_variables = db.Column(db.JSON)  # 模板变量
    usage_count = db.Column(db.Integer, default=0)  # 使用次数
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentTitle {self.title[:30]}>'


class ContentHook(db.Model):
    """钩子库表 - 开头钩子"""
    __tablename__ = 'content_hooks'

    id = db.Column(db.Integer, primary_key=True)
    hook_content = db.Column(db.Text, nullable=False)  # 钩子内容
    hook_type = db.Column(db.String(50))  # 钩子类型：提问/悬念/冲突/数字
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    is_template = db.Column(db.Boolean, default=False)
    template_variables = db.Column(db.JSON)
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentHook {self.hook_content[:30]}>'


class ContentStructure(db.Model):
    """内容结构表 - 内容框架"""
    __tablename__ = 'content_structures'

    id = db.Column(db.Integer, primary_key=True)
    structure_name = db.Column(db.String(100), nullable=False)  # 结构名称
    content_type = db.Column(db.String(50))  # 内容类型：video/graphic/long_text
    industry = db.Column(db.String(50))  # 所属行业
    structure_steps = db.Column(db.JSON)  # 结构步骤
    description = db.Column(db.Text)  # 描述
    applicable_scenarios = db.Column(db.JSON)  # 适用场景
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentStructure {self.structure_name}>'


class ContentEnding(db.Model):
    """结尾引导表"""
    __tablename__ = 'content_endings'

    id = db.Column(db.Integer, primary_key=True)
    ending_content = db.Column(db.Text, nullable=False)  # 结尾内容
    ending_type = db.Column(db.String(50))  # 结尾类型：引导评论/引导关注/引导购买
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    is_template = db.Column(db.Boolean, default=False)
    template_variables = db.Column(db.JSON)
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentEnding {self.ending_content[:30]}>'


# ========== 新内容素材库表（扩展维度） ==========

class ContentCover(db.Model):
    """封面库表"""
    __tablename__ = 'content_covers'

    id = db.Column(db.Integer, primary_key=True)
    cover_content = db.Column(db.Text, nullable=False)  # 封面内容描述
    cover_type = db.Column(db.String(50))  # 封面类型：图文/纯文字/人物/产品/场景/对比/情绪/合集
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    is_template = db.Column(db.Boolean, default=False)
    template_variables = db.Column(db.JSON)
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentCover {self.cover_content[:30]}>'


class ContentTopic(db.Model):
    """选题库表"""
    __tablename__ = 'content_topics'

    id = db.Column(db.Integer, primary_key=True)
    topic_content = db.Column(db.Text, nullable=False)  # 选题内容
    topic_type = db.Column(db.String(50))  # 选题类型：痛点/痒点/热点/干货/娱乐/情感/知识/评测/教程
    industry = db.Column(db.String(50))  # 所属行业
    keywords = db.Column(db.JSON)  # 关键词
    applicable_scenarios = db.Column(db.JSON)  # 适用场景
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentTopic {self.topic_content[:30]}>'


class ContentPsychology(db.Model):
    """心理库表"""
    __tablename__ = 'content_psychologies'

    id = db.Column(db.Integer, primary_key=True)
    psychology_content = db.Column(db.Text, nullable=False)  # 心理引导内容
    psychology_type = db.Column(db.String(50))  # 心理类型：恐惧/贪婪/好奇/从众/权威/稀缺/损失/认同/攀比/情感
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentPsychology {self.psychology_content[:30]}>'


class ContentCommercial(db.Model):
    """商业库表"""
    __tablename__ = 'content_commercials'

    id = db.Column(db.Integer, primary_key=True)
    commercial_content = db.Column(db.Text, nullable=False)  # 商业内容
    commercial_type = db.Column(db.String(50))  # 商业类型：种草/带货/品牌/引流/转化/口碑/促销/招商/加盟
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentCommercial {self.commercial_content[:30]}>'


class ContentWhyPopular(db.Model):
    """爆款库表"""
    __tablename__ = 'content_why_populars'

    id = db.Column(db.Integer, primary_key=True)
    reason_content = db.Column(db.Text, nullable=False)  # 爆款原因内容
    reason_type = db.Column(db.String(50))  # 原因类型：内容好/选题好/时机好/平台推/互动高/转化高/复盘
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentWhyPopular {self.reason_content[:30]}>'


class ContentTag(db.Model):
    """标签库表"""
    __tablename__ = 'content_tags'

    id = db.Column(db.Integer, primary_key=True)
    tag_content = db.Column(db.Text, nullable=False)  # 标签内容
    tag_type = db.Column(db.String(50))  # 标签类型：话题/关键词/品牌/人物/场景/情感/行为
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentTag {self.tag_content[:30]}>'


class ContentCharacter(db.Model):
    """人物库表"""
    __tablename__ = 'content_characters'

    id = db.Column(db.Integer, primary_key=True)
    character_content = db.Column(db.Text, nullable=False)  # 人物设计内容
    character_type = db.Column(db.String(50))  # 人物类型：人设/身份/角色/形象/性格/语气/背景
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentCharacter {self.character_content[:30]}>'


class ContentForm(db.Model):
    """形式库表"""
    __tablename__ = 'content_forms'

    id = db.Column(db.Integer, primary_key=True)
    form_content = db.Column(db.Text, nullable=False)  # 形式内容描述
    form_type = db.Column(db.String(50))  # 形式类型：口播/剧情/Vlog/测评/教程/知识/娱乐/直播/图文
    industry = db.Column(db.String(50))  # 所属行业
    applicable_scenarios = db.Column(db.JSON)  # 适用场景
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentForm {self.form_content[:30]}>'


class ContentInteraction(db.Model):
    """互动库表"""
    __tablename__ = 'content_interactions'

    id = db.Column(db.Integer, primary_key=True)
    interaction_content = db.Column(db.Text, nullable=False)  # 互动内容
    interaction_type = db.Column(db.String(50))  # 互动类型：问答/投票/挑战/抽奖/评论/连麦/合拍/回应
    industry = db.Column(db.String(50))  # 所属行业
    applicable_content_types = db.Column(db.JSON)  # 适用内容类型
    performance = db.Column(db.JSON)  # 表现数据
    usage_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContentInteraction {self.interaction_content[:30]}>'


# ========== 分析维度配置 ==========

class AnalysisDimension(db.Model):
    """分析维度配置表 - 可配置的爆款拆解分析维度"""
    __tablename__ = 'analysis_dimensions'

    id = db.Column(db.Integer, primary_key=True)

    # 维度基本信息
    name = db.Column(db.String(50), nullable=False)  # 维度名称（如：标题、封面）
    code = db.Column(db.String(50), unique=True, nullable=False)  # 维度编码（如：title、cover）
    icon = db.Column(db.String(50))  # 图标类名
    description = db.Column(db.Text)  # 维度说明

    # 分类体系
    category = db.Column(db.String(50), nullable=False)  # 一级分类：account/content/methodology
    sub_category = db.Column(db.String(50))  # 二级分类
    category_group = db.Column(db.String(50))  # 分类组（用于前端分组显示）

    # 素材库关联
    related_material_type = db.Column(db.String(50))  # 关联的素材库类型

    # 规则库关联 - 分析维度对应的入库规则配置
    rule_category = db.Column(db.String(50))  # 入库后的规则分类：keywords/topic/template/operation/market
    rule_type = db.Column(db.String(100))  # 入库后的规则类型（如 account_design_nickname、content_title 等）
    prompt_template = db.Column(db.Text)  # LLM分析时的提示词模板/建议项
    # 方案A：与公式要素一致，供 LLM 按维度打分
    examples = db.Column(db.Text)  # 示例（多个用 | 分隔，如：关注送一罐|私信咨询|到店试吃）
    usage_tips = db.Column(db.Text)  # 识别技巧/注意事项（如：行动号召是让用户做什么，联系方式是留电话/微信/地址）
    applicable_audience = db.Column(db.Text)  # 适用人群（如：创业者、企业家、B2B销售，用 | 分隔）

    # ========== 市场洞察专用字段 ==========
    # 触发条件 - JSON格式，配置何时启用此维度
    trigger_conditions = db.Column(db.JSON, default=dict)  # {
    #     "business_types": ["service", "product"],  # 业务类型触发
    #     "has_elderly": true,       # 涉及老人
    #     "has_baby": true,          # 涉及宝宝
    #     "has_enterprise": true,    # 有企业客户
    #     "is_gift": true,           # 礼品场景
    #     "search_stage": "all"      # 搜前/搜中/搜后/全部
    # }
    # 内容模板 - 用于渲染后发给LLM的内容
    content_template = db.Column(db.Text)  # 【维度名称】\n内容...
    # 重要性 - 数字越大越重要，用于排序
    importance = db.Column(db.Integer, default=1)  # 1-5星

    # LLM权重 - 用于画像分析时各维度的权重（满分10分），不影响前台显示
    weight = db.Column(db.Float, default=1.0)  # 1.0-10.0

    # 状态
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)  # 是否为默认维度
    sort_order = db.Column(db.Integer, default=0)

    # 使用统计
    usage_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<AnalysisDimension {self.code} {self.name}>'


class AnalysisDimensionCategoryOrder(db.Model):
    """分析维度二级分类排序表 - 存储每个一级分类下二级分类的显示顺序"""
    __tablename__ = 'analysis_dimension_category_orders'

    id = db.Column(db.Integer, primary_key=True)

    # 分类信息
    category = db.Column(db.String(50), nullable=False)  # 一级分类：account/content/methodology
    sub_category = db.Column(db.String(50), nullable=False)  # 二级分类

    # 排序值
    sort_order = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint('category', 'sub_category', name='uix_category_sub_category'),
    )

    def __repr__(self):
        return f'<AnalysisDimensionCategoryOrder {self.category}/{self.sub_category} order={self.sort_order}>'


# ========== 公式要素类型配置 ==========

class FormulaElementType(db.Model):
    """公式要素类型配置表 - 存储昵称/简介分析的公式要素定义"""
    __tablename__ = 'formula_element_types'

    id = db.Column(db.Integer, primary_key=True)

    # 所属分析类型
    sub_category = db.Column(db.String(50), nullable=False)  # nickname_analysis / bio_analysis

    # 要素基本信息
    name = db.Column(db.String(50), nullable=False)  # 要素名称（如：产品词、身份标签）
    code = db.Column(db.String(50), nullable=False)  # 要素编码（如：product_word、identity_tag）
    description = db.Column(db.Text)  # 要素定义说明
    examples = db.Column(db.Text)  # 示例（多个，用 | 分隔，如：香肠|茶叶|手机）

    # 排序和状态
    priority = db.Column(db.Integer, default=0)  # 优先级（数字越小越靠前）
    is_active = db.Column(db.Boolean, default=True)  # 是否启用

    # 用途说明（用于 prompt 中）
    usage_tips = db.Column(db.Text)  # 使用场景/注意事项

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('sub_category', 'code', name='uix_sub_category_code'),
    )

    def __repr__(self):
        return f'<FormulaElementType {self.sub_category}/{self.code}>'


class FormulaElementSuggestion(db.Model):
    """公式要素建议表 - LLM分析时发现的新要素建议"""
    __tablename__ = 'formula_element_suggestions'

    id = db.Column(db.Integer, primary_key=True)

    # 关联账号分析（可选）
    account_id = db.Column(db.Integer, db.ForeignKey('knowledge_accounts.id'))

    # 建议的要素信息
    sub_category = db.Column(db.String(50), nullable=False)  # nickname_analysis / bio_analysis
    name = db.Column(db.String(50), nullable=False)  # 要素名称
    code = db.Column(db.String(50), nullable=False)  # 要素编码
    description = db.Column(db.Text)  # 要素定义说明
    example = db.Column(db.String(200))  # 示例（来自分析内容）

    # 来源信息
    source_nickname = db.Column(db.String(100))  # 发现的昵称/简介
    source_formula = db.Column(db.Text)  # 发现时的 formula

    # 审核状态
    status = db.Column(db.String(20), default='pending')  # pending/approved/rejected

    # 审核信息
    reviewed_at = db.Column(db.DateTime)  # 审核时间
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 审核人
    review_note = db.Column(db.Text)  # 审核备注

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('sub_category', 'code', name='uix_suggestion_sub_category_code'),
    )

    def __repr__(self):
        return f'<FormulaElementSuggestion {self.sub_category}/{self.code}>'


# ========== 人群画像生成模块 ==========

class PersonaSession(db.Model):
    """人群画像会话表 - 存储每次生成的结果"""
    __tablename__ = 'persona_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # 会话基本信息
    name = db.Column(db.String(100))  # 会话名称（如：进口奶粉人群分析）
    industry = db.Column(db.String(50))  # 行业名称
    business_type = db.Column(db.String(20))  # 业务类型：toc/tob/both

    # 使用方与购买方关系
    buyer_equals_user = db.Column(db.Boolean, default=True)  # 购买方是否等于使用方

    # 状态
    status = db.Column(db.String(20), default='draft')  # draft/processing/completed/failed

    # 原始输入
    input_data = db.Column(db.JSON)  # 存储原始输入数据

    # 生成结果（JSON格式）
    user_problems_data = db.Column(db.JSON)  # 使用方问题列表（避免与backref冲突）
    buyer_concerns = db.Column(db.JSON)  # 付费方顾虑列表
    portraits = db.Column(db.JSON)  # 人群画像列表

    # 使用统计
    portrait_count = db.Column(db.Integer, default=0)  # 生成的人群画像数量

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='persona_sessions')

    def __repr__(self):
        return f'<PersonaSession {self.id} {self.industry}>'


class PersonaUserProblem(db.Model):
    """使用方问题表 - 产品/服务要解决的核心问题"""
    __tablename__ = 'persona_user_problems'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('persona_sessions.id'), nullable=False)

    # 问题信息
    name = db.Column(db.String(100), nullable=False)  # 问题名称（如：乳糖不耐受）
    description = db.Column(db.Text)  # 问题描述
    specific_symptoms = db.Column(db.Text)  # 具体表现（如：喝奶后腹泻、胀气）
    severity = db.Column(db.String(20))  # 严重程度：高/中/低
    user_awareness = db.Column(db.String(20))  # 用户意识：有意识/无意识

    # 触发场景
    trigger_scenario = db.Column(db.Text)  # 问题触发场景

    # 排序
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship('PersonaSession', backref='user_problems')

    def __repr__(self):
        return f'<PersonaUserProblem {self.name}>'


class PersonaBuyerConcern(db.Model):
    """付费方顾虑表 - 购买决策时的心理障碍"""
    __tablename__ = 'persona_buyer_concerns'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('persona_sessions.id'), nullable=False)

    # 顾虑信息
    concern_type = db.Column(db.String(50), nullable=False)  # 顾虑类型：真假/价格/选择/信任/其他
    name = db.Column(db.String(100), nullable=False)  # 顾虑名称
    description = db.Column(db.Text)  # 具体描述
    estimated_ratio = db.Column(db.String(20))  # 预估占比

    # 排序
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    session = db.relationship('PersonaSession', backref='buyer_concern_items')  # 避免与JSON字段buyer_concerns冲突

    def __repr__(self):
        return f'<PersonaBuyerConcern {self.concern_type} {self.name}>'


class PersonaPortrait(db.Model):
    """人群画像表 - 精准长尾细分人群"""
    __tablename__ = 'persona_portraits'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('persona_sessions.id'), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey('persona_user_problems.id'))

    # 画像基本信息
    name = db.Column(db.String(100), nullable=False)  # 画像名称（如：乳糖不耐受宝宝妈妈）
    batch_number = db.Column(db.Integer, default=1)  # 批次号（按问题分批）

    # 使用方信息
    user_description = db.Column(db.Text)  # 使用方特征描述
    user_core_problem = db.Column(db.Text)  # 使用方核心问题
    user_specific_symptoms = db.Column(db.Text)  # 具体表现
    user_pain_level = db.Column(db.String(20))  # 痛点程度

    # 购买方信息（如果与使用方分开）
    buyer_description = db.Column(db.Text)  # 购买方特征描述
    buyer_core_problem = db.Column(db.Text)  # 购买方核心问题
    buyer_concerns = db.Column(db.JSON)  # 购买方顾虑详情（JSON数组）

    # 用户旅程
    user_journey = db.Column(db.Text)  # 用户旅程描述

    # 内容选题
    content_topics = db.Column(db.JSON)  # 内容选题方向（JSON数组）
    search_keywords = db.Column(db.JSON)  # 用户会搜索的关键词

    # 排序
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = db.relationship('PersonaSession', backref='portrait_list')
    problem = db.relationship('PersonaUserProblem', backref='problem_portraits')

    def __repr__(self):
        return f'<PersonaPortrait {self.name}>'
