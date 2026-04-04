"""
统一关键词库 + 选题库生成服务

核心能力：
1. 一次 LLM 调用完成双库生成（100关键词 + 100选题）
2. 严格按 C/B 端动态调整分类数量比例
3. 关键词禁用红海大词，选题精准区分种草型/转化型
4. 新增 industry_tag 和 4 档优先级
5. MD5 缓存机制（1 小时 TTL）

输入字段：
- business_desc: 核心业务描述
- service_scenario: 7大标准场景
- business_type: 经营类型（product/personal= C端；local_service/enterprise= B端）
- problem_list: user_problem_types + buyer_concern_types
- portraits: 5个精准画像
- scenario_base_personas: 三层主干人群
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from services.llm import get_llm_service

import logging
logger = logging.getLogger(__name__)



# 三大需求底盘定义（固定不变，全链路以此为基础）
THREE_BASES = {
    '刚需痛点': {
        'name': '刚需痛点盘',
        'keyword_ratio': 0.30,   # 30% 关键词来自此盘
        'topic_ratio': 0.30,     # 30% 选题来自此盘
        'content_direction': '转化型',
    },
    '前置观望': {
        'name': '前置观望搜前种草盘',
        'keyword_ratio': 0.50,   # 50% 关键词来自此盘
        'topic_ratio': 0.50,     # 50% 选题来自此盘
        'content_direction': '种草型',
    },
    '使用配套': {
        'name': '使用配套搜后种草盘',
        'keyword_ratio': 0.20,   # 20% 关键词来自此盘
        'topic_ratio': 0.20,     # 20% 选题来自此盘
        'content_direction': '种草型',
    },
}

# 关键词库分类严格对应三盘
# ①刚需痛点盘 → 使用者问题词 + 付费者顾虑词（直接需求）
# ②前置观望搜前种草盘 → 搜前上游词（行业上游/认知科普）
# ③使用配套搜后种草盘 → 搜后周边词（周边工具/养护留存）
# C端经营类型
C端_TYPES = {'product', 'personal'}
# B端经营类型
B端_TYPES = {'local_service', 'enterprise'}

# 关键词库分类配置（严格按三盘分配，关键词数量从对应问题推导）
# 三盘比例：前置观望搜前种草盘 50% / 刚需痛点盘 30% / 使用配套搜后种草盘 20%
# 强制规则：对比选型/决策安心/上下游/原料/配料/工具/对比等全部固定归类，禁止AI自由发挥
# C端经营类型
C端_TYPES = {'product', 'personal'}
# B端经营类型
B端_TYPES = {'local_service', 'enterprise'}

# 关键词库分类配置（严格按三盘分配）
# 合计约100个
KEYWORD_CATEGORIES_C端 = [
    # ①前置观望搜前种草盘（50%≈50个）：专抓前期迷茫/做对比/查原因客户，不推产品
    {'name': '对比型搜索关键词', 'key': 'compare', 'base': '前置观望', 'min': 15,
     'desc': 'A与B区别/选型对比/哪种更好/划算对比/品牌对比，问题导向，不推产品'},
    {'name': '症状疑问关键词', 'key': 'symptom', 'base': '前置观望', 'min': 10,
     'desc': '前期症状/问题征兆疑问型词，捕捉犹豫期客户'},
    {'name': '原因分析关键词', 'key': 'cause', 'base': '前置观望', 'min': 10,
     'desc': '为什么会/原因分析/形成机理，从评论区挖认知需求'},
    {'name': '上游供应链原料选材关键词', 'key': 'upstream', 'base': '前置观望', 'min': 8,
     'desc': '原料/材质/供应链/选材/鉴别知识，上游关联词'},
    {'name': '避坑科普关键词', 'key': 'pitfall', 'base': '前置观望', 'min': 5,
     'desc': '避坑/误区/骗局/怎么分辨/如何避免，辟谣类词'},
    {'name': '行情价格关键词', 'key': 'price', 'base': '前置观望', 'min': 5,
     'desc': '价格/报价/行情/行情波动/成本构成问题词'},

    # ②刚需痛点盘（30%≈30个）：强化决策鼓励+打消顾虑，解决临门一脚
    {'name': '直接需求关键词', 'key': 'direct', 'base': '刚需痛点', 'min': 10,
     'desc': '核心词+品质服务词，直接表达购买意向'},
    {'name': '痛点关键词', 'key': 'pain_point', 'base': '刚需痛点', 'min': 10,
     'desc': '问题型+担心型+后果型，从评论区挖痛点'},
    {'name': '决策鼓励关键词', 'key': 'decision_encourage', 'base': '刚需痛点', 'min': 5,
     'desc': '用完症状加重/有副作用/出现不适怎么办，临门一脚打消顾虑类'},
    {'name': '安心保障关键词', 'key': 'reassure', 'base': '刚需痛点', 'min': 5,
     'desc': '用完有不适反应/症状加重商家怎么处理，强化使用信心类'},

    # ③使用配套搜后种草盘（20%≈20个）
    {'name': '实操技巧关键词', 'key': 'skill', 'base': '使用配套', 'min': 8,
     'desc': '实操方法/步骤流程/晾晒保存/配方调料/辅料佐料（搜后种草）'},
    {'name': '工具耗材关键词', 'key': 'tools', 'base': '使用配套', 'min': 5,
     'desc': '专用工具/周边耗材/后期养护/升级推荐（搜后种草）'},
    {'name': '行业关联关键词', 'key': 'industry', 'base': '使用配套', 'min': 5,
     'desc': '上下游业务关联词，行业生态（搜后种草）'},
    {'name': '地域季节关键词', 'key': 'region_season', 'base': '使用配套', 'min': 5,
     'desc': '地域词+季节词，本地+时效性（搜后种草）'},
]

KEYWORD_CATEGORIES_B端 = [
    # ①前置观望搜前种草盘（50%≈50个）
    {'name': '对比型搜索关键词', 'key': 'compare', 'base': '前置观望', 'min': 15,
     'desc': 'A与B区别/选型对比/哪种更好/划算对比，B端采购决策参考'},
    {'name': '症状疑问关键词', 'key': 'symptom', 'base': '前置观望', 'min': 10,
     'desc': '前期症状/问题征兆疑问型词'},
    {'name': '原因分析关键词', 'key': 'cause', 'base': '前置观望', 'min': 10,
     'desc': '为什么会/原因分析/形成机理'},
    {'name': '上游供应链原料选材关键词', 'key': 'upstream', 'base': '前置观望', 'min': 8,
     'desc': '原料/材质/供应链/选材/鉴别知识'},
    {'name': '避坑科普关键词', 'key': 'pitfall', 'base': '前置观望', 'min': 5,
     'desc': '避坑/误区/骗局/怎么分辨，B端采购防骗'},
    {'name': '行情价格关键词', 'key': 'price', 'base': '前置观望', 'min': 5,
     'desc': '价格/报价/行情/行情波动/成本构成，B端预算参考'},

    # ②刚需痛点盘（30%≈30个）
    {'name': '直接需求关键词', 'key': 'direct', 'base': '刚需痛点', 'min': 10,
     'desc': '核心词+品质服务词，直接表达B端采购意向'},
    {'name': '痛点关键词', 'key': 'pain_point', 'base': '刚需痛点', 'min': 10,
     'desc': '问题型+担心型+后果型'},
    {'name': '决策鼓励关键词', 'key': 'decision_encourage', 'base': '刚需痛点', 'min': 5,
     'desc': '用完症状加重/有副作用/出现不适怎么办，临门一脚打消顾虑'},
    {'name': '安心保障关键词', 'key': 'reassure', 'base': '刚需痛点', 'min': 5,
     'desc': '用完有不适/症状加重商家怎么处理，强化B端使用信心'},

    # ③使用配套搜后种草盘（20%≈20个）
    {'name': '实操技巧关键词', 'key': 'skill', 'base': '使用配套', 'min': 8,
     'desc': '实操方法/步骤流程/晾晒保存/配方调料（搜后种草）'},
    {'name': '工具耗材关键词', 'key': 'tools', 'base': '使用配套', 'min': 5,
     'desc': '专用工具/周边耗材/后期养护/升级推荐（搜后种草）'},
    {'name': '行业关联关键词', 'key': 'industry', 'base': '使用配套', 'min': 5,
     'desc': '上下游业务关联词，行业生态（搜后种草）'},
    {'name': '地域季节关键词', 'key': 'region_season', 'base': '使用配套', 'min': 5,
     'desc': '地域词+季节词，本地+时效性（搜后种草）'},
]

# 选题库分类：严格按三盘输出选题方向
# 三盘比例：前置观望搜前种草盘 50% / 刚需痛点盘 30% / 使用配套搜后种草盘 20%
# 内容方向：前置观望盘=种草型；刚需痛点盘=转化型；使用配套盘=种草型
# 强制规则：对比选型/决策安心/上下游/实操等全部固定归类，选题方向不得跨界
TOPIC_SERIES_C端 = [
    # ①前置观望搜前种草盘（50%≈50个）：种草型，专抓前期迷茫/做对比/查原因客户
    {'name': '对比选型系列', 'key': 'compare', 'base': '前置观望', 'min': 15,
     'desc': '使用不同产品后的症状反应对比/体感对比分析，种草型'},
    {'name': '原因分析系列', 'key': 'cause', 'base': '前置观望', 'min': 10,
     'desc': '为什么会/原因分析/形成机理，认知教育，种草型'},
    {'name': '上游科普系列', 'key': 'upstream', 'base': '前置观望', 'min': 10,
     'desc': '原料/材质/供应链/选材鉴别知识，行业上游，种草型'},
    {'name': '避坑指南系列', 'key': 'pitfall', 'base': '前置观望', 'min': 8,
     'desc': '避坑/误区/骗局/怎么分辨，行业防骗指南，种草型'},
    {'name': '行情价格系列', 'key': 'price', 'base': '前置观望', 'min': 7,
     'desc': '价格/报价/行情/成本构成，B端采购预算参考，种草型'},

    # ②刚需痛点盘（30%≈30个）：转化型，强化决策安心，解决临门一脚
    {'name': '痛点解决系列', 'key': 'pain_point', 'base': '刚需痛点', 'min': 10,
     'desc': '直面核心痛点，提供解决方案，引导成交，转化型'},
    {'name': '决策安心系列', 'key': 'decision_encourage', 'base': '刚需痛点', 'min': 10,
     'desc': '用完症状加重/有副作用/出现不适怎么办，打消顾虑，转化型'},
    {'name': '效果验证系列', 'key': 'effect_proof', 'base': '刚需痛点', 'min': 10,
     'desc': '产品效果对比/使用前后对比/真实案例，建立信任，转化型'},

    # ③使用配套搜后种草盘（20%≈20个）：种草型，使用后实操留存
    {'name': '实操技巧系列', 'key': 'skill', 'base': '使用配套', 'min': 10,
     'desc': '使用后方法/步骤流程/晾晒保存/配方调料/辅料佐料，种草型'},
    {'name': '工具耗材系列', 'key': 'tools', 'base': '使用配套', 'min': 5,
     'desc': '专用工具/周边耗材/后期养护推荐，种草型'},
    {'name': '行业关联系列', 'key': 'industry', 'base': '使用配套', 'min': 5,
     'desc': '上下游关联/复购引导/升级推荐，种草型'},
]

TOPIC_SERIES_B端 = [
    # ①前置观望搜前种草盘（50%≈50个）：种草型
    {'name': '对比选型系列', 'key': 'compare', 'base': '前置观望', 'min': 15,
     'desc': 'B端使用后症状对比/异常反应对比分析，种草型'},
    {'name': '原因分析系列', 'key': 'cause', 'base': '前置观望', 'min': 10,
     'desc': '为什么会/原因分析/形成机理，B端需求理解，种草型'},
    {'name': '上游科普系列', 'key': 'upstream', 'base': '前置观望', 'min': 10,
     'desc': '原料/材质/供应链/选材鉴别知识，行业上游，种草型'},
    {'name': '避坑指南系列', 'key': 'pitfall', 'base': '前置观望', 'min': 8,
     'desc': '避坑/误区/骗局/怎么分辨，B端采购防骗，种草型'},
    {'name': '行情价格系列', 'key': 'price', 'base': '前置观望', 'min': 7,
     'desc': '价格/报价/行情/成本构成，B端预算规划，种草型'},

    # ②刚需痛点盘（30%≈30个）：转化型
    {'name': '痛点解决系列', 'key': 'pain_point', 'base': '刚需痛点', 'min': 10,
     'desc': '直面B端核心痛点，提供解决方案，引导采购，转化型'},
    {'name': '决策安心系列', 'key': 'decision_encourage', 'base': '刚需痛点', 'min': 10,
     'desc': '用完症状加重/有副作用/出现不适怎么办，长期合作安心，转化型'},
    {'name': '效果验证系列', 'key': 'effect_proof', 'base': '刚需痛点', 'min': 10,
     'desc': 'B端效果案例/使用前后对比/行业口碑，转化型'},

    # ③使用配套搜后种草盘（20%≈20个）：种草型
    {'name': '实操技巧系列', 'key': 'skill', 'base': '使用配套', 'min': 10,
     'desc': 'B端使用后方法/维护流程/配套方案，种草型'},
    {'name': '工具耗材系列', 'key': 'tools', 'base': '使用配套', 'min': 5,
     'desc': 'B端专用工具/周边耗材/升级推荐，种草型'},
    {'name': '行业关联系列', 'key': 'industry', 'base': '使用配套', 'min': 5,
     'desc': 'B端上下游关联/增值服务推荐，种草型'},
]

# 场景标签映射
SCENARIO_TAG_MAP = {
    'hotel_restaurant': '酒店餐饮',
    'residential': '家用住宅',
    'office_enterprise': '企业办公',
    'institutional': '机构单位',
    'retail_chain': '零售连锁',
    'renovation': '装修工程',
    'food_processing': '食品加工',
    'other': '其他场景',
}

# 优先级定义
PRIORITY_CONFIG = {
    '⭐⭐⭐⭐⭐': {'min_score': 80, 'max_ratio': 0.20},  # 最高优先级 ≤20%
    '⭐⭐⭐⭐': {'min_score': 60, 'max_ratio': 0.30},    # 高优先级 ≤30%
    '⭐⭐⭐': {'min_score': 40, 'max_ratio': 0.40},     # 中优先级 ≤40%
    '⭐⭐': {'min_score': 0, 'max_ratio': 0.10},        # 低优先级 ≤10%
}


def _is_c端(business_type: str) -> bool:
    return business_type in C端_TYPES


def _get_industry_tags(business_desc: str, service_scenario: str) -> List[str]:
    """自动识别行业标签"""
    tags = []
    desc_lower = business_desc.lower()

    # 从业务描述推断
    if any(kw in desc_lower for kw in ['酒店', '餐厅', '餐饮', '饭店', '食堂', '厨房', '后厨']):
        tags.append('餐饮行业')
    if any(kw in desc_lower for kw in ['医院', '诊所', '医疗', '药店']):
        tags.append('医疗行业')
    if any(kw in desc_lower for kw in ['学校', '教育', '培训', '幼儿园']):
        tags.append('教育行业')
    if any(kw in desc_lower for kw in ['工厂', '车间', '制造', '生产']):
        tags.append('制造业')
    if any(kw in desc_lower for kw in ['小区', '业主', '物业', '家政']):
        tags.append('物业家政')
    if any(kw in desc_lower for kw in ['装修', '工装', '工程']):
        tags.append('装修工程')
    if any(kw in desc_lower for kw in ['母婴', '奶粉', '婴儿', '童装']):
        tags.append('母婴行业')
    if any(kw in desc_lower for kw in ['食品', '加工', '肉铺', '灌肠', '香肠']):
        tags.append('食品加工')
    if any(kw in desc_lower for kw in ['水', '饮料', '桶装水', '定制水']):
        tags.append('饮品行业')
    if any(kw in desc_lower for kw in ['餐具', '餐盘', '瓷器']):
        tags.append('餐具行业')

    # 从场景推断
    if service_scenario:
        scenario_tag = SCENARIO_TAG_MAP.get(service_scenario)
        if scenario_tag and scenario_tag not in tags:
            tags.append(f'{scenario_tag}行业')

    # 默认兜底
    if not tags:
        tags.append('通用行业')

    return tags[:3]  # 最多3个标签


def _build_category_distribution(is_c端: bool, total: int = 100) -> Dict[str, int]:
    """构建分类数量分布"""
    cats = KEYWORD_CATEGORIES_C端 if is_c端 else KEYWORD_CATEGORIES_B端
    distribution = {}
    for cat in cats:
        distribution[cat['key']] = cat['min']
    return distribution


def _build_series_distribution(is_c端: bool, total: int = 100) -> Dict[str, int]:
    """构建选题系列数量分布"""
    series = TOPIC_SERIES_C端 if is_c端 else TOPIC_SERIES_B端
    distribution = {}
    for s in series:
        distribution[s['key']] = s['min']
    return distribution


def _make_cache_key(params: Dict) -> str:
    """基于输入数据生成 MD5 缓存键（含 user_id 隔离）"""
    # user_id 必须参与缓存键，防止跨用户数据泄露
    cache_data = {
        'user_id': params.get('user_id', 'anonymous'),
        'business_desc': params.get('business_desc', ''),
        'service_scenario': params.get('service_scenario', ''),
        'business_type': params.get('business_type', ''),
    }
    # 加入问题概要
    problem_list = params.get('problem_list', {})
    if problem_list.get('user_problem_types'):
        cache_data['user_problems'] = [
            f"{p.get('problem_type', '')}:{p.get('description', '')[:20]}"
            for p in problem_list['user_problem_types'][:5]
        ]
    if problem_list.get('buyer_concern_types'):
        cache_data['buyer_concerns'] = [
            f"{p.get('concern_type', '')}:{p.get('description', '')[:20]}"
            for p in problem_list['buyer_concern_types'][:5]
        ]

    json_str = json.dumps(cache_data, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()


def _extract_problem_keywords(problem_list: Dict) -> List[Dict]:
    """从问题清单提取核心字段"""
    keywords = []

    for p in problem_list.get('user_problem_types', []):
        for kw in p.get('problem_keywords', []):
            keywords.append({
                'keyword': kw.get('keyword', ''),
                'type': kw.get('type', ''),
                'source': f"user_problem:{p.get('problem_type', '')}"
            })

    for p in problem_list.get('buyer_concern_types', []):
        for kw in p.get('problem_keywords', []):
            keywords.append({
                'keyword': kw.get('keyword', ''),
                'type': kw.get('type', ''),
                'source': f"buyer_concern:{p.get('concern_type', '')}"
            })

    return keywords


def _extract_portrait_summary(portraits: List) -> str:
    """从画像提取摘要用于提示词"""
    if not portraits:
        return '（未提供画像）'

    summaries = []
    for i, p in enumerate(portraits[:5], 1):
        name = p.get('name', f'人群{i}')
        summary = p.get('portrait_summary', p.get('description', ''))
        tags = p.get('identity_tags', [])
        tag_str = ','.join(tags[:3]) if tags else ''
        summaries.append(f"- {name}：{summary}{f'（{tag_str}）' if tag_str else ''}")

    return '\n'.join(summaries)


def _extract_scenario_personas(scenario_base_personas: Dict) -> str:
    """从三层人群提取摘要"""
    if not scenario_base_personas:
        return '（未提供三层人群）'

    lines = []
    for layer in ['决策层', '使用层', '对接层']:
        data = scenario_base_personas.get(layer, {})
        if data:
            desc = data.get('description', data.get('summary', ''))
            lines.append(f"- {layer}：{desc}")

    return '\n'.join(lines) if lines else '（未提供三层人群）'


class UnifiedLibraryGenerator:
    """
    统一关键词库 + 选题库生成器

    特点：
    1. 单次 LLM 调用生成双库
    2. C/B 端自动适配分类比例
    3. 严格 100+100 数量控制
    4. 4 档优先级 + industry_tag
    5. MD5 缓存 1 小时
    """

    def __init__(self):
        self.llm = get_llm_service()
        self._cache: Dict[str, tuple] = {}  # {cache_key: (result, expire_at)}

    def _check_cache(self, cache_key: str) -> Optional[Dict]:
        """检查缓存"""
        if cache_key in self._cache:
            result, expire_at = self._cache[cache_key]
            if datetime.now() < expire_at:
                logger.debug("[UnifiedLibraryGenerator] 命中缓存: %s", cache_key)
                return result
            else:
                del self._cache[cache_key]
        return None

    def _save_cache(self, cache_key: str, result: Dict):
        """保存缓存（1小时TTL）"""
        expire_at = datetime.now() + timedelta(hours=1)
        self._cache[cache_key] = (result, expire_at)
        logger.debug("[UnifiedLibraryGenerator] 已缓存: %s", cache_key)

    def _cleanup_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in expired_keys:
            del self._cache[k]

    def generate(
        self,
        params: Dict[str, Any],
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        统一生成关键词库 + 选题库

        Args:
            params: {
                user_id: int,                # 用户ID（必须，用于缓存隔离）
                business_desc: str,        # 核心业务描述
                service_scenario: str,     # 7大标准场景
                business_type: str,        # 经营类型
                problem_list: Dict,        # {user_problem_types, buyer_concern_types}
                portraits: List,           # 5个精准画像
                scenario_base_personas: Dict,  # 三层主干人群
            }
            force_refresh: bool,           # 强制刷新（跳过缓存）

        Returns:
            {
                'success': bool,
                'keyword_library': [...],  # 100个关键词
                'topic_library': [...],     # 100个选题
                'summary': {
                    'is_c端': bool,
                    'keyword_count': int,
                    'topic_count': int,
                    'industry_tags': List[str],
                },
                'cache_hit': bool,
            }
        """
        try:
            # 1. 提取基础信息（含 user_id 用于缓存隔离）
            user_id = params.get('user_id')
            business_desc = params.get('business_desc', '')
            service_scenario = params.get('service_scenario', '')
            business_type = params.get('business_type', 'local_service')
            problem_list = params.get('problem_list', {})
            portraits = params.get('portraits', [])
            scenario_base_personas = params.get('scenario_base_personas', {})

            if not business_desc:
                return {
                    'success': False,
                    'error': 'missing_business_desc',
                    'message': '缺少业务描述',
                }

            # 2. 判断 C/B 端
            is_c端 = _is_c端(business_type)
            end_type = 'C端' if is_c端 else 'B端'

            # 3. 生成缓存键（含 user_id 隔离）
            cache_key = _make_cache_key(params)

            # 4. 检查缓存
            if not force_refresh:
                cached = self._check_cache(cache_key)
                if cached:
                    cached['cache_hit'] = True
                    return cached

            # 5. 提取输入数据摘要
            industry_tags = _get_industry_tags(business_desc, service_scenario)
            problem_keywords = _extract_problem_keywords(problem_list)
            portrait_summary = _extract_portrait_summary(portraits)
            persona_summary = _extract_scenario_personas(scenario_base_personas)

            # 6. 构建分类分布说明
            kw_distribution = _build_category_distribution(is_c端)
            topic_distribution = _build_series_distribution(is_c端)

            kw_dist_text = '\n'.join([
                f"- {name}（{key}）：{count}个"
                for key, count in kw_distribution.items()
            ])
            topic_dist_text = '\n'.join([
                f"- {name}（{key}）：{count}个"
                for key, count in topic_distribution.items()
            ])

            # 7. 构建提示词
            base_map = {
                '刚需痛点': '转化型',
                '前置观望': '种草型',
                '使用配套': '种草型',
            }
            prompt = self._build_prompt(
                business_desc=business_desc,
                service_scenario=service_scenario,
                end_type=end_type,
                problem_list=problem_list,
                problem_keywords=problem_keywords,
                portrait_summary=portrait_summary,
                persona_summary=persona_summary,
                industry_tags=industry_tags,
                kw_distribution=kw_distribution,
                kw_dist_text=kw_dist_text,
                topic_distribution=topic_distribution,
                topic_dist_text=topic_dist_text,
                base_map=base_map,
            )

            # 8. 调用 LLM（重试1次）
            result = None
            for attempt in range(2):
                try:
                    response = self.llm.chat(prompt, temperature=0.2, max_tokens=15000)
                    if response:
                        result = self._parse_response(response)
                        if result and self._validate_result(result):
                            break
                except Exception as e:
                    logger.warning("[UnifiedLibraryGenerator] LLM调用异常(第%d次): %s", attempt + 1, e)

            if not result:
                return {
                    'success': False,
                    'error': 'generation_failed',
                    'message': '生成失败，请重试',
                }

            # 9. 后处理：确保数量达标 + 添加 industry_tag
            result = self._post_process(result, industry_tags, is_c端)

            # 10. 构建返回
            final_result = {
                'success': True,
                'keyword_library': result['keyword_library'],
                'topic_library': result['topic_library'],
                'summary': {
                    'is_c端': is_c端,
                    'keyword_count': len(result['keyword_library']),
                    'topic_count': len(result['topic_library']),
                    'industry_tags': industry_tags,
                },
                'cache_hit': False,
            }

            # 11. 保存缓存
            self._save_cache(cache_key, final_result)
            self._cleanup_cache()

            return final_result

        except Exception as e:
            import traceback
            logger.error("[UnifiedLibraryGenerator] 异常: %s", e)
            logger.debug("[UnifiedLibraryGenerator] 堆栈: %s", traceback.format_exc())
            return {
                'success': False,
                'error': 'exception',
                'message': str(e),
            }

    def _build_prompt(
        self,
        business_desc: str,
        service_scenario: str,
        end_type: str,
        problem_list: Dict,
        problem_keywords: List[Dict],
        portrait_summary: str,
        persona_summary: str,
        industry_tags: List[str],
        kw_distribution: Dict[str, int],
        kw_dist_text: str,
        topic_distribution: Dict[str, int],
        topic_dist_text: str,
        base_map: Dict[str, str] = None,
    ) -> str:
        """构建完整提示词"""
        if base_map is None:
            base_map = {'刚需痛点': '转化型', '前置观望': '种草型', '使用配套': '种草型'}

        # 关键词库示例
        keyword_example = """{
  "keyword_library": [
    {
      "category": "对比型搜索关键词",
      "sub_category": "定制水-选型对比",
      "keyword": "定制水和成品水哪个划算",
      "type": "对比型",
      "search_intent": "对比选择",
      "competition": "低",
      "industry_tag": "饮品行业",
      "priority": "⭐⭐⭐⭐",
      "problem_base": "前置观望"
    }
  ]"""

        # 选题库示例
        topic_example = """{
  "topic_library": [
    {
      "series": "对比选型系列",
      "sub_series": "定制水-选型对比",
      "topic": "定制水和成品水到底差在哪？看完这篇你就懂了",
      "type": "对比分析",
      "related_keyword": "定制水和成品水哪个划算",
      "priority": "⭐⭐⭐⭐",
      "content_direction": "种草型",
      "industry_tag": "饮品行业"
    }
  ]"""

        # 问题清单文本（含三盘信息）
        problems_text = ""
        if problem_list.get('user_problem_types'):
            problems_text += "【使用者问题】\n"
            for p in problem_list['user_problem_types'][:5]:
                base = p.get('problem_base', '（未标注底盘）')
                direction = base_map.get(base, '种草型')
                problems_text += f"- 底盘:{base} 内容方向:{direction} | {p.get('problem_type', '')}：{p.get('description', '')}\n"
                problems_text += f"  场景：{','.join(p.get('scenarios', [])[:2])}\n"
        if problem_list.get('buyer_concern_types'):
            problems_text += "\n【付费者顾虑】\n"
            for p in problem_list['buyer_concern_types'][:5]:
                base = p.get('concern_base', '（未标注底盘）')
                direction = base_map.get(base, '种草型')
                problems_text += f"- 底盘:{base} 内容方向:{direction} | {p.get('concern_type', '')}：{p.get('description', '')}\n"
                if p.get('examples'):
                    problems_text += f"  示例：{','.join(p.get('examples', [])[:2])}\n"

        prompt = f"""你是关键词库+选题库生成专家。严格遵循「三大需求底盘」结构，一次性生成 100个关键词 + 100个选题，全链路执行：前期对比种草→中期安心转化→后期留存种草。

=== 三大需求底盘（固定比例，禁止 AI 自由发挥归类）===
① **前置观望搜前种草盘（50%关键词 + 50%选题）**：对比选型/原因分析/上游供应链原料选材/避坑科普/行情价格，问题导向，专抓前期迷茫、做对比、查原因的潜在客户，选题全部输出种草型
② **刚需痛点盘（30%关键词 + 30%选题）**：直接需求/痛点/决策鼓励/安心保障，临门一脚解决下单犹豫，强化转化，选题全部输出转化型
③ **使用配套搜后种草盘（20%关键词 + 20%选题）**：实操技巧/工具耗材/行业关联，使用后实操留存种草，选题全部输出种草型
**强制规则：所有关键词和选题必须严格从上述分类中提取，禁止临时补充种草内容。对比选型/决策安心/上下游/原料/配料/工具等关键词已固定归入对应底盘，AI 禁止自行新增分类或自由归类**

=== 业务信息 ===
业务描述：{business_desc}
服务场景：{service_scenario}
经营类型：{end_type}（C端=product/personal；B端=local_service/enterprise）

=== 问题清单（含三盘标注，必须严格对应）===
{problems_text}

=== 画像摘要 ===
{portrait_summary}

=== 关键词库数量分布（严格对应三盘，合计100个）===
{kw_dist_text}

=== 选题库数量分布（严格对应三盘，合计100个）===
{topic_dist_text}

=== 关键词库字段规范 ===
- category: 关键词大类（严格按上述分类命名，对应三盘之一）
- sub_category: 业务细分小类（如"酒店餐损控制"）
- keyword: 口语化关键词（问句/短语，长尾优先，如"酒店食材损耗率高怎么办"）
- type: 关键词类型（对比型/问题型/顾虑型/知识型/实操型/工具型/行业型）
- search_intent: 搜索意图（寻求解决方案/了解知识/对比选择/准备决策/使用后需求）
- competition: 竞争度（低/中/高，长尾词=低）
- industry_tag: 行业标签
- priority: 4档优先级（⭐⭐⭐⭐⭐≤20%/⭐⭐⭐⭐≤30%/⭐⭐⭐≤40%/⭐⭐≤10%）
- **problem_base**: 该词对应哪个需求底盘（前置观望/刚需痛点/使用配套）

=== 选题库字段规范 ===
- series: 选题系列（严格按上述分类命名，对应三盘之一）
- sub_series: 业务细分小系列
- topic: 选题标题（含关键词+人群+场景，不抽象）
- type: 选题类型（知识科普/解决方案/对比分析/效果验证/实操技巧/行业关联）
- related_keyword: 关联核心关键词（来自关键词库）
- priority: 4档优先级（分布同上）
- **content_direction**: 内容方向（**必须严格遵循**：前置观望盘=种草型；刚需痛点盘=转化型；使用配套盘=种草型）
- industry_tag: 行业标签

=== 内容方向硬性规则 ===
- 转化型：直面核心痛点/顾虑，提供解决方案，明确关联业务优势（仅限刚需痛点盘）
- 种草型：输出行业知识/对比选型/上游关联/实操技巧，间接引导核心业务，不直接推销（仅限前置观望盘和使用配套盘）

=== 重要约束 ===
1. 关键词禁用红海大词，优先长尾词
2. 选题不抽象、有行动指引，避免空话
3. 关键词和选题的 problem_base/content_direction 必须严格对应三盘比例
4. 选题中转化型占比不超过30%（仅来自刚需痛点盘）
5. ⭐⭐低优先级占比不超过10%

=== 输出格式 ===
直接输出 JSON 字符串，无 Markdown、表格、多余文字
请基于「{business_desc}」生成完整的关键词库和选题库，严格遵循三盘结构（50%/30%/20%）和强制归类规则。
"""

        return prompt

    def _parse_response(self, response: str) -> Optional[Dict]:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            text = response.strip()

            # 尝试找到 JSON 边界
            for start in ['{', '[']:
                idx = text.find(start)
                if idx >= 0:
                    text = text[idx:]
                    break

            # 尝试 JSON 解析
            result = json.loads(text)
            return result

        except json.JSONDecodeError as e:
            logger.debug("[UnifiedLibraryGenerator] JSON解析失败: %s", e)
            # 尝试修复常见问题
            try:
                # 移除 markdown 代码块
                import re
                text = re.sub(r'```json\s*', '', response)
                text = re.sub(r'```\s*', '', text)
                text = text.strip()
                result = json.loads(text)
                return result
            except:
                pass
        except Exception as e:
            logger.debug("[UnifiedLibraryGenerator] 解析异常: %s", e)

        return None

    def _validate_result(self, result: Dict) -> bool:
        """验证结果是否符合要求"""
        # 检查关键词库
        kw_lib = result.get('keyword_library', [])
        if not isinstance(kw_lib, list) or len(kw_lib) < 80:
            logger.debug("[UnifiedLibraryGenerator] 关键词库数量不足: %s", len(kw_lib))
            return False

        # 检查选题库
        topic_lib = result.get('topic_library', [])
        if not isinstance(topic_lib, list) or len(topic_lib) < 80:
            logger.debug("[UnifiedLibraryGenerator] 选题库数量不足: %s", len(topic_lib))
            return False

        # 检查必含字段
        required_kw_fields = {'category', 'keyword', 'type', 'search_intent', 'competition', 'industry_tag', 'priority', 'problem_base'}
        for item in kw_lib[:5]:
            if not required_kw_fields.issubset(set(item.keys())):
                logger.debug("[UnifiedLibraryGenerator] 关键词字段缺失: %s", list(item.keys()))
                return False

        required_topic_fields = {'series', 'topic', 'type', 'related_keyword', 'priority', 'content_direction', 'industry_tag'}
        for item in topic_lib[:5]:
            if not required_topic_fields.issubset(set(item.keys())):
                logger.debug("[UnifiedLibraryGenerator] 选题字段缺失: %s", list(item.keys()))
                return False

        return True

    def _post_process(
        self,
        result: Dict,
        industry_tags: List[str],
        is_c端: bool,
    ) -> Dict:
        """后处理：确保数量达标 + 添加 industry_tag"""

        keyword_lib = result.get('keyword_library', [])
        topic_lib = result.get('topic_library', [])

        # 填充 industry_tag（如果没有）
        default_industry_tag = industry_tags[0] if industry_tags else '通用行业'

        for item in keyword_lib:
            if 'industry_tag' not in item or not item['industry_tag']:
                item['industry_tag'] = default_industry_tag

        # 填充 problem_base（如果没有，默认为种草型）
        valid_bases = ['刚需痛点', '前置观望', '使用配套']
        for item in keyword_lib:
            if 'problem_base' not in item or item['problem_base'] not in valid_bases:
                item['problem_base'] = '种草型'

        for item in topic_lib:
            if 'industry_tag' not in item or not item['industry_tag']:
                item['industry_tag'] = default_industry_tag

        # 确保 priority 合法
        valid_priorities = ['⭐⭐⭐⭐⭐', '⭐⭐⭐⭐', '⭐⭐⭐', '⭐⭐']
        for item in keyword_lib + topic_lib:
            if item.get('priority') not in valid_priorities:
                item['priority'] = '⭐⭐⭐'

        # 确保竞争度合法
        valid_competition = ['低', '中', '高']
        for item in keyword_lib:
            if item.get('competition') not in valid_competition:
                item['competition'] = '中'

        # 确保 content_direction 合法（从 problem_base 推导）
        base_to_direction = {'刚需痛点': '转化型', '前置观望': '种草型', '使用配套': '种草型'}
        valid_directions = ['种草型', '转化型', '种草型+转化型']
        for item in topic_lib:
            direction = item.get('content_direction')
            if direction not in valid_directions:
                base = item.get('problem_base', '')
                item['content_direction'] = base_to_direction.get(base, '种草型')

        # 统计优先级分布
        priority_counts = {'⭐⭐⭐⭐⭐': 0, '⭐⭐⭐⭐': 0, '⭐⭐⭐': 0, '⭐⭐': 0}
        for item in keyword_lib:
            p = item.get('priority', '⭐⭐⭐')
            if p in priority_counts:
                priority_counts[p] += 1

        # ⭐⭐不能超过10%
        max_2star = int(len(keyword_lib) * 0.10) + 1
        if priority_counts['⭐⭐'] > max_2star:
            # 把多余的 ⭐⭐ 降为 ⭐⭐⭐
            excess = priority_counts['⭐⭐'] - max_2star
            count = 0
            for item in keyword_lib:
                if item.get('priority') == '⭐⭐' and count < excess:
                    item['priority'] = '⭐⭐⭐'
                    count += 1

        # 同样处理选题库
        topic_priority_counts = {'⭐⭐⭐⭐⭐': 0, '⭐⭐⭐⭐': 0, '⭐⭐⭐': 0, '⭐⭐': 0}
        for item in topic_lib:
            p = item.get('priority', '⭐⭐⭐')
            if p in topic_priority_counts:
                topic_priority_counts[p] += 1

        max_topic_2star = int(len(topic_lib) * 0.10) + 1
        if topic_priority_counts['⭐⭐'] > max_topic_2star:
            excess = topic_priority_counts['⭐⭐'] - max_topic_2star
            count = 0
            for item in topic_lib:
                if item.get('priority') == '⭐⭐' and count < excess:
                    item['priority'] = '⭐⭐⭐'
                    count += 1

        return {
            'keyword_library': keyword_lib[:100],  # 确保最多100个
            'topic_library': topic_lib[:100],
        }


# 全局单例
unified_library_generator = UnifiedLibraryGenerator()
