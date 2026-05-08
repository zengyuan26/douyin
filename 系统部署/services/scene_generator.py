"""
通用场景生成器 v2

普适公式：场景 = 选题关键词 × 人群细分维度 × 痛点匹配

核心流程：
1. 从选题提取关键词（核心概念 + 疑问点）
2. 识别选题所属行业类型（教育、医疗、电商等）
3. 自动匹配最相关的人群细分维度
4. 组合人群 + 选题关键词 + 痛点 → 生成场景
"""

import re
import uuid
from typing import List, Dict, Optional

from models.models import db
from models.public_models import SavedPortrait, PublicGeneration, PublicIndustryTopic


class SceneGenerator:
    """通用场景生成器 v2"""

    # ========== 通用痛点库（适用于所有行业） ==========
    PAIN_TYPES = {
        'info': {
            'name': '信息恐慌',
            'desc': '不知道该选什么，缺乏基础知识',
            'signals': ['怎么', '如何', '什么区别', '是什么', '哪些', '哪个好',
                       '什么意思', '包含什么', '包括哪些', '有什么区别', '是什么'],
            'base_questions': ['我该选哪个', '有什么区别', '该怎么选', '要注意什么'],
        },
        'cost': {
            'name': '成本焦虑',
            'desc': '担心价格太高，或觉得不值',
            'signals': ['贵', '便宜', '价格', '性价比', '省钱', '多少钱', '费用',
                       '收费', '预算', '花多少', '值不值', '划算吗', '值得'],
            'base_questions': ['值不值', '太贵了', '有没有更便宜的', '性价比高吗'],
        },
        'risk': {
            'name': '风险担忧',
            'desc': '怕选错、怕踩坑、怕被骗',
            'signals': ['坑', '骗', '假', '注意', '小心', '误区', '陷阱',
                       '后悔', '翻车', '靠谱吗', '真的吗', '安全吗', '有问题'],
            'base_questions': ['会不会踩坑', '靠谱吗', '真的吗', '有什么坑'],
        },
        'effect': {
            'name': '效果怀疑',
            'desc': '担心没有效果，或效果不好',
            'signals': ['效果', '有用吗', '怎么样', '好不好', '真实', '评价',
                       '管用吗', '能不能', '有没有效', '真的吗', '好用吗'],
            'base_questions': ['真的有效果吗', '好不好用', '用过的感受', '效果怎么样'],
        },
        'choice': {
            'name': '选择困难',
            'desc': '选项太多，不知道哪个最适合',
            'signals': ['推荐', '对比', '区别', '哪个', '选哪个', '纠结',
                       '还是', '或者', '比较好', '更合适', '怎么选', '如何选'],
            'base_questions': ['推荐哪个', '有什么区别', 'A还是B', '该怎么选'],
        },
    }

    # ========== 人群细分维度库（行业通用） ==========
    DIMENSION_LIB = {
        'level': {
            'name': '能力等级',
            'desc': '按用户能力/水平划分',
            'values': [
                {
                    'value': '初级',
                    'audience': '{行业}小白',
                    'pain': '刚接触，不知道从哪里下手',
                },
                {
                    'value': '中级',
                    'audience': '有{行业}经验的人',
                    'pain': '遇到瓶颈，不知道怎么提升',
                },
                {
                    'value': '高级',
                    'audience': '{行业}资深用户',
                    'pain': '想要突破天花板，寻找进阶方案',
                },
            ],
            'keywords': ['初级', '中级', '高级', '入门', '进阶', '精通'],
        },
        'frequency': {
            'name': '使用频率',
            'desc': '按用户使用频率划分',
            'values': [
                {
                    'value': '高频用户',
                    'audience': '{行业}高频用户',
                    'pain': '用得多但效率低，想省时间',
                },
                {
                    'value': '低频用户',
                    'audience': '偶尔使用{行业}的人',
                    'pain': '不常用，每次都要重新了解',
                },
                {
                    'value': '新用户',
                    'audience': '{行业}新用户',
                    'pain': '刚接触，不知道怎么选',
                },
            ],
            'keywords': ['经常', '偶尔', '新手', '第一次', '常用', '高频', '低频'],
        },
        'budget': {
            'name': '预算等级',
            'desc': '按用户可承受预算划分',
            'values': [
                {
                    'value': '高预算',
                    'audience': '预算充足的{行业}用户',
                    'pain': '不差钱，但不知道什么最适合',
                },
                {
                    'value': '中预算',
                    'audience': '追求性价比的{行业}用户',
                    'pain': '想花合适的钱，得到最好的效果',
                },
                {
                    'value': '低预算',
                    'audience': '预算有限的{行业}用户',
                    'pain': '钱不多，但不想将就',
                },
            ],
            'keywords': ['贵', '便宜', '省钱', '性价比', '预算', '钱', '费用', '价格'],
        },
        'experience': {
            'name': '经验程度',
            'desc': '按用户过往经验划分',
            'values': [
                {
                    'value': '有经验',
                    'audience': '用过{行业}的人',
                    'pain': '有经验但踩过坑，最想分享',
                },
                {
                    'value': '无经验',
                    'audience': '没接触过{行业}的人',
                    'pain': '完全不懂，怕被骗怕踩坑',
                },
            ],
            'keywords': ['用过', '第一次', '没试过', '新手', '有经验', '踩坑'],
        },
        'urgency': {
            'name': '紧急程度',
            'desc': '按用户需求的紧迫程度划分',
            'values': [
                {
                    'value': '紧急',
                    'audience': '急着解决{行业}问题的人',
                    'pain': '火烧眉毛，必须马上找到答案',
                },
                {
                    'value': '常规',
                    'audience': '有充裕时间研究{行业}的人',
                    'pain': '有时间慢慢选，不想仓促决定',
                },
            ],
            'keywords': ['紧急', '着急', '马上', '立刻', '尽快', '时间紧'],
        },
    }

    # ========== 行业 → 维度映射 ==========
    # 注意：此配置仅作为 fallback，已主要改为从画像动态提取
    INDUSTRY_DIMENSION_MAP = {
        'default': {
            'industry_aliases': [],
            'dimensions': ['level', 'budget', 'experience'],
        },
    }

    # ========== 痛点 → 风格 映射 ==========
    PAIN_STYLE_MAP = {
        'info': '干货科普',
        'cost': '犀利吐槽',
        'risk': '情绪共鸣',
        'effect': '故事叙述',
        'choice': '权威背书',
    }

    # ========== 痛点优先级 ==========
    PAIN_PRIORITY = {
        'risk': 1,
        'effect': 2,
        'cost': 3,
        'choice': 4,
        'info': 5,
    }

    # ========== 内容风格信息 ==========
    STYLE_INFO = {
        '情绪共鸣': {'icon': '💭', 'desc': '引发情感共鸣，建立信任'},
        '干货科普': {'icon': '📚', 'desc': '传递专业知识，降低认知门槛'},
        '故事叙述': {'icon': '📖', 'desc': '讲述真实案例，增强说服力'},
        '权威背书': {'icon': '🏆', 'desc': '专家/机构认证，增强信心'},
        '犀利吐槽': {'icon': '😏', 'desc': '打破常规认知，突出差异化'},
    }

    @classmethod
    def generate_scenes(cls, topic: Dict, account_info: Dict = None) -> List[Dict]:
        """为选题生成场景选项列表

        Args:
            topic: 选题信息
            account_info: 账号信息，包含 account_positioning, brand_name, industry, target_customer 等
        """
        # 获取账号定位信息
        account_positioning = ''
        brand_name = ''
        industry = ''
        target_customer = ''
        if account_info:
            account_positioning = account_info.get('account_positioning', '')
            brand_name = account_info.get('brand_name', '')
            industry = account_info.get('industry', '')
            target_customer = account_info.get('target_customer', '')

        # 如果画像有行业信息，优先使用
        topic_industry = topic.get('industry', '') or industry

        # 获取当前时间信息
        from datetime import datetime
        now = datetime.now()
        month = now.month
        season_info = cls._get_season_info(month)

        # Step 1: 识别选题行业类型（优先用画像行业）
        industry_type = cls._identify_industry(topic, topic_industry)

        # Step 2: 获取该行业对应的维度配置
        dimension_config = cls._get_dimension_config(industry_type)

        # Step 3: 如果有目标客户信息，基于它生成更具体的场景
        if target_customer:
            dimension_config = cls._customize_dimension_with_target(
                dimension_config, target_customer, topic_industry
            )

        # Step 4: 从选题提取关键词和核心概念
        keywords = cls._extract_keywords(topic)
        topic_keyword = cls._get_topic_keyword(keywords, topic)

        # Step 5: 识别痛点类型
        pain_types = cls._identify_pains(keywords)
        primary_pain = pain_types[0][0] if pain_types else 'info'

        # Step 6: 为每个维度生成场景
        scenes = []
        for dim_key in dimension_config['dimensions']:
            dim_info = dimension_config.get(dim_key) or cls.DIMENSION_LIB.get(dim_key)
            if not dim_info:
                continue

            for val_info in dim_info.get('values', []):
                scene = cls._build_scene_v3(
                    dim_key=dim_key,
                    dim_value=val_info['value'],
                    audience_template=val_info['audience'],
                    pain_template=val_info['pain'],
                    topic_keyword=topic_keyword,
                    primary_pain=primary_pain,
                    keywords=keywords,
                    topic=topic,
                    account_positioning=account_positioning,
                    season_info=season_info,
                    industry=topic_industry,  # 传递行业信息
                )
                if scene:
                    scenes.append(scene)

        # Step 7: 按优先级排序并限制数量
        scenes.sort(key=lambda x: cls.PAIN_PRIORITY.get(x['pain_type'], 99))
        return scenes[:5]

    @classmethod
    def _identify_industry(cls, topic: Dict, industry_hint: str = None) -> str:
        """识别选题所属行业类型

        主要依赖画像传入的行业信息，不再硬编码行业关键词
        """
        # 优先使用传入的行业提示（来自画像）
        if industry_hint:
            return industry_hint

        # 回退：从选题行业字段获取
        topic_industry = topic.get('industry', '')
        if topic_industry:
            return topic_industry

        return 'default'

    @classmethod
    def _customize_dimension_with_target(cls, dimension_config: Dict, target_customer: str, industry: str) -> Dict:
        """基于目标客户信息动态生成场景维度

        从目标客户描述中智能提取人群特征，生成贴合业务的场景
        """
        config = dict(dimension_config)
        target_lower = target_customer.lower() if target_customer else ''

        if not target_lower:
            return config

        # 通用人群特征模式库（用于从目标客户描述中识别）
        # 这些模式用于匹配目标客户描述中的关键词，而非硬编码行业
        customer_patterns = [
            # 经验程度
            (['新手', '第一次', '刚开始', '0经验'], '新手', '刚开始接触，不知道从哪里入手'),
            (['老手', '有经验', '用过', '熟悉'], '有经验者', '有一定了解，想深入学习'),

            # 角色身份
            (['妈妈', '宝妈', '妈'], '妈妈群体', '需要照顾家庭，时间精力有限'),
            (['爸爸', '宝爸'], '爸爸群体', '参与育儿，想找到最合适的方案'),
            (['上班族', '职场', '上班', '打工人'], '上班族', '工作忙，只能利用碎片时间'),
            (['全职', '全职带娃'], '全职家长', '有精力深入研究，但需要高效方案'),
            (['新手爸妈', '新手父母', '新手家长'], '新手爸妈', '第一次当爸妈，什么都不懂最焦虑'),

            # 家庭情况
            (['二胎', '两个娃', '两个孩子'], '二胎家庭', '有经验但担心顾不过来'),
            (['双胞胎', '龙凤胎'], '多胎家庭', '开销大，需要性价比方案'),
            (['大宝', '大孩子'], '有大宝的家庭', '需要平衡多个孩子的需求'),

            # 特殊需求
            (['过敏', '敏宝', '敏感'], '过敏体质宝宝家长', '担心过敏问题，选产品最纠结'),
            (['早产', '早产儿'], '早产儿家长', '需要特殊配方或产品'),
            (['体弱', '体质差'], '体质较弱宝宝的家长', '想增强体质但不知道怎么做'),

            # 关注点
            (['价格', '便宜', '省钱', '性价比'], '价格敏感型', '预算有限，想找到最划算的选择'),
            (['高端', '品质', '贵', '最好'], '品质优先型', '不差钱，要最好的'),
            (['效果', '有用', '管用'], '效果导向型', '最关心实际效果'),
            (['成分', '配方', '配料'], '成分研究型', '喜欢研究配料表和成分'),
            (['安全', '放心', '健康'], '安全优先型', '最关心安全性和健康'),
        ]

        matched_values = []
        for keywords, label, pain in customer_patterns:
            for kw in keywords:
                if kw in target_lower:
                    matched_values.append({
                        'value': label,
                        'audience': label,
                        'pain': pain
                    })
                    break

        # 去重
        seen = set()
        unique_values = []
        for v in matched_values:
            if v['value'] not in seen:
                seen.add(v['value'])
                unique_values.append(v)

        # 如果匹配到人群特征，插入到维度配置前面
        if unique_values:
            config['dimensions'] = ['customer_segment'] + config.get('dimensions', [])[:2]
            config['customer_segment'] = {
                'name': '目标人群细分',
                'values': unique_values[:3]  # 最多3个
            }

        return config

    @classmethod
    def _get_season_info(cls, month: int) -> Dict:
        """获取当前季节信息"""
        season_map = {
            3: {'season': '春季', 'keyword': '春季', 'tip': '春季高发问题'},
            4: {'season': '春季', 'keyword': '春季', 'tip': '春季高发问题'},
            5: {'season': '春季', 'keyword': '春季', 'tip': '春季高发问题'},
            6: {'season': '夏季', 'keyword': '暑期', 'tip': '暑期热门话题'},
            7: {'season': '夏季', 'keyword': '暑期', 'tip': '暑期热门话题'},
            8: {'season': '夏季', 'keyword': '暑期', 'tip': '暑期热门话题'},
            9: {'season': '秋季', 'keyword': '秋季', 'tip': '秋季常见问题'},
            10: {'season': '秋季', 'keyword': '秋季', 'tip': '秋季常见问题'},
            11: {'season': '秋季', 'keyword': '秋季', 'tip': '秋季常见问题'},
            12: {'season': '冬季', 'keyword': '冬季', 'tip': '冬季热点话题'},
            1: {'season': '冬季', 'keyword': '寒假期', 'tip': '寒期热门话题'},
            2: {'season': '冬季', 'keyword': '春季开学', 'tip': '开学季问题'},
        }
        return season_map.get(month, {'season': '', 'keyword': '', 'tip': ''})

    @classmethod
    def _identify_industry(cls, topic: Dict) -> str:
        """识别选题所属行业类型"""
        title = topic.get('title', '')
        industry = topic.get('industry', '')

        for ind_key, ind_info in cls.INDUSTRY_DIMENSION_MAP.items():
            if ind_key == 'default':
                continue
            for alias in ind_info['industry_aliases']:
                if alias in title or alias in industry:
                    return ind_key

        return 'default'

    @classmethod
    def _get_dimension_config(cls, industry_type: str) -> Dict:
        """获取行业对应的维度配置"""
        ind_info = cls.INDUSTRY_DIMENSION_MAP.get(industry_type)
        if not ind_info:
            ind_info = cls.INDUSTRY_DIMENSION_MAP['default']

        return ind_info

    @classmethod
    def _extract_keywords(cls, topic: Dict) -> List[str]:
        """从选题中提取关键词"""
        keywords = []
        title = topic.get('title', '')
        existing_keywords = topic.get('keywords', [])

        if isinstance(existing_keywords, list):
            keywords.extend([str(k).strip() for k in existing_keywords if k])

        quoted = re.findall(r'["""\'\']([^"""\']+)["""\']', title)
        keywords.extend(quoted)

        question_patterns = [
            r'(?:怎么|如何|为什么|什么|哪些|哪个|是不是|能不能)([^\s，。!?：:；;]{1,10})',
            r'([^\s，。!?：:；;]{1,6})(?:吗|么|吧|呀|呢)',
            r'(?:选|用|买|做|搞|找|定)([^\s，。!?]{1,6})',
            r'([^\s，。!?]{1,8})(?:的区别|的是什么|有哪些)',
        ]
        for pattern in question_patterns:
            matches = re.findall(pattern, title)
            keywords.extend(matches)

        numbers = re.findall(r'(\d+[分线元角]+|\d+%|\d+年期)', title)
        keywords.extend(numbers)

        return list(set([k for k in keywords if k and len(k) > 1]))

    @classmethod
    def _identify_pains(cls, keywords: List[str]) -> List[tuple]:
        """根据关键词识别痛点类型"""
        pain_scores = {}

        for kw in keywords:
            for pain_key, pain_info in cls.PAIN_TYPES.items():
                for signal in pain_info['signals']:
                    if signal in kw or kw in signal:
                        if pain_key not in pain_scores:
                            pain_scores[pain_key] = 0
                        pain_scores[pain_key] += 1
                        break

        if not pain_scores:
            pain_scores['info'] = 1

        return sorted(pain_scores.items(), key=lambda x: x[1], reverse=True)

    @classmethod
    def _get_topic_keyword(cls, keywords: List[str], topic: Dict) -> str:
        """获取选题的核心关键词"""
        title = topic.get('title', '')

        words_to_remove = [
            '怎么', '如何', '为什么', '什么', '是不是', '能不能',
            '哪个', '哪些', '好吗', '吗', '呢', '吧', '呀',
            '的区别', '是什么', '有哪些', '怎么办', '怎么样'
        ]

        title_keywords = []
        for kw in keywords:
            if kw in title:
                is_core = True
                for remove_word in words_to_remove:
                    if remove_word in kw:
                        is_core = False
                        break
                if is_core:
                    title_keywords.append(kw)

        if title_keywords:
            return title_keywords[0]

        return title[:8] if title else "核心问题"

    @classmethod
    def _build_scene_v2(cls, dim_key: str, dim_value: str, audience_template: str,
                       pain_template: str, topic_keyword: str, primary_pain: str,
                       keywords: List[str], topic: Dict) -> Optional[Dict]:
        """构建单个场景（v2版本，兼容旧调用）"""
        return cls._build_scene_v3(
            dim_key=dim_key,
            dim_value=dim_value,
            audience_template=audience_template,
            pain_template=pain_template,
            topic_keyword=topic_keyword,
            primary_pain=primary_pain,
            keywords=keywords,
            topic=topic,
            account_positioning='',
            season_info={},
        )

    @classmethod
    def _build_scene_v3(cls, dim_key: str, dim_value: str, audience_template: str,
                       pain_template: str, topic_keyword: str, primary_pain: str,
                       keywords: List[str], topic: Dict,
                       account_positioning: str = '',
                       season_info: Dict = None,
                       industry: str = '') -> Optional[Dict]:
        """构建单个场景（v3版本 - 含账号定位和季节信息、行业信息）"""
        if season_info is None:
            season_info = {}

        pain_info = cls.PAIN_TYPES.get(primary_pain, cls.PAIN_TYPES['info'])

        # 优先使用传入的行业信息，其次从 topic 获取
        industry_name = industry or topic.get('industry', '') or '目标用户'

        # 获取风格
        style = cls.PAIN_STYLE_MAP.get(primary_pain, '情绪共鸣')
        style_info = cls.STYLE_INFO.get(style, {})

        # 构建易懂的用户标签
        user_friendly_label = audience

        # 人群描述：痛点问题
        user_friendly_desc = pain_template

        # 构建推荐理由（结合账号定位 + 季节 + 风格）
        recommendation_reasons = []

        # 1. 结合账号定位推荐
        if account_positioning:
            # 提取账号定位中的关键词
            positioning_keywords = cls._extract_keywords_from_text(account_positioning)
            if positioning_keywords:
                recommendation_reasons.append(f"符合账号定位「{account_positioning[:20]}...」")

        # 2. 结合季节推荐
        if season_info.get('tip'):
            recommendation_reasons.append(f"{season_info.get('tip')}，需求量大")

        # 3. 内容风格建议
        recommendation_reasons.append(f"建议{style}风格，{style_info.get('desc', '')}")

        # 4. 痛点强度
        if primary_pain == 'risk':
            recommendation_reasons.append("情绪共鸣强，容易引发转发")
        elif primary_pain == 'effect':
            recommendation_reasons.append("真实案例，增强说服力")
        elif primary_pain == 'info':
            recommendation_reasons.append("干货内容，高收藏率")

        user_friendly_reason = " | ".join(recommendation_reasons[:2])  # 最多2条理由

        return {
            'id': f'scene_{uuid.uuid4().hex[:8]}',
            'pain_type': primary_pain,
            'pain_name': pain_info['name'],
            'pain_desc': pain_info['desc'],
            'label': user_friendly_label,
            'audience': audience,
            'question': user_friendly_desc,
            'reason': user_friendly_reason,
            'group': f"{dim_value} → {topic_keyword}",
            'style': style,
            'style_icon': style_info.get('icon', '💭'),
            'style_desc': style_info.get('desc', ''),
            'priority': cls.PAIN_PRIORITY.get(primary_pain, 99),
            'urgency': 'high' if primary_pain in ['risk', 'effect'] else 'medium',
            'keywords': keywords[:3],
            'dim_key': dim_key,
            'dim_value': dim_value,
        }

    @classmethod
    def _extract_keywords_from_text(cls, text: str) -> List[str]:
        """从文本中提取关键词"""
        if not text:
            return []
        # 简单分词：按标点和常见分隔符分割
        import re
        words = re.split(r'[，。！？、；：""''【】（）\s,!?;:\'\"()\[\]]+', text)
        return [w.strip() for w in words if len(w.strip()) >= 2][:5]

    @classmethod
    def get_style_for_pain(cls, pain_type: str) -> str:
        """根据痛点获取推荐的内容风格"""
        return cls.PAIN_STYLE_MAP.get(pain_type, '情绪共鸣')

    @classmethod
    def get_style_info(cls, style: str) -> Dict:
        """获取内容风格的详细信息"""
        return cls.STYLE_INFO.get(style, {
            'icon': '💭',
            'desc': '通用风格',
        })

    @classmethod
    def _normalize_scene_options(cls, scene_options: list) -> list:
        """
        将旧格式场景选项转换为新格式，并确保所有必要字段存在。

        旧格式：[{ "id": "...", "标签": "...", "组合": "...", "风格": "..." }]
        新格式：[{ "id": "...", "pain_name": "...", "group": "...", "style": "..." }]
        LLM新格式：[{ "label": "...", "audience": "...", "pain": "...", "pain_type": "...", "content_form": "..." }]
        """
        if not scene_options:
            return []

        normalized = []
        for scene in scene_options:
            # 检查是否是 LLM 新格式（有 label/audience/pain 但没有 pain_name）
            if 'label' in scene and 'audience' in scene and 'pain' in scene:
                pain_type = scene.get('pain_type', 'info')
                new_scene = {
                    'id': scene.get('id', f'scene_{uuid.uuid4().hex[:8]}'),
                    'pain_type': pain_type,
                    'pain_name': scene.get('label', '通用场景'),
                    'pain_desc': scene.get('pain', ''),
                    'label': scene.get('label', '通用场景'),
                    'group': scene.get('audience', ''),
                    'question': scene.get('pain', '怎么办'),
                    'style': cls.get_style_for_pain(pain_type),  # 根据痛点类型推断风格
                    'priority': 2,
                    'urgency': 'medium',
                    'keywords': [],
                    'audience': scene.get('audience', ''),
                    'content_form': scene.get('content_form', ''),  # LLM 新增的内容形式
                    'reason': scene.get('pain', ''),  # 推荐理由
                }
                normalized.append(new_scene)
                continue

            if 'pain_name' in scene or 'label' in scene:
                # 确保有 style 字段
                if 'style' not in scene:
                    scene['style'] = cls.get_style_for_pain(scene.get('pain_type', 'info'))
                normalized.append(scene)
                continue

            new_scene = {
                'id': scene.get('id', f'scene_{uuid.uuid4().hex[:8]}'),
                'pain_type': cls._infer_pain_type_from_style(scene.get('风格', '')),
                'pain_name': scene.get('标签', '通用场景').replace('型', ''),
                'pain_desc': scene.get('组合', ''),
                'label': scene.get('标签', '通用场景'),
                'group': scene.get('组合', ''),
                'question': scene.get('组合', '怎么办'),
                'style': scene.get('风格', '情绪共鸣'),
                'priority': cls._infer_priority_from_style(scene.get('风格', '')),
                'urgency': 'medium',
                'keywords': [],
                'audience': cls._extract_audience_from_label(scene.get('标签', '')),
            }
            normalized.append(new_scene)

        normalized.sort(key=lambda x: x.get('priority', 99))
        return normalized[:5]

    @classmethod
    def _infer_pain_type_from_style(cls, style: str) -> str:
        style_pain_map = {
            '情绪共鸣': 'risk',
            '干货科普': 'info',
            '故事叙述': 'effect',
            '权威背书': 'choice',
            '犀利吐槽': 'cost',
        }
        return style_pain_map.get(style, 'info')

    @classmethod
    def _infer_priority_from_style(cls, style: str) -> int:
        style_priority_map = {
            '情绪共鸣': 1,
            '干货科普': 5,
            '故事叙述': 2,
            '权威背书': 4,
            '犀利吐槽': 3,
        }
        return style_priority_map.get(style, 5)

    @classmethod
    def _extract_audience_from_label(cls, label: str) -> str:
        if not label:
            return '目标用户'
        label = label.replace('型', '')
        if '-' in label:
            return label.split('-')[0].strip()
        return label

    DEFAULT_SCENE_TEMPLATES = [
        # pain_type, 痛点名称, 内容风格, 默认受众, 痛点描述
        {'pain_type': 'info',     'pain_name': '信息恐慌', 'style': '干货科普',
         'audience': '信息匮乏的用户', 'desc': '不了解相关知识，需要科普指导'},
        {'pain_type': 'cost',    'pain_name': '成本焦虑', 'style': '犀利吐槽',
         'audience': '价格敏感型用户', 'desc': '担心花冤枉钱，需要性价比分析'},
        {'pain_type': 'risk',    'pain_name': '风险担忧', 'style': '情绪共鸣',
         'audience': '谨慎型用户', 'desc': '担心风险和后果，需要安全感'},
        {'pain_type': 'effect',  'pain_name': '效果怀疑', 'style': '故事叙述',
         'audience': '效果存疑的用户', 'desc': '怀疑效果真实性，需要真实案例'},
        {'pain_type': 'choice',  'pain_name': '选择困难', 'style': '权威背书',
         'audience': '选择困难型用户', 'desc': '选择太多太难，需要专业建议'},
    ]

    @classmethod
    def _fill_scene_options_to_min(cls, scene_options: list, topic_title: str = '',
                                   account_positioning: str = '', season_info: Dict = None) -> list:
        if scene_options is None:
            scene_options = []
        if season_info is None:
            season_info = {}

        existing_types = set(s.get('pain_type', 'info') for s in scene_options)
        count = len(scene_options)
        next_id = count

        for tmpl in cls.DEFAULT_SCENE_TEMPLATES:
            if count >= 5:
                break
            if tmpl['pain_type'] in existing_types:
                continue

            # 构建推荐理由
            recommendation_reasons = []
            if account_positioning:
                recommendation_reasons.append(f"符合账号定位「{account_positioning[:15]}...」")
            if season_info.get('tip'):
                recommendation_reasons.append(f"{season_info.get('tip')}，需求量大")
            recommendation_reasons.append(f"建议{tmpl['style']}风格")

            scene_options.append({
                'id': f'scene_default_{next_id}',
                'pain_type': tmpl['pain_type'],
                'pain_name': tmpl['pain_name'],
                'pain_desc': tmpl['desc'],
                'label': tmpl['audience'],
                'audience': tmpl['audience'],
                'question': tmpl['desc'],
                'reason': ' | '.join(recommendation_reasons[:2]),
                'group': topic_title,
                'style': tmpl['style'],
                'priority': count + 1,
                'urgency': 'medium',
                'keywords': [],
                'dim_key': 'default',
                'dim_value': tmpl['pain_type'],
            })
            existing_types.add(tmpl['pain_type'])
            next_id += 1
            count += 1

        return scene_options

    @classmethod
    def enrich_topics_with_scene_options(cls, topics: list, account_info: Dict = None) -> list:
        """
        为选题列表补充 scene_options 和 content_style 字段。

        Args:
            topics: 选题列表
            account_info: 账号信息，包含 account_positioning, brand_name 等
        """
        # 获取账号定位信息
        account_positioning = ''
        if account_info:
            account_positioning = account_info.get('account_positioning', '')

        # 获取当前季节信息
        from datetime import datetime
        now = datetime.now()
        season_info = cls._get_season_info(now.month)

        enriched = []
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            t = dict(topic)

            if isinstance(t.get('scene_options'), list) and len(t.get('scene_options', [])) > 0:
                t['scene_options'] = cls._normalize_scene_options(t['scene_options'])
                t['scene_options'] = cls._fill_scene_options_to_min(
                    t['scene_options'], t.get('title', ''),
                    account_positioning=account_positioning, season_info=season_info
                )
                t['content_style'] = t.get('content_style', '') or (
                    t['scene_options'][0]['style'] if t['scene_options'] else ''
                )
            elif 'industry' in t and 'title' in t:
                db_topic = PublicIndustryTopic.query.filter_by(title=t['title']).first()
                if db_topic and db_topic.scene_options:
                    t['scene_options'] = cls._normalize_scene_options(db_topic.scene_options)
                    t['scene_options'] = cls._fill_scene_options_to_min(
                        t['scene_options'], t.get('title', ''),
                        account_positioning=account_positioning, season_info=season_info
                    )
                    t['content_style'] = db_topic.content_style or (
                        t['scene_options'][0]['style'] if t['scene_options'] else ''
                    )
                else:
                    t['scene_options'] = cls.generate_scenes(t, account_info=account_info)
                    t['scene_options'] = cls._fill_scene_options_to_min(
                        t['scene_options'], t.get('title', ''),
                        account_positioning=account_positioning, season_info=season_info
                    )
                    t['content_style'] = t.get('content_style', '') or (
                        t['scene_options'][0]['style'] if t['scene_options'] else ''
                    )
            else:
                t['scene_options'] = cls.generate_scenes(t, account_info=account_info)
                t['scene_options'] = cls._fill_scene_options_to_min(
                    t['scene_options'], t.get('title', ''),
                    account_positioning=account_positioning, season_info=season_info
                )
                t['content_style'] = t.get('content_style', '') or (
                    t['scene_options'][0]['style'] if t['scene_options'] else ''
                )

            enriched.append(t)

        return enriched


scene_generator = SceneGenerator()
