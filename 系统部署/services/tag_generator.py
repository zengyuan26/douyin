"""
标签生成器 - 金字塔覆盖法

三层标签结构，精准覆盖"搜索"和"推荐"算法：

第一层（公域流量）：大类目标签，进入大流量池
  - #科学育儿 #育儿干货 #新手妈妈

第二层（垂直细分）：精准需求标签，锁定高转化用户
  - #早产儿喂养 #宝宝肠胃虚弱 #追重攻略

第三层（长尾场景）：搜索入口标签，命中用户真实搜索句
  - #早产儿消化不良怎么办 #新手妈妈避雷


使用方式：
    from services.tag_generator import TagGenerator

    gen = TagGenerator()
    result = gen.generate(
        topic_title="早产儿怎么喂养更健康",
        industry="育儿",
        keywords={"core": ["早产儿"], "long_tail": [...], "scene": [...]},
        portrait={"identity": "早产儿家长", "pain_points": [...]},
    )
    for tag in result.hashtags:
        print(tag)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class TagGeneratorResult:
    """标签生成结果"""
    success: bool = False
    error_message: str = ""

    # 三层标签
    tier1_common: List[str] = field(default_factory=list)    # 公域流量
    tier2_vertical: List[str] = field(default_factory=list)  # 垂直细分
    tier3_longtail: List[str] = field(default_factory=list)  # 长尾场景

    # 合并后的 hashtag 列表
    hashtags: List[str] = field(default_factory=list)

    # 搜索命中关键词
    search_keywords: List[str] = field(default_factory=list)

    # 原始 LLM 输出
    raw_output: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'error_message': self.error_message,
            'tier1_common': self.tier1_common,
            'tier2_vertical': self.tier2_vertical,
            'tier3_longtail': self.tier3_longtail,
            'hashtags': self.hashtags,
            'search_keywords': self.search_keywords,
        }


# =============================================================================
# 行业固定标签库（第一层）
# =============================================================================

_TIER1_TEMPLATES: Dict[str, List[str]] = {
    "育儿": [
        "#科学育儿", "#育儿干货", "#育儿知识", "#育儿经验",
        "#母婴好物", "#宝宝辅食", "#育儿日常",
    ],
    "母婴": [
        "#科学育儿", "#育儿干货", "#新手妈妈", "#宝妈分享",
        "#宝宝日常", "#母婴健康", "#育儿经验",
    ],
    "教育": [
        "#学习方法", "#教育心得", "#知识分享", "#高考志愿",
        "#家长必读", "#教育经验", "#学业规划",
    ],
    "培训": [
        "#技能培训", "#职业教育", "#学习干货", "#考证攻略",
        "#培训心得", "#技能提升",
    ],
    "高考": [
        "#高考志愿", "#学习方法", "#学业规划", "#高考加油",
        "#志愿填报", "#教育经验",
    ],
    "健康": [
        "#健康生活", "#养生知识", "#健康科普", "#健康养生",
        "#健康饮食", "#生活习惯", "#医学科普",
    ],
    "医疗": [
        "#健康科普", "#医学知识", "#健康养生", "#就医指南",
        "#健康知识", "#医疗科普",
    ],
    "美食": [
        "#美食分享", "#家常菜谱", "#简单食谱", "#吃货日常",
        "#美食教程", "#下饭菜", "#厨房小白",
    ],
    "本地服务": [
        "#同城推荐", "#本地生活", "#生活技巧", "#本地攻略",
        "#城市生活", "#便民服务",
    ],
    "default": [
        "#干货分享", "#经验分享", "#实用技巧", "#生活小妙招",
        "#收藏备用", "#必看推荐",
    ],
}


def _get_tier1_tags(industry: str) -> List[str]:
    """获取第一层公域标签"""
    if not industry:
        return _TIER1_TEMPLATES["default"]
    industry_lower = industry.lower()
    for key, tags in _TIER1_TEMPLATES.items():
        if key.lower() in industry_lower:
            return tags
    return _TIER1_TEMPLATES["default"]


# =============================================================================
# 长尾标签生成规则（第三层）
# =============================================================================

_LONGTAIL_TEMPLATES: List[str] = [
    "{core}{action}{what}",
    "{core}{pain}{怎么办}",
    "{persona}{action}{status}",
    "{core}{compare}{哪个好}",
    "{core}{pain}{指南}",
    "{core}{howto}",
    "{persona}{pain}{怎么办}",
]


# =============================================================================
# 标签清洗规则
# =============================================================================

def _clean_tag(tag: str) -> str:
    """清洗标签：去掉空格、确保以#开头、去掉过长部分"""
    tag = tag.strip()
    if not tag:
        return ""

    # 去掉末尾的标点
    tag = re.sub(r'[，。！？、；：]$', '', tag)

    # 去掉开头可能的空格或#
    tag = tag.lstrip('#').lstrip()

    # 长度限制
    if len(tag) > 20:
        tag = tag[:20]

    if not tag:
        return ""

    return f"#{tag}"


