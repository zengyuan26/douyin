"""
关键词库生成服务

功能：
1. 基于业务描述和选定的业务方向，生成精准的关键词库
2. 生成问题类型标签
3. 区分蓝海/红海关键词

使用方式：
from services.keyword_library_generator import KeywordLibraryGenerator, KeywordLibraryResult

generator = KeywordLibraryGenerator()
result = generator.generate(
    business_info={'business_description': '卖奶粉', 'industry': '奶粉'},
    business_direction='进口有机羊奶粉',  # 用户选择的蓝海方向
    max_keywords=200
)

result.keyword_library  # 关键词库
result.problem_types    # 问题类型
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class ProblemType:
    """问题类型（画像分类标签）"""
    type_name: str                   # 类型名称，如"肠道问题"
    description: str                 # 描述
    target_audience: str             # 目标人群
    keywords: List[str]              # 关联关键词


@dataclass
class KeywordLibraryResult:
    """关键词库生成结果"""
    success: bool = False
    error_message: str = ""

    # 核心产出
    keyword_library: Dict[str, Any] = field(default_factory=dict)
    problem_types: List[ProblemType] = field(default_factory=list)

    # 原始LLM输出（用于调试）
    raw_output: Dict[str, Any] = field(default_factory=dict)

    # 统计信息
    total_keywords: int = 0
    blue_ocean_keywords: int = 0
    red_ocean_keywords: int = 0


class KeywordLibraryGenerator:
    """
    关键词库生成器

    核心能力：
    1. 基于选定的业务方向，生成精准的关键词库
    2. 生成问题类型标签
    3. 区分蓝海/红海关键词

    与 MarketAnalyzer 的区别：
    - MarketAnalyzer：一次性生成蓝海机会 + 关键词库（快速但不精准）
    - KeywordLibraryGenerator：基于已选定的业务方向，精准生成关键词库
    """

    def __init__(self):
        self.llm = get_llm_service()

    def generate(
        self,
        business_info: Dict[str, Any],
        business_direction: str,
        max_keywords: int = 200,
    ) -> KeywordLibraryResult:
        """
        生成关键词库

        Args:
            business_info: 业务信息
                - business_description: 原始业务描述
                - industry: 行业
                - business_type: 业务类型 (product/service)
            business_direction: 用户选择的蓝海业务方向（如"进口有机羊奶粉"）
            max_keywords: 最大关键词数量

        Returns:
            KeywordLibraryResult: 生成结果
        """
        result = KeywordLibraryResult()

        try:
            # 参数提取
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')

            if not business_direction:
                result.error_message = "业务方向不能为空"
                return result

            if not business_desc:
                result.error_message = "业务描述不能为空"
                return result

            # 生成Prompt
            prompt = self._build_keyword_prompt(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                business_direction=business_direction,
                max_keywords=max_keywords,
            )

            # 调用LLM
            logger.info("[KeywordLibraryGenerator] 开始调用LLM...")
            logger.info(f"[KeywordLibraryGenerator] 业务方向: {business_direction}")

            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=4000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            # 解析结果
            result = self._parse_result(response, result)

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
                "[KeywordLibraryGenerator] 生成完成: 问题类型=%d, 关键词=%d (蓝海=%d, 红海=%d)",
                len(result.problem_types),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
            )

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] 生成异常: %s", str(e))
            result.error_message = f"生成异常: {str(e)}"

        return result

    def _build_keyword_prompt(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        business_direction: str,
        max_keywords: int,
    ) -> str:
        """构建关键词库生成Prompt"""

        # 问题类型分类指引
        problem_type_guide = """
【问题类型分类指引】（仅作为画像分类标签，一个类型可对应多个画像场景）
问题类型应该：
- 简短明确：2-4个字，如"肠道问题"、"效果存疑"
- 代表一类痛点或需求：不要过于具体，也不要过于抽象
- 有区分度：不同类型之间有明显差异
- **每个类型必须包含5-10个场景关键词**

示例（奶粉行业，方向="进口有机羊奶粉"）：
- "肠道问题" → 羊奶粉拉肚子、羊奶粉便秘、羊奶粉腹胀、羊奶粉绿便、羊奶粉不消化、换羊奶粉拉肚子
- "发育焦虑" → 羊奶粉宝宝不长肉、羊奶粉宝宝不长个、羊奶粉体重增长慢、羊奶粉厌奶怎么办
- "选品困惑" → 羊奶粉哪个牌子好、羊奶粉和牛奶粉区别、有机羊奶粉怎么选
- "购买顾虑" → 羊奶粉会不会买到假货、羊奶粉价格太贵、羊奶粉真假辨别

