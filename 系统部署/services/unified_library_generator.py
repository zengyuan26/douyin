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


# C端经营类型
C端_TYPES = {'product', 'personal'}
# B端经营类型
B端_TYPES = {'local_service', 'enterprise'}

# 关键词库分类配置（按 C/B 端）
KEYWORD_CATEGORIES_C端 = [
    {'name': '使用者问题词', 'key': 'user_problem', 'min': 30,
     'desc': '问题型，用户核心痛点，来自 user_problem_types'},
    {'name': '付费者顾虑词', 'key': 'buyer_concern', 'min': 20,
     'desc': '顾虑型，付费决策担忧，来自 buyer_concern_types'},
    {'name': '产品推荐词', 'key': 'product_recommend', 'min': 15,
     'desc': '对比型/推荐型/阶段型，基于业务+核心问题'},
    {'name': '搜前上游词', 'key': 'pre_search', 'min': 10,
     'desc': '准备型/上游知识型，行业上游+决策前需求'},
    {'name': '搜后周边词', 'key': 'post_search', 'min': 15,
     'desc': '后续型/周边配套型，使用后需求+周边服务'},
    {'name': '行业生态词', 'key': 'industry_eco', 'min': 10,
     'desc': '关联需求型/上下游型，行业生态+关联业务'},
]

KEYWORD_CATEGORIES_B端 = [
    {'name': '使用者问题词', 'key': 'user_problem', 'min': 20,
     'desc': '问题型，用户核心痛点，来自 user_problem_types'},
    {'name': '付费者顾虑词', 'key': 'buyer_concern', 'min': 30,
     'desc': '顾虑型，付费决策担忧，来自 buyer_concern_types'},
    {'name': '产品推荐词', 'key': 'product_recommend', 'min': 15,
     'desc': '对比型/推荐型/阶段型，基于业务+核心问题'},
    {'name': '搜前上游词', 'key': 'pre_search', 'min': 15,
     'desc': '准备型/上游知识型，行业上游+决策前需求'},
    {'name': '搜后周边词', 'key': 'post_search', 'min': 5,
     'desc': '后续型/周边配套型，使用后需求+周边服务'},
    {'name': '行业生态词', 'key': 'industry_eco', 'min': 15,
     'desc': '关联需求型/上下游型，行业生态+关联业务'},
]

# 选题库分类配置（按 C/B 端）
TOPIC_SERIES_C端 = [
    {'name': '使用者问题系列', 'key': 'user_problem_series', 'min': 30,
     'desc': '知识科普/解决方案，种草型+转化型结合'},
    {'name': '付费者决策系列', 'key': 'buyer_decision_series', 'min': 20,
     'desc': '知识科普/渠道推荐/价格分析，转化型'},
    {'name': '产品推荐系列', 'key': 'product_recommend_series', 'min': 15,
     'desc': '产品推荐/对比分析/产品评测，转化型'},
    {'name': '年龄段/场景系列', 'key': 'age_scene_series', 'min': 5,
     'desc': '选购指南/产品推荐，种草型'},
    {'name': '搜前上游系列', 'key': 'pre_search_series', 'min': 10,
     'desc': '知识科普/经验分享，种草型'},
    {'name': '搜后周边系列', 'key': 'post_search_series', 'min': 15,
     'desc': '知识科普/工具推荐，种草型'},
    {'name': '行业生态系列', 'key': 'industry_eco_series', 'min': 5,
     'desc': '知识科普/关联需求分析，种草型'},
]

