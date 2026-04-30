"""
统一 JSON 解析器模块

提供7层降级的 JSON 解析逻辑，供所有生成器复用。

使用方法：
    from services.json_parser import JSONParser

    parser = JSONParser()
    result = parser.parse_with_fallback(response_text, schema)
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class JSONParser:
    """
    统一 JSON 解析器

    支持7层降级解析，适用于各种 LLM 输出场景：
    1. 直接解析
    2. 修复常见错误后解析
    3. 提取 JSON code block
    4. 提取 JSON 数组
    5. 提取 JSON 对象
    6. 逐行提取 JSON 对象
    7. 从后向前提取

    使用方法：
        parser = JSONParser()
        result = parser.parse_with_fallback(llm_response, schema)
    """

    def __init__(self):
        self.parse_count = 0
        self.parse_fails = 0

    def parse_with_fallback(
        self,
        text: str,
        schema: Dict = None,
        default_field: str = None,
    ) -> Optional[Dict]:
        """
        带降级的 JSON 解析

        Args:
            text: LLM 返回的原始文本
            schema: 输出 schema（用于提取特定字段）
            default_field: 默认提取字段名

        Returns:
            解析后的字典，或 None
        """
        self.parse_count += 1

        # 预处理
        clean_text = self._preprocess(text)

        # 第1层：直接解析
        result = self._try_parse_direct(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第2层：修复常见错误后解析
        result = self._try_parse_after_fix(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第3层：提取 JSON code block
        result = self._try_parse_code_block(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第4层：提取 JSON 数组
        result = self._try_parse_json_array(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第5层：提取 JSON 对象
        result = self._try_parse_json_object(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第6层：逐行提取 JSON 对象
        result = self._try_parse_line_by_line(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 第7层：从后向前提取
        result = self._try_parse_backward(clean_text)
        if result is not None:
            return self._normalize_result(result, schema, default_field)

        # 所有层都失败
        self.parse_fails += 1
        logger.error(
            f"[JSONParser] 全部7层解析失败，原始文本前300字: {clean_text[:300]!r}"
        )
        return None

    def parse_array_with_fallback(
        self,
        text: str,
        schema: Dict = None,
    ) -> List[Dict]:
        """
        解析 JSON 数组

        适用于 LLM 返回数组格式的场景（如选题列表）

        Args:
            text: LLM 返回的原始文本
            schema: 输出 schema

        Returns:
            解析后的字典列表
        """
        result = self.parse_with_fallback(text, schema, default_field=None)

        if result is None:
            return []

        # 尝试提取数组
        if isinstance(result, list):
            return result

        # 从 result 中提取数组
        for key in ['topics', 'titles', 'keywords', 'items', 'data', 'results']:
            if key in result and isinstance(result[key], list):
                return result[key]

        return [result] if isinstance(result, dict) else []

    def _preprocess(self, text: str) -> str:
        """预处理：去除多余空白和标记"""
        if not text:
            return ""

        clean = text.strip()

        # 去除 markdown 代码块标记
        if clean.startswith('```json'):
            clean = clean[7:]
        elif clean.startswith('```'):
            clean = clean[3:]

        # 去除结尾的代码块标记
        if clean.endswith('```'):
            clean = clean[:-3]

        return clean.strip()

    def _try_parse_direct(self, text: str) -> Optional[Any]:
        """第1层：直接解析"""
        try:
            result = json.loads(text)
            logger.info(f"[JSONParser] 第1层直接解析成功")
            return result
        except (json.JSONDecodeError, TypeError):
            return None

    def _try_parse_after_fix(self, text: str) -> Optional[Any]:
        """第2层：修复常见错误后解析"""
        fixed = self._fix_json_errors(text)
        try:
            result = json.loads(fixed)
            logger.info(f"[JSONParser] 第2层修复后解析成功")
            return result
        except (json.JSONDecodeError, TypeError):
            return None

    def _try_parse_code_block(self, text: str) -> Optional[Any]:
        """第3层：提取 JSON code block"""
        # 提取 ```json ... ```
        patterns = [
            r'```json\s*\n?(.*?)\n?```',
            r'```\s*\n?(.*?)\n?```',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                cleaned = match.strip()
                try:
                    result = json.loads(cleaned)
                    logger.info(f"[JSONParser] 第3层code block解析成功")
                    return result
                except (json.JSONDecodeError, TypeError):
                    continue

        return None

    def _try_parse_json_array(self, text: str) -> Optional[Any]:
        """第4层：提取 JSON 数组"""
        # 查找 [...] 数组
        match = re.search(r'\[\s*\{', text)
        if match:
            start = match.start()
            for end in range(len(text), start, -1):
                candidate = text[start:end]
                # 修复双大括号
                candidate = candidate.replace('{{', '{').replace('}}', '}')
                try:
                    result = json.loads(candidate)
                    if isinstance(result, list) and len(result) > 0:
                        logger.info(f"[JSONParser] 第4层JSON数组解析成功，得到 {len(result)} 条")
                        return result
                except (json.JSONDecodeError, TypeError):
                    continue

        return None

    def _try_parse_json_object(self, text: str) -> Optional[Any]:
        """第5层：提取 JSON 对象"""
        # 查找第一个完整 {...} 对象
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            for end in range(len(text), match.start(), -1):
                candidate = text[match.start():end]
                # 修复双大括号
                candidate = candidate.replace('{{', '{').replace('}}', '}')
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        logger.info(f"[JSONParser] 第5层JSON对象解析成功")
                        return result
                except (json.JSONDecodeError, TypeError):
                    continue

        return None

    def _try_parse_line_by_line(self, text: str) -> Optional[Any]:
        """第6层：逐行提取 JSON 对象"""
        lines = text.split('\n')
        objects = []

        bracket_depth = 0
        in_json = False
        json_start = -1

        for i, char in enumerate(text):
            if char == '{':
                if not in_json:
                    json_start = i
                    in_json = True
                bracket_depth += 1
            elif char == '}':
                bracket_depth -= 1
                if in_json and bracket_depth == 0:
                    json_str = text[json_start:i+1]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict):
                            objects.append(obj)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    in_json = False
                    json_start = -1

        if objects:
            logger.info(f"[JSONParser] 第6层逐行提取成功，得到 {len(objects)} 个对象")
            # 返回第一个包含关键字段的对象，或对象列表
            for obj in objects:
                if any(k in obj for k in ['title', 'topics', 'portraits']):
                    return obj
            return objects[0] if len(objects) == 1 else {"items": objects}

        return None

    def _try_parse_backward(self, text: str) -> Optional[Any]:
        """第7层：从后向前提取"""
        # 反转文本，查找最后一个完整对象
        reversed_text = text[::-1]

        # 从后向前查找 }
        end_markers = []
        for i, char in enumerate(reversed_text):
            if char == '}':
                end_markers.append(len(text) - 1 - i)

        for end_pos in end_markers:
            for start_pos in range(0, end_pos):
                candidate = text[start_pos:end_pos+1]
                # 修复双大括号
                candidate = candidate.replace('{{', '{').replace('}}', '}')
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict) and len(result) > 0:
                        logger.info(f"[JSONParser] 第7层从后向前解析成功")
                        return result
                except (json.JSONDecodeError, TypeError):
                    continue

        return None

    def _normalize_result(
        self,
        result: Any,
        schema: Dict = None,
        default_field: str = None,
    ) -> Optional[Dict]:
        """
        规范化解析结果

        处理以下情况：
        1. 数据被包裹在额外层级中
        2. 数据字段名与预期不符
        """
        if not isinstance(result, dict):
            return {"_data": result}

        # 如果有默认字段，尝试提取
        if default_field and default_field in result:
            return result

        # 尝试从常见的数据包裹字段中提取
        wrapper_keys = ['content', 'data', 'result', 'output', 'response']
        for wrapper in wrapper_keys:
            if wrapper in result:
                inner = result[wrapper]
                if isinstance(inner, dict):
                    return inner
                elif isinstance(inner, (list, str)):
                    return {default_field or 'data': inner}

        # 尝试提取数组类型数据
        if default_field:
            for key in [default_field, 'items', 'data', 'results']:
                if key in result:
                    return result

        return result

    @staticmethod
    def _fix_json_errors(text: str) -> str:
        """
        修复常见的 JSON 错误

        修复内容：
        1. 尾部多余逗号
        2. 单引号改为双引号
        3. 中文字符作为键值
        """
        fixed = text

        # 修复尾部多余逗号
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)

        # 修复单引号
        # 注意：这可能会导致问题，仅在必要时使用
        # fixed = fixed.replace("'", '"')

        # 修复中文引号
        fixed = fixed.replace("""", '"').replace(""", '"')
        fixed = fixed.replace("'", '"').replace("'", '"')

        # 移除注释行
        lines = []
        for line in fixed.split('\n'):
            stripped = line.strip()
            if not stripped.startswith('//') and not stripped.startswith('#'):
                lines.append(line)
        fixed = '\n'.join(lines)

        return fixed

    @staticmethod
    def extract_json_block(text: str) -> str:
        """
        从文本中提取 JSON 块

        Args:
            text: 原始文本

        Returns:
            提取的 JSON 字符串
        """
        # 提取 ```json ... ```
        match = re.search(r'```json\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 提取 ``` ... ```
        match = re.search(r'```\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 返回原始文本
        return text.strip()

    def get_stats(self) -> Dict[str, int]:
        """获取解析统计"""
        return {
            "total": self.parse_count,
            "fails": self.parse_fails,
            "success_rate": (
                (self.parse_count - self.parse_fails) / self.parse_count * 100
                if self.parse_count > 0 else 0
            ),
        }


# =============================================================================
# 便捷函数
# =============================================================================

def parse_json(
    text: str,
    schema: Dict = None,
    default_field: str = None,
) -> Optional[Dict]:
    """
    便捷函数：解析 JSON

    使用方法：
        from services.json_parser import parse_json

        result = parse_json(llm_response)
    """
    parser = JSONParser()
    return parser.parse_with_fallback(text, schema, default_field)


def parse_json_array(
    text: str,
    schema: Dict = None,
) -> List[Dict]:
    """
    便捷函数：解析 JSON 数组

    使用方法：
        from services.json_parser import parse_json_array

        results = parse_json_array(llm_response)
    """
    parser = JSONParser()
    return parser.parse_array_with_fallback(text, schema)


def extract_json(text: str) -> Optional[Dict]:
    """
    便捷函数：从文本中提取 JSON

    使用方法：
        from services.json_parser import extract_json

        result = extract_json(markdown_text)
    """
    parser = JSONParser()
    extracted = parser.extract_json_block(text)
    return parser.parse_with_fallback(extracted)
