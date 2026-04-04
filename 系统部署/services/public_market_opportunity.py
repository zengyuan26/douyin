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
        """构建蓝海挖掘提示词"""
        personas_text = '\n'.join([f"- {p}" for p in context['personas']]) if context['personas'] else "暂无画像"

        prompt = f"""你是蓝海市场挖掘专家。请根据以下用户画像，从多个维度拆解切入点。

**重要：只基于用户画像分析，不要引入行业、业务等额外背景信息。**

【用户画像】
{personas_text}

**任务**：
画像描述了用户的具体问题。现在请从**多个维度**分析切入点：
- 每个维度代表一种切入角度
- 维度之间相互独立，可以同时存在
- 直接基于画像中的具体问题来拆解

**维度拆解思路**（可根据画像自由选择）：

| 维度 | 拆解方向 | 示例 |
|------|----------|------|
| **产品包装** | 规格、材质、形态、标识 | 瓶子太大→小瓶装；容易拿错→定制标记 |
| **产品规格** | 容量、浓度、份量 | 喝不完→一次性小剂量 |
| **使用场景** | 时间、地点、频次 | 上学不方便→随身装；办公→桌面装 |
| **购买方式** | 渠道、频次、门槛 | 定期购买→订阅制；试用→小包装试买 |
| **配送方式** | 速度、频次、范围 | 上门配送→定时达；自提→驿站覆盖 |
| **产品形态** | 固体/液体/即食/浓缩 | 桶装水→净水器+水袋；瓶装→即热式 |
| **服务模式** | 售前/售后/增值 | 免费试用→先用后买；检测→专业背书 |
| **人群细分** | 年龄/职业/习惯 | 学生→校园装；白领→办公室装 |

**输出格式**：

请根据画像，从**4-6个维度**给出切入点：

1. **【XX维度】切入点名称**
   - 针对画像：[画像中的什么问题]
   - 切入点：[具体怎么切入]

2. ...

**要求**：
- 4-6个维度，只基于画像中出现的痛点
- 每个切入点要具体，如"200ml以下迷你瓶，专为书包侧袋设计"
- 不引入画像之外的任何人群或场景"""
        return prompt

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
