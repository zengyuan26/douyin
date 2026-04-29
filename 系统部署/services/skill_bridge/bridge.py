"""
SkillBridge — 对外统一接口

封装 SkillExecutor，对外提供简洁的业务级 API。
使用者无需了解配置细节，直接调用业务方法即可。
"""

import logging
from typing import Any, Dict, List, Optional

from .registry import SkillRegistry
from .executor import SkillExecutor, SkillExecutionResult

logger = logging.getLogger(__name__)


class SkillBridge:
    """
    Skill Bridge — 对外统一接口（单例）

    使用示例：
        from services.skill_bridge import SkillBridge

        bridge = SkillBridge()
        result = bridge.execute_market_analyzer(
            business_description="卖奶粉",
            industry="奶粉",
            business_type="b2c",
        )
        print(result.success, result.full_output)
    """

    _instance: Optional['SkillBridge'] = None

    def __new__(cls, llm_call_func=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, llm_call_func=None):
        if self._initialized:
            return
        self._initialized = True

        if llm_call_func is None:
            from services.llm import get_llm_service
            llm_service = get_llm_service()
            self._llm_service = llm_service
            self._llm_call = None
        else:
            self._llm_service = None
            self._llm_call = llm_call_func

        self._registry = SkillRegistry()
        self._executor = SkillExecutor(self._llm_call, llm_service=self._llm_service)

    # -------------------------------------------------------------------------
    # 业务 API
    # -------------------------------------------------------------------------

    def execute_market_analyzer(
        self,
        business_description: str,
        industry: str,
        business_type: str,
        service_scenario: Optional[str] = None,
        skip_steps: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
    ) -> SkillExecutionResult:
        """
        执行市场分析 skill（行业7步诊断法）。

        Args:
            business_description: 业务描述，如"卖奶粉"
            industry: 行业，如"奶粉"
            business_type: 业务类型，"b2b" | "b2c" | "both"
            service_scenario: 服务场景（可选）
            skip_steps: 跳过的步骤 ID
            max_steps: 最多执行前 N 个步骤

        Returns:
            SkillExecutionResult
        """
        manual_inputs = {
            "business_description": business_description,
            "industry": industry,
            "business_type": business_type,
        }
        if service_scenario:
            manual_inputs["service_scenario"] = service_scenario

        return self._executor.execute_skill(
            "market_analyzer",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
            max_steps=max_steps,
        )

    def execute_keyword_library(
        self,
        business_description: str,
        industry: str,
        business_type: str,
        market_analyzer_output: Optional[dict] = None,
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行关键词库生成 skill。

        如果传入了 market_analyzer_output，会自动映射：
          step3_audience_segment   → keyword_library.input.paying_equals_using
          step4_search_journey    → keyword_library.input.search_journey
        """
        outputs = {}
        if market_analyzer_output:
            outputs["market_analyzer"] = market_analyzer_output

        manual_inputs = {
            "business_description": business_description,
            "industry": industry,
            "business_type": business_type,
        }

        return self._executor.execute_skill(
            "keyword_library_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_topic_library(
        self,
        industry: Optional[str] = None,
        business_description: Optional[str] = None,
        keyword_library_output: Optional[dict] = None,
        market_analyzer_output: Optional[dict] = None,
        content_stage: str = "成长阶段",
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行选题库生成 skill。

        自动映射上游输出：
          market_analyzer.step3_audience_segment  → input.audience_segment
          market_analyzer.step6_search_journey   → input.search_journey
          keyword_library.blue_ocean.L2_long_tail → input.blue_ocean_long_tail
          keyword_library.priority_keywords       → input.priority_keywords
        """
        outputs = {}
        if market_analyzer_output:
            outputs["market_analyzer"] = market_analyzer_output
        if keyword_library_output:
            outputs["keyword_library_generator"] = keyword_library_output

        manual_inputs = {
            "content_stage": content_stage,
        }
        if industry:
            manual_inputs["industry"] = industry
        if business_description:
            manual_inputs["business_description"] = business_description

        return self._executor.execute_skill(
            "topic_library_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_portrait_generator(
        self,
        industry: str,
        business_description: str,
        business_type: str,
        keyword_library: Optional[dict] = None,
        market_analyzer_output: Optional[dict] = None,
        portraits_per_type: int = 3,
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行画像生成 skill。

        自动映射上游输出：
          market_analyzer.step3_audience_segment  → input.audience_segment
          market_analyzer.step2_blue_ocean        → input.blue_ocean_opportunities
          market_analyzer.step6_search_journey    → input.search_journey
        """
        outputs = {}
        if market_analyzer_output:
            outputs["market_analyzer"] = market_analyzer_output

        manual_inputs = {
            "industry": industry,
            "business_description": business_description,
            "business_type": business_type,
            "keyword_library": keyword_library or {},
            "portraits_per_type": portraits_per_type,
        }

        return self._executor.execute_skill(
            "portrait_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_content_generator(
        self,
        topic_id: str,
        topic_title: str,
        topic_type: str,
        business_description: str,
        topic_type_key: str = "",
        portrait: Optional[dict] = None,
        brand_context: Optional[dict] = None,
        keyword_library: Optional[dict] = None,
        selected_scene: Optional[dict] = None,
        content_style: str = "",
        business_range: str = "",
        business_type: str = "",
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行内容生成 skill。

        自动映射上游输出：
          topic_library 输出 → 选题信息和五段式规划
          portrait_generator 输出 → 画像信息
        """
        manual_inputs = {
            "topic_id": topic_id,
            "topic_title": topic_title,
            "topic_type": topic_type,
            "business_description": business_description,
        }
        if topic_type_key:
            manual_inputs["topic_type_key"] = topic_type_key
        if portrait:
            manual_inputs["portrait"] = portrait
        # [DEBUG] 始终传入，确保 prompt 填充不缺占位符
        manual_inputs["brand_context"] = brand_context if brand_context else {}
        manual_inputs["keyword_library"] = keyword_library if keyword_library else {}
        if selected_scene:
            manual_inputs["selected_scene"] = selected_scene
            # 从 selected_scene 提取 geo_mode（dim_value 如"初级"对应 GEO 模式）
            geo_from_scene = selected_scene.get('dim_value', '') or selected_scene.get('label', '')
            if geo_from_scene:
                manual_inputs["geo_mode"] = geo_from_scene
        if content_style:
            manual_inputs["content_style"] = content_style
        if business_range:
            manual_inputs["business_range"] = business_range
        if business_type:
            manual_inputs["business_type"] = business_type

        return self._executor.execute_skill(
            "content_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_video_script_generator(
        self,
        topic_id: str,
        topic_title: str,
        topic_type: str,
        business_description: str,
        topic_type_key: str = "",
        portrait: Optional[dict] = None,
        brand_context: Optional[dict] = None,
        keyword_library: Optional[dict] = None,
        selected_scene: Optional[dict] = None,
        content_style: str = "",
        business_range: str = "",
        business_type: str = "",
        structure_id: str = "",
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行短视频脚本生成 skill。

        自动映射上游输出：
          topic_library 输出 → 选题信息
          portrait_generator 输出 → 画像信息
          keyword_library 输出 → 信任关键词
        """
        manual_inputs = {
            "topic_id": topic_id,
            "topic_title": topic_title,
            "topic_type": topic_type,
            "business_description": business_description,
        }
        if topic_type_key:
            manual_inputs["topic_type_key"] = topic_type_key
        if portrait:
            manual_inputs["portrait"] = portrait
        if brand_context:
            manual_inputs["brand_context"] = brand_context
        if keyword_library:
            manual_inputs["keyword_library"] = keyword_library
        if selected_scene:
            manual_inputs["selected_scene"] = selected_scene
        if content_style:
            manual_inputs["content_style"] = content_style
        if business_range:
            manual_inputs["business_range"] = business_range
        if business_type:
            manual_inputs["business_type"] = business_type
        if structure_id:
            manual_inputs["structure_id"] = structure_id

        return self._executor.execute_skill(
            "video_script_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_long_text_generator(
        self,
        topic_id: str,
        topic_title: str,
        topic_type: str,
        business_description: str,
        topic_type_key: str = "",
        portrait: Optional[dict] = None,
        brand_context: Optional[dict] = None,
        keyword_library: Optional[dict] = None,
        selected_scene: Optional[dict] = None,
        content_style: str = "",
        business_range: str = "",
        business_type: str = "",
        template_id: str = "",
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行长文内容生成 skill。

        自动映射上游输出：
          topic_library 输出 → 选题信息
          portrait_generator 输出 → 画像信息
          keyword_library 输出 → 信任关键词
        """
        manual_inputs = {
            "topic_id": topic_id,
            "topic_title": topic_title,
            "topic_type": topic_type,
            "business_description": business_description,
        }
        if topic_type_key:
            manual_inputs["topic_type_key"] = topic_type_key
        if portrait:
            manual_inputs["portrait"] = portrait
        if brand_context:
            manual_inputs["brand_context"] = brand_context
        if keyword_library:
            manual_inputs["keyword_library"] = keyword_library
        if selected_scene:
            manual_inputs["selected_scene"] = selected_scene
        if content_style:
            manual_inputs["content_style"] = content_style
        if business_range:
            manual_inputs["business_range"] = business_range
        if business_type:
            manual_inputs["business_type"] = business_type
        if template_id:
            manual_inputs["template_id"] = template_id

        return self._executor.execute_skill(
            "long_text_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_psychology_reviewer(
        self,
        content: dict,
        portrait: Optional[dict] = None,
        brand_context: Optional[dict] = None,
        content_purpose: str = "traffic",
        business_type: str = "",
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行心理学审核 skill。

        在内容生成后调用，审核内容的消费心理学驱动效果，
        评估6大心理维度并给出增强建议。
        """
        manual_inputs = {
            "content": content,
            "content_purpose": content_purpose,
        }
        if portrait:
            manual_inputs["portrait"] = portrait
        if brand_context:
            manual_inputs["brand_context"] = brand_context
        if business_type:
            manual_inputs["business_type"] = business_type

        return self._executor.execute_skill(
            "psychology_reviewer",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_title_generator(
        self,
        topic_title: str,
        portrait: Optional[dict] = None,
        keywords: Optional[dict] = None,
        geo_mode: str = "",
        industry: str = "",
        num_variants: int = 4,
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行 H-V-F 标题生成 skill。

        生成4种模式（A/B/C/D）的标题，并自动评分。
        """
        manual_inputs = {
            "topic_title": topic_title,
        }
        if portrait:
            manual_inputs["portrait"] = portrait
        if keywords:
            manual_inputs["keywords"] = keywords
        if geo_mode:
            manual_inputs["geo_mode"] = geo_mode
        if industry:
            manual_inputs["industry"] = industry
        manual_inputs["num_variants"] = num_variants

        return self._executor.execute_skill(
            "title_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_tag_generator(
        self,
        topic_title: str,
        industry: str = "",
        keywords: Optional[dict] = None,
        portrait: Optional[dict] = None,
        geo_mode: str = "",
        max_tags: int = 8,
        skip_steps: Optional[List[str]] = None,
    ) -> SkillExecutionResult:
        """
        执行金字塔标签生成 skill。

        生成三层标签（公域+垂直+长尾）。
        """
        manual_inputs = {
            "topic_title": topic_title,
        }
        if industry:
            manual_inputs["industry"] = industry
        if keywords:
            manual_inputs["keywords"] = keywords
        if portrait:
            manual_inputs["portrait"] = portrait
        if geo_mode:
            manual_inputs["geo_mode"] = geo_mode
        manual_inputs["max_tags"] = max_tags

        return self._executor.execute_skill(
            "tag_generator",
            manual_inputs=manual_inputs,
            skip_steps=skip_steps,
        )

    def execute_full_pipeline(
        self,
        business_description: str,
        industry: str,
        business_type: str,
        service_scenario: Optional[str] = None,
        content_stage: str = "成长阶段",
    ) -> Dict[str, Any]:
        """
        执行完整流水线：市场分析 → 关键词库 → 选题库

        Returns:
            {
                "market_analyzer": SkillExecutionResult,
                "keyword_library": SkillExecutionResult,
                "topic_library": SkillExecutionResult,
            }
        """
        results = {}

        # Step 1: 市场分析
        logger.info("[SkillBridge] 执行市场分析...")
        market_result = self.execute_market_analyzer(
            business_description=business_description,
            industry=industry,
            business_type=business_type,
            service_scenario=service_scenario,
        )
        results["market_analyzer"] = market_result

        if not market_result.success:
            logger.warning("[SkillBridge] 市场分析失败，终止流水线")
            return results

        # Step 2: 关键词库（传入市场分析输出，自动数据映射）
        logger.info("[SkillBridge] 执行关键词库生成...")
        keyword_result = self.execute_keyword_library(
            business_description=business_description,
            industry=industry,
            business_type=business_type,
            market_analyzer_output=market_result.full_output,
        )
        results["keyword_library"] = keyword_result

        # Step 3: 选题库（传入关键词库输出，自动数据映射）
        logger.info("[SkillBridge] 执行选题库生成...")
        topic_result = self.execute_topic_library(
            industry=industry,
            business_description=business_description,
            keyword_library_output=keyword_result.full_output,
            market_analyzer_output=market_result.full_output,
            content_stage=content_stage,
        )
        results["topic_library"] = topic_result

        return results

    # -------------------------------------------------------------------------
    # 通用执行
    # -------------------------------------------------------------------------

    def execute(
        self,
        skill_name: str,
        manual_inputs: Optional[dict] = None,
        skip_steps: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
    ) -> SkillExecutionResult:
        """
        通用执行接口，直接指定 skill 名称。

        Args:
            skill_name: skill 配置名称（config/*.json 的文件名）
            manual_inputs: 手动输入变量
            skip_steps: 跳过的步骤
            max_steps: 最多执行前 N 步
        """
        return self._executor.execute_skill(
            skill_name,
            manual_inputs=manual_inputs or {},
            skip_steps=skip_steps,
            max_steps=max_steps,
        )

    # -------------------------------------------------------------------------
    # 元信息查询
    # -------------------------------------------------------------------------

    def list_skills(self) -> List[str]:
        """列出所有已加载的 skill"""
        return self._registry.list_skills()

    def get_skill_info(self, skill_name: str) -> Optional[dict]:
        """获取 skill 信息"""
        return self._registry.get_skill_meta(skill_name)

    def get_skill_steps(self, skill_name: str) -> List[dict]:
        """获取 skill 的步骤列表（按顺序）"""
        return self._registry.get_steps_ordered(skill_name)

    # -------------------------------------------------------------------------
    # 热重载
    # -------------------------------------------------------------------------

    def reload(self, skill_name: Optional[str] = None):
        """热重载配置"""
        self._registry.reload(skill_name)
        logger.info(f"[SkillBridge] 热重载完成: {skill_name or '全部'}")
