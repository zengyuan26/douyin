"""
topic_library_generator v3.1

优化版：复用超级定位已有的选题库数据

新增内容计划功能（基于已有选题库）：
- H-V-F 三段论标题生成
- 金字塔标签法 L1-L3
- 四维设计系统（情绪动线+版式）

6步执行流程（优化后）：
- step_1: 读取现有选题库（复用已有数据，不再重复生成）
- step_2: 标题生成（H-V-F模型）
- step_3: 标签生成（金字塔标签）
- step_4: 情绪动线生成
- step_5: 内容组装（更新extra_data）
- step_6: 最终汇总
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class TopicLibraryGeneratorV3:
    """
    选题库生成器 v3.1

    复用超级定位已有的选题库数据，仅生成内容计划
    """

    # =============================================================================
    # 静态配置
    # =============================================================================

    # 五段式阶段定义
    STAGE_CONFIG = {
        'audience': {'name': '受众锁定', 'ratio': 0.15},
        'pain': {'name': '痛点放大', 'ratio': 0.25},
        'compare': {'name': '方案对比', 'ratio': 0.30},
        'vision': {'name': '愿景勾画', 'ratio': 0.15},
        'hesitation': {'name': '顾虑消除', 'ratio': 0.15},
    }

    # 内容类型配置
    CONTENT_TYPE_CONFIG = {
        'graphic': {
            'name': '图文',
            'emotional_curve': ['期待', '焦虑', '专注', '坚定', '确信', '温暖', '信任'],
            'layouts': ['billboard', 'problem-solver', 'matrix', 'matrix', 'matrix', 'trust-builder', 'trust-builder'],
        },
        'long_text': {
            'name': '长文',
            'emotional_curve': ['共情痛点', '问题分析', '方案拆解', '高潮分享', '总结升华'],
        },
        'short_video': {
            'name': '短视频',
            'emotional_curve': {
                '0_3s': '期待/好奇',
                '3_10s': '焦虑/专注',
                '10_20s': '坚定/确信',
                '20_30s': '温暖/信任'
            },
            'duration': 30,
        }
    }

    # 情绪动线配置
    EMOTION_CURVE_CONFIG = {
        'p1': {'emotion': '期待/好奇', 'ratio': 0.15, 'goal': '吸引注意'},
        'p2': {'emotion': '焦虑/担忧', 'ratio': 0.20, 'goal': '产生共鸣'},
        'p3': {'emotion': '专注/思考', 'ratio': 0.25, 'goal': '建立信任'},
        'p4': {'emotion': '坚定/信任', 'ratio': 0.20, 'goal': '认可价值'},
        'p5': {'emotion': '温暖/满足', 'ratio': 0.20, 'goal': '引导行动'},
    }

    # =============================================================================
    # 主入口
    # =============================================================================

    def __init__(self):
        self.llm = get_llm_service()

    def generate_content_plan(
        self,
        topic_library: List[Dict],
        business_description: str = '',
        industry: str = '',
        content_types: List[str] = None,
    ) -> Dict:
        """
        生成内容计划（复用现有选题库）

        Args:
            topic_library: 现有选题库列表（来自 portrait.topic_library['topics']）
            business_description: 业务描述
            industry: 行业
            content_types: 内容类型列表 ['graphic', 'long_text', 'short_video']

        Returns:
            {
                'success': bool,
                'topics_with_plan': [
                    {
                        'id': '选题ID',
                        'title': '选题标题',
                        'content_plan': {
                            'hvf_title': {...},
                            'pyramid_tags': {...},
                            'emotion_curve': {...},
                            'layout': '...'
                        }
                    }
                ],
                'summary': {...}
            }
        """
        try:
            if not topic_library:
                return {'success': False, 'error': '选题库为空'}

            content_types = content_types or ['graphic']

            # 限制处理数量（避免token超限）
            topics_to_process = topic_library[:50]

            # 生成内容计划
            hvf_result = self._generate_hvf_titles(topics_to_process, business_description)
            tags_result = self._generate_pyramid_tags(topics_to_process, industry)
            emotion_result = self._generate_emotion_curves(topics_to_process)

            # 组装结果
            topics_with_plan = self._assemble_content_plans(
                topics=topics_to_process,
                hvf_titles=hvf_result.get('title_options', []),
                pyramid_tags=tags_result.get('tag_options', []),
                emotion_curves=emotion_result.get('curve_options', []),
                content_types=content_types
            )

            return {
                'success': True,
                'topics_with_plan': topics_with_plan,
                'summary': {
                    'total_count': len(topics_with_plan),
                    'by_stage': self._count_by_stage(topics_with_plan),
                    'by_priority': self._count_by_priority(topics_with_plan),
                    'by_content_type': self._count_by_content_type(topics_with_plan),
                }
            }

        except Exception as e:
            logger.exception("[TopicLibraryV3] Error: %s", e)
            return {'success': False, 'error': str(e)}

    # =============================================================================
    # Step 2: H-V-F 标题生成
    # =============================================================================

    def _generate_hvf_titles(
        self,
        topics: List[Dict],
        business_description: str,
    ) -> Dict:
        """为选题生成H-V-F三段论标题"""

        if not topics:
            return {'title_options': []}

        # 构建选题列表
        topic_list = []
        for i, topic in enumerate(topics[:20]):  # 限制20个
            topic_list.append({
                'index': i + 1,
                'title': topic.get('title', ''),
                'type': topic.get('type', ''),
                'keywords': topic.get('keywords', [])[:5],
            })

        prompt = f"""
