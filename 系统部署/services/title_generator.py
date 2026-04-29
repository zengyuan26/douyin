"""
标题生成器 - H-V-F 三段论模型

基于 Hook-Value-Format 三段论生成高点击率标题。

Hook（钩子）：解决"与我有关"
  - identity: 身份标签（新手妈妈、早产儿家长）
  - pain_point: 痛点触发（拉肚子、焦虑）
  - emotion: 情绪共鸣（终于、救命、崩溃）

Value（价值）：解决"看完能得什么"
  - result: 具体结果（长肉了、肠胃变好）
  - backing: 背书力量（卫健委建议、主任医生）

Format（形式）：解决"看起来累不累"
  - quantity: 量化（7张图、5个要点）
  - simple: 简单化（新手必备、抄作业）

使用方式：
    from services.title_generator import TitleGenerator

    gen = TitleGenerator()
    result = gen.generate(
        topic_title="早产儿怎么喂养更健康",
        portrait={"identity": "早产儿家长", "pain_points": ["担心宝宝体重"], ...},
        keywords={"core": ["早产儿"], "long_tail": ["早产儿喂养", "早产儿奶粉"]},
        geo_mode="问题-答案模式",
        industry="育儿",
    )
    for title in result.titles:
        print(title.main_title, title.pattern, title.hvf_score)
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class HVFScore:
    """H-V-F 三段论评分"""
    hook: int = 0          # 0-10
    value: int = 0          # 0-10
    format: int = 0          # 0-10
    total: int = 0          # 0-30

    def __post_init__(self):
        self.total = self.hook + self.value + self.format


@dataclass
class GeneratedTitle:
    """生成的标题"""
    pattern: str                    # 标题模式：A/B/C/D
    main_title: str                 # 主标题（≤15字）
    subtitle: str                   # 副标题（≤15字）
    big_slogan: str                 # 大字金句（≤15字）
    hook_type: str = ""             # hook 类型
    value_type: str = ""            # value 类型
    format_type: str = ""           # format 类型
    hvf_score: HVFScore = field(default_factory=HVFScore)
    hook_coverage: str = ""        # 覆盖的 hook 类型描述
    value_coverage: str = ""       # 覆盖的 value 类型描述
    format_coverage: str = ""      # 覆盖的 format 类型描述


@dataclass
class TitleGeneratorResult:
    """标题生成结果"""
    success: bool = False
    error_message: str = ""
    titles: List[GeneratedTitle] = field(default_factory=list)
    raw_output: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'error_message': self.error_message,
            'titles': [
                {
                    'pattern': t.pattern,
                    'main_title': t.main_title,
                    'subtitle': t.subtitle,
                    'big_slogan': t.big_slogan,
                    'hook_type': t.hook_type,
                    'value_type': t.value_type,
                    'format_type': t.format_type,
                    'hvf_score': {
                        'hook': t.hvf_score.hook,
                        'value': t.hvf_score.value,
                        'format': t.hvf_score.format,
                        'total': t.hvf_score.total,
                    },
                    'hook_coverage': t.hook_coverage,
                    'value_coverage': t.value_coverage,
                    'format_coverage': t.format_coverage,
                }
                for t in self.titles
            ],
        }


# =============================================================================
# 行业 Hook/Value/Format 词库
# =============================================================================

_HOOK_TEMPLATES: Dict[str, List[str]] = {
    "育儿": {
        "identity": [
            "新手妈妈", "早产儿家长", "职场背奶族", "二胎妈妈",
            "高龄产妇", "全职妈妈", "混合喂养妈妈",
        ],
        "pain_point": [
            "宝宝拉肚子", "不长肉", "半夜哭闹", "不喝奶",
            "转奶难", "厌奶期", "体重不达标", "夜醒频繁",
        ],
        "emotion": [
            "终于", "救命", "崩溃", "熬过", "心累",
            "焦虑", "崩溃大哭", "熬出头了",
        ],
    },
    "教育": {
        "identity": [
            "高三家长", "艺考生", "复读生", "县城家长",
            "焦虑妈妈", "陪读家长",
        ],
        "pain_point": [
            "分数不够", "填错志愿", "专业怎么选", "迷茫",
            "浪费分", "滑档", "录取结果",
        ],
        "emotion": [
            "终于等到", "焦虑", "睡不着", "操碎心",
            "不后悔", "熬过来了",
        ],
    },
    "健康": {
        "identity": [
            "亚健康人群", "熬夜党", "久坐上班族", "中老年人",
        ],
        "pain_point": [
            "失眠", "掉头发", "腰酸背痛", "精力不足",
            "体检异常", "慢性疲劳",
        ],
        "emotion": [
            "崩溃", "扛不住", "终于找到", "救命",
            "后悔没早知道",
        ],
    },
    "本地服务": {
        "identity": [
            "本地居民", "新房主", "小店老板", "创业者",
        ],
        "pain_point": [
            "不知道找谁", "怕被坑", "价格不透明",
            "质量不放心", "售后没人管",
        ],
        "emotion": [
            "终于找到", "太不容易", "终于解决",
            "亲测有效", "强烈推荐",
        ],
    },
}

_VALUE_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "育儿": {
        "result": [
            "宝宝长肉了", "肠胃变好了", "终于睡整觉了",
            "不再焦虑了", "顺利转奶了", "追重成功了",
        ],
        "backing": [
            "卫健委建议", "儿科主任建议", "科学喂养",
            "循证医学", "三甲医院推荐",
        ],
    },
    "教育": {
        "result": [
            "被理想大学录取了", "没浪费一分", "顺利入学",
            "避开了坑", "选对了专业", "分数没白考",
        ],
        "backing": [
            "招办老师建议", "过来人经验", "数据验证",
            "历年录取规律", "高校专业解读",
        ],
    },
    "健康": {
        "result": [
            "睡眠质量提升了", "精力充沛了", "头发不掉那么多了",
            "体检正常了", "不再失眠了",
        ],
        "backing": [
            "医生建议", "营养师指导", "临床验证",
            "研究数据支持", "循证方法",
        ],
    },
    "本地服务": {
        "result": [
            "问题解决了", "省了冤枉钱", "少走了弯路",
            "终于找到靠谱的", "体验超预期",
        ],
        "backing": [
            "亲测有效", "朋友推荐", "真实评价",
            "行业内部", "多年经验",
        ],
    },
}

_FORMAT_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "育儿": {
        "quantity": [
            "7张图讲清", "5分钟看完", "3步搞定", "只需3步",
            "一图看懂", "5个要点", "7天见效", "1张图说清楚",
        ],
        "simple": [
            "新手妈妈必看", "照着做就行", "抄作业",
            "一看就会", "新手必备", "有手就会",
            "照着喂就行", "直接抄",
        ],
    },
    "教育": {
        "quantity": [
            "5分钟搞懂", "一张表说清", "3步填完", "1分钟看懂",
            "5个注意事项", "历年数据对比", "3个核心指标",
        ],
        "simple": [
            "照着填就行", "无脑冲", "直接套", "有手就会",
            "新手家长必看", "无脑选", "傻瓜式教程",
        ],
    },
    "健康": {
        "quantity": [
            "7天改善", "3个月见效", "5个动作", "1个方法",
            "每天5分钟", "坚持30天", "5个信号",
        ],
        "simple": [
            "有手就会", "照着做就行", "无需复杂操作",
            "在家就能做", "每天5分钟", "懒人版",
        ],
    },
    "本地服务": {
        "quantity": [
            "3步找到", "1个电话搞定", "3个标准判断",
            "5分钟了解", "对比表",
        ],
        "simple": [
            "照着选", "直接问", "记住这3点",
            "有手就会", "收藏备用", "无坑版本",
        ],
    },
}

# 行业到词库 key 的映射
_INDUSTRY_KEY_MAP: Dict[str, str] = {
    "育儿": "育儿", "母婴": "育儿", "奶粉": "育儿",
    "教育": "教育", "培训": "教育", "高考": "教育", "志愿": "教育",
    "健康": "健康", "医疗": "健康", "养生": "健康",
    "本地服务": "本地服务", "本地": "本地服务", "服务": "本地服务",
}


def _get_industry_key(industry: str) -> str:
    """从行业名映射到词库 key"""
    if not industry:
        return "育儿"  # 默认
    for key, mapped in _INDUSTRY_KEY_MAP.items():
        if key in industry:
            return mapped
    return "育儿"


# =============================================================================
# 标题模式定义
# =============================================================================

_TITLE_PATTERNS = [
    {
        "id": "A",
        "name": "干货攻略型",
        "template": "[痛点] + [Hook量化] + [结果]",
        "example": "早产儿喂养难题？拉肚子怎么办？7张图全讲清了！",
        "description": "用痛点开头 + 量化形式降低门槛，适合知识科普类",
        "best_for": ["知识科普", "选购指南", "避坑指南", "疑问揭秘型"],
        "hvf_combo": "H-pain + F-quantity",
    },
    {
        "id": "B",
        "name": "情绪共鸣型",
        "template": "[身份] + [情绪词] + [转折结果]",
        "example": "新手妈妈必看：从崩溃到轻松，我只用了这一招！",
        "description": "身份锁定 + 情绪共鸣 + 过来人背书，适合经历分享类",
        "best_for": ["经历分享", "经验总结", "用户证言", "场景故事型"],
        "hvf_combo": "H-identity + H-emotion + V-result",
    },
    {
        "id": "C",
        "name": "权威数据型",
        "template": "[权威背书] + [核心痛点] + [承诺]",
        "example": "卫健委建议：早产儿喂养做好这几点，宝宝追赶生长！",
        "description": "权威来源开头 + 承诺结果，适合专业背书类",
        "best_for": ["知识科普", "专家建议", "行业揭秘", "知识科普型"],
        "hvf_combo": "V-backing + H-pain + V-result",
    },
    {
        "id": "D",
        "name": "结果反转型",
        "template": "[惊人结果] + [认知颠覆]",
        "example": "宝宝终于长肉了！原来一直喂错了...",
        "description": "结果先行 + 引发好奇，适合案例分享类",
        "best_for": ["案例分享", "对比冲击", "效果证明", "升级迭代型"],
        "hvf_combo": "H-emotion + H-pain",
    },
]


# =============================================================================
# 核心生成器
# =============================================================================

class TitleGenerator:
    """
    H-V-F 三段论标题生成器

    使用示例：
        gen = TitleGenerator()
        result = gen.generate(
            topic_title="早产儿怎么喂养更健康",
            portrait={"identity": "早产儿家长", "pain_points": ["担心体重", "喂养焦虑"]},
            keywords={"core": ["早产儿"], "long_tail": ["早产儿喂养", "早产儿奶粉", "早产儿注意事项"]},
            geo_mode="问题-答案模式",
            industry="育儿",
        )
    """

    _llm_semaphore: Optional['threading.BoundedSemaphore'] = None

    def __init__(self):
        self.llm = get_llm_service()
        # 全局限流：最多同时运行 3 个 LLM 调用
        import threading
        if TitleGenerator._llm_semaphore is None:
            with threading.Lock():
                if TitleGenerator._llm_semaphore is None:
                    TitleGenerator._llm_semaphore = threading.BoundedSemaphore(3)

    def generate(
        self,
        topic_title: str,
        portrait: Optional[Dict] = None,
        keywords: Optional[Dict] = None,
        geo_mode: str = "",
        industry: str = "",
        num_variants: int = 4,
    ) -> TitleGeneratorResult:
        """
        生成多个标题变体（A/B/C/D 四种模式各一个）

        Args:
            topic_title: 选题标题
            portrait: 用户画像 dict
            keywords: 关键词库 dict（core/long_tail/scene/problem）
            geo_mode: GEO 内容模式
            industry: 行业名
            num_variants: 生成变体数量（默认4）

        Returns:
            TitleGeneratorResult
        """
        import threading

        industry_key = _get_industry_key(industry)

        # 提取画像信息
        identity = self._extract_identity(portrait)
        pain_points = self._extract_pain_points(portrait)
        emotion_words = self._extract_emotion(portrait)

        # 提取关键词
        core_kws = self._flatten_kws(keywords.get('core', []) if keywords else [])
        longtail_kws = self._flatten_kws(keywords.get('long_tail', []) if keywords else [])
        scene_kws = self._flatten_kws(keywords.get('scene', []) if keywords else [])
        problem_kws = self._flatten_kws(keywords.get('problem', []) if keywords else [])

        # 获取词库
        hook_templates = _HOOK_TEMPLATES.get(industry_key, _HOOK_TEMPLATES["育儿"])
        value_templates = _VALUE_TEMPLATES.get(industry_key, _VALUE_TEMPLATES["育儿"])
        format_templates = _FORMAT_TEMPLATES.get(industry_key, _FORMAT_TEMPLATES["育儿"])

        all_hooks = (
            hook_templates.get('identity', []) +
            hook_templates.get('pain_point', []) +
            hook_templates.get('emotion', [])
        )
        all_values = (
            value_templates.get('result', []) +
            value_templates.get('backing', [])
        )
        all_formats = (
            format_templates.get('quantity', []) +
            format_templates.get('simple', [])
        )

        # 构建 prompt
        prompt = self._build_prompt(
            topic_title=topic_title,
            identity=identity,
            pain_points=pain_points,
            emotion_words=emotion_words,
            core_kws=core_kws,
            longtail_kws=longtail_kws,
            scene_kws=scene_kws,
            problem_kws=problem_kws,
            geo_mode=geo_mode,
            industry=industry,
            all_hooks=all_hooks,
            all_values=all_values,
            all_formats=all_formats,
            patterns=_TITLE_PATTERNS,
            num_variants=num_variants,
        )

        try:
            with TitleGenerator._llm_semaphore:
                raw_output = self.llm.chat(prompt)
        except Exception as e:
            logger.error(f"[TitleGenerator] LLM调用失败: {e}")
            return TitleGeneratorResult(
                success=False,
                error_message=f"LLM调用失败: {str(e)}"
            )

        return self._parse_output(raw_output, _TITLE_PATTERNS)

    def generate_single(
        self,
        topic_title: str,
        portrait: Optional[Dict] = None,
        keywords: Optional[Dict] = None,
        pattern: str = "A",
        industry: str = "",
    ) -> TitleGeneratorResult:
        """生成单个指定模式的标题"""
        result = self.generate(
            topic_title=topic_title,
            portrait=portrait,
            keywords=keywords,
            industry=industry,
            num_variants=4,
        )
        # 过滤指定模式
        if result.success:
            result.titles = [t for t in result.titles if t.pattern == pattern]
        return result

    # -------------------------------------------------------------------------
    # Prompt 构建
    # -------------------------------------------------------------------------

    def _build_prompt(
        self,
        topic_title: str,
        identity: str,
        pain_points: str,
        emotion_words: str,
        core_kws: str,
        longtail_kws: str,
        scene_kws: str,
        problem_kws: str,
        geo_mode: str,
        industry: str,
        all_hooks: List[str],
        all_values: List[str],
        all_formats: List[str],
        patterns: List[Dict],
        num_variants: int,
    ) -> str:
        """构建标题生成 Prompt"""

        pattern_list = "\n".join([
            f"**模式{p['id']}-{p['name']}**：{p['template']}\n"
            f"   示例：{p['example']}\n"
            f"   适合：{p['best_for']}\n"
            f"   H-V-F组合：{p['hvf_combo']}"
            for p in patterns
        ])

        hook_identity = "/".join(all_hooks[:6])
        hook_emotion = "/".join(all_hooks[-6:])
        value_result = "/".join(all_values[:6])
        value_backing = "/".join(all_values[-4:])
        format_qty = "/".join(all_formats[:6])
        format_simple = "/".join(all_formats[-4:])

        return f"""你是小红书/抖音爆款标题生成专家。请基于以下信息，严格按H-V-F三段论生成{num_variants}个标题变体。

