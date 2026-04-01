"""
选题生成服务

基于用户画像和问题关键词，生成5个精准选题
"""

import json
import re
import random
import logging
from datetime import datetime
from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class TopicGenerator:
    """选题生成器"""

    # 选题类型
    TOPIC_TYPES = [
        '问题诊断',   # 诊断类：指出问题，引发共鸣
        '解决方案',   # 方案类：给出具体解决方案
        '经验分享',   # 故事类：分享真实经历
        '避坑指南',   # 警示类：帮助用户避雷
        '知识科普',   # 科普类：传递专业知识
    ]

    def __init__(self):
        self.llm = get_llm_service()

    def generate_topics(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portraits: list,
        problem_keywords: list,
        is_premium: bool = False
    ) -> dict:
        """
        生成选题

        Args:
            business_description: 业务描述
            business_range: 经营范围 (local/cross_region)
            business_type: 业务类型
            portraits: 用户画像列表
            problem_keywords: 问题关键词列表
            is_premium: 是否付费用户

        Returns:
            dict: {
                "success": bool,
                "topics": list,
                "error": str (可选)
            }
        """
        try:
            # 构建用户画像描述
            portrait_descriptions = self._build_portrait_descriptions(portraits)

            # 构建问题关键词描述
            keyword_text = ', '.join(problem_keywords[:10]) if problem_keywords else ''

            # 获取当前时间信息
            current_season = self._get_current_season()
            current_month = datetime.now().month

            # 构建Prompt
            prompt = self._build_topic_prompt(
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portrait_descriptions=portrait_descriptions,
                keyword_text=keyword_text,
                current_season=current_season,
                current_month=current_month,
                is_premium=is_premium
            )

            # 调用LLM生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容策划专家，擅长根据用户画像和问题关键词，生成精准的短视频/图文选题。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            topics = self._parse_topics_response(response)

            if not topics:
                return {
                    'success': False,
                    'error': '选题生成失败，请重试'
                }

            return {
                'success': True,
                'topics': topics
            }

        except Exception as e:
            logger.error("[TopicGenerator] Error: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def _build_portrait_descriptions(self, portraits: list) -> str:
        """构建用户画像描述"""
        if not portraits:
            return ''

        descriptions = []
        for i, portrait in enumerate(portraits[:5]):  # 最多5个画像
            if isinstance(portrait, dict):
                identity = portrait.get('identity', '')
                pain_point = portrait.get('pain_point', portrait.get('核心痛点', ''))
                concern = portrait.get('concern', portrait.get('核心顾虑', ''))

                desc = f"{i+1}. {identity}"
                if pain_point:
                    desc += f" - 痛点: {pain_point}"
                if concern:
                    desc += f" - 顾虑: {concern}"
                descriptions.append(desc)
            else:
                descriptions.append(f"{i+1}. {str(portrait)}")

        return '\n'.join(descriptions)

    def _get_current_season(self) -> str:
        """获取当前季节"""
        month = datetime.now().month

        if month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        elif month in [9, 10, 11]:
            return "秋季"
        else:
            return "冬季"

    def _build_topic_prompt(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portrait_descriptions: str,
        keyword_text: str,
        current_season: str,
        current_month: int,
        is_premium: bool
    ) -> str:
        """构建选题生成Prompt"""

        # 根据业务类型调整提示
        if business_type == 'local_service':
            content_focus = "本地服务"
            keyword_focus = "地域词、服务词"
        elif business_type == 'product':
            content_focus = "产品销售"
            keyword_focus = "产品词、品质词"
        else:
            content_focus = "专业服务"
            keyword_focus = "专业词、方案词"

        prompt = f"""你是一位资深的内容策划专家。请根据以下信息，生成5个精准的短视频/图文选题。

## 业务信息
- 业务描述：{business_description}
- 经营范围：{'本地服务' if business_range == 'local' else '跨区域服务'}
- 业务类型：{content_focus}

## 目标用户画像
{portrait_descriptions or '暂无详细画像信息'}

## 问题关键词
{keyword_text or '暂无关键词信息'}

## 当前时间
- 季节：{current_season}（{current_month}月）
- 选题需考虑季节特性

## 选题要求
1. 每个选题围绕一个具体问题，标题简洁有力
2. 标题包含问题关键词或痛点词
3. 选题类型包含：
   - 问题诊断型：引发用户共鸣
   - 解决方案型：给出实用建议
   - 经验分享型：真实故事
4. 符合当前时间节点特点
5. 每个选题说明推荐理由

## 输出格式（严格JSON）
```json
[
  {{
    "id": "1",
    "title": "选题标题（20字以内）",
    "type": "问题诊断/解决方案/经验分享/避坑指南/知识科普",
    "target": "目标人群描述",
    "reason": "推荐理由（为什么选这个选题）"
  }},
  ...共5个选题
]
```

请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _parse_topics_response(self, response: str) -> list:
        """解析LLM返回的选题结果"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                topics = json.loads(json_str)
                if isinstance(topics, list):
                    return topics[:5]  # 最多返回5个

            # 如果解析失败，返回默认选题
            return self._get_default_topics()

        except Exception as e:
            logger.debug("[TopicGenerator] Parse error: %s", e)
            return self._get_default_topics()

    def _get_default_topics(self) -> list:
        """获取默认选题（当LLM生成失败时使用）"""
        return [
            {
                "id": "1",
                "title": "您可能遇到的问题及解决方案",
                "type": "问题诊断",
                "target": "目标用户",
                "reason": "通用问题诊断选题"
            },
            {
                "id": "2",
                "title": "如何选择适合自己的方案",
                "type": "解决方案",
                "target": "有选择困惑的用户",
                "reason": "解决方案型选题"
            },
            {
                "id": "3",
                "title": "过来人的真实经验分享",
                "type": "经验分享",
                "target": "想了解真实案例的用户",
                "reason": "经验分享型选题"
            },
            {
                "id": "4",
                "title": "新手常见的误区与避坑指南",
                "type": "避坑指南",
                "target": "新手用户",
                "reason": "避坑指南型选题"
            },
            {
                "id": "5",
                "title": "必须了解的核心知识点",
                "type": "知识科普",
                "target": "想深入了解的用户",
                "reason": "知识科普型选题"
            }
        ]
