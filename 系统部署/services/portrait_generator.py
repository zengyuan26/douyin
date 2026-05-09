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
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    # 痛点相关（无默认值字段）
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

    # 五要素摘要（核心！）有默认值
    portrait_summary: str = ""                  # 画像摘要：身份+问题+想转变+困境+深层需求

    # 元信息（默认值字段放最后）
    scene_tags: List[str] = field(default_factory=list)   # 场景标签
    behavior_tags: List[str] = field(default_factory=list)  # 行为标签
    content_direction: str = "种草型"                        # 内容方向

    # ===== 增强字段（任务1.1新增）=====
    language_style: str = ""                    # 人群语言风格：口语化/专业术语/情绪化/温情型
    crowd_perspective: str = ""                 # 人群视角：第一人称/第三人称/对话式
    age_range: str = ""                         # 年龄范围：如"18-25岁"、"26-35岁"、"35-45岁"
    pain_point_level: str = "medium"             # 痛点强度：high(高)/medium(中)/low(低)
    decision_stage: str = "consideration"        # 决策阶段：awareness(认知)/consideration(考量)/decision(决策)

    # ===== 三类客户分类（任务1.2新增）=====
    customer_type: str = ""                     # 客户类型：本地居民/返乡人/在外本地人
    customer_subtype: str = ""                  # 客户子类型：如"春节返乡送礼"

    # ===== B端/C端区分（任务1.2新增）=====
    client_type: str = ""                       # B端(企业)/C端(家庭/个人)
    decision_makers: List[str] = field(default_factory=list)  # 决策人列表

    # ===== 付费人/使用人（任务1.2新增）=====
    payer_info: Dict[str, Any] = field(default_factory=dict)   # 付费人信息：{role, concerns}
    user_info: Dict[str, Any] = field(default_factory=dict)    # 使用人信息：{role, concerns}
    is_payer_user_separated: bool = False       # 付费人/使用人是否分离

    # ===== 搜前搜后阶段（任务1.2新增）=====
    search_stage: str = ""                      # 搜索阶段：awareness/consideration/decision
    conversion_cycle: str = ""                  # 转化周期：短(当天)/中(3天内)/长(7天+)


@dataclass
class PortraitGenerationContext:
    """画像生成上下文"""
    keyword_library: Dict[str, Any]             # 关键词库
    problem_types: List[Dict[str, Any]]         # 问题类型列表（来自选中蓝海机会）
    business_info: Dict[str, Any]              # 业务信息
    problem_scenes: List[Dict[str, Any]] = field(default_factory=list)  # 问题场景列表（每个场景=一个画像）
    market_opportunities: List[Dict[str, Any]] = field(default_factory=list)  # 市场机会
    selected_opportunity: Dict[str, Any] = field(default_factory=dict)  # 用户选中的蓝海机会
    portraits_per_type: int = 3                 # 每个问题类型生成画像数