## H-V-F 三段论标题生成

你是内容策划专家。请为以下选题生成H-V-F三段论标题。

### H-V-F 模型说明
- **H (Hook)**：钩子，解决"与我有关"
  - 身份标签：新手妈妈/宝爸/老板/学生
  - 痛点触发：拉肚子/不懂/不会/太贵
  - 情绪词：焦虑/担心/崩溃/头大

- **V (Value)**：价值，解决"看完能得什么"
  - 具体结果：孩子不哭了/省了500块
  - 背书力量：主任医生/10年经验/10000+案例

- **F (Format)**：形式，解决"看起来累不累"
  - 量化词：3步/5个/90%
  - 简单化词：一张图/一句话/轻松学会

### 五种标题模式
A 干货攻略型：[Subject] + [Pain Point] + [Quantity] + 效果词
B 情绪共鸣型：[Status] + [Subject] + [Pain Point] + [Emotion]
C 权威型：[Subject] + [Action] + [Value] + [Backing]
D 反常识型：[Misconception] + 反转 + [Solution]
E 数字悬念型：[Number] + [Common Mistake] + [Promise]

### 选题列表
{json.dumps(topic_list, ensure_ascii=False, indent=2)}

### 业务背景
{business_description or '通用业务'}

请为每个选题生成3个标题候选，输出JSON格式：
{{
    "title_options": [
        {{
            "topic_title": "选题原标题",
            "titles": [
                {{
                    "title": "完整标题",
                    "pattern": "A/B/C/D/E",
                    "hvf": {{
                        "hook": "钩子部分",
                        "value": "价值部分", 
                        "format": "形式部分"
                    }},
                    "recommended": true/false
                }}
            ]
        }}
    ]
}}
"""

        messages = [
            {"role": "system", "content": "你是资深内容策划专家，擅长生成高点击率标题。必须严格按照JSON格式输出。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm.chat(messages)
            result = self._parse_json_response(response)
            return result if result else {'title_options': []}
        except Exception as e:
            logger.warning("[H-V-F] LLM调用失败: %s", e)
            return {'title_options': []}

    # =============================================================================
    # Step 3: 金字塔标签生成
    # =============================================================================

    def _generate_pyramid_tags(
        self,
        topics: List[Dict],
        industry: str,
    ) -> Dict:
        """生成金字塔标签"""

        if not topics:
            return {'tag_options': []}

        # 提取所有关键词
        all_keywords = set()
        for topic in topics:
            if topic.get('keywords'):
                for kw in topic['keywords'][:10]:
                    all_keywords.add(kw)
            if topic.get('title'):
                # 从标题中提取词
                words = re.findall(r'[\u4e00-\u9fa5]{2,}', topic['title'])
                all_keywords.update(words[:5])

        keywords_list = list(all_keywords)[:30]

        prompt = f"""
