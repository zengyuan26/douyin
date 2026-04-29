"""
SkillExecutor — 步骤执行器

负责：
1. 按配置文件顺序执行各步骤
2. prompt 模板变量填充
3. 调用 LLM 获取结果
4. 解析 LLM 输出为结构化数据（JSON / markdown code block / 表格）
5. 约束验证（数量下限、必填字段）
6. 记录执行结果（成功/失败/耗时/错误）
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .registry import SkillRegistry
from .data_mapper import DataMapper

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class StepResult:
    """单个步骤的执行结果"""
    step_id: str
    success: bool
    output: dict = field(default_factory=dict)
    raw_output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class SkillExecutionResult:
    """整个 skill 的执行结果"""
    skill_name: str
    success: bool
    full_output: dict = field(default_factory=dict)
    step_results: List[StepResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "success": self.success,
            "full_output": self.full_output,
            "steps": [
                {
                    "step_id": s.step_id,
                    "success": s.success,
                    "output": s.output,
                    "error": s.error,
                    "duration_ms": s.duration_ms,
                    "warnings": s.validation_warnings,
                }
                for s in self.step_results
            ],
            "errors": self.errors,
            "total_duration_ms": self.total_duration_ms,
        }


# =============================================================================
# SkillExecutor
# =============================================================================

class SkillExecutor:
    """
    Skill 执行器

    使用示例：
        executor = SkillExecutor(
            llm_call_func=lambda prompt: llm_service.chat(prompt),
        )
        result = executor.execute_skill(
            "market_analyzer",
            manual_inputs={"industry": "奶粉", "business_type": "product"},
            skip_steps=["step7_upstream_downstream"],
        )
    """

    def __init__(
        self,
        llm_call_func: Callable[[str], Optional[str]] = None,
        llm_service=None,
    ):
        """
        Args:
            llm_call_func: LLM 调用函数，签名为 (prompt: str) -> Optional[str]
                           返回 None 表示调用失败
            llm_service: LLMService 实例，优先级高于 llm_call_func，
                         用于动态传入 task_type 以获得正确的 max_tokens
        """
        self.registry = SkillRegistry()
        self.mapper = DataMapper(self.registry)
        self._llm_service = llm_service
        if llm_service is not None:
            # 持有 llm_service，调用时动态传入 skill_name 作为 task_type
            self.llm_call = lambda prompt, skill_name='content_create': llm_service.chat(prompt, task_type=skill_name)
        else:
            self.llm_call = llm_call_func
        self._outputs: Dict[str, dict] = {}

    # -------------------------------------------------------------------------
    # 主流程
    # -------------------------------------------------------------------------

    def execute_skill(
        self,
        skill_name: str,
        manual_inputs: Optional[dict] = None,
        skip_steps: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
        stop_on_error: bool = False,
        _full_output_preset: Optional[dict] = None,
    ) -> SkillExecutionResult:
        """
        执行整个 skill。

        Args:
            skill_name: skill 配置名称（对应 config/*.json 的文件名）
            manual_inputs: 手动输入的变量（对应 prompt 模板中的 {变量名}）
            skip_steps: 跳过的步骤 ID 列表
            max_steps: 最多执行前 N 个步骤
            stop_on_error: 某步骤失败时是否停止后续步骤
            _full_output_preset: 内部参数，用于预填充某些 step 的输出（如手动质量评分场景）

        Returns:
            SkillExecutionResult，包含完整输出和每步详情
        """
        skill = self.registry.get_skill(skill_name)
        if not skill:
            return SkillExecutionResult(
                skill_name=skill_name,
                success=False,
                errors=[f"Skill '{skill_name}' 未找到"],
            )

        manual_inputs = manual_inputs or {}
        skip_steps = skip_steps or []
        steps = self.registry.get_steps_ordered(skill_name)

        if max_steps is not None:
            steps = steps[:max_steps]

        # 预填充的输出（如手动质量评分时，跳过内容生成但仍需该步输出）
        full_output: dict = dict(_full_output_preset) if _full_output_preset else {}
        step_results: List[StepResult] = []
        errors: List[str] = []
        start_time = time.time()

        # 同步到 self._outputs，供 build_input_context 读取
        self._outputs[skill_name] = full_output

        for step in steps:
            step_id = step["id"]

            if step_id in skip_steps:
                logger.info(f"[SkillExecutor] 跳过步骤: {step_id}")
                continue

            # 构建上下文：上游输出 + 手动输入
            context = self.mapper.build_input_context(skill_name, self._outputs)
            context.update(manual_inputs)

            # 执行步骤
            result = self._execute_step(skill_name, step, context)
            step_results.append(result)

            if result.success:
                full_output[step_id] = result.output
            else:
                errors.append(f"步骤 {step_id} 失败: {result.error}")
                if stop_on_error:
                    break

        total_duration_ms = int((time.time() - start_time) * 1000)

        # 更新全局输出缓存
        self._outputs[skill_name] = full_output

        return SkillExecutionResult(
            skill_name=skill_name,
            success=len(errors) == 0,
            full_output=full_output,
            step_results=step_results,
            errors=errors,
            total_duration_ms=total_duration_ms,
        )

    # -------------------------------------------------------------------------
    # 单步执行
    # -------------------------------------------------------------------------

    def _execute_step(
        self,
        skill_name: str,
        step: dict,
        context: dict,
    ) -> StepResult:
        """执行单个步骤"""
        step_id = step["id"]
        step_name = step.get("name", step_id)
        start_time = time.time()

        # 1. 填充 prompt
        prompt_template = step.get("llm_prompt_template", "")
        if not prompt_template:
            return StepResult(
                step_id=step_id,
                success=False,
                error=f"步骤 {step_name} 缺少 llm_prompt_template",
                duration_ms=0,
            )

        try:
            prompt = self._fill_prompt(prompt_template, context, step)
        except Exception as e:
            return StepResult(
                step_id=step_id,
                success=False,
                error=f"Prompt 填充失败: {e}",
                duration_ms=0,
            )

        # 2. 调用 LLM
        try:
            raw_output = self.llm_call(prompt, skill_name)
            if raw_output is None:
                return StepResult(
                    step_id=step_id,
                    success=False,
                    error="LLM 调用返回 None",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
        except Exception as e:
            return StepResult(
                step_id=step_id,
                success=False,
                error=f"LLM 调用异常: {e}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # 3. 解析输出
        try:
            structured_output = self._parse_output(
                raw_output,
                step.get("output_schema", {}),
                step.get("output_field", step_id),
                step_id=step_id,
            )
        except Exception as e:
            return StepResult(
                step_id=step_id,
                success=False,
                error=f"输出解析失败: {e}",
                raw_output=raw_output[:500],
                duration_ms=int((time.time() - start_time) * 1000),
            )

        # 4. 约束验证
        constraints = self.registry.get_constraints(skill_name)
        warnings = self._validate_constraints(structured_output, constraints, step)

        duration_ms = int((time.time() - start_time) * 1000)

        return StepResult(
            step_id=step_id,
            success=True,
            output=structured_output,
            raw_output=raw_output[:1000],
            validation_warnings=warnings,
            duration_ms=duration_ms,
        )

    # -------------------------------------------------------------------------
    # Prompt 填充
    # -------------------------------------------------------------------------

    def _fill_prompt(self, template: str, context: dict, step: dict = None) -> str:
        """
        填充 prompt 模板中的占位符。

        支持两种占位符格式：
        - `<<variable>>` — 推荐（JSON 字符串内不会与 {{ }} 冲突）
        - `{variable}`    — 兼容（仅用于 JSON 安全场景）

        占位符内嵌 JSON 示例块时，使用 {{ }} 无需转义：
            "请按格式输出：<<example>>"  其中 example="{\"key\": \"value\"}"
        """
        import re
        result = template

        # 优先处理 <<variable>> 格式（JSON 安全的双尖括号）
        for key, value in context.items():
            placeholder = f"<<{key}>>"
            if placeholder not in result:
                continue

            if isinstance(value, (dict, list)):
                json_str = json.dumps(value, ensure_ascii=False, indent=2)
                result = result.replace(placeholder, json_str)
            elif value is None:
                result = result.replace(placeholder, "(未提供)")
            else:
                result = result.replace(placeholder, str(value))

        # 兼容 {variable} 格式
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder not in result:
                continue

            if isinstance(value, (dict, list)):
                json_str = json.dumps(value, ensure_ascii=False, indent=2)
                result = result.replace(placeholder, json_str)
            elif value is None:
                result = result.replace(placeholder, "(未提供)")
            else:
                result = result.replace(placeholder, str(value))

        # 检测未填充的关键占位符（常见原因：参数缺失 → 数据为空）
        unfilled_dd = re.findall(r'<<([^>]+)>>', result)
        if unfilled_dd:
            logger.error(
                f"[SkillExecutor] step={step.get('id', '?')} 存在未填充占位符: {unfilled_dd}, "
                f"context_keys={list(context.keys())}"
            )

        return result

    # -------------------------------------------------------------------------
    # 输出解析
    # -------------------------------------------------------------------------

    def _parse_output(
        self,
        raw_output: str,
        schema: dict,
        default_field: str,
        step_id: str = '',
    ) -> dict:
        """
        将 LLM 返回的原始文本解析为结构化字典。

        解析优先级：
        1. 直接解析为 JSON 对象
        2. 从 markdown ```json ``` code block 中提取
        3. 从 markdown ``` ``` code block 中提取
        4. 从 markdown 文本中提取 JSON-like 片段（slides数组、title等）
        5. 提取表格行为关键词列表（适用于 schema 暗示为数组的场景）
        6. 返回 {"_raw": raw_output}
        """
        raw = raw_output.strip()

        # 优先级1：直接 JSON
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 优先级2：```json code block
        code_blocks = re.findall(
            r"```json\s*\n?(.*?)\n?```", raw, re.DOTALL
        )
        for block in code_blocks:
            try:
                parsed = json.loads(block.strip())
                result = self._normalize_output(parsed, default_field)
                logger.info(f"[SkillExecutor] step={step_id} JSON block parsed, keys={list(result.keys())}, slides={bool(result.get('slides'))}")
                return result
            except json.JSONDecodeError:
                pass

        # 优先级3：普通 ``` code block
        code_blocks = re.findall(
            r"```\s*\n?(.*?)\n?```", raw, re.DOTALL
        )
        for block in code_blocks:
            try:
                parsed = json.loads(block.strip())
                result = self._normalize_output(parsed, default_field)
                logger.info(f"[SkillExecutor] step={step_id} code block parsed, keys={list(result.keys())}, slides={bool(result.get('slides'))}")
                return result
            except json.JSONDecodeError:
                pass

        # 优先级4：从 markdown 文本中提取 JSON-like 片段
        # 适用于 LLM 返回描述性文字但其中嵌入了结构化数据
        extracted = self._extract_json_from_markdown(raw, schema)
        if extracted:
            logger.info(f"[SkillExecutor] step={step_id} 从 markdown 中提取到结构化数据")
            return extracted

        # 优先级5：表格行为列表（keyword/list 等字段）
        schema_str = str(schema).lower()
        if any(k in schema_str for k in ["keyword", "list", "items", "array"]):
            keywords = self._extract_lines_as_list(raw)
            if keywords:
                return {default_field: keywords}

        # 降级处理：无法解析为 JSON，记录 ERROR 并返回原始文本
        logger.error(
            f"[SkillExecutor] step={step_id} 无法解析为结构化 JSON，返回原始文本 "
            f"(前300字符): {raw[:300]!r}"
        )
        return {"_raw": raw}

    def _normalize_output(self, parsed: dict, default_field: str) -> dict:
        """
        规范化 LLM 返回的 JSON 数据。

        处理以下情况：
        1. 数据被包裹在额外层级中（如 {"content": [...]} 而不是直接是数组）
        2. 数据字段名与预期不符（如 "tags" vs "tag_list"）

        根据 output_field 决定：
        - 如果 default_field 存在于 parsed 中，直接返回 parsed
        - 如果 data_wrapper 存在于 parsed 中，尝试从中提取数据
        - 如果 parsed 只包含一个 key 且是数组/对象，返回该值
        - 否则返回 parsed
        """
        if not isinstance(parsed, dict):
            return {default_field: parsed}

        # 如果默认字段已存在，直接返回
        if default_field in parsed:
            return parsed

        # 尝试从常见的数据包裹字段中提取
        wrapper_keys = ['content', 'data', 'result', 'output', 'response']
        for wrapper in wrapper_keys:
            if wrapper in parsed:
                inner = parsed[wrapper]
                if isinstance(inner, dict):
                    # 递归规范化内部字典
                    return self._normalize_output(inner, default_field)
                elif isinstance(inner, (list, str)):
                    # 对于 output_field='content' 的情况，返回内部值
                    # （_build_content_data_from_bridge 会处理列表解析）
                    if default_field == 'content':
                        return {default_field: inner}
                    # 对于 output_field='slides' 但数据在 content 中的情况
                    # 尝试解析内容中的 JSON 片段
                    if default_field == 'slides' and isinstance(inner, list):
                        parsed_slides = []
                        any_parsed = False
                        for item in inner:
                            if isinstance(item, dict):
                                parsed_slides.append(item)
                                any_parsed = True
                            elif isinstance(item, str):
                                # 尝试1：将字符串解析为 JSON
                                try:
                                    parsed_item = json.loads(item)
                                    if isinstance(parsed_item, dict):
                                        parsed_slides.append(parsed_item)
                                        any_parsed = True
                                        continue
                                except (json.JSONDecodeError, ValueError):
                                    pass
                                # 尝试2：从文本中提取 slide 结构
                                slide = self._parse_text_to_slide(item)
                                if slide:
                                    parsed_slides.append(slide)
                                    any_parsed = True
                                else:
                                    # 无法解析，保留原值
                                    parsed_slides.append(item)
                        # 只要有任何一个成功解析为 dict，就返回
                        if any_parsed:
                            return {default_field: parsed_slides}
                        # 如果完全无法解析，保留原 content
                        return {default_field: inner}
                    return {default_field: inner}

        # 如果 parsed 只有一个 key 且值是 dict/array，且 key 不是常见元字段
        meta_keys = {'status', 'code', 'message', 'error', 'success', 'total', 'count'}
        non_meta_keys = [k for k in parsed.keys() if k.lower() not in meta_keys]
        if len(non_meta_keys) == 1:
            sole_key = non_meta_keys[0]
            sole_val = parsed[sole_key]
            if isinstance(sole_val, (dict, list)):
                return self._normalize_output(sole_val, default_field)

        # 无法规范化，直接返回原始数据
        return parsed

    def _parse_text_to_slide(self, text: str) -> Optional[dict]:
        """
        将一段文本解析为 slide 对象。

        适用于 LLM 返回格式如：
        "镜头1【封面引流帧】\n\n帧编号：1\n帧名称：封面引流帧\n\n视觉目标：..."
        的场景。
        """
        if not text or not isinstance(text, str):
            return None

        slide = {}
        lines = text.split('\n')
        current_key = None
        current_value = []

        # 字段映射
        field_mappings = {
            '帧编号': 'index', '编号': 'index', 'index': 'index',
            '帧名称': 'frame_id', '名称': 'frame_id', 'frame_id': 'frame_id',
            '角色': 'role', 'role': 'role',
            '版式': 'layout_type', 'layout_type': 'layout_type',
            '主标题': 'main_title', 'main_title': 'main_title',
            '大字金句': 'big_slogan', 'big_slogan': 'big_slogan',
            '情绪': 'emotion_stage', 'emotion_stage': 'emotion_stage',
            '视觉目标': 'visual_target', 'visual_target': 'visual_target',
            '画面逻辑': 'scene_logic', 'scene_logic': 'scene_logic',
            '色调': 'color_tone', 'color_tone': 'color_tone',
            '副标题': 'sub_content', 'sub_content': 'sub_content',
            '画面风格': 'visual_style', 'visual_style': 'visual_style',
            '人物统一': 'character_consistency', 'character_consistency': 'character_consistency',
            '光影逻辑': 'light_shadow_logic', 'light_shadow_logic': 'light_shadow_logic',
            '场景道具': 'scene_dressing', 'scene_dressing': 'scene_dressing',
            '氛围感': 'atmosphere_filter', 'atmosphere_filter': 'atmosphere_filter',
            '信息层级': 'info_zones', 'info_zones': 'info_zones',
            '字数限制': 'text_count_limit', 'text_count_limit': 'text_count_limit',
            '情绪过渡': 'emotion_transition', 'emotion_transition': 'emotion_transition',
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是字段行
            is_field_line = False
            for field, key in field_mappings.items():
                for sep in ['：', ':', ' ']:
                    if line.startswith(field + sep):
                        # 提取值
                        value = line[len(field) + len(sep):].strip()
                        # 去掉常见前缀
                        value = re.sub(r'^[*#\-\s]+', '', value)
                        if value:
                            slide[key] = value
                            current_key = key
                            current_value = []
                        is_field_line = True
                        break
                if is_field_line:
                    break

            # 如果是帧开始标记
            if not is_field_line:
                match = re.search(r'镜?头?[\s:：]*(\d+)', line)
                if match and 'index' not in slide:
                    slide['index'] = int(match.group(1))
                    continue

                match = re.search(r'【([^】]+)】', line)
                if match and 'role' not in slide:
                    slide['role'] = match.group(1)
                    continue

        # 设置默认值
        if 'index' not in slide:
            slide['index'] = 1
        if 'role' not in slide:
            slide['role'] = '内容页'

        # 收集 sub_points（没有被特定字段捕获的内容）
        # 将当前 slide 的内容作为 big_slogan 或 sub_points
        if not slide.get('big_slogan') and not slide.get('main_title'):
            # 使用整个文本的前100个字符作为 big_slogan
            text_preview = text[:100].replace('\n', ' ').strip()
            slide['big_slogan'] = text_preview

        return slide if slide else None

    def _extract_json_from_markdown(self, text: str, schema: dict) -> Optional[dict]:
        """
        从 markdown 文本中智能提取结构化数据。

        适用于 LLM 返回描述性文字（如"以下是生成的内容：\n\n### 标题\n内容..."）
        但其中嵌入了 JSON-like 结构或可直接解析的字段。

        Returns:
            提取到的字典，或 None（无法提取时）
        """
        result = {}

        # ── 提取 slides 数组 ────────────────────────────────────────────────
        # 查找 markdown 中嵌入的 slides 数据
        slides_patterns = [
            # 格式1: "slides": [...] 或 "slides":[
            r'"slides"\s*:\s*\[',
            # 格式2: "1": {"role": ... 形式（对象键为数字）
            r'"\d+"\s*:\s*\{',
        ]
        has_slides = any(re.search(p, text) for p in slides_patterns)

        if has_slides:
            slides = self._extract_slides_from_markdown(text)
            if slides:
                result['slides'] = slides

        # ── 提取顶层字段 ─────────────────────────────────────────────────
        # 匹配 "field": "value" 或 "field": value 形式
        top_fields = [
            'title', 'subtitle', 'structure', 'geo_mode', 'opening', 'cta',
            'first_comment', 'publish_strategy', 'content_plan', 'comment', 'publish',
            'slides_count', 'text_count_limit', 'color_tone', 'main_title', 'big_slogan',
            'emotion_stage', 'visual_target', 'scene_logic', 'role', 'layout_type',
            'visual_style', 'sub_content', 'info_zones', 'design_specs',
            'emotion_transition', 'data_content', 'character_consistency',
            'light_shadow_logic', 'scene_dressing', 'atmosphere_filter',
        ]
        for field in top_fields:
            # 匹配 "field": "value" 或 "field": 'value'
            patterns = [
                rf'"{field}"\s*:\s*"([^"]*)"',
                rf'"{field}"\s*:\s*\'([^\']*)\'',
                rf'"{field}"\s*:\s*([\d]+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    val = match.group(1)
                    if val and val.strip():
                        result[field] = val.strip()
                    break

        # ── 提取 hashtags 数组 ─────────────────────────────────────────────
        hashtag_match = re.search(r'"hashtags"\s*:\s*\[([^\]]+)\]', text)
        if hashtag_match:
            tags = re.findall(r'"([^"]+)"', hashtag_match.group(1))
            if tags:
                result['hashtags'] = tags

        # ── 提取 tags 数组 ────────────────────────────────────────────────
        tags_match = re.search(r'"tags"\s*:\s*\[([^\]]+)\]', text)
        if tags_match:
            tags = re.findall(r'"([^"]+)"', tags_match.group(1))
            if tags:
                result['tags'] = tags

        # ── 提取 sub_points 数组 ──────────────────────────────────────────
        # 查找当前 slide 上下文中的 sub_points
        sub_points_match = re.search(r'"sub_points"\s*:\s*\[([^\]]+)\]', text)
        if sub_points_match:
            points = re.findall(r'"([^"]+)"', sub_points_match.group(1))
            if points:
                result['sub_points'] = points

        # ── 提取 visual_elements 数组 ─────────────────────────────────────
        ve_match = re.search(r'"visual_elements"\s*:\s*\[([^\]]+)\]', text)
        if ve_match:
            elements = re.findall(r'"([^"]+)"', ve_match.group(1))
            if elements:
                result['visual_elements'] = elements

        # ── 提取 trust_evidence 数组 ──────────────────────────────────────
        te_match = re.search(r'"trust_evidence"\s*:\s*\[([^\]]+)\]', text)
        if te_match:
            ev_str = te_match.group(1)
            ev_items = re.findall(r'\{[^}]+\}', ev_str)
            trust_ev = []
            for ev in ev_items:
                ev_match = re.search(r'"content"\s*:\s*"([^"]*)"', ev)
                type_match = re.search(r'"type"\s*:\s*"([^"]*)"', ev)
                source_match = re.search(r'"source"\s*:\s*"([^"]*)"', ev)
                if ev_match:
                    item = {'content': ev_match.group(1)}
                    if type_match:
                        item['type'] = type_match.group(1)
                    if source_match:
                        item['source'] = source_match.group(1)
                    trust_ev.append(item)
            if trust_ev:
                result['trust_evidence'] = trust_ev

        # ── 提取 seo_keywords 对象 ─────────────────────────────────────────
        seo_match = re.search(r'"seo_keywords"\s*:\s*\{([^}]+)\}', text)
        if seo_match:
            seo = {}
            for k in ['core', 'long_tail', 'scene', 'problem']:
                kw_match = re.search(rf'"{k}"\s*:\s*\[([^\]]+)\]', seo_match.group(1))
                if kw_match:
                    kws = re.findall(r'"([^"]+)"', kw_match.group(1))
                    if kws:
                        seo[k] = kws
            if seo:
                result['seo_keywords'] = seo

        # ── 提取 cover_suggestion 对象 ────────────────────────────────────
        cover_match = re.search(r'"cover_suggestion"\s*:\s*\{([^}]+)\}', text)
        if cover_match:
            cover = {}
            for k in ['opening_words', 'emotion_words', 'action_guide']:
                cv = re.search(rf'"{k}"\s*:\s*"([^"]*)"', cover_match.group(1))
                if cv:
                    cover[k] = cv.group(1)
            if cover:
                result['cover_suggestion'] = cover

        # ── 提取 color_scheme 对象 ─────────────────────────────────────────
        cs_match = re.search(r'"color_scheme"\s*:\s*\{([^}]+)\}', text)
        if cs_match:
            cs = {}
            for k in ['cold_pages', 'warm_pages', 'brand_pages']:
                cv = re.search(rf'"{k}"\s*:\s*\[([^\]]+)\]', cs_match.group(1))
                if cv:
                    vals = re.findall(r'"([^"]+)"', cv.group(1))
                    if vals:
                        cs[k] = vals
            if cs:
                result['color_scheme'] = cs

        # ── 提取 golden_quote_block 对象 ───────────────────────────────────
        gq_match = re.search(r'"golden_quote_block"\s*:\s*\{([^}]+)\}', text)
        if gq_match:
            gq = {}
            gq_text = re.search(r'"text"\s*:\s*"([^"]*)"', gq_match.group(1))
            gq_bg = re.search(r'"bg_color"\s*:\s*"([^"]*)"', gq_match.group(1))
            if gq_text:
                gq['text'] = gq_text.group(1)
            if gq_bg:
                gq['bg_color'] = gq_bg.group(1)
            if gq:
                result['golden_quote_block'] = gq

        # 只有当提取到有效数据时才返回
        if result:
            return result
        return None

    def _extract_slides_from_markdown(self, text: str) -> Optional[List[dict]]:
        """
        从 markdown 文本中提取 slides 数组数据。

        查找以下模式：
        1. 明确标记的帧编号（如"图片1"、"### 图片1"、"P1"等）
        2. 角色标签（如"封面"、"痛点"、"分析"等）
        3. 内容描述行
        """
        slides = []
        lines = text.split('\n')

        current_slide = None
        slide_idx = 0

        # 帧识别模式
        slide_patterns = [
            r'^(?:图片|第|P|p)[\s:：]*(\d+)',
            r'^#{1,6}\s*(?:图片|第)?[\s:：]*(\d+)',
            r'^###?\s*\[?镜头?\s*(\d+)',
            r'^\d+[.、)]\s*\[?[帧页图片]',
            r'^(?:P|p)(\d+)\s*[-_：:]',
        ]

        # 角色识别关键词
        role_keywords = ['封面', '痛点', '共情', '分析', '干货', '总结', '升华', '转化', '信任', '方案', '拆解', '强化']

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是新的帧开始
            is_new_slide = False
            for pattern in slide_patterns:
                match = re.search(pattern, line)
                if match:
                    idx_str = match.group(1)
                    try:
                        parsed_idx = int(idx_str)
                        if parsed_idx != slide_idx:
                            is_new_slide = True
                            slide_idx = parsed_idx
                            break
                    except ValueError:
                        pass

            # 检查是否包含角色关键词
            if not is_new_slide and current_slide:
                for role_kw in role_keywords:
                    if role_kw in line and len(line) < 100:
                        # 检查这一行是否主要是角色描述
                        if re.match(rf'^(?:图片|第|\d+)?\s*\[?{role_kw}', line) or re.match(rf'^{role_kw}', line):
                            is_new_slide = True
                            break

            if is_new_slide and current_slide and current_slide.get('main_title') or current_slide and len(current_slide) > 1:
                slides.append(current_slide)

            if is_new_slide:
                current_slide = {'index': slide_idx}
                # 从行中提取角色
                for role_kw in role_keywords:
                    if role_kw in line:
                        current_slide['role'] = role_kw
                        break
                # 提取主标题（去掉角色前缀后的内容）
                title_part = re.sub(r'^(?:图片|第|\d+|\s|\[)+', '', line)
                title_part = re.sub(rf'[{role_kw}]+', '', title_part).strip()
                if title_part and len(title_part) < 100:
                    current_slide['main_title'] = title_part
            elif current_slide:
                # 提取内容到当前 slide
                # 主标题
                if not current_slide.get('main_title') and len(line) < 100:
                    # 检查是否是标题行
                    if re.match(r'^[*#\-\s]*(?:标题|主标题|大字金句)', line):
                        title = re.sub(r'^[*#\-\s]*(?:标题|主标题|大字金句)[:：]?\s*', '', line)
                        if title:
                            current_slide['main_title'] = title
                    elif not line.startswith(('##', '---', '>')) and len(line) > 5:
                        # 检查是否是连续的内容行
                        if current_slide.get('main_title'):
                            # 作为 sub_point
                            sub_points = current_slide.get('sub_points', [])
                            sub_points.append(line)
                            current_slide['sub_points'] = sub_points
                        else:
                            current_slide['main_title'] = line

        # 添加最后一个 slide
        if current_slide and (current_slide.get('main_title') or len(current_slide) > 1):
            slides.append(current_slide)

        return slides if slides else None

    def _extract_lines_as_list(self, text: str) -> List[str]:
        """
        从文本中提取非空行作为列表。

        适用于 LLM 返回类似：
          - 关键词1
          - 关键词2
        或
          | 关键词1 |
          | 关键词2 |
        的场景。
        """
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            # 去掉常见的列表前缀符号
            line = re.sub(r"^[-*|>\s]+\s*", "", line)
            line = line.strip()
            # 过滤太短或明显是标题/说明的行
            if line and len(line) >= 2 and not re.match(
                r"^[\d\.\)]+\s*[A-Z]", line
            ):
                lines.append(line)
        return lines

    # -------------------------------------------------------------------------
    # 约束验证
    # -------------------------------------------------------------------------

    def _validate_constraints(
        self,
        output: dict,
        constraints: dict,
        step: dict,
    ) -> List[str]:
        """
        验证输出是否满足约束条件。

        返回警告列表（不影响执行成功，只做提示）。
        """
        warnings = []

        # 1. 检查数量要求（顶层字段）
        quantity = constraints.get("quantity_requirements", {})
        for field_name, min_count in quantity.items():
            if field_name in output:
                actual = self._count_items(output[field_name])
                if actual < min_count:
                    warnings.append(
                        f"字段 {field_name} 数量不足：要求≥{min_count}，实际{actual}"
                    )

        # 2. 检查 output_schema 中的 minItems
        schema = step.get("output_schema", {})
        flat_schema = DataMapper.flatten_schema(schema)
        for path, field_schema in flat_schema.items():
            if field_schema.get("type") == "array":
                min_items = field_schema.get("minItems")
                if min_items:
                    actual_count = self._count_items(
                        DataMapper.get_nested(output, path)
                    )
                    if actual_count < min_items:
                        warnings.append(
                            f"字段 {path} 数量不足：要求≥{min_items}，实际{actual_count}"
                        )

        # 3. 记录警告
        for w in warnings:
            logger.warning(f"[SkillExecutor] 约束验证: {w}")

        return warnings

    @staticmethod
    def _count_items(value: Any) -> int:
        """安全计数"""
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        # 字符串不是合法的数组格式，不再按行分割计数（避免 markdown 文本被误计）
        return 0

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    def get_skill_output(self, skill_name: str) -> Optional[dict]:
        """获取 skill 的完整输出（从缓存）"""
        return self._outputs.get(skill_name)

    def get_step_output(self, skill_name: str, step_id: str) -> Optional[dict]:
        """获取特定步骤的输出（从缓存）"""
        return self._outputs.get(skill_name, {}).get(step_id)

    def clear_cache(self, skill_name: Optional[str] = None):
        """清空输出缓存"""
        if skill_name:
            self._outputs.pop(skill_name, None)
        else:
            self._outputs.clear()
