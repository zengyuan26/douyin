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
