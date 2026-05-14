"""
客户管理模块 - 数据模型

管理客户档案，支持超级定位、内容生成等业务与客户的关联。
"""

from datetime import datetime
from models.models import db


class Customer(db.Model):
    """客户管理表 - 统一管理所有客户的档案信息"""
    __tablename__ = 'customers'
    __table_args__ = (
        db.Index('idx_customer_admin', 'admin_id'),
        db.Index('idx_customer_industry', 'industry'),
        db.Index('idx_customer_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_code = db.Column(db.String(50), unique=True)

    # 关联管理员
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # ── 基础信息 (client_profile) ──
    client_type = db.Column(db.String(20))  # product/service/both
    client_type_detail = db.Column(db.String(100))
    industry = db.Column(db.String(50))
    business_description = db.Column(db.Text)

    # ── 地域信息 ──
    geographic_scope = db.Column(db.String(20))  # local/regional/global
    scope_detail = db.Column(db.String(200))
    target_cities = db.Column(db.JSON)
    local_focus = db.Column(db.Boolean, default=False)

    # ── 品牌信息 ──
    brand_name = db.Column(db.String(100))
    personal_brand = db.Column(db.Boolean, default=False)
    company_brand = db.Column(db.Boolean, default=False)
    brand_priority = db.Column(db.String(20))  # personal/company/both

    # ── 语言风格 ──
    primary_language = db.Column(db.String(50))  # mandarin/cantonese/sichuan...
    dialect_ratio = db.Column(db.String(20))  # full/dominant/accent/minimal
    dialect_detail = db.Column(db.String(100))

    # ── 产品/服务 ──
    product_type = db.Column(db.String(50))
    price_range = db.Column(db.String(20))
    seasonal = db.Column(db.Boolean, default=False)

    # ── 交付模式 ──
    delivery_mode = db.Column(db.String(20))  # offline/online/hybrid
    delivery_frequency = db.Column(db.String(20))  # one-time/recurring/membership
    unit_price = db.Column(db.String(50))

    # ── 项目目标 ──
    primary_goal = db.Column(db.String(50))  # traffic/brand/conversion/education
    secondary_goals = db.Column(db.JSON)
    timeline = db.Column(db.String(20))  # short/medium/long
    budget_level = db.Column(db.String(20))

    # ── 资源与团队 ──
    has_team = db.Column(db.Boolean)
    team_size = db.Column(db.Integer)
    content_frequency = db.Column(db.String(20))  # daily/weekly/occasional

    # ── 内容偏好 ──
    content_style = db.Column(db.JSON)  # [professional/humorous/story/tutorial]
    reference_accounts = db.Column(db.JSON)

    # ── 元数据 ──
    status = db.Column(db.String(20), default='active')
    contact_person = db.Column(db.String(100))
    contact_phone = db.Column(db.String(50))
    contact_email = db.Column(db.String(120))
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    admin = db.relationship('User', backref='managed_customers')
    portraits = db.relationship('SavedPortrait', back_populates='customer', lazy='dynamic')
    generations = db.relationship('PublicGeneration', back_populates='customer', lazy='dynamic')

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'customer_code': self.customer_code,
            'admin_id': self.admin_id,
            'admin_name': self.admin.username if self.admin else None,
            'client_type': self.client_type,
            'client_type_detail': self.client_type_detail,
            'industry': self.industry,
            'business_description': self.business_description,
            'geographic_scope': self.geographic_scope,
            'scope_detail': self.scope_detail,
            'target_cities': self.target_cities,
            'local_focus': self.local_focus,
            'brand_name': self.brand_name,
            'personal_brand': self.personal_brand,
            'company_brand': self.company_brand,
            'brand_priority': self.brand_priority,
            'primary_language': self.primary_language,
            'dialect_ratio': self.dialect_ratio,
            'dialect_detail': self.dialect_detail,
            'product_type': self.product_type,
            'price_range': self.price_range,
            'seasonal': self.seasonal,
            'delivery_mode': self.delivery_mode,
            'delivery_frequency': self.delivery_frequency,
            'unit_price': self.unit_price,
            'primary_goal': self.primary_goal,
            'secondary_goals': self.secondary_goals,
            'timeline': self.timeline,
            'budget_level': self.budget_level,
            'has_team': self.has_team,
            'team_size': self.team_size,
            'content_frequency': self.content_frequency,
            'content_style': self.content_style,
            'reference_accounts': self.reference_accounts,
            'status': self.status,
            'contact_person': self.contact_person,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'remarks': self.remarks,
            'portrait_count': self.portraits.count() if self.portraits else 0,
            'generation_count': self.generations.count() if self.generations else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Customer {self.customer_name}>'
