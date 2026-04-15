"""
画像生成服务（基于关键词库）

功能：
1. 基于关键词库生成人群画像
2. 支持问题类型标签（用于分类）
3. 一个问题类型可生成多个画像（不同场景）
4. 画像包含：身份、痛点、顾虑、场景等

使用方式：
from services.portrait_generator import PortraitGenerator, PortraitGenerationContext

generator = PortraitGenerator()
portraits = generator.generate_portraits(
    keyword_library=keyword_library,
    problem_types=problem_types,
    business_info=business_info,
    portraits_per_type=3  # 每个问题类型生成3个画像
)
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class Portrait:
    """人群画像"""
    # 基础信息
    portrait_id: str                              # 画像ID
    problem_type: str                            # 问题类型（分类标签）
    problem_type_description: str               # 问题类型描述

    # 核心维度
    identity: str                                # 身份标签
    identity_description: str                   # 身份描述

    # 五要素摘要（核心！）
    portrait_summary: str = ""                  # 画像摘要：身份+问题+想转变+困境+深层需求

    # 痛点相关
    pain_points: List[str]                       # 核心痛点
    pain_scenarios: List[str]                   # 痛点场景

    # 心理相关
    psychology: Dict[str, Any]                  # 心理画像
    barriers: List[str]                          # 购买顾虑

    # 行为相关
    search_keywords: List[str]                  # 搜索关键词
    content_preferences: List[str]               # 内容偏好

    # 市场定位
    market_type: str                             # blue_ocean / red_ocean
    differentiation: str                         # 差异化方向

    # 元信息
    scene_tags: List[str] = field(default_factory=list)   # 场景标签
    behavior_tags: List[str] = field(default_factory=list)  # 行为标签
    content_direction: str = "种草型"                        # 内容方向


@dataclass
class PortraitGenerationContext:
    """画像生成上下文"""
    keyword_library: Dict[str, Any]             # 关键词库
    problem_types: List[Dict[str, Any]]         # 问题类型列表
    business_info: Dict[str, Any]                # 业务信息
    market_opportunities: List[Dict[str, Any]] = field(default_factory=list)  # 市场机会
    portraits_per_type: int = 3                   # 每个问题类型生成画像数


class PortraitGenerator:
    """
    画像生成器（基于关键词库）

    核心能力：
    1. 基于关键词库生成精准画像
    2. 按问题类型分类（一个类型 → 多个画像）
    3. 画像包含完整的身份、痛点、心理、行为维度
    """

    def __init__(self):
        self.llm = get_llm_service()

    def generate_portraits(
        self,
        context: PortraitGenerationContext,
    ) -> List[Portrait]:
        """
        批量生成画像

        Args:
            context: 生成上下文
                - keyword_library: 关键词库
                - problem_types: 问题类型列表
                - business_info: 业务信息
                - portraits_per_type: 每个问题类型生成画像数

        Returns:
            List[Portrait]: 画像列表
        """
        portraits = []

        try:
            business_desc = context.business_info.get('business_description', '')
            business_type = context.business_info.get('business_type', 'product')

            logger.info(
                "[PortraitGenerator] 开始生成: 业务=%s, 问题类型=%d, 每类型画像=%d",
                business_desc[:30],
                len(context.problem_types),
                context.portraits_per_type,
            )

            # 按问题类型分组生成画像
            for i, problem_type in enumerate(context.problem_types):
                type_name = problem_type.get('type_name', '')
                type_desc = problem_type.get('description', '')
                type_audience = problem_type.get('target_audience', '')
                type_keywords = problem_type.get('keywords', [])

                logger.info(
                    "[PortraitGenerator] 生成问题类型 %d/%d: %s",
                    i + 1, len(context.problem_types), type_name
                )

                # 为每个问题类型生成多个画像（不同场景）
                type_portraits = self._generate_portraits_for_type(
                    problem_type_name=type_name,
                    problem_type_desc=type_desc,
                    target_audience=type_audience,
                    type_keywords=type_keywords,
                    keyword_library=context.keyword_library,
                    business_info=context.business_info,
                    count=context.portraits_per_type,
                    market_opportunities=context.market_opportunities,
                )

                portraits.extend(type_portraits)

            logger.info("[PortraitGenerator] 生成完成: 共 %d 个画像", len(portraits))

        except Exception as e:
            logger.error("[PortraitGenerator] 生成异常: %s", str(e))

        return portraits

    def _generate_portraits_for_type(
        self,
        problem_type_name: str,
        problem_type_desc: str,
        target_audience: str,
        type_keywords: List[str],
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
        count: int,
        market_opportunities: List[Dict[str, Any]],
    ) -> List[Portrait]:
        """为一个问题类型生成多个画像"""

        portraits = []

        # 构建Prompt
        prompt = self._build_portrait_prompt(
            problem_type_name=problem_type_name,
            problem_type_desc=problem_type_desc,
            target_audience=target_audience,
            type_keywords=type_keywords,
            keyword_library=keyword_library,
            business_info=business_info,
            count=count,
            market_opportunities=market_opportunities,
        )

        # 调用LLM
        logger.info("[PortraitGenerator] 开始调用LLM...")
        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat(messages, temperature=0.7, max_tokens=4000)

        if not response:
            logger.warning("[PortraitGenerator] LLM返回为空")
            return portraits

        # 解析画像
        portraits = self._parse_portraits(
            response=response,
            problem_type_name=problem_type_name,
            problem_type_desc=problem_type_desc,
        )

        return portraits

    def _build_portrait_prompt(
        self,
        problem_type_name: str,
        problem_type_desc: str,
        target_audience: str,
        type_keywords: List[str],
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
        count: int,
        market_opportunities: List[Dict[str, Any]],
    ) -> str:
        """构建画像生成Prompt"""

        business_desc = business_info.get('business_description', '')
        industry = business_info.get('industry', '')
        business_type = business_info.get('business_type', 'product')

        # 提取蓝海关键词
        blue_ocean_kw = []
        for cat in keyword_library.get('categories', []):
            if cat.get('market_type') == 'blue_ocean':
                blue_ocean_kw.extend(cat.get('keywords', [])[:20])

        # 提取红海关键词
        red_ocean_kw = []
        for cat in keyword_library.get('categories', []):
            if cat.get('market_type') == 'red_ocean':
                red_ocean_kw.extend(cat.get('keywords', [])[:10])

        # 市场机会信息
        opportunities_text = ""
        if market_opportunities:
            opp_list = []
            for opp in market_opportunities[:3]:
                opp_list.append(
                    f"- {opp.get('opportunity_name', '')}: "
                    f"{opp.get('target_audience', '')} - {opp.get('pain_points', [])}"
                )
            opportunities_text = "\n".join(opp_list)

        prompt = f"""你是人群画像生成专家。请基于以下信息，为「{problem_type_name}」类型生成{count}个精准人群画像。

