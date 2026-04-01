"""
公开内容生成平台 - 预设数据初始化

使用方法：
python -c "from app import app; from services.init_public_data import init_preset_data; app.app_context().push(); init_preset_data()"
或（从系统部署目录运行）：
python services/init_public_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.public_models import (
    PublicPricingPlan, PublicTargetCustomer, PublicIndustryKeyword,
    PublicIndustryTopic, PublicContentTemplate, PublicTitleTemplate,
    PublicTagTemplate
)
from models.models import db


def init_pricing_plans():
    """初始化定价方案"""
    plans = [
        {
            'plan_code': 'free',
            'plan_name': '免费体验',
            'price': 0,
            'price_unit': 'month',
            'daily_limit': 2,
            'monthly_limit': None,
            'token_limit': None,
            'overage_price': None,
            'features': [
                '每日2次生成',
                '基础内容模板',
                '2种内容结构',
                '2个标题方案',
                '预设标签模板',
            ],
            'is_visible': True,
            'is_default': True,
            'sort_order': 1,
        },
        {
            'plan_code': 'basic',
            'plan_name': '基础版',
            'price': 99,
            'price_unit': 'month',
            'daily_limit': None,
            'monthly_limit': 100,
            'token_limit': None,
            'overage_price': 3,
            'features': [
                '每月100次生成',
                '10种爆款内容结构',
                '5个爆款标题方案',
                '多目标客户分层',
                'AI内容增强',
                '专属选题推荐',
            ],
            'is_visible': True,
            'is_default': False,
            'sort_order': 2,
        },
        {
            'plan_code': 'professional',
            'plan_name': '专业版',
            'price': 299,
            'price_unit': 'month',
            'daily_limit': None,
            'monthly_limit': 300,
            'token_limit': None,
            'overage_price': 2,
            'features': [
                '每月300次生成',
                '15种爆款内容结构',
                '10个爆款标题方案',
                '混合选题生成',
                '精准埋词方案',
                '图片比例可选',
                '优先客服支持',
            ],
            'is_visible': True,
            'is_default': False,
            'sort_order': 3,
        },
        {
            'plan_code': 'enterprise',
            'plan_name': '企业版',
            'price': 999,
            'price_unit': 'month',
            'daily_limit': None,
            'monthly_limit': None,
            'token_limit': None,
            'overage_price': None,
            'features': [
                '不限次数生成',
                '20种爆款内容结构',
                '15个爆款标题方案',
                '混合选题生成',
                '精准埋词方案',
                '所有图片比例',
                'API接口访问',
                '专属客服支持',
            ],
            'is_visible': True,
            'is_default': False,
            'sort_order': 4,
        },
    ]

    for plan_data in plans:
        existing = PublicPricingPlan.query.filter_by(plan_code=plan_data['plan_code']).first()
        if not existing:
            plan = PublicPricingPlan(**plan_data)
            db.session.add(plan)

    db.session.commit()
    print(f"[Init] 定价方案初始化完成")


def init_target_customers():
    """初始化目标客户模板 - 桶装水行业按批次分组"""

    # 桶装水行业批次分组
    tongzhuangshui_batches = [
        # 第一批：建立信任、提升复购
        {
            'batch_id': 'trust_repurchase_batch1',
            'batch_goal': '建立信任、提升复购',
            'customers': [
                {
                    'customer_type': 'new_resident',
                    'customer_name': '新搬小区',
                    'description': '首次选水、信任优先',
                    'icon': '🏠',
                    'applicable_industries': ['tongzhuangshui'],
                    'pain_point': '不知道哪家好，送水快不快、水干不干净都不知道，万一不好喝或者服务差，退水还麻烦',
                    'pain_point_detail': '刚搬来不知道哪家好，送水快不快、水干不干净都不知道，万一不好喝或者服务差，退水还麻烦。核心诉求：先试试看、有保障、口碑好值得信任',
                    'action_motivation': '口碑值得试、有保障、首单体验好',
                    'batch_display_order': 1,
                    'priority': 10,
                    'batch_id': 'trust_repurchase_batch1',
                    'batch_goal': '建立信任、提升复购',
                },
                {
                    'customer_type': 'renewal_user',
                    'customer_name': '老客户续费',
                    'description': '价格敏感、续约优先',
                    'icon': '💰',
                    'applicable_industries': ['tongzhuangshui'],
                    'pain_point': '用了一年了，每次到期就开始被推销各种套餐，想换个便宜的，又怕新水不好喝、服务跟不上',
                    'pain_point_detail': '用了一年了，每次到期就开始被推销各种套餐，想换个便宜的，又怕新水不好喝、服务跟不上。核心诉求：续费优惠大、老客有待遇、不被当冤大头',
                    'action_motivation': '续费有优惠、老客不被坑、长期锁定',
                    'batch_display_order': 2,
                    'priority': 9,
                    'batch_id': 'trust_repurchase_batch1',
                    'batch_goal': '建立信任、提升复购',
                },
                {
                    'customer_type': 'referral_user',
                    'customer_name': '老带新客户',
                    'description': '口碑推荐、关系优先',
                    'icon': '👥',
                    'applicable_industries': ['tongzhuangshui'],
                    'pain_point': '我们公司一直用这家水，感觉还行，朋友公司正好要找送水的，推荐了过去怕担责任',
                    'pain_point_detail': '我们公司一直用这家水，感觉还行，朋友公司正好要找送水的，推荐了过去怕担责任。核心诉求：品质稳定值得推、推荐有好处、出问题不扯皮',
                    'action_motivation': '推荐有奖励、品质稳定可推荐、推荐后关系维护',
                    'batch_display_order': 3,
                    'priority': 8,
                    'batch_id': 'trust_repurchase_batch1',
                    'batch_goal': '建立信任、提升复购',
                },
                {
                    'customer_type': 'complained_user',
                    'customer_name': '投诉过客户',
                    'description': '挽回优先、复购优先',
                    'icon': '😤',
                    'applicable_industries': ['tongzhuangshui'],
                    'pain_point': '上次送错水、桶有异味、服务态度差，投诉了也没下文，这次犹豫要不要继续订，怕还是老样子',
                    'pain_point_detail': '上次送错水、桶有异味、服务态度差，投诉了也没下文，这次犹豫要不要继续订，怕还是老样子。核心诉求：道歉有诚意、补偿到位、这次真改了',
                    'action_motivation': '改过自新值得再信、挽回后忠诚度高',
                    'batch_display_order': 4,
                    'priority': 7,
                    'batch_id': 'trust_repurchase_batch1',
                    'batch_goal': '建立信任、提升复购',
                },
                {
                    'customer_type': 'family_with_kids',
                    'customer_name': '家庭有娃',
                    'description': '健康敏感、长期优先',
                    'icon': '👨‍👩‍👧',
                    'applicable_industries': ['tongzhuangshui'],
                    'pain_point': '家里有小孩，对水质特别在意，桶装水放久了会不会有细菌？水源地是哪？能不能溯源？',
                    'pain_point_detail': '家里有小孩，对水质特别在意，桶装水放久了会不会有细菌？水源地是哪？能不能溯源？核心诉求：水源透明、检测报告、长期用着放心',
                    'action_motivation': '透明可溯源信得过、水质安全承诺',
                    'batch_display_order': 5,
                    'priority': 8,
                    'batch_id': 'trust_repurchase_batch1',
                    'batch_goal': '建立信任、提升复购',
                },
            ]
        },
    ]

    # 其他行业的通用目标客户（不受批次分组影响）
    other_industry_customers = [
        # 企业管理层（适用于所有行业）
        {
            'customer_type': 'enterprise_manager',
            'customer_name': '企业管理层',
            'description': '35-50岁，商务接待需求',
            'icon': '💼',
            'applicable_industries': ['meishi', 'fuzhuang', 'jiaju'],
            'batch_id': 'general',
            'batch_goal': '商务接待、效率为先',
            'pain_point': '接待客户要面子，用的东西不能太low',
            'pain_point_detail': '商务接待要面子，用的东西不能太low',
            'action_motivation': '品质对等价格、服务到位',
            'batch_display_order': 1,
            'priority': 10,
        },
        # 行政采购（适用于所有行业）
        {
            'customer_type': 'admin_purchase',
            'customer_name': '行政采购',
            'description': '25-40岁，负责企业采购决策',
            'icon': '📋',
            'applicable_industries': ['jiadian', 'jiaju'],
            'batch_id': 'general',
            'batch_goal': '性价比优先、流程规范',
            'pain_point': '采购要层层审批，价格要对比，服务要稳定',
            'pain_point_detail': '采购要层层审批，价格要对比，服务要稳定',
            'action_motivation': '性价比高、服务稳定',
            'batch_display_order': 2,
            'priority': 9,
        },
        # 送礼人群
        {
            'customer_type': 'gift_buyer',
            'customer_name': '送礼人群',
            'description': '30-50岁，节日送礼、探亲访友',
            'icon': '🎁',
            'applicable_industries': ['meishi', 'fuzhuang', 'meirong'],
            'batch_id': 'general',
            'batch_goal': '送礼有面子、包装要好看',
            'pain_point': '送礼要体面，价格要合适，东西要有档次',
            'pain_point_detail': '送礼要体面，价格要合适，东西要有档次',
            'action_motivation': '包装精美、档次高',
            'batch_display_order': 3,
            'priority': 7,
        },
        # 年轻白领
        {
            'customer_type': 'young_white',
            'customer_name': '年轻白领',
            'description': '20-35岁，个人消费、追求品质',
            'icon': '👔',
            'applicable_industries': ['meishi', 'fuzhuang', 'meirong', 'liren'],
            'batch_id': 'general',
            'batch_goal': '品质生活、性价比',
            'pain_point': '钱不多但要求高，要好看还要好用',
            'pain_point_detail': '钱不多但要求高，要好看还要好用',
            'action_motivation': '颜值高、性价比',
            'batch_display_order': 4,
            'priority': 6,
        },
        # 实体店主
        {
            'customer_type': 'store_owner',
            'customer_name': '实体店主',
            'description': '30-50岁，店铺经营、成本控制',
            'icon': '🏪',
            'applicable_industries': ['meishi', 'fuzhuang', 'jiadian'],
            'batch_id': 'general',
            'batch_goal': '成本控制、批量采购',
            'pain_point': '开店成本高，进货要便宜，质量还不能差',
            'pain_point_detail': '开店成本高，进货要便宜，质量还不能差',
            'action_motivation': '批发价、质量稳定',
            'batch_display_order': 5,
            'priority': 5,
        },
    ]

    # 合并所有客户数据
    all_customers = tongzhuangshui_batches[0]['customers'] + other_industry_customers

    all_customers = tongzhuangshui_batches[0]['customers'] + other_industry_customers

    for customer_data in all_customers:
        existing = PublicTargetCustomer.query.filter_by(
            customer_type=customer_data['customer_type']
        ).first()
        if not existing:
            customer = PublicTargetCustomer(**customer_data)
            db.session.add(customer)
        else:
            # 更新已有记录
            for key, value in customer_data.items():
                if key != 'customer_type':
                    setattr(existing, key, value)

    db.session.commit()
    print(f"[Init] 目标客户模板初始化完成（桶装水分批分组）")


def init_industry_keywords():
    """初始化行业关键词库"""
    keywords = [
        # 桶装水行业
        {'industry': 'tongzhuangshui', 'keyword': '桶装水', 'keyword_type': 'core', 'priority': 10},
        {'industry': 'tongzhuangshui', 'keyword': '矿泉水', 'keyword_type': 'core', 'priority': 9},
        {'industry': 'tongzhuangshui', 'keyword': '饮用水', 'keyword_type': 'core', 'priority': 8},
        {'industry': 'tongzhuangshui', 'keyword': '定制水', 'keyword_type': 'core', 'priority': 10},
        {'industry': 'tongzhuangshui', 'keyword': '送水', 'keyword_type': 'scene', 'priority': 8},
        {'industry': 'tongzhuangshui', 'keyword': '桶装水配送', 'keyword_type': 'scene', 'priority': 7},
        {'industry': 'tongzhuangshui', 'keyword': '办公室用水', 'keyword_type': 'scene', 'priority': 8},
        {'industry': 'tongzhuangshui', 'keyword': '商务接待', 'keyword_type': 'scene', 'priority': 9},
        {'industry': 'tongzhuangshui', 'keyword': '家庭饮水', 'keyword_type': 'scene', 'priority': 7},
        {'industry': 'tongzhuangshui', 'keyword': '水质不好', 'keyword_type': 'pain_point', 'priority': 8},
        {'industry': 'tongzhuangshui', 'keyword': '喝水不健康', 'keyword_type': 'pain_point', 'priority': 7},
        {'industry': 'tongzhuangshui', 'keyword': '不知道选什么水', 'keyword_type': 'pain_point', 'priority': 6},
        {'industry': 'tongzhuangshui', 'keyword': '桶装水哪个好', 'keyword_type': 'long_tail', 'priority': 7},
        {'industry': 'tongzhuangshui', 'keyword': '矿泉水和纯净水区别', 'keyword_type': 'long_tail', 'priority': 6},
        {'industry': 'tongzhuangshui', 'keyword': '如何辨别水质', 'keyword_type': 'long_tail', 'priority': 6},
        # 美食餐饮行业
        {'industry': 'meishi', 'keyword': '美食', 'keyword_type': 'core', 'priority': 10},
        {'industry': 'meishi', 'keyword': '餐厅', 'keyword_type': 'core', 'priority': 9},
        {'industry': 'meishi', 'keyword': '小吃', 'keyword_type': 'core', 'priority': 8},
        {'industry': 'meishi', 'keyword': '好吃', 'keyword_type': 'scene', 'priority': 9},
        {'industry': 'meishi', 'keyword': '外卖', 'keyword_type': 'scene', 'priority': 8},
        {'industry': 'meishi', 'keyword': '味道好', 'keyword_type': 'pain_point', 'priority': 7},
        # 服装行业
        {'industry': 'fuzhuang', 'keyword': '衣服', 'keyword_type': 'core', 'priority': 10},
        {'industry': 'fuzhuang', 'keyword': '时尚', 'keyword_type': 'scene', 'priority': 9},
        {'industry': 'fuzhuang', 'keyword': '搭配', 'keyword_type': 'scene', 'priority': 8},
        # 美容护肤行业
        {'industry': 'meirong', 'keyword': '护肤', 'keyword_type': 'core', 'priority': 10},
        {'industry': 'meirong', 'keyword': '美容', 'keyword_type': 'core', 'priority': 9},
        {'industry': 'meirong', 'keyword': '皮肤', 'keyword_type': 'scene', 'priority': 8},
        {'industry': 'meirong', 'keyword': '效果好', 'keyword_type': 'pain_point', 'priority': 7},
        # 更多行业可继续添加...
    ]

    for kw_data in keywords:
        existing = PublicIndustryKeyword.query.filter_by(
            industry=kw_data['industry'],
            keyword=kw_data['keyword'],
            keyword_type=kw_data['keyword_type']
        ).first()
        if not existing:
            keyword = PublicIndustryKeyword(**kw_data)
            db.session.add(keyword)

    db.session.commit()
    print(f"[Init] 行业关键词库初始化完成")


def init_industry_topics():
    """初始化行业选题库"""
    topics = [
        # 桶装水行业
        {
            'industry': 'tongzhuangshui',
            'title': '商务接待用水的坑，你踩过几个？',
            'description': '从假龙井到定制水的升级之路',
            'topic_type': 'problem',
            'structure_type': 'problem_solution',
            'priority': 10,
        },
        {
            'industry': 'tongzhuangshui',
            'title': '桶装水有异味？3步教你辨别水质',
            'description': '简单实用的水质辨别方法',
            'topic_type': 'knowledge',
            'structure_type': 'knowledge',
            'priority': 9,
        },
        {
            'industry': 'tongzhuangshui',
            'title': '为什么企业都在换定制水？',
            'description': '揭秘企业接待用水的秘密',
            'topic_type': 'recommend',
            'structure_type': 'reason_analysis',
            'priority': 8,
        },
        {
            'industry': 'tongzhuangshui',
            'title': '办公室桶装水多久换一次最合适？',
            'description': '饮水健康小知识',
            'topic_type': 'knowledge',
            'structure_type': 'q&a',
            'priority': 7,
        },
        {
            'industry': 'tongzhuangshui',
            'title': '定制水瓶身的LOGO设计有什么讲究？',
            'description': '企业品牌形象的细节',
            'topic_type': 'knowledge',
            'structure_type': 'knowledge',
            'is_premium': True,
            'priority': 8,
        },
        # 美食餐饮行业
        {
            'industry': 'meishi',
            'title': '这家店的东西为什么这么好吃？',
            'description': '探店类内容模板',
            'topic_type': 'recommend',
            'structure_type': 'story',
            'priority': 10,
        },
        {
            'industry': 'meishi',
            'title': '如何在家做出餐厅的味道？',
            'description': '教程类内容',
            'topic_type': 'knowledge',
            'structure_type': 'tutorial',
            'priority': 9,
        },
        # 更多选题...
    ]

    for topic_data in topics:
        existing = PublicIndustryTopic.query.filter_by(
            industry=topic_data['industry'],
            title=topic_data['title']
        ).first()
        if not existing:
            topic = PublicIndustryTopic(**topic_data)
            db.session.add(topic)

    db.session.commit()
    print(f"[Init] 行业选题库初始化完成")


def init_content_templates():
    """初始化内容模板"""
    templates = [
        # 基础模板（免费用户可用）
        {
            'template_code': 'problem_solution_basic',
            'template_name': '问题解决型（基础）',
            'description': '痛点引入 → 原因分析 → 解决方案',
            'applicable_industries': ['tongzhuangshui', 'meishi', 'fuzhuang', 'meirong', 'jiadian', 'jiaju'],
            'structure_type': 'problem_solution',
            'content_type': 'graphic',
            'image_count': 5,
            'image_ratio': '9:16',
            'is_premium': False,
            'priority': 10,
        },
        {
            'template_code': 'knowledge_basic',
            'template_name': '知识科普型（基础）',
            'description': '知识点讲解 → 应用场景 → 总结建议',
            'applicable_industries': ['tongzhuangshui', 'jiaoyu', 'meirong'],
            'structure_type': 'knowledge',
            'content_type': 'graphic',
            'image_count': 5,
            'image_ratio': '9:16',
            'is_premium': False,
            'priority': 9,
        },
        # 高级模板（付费用户可用）
        {
            'template_code': 'story_scene',
            'template_name': '故事场景型',
            'description': '场景故事 → 冲突转折 → 解决方案 → 情感共鸣',
            'applicable_industries': ['tongzhuangshui', 'meishi', 'fuzhuang', 'meirong'],
            'structure_type': 'story',
            'content_type': 'graphic',
            'image_count': 6,
            'image_ratio': '9:16',
            'is_premium': True,
            'priority': 10,
        },
        {
            'template_code': 'comparison',
            'template_name': '对比测评型',
            'description': 'A vs B → 各项对比 → 推荐结论',
            'applicable_industries': ['tongzhuangshui', 'jiadian', 'fuzhuang'],
            'structure_type': 'comparison',
            'content_type': 'graphic',
            'image_count': 5,
            'image_ratio': '9:16',
            'is_premium': True,
            'priority': 9,
        },
        {
            'template_code': 'hotspot',
            'template_name': '热点蹭造型',
            'description': '热点引入 → 关联产品 → 植入广告',
            'applicable_industries': ['tongzhuangshui', 'meishi', 'fuzhuang', 'meirong'],
            'structure_type': 'hotspot',
            'content_type': 'graphic',
            'image_count': 5,
            'image_ratio': '9:16',
            'is_premium': True,
            'priority': 8,
        },
        {
            'template_code': 'insider',
            'template_name': '揭秘内幕型',
            'description': '行业秘密 → 验证方法 → 选购建议',
            'applicable_industries': ['tongzhuangshui', 'meishi', 'fuzhuang', 'meirong', 'jiadian'],
            'structure_type': 'insider',
            'content_type': 'graphic',
            'image_count': 6,
            'image_ratio': '9:16',
            'is_premium': True,
            'priority': 9,
        },
        {
            'template_code': 'festival_marketing',
            'template_name': '节日营销型',
            'description': '节日氛围 → 场景关联 → 产品推荐',
            'applicable_industries': ['tongzhuangshui', 'meishi', 'fuzhuang', 'meirong', 'jiaju'],
            'structure_type': 'festival',
            'content_type': 'graphic',
            'image_count': 5,
            'image_ratio': '9:16',
            'is_premium': True,
            'priority': 8,
        },
    ]

    for tpl_data in templates:
        existing = PublicContentTemplate.query.filter_by(
            template_code=tpl_data['template_code']
        ).first()
        if not existing:
            template = PublicContentTemplate(**tpl_data)
            db.session.add(template)

    db.session.commit()
    print(f"[Init] 内容模板初始化完成")


def init_title_templates():
    """初始化标题模板"""
    titles = [
        # 疑问型
        {'template_pattern': '为什么{keyword}都{action}？', 'title_type': '疑问', 'is_premium': False, 'priority': 10},
        {'template_pattern': '{keyword}到底怎么选？', 'title_type': '疑问', 'is_premium': False, 'priority': 9},
        {'template_pattern': '{keyword}的那些坑，你踩过几个？', 'title_type': '疑问', 'is_premium': False, 'priority': 8},
        # 数字型
        {'template_pattern': '{num}个{keyword}的{point}，第{num}个最关键', 'title_type': '数字', 'is_premium': False, 'priority': 9},
        {'template_pattern': '{num}步教你选出好{keyword}', 'title_type': '数字', 'is_premium': False, 'priority': 8},
        # 情感型
        {'template_pattern': '{keyword}翻车了！{action}', 'title_type': '情感', 'is_premium': False, 'priority': 9},
        {'template_pattern': '看完这篇，{keyword}再也不踩坑', 'title_type': '情感', 'is_premium': False, 'priority': 8},
        # 爆款型（付费）
        {'template_pattern': '老板说：用这个招待客户，单子直接签了', 'title_type': '爆款', 'is_premium': True, 'priority': 10},
        {'template_pattern': '客户当场问我公司地址，说下次还来', 'title_type': '爆款', 'is_premium': True, 'priority': 9},
        {'template_pattern': '员工说：用了这个，老板当场给我涨薪', 'title_type': '爆款', 'is_premium': True, 'priority': 8},
    ]

    for title_data in titles:
        existing = PublicTitleTemplate.query.filter_by(
            template_pattern=title_data['template_pattern']
        ).first()
        if not existing:
            title = PublicTitleTemplate(**title_data)
            db.session.add(title)

    db.session.commit()
    print(f"[Init] 标题模板初始化完成")


def init_tag_templates():
    """初始化标签模板"""
    tags = [
        # 桶装水
        {'industry': 'tongzhuangshui', 'tag_source': 'core', 'tags': ['桶装水', '矿泉水', '定制水'], 'priority': 10},
        {'industry': 'tongzhuangshui', 'tag_source': 'pain_point', 'tags': ['饮水健康', '水质', '桶装水配送'], 'priority': 8},
        {'industry': 'tongzhuangshui', 'tag_source': 'scene', 'tags': ['商务接待', '办公室用水', '家庭饮水'], 'priority': 9},
        {'industry': 'tongzhuangshui', 'tag_source': 'long_tail', 'tags': ['桶装水哪个牌子好', '如何辨别水质'], 'priority': 7},
        {'industry': 'tongzhuangshui', 'tag_source': 'hot', 'tags': ['企业定制', '招待用水', '送水服务'], 'is_premium': True, 'priority': 8},
        # 美食餐饮
        {'industry': 'meishi', 'tag_source': 'core', 'tags': ['美食', '好吃', '探店'], 'priority': 10},
        {'industry': 'meishi', 'tag_source': 'scene', 'tags': ['餐厅推荐', '外卖', '家常菜'], 'priority': 8},
        # 更多行业...
    ]

    for tag_data in tags:
        existing = PublicTagTemplate.query.filter_by(
            industry=tag_data['industry'],
            tag_source=tag_data['tag_source']
        ).first()
        if not existing:
            tag = PublicTagTemplate(**tag_data)
            db.session.add(tag)

    db.session.commit()
    print(f"[Init] 标签模板初始化完成")


def init_preset_data():
    """初始化所有预设数据"""
    print("[Init] 开始初始化预设数据...")
    with app.app_context():
        init_pricing_plans()
        init_target_customers()
        init_industry_keywords()
        init_industry_topics()
        init_content_templates()
        init_title_templates()
        init_tag_templates()

        # 初始化公开平台模板（关键词库/选题库模板 + 变量）
        # 如需重新导入 geo-seo skill 模板，执行：
        # from migrations.init_public_template_data import run; run()
        try:
            from migrations.init_public_template_data import import_geo_seo_templates, init_default_variables
            import_geo_seo_templates()
            init_default_variables()
            print("[Init] 公开平台模板初始化完成")
        except Exception as e:
            print(f"[Init] 公开平台模板初始化跳过: {e}")

    print("[Init] 预设数据初始化完成！")


if __name__ == '__main__':
    init_preset_data()
