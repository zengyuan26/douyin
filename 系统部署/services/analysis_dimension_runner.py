"""
分析维度执行/辅助工具

主要职责：
- 提供按分类读取「启用中的」分析维度的便捷方法
- 为内容分析过滤前端传入的 modules，只保留在维度管理中启用的维度
- 为账号设计分析提供「昵称/简介」相关维度列表，便于在 Prompt 中引用
"""

from typing import Dict, List, Optional

import logging

from models.models import AnalysisDimension

logger = logging.getLogger(__name__)


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

