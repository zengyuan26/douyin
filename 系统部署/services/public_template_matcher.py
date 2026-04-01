"""
公开内容生成平台 - 模板匹配服务

功能：
1. 根据行业和目标客户匹配内容模板
2. 匹配关键词库
3. 匹配选题库
4. 匹配标题模板
5. 匹配标签模板
"""

import random
from typing import List, Dict, Optional, Any
from models.public_models import (
    PublicIndustryKeyword,
    PublicIndustryTopic,
    PublicContentTemplate,
    PublicTitleTemplate,
    PublicTagTemplate
)
from services.public_cache import public_cache, cached
import logging

logger = logging.getLogger(__name__)


class TemplateMatcher:
    """模板匹配器"""

    # 预设行业列表
    INDUSTRIES = [
        {'code': 'tongzhuangshui', 'name': '桶装水', 'aliases': ['饮用水', '矿泉水', '纯净水']},
        {'code': 'meishi', 'name': '美食餐饮', 'aliases': ['餐厅', '小吃', '外卖']},
        {'code': 'fuzhuang', 'name': '服装', 'aliases': ['衣服', '鞋子', '包包']},
        {'code': 'meirong', 'name': '美容护肤', 'aliases': ['化妆品', '护肤品', '美妆']},
        {'code': 'jiadian', 'name': '家电数码', 'aliases': ['电器', '手机', '电脑']},
        {'code': 'jiaju', 'name': '家居用品', 'aliases': ['家具', '装饰', '家纺']},
        {'code': 'jiaoyu', 'name': '教育培训', 'aliases': ['培训', '课程', '教育']},
        {'code': 'liren', 'name': '丽人', 'aliases': ['美发', '美甲', '美容']},
        {'code': 'qita', 'name': '其他', 'aliases': []},
    ]

    @classmethod
    def get_industries(cls) -> List[Dict]:
        """获取行业列表"""
        # 先尝试从缓存获取
        cached_data = public_cache.get_industries()
        if cached_data:
            return cached_data

        # 缓存到内存
        public_cache.set_industries(cls.INDUSTRIES)
        return cls.INDUSTRIES

    @classmethod
    @cached('customers', key_func=lambda industry: industry)
    def get_target_customers(cls, industry: str) -> List[Dict]:
        """
        获取目标客户列表

        Args:
            industry: 行业代码

        Returns:
            目标客户列表
        """
        customers = []

        # 从数据库查询
        try:
            db_customers = PublicTargetCustomer.query.filter_by(
                is_active=True
            ).order_by(PublicTargetCustomer.priority.desc()).all()

            for c in db_customers:
                # 检查行业是否适用
                if c.applicable_industries and industry not in c.applicable_industries:
                    continue

                customer_data = {
                    'customer_type': c.customer_type,
                    'customer_name': c.customer_name,
                    'description': c.description,
                    'icon': c.icon,
                    'pain_point': c.pain_point,
                    'pain_point_detail': c.pain_point_detail,
                    'action_motivation': c.action_motivation,
                    'batch_id': c.batch_id,
                    'batch_goal': c.batch_goal,
                    'batch_display_order': c.batch_display_order,
                }
                customers.append(customer_data)
        except Exception as e:
            logger.warning("[TemplateMatcher] 获取目标客户失败: %s", e)

        return customers

    @classmethod
    def get_target_customers_by_batch(cls, industry: str) -> Dict[str, Any]:
        """
        获取按批次分组的目标客户

        Args:
            industry: 行业代码

        Returns:
            {
                'batches': [{'batch_id': 'xxx', 'batch_goal': 'xxx', 'customers': [...]}],
                'general_customers': [...],
                'all_customers': [...],
            }
        """
        all_customers = cls.get_target_customers(industry)

        # 分离有批次信息的客户和通用客户
        batched_customers = []
        general_customers = []

        for c in all_customers:
            if c.get('batch_id') and c.get('batch_id') != 'general':
                batched_customers.append(c)
            else:
                general_customers.append(c)

        # 按批次分组
        batch_groups = {}
        for c in batched_customers:
            batch_id = c.get('batch_id', 'default')
            if batch_id not in batch_groups:
                batch_groups[batch_id] = {
                    'batch_id': batch_id,
                    'batch_goal': c.get('batch_goal', ''),
                    'customers': [],
                }
            batch_groups[batch_id]['customers'].append(c)

        # 按批次显示顺序排序
        for batch_id in batch_groups:
            batch_groups[batch_id]['customers'].sort(
                key=lambda x: x.get('batch_display_order', 0)
            )

        # 构建结果
        return {
            'batches': list(batch_groups.values()),
            'general_customers': general_customers,
            'all_customers': all_customers,
        }

    @classmethod
    def match_customers_for_business(cls, industry: str, business_range: str,
                                     business_type: str) -> Dict[str, Any]:
        """
        根据业务信息匹配合适的目标客户批次

        Args:
            industry: 行业代码
            business_range: 经营范围（local/cross_region）
            business_type: 经营类型（product/local_service/personal/enterprise）

        Returns:
            匹配合适的批次和客户推荐
        """
        batch_data = cls.get_target_customers_by_batch(industry)

        # 根据经营范围和类型筛选合适的客户
        recommended_batches = []
        recommended_customers = []

        for batch in batch_data['batches']:
            # 根据业务类型推荐不同的批次
            if business_type == 'enterprise' or business_type == 'local_service':
                # 企业服务/本地服务优先推荐信任建立批次
                if 'trust' in batch['batch_id'].lower() or 'repurchase' in batch['batch_id'].lower():
                    batch['recommendation_reason'] = '适合建立客户信任'
                    recommended_batches.append(batch)

            if business_type == 'product':
                # 消费品优先推荐品牌认知批次
                if 'brand' in batch['batch_id'].lower() or 'awareness' in batch['batch_id'].lower():
                    batch['recommendation_reason'] = '适合品牌推广'
                    recommended_batches.append(batch)

        # 如果没有特定匹配，返回所有批次
        if not recommended_batches:
            recommended_batches = batch_data['batches']

        return {
            'recommended_batches': recommended_batches,
            'all_batches': batch_data['batches'],
            'general_customers': batch_data['general_customers'],
            'match_criteria': {
                'industry': industry,
                'business_range': business_range,
                'business_type': business_type,
            }
        }

    @classmethod
    def get_keywords(cls, industry: str, customer_type: str,
                    keyword_type: Optional[str] = None,
                    limit: int = 10) -> List[Dict]:
        """
        获取关键词列表

        Args:
            industry: 行业
            customer_type: 客户类型
            keyword_type: 关键词类型（core/pain_point/scene/long_tail/hot）
            limit: 返回数量
        """
        # 缓存键
        cache_key = f'{industry}:{customer_type}:{keyword_type}:{limit}'
        cached_data = public_cache.get_keywords(industry, cache_key)
        if cached_data:
            return cached_data

        # 从数据库查询
        query = PublicIndustryKeyword.query.filter_by(
            industry=industry,
            is_active=True
        )

        if keyword_type:
            query = query.filter_by(keyword_type=keyword_type)

        query = query.order_by(PublicIndustryKeyword.priority.desc()).limit(limit)
        keywords = [{'keyword': k.keyword, 'type': k.keyword_type, 'intent': k.search_intent} for k in query.all()]

        public_cache.set_keywords(industry, cache_key, keywords)
        return keywords

    @classmethod
    def get_topics(cls, industry: str, customer_type: str,
                  topic_type: Optional[str] = None,
                  limit: int = 5) -> List[Dict]:
        """
        获取选题列表

        Args:
            industry: 行业
            customer_type: 客户类型
            topic_type: 选题类型
            limit: 返回数量
        """
        cache_key = f'{industry}:{customer_type}:{topic_type}:{limit}'
        cached_data = public_cache.get_topics(industry, cache_key)
        if cached_data:
            return cached_data

        query = PublicIndustryTopic.query.filter_by(
            industry=industry,
            is_active=True
        )

        if topic_type:
            query = query.filter_by(topic_type=topic_type)

        query = query.order_by(PublicIndustryTopic.priority.desc()).limit(limit)
        topics = [{
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'type': t.topic_type,
            'structure': t.structure_type,
            'is_premium': t.is_premium,
        } for t in query.all()]

        public_cache.set_topics(industry, cache_key, topics)
        return topics

    @classmethod
    def get_content_template(cls, industry: str, customer_type: str,
                            is_premium: bool = False,
                            structure_type: Optional[str] = None) -> Optional[Dict]:
        """
        获取内容模板

        Args:
            industry: 行业
            customer_type: 客户类型
            is_premium: 是否付费模板
            structure_type: 结构类型
        """
        query = PublicContentTemplate.query.filter_by(
            is_active=True
        )

        if is_premium:
            query = query.filter_by(is_premium=True)
        else:
            query = query.filter_by(is_premium=False)

        if structure_type:
            query = query.filter_by(structure_type=structure_type)

        template = query.order_by(PublicContentTemplate.priority.desc()).first()

        if template:
            return {
                'code': template.template_code,
                'name': template.template_name,
                'description': template.description,
                'image_count': template.image_count,
                'image_ratio': template.image_ratio,
                'structure': template.template_structure,
                'content': template.template_content,
            }
        return None

    @classmethod
    def get_title_templates(cls, industry: str, customer_type: str,
                          is_premium: bool = False,
                          limit: int = 5) -> List[Dict]:
        """
        获取标题模板

        Args:
            industry: 行业
            customer_type: 客户类型
            is_premium: 是否付费模板
            limit: 返回数量
        """
        query = PublicTitleTemplate.query.filter_by(is_active=True)

        if is_premium:
            query = query.filter_by(is_premium=True)
        else:
            query = query.filter_by(is_premium=False)

        query = query.order_by(PublicTitleTemplate.priority.desc()).limit(limit)
        titles = [{
            'pattern': t.template_pattern,
            'type': t.title_type,
            'examples': t.example_titles,
        } for t in query.all()]

        return titles

    @classmethod
    def get_tag_templates(cls, industry: str, customer_type: str,
                         is_premium: bool = False) -> Dict[str, List[str]]:
        """
        获取标签模板

        Args:
            industry: 行业
            customer_type: 客户类型
            is_premium: 是否付费模板
        """
        query = PublicTagTemplate.query.filter_by(
            industry=industry,
            is_active=True
        )

        if is_premium:
            query = query.filter_by(is_premium=True)

        tags_by_source = {}
        for tag_tpl in query.all():
            source = tag_tpl.tag_source
            if source not in tags_by_source:
                tags_by_source[source] = []
            if tag_tpl.tags:
                tags_by_source[source].extend(tag_tpl.tags)

        return tags_by_source

    @classmethod
    def select_random_topics(cls, topics: List[Dict], count: int = 1) -> List[Dict]:
        """随机选择选题"""
        if len(topics) <= count:
            return topics
        return random.sample(topics, count)

    @classmethod
    def match_for_generation(cls, industry: str, customer_type: str,
                           is_premium: bool = False) -> Dict[str, Any]:
        """
        为内容生成匹配所有必要资源

        Args:
            industry: 行业
            customer_type: 客户类型
            is_premium: 是否付费用户

        Returns:
            包含关键词、选题、模板等的字典
        """
        return {
            'keywords': {
                'core': cls.get_keywords(industry, customer_type, 'core', 2),
                'pain_point': cls.get_keywords(industry, customer_type, 'pain_point', 3),
                'scene': cls.get_keywords(industry, customer_type, 'scene', 2),
                'long_tail': cls.get_keywords(industry, customer_type, 'long_tail', 3),
            },
            'topics': cls.get_topics(industry, customer_type, limit=10),
            'template': cls.get_content_template(industry, customer_type, is_premium),
            'title_templates': cls.get_title_templates(industry, customer_type, is_premium, 5),
            'tag_templates': cls.get_tag_templates(industry, customer_type, is_premium),
        }


# 全局实例
template_matcher = TemplateMatcher()
