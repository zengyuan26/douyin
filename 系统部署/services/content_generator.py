"""
选题内容生成服务

基于选题，生成完整的图文内容
- 免费用户：2种基础结构
- 基础版：10种结构
- 专业版：15种结构
- 企业版：20种结构 + SEO优化 + 精准埋词
"""

import json
import re
from datetime import datetime
from services.llm import get_llm_service


class TopicContentGenerator:
    """选题内容生成器"""

    # 免费用户基础结构
    BASIC_STRUCTURES = [
        {
            'name': '痛点共鸣型',
            'slides': 5,
            'desc': '封面→痛点→分析→方案→品牌'
        },
        {
            'name': '疑问揭秘型',
            'slides': 5,
            'desc': '封面→疑问→揭秘→对比→引导'
        },
    ]

    # 基础版 10 种结构
    BASIC_10_STRUCTURES = [
        {'name': '痛点共鸣型', 'slides': 5, 'desc': '封面→痛点→分析→方案→品牌'},
        {'name': '疑问揭秘型', 'slides': 5, 'desc': '封面→疑问→揭秘→对比→引导'},
        {'name': '数字清单型', 'slides': 6, 'desc': '封面→数字概览→逐条展开→总结→品牌'},
        {'name': '对比冲击型', 'slides': 6, 'desc': '封面→错误做法→正确做法→对比表→方案→品牌'},
        {'name': '场景故事型', 'slides': 5, 'desc': '封面→场景描述→问题升级→解决方案→行动'},
        {'name': '经验总结型', 'slides': 6, 'desc': '封面→踩坑回顾→原因分析→避坑指南→推荐→品牌'},
        {'name': '知识科普型', 'slides': 5, 'desc': '封面→冷知识→原理说明→应用场景→品牌'},
        {'name': '产品评测型', 'slides': 6, 'desc': '封面→评测背景→维度展示→数据对比→结论→品牌'},
        {'name': '选购指南型', 'slides': 6, 'desc': '封面→选购痛点→关键指标→方案推荐→对比→品牌'},
        {'name': '避坑指南型', 'slides': 5, 'desc': '封面→常见误区→后果展示→正确做法→提醒→品牌'},
    ]

    # 专业版 15 种结构 = 基础 10 种 + 新增 5 种
    PROFESSIONAL_15_STRUCTURES = BASIC_10_STRUCTURES + [
        {'name': '时间节点型', 'slides': 7, 'desc': '封面→时间背景→阶段问题→对应方案→注意事项→时机选择→品牌'},
        {'name': '人群细分型', 'slides': 7, 'desc': '封面→人群A→人群B→人群C→各自痛点→各自方案→品牌'},
        {'name': '价格博弈型', 'slides': 6, 'desc': '封面→价格误区→定价逻辑→成本拆解→价值对比→品牌'},
        {'name': '替代方案型', 'slides': 6, 'desc': '封面→替代品问题→替代原理→效果对比→推荐方案→品牌'},
        {'name': '升级迭代型', 'slides': 7, 'desc': '封面→旧方案问题→升级思路→新方案亮点→对比→使用建议→品牌'},
    ]

    # 企业版 20 种结构 = 专业 15 种 + 新增 5 种
    ENTERPRISE_20_STRUCTURES = PROFESSIONAL_15_STRUCTURES + [
        {'name': '行业揭秘型', 'slides': 7, 'desc': '封面→行业潜规则→内幕揭秘→消费者误区→正确认知→品牌'},
        {'name': '数据说话型', 'slides': 7, 'desc': '封面→核心数据→数据解读→行业对比→趋势预判→品牌'},
        {'name': '场景矩阵型', 'slides': 8, 'desc': '封面→场景1→场景2→场景3→各自方案→场景选择建议→品牌'},
        {'name': '决策树型', 'slides': 7, 'desc': '封面→决策入口→分支A/B/C→各分支结论→通用建议→品牌'},
        {'name': '用户证言型', 'slides': 7, 'desc': '封面→用户痛点→真实故事→改变过程→使用效果→品牌'},
    ]

    # Token 消耗估算（参考 public_content_generator.py）
    TOKEN_ESTIMATE = {
        'free': {'prompt': 800, 'completion': 1200, 'total': 2000},
        'basic': {'prompt': 1200, 'completion': 2000, 'total': 3200},
        'professional': {'prompt': 1500, 'completion': 2800, 'total': 4300},
        'enterprise': {'prompt': 2000, 'completion': 3500, 'total': 5500},
    }

    def __init__(self):
        self.llm = get_llm_service()

    def generate_content(
        self,
        topic_id: str,
        topic_title: str,
        topic_type: str,
        business_description: str,
        business_range: str,
        business_type: str,
        portrait: dict,
        is_premium: bool = False,
        premium_plan: str = 'free'
    ) -> dict:
        """
        生成图文内容

        Args:
            topic_id: 选题ID
            topic_title: 选题标题
            topic_type: 选题类型
            business_description: 业务描述
            business_range: 经营范围
            business_type: 业务类型
            portrait: 用户画像
            is_premium: 是否付费用户
            premium_plan: 套餐类型 free/basic/professional/enterprise

        Returns:
            dict: {
                "success": bool,
                "content": {...},
                "tokens_used": int
            }
        """
        try:
            # 确定可用结构数量
            plan = premium_plan if premium_plan in ('free', 'basic', 'professional', 'enterprise') else 'free'
            structures = self._get_structures_for_plan(plan)
            structure_names = [s['name'] for s in structures]

            # 构建 Prompt
            prompt = self._build_content_prompt(
                topic_title=topic_title,
                topic_type=topic_type,
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portrait=portrait,
                structures=structures,
                plan=plan,
            )

            # 调用 LLM 生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容创作专家，精通短视频脚本和图文内容创作。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            content = self._parse_content_response(response)

            # 估算 token
            tokens_used = self.TOKEN_ESTIMATE.get(plan, self.TOKEN_ESTIMATE['free'])['total']

            return {
                'success': True,
                'content': content,
                'tokens_used': tokens_used,
                '_meta': {
                    'plan': plan,
                    'structures_available': len(structures),
                    'structure_names': structure_names,
                }
            }

        except Exception as e:
            logger.error("[TopicContentGenerator] Error: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def _get_structures_for_plan(self, plan: str) -> list:
        """根据套餐返回可用内容结构"""
        if plan == 'basic':
            return self.BASIC_10_STRUCTURES
        elif plan == 'professional':
            return self.PROFESSIONAL_15_STRUCTURES
        elif plan == 'enterprise':
            return self.ENTERPRISE_20_STRUCTURES
        else:
            return self.BASIC_STRUCTURES

    def _build_content_prompt(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        business_range: str,
        business_type: str,
        portrait: dict,
        structures: list,
        plan: str,
    ) -> str:
        """构建内容生成 Prompt"""

        portrait_info = self._get_portrait_info(portrait)
        current_month = datetime.now().month
        current_season = self._get_current_season()

        # 生成结构选择说明
        struct_list_text = '\n'.join([
            f"{i+1}. 【{s['name']}】{s['desc']}（{s['slides']}张图）"
            for i, s in enumerate(structures)
        ])

        # SEO 和精准埋词（专业版/企业版专属）
        seo_section = ""
        if plan in ('professional', 'enterprise'):
            seo_section = """
## SEO优化要求（精准埋词）
- 标题必须包含核心业务关键词
- 每张图片副标题需自然融入1-2个长尾关键词
- 标签选取：2个核心词 + 3个长尾词 + 1个流量词
- 话题标签：1个品牌词 + 2个品类词 + 2个痛点词 + 1个地域词（适用时）
"""
            if plan == 'enterprise':
                seo_section += """
## 企业版专属 - 专家评审维度
生成内容后自检以下维度：
1. 消费心理学维度：痛点→共鸣→解决→信任→行动 链路是否完整
2. SEO关键词密度：核心词出现≥3次，长尾词出现≥5次
3. 视觉设计提示：每张图需标注画面风格要求
4. 评论区首评引导：预设一条能引发互动的首评
"""

        prompt = f"""你是一位资深的内容创作专家。请根据以下选题，生成一篇完整的抖音图文内容。

## 选题信息
- 选题标题：{topic_title}
- 选题类型：{topic_type}

## 业务信息
- 业务描述：{business_description}
- 经营范围：{'本地服务' if business_range == 'local' else '跨区域服务'}
- 业务类型：{business_type}

## 目标用户画像
{portrait_info}

## 当前时间
- 月份：{current_month}月
- 季节：{current_season}

## 可用内容结构（共{len(structures)}种，付费版本越高可选越多）
{struct_list_text}

请根据选题类型和目标用户，选择最合适的1种结构来生成内容。{seo_section}

## 图文基础规范（必须遵守）
1. **尺寸**：1080×1920px（9:16竖图）
2. **张数**：根据所选结构确定（参考上方的张数）
3. **单行字数**：每张图文字≤10字
4. **文案风格**：口语化、接地气、戳心、有共鸣
5. **封面要求**：前3秒字幕最大最醒目，≤10字，要戳心
6. **画面要求**：真实场景图，禁止纯色/渐变背景

## 图文内容结构要求
请按所选结构，每张图详细输出：
- 图号和角色（封面/痛点/分析等）
- 主标题（≤10字）
- 副标题/要点（口语化短句）
- 画面风格描述
- 关键词埋入位置

## 输出格式（严格JSON）
```json
{{
  "structure": "所选结构名称",
  "slides_count": 图片张数,
  "title": "主标题（≤15字，戳心）",
  "subtitle": "副标题（≤15字）",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5", "标签6"],
  "slides": [
    {{
      "index": 1,
      "role": "封面",
      "main_title": "主标题（≤10字）",
      "sub_content": "副标题/要点（口语化短句）",
      "keywords": ["埋入的关键词"],
      "visual_style": "画面风格描述"
    }},
    ...
  ],
  "hashtags": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"],
  "first_comment": "首评引导内容（能引发互动）",
  "tips": "发布建议（时间+注意事项）"
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _get_portrait_info(self, portrait: dict) -> str:
        """获取画像信息"""
        if not portrait:
            return "暂无详细画像信息"

        if isinstance(portrait, dict):
            identity = portrait.get('identity', '')
            pain_point = portrait.get('pain_point', portrait.get('核心痛点', ''))
            concern = portrait.get('concern', portrait.get('核心顾虑', ''))
            scenario = portrait.get('scenario', portrait.get('场景', ''))

            info = f"用户身份：{identity}" if identity else ""
            info += f"\n核心痛点：{pain_point}" if pain_point else ""
            info += f"\n核心顾虑：{concern}" if concern else ""
            info += f"\n使用场景：{scenario}" if scenario else ""

            return info or "暂无详细画像信息"

        return str(portrait)

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

    def _parse_content_response(self, response: str) -> dict:
        """解析 LLM 返回的内容结果"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                content = json.loads(json_str)
                if isinstance(content, dict):
                    return self._validate_content(content)

            return self._get_default_content()

        except Exception as e:
            logger.debug("[TopicContentGenerator] Parse error: %s", e)
            return self._get_default_content()

    def _validate_content(self, content: dict) -> dict:
        """验证并补充内容字段"""
        default = self._get_default_content()

        return {
            'title': content.get('title', default['title']),
            'subtitle': content.get('subtitle', default['subtitle']),
            'tags': content.get('tags', default['tags']),
            'body': self._slides_to_body(content.get('slides', [])),
            'slides': content.get('slides', []),
            'structure': content.get('structure', ''),
            'hashtags': content.get('hashtags', default['hashtags']),
            'first_comment': content.get('first_comment', ''),
            'tips': content.get('tips', default['tips']),
        }

    def _slides_to_body(self, slides: list) -> str:
        """将 slides 转换为可读的 body 文本"""
        if not slides:
            return ''
        lines = []
        for slide in slides:
            role = slide.get('role', f'图{slide.get("index", "?")}')
            lines.append(f"**【{role}】**")
            if slide.get('main_title'):
                lines.append(f"  标题：{slide['main_title']}")
            if slide.get('sub_content'):
                lines.append(f"  内容：{slide['sub_content']}")
            if slide.get('keywords'):
                lines.append(f"  关键词：{', '.join(slide['keywords'])}")
            if slide.get('visual_style'):
                lines.append(f"  画面：{slide['visual_style']}")
            lines.append('')
        return '\n'.join(lines)

    def _get_default_content(self) -> dict:
        """获取默认内容结构"""
        return {
            'title': '请选择一个选题开始创作',
            'subtitle': '',
            'tags': ['标签1', '标签2', '标签3', '标签4', '标签5', '标签6'],
            'body': '请先生成选题，然后选择选题开始创作内容。\n\n内容将在这里显示。',
            'slides': [],
            'structure': '',
            'hashtags': ['#话题1', '#话题2', '#话题3', '#话题4', '#话题5'],
            'first_comment': '',
            'tips': '建议在午休时间（12:00-13:00）或晚间（20:00-21:00）发布，效果更佳。'
        }