## 选题信息
标题：{topic_title}
行业：{industry}
GEO模式：{geo_mode}

## 用户画像
身份标签：{identity}
核心痛点：{pain_points}
情绪词：{emotion_words}

## 关键词素材
核心关键词：{core_kws}
长尾关键词：{longtail_kws}
场景关键词：{scene_kws}
问题关键词：{problem_kws}

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## H-V-F 三段论强制规则（缺一扣分）
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### H-Hook（钩子）解决"与我有关"：
- 身份标签（选填）：{hook_identity}
- 痛点触发（必含）：{pain_points}
- 情绪共鸣（选填）：{hook_emotion}

### V-Value（价值）解决"看完能得什么"：
- 具体结果（必含）：{value_result}
- 背书力量（选填）：{value_backing}

### F-Format（形式）解决"看起来累不累"：
- 量化词（选填）：{format_qty}
- 简单化（选填）：{format_simple}

## 四种标题模式

{pattern_list}

## 输出要求

请为每个模式生成1个标题，共{num_variants}个：

```json
{{
  "titles": [
    {{
      "pattern": "A",
      "main_title": "主标题（≤15字，必须戳心）",
      "subtitle": "副标题（≤15字，补充说明）",
      "big_slogan": "大字金句（≤15字，口语化，用于封面字幕）",
      "hook_type": "identity/pain_point/emotion（主Hook类型）",
      "value_type": "result/backing（主Value类型）",
      "format_type": "quantity/simple（Format类型）",
      "hvf_score": {{
        "hook": 0-10,
        "value": 0-10,
        "format": 0-10
      }},
      "hook_coverage": "覆盖了哪些Hook元素（如：痛点+情绪）",
      "value_coverage": "覆盖了哪些Value元素（如：结果+背书）",
      "format_coverage": "覆盖了哪些Format元素（如：量化+简单化）"
    }}
  ]
}}
```

