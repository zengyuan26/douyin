"""
分析维度执行/辅助工具

主要职责：
- 提供按分类读取「启用中的」分析维度的便捷方法
- 为内容分析过滤前端传入的 modules，只保留在维度管理中启用的维度
- 为账号设计分析提供「昵称/简介」相关维度列表，便于在 Prompt 中引用
- 提供维度优先级和上下文管理功能，优化 Token 使用
"""

from typing import Dict, List, Optional, Tuple

import logging

from models.models import AnalysisDimension

logger = logging.getLogger(__name__)


# ========== Token 估算常量 ==========
# 估算：中文每字符约 2 tokens，英文每单词约 1.3 tokens，JSON 开销约 50 tokens
TOKEN_PER_CHINESE_CHAR = 2
TOKEN_PER_OTHER_CHAR = 0.5
JSON_OVERHEAD_ESTIMATE = 50


def estimate_dimension_tokens(dim: AnalysisDimension) -> int:
    """
    估算单个维度在 prompt 中占用的 token 数。

    估算公式：name + description + examples + usage_tips + JSON 格式开销
    """
    estimate = 0

    if dim.name:
        estimate += len(dim.name) * TOKEN_PER_CHINESE_CHAR
    if dim.description:
        estimate += len(dim.description) * TOKEN_PER_CHINESE_CHAR
    if dim.examples:
        estimate += len(dim.examples) * TOKEN_PER_CHINESE_CHAR
    if dim.usage_tips:
        estimate += len(dim.usage_tips) * TOKEN_PER_CHINESE_CHAR

    # JSON 格式开销（字段名、标点、缩进）
    estimate += JSON_OVERHEAD_ESTIMATE

    return int(estimate)


def select_dimensions_by_token_budget(
    dims: List[AnalysisDimension],
    token_budget: int = 3000,
    min_dims: int = 3,
    max_dims: int = 15
) -> Tuple[List[AnalysisDimension], int]:
    """
    根据 Token 预算智能选择维度。

    策略：
    1. 按 importance（重要性）降序排序
    2. 按优先级依次添加，直到 token 预算用完
    3. 确保至少保留 min_dims 个维度

    Args:
        dims: 可用维度列表
        token_budget: 允许的 Token 预算（默认 3000）
        min_dims: 最少保留维度数
        max_dims: 最多保留维度数

    Returns:
        (选中的维度列表, 估算的总 token 数)
    """
    if not dims:
        return [], 0

    # 按 importance 降序、sort_order 升序排序
    sorted_dims = sorted(
        dims,
        key=lambda d: (
            -(getattr(d, 'importance', 1) or 1),
            getattr(d, 'sort_order', 0) or 0
        )
    )

    selected = []
    used_tokens = 0

    for dim in sorted_dims:
        if len(selected) >= max_dims:
            break

        dim_tokens = estimate_dimension_tokens(dim)

        # 如果加这个维度会超预算
        if used_tokens + dim_tokens > token_budget and len(selected) >= min_dims:
            # 检查是否是最后一个必要维度
            continue

        selected.append(dim)
        used_tokens += dim_tokens

    # 如果选得太少，强制加入一些
    if len(selected) < min_dims:
        remaining = [d for d in sorted_dims if d not in selected]
        for dim in remaining[:min_dims - len(selected)]:
            selected.append(dim)
            used_tokens += estimate_dimension_tokens(dim)

    logger.info(
        f"[DimensionSelect] budget={token_budget}, "
        f"total_dims={len(dims)}, selected={len(selected)}, "
        f"used_tokens≈{used_tokens}"
    )

    return selected, used_tokens


def get_token_aware_dimensions(
    category: str,
    sub_category: Optional[str] = None,
    token_budget: int = 3000
) -> Tuple[List[AnalysisDimension], int]:
    """
    获取考虑 Token 预算的维度列表。

    与 get_active_dimensions 不同，这个函数会：
    1. 获取所有启用的维度
    2. 根据 Token 预算智能筛选
    3. 返回 (维度列表, 估算的 token 数)

    Args:
        category: 一级分类
        sub_category: 二级分类（可选）
        token_budget: Token 预算

    Returns:
        (选中的维度列表, 估算的 token 数)
    """
    from services.llm import estimate_tokens, get_model_context_limit

    dims = get_active_dimensions(category=category, sub_category=sub_category)

    if not dims:
        return [], 0

    # 计算输入内容的 token（如果有）
    input_tokens = 0

    # 模型上下文限制
    limits = get_model_context_limit()
    available_for_dims = token_budget

    return select_dimensions_by_token_budget(
        dims,
        token_budget=available_for_dims,
        min_dims=3,
        max_dims=15
    )


