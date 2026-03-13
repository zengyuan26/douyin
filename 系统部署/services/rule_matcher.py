"""
规则匹配工具

封装针对文本在知识规则库中做相似匹配的逻辑，供账号设计/维度分析等场景复用。
"""

from typing import List, Dict, Optional

import logging

from models.models import KnowledgeRule

logger = logging.getLogger(__name__)


def match_rules_for_text(
    text: str,
    category: Optional[str] = None,
    rule_types: Optional[List[str]] = None,
    status: str = "active",
    limit: int = 5,
) -> List[Dict]:
    """
    在知识规则表中查找与给定文本相似的规则。

    Args:
        text: 待匹配的原始文本（如昵称、简介等）
        category: 规则大类（如 operation / keywords 等），可选
        rule_types: 需要限定的 rule_type 列表，可选
        status: 规则状态过滤，默认只匹配 active
        limit: 返回规则条数上限
    """
    if not text:
        return []

    query = KnowledgeRule.query

    if status:
        query = query.filter(KnowledgeRule.status == status)
    if category:
        query = query.filter(KnowledgeRule.category == category)
    if rule_types:
        query = query.filter(KnowledgeRule.rule_type.in_(rule_types))

    rules = query.all()
    text_lower = text.lower()

    matched: List[Dict] = []

    for rule in rules:
        rule_title = (rule.rule_title or "").lower()
        rule_content = (rule.rule_content or "").lower()

        # 完全包含匹配
        if (
            rule_title
            and (text_lower in rule_title or rule_title in text_lower)
        ) or (
            rule_content
            and (text_lower in rule_content or rule_content in text_lower)
        ):
            matched.append(
                {
                    "id": rule.id,
                    "title": rule.rule_title,
                    "content": (rule.rule_content or "")[:200],
                    "category": rule.category,
                    "match_type": "title_or_content_contains",
                }
            )
            continue

        # 简单字符交集匹配（粗粒度，避免漏掉明显相似项）
        title_keywords = set(rule_title) | set(rule_content)
        common = set(text_lower) & title_keywords
        if len(common) >= 2:
            matched.append(
                {
                    "id": rule.id,
                    "title": rule.rule_title,
                    "content": (rule.rule_content or "")[:200],
                    "category": rule.category,
                    "match_type": "char_overlap",
                }
            )

        if len(matched) >= limit:
            break

    logger.debug(
        "Matched %s rules for text=%r, category=%s, rule_types=%s",
        len(matched),
        text[:50],
        category,
        rule_types,
    )
    return matched

