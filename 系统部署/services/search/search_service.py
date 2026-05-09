"""
搜索服务层

核心服务：
- SearchService: 搜索服务主类
- SearchNeedsAnalyzer: 搜索需求分析器
"""

import logging
import time
from typing import List, Dict, Any, Optional

from services.search.tavily_client import TavilySearchClient, SearchAPIError
from services.search.models import SearchReference, ReferenceType, SearchResult
from services.search.config import SearchConfig, get_default_config
from services.search.cache import SearchCache
from services.search.fallback import search_with_fallback

logger = logging.getLogger(__name__)


class SearchNeedsAnalyzer:
    """
    搜索需求分析器

    分析脚本生成需求，判断是否需要搜索，以及搜索什么内容
    """

    # 引用类型关键词映射
    TYPE_KEYWORDS = {
        ReferenceType.QUOTE: ["名言", "说", "曾说", "说过", "观点", "金句"],
        ReferenceType.DATA: ["数据", "统计", "研究", "报告", "多少", "比例"],
        ReferenceType.CASE: ["案例", "例子", "故事", "企业", "公司", "成功"],
        ReferenceType.HOT: ["热点", "新闻", "最近", "今日", "最新", "趋势"],
        ReferenceType.TERM: ["概念", "定义", "解释", "什么是", "术语"],
    }

    # 需要搜索的话题类型
    SEARCHABLE_TOPIC_TYPES = [
        "知识科普", "解决方案", "疑问揭秘", "时事热点", "行业分析"
    ]

    # 短时长话题类型（一般不搜索）
    SHORT_DURATION_TYPES = ["情感共鸣", "痛点共鸣"]

    def analyze(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
        style: str = ""
    ) -> List[Dict[str, Any]]:
        """
        分析搜索需求

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长（秒）
            style: 风格要求

        Returns:
            搜索需求列表，每项包含 type, keywords, priority
        """
        needs = []

        # 1. 时长判断
        if duration < 30:
            logger.debug(f"视频时长{duration}秒过短，跳过搜索")
            return needs

        # 2. 话题类型判断
        if topic_type in self.SHORT_DURATION_TYPES and duration < 60:
            logger.debug(f"话题类型{topic_type}不触发搜索")
            return needs

        # 3. 分析引用类型需求
        for ref_type, keywords in self.TYPE_KEYWORDS.items():
            if any(kw in topic for kw in keywords):
                # 提取关键词
                query_keywords = self._extract_keywords(topic, keywords)
                if query_keywords:
                    priority = self._calculate_priority(ref_type, topic_type, duration)
                    needs.append({
                        "type": ref_type,
                        "keywords": query_keywords,
                        "priority": priority
                    })

        # 4. 话题类型默认需求
        if topic_type in self.SEARCHABLE_TOPIC_TYPES and not needs:
            default_keywords = self._extract_default_keywords(topic)
            if default_keywords:
                needs.append({
                    "type": ReferenceType.DATA,
                    "keywords": default_keywords,
                    "priority": 2
                })

        # 5. 按优先级排序
        needs.sort(key=lambda x: x["priority"], reverse=True)

        return needs

    def _extract_keywords(self, topic: str, type_keywords: List[str]) -> List[str]:
        """从主题中提取相关关键词"""
        keywords = []

        # 直接提取包含类型关键词的片段
        for kw in type_keywords:
            import re
            pattern = rf"[，。、]{kw}|[^，。、]*{kw}[^，。、]*"
            matches = re.findall(pattern, topic)
            keywords.extend(matches)

        # 如果没有匹配，提取主题前部作为关键词
        if not keywords:
            main_topic = topic.split("，")[0].split("。")[0]
            if len(main_topic) <= 20:
                keywords = [main_topic]

        return list(set(keywords))[:3]  # 去重，最多3个

    def _extract_default_keywords(self, topic: str) -> List[str]:
        """提取默认搜索关键词"""
        # 分割主题，提取核心词
        parts = topic.replace("、", ",").replace("和", ",").split(",")
        keywords = [p.strip() for p in parts if p.strip() and len(p.strip()) <= 15]
        return keywords[:2]

    def _calculate_priority(
        self,
        ref_type: ReferenceType,
        topic_type: str,
        duration: int
    ) -> int:
        """计算搜索优先级"""
        priority = 2  # 默认优先级

        # 时长越长，优先级越高
        if duration > 120:
            priority += 1

        # 话题类型相关
        if topic_type == "知识科普" and ref_type == ReferenceType.DATA:
            priority = 3
        elif topic_type == "时事热点" and ref_type == ReferenceType.HOT:
            priority = 3

        return priority