## 金字塔标签法生成

请为以下选题生成金字塔标签体系。

### 金字塔结构
- **L1（顶层）**：核心公域流量，大类目标签，如 #育儿/#美食/#教育
- **L2（中层）**：垂直细分流量，精准需求标签，如 #宝宝拉肚子/#乳糖不耐受
- **L3（底层）**：长尾/场景流量，搜索入口标签，如 #宝宝拉肚子怎么调理/#0-3岁宝宝辅食

### 标签规则
- L1：取1-2个（行业大类）
- L2：取2-3个（细分领域+痛点）
- L3：取1-2个（场景词+搜索词）
- 总计：5-7个标签

### 行业
{industry or '通用行业'}

### 关键词库
{', '.join(keywords_list)}

### 选题列表
{json.dumps([{'title': t.get('title', ''), 'type': t.get('type', '')} for t in topics[:20]], ensure_ascii=False, indent=2)}

请输出JSON格式：
{{
    "tag_options": [
        {{
            "topic_title": "选题标题",
            "l1_tags": ["L1标签1", "L1标签2"],
            "l2_tags": ["L2标签1", "L2标签2", "L2标签3"],
            "l3_tags": ["L3标签1", "L3标签2"],
            "all_tags": ["#标签1", "#标签2", "#标签3", "#标签4", "#标签5", "#标签6", "#标签7"]
        }}
    ]
}}
"""

        messages = [
            {"role": "system", "content": "你是标签优化专家，擅长生成精准的内容标签。必须严格按照JSON格式输出。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm.chat(messages)
            result = self._parse_json_response(response)
            return result if result else {'tag_options': []}
        except Exception as e:
            logger.warning("[PyramidTags] LLM调用失败: %s", e)
            return {'tag_options': []}

    # =============================================================================
    # Step 4: 情绪动线生成
    # =============================================================================

    def _generate_emotion_curves(
        self,
        topics: List[Dict],
    ) -> Dict:
        """生成情绪动线"""

        if not topics:
            return {'curve_options': []}

        prompt = f"""
## 情绪动线规划

请为以下选题规划情绪动线。

### 五段式情绪曲线
- **P1 期待/好奇** (15%)：吸引注意，制造悬念
- **P2 焦虑/担忧** (20%)：放大痛点，引发共鸣
- **P3 专注/思考** (25%)：分析问题，建立信任
- **P4 坚定/信任** (20%)：展示方案，认可价值
- **P5 温暖/满足** (20%)：引导行动，情感升华

### 内容版式建议
- 图文版式：billboard（封面）/ problem-solver（痛点）/ matrix（矩阵）/ trust-builder（信任）
- 视觉风格：大场景/特写/对比图/数据图

### 选题列表
{json.dumps([{'title': t.get('title', ''), 'type': t.get('type', ''), 'stage': t.get('stage', '')} for t in topics[:20]], ensure_ascii=False, indent=2)}

