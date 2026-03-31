"""
画像专属选题库生成服务

功能：
1. 读取模板配置，生成专属选题库
2. 基于关键词库 + 实时上下文
3. 持久化到 saved_portraits.topic_library
4. 支持实时刷新 + 配额检查
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models.public_models import SavedPortrait, db
from services.template_config_service import template_config_service
from services.llm import get_llm_service


class TopicLibraryGenerator:
    """
    选题库生成器

    复用 geo-seo skill 中的选题库模板逻辑：
    - 10大选题来源（评论区挖痛点、颠覆常识、搜索框挖需求等）
    - 选题优先级矩阵（P0-P3）
    - B/C端区分
    """

    # 选题分类（与 geo-seo 保持一致）
    TOPIC_TYPES = [
        {'name': '问题解决类', 'key': 'problem', 'source': '评论区挖痛点',
         'desc': '用户真实问题，高共鸣', 'priority': 'P0'},
        {'name': '认知颠覆类', 'key': 'rethink', 'source': '颠覆常识',
         'desc': '打破认知，易传播', 'priority': 'P1'},
        {'name': '知识教程类', 'key': 'tutorial', 'source': '搜索框挖需求',
         'desc': '主动搜索，精准流量', 'priority': 'P1'},
        {'name': '经验分享类', 'key': 'experience', 'source': '传统经验',
         'desc': '差异化，老一辈智慧', 'priority': 'P2'},
        {'name': '季节营销类', 'key': 'seasonal', 'source': '季节节点',
         'desc': '时效性强', 'priority': 'P2'},
        {'name': '节日营销类', 'key': 'festival', 'source': '节日方法论',
         'desc': '节日刚需，高转化', 'priority': 'P0'},
        {'name': '节气养生类', 'key': 'solar_term', 'source': '节气方法论',
         'desc': '传统智慧，持续输出', 'priority': 'P2'},
        {'name': '场景细分类', 'key': 'scene', 'source': '场景关键词',
         'desc': '精准人群，高转化', 'priority': 'P1'},
        {'name': '地域精准类', 'key': 'region', 'source': '流量关键词',
         'desc': '本地流量，精准转化', 'priority': 'P2'},
        {'name': '情感故事类', 'key': 'emotional', 'source': '情感共鸣词',
         'desc': '易引发转发', 'priority': 'P3'},
    ]

    def __init__(self):
        self.llm = get_llm_service()

    def generate(
        self,
        portrait_data: Dict,
        business_info: Dict,
        keyword_library: Dict = None,
        plan_type: str = 'professional',
        use_template: bool = True,
        topic_count: int = 20,
    ) -> Dict[str, Any]:
        """
        生成选题库

        Args:
            portrait_data: 画像数据
            business_info: 业务信息
            keyword_library: 关键词库（可选，用于精准选题）
            plan_type: 套餐类型
            use_template: 是否使用模板配置
            topic_count: 选题数量

        Returns:
            {
                'success': bool,
                'topic_library': {
                    'topics': [...],  # 选题列表
                    'by_type': {...},  # 按类型分组
                    'priorities': {...},  # 优先级分布
                },
                'tokens_used': int,
            }
        """
        try:
            # 获取实时上下文
            realtime = template_config_service.get_realtime_context()

            # 构建变量上下文
            context = self._build_context(portrait_data, business_info, keyword_library, realtime)

            # 构建 Prompt
            if use_template:
                template = template_config_service.get_template('topic')
                if template:
                    prompt = template_config_service.replace_variables(
                        template['template_content'], context
                    )
                else:
                    prompt = self._build_default_prompt(context, keyword_library, topic_count)
            else:
                prompt = self._build_default_prompt(context, keyword_library, topic_count)

            # 调用 LLM
            system_msg = (
                "你是一位抖音爆款选题策划专家，精通本地商家内容营销。"
                "必须严格按照JSON格式输出，选题必须有差异化、能引发共鸣。"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            result = self._parse_response(response)

            return {
                'success': True,
                'topic_library': result,
                'tokens_used': self._estimate_tokens(prompt, response),
                '_meta': {
                    'plan_type': plan_type,
                    'realtime': realtime,
                    'used_template': use_template,
                    'based_on_keywords': bool(keyword_library),
                }
            }

        except Exception as e:
            print(f"[TopicLibraryGenerator] Error: {e}")
            return {'success': False, 'error': str(e)}

    def save_to_portrait(
        self,
        portrait_id: int,
        topic_library: Dict,
        user_id: int,
        plan_type: str = 'professional',
    ) -> bool:
        """保存选题库到画像记录"""
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return False

        ttl_hours = {
            'basic': 24,
            'professional': 168,
            'enterprise': 720,
        }.get(plan_type, 24)

        portrait.topic_library = topic_library
        portrait.topic_updated_at = datetime.utcnow()
        portrait.topic_update_count = (portrait.topic_update_count or 0) + 1
        portrait.topic_cache_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        db.session.commit()
        return True

    def get_from_portrait(self, portrait_id: int) -> Optional[Dict]:
        """从画像获取已保存的选题库"""
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return None

        if portrait.topic_library_expired:
            return None

        return portrait.topic_library

    def select_topics(
        self,
        topic_library: Dict,
        count: int = 5,
        topic_type: str = None,
        keyword_hint: str = None,
    ) -> List[Dict]:
        """
        从选题库中选择选题

        Args:
            topic_library: 选题库
            count: 选择数量
            topic_type: 指定类型
            keyword_hint: 关键词提示（用于筛选相关选题）

        Returns:
            选中的选题列表
        """
        topics = topic_library.get('topics', [])

        if not topics:
            return []

        # 按关键词过滤
        if keyword_hint and keyword_hint.strip():
            keyword = keyword_hint.strip().lower()
            topics = [
                t for t in topics
                if keyword in (t.get('title', '') + t.get('keywords', '')).lower()
            ]

        # 按类型筛选
        if topic_type:
            topics = [t for t in topics if t.get('type_key') == topic_type]

        # 按优先级排序
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2, 'P3': 3}
        topics = sorted(
            topics,
            key=lambda t: priority_order.get(t.get('priority', 'P3'), 3)
        )

        # 随机打乱同优先级
        random.shuffle(topics)

        return topics[:count]

    def _build_context(
        self,
        portrait_data: Dict,
        business_info: Dict,
        keyword_library: Dict = None,
        realtime: Dict = None,
    ) -> Dict:
        """构建模板变量上下文"""
        if realtime is None:
            realtime = {}

        # 从关键词库提取关键词
        keywords_text = ''
        if keyword_library:
            all_kw = []
            for cat in keyword_library.get('categories', []):
                all_kw.extend(cat.get('keywords', [])[:5])
            keywords_text = ', '.join(all_kw[:50])

        context = {
            # 画像
            '目标客户身份': portrait_data.get('identity', ''),
            '核心痛点': portrait_data.get('pain_point', ''),
            '核心顾虑': portrait_data.get('concern', ''),
            '使用场景': portrait_data.get('scenario', ''),

            # 业务
            '业务描述': business_info.get('business_description', ''),
            '行业': business_info.get('industry', ''),
            '产品': ', '.join(business_info.get('products', [])),
            '地域': business_info.get('region', ''),
            '目标客户': business_info.get('target_customer', ''),

            # 实时
            '当前季节': realtime.get('当前季节', ''),
            '月份名称': realtime.get('月份名称', ''),
            '季节消费特点': realtime.get('季节消费特点', ''),
            '月度热点前缀': realtime.get('月度热点前缀', ''),
            '当前节日': realtime.get('当前节日', '无'),
            '当前节气': realtime.get('当前节气', '无'),

            # 关键词
            '关键词库': keywords_text,
        }
        return context

    def _build_default_prompt(
        self,
        context: Dict,
        keyword_library: Dict = None,
        topic_count: int = 20,
    ) -> str:
        """构建默认提示词"""

        type_rules = '\n'.join([
            f"{i+1}. **{t['name']}**（来源：{t['source']}）：{t['desc']} 【{t['priority']}】"
            for i, t in enumerate(self.TOPIC_TYPES)
        ])

        return f"""你是一位抖音爆款选题策划专家。请为以下业务生成{topic_count}个精准选题。

