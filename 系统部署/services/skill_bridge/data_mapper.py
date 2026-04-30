"""
DataMapper — 数据映射器

负责：
1. 点号路径的 get/set 操作（支持嵌套字典）
2. 基于配置文件中的 data_flow，将上游 skill 输出映射到下游 skill 输入
3. 构建完整的输入上下文（整合所有上游输出 + 手动输入）
"""

from typing import Any, Dict, Optional


class DataMapper:
    """
    数据映射器

    使用示例：
        mapper = DataMapper(registry)
        mapped = mapper.map_output_to_input(
            from_skill="market_analyzer",
            output_data={"step3_audience_segment": {...}},
            to_skill="keyword_library_generator"
        )
    """

    def __init__(self, registry):
        self.registry = registry

    # ------------------------------------------------------------------
    # 路径操作
    # ------------------------------------------------------------------

    @staticmethod
    def get_nested(data: dict, path: str) -> Any:
        """
        获取嵌套字典中的值，支持点号路径。

        Examples:
            get_nested({"a": {"b": 1}}, "a.b")      → 1
            get_nested({"a": [0, 1]}, "a.1")         → 1
            get_nested({"a": {"b": 1}}, "a.c")      → None
        """
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list):
                try:
                    value = value[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return value

    @staticmethod
    def set_nested(data: dict, path: str, value: Any):
        """
        设置嵌套字典中的值，支持点号路径（自动创建中间节点）。

        Examples:
            set_nested({}, "a.b", 1)   → {"a": {"b": 1}}
            set_nested({}, "a.0", 1)   → {"a": [1]}
        """
        keys = path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current:
                # 尝试判断：如果下一个 key 是数字，则创建 list
                next_key = keys[keys.index(key) + 1]
                current[key] = [] if next_key.isdigit() else {}
            current = current[key]
        current[keys[-1]] = value

    # ------------------------------------------------------------------
    # 数据流映射
    # ------------------------------------------------------------------

    def map_output_to_input(
        self,
        from_skill: str,
        output_data: dict,
        to_skill: str
    ) -> dict:
        """
        将 from_skill 的输出映射到 to_skill 的输入。

        基于配置文件中的 data_flow.outputs 定义，只映射 target == to_skill 的字段。

        Returns:
            映射后的输入字典（可能为空）
        """
        data_flow = self.registry.get_data_flow(from_skill)
        if not data_flow:
            return {}

        mapped_input = {}

        for output_path, flow_config in data_flow.items():
            target = flow_config.get("target")
            if target != to_skill:
                continue

            field = flow_config.get("field")
            value = self.get_nested(output_data, output_path)

            if value is not None:
                self.set_nested(mapped_input, field, value)

        return mapped_input

    # ------------------------------------------------------------------
    # 上下文构建
    # ------------------------------------------------------------------

    def build_input_context(
        self,
        skill_name: str,
        outputs: Dict[str, dict]
    ) -> dict:
        """
        构建完整的输入上下文。

        整合：
        - 上游 skill 的输出（根据 input_schema 的 from_step 映射）
        - 同 skill 内前序步骤的输出（支持 <<step_xxx>> 链式引用）
        - 手动输入（由调用方在 executor 中 update）

        Returns:
            完整的上下文字典，键名与 skill 配置中的变量名一致
        """
        context = {}

        # ── 1. 上游 skill 输出（跨 skill 引用）───────────────────────────────
        input_schema = self.registry.get_input_schema(skill_name)
        if input_schema:
            for field_name, field_config in input_schema.items():
                from_step = field_config.get("from_step")
                if not from_step:
                    continue

                parts = from_step.split(".", 1)
                from_skill = parts[0]
                from_path = parts[1] if len(parts) > 1 else None

                # 如果是同 skill 内的步骤引用（e.g. "title_generator.step_hvf_analysis"）
                # 特殊处理：from_skill == skill_name 时，直接从 outputs[skill_name] 取
                if from_skill == skill_name:
                    skill_outputs = outputs.get(skill_name, {})
                    if from_path:
                        value = self.get_nested(skill_outputs, from_path)
                    else:
                        value = skill_outputs
                    if value is not None:
                        context[field_name] = value
                    continue

                if from_skill not in outputs:
                    continue

                output_data = outputs[from_skill]
                if from_path:
                    value = self.get_nested(output_data, from_path)
                else:
                    value = output_data

                if value is not None:
                    context[field_name] = value

        # ── 2. 同 skill 内前序步骤输出（链式引用 <<step_xxx>>）─────────────
        # 注入前序步骤的输出，键名为步骤 ID，供链式 prompt 引用
        # 例如：tag_generator 的 step_tag_generate 可以引用 <<step_tier_analysis>>
        skill_outputs = outputs.get(skill_name, {})
        for step_id, step_output in skill_outputs.items():
            if isinstance(step_output, dict):
                context[step_id] = step_output
            elif step_output is not None:
                context[step_id] = step_output

        return context

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def flatten_schema(schema: dict, prefix: str = "") -> Dict[str, dict]:
        """
        将嵌套 schema 展平为点号路径。

        Examples:
            flatten_schema({"a": {"type": "string"}}, "")
                → {"a": {"type": "string"}}
            flatten_schema({"a": {"b": {"type": "string"}}}, "")
                → {"a.b": {"type": "string"}}
        """
        result = {}
        for key, value in schema.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and "type" in value:
                result[path] = value
            elif isinstance(value, dict):
                result.update(DataMapper.flatten_schema(value, path))
        return result

    # ===========================================================================
    # 增强映射方法（任务2.2新增）
    # ===========================================================================

    def map_portrait_to_content(self, portrait: dict) -> dict:
        """
        将画像数据映射为内容生成所需的上下文格式。

        提取并转换画像中的关键信息，供 content_generator / graphic_skill 使用。

        Args:
            portrait: 画像数据字典

        Returns:
            dict: 内容生成所需的画像上下文
        """
        if not portrait:
            return {}

        # 基础信息
        result = {
            'identity': portrait.get('identity', ''),
            'identity_description': portrait.get('identity_description', ''),
            'portrait_summary': portrait.get('portrait_summary', ''),
        }

        # 增强字段（任务1.1新增）
        result['language_style'] = portrait.get('language_style', '')
        result['crowd_perspective'] = portrait.get('crowd_perspective', '')
        result['age_range'] = portrait.get('age_range', '')
        result['pain_point_level'] = portrait.get('pain_point_level', 'medium')
        result['decision_stage'] = portrait.get('decision_stage', 'consideration')

        # 痛点信息
        pain_points = portrait.get('pain_points', [])
        if isinstance(pain_points, list):
            result['pain_points'] = pain_points
            result['main_pain_point'] = pain_points[0] if pain_points else ''
        else:
            result['pain_points'] = []
            result['main_pain_point'] = ''

        # 痛点场景
        pain_scenarios = portrait.get('pain_scenarios', [])
        if isinstance(pain_scenarios, list):
            result['pain_scenarios'] = pain_scenarios
            result['main_scenario'] = pain_scenarios[0] if pain_scenarios else ''
        else:
            result['pain_scenarios'] = []
            result['main_scenario'] = ''

        # 心理画像
        psychology = portrait.get('psychology', {})
        if isinstance(psychology, dict):
            result['psychology'] = psychology
            result['inner_voice'] = psychology.get('inner_voice', '')
            result['core_needs'] = psychology.get('core_needs', [])
            result['purchase_motivation'] = psychology.get('purchase_motivation', '')
        else:
            result['psychology'] = {}
            result['inner_voice'] = ''
            result['core_needs'] = []
            result['purchase_motivation'] = ''

        # 购买顾虑
        barriers = portrait.get('barriers', [])
        if isinstance(barriers, list):
            result['barriers'] = barriers
        else:
            result['barriers'] = []

        # 搜索关键词
        search_keywords = portrait.get('search_keywords', [])
        if isinstance(search_keywords, list):
            result['search_keywords'] = search_keywords
        else:
            result['search_keywords'] = []

        # 内容偏好
        content_preferences = portrait.get('content_preferences', [])
        if isinstance(content_preferences, list):
            result['content_preferences'] = content_preferences
        else:
            result['content_preferences'] = []

        # 标签
        result['scene_tags'] = portrait.get('scene_tags', [])
        result['behavior_tags'] = portrait.get('behavior_tags', [])

        # 内容方向
        result['content_direction'] = portrait.get('content_direction', '种草型')

        # 市场定位
        result['market_type'] = portrait.get('market_type', 'blue_ocean')
        result['differentiation'] = portrait.get('differentiation', '')

        return result

    def map_topic_to_content(self, topic: dict) -> dict:
        """
        将选题数据映射为内容生成所需的上下文格式。

        Args:
            topic: 选题数据字典

        Returns:
            dict: 内容生成所需的选题上下文
        """
        if not topic:
            return {}

        result = {
            'topic_id': topic.get('id', topic.get('topic_id', '')),
            'title': topic.get('title', ''),
            'type_key': topic.get('type_key', ''),
            'type_name': topic.get('type_name', ''),
            'stage_key': topic.get('stage_key', ''),
            'stage_name': topic.get('stage_name', ''),
            'priority': topic.get('priority', ''),
            'keywords': topic.get('keywords', []),
            'recommended_reason': topic.get('recommended_reason', ''),
        }

        # 增强字段（任务1.2新增）
        result['scene_details'] = topic.get('scene_details', [])
        result['core_value'] = topic.get('core_value', '')
        result['content_format'] = topic.get('content_format', '种草')
        result['emotion_curve'] = topic.get('emotion_curve', '')

        # 五段式阶段
        result['content_direction'] = topic.get('content_direction', '种草型')

        return result

    def map_keyword_to_content(self, keyword_library: dict) -> dict:
        """
        将关键词库数据映射为内容生成所需的上下文格式。

        Args:
            keyword_library: 关键词库数据

        Returns:
            dict: 内容生成所需的关键词库上下文
        """
        if not keyword_library:
            return {}

        result = {
            'keyword_core': keyword_library.get('keyword_core', ''),
            'total_keywords': keyword_library.get('total_keywords', 0),
        }

        # 增强字段（任务1.3新增）
        result['geo_score'] = keyword_library.get('geo_score', {})
        result['trust_keywords'] = keyword_library.get('trust_keywords', [])
        result['data_sources'] = keyword_library.get('data_sources', [])

        # 扁平关键词字段
        for field in ['problem_type_keywords', 'pain_point_keywords', 'scene_keywords',
                      'concern_keywords', 'direct_demand_keywords', 'trust_keywords']:
            if field in keyword_library:
                result[field] = keyword_library[field]

        # 分类关键词
        categories = keyword_library.get('categories', [])
        if isinstance(categories, list):
            result['categories_count'] = len(categories)
            result['category_names'] = [c.get('category_name', '') for c in categories if isinstance(c, dict)]
        else:
            result['categories_count'] = 0
            result['category_names'] = []

        return result

    def build_content_context(
        self,
        topic: dict,
        portrait: dict,
        keyword_library: dict,
        business_info: dict = None,
    ) -> dict:
        """
        构建完整的图文内容生成上下文。

        整合选题、画像、关键词库和业务信息，为 content_generator / graphic_skill 提供完整输入。

        Args:
            topic: 选题数据
            portrait: 画像数据
            keyword_library: 关键词库
            business_info: 业务信息（可选）

        Returns:
            dict: 完整的图文内容上下文
        """
        context = {}

        # 添加选题信息
        topic_context = self.map_topic_to_content(topic)
        for key, value in topic_context.items():
            context[f'topic_{key}'] = value

        # 添加画像信息
        portrait_context = self.map_portrait_to_content(portrait)
        for key, value in portrait_context.items():
            context[f'portrait_{key}'] = value

        # 添加关键词库信息
        keyword_context = self.map_keyword_to_content(keyword_library)
        for key, value in keyword_context.items():
            context[f'keyword_{key}'] = value

        # 添加业务信息
        if business_info:
            context['business_description'] = business_info.get('business_description', '')
            context['business_type'] = business_info.get('business_type', 'product')
            context['industry'] = business_info.get('industry', '')

        # 简化键名（去掉前缀）供 prompt 直接使用
        # 这些键与 skill 配置中的占位符对应
        simple_context = {
            'topic': topic_context,
            'portrait': portrait_context,
            'keyword_library': keyword_context,
        }
        if business_info:
            simple_context['business_info'] = business_info

        return simple_context