def _extract_keywords_from_tag(tag: str) -> str:
    """从标签提取关键词（去掉#和多余字）"""
    tag = tag.lstrip('#').strip()
    # 去掉常见后缀
    tag = re.sub(r'(怎么办|怎么|指南|攻略|技巧|方法|干货|分享)$', '', tag)
    return tag


# =============================================================================
# 核心生成器
# =============================================================================

class TagGenerator:
    """
    金字塔三层标签生成器

    使用示例：
        gen = TagGenerator()
        result = gen.generate(
            topic_title="早产儿怎么喂养更健康",
            industry="育儿",
            keywords={
                "core": ["早产儿"],
                "long_tail": ["早产儿喂养", "早产儿奶粉", "早产儿注意事项"],
                "scene": ["医院建议", "追重方法"],
                "problem": ["拉肚子", "不长肉"],
            },
            portrait={"identity": "早产儿家长", "pain_points": ["担心体重", "喂养焦虑"]},
        )
    """

    _llm_semaphore: Optional['threading.BoundedSemaphore'] = None

    def __init__(self):
        self.llm = get_llm_service()
        import threading
        if TagGenerator._llm_semaphore is None:
            with threading.Lock():
                if TagGenerator._llm_semaphore is None:
                    TagGenerator._llm_semaphore = threading.BoundedSemaphore(3)

    def generate(
        self,
        topic_title: str,
        industry: str = "",
        keywords: Optional[Dict] = None,
        portrait: Optional[Dict] = None,
        geo_mode: str = "",
        max_tags: int = 8,
    ) -> TagGeneratorResult:
        """
        生成三层金字塔标签

        Args:
            topic_title: 选题标题
            industry: 行业
            keywords: 关键词库
            portrait: 用户画像
            geo_mode: GEO 模式
            max_tags: 最终 hashtags 列表最大数量

        Returns:
            TagGeneratorResult
        """
        import threading

        core_kws = self._flatten(keywords.get('core', []) if keywords else [])
        longtail_kws = self._flatten(keywords.get('long_tail', []) if keywords else [])
        scene_kws = self._flatten(keywords.get('scene', []) if keywords else [])
        problem_kws = self._flatten(keywords.get('problem', []) if keywords else [])

        identity = self._extract_identity(portrait)
        pain_points = self._extract_pain_points(portrait)

        # 第一层：固定公域标签（直接取）
        tier1 = _get_tier1_tags(industry)[:2]

        prompt = self._build_prompt(
            topic_title=topic_title,
            industry=industry,
            core_kws=core_kws,
            longtail_kws=longtail_kws,
            scene_kws=scene_kws,
            problem_kws=problem_kws,
            identity=identity,
            pain_points=pain_points,
            geo_mode=geo_mode,
            tier1_common=tier1,
            max_tags=max_tags,
        )

        try:
            with TagGenerator._llm_semaphore:
                raw_output = self.llm.chat(prompt)
        except Exception as e:
            logger.error(f"[TagGenerator] LLM调用失败: {e}")
            return TagGeneratorResult(
                success=False,
                error_message=f"LLM调用失败: {str(e)}"
            )

        result = self._parse_output(raw_output, tier1, max_tags)
        return result

    def generate_tier2_only(
        self,
        topic_title: str,
        keywords: Optional[Dict] = None,
        max_tags: int = 3,
    ) -> List[str]:
        """仅生成第二层（垂直细分）标签，用于快速补充"""
        result = self.generate(
            topic_title=topic_title,
            keywords=keywords,
            max_tags=max_tags,
        )
        return result.tier2_vertical[:max_tags]

    def generate_tier3_only(
        self,
        topic_title: str,
        keywords: Optional[Dict] = None,
        max_tags: int = 3,
    ) -> List[str]:
        """仅生成第三层（长尾场景）标签，用于快速补充"""
        result = self.generate(
            topic_title=topic_title,
            keywords=keywords,
            max_tags=max_tags,
        )
        return result.tier3_longtail[:max_tags]

    # -------------------------------------------------------------------------
    # Prompt 构建
    # -------------------------------------------------------------------------

    def _build_prompt(
        self,
        topic_title: str,
        industry: str,
        core_kws: str,
        longtail_kws: str,
        scene_kws: str,
        problem_kws: str,
        identity: str,
        pain_points: str,
        geo_mode: str,
        tier1_common: List[str],
        max_tags: int,
    ) -> str:
        return f"""你是小红书/抖音标签生成专家（金字塔三层覆盖法）。请为以下选题生成精准标签。

## 选题信息
标题：{topic_title}
行业：{industry}
GEO模式：{geo_mode}

## 关键词素材
核心关键词：{core_kws}
长尾关键词：{longtail_kws}
场景关键词：{scene_kws}
问题关键词：{problem_kws}

## 用户画像
身份标签：{identity}
核心痛点：{pain_points}

## 第一层标签（已选定）
{tier1_common}

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 金字塔三层标签生成规则
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### 第一层：公域流量标签（已选定，无需生成）
目的：进入大流量池
示例：#科学育儿 #育儿干货
规则：直接使用传入的标签

### 第二层：垂直细分标签（需生成2-3个）
目的：锁定有特定需求的高转化用户
来源：从 core_kws 和 longtail_kws 中提取
规则：
1. 使用核心业务词 + 痛点词组合
2. 格式：#[核心词][痛点/动作]
示例：
- 核心=早产儿 + 痛点=喂养 → #早产儿喂养
- 核心=早产儿 + 痛点=不长肉 → #早产儿不长肉
- 核心=早产儿 + 动作=追重 → #早产儿追重攻略
禁止：纯大类目词（如#育儿 #母婴）

### 第三层：长尾场景标签（需生成2-3个）
目的：命中用户在搜索框输入的具体问题
来源：从 scene_kws 和 problem_kws 中提取
规则：
1. 模板组合或直接提取搜索句
2. 格式：#[核心词][场景/问题词][怎么办/指南/攻略]
示例：
- 早产儿+消化不良+怎么办 → #早产儿消化不良怎么办
- 新手妈妈+焦虑+避雷 → #新手妈妈避雷
- 早产儿+转奶+攻略 → #早产儿转奶攻略
禁止：太泛（如#怎么办）、太长（超过15字）

### 标签组合规则
最终 {max_tags} 个标签的配比：
- 第1层（公域）：1-2个（已选定）
- 第2层（垂直）：2-3个
- 第3层（长尾）：2-3个
总标签数 ≤ {max_tags}

## 输出格式

```json
{{
  "tier1_common": ["#公域标签1", "#公域标签2"],
  "tier2_vertical": ["#垂直标签1", "#垂直标签2", "#垂直标签3"],
  "tier3_longtail": ["#长尾标签1", "#长尾标签2", "#长尾标签3"],
  "hashtags": ["最终标签列表（按优先级排序，最多{max_tags}个）"],
  "search_keywords": ["能命中搜索的关键词（3-5个）"]
}}
```

请严格JSON输出，不要包含其他内容。"""

    # -------------------------------------------------------------------------
    # 解析输出
    # -------------------------------------------------------------------------

    def _parse_output(
        self,
        raw_output: str,
        tier1_common: List[str],
        max_tags: int,
    ) -> TagGeneratorResult:
        """解析 LLM 输出"""
        import json
        import re

        result = TagGeneratorResult()

        # 提取 JSON
        code_blocks = re.findall(r"```(?:json)?\s*(.*?)\s*```", raw_output, re.DOTALL)
        for block in code_blocks:
            block = block.strip()
            try:
                data = json.loads(block)
                return self._build_result(data, tier1_common, max_tags)
            except json.JSONDecodeError:
                continue

        try:
            data = json.loads(raw_output.strip())
            return self._build_result(data, tier1_common, max_tags)
        except json.JSONDecodeError as e:
            logger.warning(f"[TagGenerator] JSON解析失败: {e}")
            result.error_message = f"JSON解析失败: {str(e)}"
            return result

    def _build_result(
        self,
        data: Dict,
        tier1_common: List[str],
        max_tags: int,
    ) -> TagGeneratorResult:
        result = TagGeneratorResult(raw_output=data)

        # 清洗各层标签
        result.tier1_common = self._clean_tags(data.get('tier1_common', tier1_common))
        result.tier2_vertical = self._clean_tags(data.get('tier2_vertical', []))
        result.tier3_longtail = self._clean_tags(data.get('tier3_longtail', []))

        # 合并为最终 hashtags
        raw_hashtags = data.get('hashtags', [])
        if not raw_hashtags:
            # 如果 LLM 没有返回，直接拼接
            combined = result.tier1_common[:2] + result.tier2_vertical[:3] + result.tier3_longtail[:3]
            raw_hashtags = combined

        result.hashtags = self._dedup_and_limit(
            self._clean_tags(raw_hashtags), max_tags
        )

        # 去重逻辑：第二层+第三层中如果有重复第一层的，去掉
        tier1_cores = {_extract_keywords_from_tag(t) for t in result.tier1_common}
        final = []
        for tag in result.hashtags:
            core = _extract_keywords_from_tag(tag)
            # 避免完全重复
            if tag not in final and core not in [t.lstrip('#') for t in final]:
                final.append(tag)
        result.hashtags = final[:max_tags]

        result.search_keywords = data.get('search_keywords', [])
        if isinstance(result.search_keywords, list):
            result.search_keywords = [str(k) for k in result.search_keywords[:5]]

        result.success = True
        return result

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

    def _clean_tags(self, tags: Any) -> List[str]:
        """清洗标签列表"""
        if not tags:
            return []
        if isinstance(tags, str):
            # 逗号分隔的字符串
            tags = [t.strip() for t in tags.split(',')]
        if not isinstance(tags, list):
            return []
        cleaned = [_clean_tag(str(t)) for t in tags]
        return [t for t in cleaned if t]

    def _dedup_and_limit(self, tags: List[str], max_tags: int) -> List[str]:
        """去重 + 限制数量"""
        seen = set()
        result = []
        for tag in tags:
            normalized = tag.lstrip('#')
            if normalized not in seen and len(tag) > 1:
                seen.add(normalized)
                result.append(tag)
                if len(result) >= max_tags:
                    break
        return result

    def _flatten(self, items: Any) -> str:
        if isinstance(items, list):
            return '、'.join(str(x) for x in items[:10])
        if items:
            return str(items)
        return ""

    def _extract_identity(self, portrait: Optional[Dict]) -> str:
        if not portrait:
            return ""
        if isinstance(portrait, dict):
            return portrait.get('identity', '') or portrait.get('identity_description', '')
        return str(portrait)

    def _extract_pain_points(self, portrait: Optional[Dict]) -> str:
        if not portrait:
            return ""
        if isinstance(portrait, dict):
            pps = portrait.get('pain_points', [])
            if isinstance(pps, list):
                return '、'.join(str(p) for p in pps[:5])
            return str(pps)
        return str(portrait)

    def merge_with_existing(
        self,
        existing_tags: List[str],
        new_result: TagGeneratorResult,
        max_total: int = 12,
    ) -> List[str]:
        """
        合并已有标签和新生成的标签

        策略：
        1. 优先保留已有标签（用户已选）
        2. 补充新生成的标签（系统推荐）
        3. 总数不超过 max_total
        """
        existing = self._clean_tags(existing_tags)
        new_tags = new_result.hashtags

        merged = list(existing)
        seen = {t.lstrip('#') for t in merged}

        for tag in new_tags:
            core = tag.lstrip('#')
            if core not in seen and len(merged) < max_total:
                merged.append(tag)
                seen.add(core)

        return merged
