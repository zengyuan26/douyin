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
    INDUSTRY_DIMENSION_MAP = {
        'education': {
            'industry_aliases': ['教育', '高考', '中考', '考研', '志愿', '升学', '分数线', '录取', '选科'],
            'dimensions': ['score_level', 'need_type', 'time_horizon'],
            'score_level': {
                'name': '分数维度',
                'values': [
                    {'value': '临界分', 'audience': '踩线考生', 'pain': '踩线最危险，必须搞清楚能报什么批次'},
                    {'value': '高分', 'audience': '高分考生家长', 'pain': '想冲名校，要全部批次线都了解'},
                    {'value': '低分', 'audience': '低分考生家长', 'pain': '分数不够，想找所有能报的出路'},
                ],
            },
            'need_type': {
                'name': '需求类型',
                'values': [
                    {'value': '普通类', 'audience': '普通类考生家长', 'pain': '只了解普通批次，不知道还有特殊类型'},
                    {'value': '特殊类', 'audience': '军警师范考生家长', 'pain': '只看过特控线，不知道还要看一本线'},
                    {'value': '艺体类', 'audience': '艺体类考生家长', 'pain': '艺体类批次线计算方式完全不同，不知道怎么算'},
                ],
            },
            'time_horizon': {
                'name': '时间维度',
                'values': [
                    {'value': '高三', 'audience': '高三考生家长', 'pain': '时间紧迫，必须马上做决定'},
                    {'value': '高一高二', 'audience': '高一高二学生家长', 'pain': '还有时间提前规划，想提前了解'},
                ],
            },
        },
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
    def generate_scenes(cls, topic: Dict) -> List[Dict]:
        """为选题生成场景选项列表"""
        # Step 1: 识别选题行业类型
        industry_type = cls._identify_industry(topic)

        # Step 2: 获取该行业对应的维度配置
        dimension_config = cls._get_dimension_config(industry_type)

        # Step 3: 从选题提取关键词和核心概念
        keywords = cls._extract_keywords(topic)
        topic_keyword = cls._get_topic_keyword(keywords, topic)

        # Step 4: 识别痛点类型
        pain_types = cls._identify_pains(keywords)
        primary_pain = pain_types[0][0] if pain_types else 'info'

        # Step 5: 为每个维度生成场景
        scenes = []
        for dim_key in dimension_config['dimensions']:
            dim_info = dimension_config.get(dim_key) or cls.DIMENSION_LIB.get(dim_key)
            if not dim_info:
                continue

            for val_info in dim_info.get('values', []):
                scene = cls._build_scene_v2(
                    dim_key=dim_key,
                    dim_value=val_info['value'],
                    audience_template=val_info['audience'],
                    pain_template=val_info['pain'],
                    topic_keyword=topic_keyword,
                    primary_pain=primary_pain,
                    keywords=keywords,
                    topic=topic,
                )
                if scene:
                    scenes.append(scene)

        # Step 6: 按优先级排序并限制数量
        scenes.sort(key=lambda x: cls.PAIN_PRIORITY.get(x['pain_type'], 99))
        return scenes[:5]

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
        """构建单个场景（v2版本）"""
        pain_info = cls.PAIN_TYPES.get(primary_pain, cls.PAIN_TYPES['info'])

        # 填充人群模板
        industry = topic.get('industry', '')
        audience = audience_template.replace('{行业}', industry or '目标')

        # 组合场景描述
        group = f"{dim_value}的{industry}用户 → {topic_keyword}时"

        # 场景标签
        label = f"{dim_value} - {pain_info['name']}型"

        # 生成痛点问题（替换模板变量）
        pain_question = pain_template

        # 获取风格
        style = cls.PAIN_STYLE_MAP.get(primary_pain, '情绪共鸣')
        style_info = cls.STYLE_INFO.get(style, {})

        return {
            'id': f'scene_{uuid.uuid4().hex[:8]}',
            'pain_type': primary_pain,
            'pain_name': pain_info['name'],
            'pain_desc': pain_info['desc'],
            'label': label,
            'group': group,
            'question': pain_question,
            'style': style,
            'style_icon': style_info.get('icon', '💭'),
            'style_desc': style_info.get('desc', ''),
            'priority': cls.PAIN_PRIORITY.get(primary_pain, 99),
            'urgency': 'high' if primary_pain in ['risk', 'effect'] else 'medium',
            'keywords': keywords[:3],
            'audience': audience,
            'dim_key': dim_key,
            'dim_value': dim_value,
        }

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


scene_generator = SceneGenerator()