请输出JSON格式：
{{
    "curve_options": [
        {{
            "topic_title": "选题标题",
            "emotion_curve": {{
                "p1": {{"emotion": "期待/好奇", "keywords": ["关键词1"], "goal": "吸引注意"}},
                "p2": {{"emotion": "焦虑/担忧", "keywords": ["关键词2"], "goal": "引发共鸣"}},
                "p3": {{"emotion": "专注/思考", "keywords": ["关键词3"], "goal": "建立信任"}},
                "p4": {{"emotion": "坚定/信任", "keywords": ["关键词4"], "goal": "认可价值"}},
                "p5": {{"emotion": "温暖/满足", "keywords": ["关键词5"], "goal": "引导行动"}}
            }},
            "recommended_layouts": ["billboard", "problem-solver", "matrix", "trust-builder"],
            "visual_hints": {{
                "cover": "大场景/人物特写",
                "body": "数据图/对比图/步骤图",
                "ending": "温暖场景/引导截图"
            }}
        }}
    ]
}}
"""

        messages = [
            {"role": "system", "content": "你是情绪策划专家，擅长规划内容情绪动线。必须严格按照JSON格式输出。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm.chat(messages)
            result = self._parse_json_response(response)
            return result if result else {'curve_options': []}
        except Exception as e:
            logger.warning("[EmotionCurve] LLM调用失败: %s", e)
            return {'curve_options': []}

    # =============================================================================
    # Step 5: 组装内容计划
    # =============================================================================

    def _assemble_content_plans(
        self,
        topics: List[Dict],
        hvf_titles: List[Dict],
        pyramid_tags: List[Dict],
        emotion_curves: List[Dict],
        content_types: List[str],
    ) -> List[Dict]:
        """组装完整的内容计划"""

        # 建立索引映射
        hvf_map = {item.get('topic_title'): item for item in hvf_titles}
        tags_map = {item.get('topic_title'): item for item in pyramid_tags}
        emotion_map = {item.get('topic_title'): item for item in emotion_curves}

        result = []
        for topic in topics:
            title = topic.get('title', '')

            # 匹配H-V-F
            hvf_item = hvf_map.get(title, {})
            recommended_title = None
            if hvf_item.get('titles'):
                for t in hvf_item['titles']:
                    if t.get('recommended'):
                        recommended_title = t
                        break
                if not recommended_title and hvf_item['titles']:
                    recommended_title = hvf_item['titles'][0]

            # 匹配标签
            tags_item = tags_map.get(title, {})

            # 匹配情绪动线
            emotion_item = emotion_map.get(title, {})

            # 选择内容版式
            content_type = content_types[0] if content_types else 'graphic'
            layouts = self.CONTENT_TYPE_CONFIG.get(content_type, {}).get('layouts', ['billboard', 'problem-solver'])

            # 构建内容计划
            content_plan = {
                'hvf_title': {
                    'recommended': recommended_title.get('title') if recommended_title else None,
                    'all_options': hvf_item.get('titles', []),
                    'pattern': recommended_title.get('pattern') if recommended_title else None,
                    'hvf_detail': recommended_title.get('hvf') if recommended_title else None,
                } if recommended_title else None,
                'pyramid_tags': {
                    'l1': tags_item.get('l1_tags', []),
                    'l2': tags_item.get('l2_tags', []),
                    'l3': tags_item.get('l3_tags', []),
                    'all': tags_item.get('all_tags', []),
                } if tags_item else None,
                'emotion_curve': emotion_item.get('emotion_curve') if emotion_item else None,
                'recommended_layouts': emotion_item.get('recommended_layouts', layouts) if emotion_item else layouts,
                'visual_hints': emotion_item.get('visual_hints') if emotion_item else None,
                'content_type': content_type,
            }

            result.append({
                'id': topic.get('id'),
                'title': title,
                'type': topic.get('type'),
                'priority': topic.get('priority'),
                'stage': topic.get('stage'),
                'keywords': topic.get('keywords', []),
                'scene_options': topic.get('scene_options', []),
                'content_plan': content_plan,
            })

        return result

    # =============================================================================
    # 统计函数
    # =============================================================================

    def _count_by_stage(self, topics: List[Dict]) -> Dict:
        """按阶段统计"""
        counts = {}
        for t in topics:
            stage = t.get('stage', 'unknown')
            counts[stage] = counts.get(stage, 0) + 1
        return counts

    def _count_by_priority(self, topics: List[Dict]) -> Dict:
        """按优先级统计"""
        counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}
        for t in topics:
            priority = t.get('priority', 'P2')
            if priority in counts:
                counts[priority] += 1
        return counts

    def _count_by_content_type(self, topics: List[Dict]) -> Dict:
        """按内容类型统计"""
        counts = {}
        for t in topics:
            ct = t.get('content_plan', {}).get('content_type', 'graphic')
            counts[ct] = counts.get(ct, 0) + 1
        return counts

    # =============================================================================
    # 工具函数
    # =============================================================================

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """解析LLM返回的JSON响应"""
        if not response:
            return None

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试提取代码块
        try:
            import re
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass

        # 尝试提取JSON对象
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass

        return None

    # =============================================================================
    # 异步步骤处理方法（供 content_plan_task_executor 调用）
    # =============================================================================

    async def handle_step_1(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_1: 读取现有选题库

        从输入数据中获取已有选题库，不再重复生成
        """
        logger.info(f"[handle_step_1] input_data keys: {list(input_data.keys()) if input_data else 'None'}, topics count: {len(input_data.get('topics', [])) if input_data else 0}")

        # 优先从 input_data 获取选题库
        topics = input_data.get('topics', [])

        # 如果 input_data 没有，尝试从 portrait 相关的字段获取
        if not topics:
            portrait = input_data.get('portrait', {})
            topic_library = portrait.get('topic_library', {}) if isinstance(portrait, dict) else {}
            topics = topic_library.get('topics', [])

        logger.info(f"[handle_step_1] 获取到 topics 数量: {len(topics) if topics else 0}")

        if not topics:
            return {
                'topics': [],
                'message': '选题库为空'
            }

        return {
            'topics': topics,
            'count': len(topics),
            'industry': input_data.get('industry', ''),
            'business_description': input_data.get('business_description', ''),
        }

    async def handle_step_2(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_2: H-V-F 标题生成
        """
        step_1_result = deps_results.get('step_1', {})
        topics = step_1_result.get('topics', [])
        business_description = step_1_result.get('business_description', '')

        logger.info(f"[handle_step_2] step_1_result={step_1_result}, topics count={len(topics)}")

        if not topics:
            return {'title_options': []}

        # 复用同步方法
        result = self._generate_hvf_titles(topics, business_description)
        logger.info(f"[handle_step_2] 生成结果 title_options count={len(result.get('title_options', []))}")
        return result

    async def handle_step_3(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_3: 金字塔标签生成
        """
        step_1_result = deps_results.get('step_1', {})
        topics = step_1_result.get('topics', [])
        industry = step_1_result.get('industry', '')

        if not topics:
            return {'tag_options': []}

        # 复用同步方法
        result = self._generate_pyramid_tags(topics, industry)
        return result

    async def handle_step_4(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_4: 情绪动线生成
        """
        step_1_result = deps_results.get('step_1', {})
        topics = step_1_result.get('topics', [])

        if not topics:
            return {'curve_options': []}

        # 复用同步方法
        result = self._generate_emotion_curves(topics)
        return result

    async def handle_step_5(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_5: 内容组装
        """
        step_1_result = deps_results.get('step_1', {})
        step_2_result = deps_results.get('step_2', {})
        step_3_result = deps_results.get('step_3', {})
        step_4_result = deps_results.get('step_4', {})

        topics = step_1_result.get('topics', [])
        content_types = input_data.get('content_types', ['graphic'])

        logger.info(f"[handle_step_5] topics={len(topics)}, step_2={len(step_2_result.get('title_options', []))}, step_3={len(step_3_result.get('tag_options', []))}")

        if not topics:
            return {'topics_with_plan': [], 'assembled': True}

        # 组装内容计划
        topics_with_plan = self._assemble_content_plans(
            topics=topics,
            hvf_titles=step_2_result.get('title_options', []),
            pyramid_tags=step_3_result.get('tag_options', []),
            emotion_curves=step_4_result.get('curve_options', []),
            content_types=content_types
        )

        logger.info(f"[handle_step_5] 组装完成 topics_with_plan count={len(topics_with_plan)}")
        return {
            'topics_with_plan': topics_with_plan,
            'assembled': True
        }

    async def handle_step_6(self, context, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
        """
        step_6: 最终汇总
        """
        step_5_result = deps_results.get('step_5', {})
        topics_with_plan = step_5_result.get('topics_with_plan', [])

        # 生成统计
        summary = {
            'total_count': len(topics_with_plan),
            'by_stage': self._count_by_stage(topics_with_plan),
            'by_priority': self._count_by_priority(topics_with_plan),
            'by_content_type': self._count_by_content_type(topics_with_plan),
        }

        return {
            'summary': summary,
            'topics_with_plan': topics_with_plan,
            'completed': True
        }