示例（桶装水行业，方向="办公室桶装水配送"）：
- "送水等待" → 等水等到嗓子冒烟、楼层高搬水太费劲、周末没人送水
- "水质担忧" → 桶装水安全吗、饮水机内部有多脏、水源来自哪里
- "机器维护" → 饮水机多久清洗一次、滤芯什么时候换、饮水机有异味
- "订购套路" → 第一次订桶装水被坑、续费发现价格涨了、买水送饮水机划算吗
"""

        # 关键词库分类
        keyword_guide = """
【关键词库生成要求】
基于业务方向「{business_direction}」，按以下分类生成{max_keywords}个关键词，严格区分蓝海/红海：

1. 蓝海关键词（细分人群/长尾需求）：
   - 细分人群词：围绕业务方向的细分人群
   - 细分场景词：围绕业务方向的具体使用场景
   - 细分痛点词：围绕业务方向的痛点需求
   - 长尾问题词：围绕业务方向的问题搜索

2. 红海关键词（大众竞争词）：
   - 品类大词：业务方向的通用品类词
   - 品牌词：已有品牌名称
   - 通用需求词：大众化需求词

蓝海关键词占比建议：60%以上

每个分类关键词数量要求：
- 蓝海关键词：至少{min_blue}个
- 红海关键词：最多{max_red}个
""".format(
            business_direction=business_direction,
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

        prompt = f"""你是关键词库生成专家。请基于给定的业务方向，生成精准的关键词库和问题类型。

=== 业务信息 ===
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
业务类型：{business_type_hint}

=== 核心业务方向（用户选定）===
{business_direction}

这是用户经过市场分析后选择的蓝海方向，你需要围绕这个方向生成最精准的关键词库。

=== 生成任务 ===

1. **问题类型生成**：基于业务方向，生成3-6个问题类型
   - 一个类型对应一类痛点，可生成多个画像
   - **【重要】每个类型必须生成5-10个场景关键词，用于后续画像生成**
{problem_type_guide}

2. **关键词库生成**（区分蓝海/红海）：
{keyword_guide}

=== 输出格式 ===
请严格按以下JSON格式输出，不要输出任何其他内容：

{{
    "problem_types": [
        {{
            "type_name": "肠道问题",
            "description": "宝宝肠道相关问题",
            "target_audience": "羊奶粉喂养宝宝家庭",
            "keywords": ["羊奶粉拉肚子", "羊奶粉便秘", "羊奶粉腹胀", "羊奶粉绿便", "羊奶粉不消化", "换羊奶粉拉肚子", "羊奶粉过敏症状", "羊奶粉乳糖不耐受"]
        }}
    ],
    "keyword_library": {{
        "total_count": {max_keywords},
        "business_direction": "{business_direction}",
        "categories": [
            {{
                "category_name": "细分人群词",
                "keywords": ["有机羊奶粉宝宝", "进口羊奶粉宝宝"],
                "market_type": "blue_ocean",
                "proportion": 0.2
            }},
            {{
                "category_name": "品类大词",
                "keywords": ["羊奶粉", "羊奶"],
                "market_type": "red_ocean",
                "proportion": 0.15
            }}
        ]
    }}
}}

请开始生成："""

        return prompt

    def _parse_result(
        self,
        response: str,
        result: KeywordLibraryResult
    ) -> KeywordLibraryResult:
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
            logger.warning("[KeywordLibraryGenerator] JSON解析失败，尝试修复: %s", e)
            data = self._try_fix_json(response)
            if not data:
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

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

        return result

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的JSON"""

        import re

        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]

            try:
                return json.loads(json_str)
            except:
                pass

            # 修复常见问题
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                return json.loads(json_str)
            except:
                pass

        return None


# ============================================================
# 便捷函数
# ============================================================

def generate_keyword_library(
    business_info: Dict[str, Any],
    business_direction: str,
    max_keywords: int = 200,
) -> KeywordLibraryResult:
    """
    便捷函数：生成关键词库

    使用方式：
        from services.keyword_library_generator import generate_keyword_library

        result = generate_keyword_library(
            business_info={'business_description': '卖奶粉', 'industry': '奶粉'},
            business_direction='进口有机羊奶粉',
            max_keywords=200
        )

        if result.success:
            print(f"生成 {result.total_keywords} 个关键词")
            print(f"蓝海关键词: {result.blue_ocean_keywords}")
    """
    generator = KeywordLibraryGenerator()
    return generator.generate(business_info, business_direction, max_keywords)