=== 业务信息 ===
业务：{business_desc}
行业：{industry or '根据业务描述推断'}
问题类型：{problem_type_name}
问题描述：{problem_type_desc}
目标人群：{target_audience}
类型关键词：{', '.join(type_keywords[:10])}

=== 蓝海关键词（优先使用）===
{', '.join(blue_ocean_kw[:30])}

=== 红海关键词（辅助参考）===
{', '.join(red_ocean_kw[:20])}

=== 市场机会参考 ===
{opportunities_text}

=== 画像生成要求 ===
为「{problem_type_name}」问题类型生成{count}个画像，每个画像要：
1. **场景差异化**：场景要不同，如"宝宝拉肚子急哭的新手妈妈" vs "长期便秘困扰的宝宝家庭"
2. **痛点细化**：痛点要具体，如"不知道是不是奶粉问题" vs "确定是奶粉问题但不知道换哪个"
3. **身份细分**：身份要有区分度，如"职场妈妈" vs "全职妈妈"

每个画像必须包含：
- identity: 身份标签（简短，如"职场新手妈妈"）
- identity_description: 身份描述（50字内）
- portrait_summary: 【核心必填】2-3句口语化自然中文摘要，结构公式：身份 + 当前问题/症状 + 想转变 + 受限于困境 + 【深层需求】。禁止用【】、禁止列模板标签、禁止JSON式字段名。
- pain_points: 3-5个核心痛点
- pain_scenarios: 2-3个痛点场景
- psychology: 心理画像
- barriers: 2-3个购买顾虑
- search_keywords: 3-5个搜索关键词（用蓝海词）
- content_preferences: 2-3个内容偏好
- market_type: blue_ocean
- differentiation: 差异化方向

=== 输出格式 ===
请严格按以下JSON格式输出{count}个画像：

{{
    "portraits": [
        {{
            "identity": "画像身份标签",
            "identity_description": "画像身份详细描述",
            "portrait_summary": "【必填】口语化自然中文，结构：身份+问题症状+想转变+困境+【深层需求】",
            "pain_points": ["痛点1", "痛点2", "痛点3"],
            "pain_scenarios": ["场景1", "场景2"],
            "psychology": {{
                "核心焦虑": "心理描述",
                "决策障碍": "障碍描述"
            }},
            "barriers": ["顾虑1", "顾虑2"],
            "search_keywords": ["关键词1", "关键词2"],
            "content_preferences": ["偏好1", "偏好2"],
            "market_type": "blue_ocean",
            "differentiation": "差异化方向"
        }}
    ]
}}