def get_all_dimensions(
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
) -> List[AnalysisDimension]:
    """
    获取所有分析维度（不分启用状态）。

    Args:
        category: 一级分类：account / content / methodology（可选）
        sub_category: 二级分类（可选）
    """
    query = AnalysisDimension.query

    if category:
        query = query.filter(AnalysisDimension.category == category)
    if sub_category:
        query = query.filter(AnalysisDimension.sub_category == sub_category)

    query = query.order_by(AnalysisDimension.sort_order.asc(), AnalysisDimension.id.asc())
    return query.all()


def get_active_dimensions(
    category: Optional[str] = None,
    sub_category: Optional[str] = None,
) -> List[AnalysisDimension]:
    """
    获取启用中的分析维度。

    Args:
        category: 一级分类：account / content / methodology（可选）
        sub_category: 二级分类（可选）
    """
    query = AnalysisDimension.query.filter(AnalysisDimension.is_active.is_(True))

    if category:
        query = query.filter(AnalysisDimension.category == category)
    if sub_category:
        query = query.filter(AnalysisDimension.sub_category == sub_category)

    query = query.order_by(AnalysisDimension.sort_order.asc(), AnalysisDimension.id.asc())
    return query.all()


def get_active_dimension_codes(category: Optional[str] = None) -> List[str]:
    """
    获取指定分类下所有启用中的维度编码列表。
    """
    dims = get_active_dimensions(category=category)
    codes = [d.code for d in dims if d.code]
    logger.debug("Active dimension codes for category %s: %s", category, codes)
    return codes


def filter_modules_by_active_dimensions(
    modules: List[str],
    category: str = "content",
) -> List[str]:
    """
    根据维度管理中启用的维度，过滤前端传入的 modules。

    - 只保留在指定 category 下且 is_active = True 的 code
    - 如果全部被过滤掉，则返回原始 modules，避免前端出现“什么都不分析”的情况
    """
    if not modules:
        return modules

    active_codes = set(get_active_dimension_codes(category=category))
    if not active_codes:
        # 没有配置启用维度，保持原有行为
        return modules

    filtered = [m for m in modules if m in active_codes]

    if not filtered:
        logger.warning(
            "All requested modules %s are inactive under category=%s, "
            "fallback to original modules.",
            modules,
            category,
        )
        return modules

    logger.info(
        "Filter modules by active dimensions, category=%s, requested=%s, used=%s",
        category,
        modules,
        filtered,
    )
    return filtered


def get_dimension_by_code(code: str) -> Optional[AnalysisDimension]:
    """
    根据 code 获取维度对象。

    Args:
        code: 维度编码
    """
    return AnalysisDimension.query.filter(AnalysisDimension.code == code).first()


def get_account_design_dimensions() -> Dict[str, List[Dict[str, str]]]:
    """
    获取账号设计相关维度（昵称 / 简介），供 Prompt 使用。

    Returns:
        {
            "nickname": [{"code": "...", "name": "...", "description": "..."}, ...],
            "bio": [{"code": "...", "name": "...", "description": "..."}, ...]
        }
    """
    result: Dict[str, List[Dict[str, str]]] = {"nickname": [], "bio": []}

    # 前端 key 为 nickname/bio，DB 二级分类为 nickname_analysis/bio_analysis
    for key, db_sub_cat in [("nickname", "nickname_analysis"), ("bio", "bio_analysis")]:
        dims = get_active_dimensions(category="account", sub_category=db_sub_cat)
        items: List[Dict[str, str]] = []
        for d in dims:
            items.append(
                {
                    "code": d.code or "",
                    "name": d.name or "",
                    "description": d.description or "",
                    "prompt_template": d.prompt_template or "",
                    "examples": getattr(d, "examples", None) or "",
                    "usage_tips": getattr(d, "usage_tips", None) or "",
                    "rule_category": d.rule_category or "",
                    "rule_type": d.rule_type or ""
                }
            )
        result[key] = items

    return result