请严格JSON输出，不要包含其他内容。"""

    # -------------------------------------------------------------------------
    # 解析输出
    # -------------------------------------------------------------------------

    def _parse_output(self, raw_output: str, patterns: List[Dict]) -> TitleGeneratorResult:
        """解析 LLM 输出为结构化标题"""
        import json
        import re

        result = TitleGeneratorResult(raw_output={})

        # 尝试从 markdown code block 提取 JSON
        code_blocks = re.findall(r"```(?:json)?\s*(.*?)\s*```", raw_output, re.DOTALL)
        for block in code_blocks:
            block = block.strip()
            try:
                data = json.loads(block)
                result.raw_output = data
                titles_data = data.get('titles', [])
                for t in titles_data:
                    hvf = t.get('hvf_score', {})
                    score = HVFScore(
                        hook=hvf.get('hook', 0),
                        value=hvf.get('value', 0),
                        format=hvf.get('format', 0),
                    )
                    title = GeneratedTitle(
                        pattern=t.get('pattern', ''),
                        main_title=t.get('main_title', ''),
                        subtitle=t.get('subtitle', ''),
                        big_slogan=t.get('big_slogan', ''),
                        hook_type=t.get('hook_type', ''),
                        value_type=t.get('value_type', ''),
                        format_type=t.get('format_type', ''),
                        hvf_score=score,
                        hook_coverage=t.get('hook_coverage', ''),
                        value_coverage=t.get('value_coverage', ''),
                        format_coverage=t.get('format_coverage', ''),
                    )
                    result.titles.append(title)
                result.success = True
                return result
            except json.JSONDecodeError:
                continue

        # 尝试直接解析
        try:
            data = json.loads(raw_output.strip())
            result.raw_output = data
            titles_data = data.get('titles', [])
            for t in titles_data:
                hvf = t.get('hvf_score', {})
                score = HVFScore(
                    hook=hvf.get('hook', 0),
                    value=hvf.get('value', 0),
                    format=hvf.get('format', 0),
                )
                title = GeneratedTitle(
                    pattern=t.get('pattern', ''),
                    main_title=t.get('main_title', ''),
                    subtitle=t.get('subtitle', ''),
                    big_slogan=t.get('big_slogan', ''),
                    hook_type=t.get('hook_type', ''),
                    value_type=t.get('value_type', ''),
                    format_type=t.get('format_type', ''),
                    hvf_score=score,
                )
                result.titles.append(title)
            result.success = True
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"[TitleGenerator] JSON解析失败: {e}，原始输出：{raw_output[:200]}")
            result.error_message = f"JSON解析失败: {str(e)}"
            return result

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------

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

    def _extract_emotion(self, portrait: Optional[Dict]) -> str:
        if not portrait:
            return ""
        if isinstance(portrait, dict):
            psych = portrait.get('psychology', {})
            if isinstance(psych, dict):
                inner = psych.get('inner_voice', '') or psych.get('内心独白', '')
                return str(inner)
        return ""

    def _flatten_kws(self, kw_list: Any) -> str:
        if isinstance(kw_list, list):
            return '、'.join(str(k) for k in kw_list[:10])
        if kw_list:
            return str(kw_list)
        return ""

    def get_best_title(self, result: TitleGeneratorResult, prefer_pattern: str = "A") -> Optional[GeneratedTitle]:
        """
        从生成结果中选择最佳标题

        策略：
        1. 优先指定模式
        2. 其次按 H-V-F 总分排序
        3. 过滤掉分数过低的
        """
        if not result.success or not result.titles:
            return None

        # 优先指定模式
        for t in result.titles:
            if t.pattern == prefer_pattern and t.hvf_score.total >= 15:
                return t

        # 按总分排序
        sorted_titles = sorted(result.titles, key=lambda x: x.hvf_score.total, reverse=True)

        # 取总分最高的
        for t in sorted_titles:
            if t.hvf_score.total >= 12:  # 过滤总分过低的
                return t

        return sorted_titles[0] if sorted_titles else None

    @staticmethod
    def get_pattern_info(pattern_id: str) -> Optional[Dict]:
        """获取指定模式的详细信息"""
        for p in _TITLE_PATTERNS:
            if p['id'] == pattern_id:
                return p
        return None