## 业务信息
- 行业：{context['行业']}
- 业务描述：{context['业务描述']}
- 产品：{context['产品']}
- 地域：{context['地域']}
- 目标客户：{context['目标客户']}

## 目标用户画像
- 用户身份：{context['目标客户身份']}
- 核心痛点：{context['核心痛点']}
- 核心顾虑：{context['核心顾虑']}
- 使用场景：{context['使用场景']}

## 实时上下文
- 当前季节：{context['当前季节']}（{context['月份名称']}）
- 季节消费特点：{context['季节消费特点']}
- 月度热点：{context['月度热点前缀']}
- 当前节日：{context['当前节日']}
- 当前节气：{context['当前节气']}

## 关键词参考
{context['关键词库'] or '（无关键词库，将根据业务描述生成）'}

## 选题分类（必须覆盖多种类型）
{type_rules}

## 选题要求
1. 必须围绕用户真实痛点，差异化明显
2. 优先选择高优先级（P0/P1）选题
3. 融入季节、节日等实时因素
4. 每条选题包含：标题、类型、来源、关键词、推荐理由
5. 涵盖至少5种以上选题类型

## 输出格式（严格JSON，共{topic_count}条）
```json
{{
  "topics": [
    {{
      "title": "选题标题（戳心、≤20字）",
      "type_name": "问题解决类",
      "type_key": "problem",
      "source": "评论区挖痛点",
      "priority": "P0",
      "keywords": ["关联关键词1", "关联关键词2"],
      "reason": "推荐理由（为什么这条选题会火）",
      "publish_timing": "推荐发布时间",
      "content_hints": "内容创作提示"
    }},
    ...
  ],
  "by_type": {{
    "problem": 4,
    "rethink": 3,
    ...
  }},
  "priorities": {{
    "P0": 5,
    "P1": 8,
    "P2": 5,
    "P3": 2
  }}
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

    def _parse_response(self, response: str) -> Dict:
        """解析 LLM 返回"""
        import re
        import json
        
        try:
            # 尝试多种方式提取 JSON
            # 1. 尝试直接解析（去除 markdown 代码块）
            clean_response = response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            elif clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # 2. 尝试用双大括号匹配（因为 prompt 中用的是 {{}}）
            json_match = re.search(r'\{[\s\S]*\}', clean_response)
            if json_match:
                json_str = json_match.group(0)
                # 替换双大括号为单大括号
                json_str = json_str.replace('{{', '{').replace('}}', '}')
                result = json.loads(json_str)
                return self._validate_and_fill(result)
            
            # 3. 尝试直接解析清理后的字符串
            result = json.loads(clean_response)
            return self._validate_and_fill(result)
            
        except json.JSONDecodeError as e:
            print(f"[TopicLibraryGenerator] JSON解析失败: {e}")
            print(f"[TopicLibraryGenerator] 原始响应前200字符: {response[:200]}")
            return self._get_default_library()
        except Exception as e:
            print(f"[TopicLibraryGenerator] Parse error: {e}")
            return self._get_default_library()

    def _validate_and_fill(self, result: Dict) -> Dict:
        """验证并补充选题库"""
        default = self._get_default_library()

        if 'topics' not in result or not result['topics']:
            result['topics'] = default['topics']

        # 补充缺失字段
        for topic in result['topics']:
            if 'type_key' not in topic:
                topic['type_key'] = topic.get('type', 'unknown')
            if 'priority' not in topic:
                topic['priority'] = 'P2'

        if 'by_type' not in result:
            result['by_type'] = self._count_by_type(result['topics'])

        if 'priorities' not in result:
            result['priorities'] = self._count_by_priority(result['topics'])

        return result

    def _count_by_type(self, topics: List[Dict]) -> Dict:
        counts = {}
        for t in topics:
            key = t.get('type_key', 'unknown')
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _count_by_priority(self, topics: List[Dict]) -> Dict:
        counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0}
        for t in topics:
            p = t.get('priority', 'P2')
            if p in counts:
                counts[p] += 1
        return counts

    def _get_default_library(self) -> Dict:
        """获取默认选题库（当LLM生成失败时使用）"""
        return {
            'topics': [
                {
                    'title': '使用我们的服务，解决您的核心痛点',
                    'type_name': '问题解决类',
                    'type_key': 'problem',
                    'source': '评论区挖痛点',
                    'priority': 'P0',
                    'keywords': [],
                    'reason': '直击用户最关心的问题',
                    'publish_timing': '工作日午间',
                    'content_hints': '展示痛点场景 + 解决方案',
                },
                {
                    'title': '为什么选择我们而不是其他家',
                    'type_name': '对比类',
                    'type_key': 'compare',
                    'source': '用户决策路径',
                    'priority': 'P1',
                    'keywords': [],
                    'reason': '解答用户选择疑虑',
                    'publish_timing': '周末晚间',
                    'content_hints': '对比优势 + 真实案例',
                },
                {
                    'title': '客户案例：用了都说好',
                    'type_name': '案例类',
                    'type_key': 'case',
                    'source': '客户反馈',
                    'priority': 'P1',
                    'keywords': [],
                    'reason': '真实案例增强信任',
                    'publish_timing': '工作日下午',
                    'content_hints': '前后对比 + 用户评价',
                },
                {
                    'title': '您可能遇到的误区',
                    'type_name': '避坑类',
                    'type_key': 'warning',
                    'source': '常见问题',
                    'priority': 'P2',
                    'keywords': [],
                    'reason': '帮助用户避免损失',
                    'publish_timing': '工作日午间',
                    'content_hints': '误区场景 + 正确做法',
                },
                {
                    'title': '行业趋势与我们的优势',
                    'type_name': '行业洞察类',
                    'type_key': 'insight',
                    'source': '行业分析',
                    'priority': 'P2',
                    'keywords': [],
                    'reason': '展示专业深度',
                    'publish_timing': '周末上午',
                    'content_hints': '数据支撑 + 专业解读',
                },
            ],
            'by_type': {'problem': 1, 'compare': 1, 'case': 1, 'warning': 1, 'insight': 1},
            'priorities': {'P0': 1, 'P1': 2, 'P2': 2, 'P3': 0},
        }

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算 token 消耗"""
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
topic_library_generator = TopicLibraryGenerator()