请开始生成："""

        return prompt

    def _parse_portraits(
        self,
        response: str,
        problem_type_name: str,
        problem_type_desc: str,
    ) -> List[Portrait]:
        """解析LLM返回的画像"""

        import re

        portraits = []

        try:
            # 提取JSON
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            portrait_list = data.get('portraits', [])

            for i, p in enumerate(portrait_list):
                portrait = Portrait(
                    portrait_id=f"{problem_type_name}_{i+1}",
                    problem_type=problem_type_name,
                    problem_type_description=problem_type_desc,
                    identity=p.get('identity', ''),
                    identity_description=p.get('identity_description', ''),
                    portrait_summary=p.get('portrait_summary', ''),
                    pain_points=p.get('pain_points', []),
                    pain_scenarios=p.get('pain_scenarios', []),
                    psychology=p.get('psychology', {}),
                    barriers=p.get('barriers', []),
                    search_keywords=p.get('search_keywords', []),
                    content_preferences=p.get('content_preferences', []),
                    market_type=p.get('market_type', 'blue_ocean'),
                    differentiation=p.get('differentiation', ''),
                )
                portraits.append(portrait)

        except json.JSONDecodeError:
            logger.warning("[PortraitGenerator] JSON解析失败: %s", response[:200])

        return portraits

    def generate_single_portrait(
        self,
        problem_type: str,
        problem_type_desc: str,
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
    ) -> Optional[Portrait]:
        """
        生成单个画像

        Args:
            problem_type: 问题类型
            problem_type_desc: 问题类型描述
            keyword_library: 关键词库
            business_info: 业务信息

        Returns:
            Portrait 或 None
        """
        context = PortraitGenerationContext(
            keyword_library=keyword_library,
            problem_types=[{
                'type_name': problem_type,
                'description': problem_type_desc,
                'target_audience': '',
                'keywords': [],
            }],
            business_info=business_info,
            portraits_per_type=1,
        )

        portraits = self.generate_portraits(context)
        return portraits[0] if portraits else None


# ============================================================
# 便捷函数
# ============================================================

def generate_portraits_from_analysis(
    analysis_result: Dict[str, Any],
    business_info: Dict[str, Any],
    portraits_per_type: int = 3,
) -> List[Dict[str, Any]]:
    """
    从市场分析结果生成画像

    使用方式：
        from services.portrait_generator import generate_portraits_from_analysis

        portraits = generate_portraits_from_analysis(
            analysis_result={
                'keyword_library': result.keyword_library,
                'problem_types': [p.__dict__ for p in result.problem_types],
                'market_opportunities': [o.__dict__ for o in result.market_opportunities],
            },
            business_info={'business_description': '卖奶粉'},
            portraits_per_type=3,
        )
    """
    generator = PortraitGenerator()

    # 转换数据格式
    keyword_library = analysis_result.get('keyword_library', {})
    problem_types = analysis_result.get('problem_types', [])
    market_opportunities = analysis_result.get('market_opportunities', [])

    # 确保problem_types格式正确
    if problem_types and hasattr(problem_types[0], '__dict__'):
        # dataclass对象转换为dict
        problem_types = [
            {
                'type_name': p.type_name,
                'description': p.description,
                'target_audience': p.target_audience,
                'keywords': p.keywords,
            }
            for p in problem_types
        ]

    # 确保market_opportunities格式正确
    if market_opportunities and hasattr(market_opportunities[0], '__dict__'):
        market_opportunities = [
            {
                'opportunity_name': o.opportunity_name,
                'target_audience': o.target_audience,
                'pain_points': o.pain_points,
                'keywords': o.keywords,
                'content_direction': o.content_direction,
                'market_type': o.market_type,
                'confidence': o.confidence,
            }
            for o in market_opportunities
        ]

    context = PortraitGenerationContext(
        keyword_library=keyword_library,
        problem_types=problem_types,
        business_info=business_info,
        market_opportunities=market_opportunities,
        portraits_per_type=portraits_per_type,
    )

    portraits = generator.generate_portraits(context)

    # 转换为字典格式
    return [
        {
            'portrait_id': p.portrait_id,
            'problem_type': p.problem_type,
            'problem_type_description': p.problem_type_description,
            'identity': p.identity,
            'identity_description': p.identity_description,
            'pain_points': p.pain_points,
            'pain_scenarios': p.pain_scenarios,
            'psychology': p.psychology,
            'barriers': p.barriers,
            'search_keywords': p.search_keywords,
            'content_preferences': p.content_preferences,
            'market_type': p.market_type,
            'differentiation': p.differentiation,
            'scene_tags': p.scene_tags,
            'behavior_tags': p.behavior_tags,
            'content_direction': p.content_direction,
        }
        for p in portraits
    ]


def group_portraits_by_problem_type(
    portraits: List[Union['Portrait', Dict[str, Any]]]
) -> Dict[str, List[Union['Portrait', Dict[str, Any]]]]:
    """
    按问题类型分组画像
    支持 Portrait 对象或字典列表

    Returns:
        {
            '肠道问题': [portrait1, portrait2, ...],
            '发育焦虑': [portrait3, portrait4, ...],
        }
    """
    grouped = {}
    for portrait in portraits:
        # 支持 Portrait 对象或字典
        if hasattr(portrait, 'problem_type'):
            problem_type = portrait.problem_type
        else:
            problem_type = portrait.get('problem_type', '未分类') if isinstance(portrait, dict) else '未分类'

        if problem_type not in grouped:
            grouped[problem_type] = []
        grouped[problem_type].append(portrait)
    return grouped