class PortraitGenerator:
    """
    画像生成器（基于关键词库）

    核心能力：
    1. 基于关键词库生成精准画像
    2. 按问题类型分类（一个类型 → 多个画像）
    3. 画像包含完整的身份、痛点、心理、行为维度
    """

    # 全局限流：最多同时运行 N 个 LLM 调用
    _llm_semaphore: Optional['threading.BoundedSemaphore'] = None
    _semaphore_lock: 'threading.Lock' = None

    def __init__(self):
        self.llm = get_llm_service()
        # 延迟初始化信号量（线程安全单例）
        if PortraitGenerator._llm_semaphore is None:
            import threading
            with threading.Lock():
                if PortraitGenerator._llm_semaphore is None:
                    PortraitGenerator._llm_semaphore = threading.BoundedSemaphore(5)
                    PortraitGenerator._semaphore_lock = threading.Lock()

    def generate_portraits(
        self,
        context: PortraitGenerationContext,
    ) -> List[Portrait]:
        """
        批量生成画像

        Args:
            context: 生成上下文
                - keyword_library: 关键词库
                - problem_types: 问题类型列表（可为空，将从关键词库分类提取）
                - business_info: 业务信息
                - portraits_per_type: 每个问题类型生成画像数

        Returns:
            List[Portrait]: 画像列表
        """
        portraits = []

        try:
            business_desc = context.business_info.get('business_description', '')
            business_type = context.business_info.get('business_type', 'product')

            # 优先级 1：选中蓝海机会的问题类型 → 场景
            selected_opp = context.selected_opportunity
            opp_problem_types = context.problem_types
            if selected_opp:
                opp_problem_types = selected_opp.get('problem_types', [])
                logger.info(
                    "[PortraitGenerator] 使用选中蓝海机会: %s, 问题类型=%d",
                    selected_opp.get('opportunity_name', ''),
                    len(opp_problem_types)
                )

            # 构建场景列表：一个场景 = 一个画像
            # 每个场景需要知道它的父问题类型名称
            problem_scenes = []
            for pt in opp_problem_types:
                pt_name = pt.get('name', '') or pt.get('type_name', '')
                pt_desc = pt.get('description', '')
                pt_scenes = pt.get('scenes', [])
                if pt_scenes:
                    # 从问题类型的场景列表提取
                    for scene in pt_scenes:
                        scene_name = scene.get('name', '')
                        if scene_name:
                            problem_scenes.append({
                                'scene_name': scene_name,
                                'scene_description': scene.get('description', ''),
                                'scene_keywords': scene.get('keywords', []),
                                'scene_target_audience': scene.get('target_audience', ''),
                                '_problem_type_name': pt_name,
                                '_problem_type_desc': pt_desc,
                            })
                elif pt_name:
                    # 没有场景列表时，问题类型本身就是场景
                    problem_scenes.append({
                        'scene_name': pt_name,
                        'scene_description': pt_desc,
                        'scene_keywords': pt.get('keywords', []),
                        'scene_target_audience': '',
                        '_problem_type_name': pt_name,
                        '_problem_type_desc': pt_desc,
                    })

            # 优先级 2：context.problem_scenes（如果上面的为空）
            if not problem_scenes:
                problem_scenes = [
                    {
                        'scene_name': s.get('scene_name', '') or s.get('name', ''),
                        'scene_description': s.get('scene_description', '') or s.get('description', ''),
                        'scene_keywords': s.get('scene_keywords', []),
                        'scene_target_audience': s.get('scene_target_audience', ''),
                        '_problem_type_name': s.get('_problem_type_name', ''),
                        '_problem_type_desc': s.get('_problem_type_desc', ''),
                    }
                    for s in context.problem_scenes
                    if s.get('scene_name', '') or s.get('name', '')
                ]

            # 优先级 3：从关键词库提取（完全兜底）
            if not problem_scenes:
                library_problem_types = self._extract_problem_types_from_keyword_library(
                    context.keyword_library,
                    context.business_info
                )
                for pt in library_problem_types:
                    problem_scenes.append({
                        'scene_name': pt.get('type_name', ''),
                        'scene_description': pt.get('description', ''),
                        'scene_keywords': pt.get('keywords', []),
                        'scene_target_audience': '',
                        '_problem_type_name': pt.get('type_name', ''),
                        '_problem_type_desc': pt.get('description', ''),
                    })
                logger.info(
                    "[PortraitGenerator] 从关键词库提取问题类型: %d 个",
                    len(library_problem_types)
                )

            logger.info(
                "[PortraitGenerator] 开始生成: 业务=%s, 场景数=%d, 每场景画像=%d",
                business_desc[:30] if business_desc else 'N/A',
                len(problem_scenes),
                context.portraits_per_type,
            )

            # 按问题场景并行生成画像（最多同时 5 个 LLM 调用）
            # 每个场景的生成任务
            def gen_for_scene(scene: Dict[str, Any]) -> List[Portrait]:
                scene_name = scene.get('scene_name', '')
                scene_desc = scene.get('scene_description', '')
                scene_audience = scene.get('scene_target_audience', '')
                scene_keywords = scene.get('scene_keywords', [])

                # 直接从场景字典获取父问题类型名称
                problem_type_name = scene.get('_problem_type_name', '')

                logger.info(
                    "[PortraitGenerator] 生成场景: %s (问题类型: %s)",
                    scene_name, problem_type_name
                )

                # 限流：信号量保证最多同时 5 个 LLM 调用
                with PortraitGenerator._llm_semaphore:
                    return self._generate_portraits_for_scene(
                        scene_name=scene_name,
                        scene_description=scene_desc,
                        scene_audience=scene_audience,
                        scene_keywords=scene_keywords,
                        problem_type_name=problem_type_name,
                        keyword_library=context.keyword_library,
                        business_info=context.business_info,
                        count=context.portraits_per_type,
                        market_opportunities=context.market_opportunities,
                    )

            # 限制并发数，避免超过 LLM API 速率限制
            max_workers = min(5, len(problem_scenes))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(gen_for_scene, scene): scene.get('scene_name', '')
                    for scene in problem_scenes
                }
                for future in as_completed(futures):
                    scene_name = futures[future]
                    try:
                        scene_portraits = future.result()
                        portraits.extend(scene_portraits)
                    except Exception as e:
                        logger.error("[PortraitGenerator] 场景「%s」生成失败: %s", scene_name, str(e))

            logger.info("[PortraitGenerator] 生成完成: 共 %d 个画像", len(portraits))

        except Exception as e:
            logger.error("[PortraitGenerator] 生成异常: %s", str(e))

        return portraits

    def _extract_problem_types_from_keyword_library(
        self,
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        从关键词库中提取问题类型

        问题类型的来源应该是具体的问题症状，而不是抽象的分类标签。
        例如：核心业务是"XX定制代理服务"，问题类型应该是"价格怎么算"、
        "效果好不好"，而不是"痛点放大"、"顾虑消除"。

        提取策略：
        1. 从关键词中提取用户真实的问题症状
        2. 从核心业务和蓝海机会生成问题类型
        3. 如果以上都失败，调用 LLM 生成问题类型

        Args:
            keyword_library: 关键词库
            business_info: 业务信息

        Returns:
            List[Dict[str, Any]]: 问题类型列表
        """
        categories = keyword_library.get('categories', [])

        # 第一步：从关键词中提取具体问题症状
        extracted_problems = self._extract_problems_from_keywords(categories)

        if extracted_problems:
            logger.info(
                "[PortraitGenerator] 从关键词提取到 %d 个问题类型",
                len(extracted_problems)
            )
            return extracted_problems[:8]

        # 第二步：如果关键词提取失败，从核心业务生成问题类型
        keyword_core = keyword_library.get('keyword_core', '')
        business_desc = business_info.get('business_description', '')
        problem_types = self._generate_problem_types_from_core(
            keyword_core or business_desc,
            business_info
        )
        logger.info(
            "[PortraitGenerator] 从核心业务生成 %d 个问题类型",
            len(problem_types)
        )
        return problem_types

    def _extract_problems_from_keywords(
        self,
        categories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        从关键词中提取具体问题症状

        扫描所有分类的关键词，找到用户真实搜索的问题，
        并按问题类型归类。

        例如：
        - 关键词"分数不够上好大学怎么办" -> 问题类型"分数不够"
        - 关键词"被调剂到不喜欢的专业怎么办" -> 问题类型"专业调剂"

        Returns:
            按问题核心归类的关键词列表
        """
        all_keywords = []

        # 收集所有关键词
        for cat in categories:
            keywords = cat.get('keywords', [])
            all_keywords.extend(keywords)

        if not all_keywords:
            return []

        # 从关键词中提取问题核心
        # 匹配模式：包含"怎么办"、"好吗"、"多少"、"怎么选"等疑问词的关键词
        question_patterns = [
            '怎么办', '好不好', '多少钱', '怎么选', '怎么填',
            '哪个好', '要不要', '能不能', '该不该', '会不会',
            '是什么', '为什么', '有没有', '好不好', '哪里有',
        ]

        problem_buckets = {}  # {问题核心: [关键词列表]}

        for kw in all_keywords:
            # 检查是否包含疑问词
            has_question = any(pattern in kw for pattern in question_patterns)
            if has_question:
                # 提取问题核心（去掉疑问词后的部分）
                problem_root = kw
                for pattern in question_patterns:
                    problem_root = problem_root.replace(pattern, '')
                problem_root = problem_root.strip()

                # 进一步精简
                for prefix in ['要不要', '能不能', '该不该', '会不会', '有没有']:
                    if problem_root.startswith(prefix):
                        problem_root = problem_root[len(prefix):].strip()

                if problem_root and len(problem_root) >= 2:
                    if problem_root not in problem_buckets:
                        problem_buckets[problem_root] = []
                    problem_buckets[problem_root].append(kw)

        # 转换为问题类型格式
        problem_types = []
        for root, keywords in problem_buckets.items():
            problem_types.append({
                'type_name': root,
                'description': f'{root}相关问题',
                'target_audience': '',
                'keywords': keywords[:20],
                'scene_keywords': keywords[:20],
            })

        return problem_types

    def _generate_problem_types_from_core(
        self,
        keyword_core: str,
        business_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        从核心业务词生成问题类型

        基于核心业务，让 LLM 生成用户会问的具体问题类型。

        Args:
            keyword_core: 核心业务词
            business_info: 业务信息

        Returns:
            问题类型列表
        """
        prompt = f"""你是问题类型分析师。请分析「{keyword_core}」这个业务，用户会遇到哪些具体问题。

业务描述：{business_info.get('business_description', '')}

请列出用户最关心的 6-8 个具体问题类型：

要求：
1. 问题类型要具体，不要抽象（如"分数不够怎么办"，而不是"痛点问题"）
2. 每个问题类型 2-6 个字
3. 覆盖用户从决策到售后的全流程问题

请用 JSON 格式输出：
{{
    "problem_types": [
        {{"name": "问题名称", "description": "问题描述"}},
        ...
    ]
}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.3, max_tokens=1000)

            if not response:
                return self._default_problem_types(keyword_core)

            # 解析 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                problem_types_data = data.get('problem_types', [])

                return [
                    {
                        'type_name': pt.get('name', ''),
                        'description': pt.get('description', ''),
                        'target_audience': '',
                        'keywords': [],
                        'scene_keywords': [],
                    }
                    for pt in problem_types_data
                ]

        except Exception as e:
            logger.warning("[PortraitGenerator] 生成问题类型失败: %s", str(e))

        return self._default_problem_types(keyword_core)

    def _default_problem_types(
        self,
        keyword_core: str,
    ) -> List[Dict[str, Any]]:
        """
        返回默认问题类型

        Args:
            keyword_core: 核心业务词

        Returns:
            默认问题类型列表
        """
        return [
            {
                'type_name': f'{keyword_core}的选择',
                'description': f'{keyword_core}相关选择问题',
                'target_audience': '',
                'keywords': [],
                'scene_keywords': [],
            },
            {
                'type_name': f'{keyword_core}的顾虑',
                'description': f'{keyword_core}相关顾虑问题',
                'target_audience': '',
                'keywords': [],
                'scene_keywords': [],
            },
            {
                'type_name': f'{keyword_core}的效果',
                'description': f'{keyword_core}效果相关问题',
                'target_audience': '',
                'keywords': [],
                'scene_keywords': [],
            },
        ]



        return problem_types[:5]

    def _generate_portraits_for_scene(
        self,
        scene_name: str,
        scene_description: str,
        scene_audience: str,
        scene_keywords: List[str],
        problem_type_name: str,
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
        count: int,
        market_opportunities: List[Dict[str, Any]],
    ) -> List[Portrait]:
        """为一个问题场景生成多个画像"""

        portraits = []

        # 构建Prompt
        prompt = self._build_scene_portrait_prompt(
            scene_name=scene_name,
            scene_description=scene_description,
            scene_audience=scene_audience,
            scene_keywords=scene_keywords,
            problem_type_name=problem_type_name,
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
            problem_type_desc=scene_description,
        )

        return portraits

    def _build_scene_portrait_prompt(
        self,
        scene_name: str,
        scene_description: str,
        scene_audience: str,
        scene_keywords: List[str],
        problem_type_name: str,
        keyword_library: Dict[str, Any],
        business_info: Dict[str, Any],
        count: int,
        market_opportunities: List[Dict[str, Any]],
    ) -> str:
        """构建基于场景的画像生成Prompt（增强版，融入三类客户+B端C端+付费人使用人）"""

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

        # 市场机会信息（增强版）
        opportunities_text = ""
        if market_opportunities:
            opp_list = []
            for opp in market_opportunities[:3]:
                if isinstance(opp, dict):
                    opp_name = opp.get('opportunity_name', '')
                    opp_audience = opp.get('target_audience', '')
                    opp_diff = opp.get('differentiation', '')
                    pain_level = opp.get('pain_level', 'medium')
                    severity = opp.get('severity_urgency', 'P2')
                else:
                    opp_name = getattr(opp, 'opportunity_name', '')
                    opp_audience = getattr(opp, 'target_audience', '')
                    opp_diff = getattr(opp, 'differentiation', '')
                    pain_level = getattr(opp, 'pain_level', 'medium')
                    severity = getattr(opp, 'severity_urgency', 'P2')

                opp_list.append(
                    f"- {opp_name}\n  人群：{opp_audience}\n  "
                    f"痛点强度：{pain_level} | 优先级：{severity}\n  "
                    f"差异化：{opp_diff}"
                )
            opportunities_text = "\n".join(opp_list)

        # 场景关键词文本
        scene_keywords_text = ", ".join(scene_keywords[:15]) if scene_keywords else ""

        prompt = f"""你是用户画像分析专家。请基于以下信息，生成{count}个精准用户画像。

=== 业务信息 ===
业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
业务类型：{business_type}

=== 问题场景信息 ===
问题类型：{problem_type_name}
场景名称：{scene_name}
场景描述：{scene_description}
目标人群：{scene_audience or '根据场景推断'}
场景关键词：{scene_keywords_text}

=== 市场机会（增强版）===
{opportunities_text or '暂无市场机会数据'}

=== 关键词库（参考）===
蓝海关键词（细分方向）：{', '.join(blue_ocean_kw[:10]) if blue_ocean_kw else '暂无'}
红海关键词（竞争方向）：{', '.join(red_ocean_kw[:5]) if red_ocean_kw else '暂无'}

=== 三类客户群体框架（必须覆盖）===
每个画像必须明确属于哪类客户：

| 客户类型 | 画像特征 | 消费场景 | 核心需求 | 内容方向 |
|----------|----------|----------|----------|----------|
| 本地居民 | 本地常住人口 | 自家消费、到店购买 | 实惠、方便、新鲜 | 性价比、便利性 |
| 返乡人 | 春节从外地返乡 | 送礼、带特产回城 | 品质、包装、便携 | 送礼攻略、品质推荐 |
| 在外本地人 | 在外地工作的本地人 | 思念家乡味、复购 | 正宗、情怀、邮寄 | 乡愁内容、品牌故事 |

=== B端 vs C端区分（必须明确）===
| 维度 | B端(企业) | C端(家庭) |
|------|-----------|-----------|
| 购买目的 | 品牌展示、招待客户、员工福利 | 日常饮用、家庭使用 |
| 决策人 | 老板、行政、采购、财务 | 家庭主妇、上班族、老年人 |
| 核心痛点 | 报销、门槛、配送 | 品质、价格、服务 |
| 搜索特点 | 专业、长尾、具体 | 通俗、广泛、口语化 |

=== 付费人 vs 使用人（必须区分）===
| 角色 | 定义 | 关注点 | 示例 |
|------|------|--------|------|
| 付费人 | 出钱购买的人 | 价值、成本、效果、可报销 | 老板、老公、父母 |
| 使用人 | 实际使用的人 | 体验、品质、方便 | 员工、孩子、老婆 |

典型分离场景：
- 桶装水企业采购：付费人(行政)关心价格，使用人(员工)关心水质
- 定制水送礼：付费人(送礼人)关心面子，使用人(收礼人)可能不使用

=== 搜前搜后覆盖（必须考虑）===
| 阶段 | 用户行为 | 关键词类型 | 画像内容偏好 |
|------|----------|------------|--------------|
| 搜前 | 问题探索 | 问题词、困惑词 | "XX怎么办"类内容 |
| 搜中 | 方案对比 | 品牌词、对比词 | "XX和XX哪个好"类内容 |
| 搜后 | 购买决策 | 价格词、使用词 | "XX多少钱"类内容 |

=== 画像生成要求 ===
请生成{count}个精准用户画像，每个画像必须包含以下全部字段：

1. **身份特征**
   - identity: 具体、可识别的人群描述（如"刚创业3个月的餐饮小店老板"）
   - identity_description: 详细的人群画像描述
   - customer_type: 本地居民/返乡人/在外本地人（三选一）
   - client_type: B端/C端（二选一）

2. **痛点场景**
   - pain_points: 具体、真实的痛苦场景
   - pain_point_level: high/medium/low
   - pain_scenarios: 痛点发生的具体场景

3. **心理画像**
   - psychology: 真实的内心独白
   - barriers: 阻碍行动的卡点

4. **付费人/使用人区分**
   - payer_role: 付费人角色（如"企业老板"）
   - payer_concerns: 付费人关注点
   - user_role: 使用人角色（如"企业员工"）
   - user_concerns: 使用人关注点

5. **搜索行为**
   - search_keywords: 用户真实搜索词（3-5个）
   - search_stage: awareness/consideration/decision

6. **内容偏好**
   - content_preferences: 适合该用户的内容方向
   - language_style: 口语化/专业术语/情绪化/温情型
   - crowd_perspective: 第一人称/第三人称/对话式

7. **决策特征**
   - decision_makers: 决策人列表（如"老板+行政"）
   - decision_stage: awareness/consideration/decision
   - conversion_cycle: 短(当天)/中(3天内)/长(7天+)

请用JSON格式输出：
{{
    "portraits": [
        {{
            "identity": "具体人群描述",
            "identity_description": "人群画像描述",
            "portrait_summary": "一句话总结：身份+问题+想转变+困境+深层需求",
            "customer_type": "本地居民/返乡人/在外本地人",
            "client_type": "B端/C端",
            "decision_makers": ["决策人1", "决策人2"],
            "pain_points": ["痛点1", "痛点2"],
            "pain_scenarios": ["场景1", "场景2"],
            "pain_point_level": "high/medium/low",
            "psychology": "内心独白",
            "barriers": ["障碍1", "障碍2"],
            "payer_role": "付费人角色",
            "payer_concerns": ["关注点1", "关注点2"],
            "user_role": "使用人角色",
            "user_concerns": ["关注点1", "关注点2"],
            "search_keywords": ["搜索词1", "搜索词2"],
            "search_stage": "awareness/consideration/decision",
            "content_preferences": ["内容方向1", "内容方向2"],
            "language_style": "口语化/专业术语/情绪化/温情型",
            "crowd_perspective": "第一人称/第三人称/对话式",
            "age_range": "26-35岁",
            "decision_stage": "awareness/consideration/decision",
            "conversion_cycle": "短(当天)/中(3天内)/长(7天+)"
        }}
    ]
}}"""

        return prompt

    def _parse_portraits(
        self,
        response: str,
        problem_type_name: str,
        problem_type_desc: str,
    ) -> List[Portrait]:
        """解析 LLM 返回的画像（7 层降级）"""

        import re

        def _extract_json_block(text: str) -> str:
            """从 markdown code block 中提取 JSON"""
            text = text.strip()
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
            if m:
                return m.group(1).strip()
            return text

        def _extract_array(text: str) -> str:
            """提取 [] 中的 JSON 数组"""
            m = re.search(r'\[\s*\{[\s\S]*\}\s*\]', text)
            return m.group() if m else ""

        def _build_portrait(raw: dict, idx: int) -> Portrait:
            p = raw if isinstance(raw, dict) else {}
            
            # 处理 payer_info 和 user_info
            payer_info = p.get('payer_info', {})
            user_info = p.get('user_info', {})
            
            # 如果是字符串形式的列表，尝试解析
            if isinstance(payer_info, str):
                try:
                    payer_info = json.loads(payer_info)
                except:
                    payer_info = {}
            
            if isinstance(user_info, str):
                try:
                    user_info = json.loads(user_info)
                except:
                    user_info = {}
            
            return Portrait(
                portrait_id=f"{problem_type_name}_{idx+1}",
                problem_type=problem_type_name,
                problem_type_description=p.get('problem_type_description') or p.get('problem_type') or problem_type_desc,
                identity=p.get('identity', ''),
                identity_description=p.get('identity_description', ''),
                portrait_summary=p.get('portrait_summary') or p.get('summary', ''),
                pain_points=p.get('pain_points') or [],
                pain_scenarios=p.get('pain_scenarios') or [],
                psychology=p.get('psychology') or {},
                barriers=p.get('barriers') or [],
                search_keywords=p.get('search_keywords') or [],
                content_preferences=p.get('content_preferences') or [],
                market_type=p.get('market_type', 'blue_ocean'),
                differentiation=p.get('differentiation', ''),
                # 增强字段（任务1.1新增）
                language_style=p.get('language_style', ''),
                crowd_perspective=p.get('crowd_perspective', ''),
                age_range=p.get('age_range', ''),
                pain_point_level=p.get('pain_point_level', 'medium'),
                decision_stage=p.get('decision_stage', 'consideration'),
                # 三类客户分类（任务1.2新增）
                customer_type=p.get('customer_type', ''),
                customer_subtype=p.get('customer_subtype', ''),
                # B端C端区分（任务1.2新增）
                client_type=p.get('client_type', ''),
                decision_makers=p.get('decision_makers') or [],
                # 付费人/使用人（任务1.2新增）
                payer_info=payer_info or {},
                user_info=user_info or {},
                is_payer_user_separated=p.get('is_payer_user_separated', False),
                # 搜前搜后阶段（任务1.2新增）
                search_stage=p.get('search_stage', ''),
                conversion_cycle=p.get('conversion_cycle', ''),
            )

        def _try_parse(text: str) -> List[Portrait]:
            text = text.strip()
            # 层 1：直接解析
            try:
                data = json.loads(text)
                if isinstance(data, dict) and 'portraits' in data:
                    return [_build_portrait(p, i) for i, p in enumerate(data['portraits'])]
            except (json.JSONDecodeError, TypeError):
                pass

            # 层 2：提取 code block
            block = _extract_json_block(text)
            try:
                data = json.loads(block)
                if isinstance(data, dict) and 'portraits' in data:
                    return [_build_portrait(p, i) for i, p in enumerate(data['portraits'])]
            except (json.JSONDecodeError, TypeError):
                pass

            # 层 3：提取 JSON 数组部分
            arr_text = _extract_array(text)
            if arr_text:
                try:
                    arr = json.loads(arr_text)
                    if isinstance(arr, list):
                        return [_build_portrait(p, i) for i, p in enumerate(arr)]
                except (json.JSONDecodeError, TypeError):
                    pass

            # 层 4：非贪婪匹配第一个 {...}
            m = re.search(r'\{[\s\S]*?\}', text)
            if m:
                try:
                    data = json.loads(m.group())
                    if isinstance(data, dict) and 'portraits' in data:
                        return [_build_portrait(p, i) for i, p in enumerate(data['portraits'])]
                except (json.JSONDecodeError, TypeError):
                    pass

            # 层 5：从文本中提取所有 {..."identity"...
            matches = re.findall(r'\{[^{}]*?"identity"[^{}]*\}', text)
            for raw in matches:
                try:
                    p = json.loads(raw)
                    return [_build_portrait(p, 0)]
                except (json.JSONDecodeError, TypeError):
                    continue

            # 层 6：逐行找可解析的 JSON 对象（兜底）
            lines = text.split('\n')
            for line in lines:
                line = line.strip().strip(',')
                if not line.startswith('{'):
                    continue
                try:
                    p = json.loads(line)
                    return [_build_portrait(p, 0)]
                except (json.JSONDecodeError, TypeError):
                    continue

            return []

        portraits = _try_parse(response)
        if not portraits:
            logger.warning("[PortraitGenerator] 7 层解析全部失败: %s", response[:300])

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
            business_info={'business_description': 'XX产品定制服务'},
            portraits_per_type=3,
        )
    """
    generator = PortraitGenerator()

    # 转换数据格式
    keyword_library = analysis_result.get('keyword_library', {})
    problem_types = analysis_result.get('problem_types', [])
    market_opportunities = analysis_result.get('market_opportunities', [])

    # 从蓝海机会中提取问题类型和场景（优先级更高）
    all_scenes = []
    all_problem_types = []
    for opp in market_opportunities:
        if isinstance(opp, dict):
            problem_types = opp.get('problem_types', [])
        else:
            problem_types = getattr(opp, 'problem_types', [])
        
        for pt in problem_types:
            if isinstance(pt, dict):
                scenes = pt.get('scenes', [])
            else:
                scenes = getattr(pt, 'scenes', [])
            
            # 收集问题类型
            if isinstance(pt, dict):
                all_problem_types.append({
                    'name': pt.get('name', ''),
                    'description': pt.get('description', ''),
                    'keywords': pt.get('keywords', []),
                    'scene_keywords': pt.get('scene_keywords', []),
                })
            else:
                all_problem_types.append({
                    'name': getattr(pt, 'name', ''),
                    'description': getattr(pt, 'description', ''),
                    'keywords': getattr(pt, 'keywords', []),
                    'scene_keywords': getattr(pt, 'scene_keywords', []),
                })
            
            # 收集场景（用于生成画像）
            for scene in scenes:
                if isinstance(scene, dict):
                    all_scenes.append({
                        'scene_name': scene.get('name', ''),
                        'scene_description': scene.get('description', ''),
                        'scene_keywords': scene.get('keywords', []),
                        'scene_target_audience': scene.get('target_audience', ''),
                    })
                else:
                    all_scenes.append({
                        'scene_name': getattr(scene, 'name', ''),
                        'scene_description': getattr(scene, 'description', ''),
                        'scene_keywords': getattr(scene, 'keywords', []),
                        'scene_target_audience': getattr(scene, 'target_audience', ''),
                    })
    
    # 如果没有从蓝海机会获取到场景，才使用旧的问题类型
    if not all_scenes and problem_types:
        for pt in problem_types:
            all_scenes.append({
                'scene_name': pt.get('type_name', '') or pt.get('name', ''),
                'scene_description': pt.get('description', ''),
                'scene_keywords': pt.get('keywords', []),
                'scene_target_audience': pt.get('target_audience', ''),
            })

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
                'differentiation': getattr(o, 'differentiation', ''),
                'problem_types': getattr(o, 'problem_types', []),
            }
            for o in market_opportunities
        ]

    context = PortraitGenerationContext(
        keyword_library=keyword_library,
        problem_types=all_problem_types or problem_types,  # 优先使用蓝海机会中的问题类型
        problem_scenes=all_scenes,  # 新增：使用蓝海机会中的问题场景
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
            # 增强字段（任务1.1新增）
            'language_style': p.language_style,
            'crowd_perspective': p.crowd_perspective,
            'age_range': p.age_range,
            'pain_point_level': p.pain_point_level,
            'decision_stage': p.decision_stage,
            # 三类客户分类（任务1.2新增）
            'customer_type': p.customer_type,
            'customer_subtype': p.customer_subtype,
            # B端C端区分（任务1.2新增）
            'client_type': p.client_type,
            'decision_makers': p.decision_makers,
            # 付费人/使用人（任务1.2新增）
            'payer_info': p.payer_info,
            'user_info': p.user_info,
            'is_payer_user_separated': p.is_payer_user_separated,
            # 搜前搜后阶段（任务1.2新增）
            'search_stage': p.search_stage,
            'conversion_cycle': p.conversion_cycle,
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


# ============================================================
# 增强版分组函数（任务1.2新增）
# ============================================================

def group_portraits_by_customer_type(
    portraits: List[Union['Portrait', Dict[str, Any]]]
) -> Dict[str, List[Union['Portrait', Dict[str, Any]]]]:
    """
    按三类客户分组画像

    Returns:
        {
            '本地居民': [portrait1, portrait2, ...],
            '返乡人': [portrait3, portrait4, ...],
            '在外本地人': [portrait5, portrait6, ...],
            '未分类': [...],
        }
    """
    from services.customer_type_classifier import CustomerTypeClassifier

    classifier = CustomerTypeClassifier()

    # 先为画像补充客户类型
    enriched_portraits = []
    for portrait in portraits:
        if isinstance(portrait, dict):
            enriched = classifier.enrich_portrait_with_customer_type(portrait)
        else:
            # Portrait对象转dict
            p_dict = {
                'identity': portrait.identity,
                'identity_description': portrait.identity_description,
                'pain_points': portrait.pain_points,
                'pain_scenarios': portrait.pain_scenarios,
                'barriers': portrait.barriers,
                'search_keywords': portrait.search_keywords,
                'portrait_summary': portrait.portrait_summary,
                'customer_type': portrait.customer_type,
            }
            enriched = classifier.enrich_portrait_with_customer_type(p_dict)
            # 如果原画像没有分类但 enriched 有，更新原画像
            if not portrait.customer_type and enriched.get('customer_type'):
                portrait.customer_type = enriched.get('customer_type', '')
            enriched_portraits.append(enriched)
            continue
        enriched_portraits.append(enriched)

    # 按客户类型分组
    grouped = {
        '本地居民': [],
        '返乡人': [],
        '在外本地人': [],
        '未分类': [],
    }

    for portrait, enriched in zip(portraits, enriched_portraits):
        customer_type = enriched.get('customer_type', '')
        if customer_type in grouped:
            grouped[customer_type].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


def group_portraits_by_client_type(
    portraits: List[Union['Portrait', Dict[str, Any]]]
) -> Dict[str, List[Union['Portrait', Dict[str, Any]]]]:
    """
    按B端/C端分组画像

    Returns:
        {
            'B端': [portrait1, portrait2, ...],
            'C端': [portrait3, portrait4, ...],
            '未分类': [...],
        }
    """
    from services.client_type_classifier import ClientTypeClassifier

    classifier = ClientTypeClassifier()

    # 先为画像补充B端C端
    enriched_portraits = []
    for portrait in portraits:
        if isinstance(portrait, dict):
            enriched = classifier.enrich_portrait_with_client_type(portrait)
        else:
            # Portrait对象转dict
            p_dict = {
                'identity': portrait.identity,
                'identity_description': portrait.identity_description,
                'pain_points': portrait.pain_points,
                'pain_scenarios': portrait.pain_scenarios,
                'barriers': portrait.barriers,
                'portrait_summary': portrait.portrait_summary,
                'client_type': portrait.client_type,
            }
            enriched = classifier.enrich_portrait_with_client_type(p_dict)
            # 如果原画像没有分类但 enriched 有，更新原画像
            if not portrait.client_type and enriched.get('client_type'):
                portrait.client_type = enriched.get('client_type', '')
            enriched_portraits.append(enriched)
            continue
        enriched_portraits.append(enriched)

    # 按B端C端分组
    grouped = {
        'B端': [],
        'C端': [],
        '未分类': [],
    }

    for portrait, enriched in zip(portraits, enriched_portraits):
        client_type = enriched.get('client_type', '')
        if client_type in grouped:
            grouped[client_type].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


def group_portraits_by_payer_user_separation(
    portraits: List[Union['Portrait', Dict[str, Any]]]
) -> Dict[str, List[Union['Portrait', Dict[str, Any]]]]:
    """
    按付费人/使用人是否分离分组画像

    Returns:
        {
            '分离': [portrait1, portrait2, ...],
            '未分离': [portrait3, portrait4, ...],
            '未分类': [...],
        }
    """
    from services.payer_user_classifier import PayerUserClassifier

    classifier = PayerUserClassifier()

    # 先为画像补充付费人/使用人信息
    enriched_portraits = []
    for portrait in portraits:
        if isinstance(portrait, dict):
            enriched = classifier.enrich_portrait_with_payer_user(portrait)
        else:
            # Portrait对象转dict
            p_dict = {
                'identity': portrait.identity,
                'pain_points': portrait.pain_points,
                'barriers': portrait.barriers,
                'portrait_summary': portrait.portrait_summary,
                'payer_info': portrait.payer_info,
                'user_info': portrait.user_info,
                'is_payer_user_separated': portrait.is_payer_user_separated,
            }
            enriched = classifier.enrich_portrait_with_payer_user(p_dict)
            # 如果原画像没有但 enriched 有，更新原画像
            if not portrait.is_payer_user_separated and enriched.get('is_payer_user_separated') is not None:
                portrait.is_payer_user_separated = enriched.get('is_payer_user_separated', False)
                portrait.payer_info = enriched.get('payer_info', {})
                portrait.user_info = enriched.get('user_info', {})
            enriched_portraits.append(enriched)
            continue
        enriched_portraits.append(enriched)

    # 按是否分离分组
    grouped = {
        '分离': [],
        '未分离': [],
        '未分类': [],
    }

    for portrait, enriched in zip(portraits, enriched_portraits):
        is_separated = enriched.get('is_payer_user_separated')
        if is_separated is True:
            grouped['分离'].append(portrait)
        elif is_separated is False:
            grouped['未分离'].append(portrait)
        else:
            grouped['未分类'].append(portrait)

    # 清理空分组
    return {k: v for k, v in grouped.items() if v}


def generate_portraits_with_all_enrichments(
    context: PortraitGenerationContext,
    enable_customer_type: bool = True,
    enable_client_type: bool = True,
    enable_payer_user: bool = True,
) -> List[Portrait]:
    """
    生成画像并自动进行所有增强

    Args:
        context: 画像生成上下文
        enable_customer_type: 是否启用三类客户分类
        enable_client_type: 是否启用B端C端分类
        enable_payer_user: 是否启用付费人/使用人区分

    Returns:
        增强后的画像列表

    Usage:
        from services.portrait_generator import generate_portraits_with_all_enrichments, PortraitGenerationContext

        portraits = generate_portraits_with_all_enrichments(
            context=PortraitGenerationContext(
                keyword_library=keyword_library,
                problem_types=problem_types,
                business_info=business_info,
                portraits_per_type=3,
            ),
            enable_customer_type=True,
            enable_client_type=True,
            enable_payer_user=True,
        )
    """
    from services.customer_type_classifier import CustomerTypeClassifier
    from services.client_type_classifier import ClientTypeClassifier
    from services.payer_user_classifier import PayerUserClassifier

    # 1. 生成基础画像
    generator = PortraitGenerator()
    portraits = generator.generate_portraits(context)

    # 2. 初始化分类器
    customer_classifier = CustomerTypeClassifier()
    client_classifier = ClientTypeClassifier()
    payer_user_classifier = PayerUserClassifier()

    # 3. 遍历增强每个画像
    enhanced_portraits = []
    for portrait in portraits:
        portrait_dict = _portrait_to_dict(portrait)

        if enable_customer_type:
            portrait_dict = customer_classifier.enrich_portrait_with_customer_type(portrait_dict)

        if enable_client_type:
            portrait_dict = client_classifier.enrich_portrait_with_client_type(portrait_dict)

        if enable_payer_user:
            portrait_dict = payer_user_classifier.enrich_portrait_with_payer_user(portrait_dict)

        # 4. 转回 Portrait 对象
        enhanced = _dict_to_portrait(portrait_dict, portrait.portrait_id, portrait.problem_type)
        enhanced_portraits.append(enhanced)

    return enhanced_portraits


def _portrait_to_dict(portrait: Portrait) -> Dict[str, Any]:
    """Portrait对象转字典"""
    return {
        'portrait_id': portrait.portrait_id,
        'problem_type': portrait.problem_type,
        'problem_type_description': portrait.problem_type_description,
        'identity': portrait.identity,
        'identity_description': portrait.identity_description,
        'pain_points': portrait.pain_points,
        'pain_scenarios': portrait.pain_scenarios,
        'psychology': portrait.psychology,
        'barriers': portrait.barriers,
        'search_keywords': portrait.search_keywords,
        'content_preferences': portrait.content_preferences,
        'market_type': portrait.market_type,
        'differentiation': portrait.differentiation,
        'portrait_summary': portrait.portrait_summary,
        'scene_tags': portrait.scene_tags,
        'behavior_tags': portrait.behavior_tags,
        'content_direction': portrait.content_direction,
        'language_style': portrait.language_style,
        'crowd_perspective': portrait.crowd_perspective,
        'age_range': portrait.age_range,
        'pain_point_level': portrait.pain_point_level,
        'decision_stage': portrait.decision_stage,
        'customer_type': portrait.customer_type,
        'customer_subtype': portrait.customer_subtype,
        'client_type': portrait.client_type,
        'decision_makers': portrait.decision_makers,
        'payer_info': portrait.payer_info,
        'user_info': portrait.user_info,
        'is_payer_user_separated': portrait.is_payer_user_separated,
        'search_stage': portrait.search_stage,
        'conversion_cycle': portrait.conversion_cycle,
    }


def _dict_to_portrait(data: Dict[str, Any], portrait_id: str, problem_type: str) -> Portrait:
    """字典转Portrait对象"""
    return Portrait(
        portrait_id=portrait_id,
        problem_type=problem_type,
        problem_type_description=data.get('problem_type_description', ''),
        identity=data.get('identity', ''),
        identity_description=data.get('identity_description', ''),
        pain_points=data.get('pain_points') or [],
        pain_scenarios=data.get('pain_scenarios') or [],
        psychology=data.get('psychology') or {},
        barriers=data.get('barriers') or [],
        search_keywords=data.get('search_keywords') or [],
        content_preferences=data.get('content_preferences') or [],
        market_type=data.get('market_type', 'blue_ocean'),
        differentiation=data.get('differentiation', ''),
        portrait_summary=data.get('portrait_summary', ''),
        scene_tags=data.get('scene_tags') or [],
        behavior_tags=data.get('behavior_tags') or [],
        content_direction=data.get('content_direction', '种草型'),
        language_style=data.get('language_style', ''),
        crowd_perspective=data.get('crowd_perspective', ''),
        age_range=data.get('age_range', ''),
        pain_point_level=data.get('pain_point_level', 'medium'),
        decision_stage=data.get('decision_stage', 'consideration'),
        customer_type=data.get('customer_type', ''),
        customer_subtype=data.get('customer_subtype', ''),
        client_type=data.get('client_type', ''),
        decision_makers=data.get('decision_makers') or [],
        payer_info=data.get('payer_info') or {},
        user_info=data.get('user_info') or {},
        is_payer_user_separated=data.get('is_payer_user_separated', False),
        search_stage=data.get('search_stage', ''),
        conversion_cycle=data.get('conversion_cycle', ''),
    )