class SearchService:
    """
    搜索服务

    功能：
    - 搜索需求分析
    - 引用内容搜索
    - 结果缓存
    - 降级处理
    """

    def __init__(
        self,
        tavily_client: Optional[TavilySearchClient] = None,
        config: Optional[SearchConfig] = None,
        cache: Optional[SearchCache] = None,
    ):
        """
        初始化搜索服务

        Args:
            tavily_client: Tavily 客户端
            config: 搜索配置
            cache: 缓存实例
        """
        self.config = config or get_default_config()
        self.tavily = tavily_client or TavilySearchClient(
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        self.cache = cache
        self.analyzer = SearchNeedsAnalyzer()

        logger.info(f"SearchService初始化: async_mode={self.config.async_mode}")

    async def search_reference(
        self,
        queries: List[str],
        ref_type: ReferenceType,
    ) -> List[SearchReference]:
        """
        搜索引用内容

        Args:
            queries: 搜索词列表
            ref_type: 引用类型

        Returns:
            搜索引用列表
        """
        if not queries or not self.config.enabled:
            return []

        references = []

        for query in queries:
            try:
                ref = await self._search_single(
                    query=query,
                    ref_type=ref_type,
                )
                if ref:
                    references.append(ref)
            except Exception as e:
                logger.error(f"搜索失败: query={query}, error={e}")

        # 按相关度排序
        references.sort(key=lambda x: x.score, reverse=True)

        return references[:self.config.max_results]

    async def _search_single(
        self,
        query: str,
        ref_type: ReferenceType,
    ) -> Optional[SearchReference]:
        """
        单次搜索

        Args:
            query: 搜索词
            ref_type: 引用类型

        Returns:
            搜索引用或 None
        """
        # 1. 检查缓存
        if self.cache and self.config.cache_enabled:
            cached = await self.cache.get(query, ref_type.value)
            if cached:
                logger.debug(f"缓存命中: {query}")
                return self._parse_result(cached, ref_type, query, cached=True)

        # 2. 执行搜索（带降级）
        result = await search_with_fallback(
            client=self.tavily,
            query=query,
            max_results=3,
            fallback_on_error=self.config.fallback_on_error,
        )

        if not result or not result.get("results"):
            return None

        # 3. 保存缓存
        if self.cache and self.config.cache_enabled:
            await self.cache.set(query, ref_type.value, result, ttl=self.config.cache_ttl)

        # 4. 解析结果
        return self._parse_result(result, ref_type, query)

    def _parse_result(
        self,
        raw_result: Dict[str, Any],
        ref_type: ReferenceType,
        query: str,
        cached: bool = False,
    ) -> Optional[SearchReference]:
        """
        解析搜索结果

        Args:
            raw_result: 原始搜索结果
            ref_type: 引用类型
            query: 搜索词
            cached: 是否来自缓存

        Returns:
            解析后的引用
        """
        results = raw_result.get("results", [])
        if not results:
            return None

        # 取第一条结果
        top_result = results[0]

        # 提取作者
        author = self.tavily.extract_author(top_result)

        # 构建引用
        reference = SearchReference(
            type=ref_type,
            content=top_result.get("content", "")[:500],  # 限制长度
            source_name=top_result.get("title", "")[:100],
            source_url=top_result.get("url", ""),
            author=author,
            score=top_result.get("score", 0.0),
            search_query=query,
        )

        return reference

    async def analyze_and_search(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
    ) -> List[SearchReference]:
        """
        分析需求并执行搜索

        一步完成需求分析和搜索

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长

        Returns:
            搜索引用列表
        """
        # 1. 分析搜索需求
        needs = self.analyzer.analyze(topic, topic_type, duration)

        if not needs:
            logger.info(f"无需搜索: topic={topic}")
            return []

        # 2. 执行搜索
        all_references = []
        for need in needs:
            refs = await self.search_reference(
                queries=need["keywords"],
                ref_type=need["type"],
            )
            all_references.extend(refs)

        # 3. 去重并排序
        seen = set()
        unique_refs = []
        for ref in all_references:
            if ref.source_url not in seen:
                seen.add(ref.source_url)
                unique_refs.append(ref)

        unique_refs.sort(key=lambda x: x.score, reverse=True)

        logger.info(f"搜索完成: topic={topic}, refs={len(unique_refs)}")

        return unique_refs

    def should_search(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
    ) -> bool:
        """
        判断是否应该触发搜索

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长

        Returns:
            是否应该搜索
        """
        if not self.config.enabled:
            return False

        if duration < self.config.min_duration_for_search:
            return False

        needs = self.analyzer.analyze(topic, topic_type, duration)
        return len(needs) > 0
