"""
公开内容生成平台 - 模块化架构

目录结构：
├── public_models.py           # 公开用户相关模型
├── public_auth.py             # 认证服务
├── public_content_generator.py # 内容生成服务
├── public_quota_manager.py    # 配额管理服务
├── public_template_matcher.py  # 模板匹配服务
├── public_cache.py            # 缓存服务
└── public_api.py              # API路由

性能优化策略：
1. 内存缓存：热点数据（行业、目标客户模板）缓存到内存
2. 数据库索引：高频查询字段添加索引
3. 分页加载：关键词/选题分页查询
4. 异步处理：LLM调用异步化
5. 连接池：数据库连接复用
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from models.models import db


# =============================================================================
# 一、公开用户相关模型
# =============================================================================

class PublicUser(db.Model):
    """公开用户表"""
    __tablename__ = 'public_users'
    __table_args__ = (
        db.Index('idx_public_user_email', 'email'),
        db.Index('idx_public_user_is_premium', 'is_premium'),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nickname = db.Column(db.String(80))

    # 邮箱验证
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    verification_expires = db.Column(db.DateTime)

    # 付费状态
    is_premium = db.Column(db.Boolean, default=False)
    premium_plan = db.Column(db.String(50), default='free')
    premium_expires = db.Column(db.DateTime)
    token_balance = db.Column(db.Integer, default=0)

    # 配额（免费用户用）
    daily_free_count = db.Column(db.Integer, default=0)
    daily_free_reset_at = db.Column(db.Date)
    monthly_generation_count = db.Column(db.Integer, default=0)
    monthly_token_count = db.Column(db.Integer, default=0)
    monthly_reset_at = db.Column(db.Date)

    # 头像
    avatar = db.Column(db.String(500), default='')

    # 状态
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships - 注意：user 的 backref 在 PublicGeneration 定义处
    profile = db.relationship('PublicUserProfile', backref='user',
                              uselist=False, cascade='all, delete-orphan')
    generations = db.relationship('PublicGeneration',
                                  back_populates='user',
                                  lazy='dynamic', cascade='all, delete-orphan')

    def is_paid_user(self):
        if not self.is_premium:
            return False
        if self.premium_expires and self.premium_expires < datetime.utcnow():
            return False
        return True

    def get_plan_config(self):
        plans = {
            'free': {'daily_limit': 2, 'monthly_limit': None, 'overage_price': 0},
            'basic': {'daily_limit': None, 'monthly_limit': 100, 'overage_price': 3},
            'professional': {'daily_limit': None, 'monthly_limit': 300, 'overage_price': 2},
            'enterprise': {'daily_limit': None, 'monthly_limit': None, 'overage_price': 0},
        }
        return plans.get(self.premium_plan, plans['free'])


class PublicUserProfile(db.Model):
    """公开用户信息表"""
    __tablename__ = 'public_user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'),
                        nullable=False, unique=True)

    # 基本信息
    industry = db.Column(db.String(50))
    target_customers = db.Column(db.JSON)  # JSON数组
    business_description = db.Column(db.Text)
    differentiation = db.Column(db.Text)  # 付费用户

    # 付费用户专属
    target_user_persona = db.Column(db.JSON)
    content_purpose = db.Column(db.JSON)
    reference_accounts = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)


class PublicGeneration(db.Model):
    """公开用户生成记录表"""
    __tablename__ = 'public_generations'
    __table_args__ = (
        db.Index('idx_generation_user_created', 'user_id', 'created_at'),
        db.Index('idx_generation_portrait', 'user_id', 'portrait_id'),
        db.Index('idx_generation_problem', 'user_id', 'problem_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)

    # Relationships
    user = db.relationship('PublicUser', back_populates='generations')

    # 星系关联字段（新增）
    # 关联恒星（画像ID）
    portrait_id = db.Column(db.Integer, nullable=True)
    # 关联行星（核心问题ID）
    problem_id = db.Column(db.Integer, nullable=True)

    # 生成参数
    industry = db.Column(db.String(50))
    target_customer = db.Column(db.String(50))
    content_type = db.Column(db.String(20), default='graphic')

    # 生成内容
    titles = db.Column(db.JSON)  # 标题列表
    tags = db.Column(db.JSON)  # 标签列表
    content = db.Column(db.Text)  # 完整内容

    # 消耗
    used_tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedPortrait(db.Model):
    """用户保存的画像表"""
    __tablename__ = 'saved_portraits'
    __table_args__ = (
        db.Index('idx_portrait_user', 'user_id'),
        db.Index('idx_portrait_user_created', 'user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)

    # Relationships
    user = db.relationship('PublicUser', backref='saved_portraits')

    # 画像数据（JSON格式存储）
    portrait_data = db.Column(db.JSON, nullable=False)

    # 画像信息
    portrait_name = db.Column(db.String(100), default='未命名')
    business_description = db.Column(db.String(500))
    industry = db.Column(db.String(50))
    target_customer = db.Column(db.String(100))

    # 使用统计
    used_count = db.Column(db.Integer, default=0)

    # 默认设置
    is_default = db.Column(db.Boolean, default=False)

    # 画像专属关键词库（JSON）
    keyword_library = db.Column(db.JSON)
    # 画像专属选题库（JSON）
    topic_library = db.Column(db.JSON)
    # 关键词库更新时间/次数
    keyword_updated_at = db.Column(db.DateTime)
    keyword_update_count = db.Column(db.Integer, default=0)
    keyword_cache_expires_at = db.Column(db.DateTime)
    # 选题库更新时间/次数
    topic_updated_at = db.Column(db.DateTime)
    topic_update_count = db.Column(db.Integer, default=0)
    topic_cache_expires_at = db.Column(db.DateTime)
    # 来源会话ID（关联问题识别）
    session_id = db.Column(db.Integer)

    # 词库生成状态：pending（待生成）/ generating（生成中）/ completed（已完成）/ failed（失败）
    generation_status = db.Column(db.String(20), default='pending')
    # 词库生成错误信息
    generation_error = db.Column(db.Text)

    # 内容阶段配置（管理员专属，仅内部可见）：起号阶段/成长阶段/成熟阶段
    content_stage = db.Column(db.String(20), default='成长阶段')

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def has_keyword_library(self):
        """是否有专属关键词库"""
        return bool(self.keyword_library)

    @property
    def has_topic_library(self):
        """是否有专属选题库"""
        return bool(self.topic_library)

    @property
    def keyword_library_expired(self):
        """关键词库是否过期"""
        if not self.keyword_cache_expires_at:
            return True
        return self.keyword_cache_expires_at < datetime.utcnow()

    @property
    def topic_library_expired(self):
        """选题库是否过期"""
        if not self.topic_cache_expires_at:
            return True
        return self.topic_cache_expires_at < datetime.utcnow()


class PublicPricingPlan(db.Model):
    """定价方案表"""
    __tablename__ = 'public_pricing_plans'

    id = db.Column(db.Integer, primary_key=True)
    plan_code = db.Column(db.String(50), unique=True, nullable=False)
    plan_name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2), default=0)
    price_unit = db.Column(db.String(20), default='month')

    # 配额
    daily_limit = db.Column(db.Integer)
    monthly_limit = db.Column(db.Integer)
    token_limit = db.Column(db.Integer)
    overage_price = db.Column(db.Numeric(10, 2))

    features = db.Column(db.JSON)
    is_visible = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
# 二、预设数据模型（只读，热数据）
# =============================================================================

class PublicTargetCustomer(db.Model):
    """目标客户模板表"""
    __tablename__ = 'public_target_customers'
    __table_args__ = (
        db.Index('idx_customer_industry', 'applicable_industries', postgresql_using='gin'),
        db.Index('idx_customer_batch', 'batch_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_type = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))

    # 批次分组
    batch_id = db.Column(db.String(50))  # 批次ID，如 "trust_repurchase"
    batch_goal = db.Column(db.String(100))  # 批次核心目标，如 "建立信任、提升复购"
    batch_display_order = db.Column(db.Integer, default=0)  # 批次内显示顺序

    # 画像详情
    pain_point = db.Column(db.Text)  # 核心痛点描述（简短）
    pain_point_detail = db.Column(db.Text)  # 痛点详细描述（用于悬停/展开）
    action_motivation = db.Column(db.Text)  # 行动动机描述

    # JSON数组，如 ["桶装水", "矿泉水"]
    applicable_industries = db.Column(db.JSON)

    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PublicIndustryKeyword(db.Model):
    """行业关键词库"""
    __tablename__ = 'public_industry_keywords'
    __table_args__ = (
        db.Index('idx_keyword_industry_type', 'industry', 'keyword_type', 'is_active'),
        db.Index('idx_keyword_priority', 'priority'),
    )

    id = db.Column(db.Integer, primary_key=True)
    industry = db.Column(db.String(50), nullable=False)

    keyword = db.Column(db.String(100), nullable=False)
    keyword_type = db.Column(db.String(50))  # core/pain_point/scene/long_tail/hot
    search_intent = db.Column(db.String(50))

    # JSON数组
    applicable_customers = db.Column(db.JSON)

    usage_count = db.Column(db.Integer, default=0)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PublicIndustryTopic(db.Model):
    """行业选题库"""
    __tablename__ = 'public_industry_topics'
    __table_args__ = (
        db.Index('idx_topic_industry', 'industry', 'is_active'),
        db.Index('idx_topic_priority', 'priority'),
    )

    id = db.Column(db.Integer, primary_key=True)
    industry = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    topic_type = db.Column(db.String(50))  # recommend/problem/hotspot

    applicable_customers = db.Column(db.JSON)
    applicable_scenarios = db.Column(db.JSON)

    structure_type = db.Column(db.String(50))
    is_premium = db.Column(db.Boolean, default=False)

    usage_count = db.Column(db.Integer, default=0)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PublicContentTemplate(db.Model):
    """内容模板表"""
    __tablename__ = 'public_content_templates'
    __table_args__ = (
        db.Index('idx_template_code', 'template_code'),
        db.Index('idx_template_industry', 'applicable_industries', postgresql_using='gin'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(100), nullable=False)
    template_code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)

    applicable_industries = db.Column(db.JSON)
    applicable_customers = db.Column(db.JSON)

    content_type = db.Column(db.String(20), default='graphic')
    image_count = db.Column(db.Integer, default=5)
    image_ratio = db.Column(db.String(20), default='9:16')

    template_structure = db.Column(db.JSON)  # 结构定义
    template_content = db.Column(db.Text)  # 示例内容

    structure_type = db.Column(db.String(50))
    is_premium = db.Column(db.Boolean, default=False)

    usage_count = db.Column(db.Integer, default=0)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)


class PublicTitleTemplate(db.Model):
    """标题模板表"""
    __tablename__ = 'public_title_templates'

    id = db.Column(db.Integer, primary_key=True)
    template_pattern = db.Column(db.String(200), nullable=False)
    title_type = db.Column(db.String(50))  # 疑问/数字/对比/情感

    industry = db.Column(db.String(50))
    customer_type = db.Column(db.String(50))

    example_titles = db.Column(db.JSON)
    is_premium = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


class PublicTagTemplate(db.Model):
    """标签模板表"""
    __tablename__ = 'public_tag_templates'
    __table_args__ = (
        db.Index('idx_tag_industry', 'industry'),
    )

    id = db.Column(db.Integer, primary_key=True)
    industry = db.Column(db.String(50), nullable=False)
    customer_type = db.Column(db.String(50))

    tag_source = db.Column(db.String(50))  # core/pain_point/solution/long_tail/hot
    tags = db.Column(db.JSON)  # 标签列表

    is_premium = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)


# =============================================================================
# 三、LLM调用日志（用于成本统计）
# =============================================================================

class PublicLLMCallLog(db.Model):
    """LLM调用日志表"""
    __tablename__ = 'public_llm_call_logs'
    __table_args__ = (
        db.Index('idx_llm_user_date', 'user_id', 'created_at'),
        db.Index('idx_llm_call_type', 'call_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'))

    call_type = db.Column(db.String(50))  # keyword/title/content/tag
    model = db.Column(db.String(50))

    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    cost = db.Column(db.Numeric(10, 4), default=0)  # 成本（元）

    duration_ms = db.Column(db.Integer)
    status = db.Column(db.String(20), default='success')  # success/failed

    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
# 四、模板版本控制
# =============================================================================

class TemplateVersionHistory(db.Model):
    """模板版本历史表"""
    __tablename__ = 'template_version_history'
    __table_args__ = (
        db.Index('idx_version_template', 'template_type', 'template_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50), nullable=False)
    template_id = db.Column(db.Integer, nullable=False)
    version = db.Column(db.String(20), nullable=False)
    content_snapshot = db.Column(db.Text)
    variables_snapshot = db.Column(db.JSON)
    change_summary = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='template_versions')


class TemplateVariable(db.Model):
    """模板变量配置表"""
    __tablename__ = 'template_variable'
    __table_args__ = (
        db.Index('idx_variable_type', 'template_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_type = db.Column(db.String(50), nullable=False)
    variable_name = db.Column(db.String(100), nullable=False)
    variable_label = db.Column(db.String(200))
    variable_type = db.Column(db.String(20), default='text')  # text/select/number/date
    default_value = db.Column(db.Text)
    description = db.Column(db.Text)
    is_required = db.Column(db.Boolean, default=False)
    options = db.Column(db.JSON)  # 下拉选项 [{"value": "x", "label": "y"}]
    display_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
