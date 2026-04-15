"""
市场蓝海分析服务

功能：
1. 基于业务描述分析市场机会
2. 识别细分人群和长尾市场
3. 挖掘蓝海关键词和差异化方向
4. 生成问题类型标签（用于画像分类）
5. 整合关键词库生成（蓝海/红海区分）

使用方式：
from services.market_analyzer import MarketAnalyzer, MarketAnalysisResult

analyzer = MarketAnalyzer()
result = analyzer.analyze({
    'business_description': '卖奶粉',
    'industry': '奶粉',
    'business_type': 'product'
})

# 获取分析结果
result.market_opportunities  # 蓝海市场机会
result.keyword_library       # 关键词库（区分蓝海/红海）
result.problem_types         # 问题类型标签
result.subdivision_insights  # 细分赛道洞察
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """市场类型枚举"""
    BLUE_OCEAN = "blue_ocean"  # 蓝海：细分人群/长尾需求
    RED_OCEAN = "red_ocean"    # 红海：大众竞争市场


@dataclass
class MarketOpportunity:
    """市场机会"""
    opportunity_name: str           # 机会名称
    target_audience: str            # 目标人群描述
    pain_points: List[str]           # 痛点列表
    keywords: List[str]             # 关键词
    content_direction: str           # 内容方向
    market_type: str                # blue_ocean / red_ocean
    confidence: float = 0.8         # 置信度


@dataclass
class ProblemType:
    """问题类型（画像分类标签）"""
    type_name: str                   # 类型名称，如"肠道问题"
    description: str                 # 描述
    target_audience: str            # 目标人群
    keywords: List[str]              # 关联关键词
    opportunity_count: int = 1       # 对应机会数量（一个类型可对应多个画像）


@dataclass
class KeywordCategory:
    """关键词分类"""
    category_name: str              # 分类名称
    keywords: List[str]             # 关键词列表
    market_type: str                # blue_ocean / red_ocean
    proportion: float = 0.0         # 占比


@dataclass
class MarketAnalysisResult:
    """市场分析结果"""
    success: bool = False
    error_message: str = ""

    # 核心产出
    market_opportunities: List[MarketOpportunity] = field(default_factory=list)
    problem_types: List[ProblemType] = field(default_factory=list)
    keyword_library: Dict[str, Any] = field(default_factory=dict)

    # 细分洞察
    subdivision_insights: Dict[str, Any] = field(default_factory=dict)

    # 原始LLM输出（用于调试）
    raw_output: Dict[str, Any] = field(default_factory=dict)

    # 统计信息
    total_keywords: int = 0
    blue_ocean_keywords: int = 0
    red_ocean_keywords: int = 0


class MarketAnalyzer:
    """
    市场蓝海分析器

    核心能力：
    1. 挖掘细分人群和长尾市场
    2. 区分蓝海/红海关键词
    3. 生成问题类型标签
    4. 整合关键词库
    """

    def __init__(self):
        self.llm = get_llm_service()

    def analyze(
        self,
        business_info: Dict[str, Any],
        max_opportunities: int = 5,
        max_keywords: int = 200,
    ) -> MarketAnalysisResult:
        """
        执行市场分析

        Args:
            business_info: 业务信息
                - business_description: 业务描述
                - industry: 行业
                - business_type: 业务类型 (product/service)
                - keywords: 已有关键词（可选）
            max_opportunities: 最大市场机会数量
            max_keywords: 最大关键词数量

        Returns:
            MarketAnalysisResult: 分析结果
        """
        result = MarketAnalysisResult()

        try:
            # 参数提取
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')

            if not business_desc:
                result.error_message = "业务描述不能为空"
                return result

            # 生成分析Prompt
            prompt = self._build_analysis_prompt(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                max_opportunities=max_opportunities,
                max_keywords=max_keywords,
            )

            # 调用LLM
            logger.info("[MarketAnalyzer] 开始调用LLM...")

            # 构建消息格式
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=4000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            # 解析结果
            result = self._parse_analysis_result(response, result)

            # 统计关键词
            if result.keyword_library:
                all_kw = []
                for cat in result.keyword_library.get('categories', []):
                    all_kw.extend(cat.get('keywords', []))
                result.total_keywords = len(all_kw)
                result.blue_ocean_keywords = sum(
                    1 for cat in result.keyword_library.get('categories', [])
                    if cat.get('market_type') == 'blue_ocean'
                    for kw in cat.get('keywords', [])
                )
                result.red_ocean_keywords = result.total_keywords - result.blue_ocean_keywords

            result.success = True
            logger.info(
                "[MarketAnalyzer] 分析完成: 机会=%d, 问题类型=%d, 关键词=%d (蓝海=%d, 红海=%d)",
                len(result.market_opportunities),
                len(result.problem_types),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
            )

        except Exception as e:
            logger.error("[MarketAnalyzer] 分析异常: %s", str(e))
            result.error_message = f"分析异常: {str(e)}"

        return result

    def _build_analysis_prompt(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        max_opportunities: int,
        max_keywords: int,
    ) -> str:
        """构建分析Prompt"""

        # 问题类型分类指引
        problem_type_guide = """
