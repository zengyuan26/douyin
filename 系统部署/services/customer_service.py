"""
客户管理服务层
"""

from datetime import datetime
from models.models import db
from models.customer_models import Customer, CustomerContact, CustomerActivityLog
from models.public_models import SavedPortrait, PublicGeneration
import logging

logger = logging.getLogger(__name__)


class CustomerService:
    """客户管理服务"""

    @staticmethod
    def create_customer(data, admin_id=None):
        """
        创建客户

        Args:
            data: 客户数据字典
            admin_id: 管理员ID

        Returns:
            Customer: 创建的客户对象
        """
        customer = Customer(
            customer_name=data.get('customer_name'),
            customer_code=data.get('customer_code'),
            admin_id=admin_id or data.get('admin_id'),

            # 基础信息
            client_type=data.get('client_type'),
            client_type_detail=data.get('client_type_detail'),
            industry=data.get('industry'),
            business_description=data.get('business_description'),

            # 地域信息
            geographic_scope=data.get('geographic_scope'),
            scope_detail=data.get('scope_detail'),
            target_cities=data.get('target_cities'),
            local_focus=data.get('local_focus', False),

            # 品牌信息
            brand_name=data.get('brand_name'),
            personal_brand=data.get('personal_brand', False),
            company_brand=data.get('company_brand', False),
            brand_priority=data.get('brand_priority'),

            # 语言风格
            primary_language=data.get('primary_language'),
            dialect_ratio=data.get('dialect_ratio'),
            dialect_detail=data.get('dialect_detail'),

            # 产品/服务
            product_type=data.get('product_type'),
            price_range=data.get('price_range'),
            seasonal=data.get('seasonal', False),
            seasonal_detail=data.get('seasonal_detail'),

            # 交付模式
            delivery_mode=data.get('delivery_mode'),
            delivery_frequency=data.get('delivery_frequency'),
            unit_price=data.get('unit_price'),

            # 项目目标
            primary_goal=data.get('primary_goal'),
            secondary_goals=data.get('secondary_goals'),
            timeline=data.get('timeline'),
            budget_level=data.get('budget_level'),

            # 资源与团队
            has_team=data.get('has_team'),
            team_size=data.get('team_size'),
            content_frequency=data.get('content_frequency'),

            # 内容偏好
            content_style=data.get('content_style'),
            reference_accounts=data.get('reference_accounts'),

            # 联系信息
            contact_person=data.get('contact_person'),
            contact_phone=data.get('contact_phone'),
            contact_email=data.get('contact_email'),
            contact_wechat=data.get('contact_wechat'),

            # 备注
            notes=data.get('notes'),

            status=data.get('status', 'active')
        )

        db.session.add(customer)
        db.session.commit()

        # 记录活动日志
        CustomerService.log_activity(
            customer_id=customer.id,
            activity_type='profile_created',
            activity_detail=f'创建客户：{customer.customer_name}',
            operator_id=admin_id
        )

        logger.info(f"创建客户成功: {customer.customer_name} (ID: {customer.id})")
        return customer

    @staticmethod
    def update_customer(customer_id, data, operator_id=None):
        """
        更新客户信息

        Args:
            customer_id: 客户ID
            data: 更新数据字典
            operator_id: 操作人ID

        Returns:
            Customer: 更新后的客户对象
        """
        customer = Customer.query.get(customer_id)
        if not customer:
            raise ValueError(f"客户不存在: {customer_id}")

        # 可更新的字段
        update_fields = [
            'customer_name', 'customer_code', 'client_type', 'client_type_detail',
            'industry', 'business_description', 'geographic_scope', 'scope_detail',
            'target_cities', 'local_focus', 'brand_name', 'personal_brand',
            'company_brand', 'brand_priority', 'primary_language', 'dialect_ratio',
            'dialect_detail', 'product_type', 'price_range', 'seasonal',
            'seasonal_detail', 'delivery_mode', 'delivery_frequency', 'unit_price',
            'primary_goal', 'secondary_goals', 'timeline', 'budget_level',
            'has_team', 'team_size', 'content_frequency', 'content_style',
            'reference_accounts', 'contact_person', 'contact_phone', 'contact_email',
            'contact_wechat', 'notes', 'status'
        ]

        for field in update_fields:
            if field in data:
                setattr(customer, field, data[field])

        customer.updated_at = datetime.utcnow()
        db.session.commit()

        # 记录活动日志
        CustomerService.log_activity(
            customer_id=customer.id,
            activity_type='profile_updated',
            activity_detail=f'更新客户信息',
            operator_id=operator_id
        )

        logger.info(f"更新客户成功: {customer.customer_name} (ID: {customer.id})")
        return customer

    @staticmethod
    def delete_customer(customer_id, operator_id=None):
        """
        删除客户（软删除，将状态改为 inactive）

        Args:
            customer_id: 客户ID
            operator_id: 操作人ID

        Returns:
            bool: 是否成功
        """
        customer = Customer.query.get(customer_id)
        if not customer:
            raise ValueError(f"客户不存在: {customer_id}")

        # 软删除
        customer.status = 'inactive'
        customer.updated_at = datetime.utcnow()
        db.session.commit()

        # 记录活动日志
        CustomerService.log_activity(
            customer_id=customer.id,
            activity_type='profile_deleted',
            activity_detail=f'删除客户',
            operator_id=operator_id
        )

        logger.info(f"删除客户成功: {customer.customer_name} (ID: {customer.id})")
        return True

    @staticmethod
    def get_customer(customer_id, include_stats=False):
        """
        获取客户详情

        Args:
            customer_id: 客户ID
            include_stats: 是否包含统计信息

        Returns:
            dict: 客户数据字典
        """
        customer = Customer.query.get(customer_id)
        if not customer:
            return None

        return customer.to_dict(include_stats=include_stats)

    @staticmethod
    def list_customers(admin_id=None, industry=None, status=None,
                       search=None, page=1, page_size=20, include_stats=True):
        """
        获取客户列表

        Args:
            admin_id: 管理员ID（用于过滤）
            industry: 行业筛选
            status: 状态筛选
            search: 搜索关键词
            page: 页码
            page_size: 每页数量
            include_stats: 是否包含统计信息

        Returns:
            dict: 分页结果
        """
        query = Customer.query

        # 管理员过滤（普通管理员只能看到自己的客户）
        if admin_id:
            query = query.filter(Customer.admin_id == admin_id)

        # 行业过滤
        if industry:
            query = query.filter(Customer.industry == industry)

        # 状态过滤
        if status:
            query = query.filter(Customer.status == status)
        else:
            # 默认只显示活跃客户
            query = query.filter(Customer.status == 'active')

        # 搜索过滤
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                db.or_(
                    Customer.customer_name.ilike(search_pattern),
                    Customer.business_description.ilike(search_pattern),
                    Customer.brand_name.ilike(search_pattern)
                )
            )

        # 按创建时间倒序
        query = query.order_by(Customer.created_at.desc())

        # 分页
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [c.to_dict(include_stats=include_stats) for c in pagination.items],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        }

    @staticmethod
    def get_customer_portraits(customer_id, page=1, page_size=20):
        """
        获取客户下的所有画像

        Args:
            customer_id: 客户ID
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 分页结果
        """
        query = SavedPortrait.query.filter(
            SavedPortrait.customer_id == customer_id
        ).order_by(SavedPortrait.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [p.to_dict() for p in pagination.items],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        }

    @staticmethod
    def get_customer_generations(customer_id, page=1, page_size=20):
        """
        获取客户下的所有生成记录

        Args:
            customer_id: 客户ID
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 分页结果
        """
        query = PublicGeneration.query.filter(
            PublicGeneration.customer_id == customer_id
        ).order_by(PublicGeneration.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [g.to_dict() for g in pagination.items],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        }

    @staticmethod
    def get_client_profile(customer_id):
        """
        获取客户的标准 client_profile 格式（供 skill 系统使用）

        Args:
            customer_id: 客户ID

        Returns:
            dict: client_profile 格式的数据
        """
        customer = Customer.query.get(customer_id)
        if not customer:
            return None

        return customer.to_client_profile()

    @staticmethod
    def log_activity(customer_id, activity_type, activity_detail=None,
                   related_portrait_id=None, related_generation_id=None,
                   operator_id=None, operator_name=None):
        """
        记录客户活动日志

        Args:
            customer_id: 客户ID
            activity_type: 活动类型
            activity_detail: 活动详情
            related_portrait_id: 关联的画像ID
            related_generation_id: 关联的生成记录ID
            operator_id: 操作人ID
            operator_name: 操作人名称

        Returns:
            CustomerActivityLog: 活动日志对象
        """
        log = CustomerActivityLog(
            customer_id=customer_id,
            activity_type=activity_type,
            activity_detail=activity_detail,
            related_portrait_id=related_portrait_id,
            related_generation_id=related_generation_id,
            operator_id=operator_id,
            operator_name=operator_name
        )

        db.session.add(log)
        db.session.commit()

        return log

    @staticmethod
    def get_activity_logs(customer_id, page=1, page_size=20):
        """
        获取客户的活动日志

        Args:
            customer_id: 客户ID
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 分页结果
        """
        query = CustomerActivityLog.query.filter(
            CustomerActivityLog.customer_id == customer_id
        ).order_by(CustomerActivityLog.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [
                {
                    'id': log.id,
                    'activity_type': log.activity_type,
                    'activity_detail': log.activity_detail,
                    'related_portrait_id': log.related_portrait_id,
                    'related_generation_id': log.related_generation_id,
                    'operator_id': log.operator_id,
                    'operator_name': log.operator_name,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                }
                for log in pagination.items
            ],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        }

    @staticmethod
    def get_industries():
        """
        获取所有已使用的行业列表（用于下拉筛选）

        Returns:
            list: 行业列表
        """
        industries = db.session.query(Customer.industry).filter(
            Customer.industry.isnot(None),
            Customer.industry != ''
        ).distinct().all()

        return [i[0] for i in industries if i[0]]
