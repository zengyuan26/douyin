"""
选题生成服务

基于用户画像和问题关键词，生成5个精准选题
"""

import json
import re
import random
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from services.llm import get_llm_service
from services.temperature_word_library import temperature_word_library

logger = logging.getLogger(__name__)


class TopicGenerator:
    """选题生成器"""

    # 选题类型（与前端8大类型对应）
    TOPIC_TYPES = [
        '问题诊断',   # 诊断类：指出问题，引发共鸣
        '解决方案',   # 方案类：给出具体解决方案
        '经验分享',   # 故事类：分享真实经历
        '避坑指南',   # 警示类：帮助用户避雷
        '知识科普',   # 科普类：传递专业知识
    ]

    # 8大选题类型体系（前端展示用）
    TOPIC_TYPE_SYSTEM = [
        {'key': 'problem_diagnosis', 'name': '问题诊断类', 'desc': '挖掘痛点，引发共鸣'},
        {'key': 'solution', 'name': '解决方案类', 'desc': '提供实用方法，高收藏'},
        {'key': 'case_share', 'name': '案例分享类', 'desc': '真实案例故事，促转化'},
        {'key': 'knowledge', 'name': '知识科普类', 'desc': '传授专业知识，建权威'},
        {'key': 'hot_topic', 'name': '热点关联类', 'desc': '蹭当前热点，获流量'},
        {'key': 'persona', 'name': '人设故事类', 'desc': '价值观/故事，建立信任'},
        {'key': 'opinion', 'name': '观点输出类', 'desc': '表达立场态度，建权威'},
        {'key': 'pitfall', 'name': '避坑指南类', 'desc': '帮助用户避雷，防损失'},
    ]

    # 类型键到类型名称的映射
    TYPE_KEY_TO_NAME = {
        'problem_diagnosis': '问题诊断',
        'solution': '解决方案',
        'case_share': '经验分享',
        'knowledge': '知识科普',
        'hot_topic': '热点关联',
        'persona': '人设故事',
        'opinion': '观点输出',
        'pitfall': '避坑指南',
    }

    def __init__(self):
        self.llm = get_llm_service()

    # 问题句检测模式
    QUESTION_PATTERNS = [
        r'.*[？?]$',  # 以问号结尾
        r'^能不能',    # 能不能...
        r'^会不会',    # 会不会...
        r'^要不要',    # 要不要...
        r'^是不是',    # 是不是...
        r'^为什么',    # 为什么...
        r'^怎么办',    # 怎么办...
        r'^怎么[怎做]', # 怎么+动词
        r'^如何',      # 如何...
        r'^能不能',    # 能不能...
        r'^会不会',    # 会不会...
        r'^有多少',    # 有多少...
        r'^谁的',      # 谁的...
        r'^哪个',      # 哪个...
        r'^哪里',      # 哪里...
        r'^谁在',      # 谁在...
    ]

    def is_question_sentence(self, title: str) -> bool:
        """
        检测标题是否以问题句开头

        Args:
            title: 选题标题

        Returns:
            bool: True=问题句，False=非问题句
        """
        if not title:
            return False

        import re
        title = title.strip()

        for pattern in self.QUESTION_PATTERNS:
            if re.match(pattern, title):
                return True

        return False

    def _mark_question_sentence(self, topics: list) -> list:
        """
        为选题列表添加问题句标识

        Args:
            topics: 选题列表

        Returns:
            list: 带 is_question 标记的选题列表
        """
        for topic in topics:
            title = topic.get('title', '')
            topic['is_question'] = self.is_question_sentence(title)

        return topics

    def generate_topics(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portraits: list,
        problem_keywords: list,
        is_premium: bool = False,
        skill_mode: bool = False,
        topic_type: str = None,
        topic_type_name: str = None
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
            skill_mode: 是否使用Skill模式（输出增强字段）
            topic_type: 选题类型键（如 problem_diagnosis, solution 等）
            topic_type_name: 选题类型名称

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
                is_premium=is_premium,
                skill_mode=skill_mode,
                topic_type=topic_type,
                topic_type_name=topic_type_name
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

            # 添加问题句标识
            topics = self._mark_question_sentence(topics)

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
        is_premium: bool,
        skill_mode: bool = False,
        topic_type: str = None,
        topic_type_name: str = None
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

        # Skill模式额外字段
        skill_mode_req = ""
        skill_fields_block = ""
        if skill_mode:
            skill_mode_req = '6. Skill模式：每个选题包含core_value（核心卖点）、scene_options（场景选项）、content_type（内容类型）'
            skill_fields_block = '''
    "core_value": "核心卖点/观点（一句话概括选题能提供的核心价值）",
    "scene_options": [{"id": "A", "label": "场景A描述"}, {"id": "B", "label": "场景B描述"}],
    "content_type": "图文/长文/短视频"'''

        # 选题类型约束
        type_constraint = ""
        if topic_type and topic_type_name:
            type_constraint = f"""
## 选题类型约束【重要】
你必须生成 **"{topic_type_name}"** 类型的选题。

【{topic_type_name}选题特点】
"""

            # 根据类型添加特点描述
            type_features = {
                'problem_diagnosis': """- 挖掘用户痛点和问题
- 标题包含痛点关键词，能引发共鸣
- 内容方向：问题诊断、痛点分析、需求挖掘
- 典型标题格式："XX问题怎么办？"、"XX的XX症状你中招了吗？\"""",
                'solution': """- 提供具体的解决方案和实用建议
- 标题突出价值和效果
- 内容方向：方法步骤、实用技巧、解决方案
- 典型标题格式："XX的正确方法"、"教你XX招搞定XX\"""",
                'case_share': """- 分享真实案例和故事
- 标题具有故事性和吸引力
- 内容方向：客户案例、亲身经历、成功故事
- 典型标题格式："XX客户的XX故事"、"我用XX方法帮客户XX\"""",
                'knowledge': """- 传授专业知识和科普
- 标题专业但易懂
- 内容方向：行业知识、产品知识、专业科普
- 典型标题格式："XX知识详解"、"关于XX你不知道的事\"""",
                'hot_topic': """- 蹭当前热点和趋势
- 标题紧跟时事热点
- 内容方向：热点解读、趋势分析、话题关联
- 典型标题格式："XX热点背后的XX"、"趁着XX说说XX\"""",
                'persona': """- 建立人设和信任
- 标题展现个人特色和价值观
- 内容方向：人设故事、价值观分享、观点输出
- 典型标题格式："我是怎么XX的"、"做XX这些年我的感悟\"""",
                'opinion': """- 表达立场和观点
- 标题有态度、有立场
- 内容方向：行业观点、深度评论、犀利点评
- 典型标题格式："XX的真相"、"别被XX骗了\"""",
                'pitfall': """- 帮助用户避坑避雷
- 标题包含警示元素
- 内容方向：常见误区、避坑指南、注意事项
- 典型标题格式："XX的XX坑千万别踩"、"XX最常见的XX误区\"""",
            }
            type_feature = type_features.get(topic_type, "")
            type_constraint += type_feature + "\n"
        else:
            type_constraint = """
## 选题类型参考
选题类型包含：
   - 问题诊断型：引发用户共鸣
   - 解决方案型：给出实用建议
   - 经验分享型：真实故事
   - 避坑指南型：帮助用户避雷
   - 知识科普型：传递专业知识
"""

        prompt = f"""你是一位资深的内容策划专家。请根据以下信息，生成10个精准的短视频/图文选题。

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

{type_constraint}

## 选题要求
1. 每个选题围绕一个具体问题，标题简洁有力
2. 标题包含问题关键词或痛点词
3. 符合当前时间节点特点
4. 每个选题说明推荐理由
{skill_mode_req}

## 输出格式（严格JSON）
```json
[
  {{
    "id": "1",
    "title": "选题标题（20字以内）",
    "type": "问题诊断/解决方案/经验分享/避坑指南/知识科普",
    "type_key": "pain_point/solution/emotional/pitfall/tutorial/knowledge",
    "target": "目标人群描述",
    "reason": "推荐理由（为什么选这个选题）"
    {skill_fields_block}
  }},
  ...共10个选题
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


class ContentTemperatureMixin:
    """
    内容温度增强 Mixin

    提供温度选题生成所需的方法：
    1. 人设视角注入
    2. 三要素关键词注入
    3. 情绪词密度控制
    4. 温度选题Prompt构建
    """

    def __init__(self):
        self.word_library = temperature_word_library

    def generate_topics_with_temperature(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portraits: list,
        problem_keywords: list,
        persona_type: str = '陪伴者',
        target_elements: List[str] = None,
        is_premium: bool = False,
        skill_mode: bool = False,
        topic_type: str = None,
        topic_type_name: str = None
    ) -> dict:
        """
        生成带温度属性的选题

        Args:
            business_description: 业务描述
            business_range: 经营范围
            business_type: 业务类型
            portraits: 用户画像列表
            problem_keywords: 问题关键词列表
            persona_type: 人设类型（陪伴者/教导者/崇拜者/陪衬者/搞笑者）
            target_elements: 目标三要素（至少2个）
            is_premium: 是否付费用户
            skill_mode: Skill模式
            topic_type: 选题类型键
            topic_type_name: 选题类型名称

        Returns:
            dict: {
                "success": bool,
                "topics": list,  # 每项包含温度元数据
                "temperature_config": dict,  # 本次温度配置
                "error": str
            }
        """
        if target_elements is None:
            target_elements = ['有用', '有共鸣']

        try:
            # 构建温度Prompt
            prompt = self._build_temperature_topic_prompt(
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portraits=portraits,
                problem_keywords=problem_keywords,
                persona_type=persona_type,
                target_elements=target_elements,
                is_premium=is_premium,
                skill_mode=skill_mode,
                topic_type=topic_type,
                topic_type_name=topic_type_name
            )

            # 调用LLM生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容策划专家，擅长生成有温度、有情感共鸣的短视频/图文选题。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            topics = self._parse_topics_response(response)

            if not topics:
                return {
                    'success': False,
                    'error': '温度选题生成失败，请重试'
                }

            # 添加温度元数据
            topics = self._add_temperature_metadata(
                topics=topics,
                persona_type=persona_type,
                target_elements=target_elements
            )

            return {
                'success': True,
                'topics': topics,
                'temperature_config': {
                    'persona_type': persona_type,
                    'target_elements': target_elements
                }
            }

        except Exception as e:
            logger.error("[TopicGenerator] Temperature generate error: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def _build_temperature_topic_prompt(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portraits: list,
        problem_keywords: list,
        persona_type: str,
        target_elements: List[str],
        is_premium: bool,
        skill_mode: bool,
        topic_type: str,
        topic_type_name: str
    ) -> str:
        """构建带温度的选题Prompt"""

        # 构建用户画像描述
        portrait_descriptions = self._build_portrait_descriptions(portraits)
        keyword_text = ', '.join(problem_keywords[:10]) if problem_keywords else ''

        # 获取当前时间信息
        current_season = self._get_current_season()
        current_month = datetime.now().month

        # 获取人设词库
        persona_keywords = self.word_library.get_persona_keywords(persona_type)
        persona_angles = self.word_library.get_persona_angles(persona_type)

        # 获取三要素词库
        elements_context = self._build_elements_context(target_elements)

        # 人设角度选择
        persona_angle = random.choice(persona_angles) if persona_angles else ""

        # 温度约束
        temperature_constraint = f"""
## 【温度约束】人设视角与三要素
你必须以【{persona_type}】的人设视角来构思选题。

【{persona_type}人设特点】
- 关键词：{', '.join(persona_keywords[:5])}
- 人设角度：{persona_angle}
- 语气特点：{self._get_persona_tone_desc(persona_type)}

【目标三要素】（至少体现2个）
{elements_context}

【情绪词密度】每个选题标题或副标题中，至少包含1个情绪词
情绪词参考：{', '.join(self.word_library.HIGH_EMOTION[:10])}
"""

        # Skill模式额外字段
        skill_mode_req = ""
        skill_fields_block = ""
        if skill_mode:
            skill_mode_req = '7. Skill模式：每个选题包含core_value（核心卖点）、scene_options（场景选项）、content_type（内容类型）'
            skill_fields_block = '''
    "core_value": "核心卖点/观点（一句话概括选题能提供的核心价值）",
    "scene_options": [{"id": "A", "label": "场景A描述"}, {"id": "B", "label": "场景B描述"}],
    "content_type": "图文/长文/短视频"'''

        prompt = f"""你是一位资深的内容策划专家。请根据以下信息，生成10个有温度、有情感共鸣的短视频/图文选题。

## 业务信息
- 业务描述：{business_description}
- 经营范围：{'本地服务' if business_range == 'local' else '跨区域服务'}
- 业务类型：{business_type}

## 目标用户画像
{portrait_descriptions or '暂无详细画像信息'}

## 问题关键词
{keyword_text or '暂无关键词信息'}

## 当前时间
- 季节：{current_season}（{current_month}月）
- 选题需考虑季节特性

{temperature_constraint}

## 选题要求
1. 每个选题围绕一个具体问题，标题简洁有力（20字以内）
2. 标题必须包含情绪词，引发用户共鸣
3. 符合【{persona_type}】人设的视角和语气
4. 体现目标三要素：{', '.join(target_elements)}
5. 每个选题说明推荐理由和温度亮点
{skill_mode_req}

## 输出格式（严格JSON）
```json
[
  {{
    "id": "1",
    "title": "选题标题（20字以内，必须包含情绪词）",
    "subtitle": "副标题/补充（可选，用于增强温度感）",
    "type": "问题诊断/解决方案/经验分享/避坑指南/知识科普",
    "type_key": "pain_point/solution/emotional/pitfall/tutorial/knowledge",
    "target": "目标人群描述",
    "reason": "推荐理由",
    "temperature_highlight": "温度亮点说明（为什么这个选题有温度）"
    {skill_fields_block}
  }},
  ...共10个选题
]
```
请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _build_elements_context(self, target_elements: List[str]) -> str:
        """构建三要素词库上下文"""
        context_parts = []
        for element in target_elements:
            element_words = self.word_library.get_element_words(element)
            if element_words:
                patterns = ', '.join(element_words.get('patterns', [])[:5])
                emotions = ', '.join(element_words.get('emotions', [])[:3])
                context_parts.append(f"- {element}：关键词{patterns}，情感价值{emotions}")
        return '\n'.join(context_parts) if context_parts else "- 有用：干货分享 | 有共鸣：情感连接"

    def _get_persona_tone_desc(self, persona_type: str) -> str:
        """获取人设语气描述"""
        tone_map = {
            '陪伴者': '温暖、理解、共情的口吻，像朋友间的倾诉',
            '教导者': '专业、权威但易懂，像经验丰富的导师',
            '崇拜者': '热情、激动、强烈推荐，像种草达人',
            '陪衬者': '自嘲、低姿态，像分享踩坑经历的朋友',
            '搞笑者': '幽默、反转、娱乐，像段子手'
        }
        return tone_map.get(persona_type, '温暖友好的口吻')

    def _add_temperature_metadata(
        self,
        topics: list,
        persona_type: str,
        target_elements: List[str]
    ) -> list:
        """为选题添加温度元数据"""
        for topic in topics:
            # 人设类型
            topic['persona_type'] = persona_type

            # 三要素组合
            topic['target_elements'] = target_elements

            # 推荐情绪词（从词库随机选取）
            emotion_words = random.sample(
                self.word_library.HIGH_EMOTION + self.word_library.MEDIUM_EMOTION,
                min(3, len(self.word_library.MEDIUM_EMOTION))
            )
            topic['recommended_emotion_words'] = emotion_words

            # 推荐人设角度
            persona_angles = self.word_library.get_persona_angles(persona_type)
            topic['persona_angle_hint'] = random.choice(persona_angles) if persona_angles else ""

            # 温度标签
            topic['temperature_tags'] = {
                'persona': persona_type,
                'elements': target_elements,
                'emotion_level': 'high' if '有趣' in target_elements else 'medium'
            }

        return topics

    def build_temperature_topic_context(
        self,
        persona_type: str,
        target_elements: List[str],
        intensity: str = 'high'
    ) -> str:
        """构建温度选题上下文（供外部调用）"""
        return self.word_library.build_temperature_prompt_context(
            persona_type=persona_type,
            target_elements=target_elements,
            intensity=intensity
        )


class TemperatureTopicGenerator(TopicGenerator, ContentTemperatureMixin):
    """
    温度增强选题生成器

    继承 TopicGenerator 的所有功能，并增加温度相关能力
    """

    def __init__(self):
        TopicGenerator.__init__(self)
        ContentTemperatureMixin.__init__(self)

    def generate_topics(
        self,
        business_description: str,
        business_range: str,
        business_type: str,
        portraits: list,
        problem_keywords: list,
        is_premium: bool = False,
        skill_mode: bool = False,
        topic_type: str = None,
        topic_type_name: str = None,
        # ── 温度相关参数 ──
        enable_temperature: bool = False,
        persona_type: str = '陪伴者',
        target_elements: list = None
    ) -> dict:
        """
        生成选题（支持温度增强）

        Args:
            enable_temperature: 是否启用温度增强
            persona_type: 人设类型
            target_elements: 三要素组合
        """
        if enable_temperature:
            return self.generate_topics_with_temperature(
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portraits=portraits,
                problem_keywords=problem_keywords,
                persona_type=persona_type,
                target_elements=target_elements or ['有用', '有共鸣'],
                is_premium=is_premium,
                skill_mode=skill_mode,
                topic_type=topic_type,
                topic_type_name=topic_type_name
            )
        else:
            # 使用原有逻辑
            return TopicGenerator.generate_topics(
                self,
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portraits=portraits,
                problem_keywords=problem_keywords,
                is_premium=is_premium,
                skill_mode=skill_mode,
                topic_type=topic_type,
                topic_type_name=topic_type_name
            )


# 全局实例
topic_generator = TopicGenerator()
temperature_topic_generator = TemperatureTopicGenerator()