TOPIC_SERIES_B端 = [
    {'name': '使用者问题系列', 'key': 'user_problem_series', 'min': 20,
     'desc': '知识科普/解决方案，种草型+转化型结合'},
    {'name': '付费者决策系列', 'key': 'buyer_decision_series', 'min': 30,
     'desc': '知识科普/渠道推荐/价格分析，转化型'},
    {'name': '产品推荐系列', 'key': 'product_recommend_series', 'min': 15,
     'desc': '产品推荐/对比分析/产品评测，转化型'},
    {'name': '年龄段/场景系列', 'key': 'age_scene_series', 'min': 5,
     'desc': '选购指南/产品推荐，种草型'},
    {'name': '搜前上游系列', 'key': 'pre_search_series', 'min': 15,
     'desc': '知识科普/经验分享，种草型'},
    {'name': '搜后周边系列', 'key': 'post_search_series', 'min': 5,
     'desc': '知识科普/工具推荐，种草型'},
    {'name': '行业生态系列', 'key': 'industry_eco_series', 'min': 10,
     'desc': '知识科普/关联需求分析，种草型'},
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
    """基于输入数据生成 MD5 缓存键"""
    # 提取关键字段生成摘要
    cache_data = {
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
                print(f"[UnifiedLibraryGenerator] 命中缓存: {cache_key}")
                return result
            else:
                del self._cache[cache_key]
        return None

    def _save_cache(self, cache_key: str, result: Dict):
        """保存缓存（1小时TTL）"""
        expire_at = datetime.now() + timedelta(hours=1)
        self._cache[cache_key] = (result, expire_at)
        print(f"[UnifiedLibraryGenerator] 已缓存: {cache_key}")

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
            # 1. 提取基础信息
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

            # 3. 生成缓存键
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
                    print(f"[UnifiedLibraryGenerator] LLM调用异常(第{attempt+1}次): {e}")

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
            print(f"[UnifiedLibraryGenerator] 异常: {e}")
            print(traceback.format_exc())
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
    ) -> str:
        """构建完整提示词"""

        # 关键词库示例
        keyword_example = """{
  "keyword_library": [
    {
      "category": "使用者问题词",
      "sub_category": "餐具修复-使用痛点",
      "keyword": "餐盘破损用什么胶水粘最牢固",
      "type": "问题型",
      "search_intent": "寻求解决方案",
      "competition": "低",
      "industry_tag": "餐饮行业",
      "priority": "⭐⭐⭐⭐"
    }
  ]"""

        # 选题库示例
        topic_example = """{
  "topic_library": [
    {
      "series": "使用者问题系列",
      "sub_series": "餐盘修复-使用问题",
      "topic": "餐盘频繁破损？3个修复技巧省30%采购成本",
      "type": "解决方案",
      "related_keyword": "餐盘破损用什么胶水粘最牢固",
      "priority": "⭐⭐⭐⭐",
      "content_purpose": "转化型",
      "industry_tag": "餐饮行业"
    }
  ]"""

        # 问题清单文本
        problems_text = ""
        if problem_list.get('user_problem_types'):
            problems_text += "【使用者问题】\n"
            for p in problem_list['user_problem_types'][:5]:
                problems_text += f"- {p.get('problem_type', '')}：{p.get('description', '')}\n"
                problems_text += f"  场景：{','.join(p.get('scenarios', [])[:3])}\n"
        if problem_list.get('buyer_concern_types'):
            problems_text += "\n【付费者顾虑】\n"
            for p in problem_list['buyer_concern_types'][:5]:
                problems_text += f"- {p.get('concern_type', '')}：{p.get('description', '')}\n"
                if p.get('examples'):
                    problems_text += f"  示例：{','.join(p.get('examples', [])[:2])}\n"

        prompt = f"""你是关键词库+选题库生成专家。基于以下业务信息，严格按照数量分布生成 100 个关键词 + 100 个选题。

=== 业务信息 ===
业务描述：{business_desc}
服务场景：{service_scenario}
经营类型：{end_type}（C端=product/personal；B端=local_service/enterprise）

=== 问题清单（核心输入）===
{problems_text}

=== 画像摘要 ===
{portrait_summary}

=== 三层人群摘要 ===
{persona_summary}

=== 行业标签 ===
{', '.join(industry_tags)}

=== 关键词库数量分布（{end_type}，必须严格遵守）===
{kw_dist_text}
总计：100个

=== 选题库数量分布（{end_type}，必须严格遵守）===
{topic_dist_text}
总计：100个

=== 关键词库字段规范 ===
- category: 关键词大类（严格按上述6大类命名）
- sub_category: 业务细分小类（如"酒店餐损控制"）
- keyword: 口语化关键词（问句/短语，长尾优先，如"酒店食材损耗率高怎么办"）
- type: 关键词类型（问题型/顾虑型/推荐型/知识型/后续型/关联型）
- search_intent: 搜索意图（寻求解决方案/了解知识/对比选择/准备决策）
- competition: 竞争度（低/中/高，长尾词=低）
- industry_tag: 行业标签（来自上述行业标签列表）
- priority: 4档优先级（⭐⭐⭐⭐⭐/⭐⭐⭐⭐/⭐⭐⭐/⭐⭐），⭐⭐占比≤10%

=== 选题库字段规范 ===
- series: 选题系列（严格按上述7大系列命名）
- sub_series: 业务细分小系列（如"酒店餐损控制"）
- topic: 选题标题（含关键词+人群+场景，不抽象，如"酒店食材损耗率高？3个库存管理技巧降本"）
- type: 选题类型（知识科普/解决方案/产品推荐/对比分析/经验分享）
- related_keyword: 关联核心关键词（来自关键词库）
- priority: 4档优先级（⭐⭐⭐⭐⭐/⭐⭐⭐⭐/⭐⭐⭐/⭐⭐），⭐⭐占比≤10%
- content_purpose: 内容目的（种草型=间接引导/转化型=直面痛点）
- industry_tag: 行业标签（与关键词库一致）

=== 内容目的定义 ===
- 种草型：输出行业知识、上游/周边/关联需求，间接引导核心业务，不直接推销
- 转化型：直面核心痛点/顾虑，提供解决方案，明确关联业务优势

=== 重要约束 ===
1. 关键词禁用红海大词（如"餐具修复""灌香肠"），优先长尾词
2. 选题不抽象、有行动指引，避免空话
3. C端侧重使用者问题，B端侧重付费者顾虑（按数量分布执行）
4. 确保各分类数量严格达标，总量 100+100
5. ⭐⭐低优先级占比不超过10%

=== 输出格式 ===
直接输出 JSON 字符串，无 Markdown、表格、多余文字：
{keyword_example}
  ],
  "topic_library": [
    {topic_example}
  ]
}}

请基于「{business_desc}」生成完整的关键词库和选题库。
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
            print(f"[UnifiedLibraryGenerator] JSON解析失败: {e}")
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
            print(f"[UnifiedLibraryGenerator] 解析异常: {e}")

        return None

    def _validate_result(self, result: Dict) -> bool:
        """验证结果是否符合要求"""
        # 检查关键词库
        kw_lib = result.get('keyword_library', [])
        if not isinstance(kw_lib, list) or len(kw_lib) < 80:
            print(f"[UnifiedLibraryGenerator] 关键词库数量不足: {len(kw_lib)}")
            return False

        # 检查选题库
        topic_lib = result.get('topic_library', [])
        if not isinstance(topic_lib, list) or len(topic_lib) < 80:
            print(f"[UnifiedLibraryGenerator] 选题库数量不足: {len(topic_lib)}")
            return False

        # 检查必含字段
        required_kw_fields = {'category', 'keyword', 'type', 'search_intent', 'competition', 'industry_tag', 'priority'}
        for item in kw_lib[:5]:
            if not required_kw_fields.issubset(set(item.keys())):
                print(f"[UnifiedLibraryGenerator] 关键词字段缺失: {item.keys()}")
                return False

        required_topic_fields = {'series', 'topic', 'type', 'related_keyword', 'priority', 'content_purpose', 'industry_tag'}
        for item in topic_lib[:5]:
            if not required_topic_fields.issubset(set(item.keys())):
                print(f"[UnifiedLibraryGenerator] 选题字段缺失: {item.keys()}")
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

        # 确保内容目的合法
        valid_purposes = ['种草型', '转化型', '种草型+转化型']
        for item in topic_lib:
            if item.get('content_purpose') not in valid_purposes:
                item['content_purpose'] = '种草型'

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