【问题类型分类指引】（仅作为画像分类标签，一个类型可对应多个画像场景）
问题类型应该：
- 简短明确：2-4个字，如"肠道问题"、"效果存疑"
- 代表一类痛点或需求：不要过于具体，也不要过于抽象
- 有区分度：不同类型之间有明显差异

示例（奶粉行业）：
- "肠道问题" → 宝宝拉肚子、便秘、绿便等
- "发育焦虑" → 不长肉、不长高、发育迟缓
- "选品困惑" → 选哪个牌子、国产还是进口
- "购买顾虑" → 怕买到假货、价格贵不贵
- "喂养技巧" → 怎么冲泡、怎么转奶

示例（桶装水行业）：
- "送水等待" → 等水等到嗓子冒烟、楼层高搬水费劲
- "水质担忧" → 担心水源、担心二次污染
- "机器维护" → 饮水机清洗、滤芯更换
- "订购套路" → 第一次订被坑、续费涨价

示例（法律服务）：
- "纠纷困惑" → 不知道怎么处理、要不要请律师
- "费用顾虑" → 律师费多少、能不能风险代理
- "机构选择" → 怎么选靠谱律师、胜诉率多少
"""

        # 关键词库分类
        keyword_guide = """
【关键词库生成要求】
按以下分类生成{max_keywords}个关键词，严格区分蓝海/红海：

1. 蓝海关键词（细分人群/长尾需求）：
   - 细分人群词：如"早产儿奶粉"、"乳糖不耐受宝宝"
   - 细分场景词：如"宝宝拉肚子时"、"转奶期间"
   - 细分痛点词：如"担心激素残留"、"怕买贵了"
   - 长尾问题词：如"三个月宝宝便秘怎么办"

2. 红海关键词（大众竞争词）：
   - 品类大词：如"奶粉"、"奶粉推荐"
   - 品牌词：如"爱他美"、"美赞臣"
   - 通用需求词：如"婴儿奶粉哪种好"

蓝海关键词占比建议：60%以上

每个分类关键词数量要求：
- 蓝海关键词：至少{min_blue}个
- 红海关键词：最多{max_red}个
""".format(
            max_keywords=max_keywords,
            min_blue=int(max_keywords * 0.6),
            max_red=int(max_keywords * 0.4),
        )

        # 业务类型适配
        business_type_hint = ""
        if business_type == 'product':
            business_type_hint = "业务为消费品，重点关注：使用者症状、购买者顾虑、选择对比"
        elif business_type == 'local_service':
            business_type_hint = "业务为本地服务，重点关注：服务场景、时效顾虑、信任问题"
        elif business_type == 'enterprise':
            business_type_hint = "业务为企业服务，重点关注：决策流程、ROI顾虑、供应商选择"

        prompt = f"""你是市场蓝海机会分析专家。请分析以下业务的市场机会。

=== 业务信息 ===
业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
业务类型：{business_type_hint}

=== 分析任务 ===
请完成以下分析并输出JSON格式结果：

1. **市场机会挖掘**：识别{max_opportunities}个蓝海市场机会
   - 每个机会要明确：目标人群、核心痛点、差异化方向
   - 人群要细分：如"家有0-6个月奶粉喂养宝宝的新手妈妈"、"高层住宅无电梯家庭"

2. **问题类型生成**：生成3-6个问题类型（仅作为画像分类标签）
   - 一个类型对应一类痛点，可生成多个画像
   - 如"肠道问题"类型下，可生成：拉肚子场景、便秘场景、绿便场景等不同画像
{problem_type_guide}

3. **关键词库生成**（区分蓝海/红海）：
{keyword_guide}

=== 输出格式 ===
请严格按以下JSON格式输出，不要输出任何其他内容：

{{
    "market_opportunities": [
        {{
            "opportunity_name": "机会名称",
            "target_audience": "目标人群描述",
            "pain_points": ["痛点1", "痛点2"],
            "keywords": ["关键词1", "关键词2"],
            "content_direction": "内容方向",
            "market_type": "blue_ocean",
            "confidence": 0.85
        }}
    ],
    "problem_types": [
        {{
            "type_name": "肠道问题",
            "description": "宝宝肠道相关问题",
            "target_audience": "奶粉喂养宝宝家庭",
            "keywords": ["拉肚子", "便秘", "绿便"]
        }}
    ],
    "keyword_library": {{
        "total_count": {max_keywords},
        "categories": [
            {{
                "category_name": "细分人群词",
                "keywords": ["早产儿奶粉", "乳糖不耐受宝宝"],
                "market_type": "blue_ocean",
                "proportion": 0.2
            }},
            {{
                "category_name": "品类大词",
                "keywords": ["奶粉", "婴儿奶粉"],
                "market_type": "red_ocean",
                "proportion": 0.15
            }}
        ]
    }},
    "subdivision_insights": {{
        "main_subdivision": "主流细分方向",
        "blue_ocean_direction": "蓝海差异化方向",
        "differentiation_points": ["差异化点1", "差异化点2"]
    }}
}}

