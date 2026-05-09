#!/usr/bin/env python3
"""
公开页面市场机会分析服务

功能：精准蓝海市场机会挖掘
核心：从业务+画像出发，找到被大品牌忽略的细分机会
"""

import re
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from services.llm import smart_chat

logger = logging.getLogger(__name__)


class PublicMarketOpportunityService:
    """公开页面市场机会分析服务"""

    def _escape_fstring(self, s: str) -> str:
        """转义字符串中的花括号，防止在 f-string 中被误解析为占位符"""
        if not isinstance(s, str):
            return ''
        return s.replace('{', '{{').replace('}', '}}')

    def __init__(self):
        """初始化服务"""
        pass

    def generate_opportunity(self, business_info: Dict, portraits_data: List[Dict]) -> Dict:
        """
        生成市场机会分析 - 蓝海精准挖掘

        Args:
            business_info: 业务信息
            portraits_data: 用户画像列表

        Returns:
            市场机会分析结果
        """
        if not isinstance(business_info, dict) or not business_info.get('business_description'):
            return {'success': False, 'error': '缺少业务描述'}

        # 1. 构建精简的上下文
        context = self._build_context(business_info, portraits_data)

        # 2. 构建蓝海挖掘提示词
        prompt = self._build_blue_ocean_prompt(context)

        # 3. 调用LLM
        try:
            response = smart_chat(
                messages=[{'role': 'user', 'content': prompt}],
                task_type='market_analysis',
            )

            content = response if isinstance(response, str) else (response.get('content', '') if isinstance(response, dict) else '')
            if not content:
                return {'success': False, 'error': 'LLM返回为空'}

            # 4. 解析响应
            result = self._parse_opportunity_response(content)

            if result and isinstance(result, dict):
                return {
                    'success': True,
                    'data': {
                        'opportunities': result,
                        'generated_at': datetime.now().isoformat(),
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f'解析失败: {type(result)}',
                    'raw_response': content[:500],
                }

        except Exception as e:
            error_str = str(e)
            if len(error_str) > 300:
                error_str = error_str[:300] + '...'
            logger.error("[PublicMarketOpportunity] 生成市场机会失败: " + error_str)
            return {'success': False, 'error': error_str}

    def _build_context(self, business_info: Dict, portraits_data: List[Dict]) -> Dict:
        """构建精简上下文"""
        # 提取业务核心（去冗余）
        business_desc = business_info.get('business_description', '')

        # 提取用户核心痛点（从完整画像对象中提取关键信息）
        personas = []
        if portraits_data and isinstance(portraits_data, list):
            for p in portraits_data[:5]:  # 最多5个画像
                if isinstance(p, dict):
                    name = p.get('name', '未知')

                    # 优先从 portrait_summary 提取（自然语言摘要）
                    summary = p.get('portrait_summary', '').strip()

                    # 其次从 user_perspective.problem 提取
                    if not summary:
                        user_persp = p.get('user_perspective', {})
                        summary = user_persp.get('problem', '')

                    # 再其次从 buyer_perspective 提取
                    if not summary:
                        buyer_persp = p.get('buyer_perspective', {})
                        summary = buyer_persp.get('goal', '') or buyer_persp.get('obstacles', '')

                    if name and summary:
                        escaped_name = self._escape_fstring(name)
                        escaped_summary = self._escape_fstring(summary[:80])
                        personas.append(f"{escaped_name}: {escaped_summary}")

        return {
            'business': self._escape_fstring(business_desc),
            'personas': personas,
        }

    def _build_blue_ocean_prompt(self, context: Dict) -> str:
        """构建蓝海挖掘提示词（增强版，融入供需失衡框架）"""
        personas_text = '\n'.join([f"- {p}" for p in context['personas']]) if context['personas'] else "暂无画像"

        return f"""你是蓝海市场挖掘专家。请根据以下用户画像，识别4-6个精准切入点。

【用户画像】
{personas_text}

=== 专科医生思维（核心方法论）===
1. 行业分析：找到行业的蓝海细分市场，发现问题
2. 人群细分：从细分人群找到长尾需求
3. 付费人/使用人区分：
   - 付费人关心：价值、成本、效果、可报销
   - 使用人关心：体验、品质、方便
4. 搜前搜后覆盖：
   - 搜前：问题探索（"XX怎么办"）
   - 搜中：方案对比（"XX和XX哪个好"）
   - 搜后：购买决策（"XX多少钱"）
5. 行业关联：联动上下游业务机会

=== 供需失衡分析（必须分析）===
需求侧分析：
- 用户的问题是什么？有多痛？有多急？
- 痛点强度：高(立刻要)/中(迟早要)/低(可以等)

供给侧分析：
- 为什么没人做好？供给缺口在哪里？
- 竞品是否忽略了这个细分？

=== 严重程度 × 紧急程度矩阵 ===
| 组合 | 优先级 | 策略 |
|------|--------|------|
| 高严重+高紧急 | P0 | 立刻要解决 |
| 高严重+低紧急 | P1 | 迟早要解决 |
| 中严重+高紧急 | P2 | 快速收割 |
| 低严重+低紧急 | P3 | 长期培育 |

=== 三类客户群体覆盖 ===
必须为每个切入点分析覆盖的人群：

| 人群 | 画像 | 消费场景 | 核心需求 | 内容方向 |
|------|------|----------|----------|----------|
| 本地居民 | 本地常住人口 | 自家消费、到店 | 实惠、方便、新鲜 | 性价比、便利性 |
| 返乡人 | 春节从外地返乡 | 送礼、带特产 | 品质、包装、便携 | 送礼攻略、品质推荐 |
| 在外本地人 | 在外地工作 | 思念家乡味、复购 | 正宗、情怀、邮寄 | 乡愁内容、品牌故事 |

=== B端 vs C端区分 ===
| 维度 | B端(企业) | C端(家庭) |
|------|-----------|-----------|
| 购买目的 | 品牌展示、招待客户、员工福利 | 日常饮用、家庭使用 |
| 决策人 | 老板、行政、采购、财务 | 家庭主妇、上班族、老年人 |
| 核心需求 | 性价比、可报销、门槛低 | 品质、价格、方便 |
| 转化周期 | 3-7天 | 当天或几分钟 |

=== 维度拆解 ===
从以下维度中选择适用的，直接基于画像痛点展开：

产品维度：规格/容量/材质/形态/标识/包装
场景维度：时间/地点/频次/人群/行为习惯
渠道维度：购买渠道/配送方式/自提/订阅制
服务维度：售前/售后/增值/体验/保障

=== 约束 ===
- 只基于画像中出现的痛点，禁止虚构人群/场景
- 每个切入点要具体可落地（如"200ml迷你瓶，专为书包侧袋设计"）
- 不要引入画像之外的信息

=== 输出 ===
```json
{{
    "opportunities": [
        {{
            "dimension": "维度名",
            "entry_point": "切入点名称",
            "target_persona": "针对画像中的什么问题",
            "pain_level": "high/medium/low",
            "supply_gap": "供给缺口描述",
            "severity_urgency": "P0/P1/P2/P3",
            "customer_types": ["本地居民", "返乡人", "在外本地人"],
            "client_types": ["B端", "C端"],
            "search_stages": ["awareness", "consideration", "decision"],
            "specific_solution": "具体怎么切入"
        }}
    ]
}}
```
禁止复制格式，必须基于画像真实生成。

请开始："""

    def _parse_opportunity_response(self, content: str) -> Optional[Dict]:
        """解析切入点响应，直接返回文本内容"""
        return {'content': content.strip()}

    def format_markdown(self, result: Dict) -> str:
        """将结果格式化为Markdown"""
        if not result.get('success'):
            return f"❌ 生成失败：{result.get('error', '未知错误')}"

        data = result.get('data', {})
        opportunities = data.get('opportunities', {})
        content = opportunities.get('content', '')

        md = """# 🎯 蓝海机会挖掘

"""
        md += content if content else "（暂无内容）"

        return md


# 全局单例
_market_opportunity_service = None


def get_public_market_opportunity_service() -> PublicMarketOpportunityService:
    """获取全局单例"""
    global _market_opportunity_service
    if _market_opportunity_service is None:
        _market_opportunity_service = PublicMarketOpportunityService()
    return _market_opportunity_service
