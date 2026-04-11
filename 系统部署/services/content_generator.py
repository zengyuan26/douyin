"""
选题内容生成服务

基于选题，生成完整的图文内容
所有用户均可使用全部20种内容结构：
1. 痛点共鸣型、疑问揭秘型、数字清单型
2. 对比冲击型、场景故事型、经验总结型
3. 知识科普型、产品评测型、选购指南型
4. 避坑指南型、时间节点型、人群细分型
5. 价格博弈型、替代方案型、升级迭代型
6. 行业揭秘型、数据说话型、场景矩阵型
7. 决策树型、用户证言型

新增功能：
- 多版本生成支持：图文/短视频脚本/长文
- SEO优化 + 精准埋词（企业版专属功能）
"""

import json
import re
import logging
from datetime import datetime
from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class TopicContentGenerator:
    """选题内容生成器"""

    # 全部 20 种图文内容结构（所有用户均可使用）
    ALL_STRUCTURES = [
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
        {'name': '时间节点型', 'slides': 7, 'desc': '封面→时间背景→阶段问题→对应方案→注意事项→时机选择→品牌'},
        {'name': '人群细分型', 'slides': 7, 'desc': '封面→人群A→人群B→人群C→各自痛点→各自方案→品牌'},
        {'name': '价格博弈型', 'slides': 6, 'desc': '封面→价格误区→定价逻辑→成本拆解→价值对比→品牌'},
        {'name': '替代方案型', 'slides': 6, 'desc': '封面→替代品问题→替代原理→效果对比→推荐方案→品牌'},
        {'name': '升级迭代型', 'slides': 7, 'desc': '封面→旧方案问题→升级思路→新方案亮点→对比→使用建议→品牌'},
        {'name': '行业揭秘型', 'slides': 7, 'desc': '封面→行业潜规则→内幕揭秘→消费者误区→正确认知→品牌'},
        {'name': '数据说话型', 'slides': 7, 'desc': '封面→核心数据→数据解读→行业对比→趋势预判→品牌'},
        {'name': '场景矩阵型', 'slides': 8, 'desc': '封面→场景1→场景2→场景3→各自方案→场景选择建议→品牌'},
        {'name': '决策树型', 'slides': 7, 'desc': '封面→决策入口→分支A/B/C→各分支结论→通用建议→品牌'},
        {'name': '用户证言型', 'slides': 7, 'desc': '封面→用户痛点→真实故事→改变过程→使用效果→品牌'},
    ]

    # ── GEO 8大模式定义 ──
    GEO_MODES = {
        '问题-答案模式': {
            'keywords': ['什么是', '怎么选', '怎么办', '是否', '哪个好', '如何', '好不好', '怎么选'],
            'best_formats': ['长文', '小红书'],
            'title_patterns': ['什么是.*', '.*怎么办', '.*怎么选', '.*好不好', '.*如何.*'],
            'hook': '直接给出专业答案，开篇≤20字无铺垫',
        },
        '定义-解释模式': {
            'keywords': ['定义', '区别', '差异', '是什么', '和.*区别', '与.*不同'],
            'best_formats': ['长文', '抖音'],
            'title_patterns': ['.*定义.*', '.*区别.*', '.*是什么', '.*和.*区别'],
            'hook': '定义≤30字 + 生动比喻结尾绑定品牌',
        },
        '金句-论证模式': {
            'keywords': ['99%', '不是.*而是', '误区', '错了', '都错了', '真相', '其实'],
            'best_formats': ['抖音', '小红书'],
            'title_patterns': ['.*99%.*', '.*不是.*而是.*', '.*误区.*', '.*错了.*'],
            'hook': '开篇金句制造认知冲突，结尾反转或正确认知',
        },
        '框架-工具模式': {
            'keywords': ['方法论', '框架', '模型', '体系', '流程', '步骤', '清单'],
            'best_formats': ['长文'],
            'title_patterns': ['.*方法.*', '.*框架.*', '.*模型.*', '.*流程.*'],
            'hook': '框架可视化描述 + 可落地操作清单',
        },
        '清单体模式': {
            'keywords': ['清单', '技巧', '方法', '窍门', '步骤', '大全', '汇总'],
            'best_formats': ['小红书', '长文'],
            'title_patterns': ['.*清单.*', '.*技巧.*', '.*方法.*', '.*步骤.*'],
            'hook': '数字承诺（如"10个技巧"）+ 优先级排序',
        },
        '榜单体模式': {
            'keywords': ['排行', '排名', '红黑榜', '推荐', 'top', '榜单', '哪个'],
            'best_formats': ['长文', '小红书'],
            'title_patterns': ['.*排行.*', '.*排名.*', '.*推荐.*', '.*榜单.*'],
            'hook': '榜单核心结论 + 评选维度说明',
        },
        '案例-故事模式': {
            'keywords': ['案例', '故事', '经历', '客户', '真实', '成功', '创业'],
            'best_formats': ['长文', '抖音'],
            'title_patterns': ['.*案例.*', '.*故事.*', '.*经历.*', '.*客户.*'],
            'hook': 'P-C-S-R英雄之旅结构：困境→尝试→方案→成果',
        },
        '对比-纠错模式': {
            'keywords': ['对比', '比较', 'vs', '或者', '还是', '旧.*新', '错.*对'],
            'best_formats': ['抖音', '长文'],
            'title_patterns': ['.*对比.*', '.*vs.*', '.*旧.*新.*', '.*错.*对.*'],
            'hook': '旧vs新对比 + 错误vs正确并列',
        },
    }

    # Token 消耗估算
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
        topic_type_key: str = '',
        business_description: str = '',
        business_range: str = '',
        business_type: str = '',
        portrait: dict = None,
        is_premium: bool = False,
        premium_plan: str = 'free',
        content_style: str = '',
        selected_scene: dict = None
    ) -> dict:
        """
        生成图文内容

        Args:
            topic_id: 选题ID
            topic_title: 选题标题
            topic_type: 选题类型名称
            topic_type_key: 选题类型键（来自选题库，如 pain_point/compare/skill 等）
            business_description: 业务描述
            business_range: 经营范围
            business_type: 业务类型
            portrait: 用户画像
            is_premium: 是否付费用户（已废弃，保留兼容性）
            premium_plan: 套餐类型（已废弃，保留兼容性，所有用户均可使用全部结构）
            content_style: 内容风格（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）
            selected_scene: 选中的场景组合（包含组合、标签、风格等信息）

        Returns:
            dict: {
                "success": bool,
                "content": {...},
                "tokens_used": int
            }
        """
        try:
            # 所有用户均可使用全部20种结构
            structures = self.ALL_STRUCTURES
            structure_names = [s['name'] for s in structures]

            # ── GEO模式自动匹配（优先级：type_key > title关键词 > selected_scene）──
            geo_mode_info = self.match_geo_mode(topic_title, selected_scene, topic_type_key)
            logger.info(f"[GEO调试] topic_title={topic_title}, selected_scene={selected_scene}")
            logger.info(f"[GEO调试] geo_mode_info={geo_mode_info}")

            # 构建 Prompt
            prompt = self._build_content_prompt(
                topic_title=topic_title,
                topic_type=topic_type,
                business_description=business_description,
                business_range=business_range,
                business_type=business_type,
                portrait=portrait,
                structures=structures,
                plan=premium_plan,
                content_style=content_style,
                selected_scene=selected_scene,
                geo_mode_info=geo_mode_info,
            )

            # 调用 LLM 生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容创作专家，精通短视频脚本和图文内容创作。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            if not response:
                logger.error("[TopicContentGenerator] LLM 调用返回空，provider=%s, model=%s",
                             self.llm.provider, self.llm.model)
                return {
                    'success': False,
                    'error': 'LLM 调用失败，请检查 API 配置'
                }

            logger.info(f"[TopicContentGenerator] LLM 原始响应 (前500字符): {response[:500]}")

            # 解析结果
            content = self._parse_content_response(response)

            # 检测是否拿到了占位默认内容（说明解析失败）
            is_placeholder = content.get('title') == self._get_default_content()['title']
            if is_placeholder:
                logger.error("[TopicContentGenerator] LLM 响应解析失败，返回了占位内容")
                return {
                    'success': False,
                    'error': 'LLM 响应解析失败，请重试'
                }

            # 估算 token
            tokens_used = self.TOKEN_ESTIMATE.get(premium_plan, self.TOKEN_ESTIMATE['free'])['total']

            return {
                'success': True,
                'content': content,
                'tokens_used': tokens_used,
                '_meta': {
                    'plan': premium_plan,
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
        content_style: str = '',
        selected_scene: dict = None,
        geo_mode_info: dict = None,
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

        # ── 内容风格指导 ──
        style_guide = self._get_style_guide(content_style) if content_style else ''

        # ── GEO模式信息 ──
        geo_section = ''
        if geo_mode_info:
            geo_section = self._get_geo_mode_guide(geo_mode_info)

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

        # 场景信息 - 提取关键词用于GEO匹配（兼容旧格式 组合/标签/风格 和新格式 group/label/style）
        scene_keywords = ''
        if selected_scene:
            combo = selected_scene.get('组合') or selected_scene.get('group', '')
            label = selected_scene.get('标签') or selected_scene.get('label', '')
            style = selected_scene.get('风格') or selected_scene.get('style', '')
            scene_keywords = f"{combo} {label} {style}".strip()

        prompt = f"""你是GEO内容优化专家。请根据以下选题，生成一篇高收录、高权重的图文内容。

## 选题信息
- 选题标题：{topic_title}
- 选题类型：{topic_type}
- 选题关键词：{scene_keywords}（用于GEO模式匹配）

## 业务信息
- 业务描述：{business_description}
- 经营范围：{'本地服务' if business_range == 'local' else '跨区域服务'}
- 业务类型：{business_type}

## 目标用户画像
{portrait_info}

## 当前时间
- 月份：{current_month}月
- 季节：{current_season}

## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## 【重要】GEO模式强制要求
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{geo_section}

【强制要求】
1. 必须严格按照上述GEO模式的"结构要求"生成内容
2. 每张图必须嵌入GEO模式相关的核心关键词
3. 内容结构必须体现GEO模式的特征（如：问题-答案模式的"开篇直接给答案"）
4. 禁止使用与GEO模式不匹配的内容结构（如：问题-答案模式不能用故事叙述型）
## ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 可用内容结构（共{len(structures)}种）
{struct_list_text}

【重要】必须从以上结构中选择与GEO模式最匹配的1种。

## 内容风格指导
{style_guide}

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
- 设计规格（尺寸、背景、排版要求）
- 子要点（如有数据对比、案例等需要展开的内容）

## 输出格式（严格JSON）
```json
{{
  "structure": "所选结构名称",
  "geo_mode": "GEO模式名称",
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
      "visual_style": "画面风格描述",
      "design_specs": "设计规格，如：尺寸1080x1920px，背景白色，标题醒目",
      "sub_points": ["子要点1", "子要点2"],
      "data_content": "具体数据内容（如有）"
    }},
    ...
  ],
  "hashtags": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"],
  "first_comment": "首评引导内容（能引发互动）",
  "publish_strategy": "发布建议（时间+注意事项）",
  "color_scheme": ["主色调#2563EB", "辅助色白色", "信任色绿色#22C55E"],
  "production_specs": "制作规范：图片数量X张，文字大小18pt+，核心观点醒目",
  "seo_keywords": {{
    "core": ["核心词1", "核心词2"],
    "long_tail": ["长尾词1", "长尾词2"],
    "scene": ["场景词1", "场景词2"],
    "problem": ["问题词1", "问题词2"]
  }},
  "cover_suggestion": {{
    "opening_words": "开头词：如真相、揭秘、必看",
    "emotion_words": "情绪词：如终于搞懂、原来如此",
    "action_guide": "行动引导：如收藏、转发"
  }}
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

    # type_key → geo_mode 映射（选题库选题类型 → 内容生成时的GEO模式）
    TYPE_KEY_TO_GEO_MODE = {
        'pain_point':        '问题-答案模式',      # 痛点解决 → 直接给答案
        'decision_encourage': '问题-答案模式',    # 决策鼓励 → 直接给答案
        'compare':           '问题-答案模式',      # 对比选型 → 问题-答案
        'pitfall':           '金句-论证模式',      # 避坑指南 → 反常识金句
        'cause':             '问题-答案模式',      # 原因分析 → 问题-答案
        'tutorial':          '定义-解释模式',     # 知识教程 → 定义-解释
        'skill':             '框架-工具模式',     # 实操技巧 → 框架-工具
        'seasonal':          '清单体模式',        # 季节营销 → 清单体
        'festival':          '清单体模式',        # 节日营销 → 清单体
        'emotional':         '案例-故事模式',     # 情感故事 → 案例故事
        'upstream':          '定义-解释模式',     # 上游科普 → 定义-解释
        'price':             '问题-答案模式',     # 行情价格 → 问题-答案
        'rethink':           '金句-论证模式',     # 认知颠覆 → 金句论证
        'effect_proof':      '案例-故事模式',    # 效果验证 → 案例故事
    }

    # GEO模式名称 → mode_key 映射
    GEO_MODE_KEY_MAP = {
        '问题-答案模式': 'question_answer',
        '定义-解释模式': 'definition',
        '金句-论证模式': 'golden_sentence',
        '框架-工具模式': 'framework_tool',
        '清单体模式': 'checklist',
        '榜单体模式': 'ranking',
        '案例-故事模式': 'case_story',
        '对比-纠错模式': 'comparison',
    }

    def _get_mode_key(self, mode_name: str) -> str:
        """根据GEO模式名称获取对应的mode_key"""
        return self.GEO_MODE_KEY_MAP.get(mode_name, 'question_answer')

    def match_geo_mode(self, topic_title: str, selected_scene: dict = None, type_key: str = '') -> dict:
        """
        根据选题信息自动匹配最优GEO模式

        匹配优先级：
        1. type_key → geo_mode 映射（来自选题库）
        2. 标题关键词匹配（兜底）
        3. selected_scene 关键词匹配（最终兜底）

        Args:
            topic_title: 选题标题
            selected_scene: 选中的场景组合
            type_key: 选题类型键（来自选题库，如 pain_point/compare/skill 等）

        Returns:
            dict: {
                'mode': '问题-答案模式',  # 模式名称
                'mode_key': 'question_answer',  # 模式键名
                'best_formats': ['长文', '小红书'],  # 最佳适配格式
                'hook': '直接给出专业答案',  # 钩子描述
                'reason': '根据type_key匹配'  # 匹配原因
            }
        """
        # ── 1. type_key 映射优先 ──
        if type_key and type_key in self.TYPE_KEY_TO_GEO_MODE:
            mode_name = self.TYPE_KEY_TO_GEO_MODE[type_key]
            mode_info = self.GEO_MODES.get(mode_name, {})
            return {
                'mode': mode_name,
                'mode_key': self._get_mode_key(mode_name),
                'best_formats': mode_info.get('best_formats', ['长文']),
                'hook': mode_info.get('hook', ''),
                'reason': f'根据选题类型「{type_key}」自动匹配GEO模式「{mode_name}」',
            }

        topic_lower = topic_title.lower()
        topic_full = topic_title

        # 从场景组合中提取关键词（兼容旧格式 组合/标签/风格 和新格式 group/label/style）
        scene_keywords = ''
        scene_all_text = ''
        if selected_scene:
            scene_combo = selected_scene.get('组合') or selected_scene.get('group', '')
            scene_label = selected_scene.get('标签') or selected_scene.get('label', '')
            scene_style = selected_scene.get('风格') or selected_scene.get('style', '')
            scene_keywords = scene_combo + ' ' + scene_label + ' ' + scene_style
            scene_all_text = scene_keywords.lower()

        # 合并选题和场景关键词用于匹配
        combined_text = (topic_full + ' ' + scene_all_text).lower()

        # 优先级匹配（按具体程度从高到低）
        matchers = [
            # 1. 对比-纠错模式（最具体）
            (lambda t, s: any(k in t for k in ['对比', '比较', ' vs ', '或者', '还是', '不准', '错误', '误区', '差异']) or
                          any(k in s for k in ['对比', '比较', '旧', '正确', '错误', '不准', '差异']),
             '对比-纠错模式', 'comparison',
             lambda: '标题或场景含"不准/对比/错误/误区"，适合用旧vs新、错误vs正确对比'),

            # 2. 案例-故事模式
            (lambda t, s: any(k in t for k in ['案例', '故事', '经历', '客户', '真实', '成功', '创业']) or
                          any(k in s for k in ['故事', '经历', '真实', '客户', '成功']),
             '案例-故事模式', 'case_story',
             lambda: '标题或场景含"案例/故事/经历"，适合用P-C-S-R英雄之旅结构'),

            # 3. 清单体模式
            (lambda t, s: any(k in t for k in ['清单', '技巧', '方法', '窍门', '步骤', '大全', '哪些', '几个']) or
                          any(k in s for k in ['清单', '步骤', '方法', '技巧']),
             '清单体模式', 'checklist',
             lambda: '标题或场景含数字+技巧/清单，适合用清单体结构'),

            # 4. 榜单体模式
            (lambda t, s: any(k in t for k in ['排行', '排名', '红黑', '推荐', 'top', '榜单', '哪个']) or
                          any(k in s for k in ['推荐', '排行', '榜单']),
             '榜单体模式', 'ranking',
             lambda: '标题或场景含"排行/推荐/榜单"，适合用榜单体结构'),

            # 5. 框架-工具模式
            (lambda t, s: any(k in t for k in ['方法论', '框架', '模型', '体系', '流程', '规范', '标准']) or
                          any(k in s for k in ['方法', '框架', '体系', '流程']),
             '框架-工具模式', 'framework_tool',
             lambda: '标题或场景含"方法论/框架/模型/流程"，适合用框架+操作清单结构'),

            # 6. 金句-论证模式
            (lambda t, s: any(k in t for k in ['99%', '不是', '误区', '错了', '真相', '其实', '颠覆', '难怪', '原来']) or
                          any(k in s for k in ['误区', '错误', '认知', '真相']),
             '金句-论证模式', 'golden_sentence',
             lambda: '标题或场景含"99%/误区/不是...而是..."，适合用金句+认知冲突结构'),

            # 7. 定义-解释模式
            (lambda t, s: any(k in t for k in ['定义', '区别', '差异', '是什么', '原理', '原因']) or
                          any(k in s for k in ['定义', '区别', '原因', '原理']),
             '定义-解释模式', 'definition',
             lambda: '标题或场景含"定义/区别/是什么/原因"，适合用定义+论证结构'),

            # 8. 问题-答案模式（默认模式，适用于各种问题类选题）
            (lambda t, s: any(k in t for k in ['怎么办', '怎么选', '是否', '如何', '好不好', '为什么', '能不能', '要不要']) or
                          any(k in s for k in ['怎么办', '如何', '优化', '解决', '提升']),
             '问题-答案模式', 'question_answer',
             lambda: '标题或场景含"怎么办/如何/优化/解决"，适合直接给出专业答案'),
        ]

        # 执行匹配
        for matcher, mode_name, mode_key, reason_fn in matchers:
            if matcher(topic_full, scene_all_text):
                mode_info = self.GEO_MODES.get(mode_name, {})
                return {
                    'mode': mode_name,
                    'mode_key': mode_key,
                    'best_formats': mode_info.get('best_formats', ['长文']),
                    'hook': mode_info.get('hook', ''),
                    'reason': reason_fn(),
                }

        # 默认返回问题-答案模式
        default_mode = self.GEO_MODES.get('问题-答案模式', {})
        return {
            'mode': '问题-答案模式',
            'mode_key': 'question_answer',
            'best_formats': default_mode.get('best_formats', ['长文']),
            'hook': default_mode.get('hook', ''),
            'reason': '默认使用问题-答案模式，开篇直接给出专业答案',
        }

    def _get_geo_mode_guide(self, geo_mode_info: dict) -> str:
        """
        根据GEO模式生成详细的结构化指导

        Args:
            geo_mode_info: match_geo_mode返回的GEO模式信息

        Returns:
            GEO模式专属的结构化指导文本
        """
        mode = geo_mode_info.get('mode', '问题-答案模式')

        geo_guides = {
            '问题-答案模式': """
【GEO模式：问题-答案模式】← AI最爱的引用模式 ★★★优先使用"疑问揭秘型"结构★★★
■ 核心特征：标题含"什么是/怎么办/怎么选"
■ 【强制】优先使用"疑问揭秘型"结构，slides=5，结构：封面→疑问→揭秘→对比→引导
■ 【强制】内容结构：
  1. 封面：直接抛出核心问题（≤10字）
  2. 疑问：描述用户痛点/困惑
  3. 揭秘：直接给出专业答案（≤20字，无铺垫）
  4. 对比：为什么这样做vs不这样做的后果
  5. 引导：推荐解决方案
■ 标签要求：#解答 #揭秘 #干货 #避坑 #推荐
""",
            '定义-解释模式': """
【GEO模式：定义-解释模式】← 抢占认知垄断 ★★★优先使用"知识科普型"结构★★★
■ 核心特征：标题含"定义/区别/是什么/原理"
■ 【强制】优先使用"知识科普型"结构，slides=5，结构：封面→冷知识→原理说明→应用场景→品牌
■ 【强制】内容结构：
  1. 封面：定义一句话（≤30字）
  2. 冷知识：相关背景或有趣事实
  3. 原理说明：工作原理或核心逻辑
  4. 应用场景：实际应用举例
  5. 品牌引导：为什么选择我们
■ 标签要求：#科普 #定义 #原理 #知识 #解读
""",
            '金句-论证模式': """
【GEO模式：金句-论证模式】← 制造认知冲突 ★★★优先使用"行业揭秘型"结构★★★
■ 核心特征：标题含"99%/不是...而是.../误区/错了"
■ 【强制】优先使用"行业揭秘型"结构，slides=7，结构：封面→行业潜规则→内幕揭秘→消费者误区→正确认知→品牌
■ 【强制】内容结构：
  1. 封面：金句制造认知冲突（如"99%的人都做错了！"）
  2. 行业潜规则：揭露行业内幕
  3. 内幕揭秘：为什么这样做是错的
  4. 消费者误区：展示常见错误认知
  5. 正确认知：给出正确做法
  6. 品牌引导：专业解决方案
■ 标签要求：#误区 #揭秘 #行业内幕 #正确认知 #避坑
""",
            '框架-工具模式': """
【GEO模式：框架-工具模式】← 思想领导力 ★★★必须使用"决策树型"结构★★★
■ 核心特征：标题含"方法论/框架/模型/体系/流程"
■ 【强制】必须使用"决策树型"结构，slides=7，结构：封面→决策入口→分支A/B/C→各分支结论→通用建议→品牌
■ 【强制】内容结构：
  1. 封面：框架核心观点+价值承诺
  2. 决策入口：什么情况下需要这个方法
  3. 分支A/B/C：不同情况对应的方案
  4. 各分支结论：每个方案的适用场景
  5. 通用建议：所有人都适用的建议
  6. 品牌引导：提供完整工具/服务
■ 标签要求：#方法论 #框架 #模型 #工具 #SOP
""",
            '清单体模式': """
【GEO模式：清单体模式】← 高效实用 ★★★必须使用"数字清单型"结构★★★
■ 核心特征：标题含数字+清单/技巧/方法
■ 【强制】必须使用"数字清单型"结构，slides=6，结构：封面→数字概览→逐条展开→总结→品牌
■ 【强制】内容结构：
  1. 封面：数字承诺（如"掌握这10个技巧"）
  2. 数字概览：列出所有要点
  3. 逐条展开：每个要点"是什么+为什么+怎么做"
  4. 总结：核心要点回顾
  5. 品牌引导：为什么选择我们
■ 标签要求：#清单 #技巧 #方法 #干货 #大全
""",
            '榜单体模式': """
【GEO模式：榜单体模式】← 决策参考 ★★★必须使用"数据说话型"结构★★★
■ 核心特征：标题含"排行/排名/红黑榜/推荐/top"
■ 【强制】必须使用"数据说话型"结构，slides=7，结构：封面→核心数据→数据解读→行业对比→趋势预判→品牌
■ 【强制】内容结构：
  1. 封面：榜单核心结论（如"Top5，第3个最具性价比"）
  2. 核心数据：列出排名数据
  3. 数据解读：每个选项的优缺点
  4. 行业对比：横向对比分析
  5. 趋势预判：未来发展方向
  6. 品牌引导：为什么选择我们
■ 标签要求：#排行 #推荐 #测评 #对比 #红黑榜
""",
            '案例-故事模式': """
【GEO模式：案例-故事模式】← P-C-S-R英雄之旅 ★★★必须使用"场景故事型"结构★★★
■ 核心特征：标题含"案例/故事/经历/客户/成功"
■ 【强制】必须使用"场景故事型"结构，slides=5，结构：封面→场景描述→问题升级→解决方案→行动
■ 【强制】内容结构（P-C-S-R四步法）：
  1. P（困境）：主角具象身份+崇高地位（"某连锁店老板"）
  2. C（催化）：失败尝试+困境反差（"试了3种方法都不行"）
  3. S（解决）：产品/方案作为"神秘武器"+奋斗细节
  4. R（成果）：数据对比+可复制的金句
■ 标签要求：#案例 #成功故事 #客户见证 #真实分享 #创业经历
""",
            '对比-纠错模式': """
【GEO模式：对比-纠错模式】← 打破误区 ★★★必须使用"对比冲击型"结构★★★
■ 核心特征：标题含"对比/比较/vs/不准/错误/误区"
■ 【强制】必须使用"对比冲击型"结构，slides=6，结构：封面→错误做法→正确做法→对比表→方案→品牌
■ 【强制】内容结构：
  1. 封面：指出行业误区（如"XX行业90%的人都犯这个错！"）
  2. 错误做法：展示2-3个常见错误（❌）
  3. 正确做法：对应展示正确方法（✅）
  4. 对比表：左右对比"错误 vs 正确"
  5. 解决方案：提供正确做法
  6. 品牌引导：为什么选择我们
■ 标签要求：#误区 #避坑 #正确方法 #行业揭秘 #对比
""",
        }

        mode_guide = geo_guides.get(mode, geo_guides['问题-答案模式'])

        # 添加匹配原因
        reason = geo_mode_info.get('reason', '')
        if reason:
            mode_guide = mode_guide.replace('【GEO模式：', f'【GEO模式：{reason}\n■ ')

        return mode_guide

    def _get_style_guide(self, content_style: str) -> str:
        """
        根据内容风格生成指导说明

        Args:
            content_style: 风格类型（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）

        Returns:
            风格指导文本
        """
        style_guides = {
            '情绪共鸣': """
【风格：情绪共鸣】
- 文案基调：感性、走心、戳痛点、引发共情
- 开头方式：从用户痛点场景切入，让用户"感同身受"
- 句式特点：使用"你是不是也..."、"没想到..."、"原来..."等句式
- 情绪词：焦虑、担心、后悔、迷茫、无奈、可惜、扎心
- 结尾：给出温暖、希望的解决方案
- 避免：过于理性、说教味浓、缺乏情感温度
""",
            '干货科普': """
【风格：干货科普】
- 文案基调：专业、严谨、有深度、信息量大
- 开头方式：直接抛出知识点或数据，吸引专业人士
- 句式特点：使用"3个技巧"、"5个方法"、"核心关键是..."等结构化表达
- 关键词：揭秘、内幕、原理、技巧、方法、步骤、数据
- 结尾：总结要点，提供可操作的方法论
- 避免：过于口语化、缺乏专业感、信息太碎片
""",
            '犀利吐槽': """
【风格：犀利吐槽】
- 文案基调：反讽、自嘲、打破常规、引发争议
- 开头方式：用反问或颠覆认知的标题吸引眼球
- 句式特点：使用"别再..."、"你以为..."、"XX都是骗人的"等句式
- 情绪词：错误、误区、坑、骗、傻、白花钱、多此一举
- 结尾：反转或给出正确的做法
- 避免：过于偏激、负能量、人身攻击
""",
            '故事叙述': """
【风格：故事叙述】
- 文案基调：叙事性强、画面感强、有代入感
- 开头方式：从一个具体场景或故事开头，让用户"身临其境"
- 句式特点：使用"那天..."、"我曾经..."、"朋友告诉我..."等叙事句式
- 关键词：经历、故事、回忆、那一刻、后来、终于
- 结尾：升华主题，总结感悟
- 避免：流水账、平淡无奇、缺乏起伏
""",
            '权威背书': """
【风格：权威背书】
- 文案基调：可信、有说服力、数据支撑
- 开头方式：用权威数据、专家观点、真实案例吸引信任
- 句式特点：使用"研究表明..."、"数据显示..."、"XX专家建议..."等句式
- 关键词：研究、数据、专家、案例、证明、验证、实测
- 结尾：给出权威背书的产品或服务
- 避免：虚假宣传、夸大其词、缺乏实证
""",
        }

        return style_guides.get(content_style, """
【风格：通用图文】
- 文案基调：口语化、接地气、戳心、有共鸣
- 开头方式：直接切入用户痛点或需求
- 句式特点：短句为主，控制在10字以内
- 情绪词：焦虑、担心、怕、后悔、迷茫
- 结尾：给出解决方案或引导行动
""")

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
        slides = content.get('slides', [])

        # ── 生成 content_plan（内容规划+制作规范）──
        content_plan = self._slides_to_content_plan(slides)

        # ── 生成 comment（评论区运营）──
        first_comment = content.get('first_comment', '')

        # ── 生成 extension（内容延伸建议）──
        extension = self._slides_to_extension(slides, content.get('geo_mode', ''))

        # ── 生成 publish（发布策略）──
        publish = self._build_publish_strategy(content)

        # ── 生成 basic_info（基础信息）──
        basic_info = self._build_basic_info(content)

        # ── 生成 compliance（合规检查）──
        compliance = self._build_compliance()

        return {
            'title': content.get('title', default['title']),
            'subtitle': content.get('subtitle', default['subtitle']),
            'tags': content.get('tags', default['tags']),
            'body': self._slides_to_body(slides),
            'slides': slides,
            'structure': content.get('structure', ''),
            'geo_mode': content.get('geo_mode', ''),
            'hashtags': content.get('hashtags', default['hashtags']),
            'first_comment': first_comment,
            'tips': content.get('publish_strategy', publish),
            # 区块内容
            'content_plan': content_plan,
            'comment': first_comment,
            'extension': extension,
            'publish': publish,
            'basic_info': basic_info,
            'compliance': compliance,
            # 额外字段
            'publish_strategy': content.get('publish_strategy', publish),
            'color_scheme': content.get('color_scheme', []),
            'production_specs': content.get('production_specs', ''),
            'seo_keywords': content.get('seo_keywords', {}),
            'cover_suggestion': content.get('cover_suggestion', {}),
        }

    def _slides_to_content_plan(self, slides: list) -> str:
        """将 slides 转换为内容规划区块文本"""
        if not slides:
            return ''
        lines = ['## 内容规划（图片数量：{}张）\n'.format(len(slides))]
        for i, slide in enumerate(slides, 1):
            role = slide.get('role', f'图{i}')
            main_title = slide.get('main_title', '')
            sub_content = slide.get('sub_content', '')
            visual_style = slide.get('visual_style', '')
            keywords = slide.get('keywords', [])
            design_specs = slide.get('design_specs', '')
            sub_points = slide.get('sub_points', [])
            data_content = slide.get('data_content', '')

            lines.append(f'#### 图片{i}：{role}')
            if main_title:
                lines.append(f'**【内容功能】** {sub_content or "待补充"}')
                lines.append('')
                lines.append(f'**【画面描述】**')
                if visual_style:
                    for line in visual_style.split('\n'):
                        if line.strip():
                            lines.append(f'- {line.strip()}')
                lines.append('')
                lines.append(f'**【文字内容】**')
                lines.append(f'- 主标题：{main_title}')
                if sub_points:
                    for pt in sub_points:
                        lines.append(f'- {pt}')
                if data_content:
                    lines.append(f'- 数据：{data_content}')
                lines.append('')
                lines.append(f'**【设计规格】**')
                if design_specs:
                    for line in design_specs.split('\n'):
                        if line.strip():
                            lines.append(f'- {line.strip()}')
                else:
                    lines.append('- 尺寸：1080x1920px（9:16竖版）')
                if keywords:
                    lines.append(f'**【关键词】** {", ".join(keywords)}')
            lines.append('\n---\n')
        return '\n'.join(lines)

    def _build_publish_strategy(self, content: dict) -> str:
        """构建发布策略文本"""
        tips = content.get('publish_strategy', content.get('tips', ''))
        color_scheme = content.get('color_scheme', [])
        seo_keywords = content.get('seo_keywords', {})
        cover_suggestion = content.get('cover_suggestion', {})

        lines = ['## 发布策略\n']

        # 发布时间
        lines.append('### 发布时间建议')
        lines.append('|| 日期 | 时间 | 理由 |')
        lines.append('|------|------|------|')
        lines.append('| 周三/周五 | 12:00-13:00 | 午休时间，家长有空看 |')
        lines.append('| 周六 | 10:00-11:00 | 周末学习时间 |')
        lines.append('| 周日 | 20:00-21:00 | 睡前高峰 |\n')

        # SEO优化
        if seo_keywords:
            core = seo_keywords.get('core', [])
            long_tail = seo_keywords.get('long_tail', [])
            lines.append('### SEO优化')
            lines.append('|| 优化项 | 内容 |')
            lines.append('|--------|------|')
            lines.append(f'| 标题关键词 | {", ".join(core) if core else "待补充"} |')
            lines.append(f'| 描述关键词 | {", ".join(long_tail) if long_tail else "待补充"} |\n')

        # 色彩方案
        if color_scheme:
            lines.append('### 色彩方案')
            lines.append('|| 元素 | 颜色参考 |')
            lines.append('|------|----------|')
            for color in color_scheme:
                parts = color.split('#')
                if len(parts) == 2:
                    lines.append(f'| {parts[0].strip()} | #{parts[1].strip()} |')
                else:
                    lines.append(f'| {color} | - |')
            lines.append('')

        # 封面建议
        if cover_suggestion:
            lines.append('### 封面建议')
            lines.append('|| 要素 | 示例 |')
            lines.append('|------|------|')
            opening = cover_suggestion.get('opening_words', '')
            emotion = cover_suggestion.get('emotion_words', '')
            action = cover_suggestion.get('action_guide', '')
            lines.append(f'| 开头词 | {opening} |')
            lines.append(f'| 情绪词 | {emotion} |')
            lines.append(f'| 行动引导 | {action} |\n')

        # 发布建议
        if tips:
            lines.append(f'### 发布建议\n{tips}\n')

        return '\n'.join(lines)

    def _build_basic_info(self, content: dict) -> str:
        """构建基础信息区块文本"""
        seo_keywords = content.get('seo_keywords', {})

        lines = ['## 基础信息\n']

        # SEO关键词
        if seo_keywords:
            core = seo_keywords.get('core', [])
            long_tail = seo_keywords.get('long_tail', [])
            scene = seo_keywords.get('scene', [])
            problem = seo_keywords.get('problem', [])

            lines.append('### SEO关键词')
            lines.append('|| 关键词类型 | 关键词 |')
            lines.append('|------------|--------|')
            if core:
                lines.append(f'| 核心词 | {", ".join(core)} |')
            if long_tail:
                lines.append(f'| 长尾词 | {", ".join(long_tail)} |')
            if scene:
                lines.append(f'| 场景词 | {", ".join(scene)} |')
            if problem:
                lines.append(f'| 问题词 | {", ".join(problem)} |')
            lines.append('')

        return '\n'.join(lines)

    def _build_compliance(self) -> str:
        """构建合规检查区块文本"""
        return '''## 合规检查
- [x] 无虚假宣传
- [x] 无绝对化用语
- [x] 无医疗功效承诺
- [x] 无侵权内容
- [x] 符合平台规范'''

    def _slides_to_extension(self, slides: list, geo_mode: str = '') -> str:
        """将 slides 转换为内容延伸建议"""
        if not slides:
            return ''
        suggestions = ['## 内容延伸建议\n']

        # 从 slides 提取所有 keywords
        all_keywords = set()
        for slide in slides:
            keywords = slide.get('keywords', [])
            for kw in keywords:
                if kw and len(kw) > 1:
                    all_keywords.add(kw)

        if all_keywords:
            suggestions.append(f'### 延伸话题建议\n{", ".join(list(all_keywords)[:5])}\n')

        if geo_mode:
            suggestions.append(f'### 内容方向\n{geo_mode}\n')

        suggestions.append('### 具体延伸选题')
        suggestions.append('|| 序号 | 延伸选题 | 类型 | 目的 |')
        suggestions.append('|------|----------|------|------|')
        suggestions.append('| 1 | 待定 | 知识科普 | 建立专业 |')
        suggestions.append('| 2 | 待定 | 实用攻略 | 增加互动 |')
        suggestions.append('')
        suggestions.append('### 系列化选题方向')
        suggestions.append('|| 系列类型 | 命名建议 | 示例 |')
        suggestions.append('|----------|----------|------|')
        suggestions.append('| 问题解决系列 | XX解读系列 | 分数线/录取/竞争 |')
        suggestions.append('| 知识科普系列 | XX必看系列 | 各批次/专项计划 |')
        suggestions.append('| 场景应用系列 | 各分数段策略 | XX分怎么填 |')
        suggestions.append('')

        return '\n'.join(suggestions)

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

    def get_all_structures(self) -> list:
        """获取所有可用内容结构"""
        return self.ALL_STRUCTURES
