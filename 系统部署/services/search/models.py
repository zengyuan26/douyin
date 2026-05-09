"""
搜索服务数据模型

包含：
- ReferenceType: 引用类型枚举
- SearchReference: 搜索引用模型
- SearchTriggerDecision: 触发决策模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class ReferenceType(Enum):
    """引用类型"""
    QUOTE = "quote"       # 名言引用
    DATA = "data"         # 数据引用
    CASE = "case"         # 案例引用
    HOT = "hot"           # 热点引用
    TERM = "term"         # 术语解释


@dataclass
class SearchReference:
    """搜索引用"""
    type: ReferenceType
    content: str
    source_name: str = ""
    source_url: str = ""
    author: str = ""
    published_date: Optional[datetime] = None
    score: float = 0.0
    search_query: str = ""

    def format_for_script(self) -> str:
        """
        格式化为脚本中的引用格式

        示例：
        "查理·芒格曾说："..."（来源：穷查理宝典）
        """
        parts = []

        if self.source_name:
            parts.append(f"（来源：{self.source_name}）")

        if self.source_url and len(self.source_url) < 50:
            parts.append(f" {self.source_url}")

        return "".join(parts)

    def format_full(self) -> str:
        """
        格式化为完整引用信息

        示例：
        ┌────────────────────────────────────────────────────────┐
        │ "引用内容"                                              │
        │                                                          │
        │  ── 来源：穷查理宝典                                    │
        │     作者：查理·芒格                                     │
        │     网址：https://example.com                           │
        │     发布：2025-01-01                                    │
        └────────────────────────────────────────────────────────┘
        """
        lines = [
            f'"{self.content}"',
            "",
            f"── 来源：{self.source_name or '未知来源'}",
        ]

        if self.author:
            lines.append(f"     作者：{self.author}")

        if self.source_url:
            lines.append(f"     网址：{self.source_url}")

        if self.published_date:
            lines.append(f"     发布：{self.published_date.strftime('%Y-%m-%d')}")

        if self.score > 0:
            lines.append(f"     可信度：{self.score:.0%}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "content": self.content,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "author": self.author,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "score": self.score,
            "search_query": self.search_query,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchReference":
        """从字典创建"""
        return cls(
            type=ReferenceType(data.get("type", "quote")),
            content=data["content"],
            source_name=data.get("source_name", ""),
            source_url=data.get("source_url", ""),
            author=data.get("author", ""),
            published_date=datetime.fromisoformat(data["published_date"])
                if data.get("published_date") else None,
            score=data.get("score", 0.0),
            search_query=data.get("search_query", ""),
        )


@dataclass
class SearchTriggerDecision:
    """搜索触发决策"""
    should_search: bool
    reason: str = ""
    suggested_queries: List[str] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def search(cls, reason: str, queries: List[str], priority: int = 1) -> "SearchTriggerDecision":
        """创建搜索决策"""
        return cls(
            should_search=True,
            reason=reason,
            suggested_queries=queries,
            priority=priority
        )

    @classmethod
    def skip(cls, reason: str) -> "SearchTriggerDecision":
        """创建跳过决策"""
        return cls(
            should_search=False,
            reason=reason,
        )


@dataclass
class SearchResult:
    """搜索结果"""
    query: str
    references: List[SearchReference]
    cached: bool = False
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def has_references(self) -> bool:
        return len(self.references) > 0