请开始分析："""

        return prompt

    def _parse_analysis_result(
        self,
        response: str,
        result: MarketAnalysisResult
    ) -> MarketAnalysisResult:
        """解析LLM返回结果"""

        # 尝试JSON解析
        try:
            # 清理响应文本
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            result.raw_output = data

        except json.JSONDecodeError as e:
            logger.warning("[MarketAnalyzer] JSON解析失败，尝试修复: %s", e)
            # 尝试修复JSON
            data = self._try_fix_json(response)
            if not data:
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

        # 解析市场机会
        opportunities = data.get('market_opportunities', [])
        for opp in opportunities:
            result.market_opportunities.append(MarketOpportunity(
                opportunity_name=opp.get('opportunity_name', ''),
                target_audience=opp.get('target_audience', ''),
                pain_points=opp.get('pain_points', []),
                keywords=opp.get('keywords', []),
                content_direction=opp.get('content_direction', ''),
                market_type=opp.get('market_type', 'blue_ocean'),
                confidence=opp.get('confidence', 0.8),
            ))

        # 解析问题类型
        problem_types = data.get('problem_types', [])
        for pt in problem_types:
            result.problem_types.append(ProblemType(
                type_name=pt.get('type_name', ''),
                description=pt.get('description', ''),
                target_audience=pt.get('target_audience', ''),
                keywords=pt.get('keywords', []),
            ))

        # 解析关键词库
        result.keyword_library = data.get('keyword_library', {})

        # 解析细分洞察
        result.subdivision_insights = data.get('subdivision_insights', {})

        return result

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的JSON"""

        # 策略1：提取JSON块
        import re

        # 尝试找到JSON开始和结束
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]

            # 尝试解析
            try:
                return json.loads(json_str)
            except:
                pass

            # 策略2：修复常见问题
            # 移除trailing comma
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                return json.loads(json_str)
            except:
                pass

        return None

    def get_problem_type_for_portrait(
        self,
        portrait_context: Dict[str, Any],
        problem_types: List[ProblemType]
    ) -> Optional[ProblemType]:
        """
        根据画像上下文匹配合适的问题类型

        Args:
            portrait_context: 画像上下文（痛点、场景等）
            problem_types: 可用的问题类型列表

        Returns:
            匹配的问题类型或None
        """
        if not problem_types:
            return None

        portrait_keywords = set()
        for v in portrait_context.values():
            if isinstance(v, str):
                portrait_keywords.update(v.split())

        # 简单匹配：找关键词重叠最多的
        best_match = None
        best_score = 0

        for pt in problem_types:
            pt_keywords = set(pt.keywords)
            overlap = len(portrait_keywords & pt_keywords)
            if overlap > best_score:
                best_score = overlap
                best_match = pt

        return best_match


# ============================================================
# 便捷函数
# ============================================================

def analyze_market(business_info: Dict[str, Any]) -> MarketAnalysisResult:
    """
    便捷函数：执行市场分析

    使用方式：
        from services.market_analyzer import analyze_market

        result = analyze_market({
            'business_description': '卖奶粉',
            'industry': '奶粉',
            'business_type': 'product'
        })

        if result.success:
            print(f"发现 {len(result.market_opportunities)} 个蓝海机会")
            print(f"关键词库: {result.keyword_library}")
    """
    analyzer = MarketAnalyzer()
    return analyzer.analyze(business_info)


def get_blue_ocean_keywords(keyword_library: Dict[str, Any]) -> List[str]:
    """
    从关键词库中提取蓝海关键词

    Args:
        keyword_library: 关键词库数据

    Returns:
        蓝海关键词列表
    """
    blue_ocean_kw = []
    for cat in keyword_library.get('categories', []):
        if cat.get('market_type') == 'blue_ocean':
            blue_ocean_kw.extend(cat.get('keywords', []))
    return blue_ocean_kw


def get_red_ocean_keywords(keyword_library: Dict[str, Any]) -> List[str]:
    """
    从关键词库中提取红海关键词

    Args:
        keyword_library: 关键词库数据

    Returns:
        红海关键词列表
    """
    red_ocean_kw = []
    for cat in keyword_library.get('categories', []):
        if cat.get('market_type') == 'red_ocean':
            red_ocean_kw.extend(cat.get('keywords', []))
    return red_ocean_kw
