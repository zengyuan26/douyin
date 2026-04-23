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
        """构建基于场景的画像生成Prompt"""

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
                if isinstance(opp, dict):
                    opp_name = opp.get('opportunity_name', '')
                    business_dir = opp.get('business_direction', '')
                    opp_audience = opp.get('target_audience', '')
                    opp_diff = opp.get('differentiation', '')
                else:
                    opp_name = getattr(opp, 'opportunity_name', '')
                    business_dir = getattr(opp, 'business_direction', '')
                    opp_audience = getattr(opp, 'target_audience', '')
                    opp_diff = getattr(opp, 'differentiation', '')

                dir_text = f"（核心业务：{business_dir}）" if business_dir else ""
                diff_text = f"差异化：{opp_diff}" if opp_diff else ""
                opp_list.append(
                    f"- {opp_name}{dir_text}\n  人群：{opp_audience}\n  {diff_text}"
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

=== 市场机会 ===
{opportunities_text or '暂无市场机会数据'}

=== 关键词库（参考）===
蓝海关键词（细分方向）：{', '.join(blue_ocean_kw[:10]) if blue_ocean_kw else '暂无'}
红海关键词（竞争方向）：{', '.join(red_ocean_kw[:5]) if red_ocean_kw else '暂无'}

=== 画像生成要求 ===
请生成{count}个精准用户画像，每个画像要求：

1. **身份特征**：具体、可识别的人群描述（如"刚创业3个月的餐饮小店老板"）
2. **痛点场景**：具体的、真实的痛苦场景（如"店面刚装修完发现排烟不畅，改造成本又超预算了"）
3. **心理状态**：真实的内心独白（如"每天忙得焦头烂额，效果还是不见起色"）
4. **行为障碍**：阻碍用户行动的卡点（如"不知道该怎么选设备方案"）
5. **搜索关键词**：用户真实搜索词（3-5个）
6. **内容偏好**：适合该用户的内容方向

请用JSON格式输出：
{{
    "portraits": [
        {{
            "identity": "具体人群描述",
            "identity_description": "人群画像描述",
            "portrait_summary": "一句话总结",
            "pain_points": ["痛点1", "痛点2"],
            "pain_scenarios": ["场景1", "场景2"],
            "psychology": "内心独白",
            "barriers": ["障碍1", "障碍2"],
            "search_keywords": ["搜索词1", "搜索词2"],
            "content_preferences": ["内容方向1", "内容方向2"]
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
                'business_direction': getattr(o, 'business_direction', ''),
                'target_audience': o.target_audience,
                'pain_points': o.pain_points,
                'keywords': o.keywords,
                'content_direction': o.content_direction,
                'market_type': o.market_type,
                'confidence': o.confidence,
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
