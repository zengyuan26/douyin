"""
Tavily AI Search API 客户端

官方文档: https://docs.tavily.com/docs/python-sdk
"""

import logging
import time
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


class SearchAPIError(Exception):
    """搜索 API 错误"""

    def __init__(self, message: str, status_code: int = 0):
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{status_code}] {message}")


class TavilySearchClient:
    """
    Tavily AI 搜索客户端

    功能：
    - 中文搜索词优化
    - 搜索结果格式化
    - 错误处理
    - 超时控制
    """

    BASE_URL = "https://api.tavily.com"

    def __init__(
        self,
        api_key: str,
        timeout: int = 10,
        max_retries: int = 2,
    ):
        """
        初始化 Tavily 搜索客户端

        Args:
            api_key: Tavily API 密钥
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def _build_search_query(self, queries: List[str]) -> str:
        """
        构建搜索查询

        中文场景优化：
        - 保留中文关键词
        - 添加英文补充（可选）
        - 组合多个查询词

        Args:
            queries: 搜索词列表

        Returns:
            组合后的搜索查询字符串
        """
        if not queries:
            return ""

        # 过滤空值
        queries = [q.strip() for q in queries if q.strip()]
        if not queries:
            return ""

        # 组合搜索词
        query = " ".join(queries)

        # 添加搜索意图词（针对短视频内容）
        intent_suffixes = ["原因", "方法", "技巧", "秘诀", "干货", "解析"]

        # 检查是否需要添加意图词
        has_intent = any(suffix in query for suffix in intent_suffixes)
        if not has_intent:
            query += " 解读 分析"

        return query

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_answer: bool = False,
        include_raw_links: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数
            include_answer: 是否包含 AI 总结答案
            include_raw_links: 是否包含原始链接
            **kwargs: 其他 Tavily API 参数

        Returns:
            搜索结果字典

        Raises:
            SearchAPIError: API 调用失败
        """
        if not query:
            return {"results": [], "answer": None}

        url = f"{self.BASE_URL}/search"

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_links": include_raw_links,
            "search_depth": kwargs.get("search_depth", "basic"),
        }

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()

                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )

                duration_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    result = response.json()
                    logger.info(
                        f"Tavily搜索成功: query={query[:30]}..., "
                        f"results={len(result.get('results', []))}, "
                        f"duration={duration_ms:.0f}ms"
                    )
                    return result

                # API 错误
                error_msg = response.text or f"HTTP {response.status_code}"
                last_error = SearchAPIError(error_msg, response.status_code)

                # 认证错误不重试
                if response.status_code == 401:
                    logger.error(f"Tavily API 认证失败: {error_msg}")
                    break

                logger.warning(
                    f"Tavily搜索失败(尝试{attempt + 1}/{self.max_retries + 1}): "
                    f"{error_msg}"
                )

            except requests.Timeout:
                last_error = SearchAPIError(f"搜索超时（{self.timeout}秒）", 0)
                logger.warning(f"Tavily搜索超时: query={query[:30]}...")

            except requests.RequestException as e:
                last_error = SearchAPIError(f"网络错误: {str(e)}", 0)
                logger.warning(f"Tavily网络错误: {e}")

            # 重试前等待
            if attempt < self.max_retries:
                time.sleep(1 * (attempt + 1))  # 指数退避

        # 所有重试都失败
        raise last_error

    def search_batch(
        self,
        queries: List[str],
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        批量搜索

        Args:
            queries: 搜索词列表
            max_results: 每个查询的最大结果数

        Returns:
            搜索结果列表
        """
        results = []

        for query in queries:
            try:
                result = self.search(query, max_results=max_results)
                results.append(result)
            except SearchAPIError as e:
                logger.error(f"批量搜索失败: query={query}, error={e}")
                results.append({"results": [], "answer": None, "error": str(e)})

        return results

    def format_results(self, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        格式化搜索结果

        提取关键字段，便于后续处理

        Args:
            raw_results: 原始搜索结果

        Returns:
            格式化后的结果列表
        """
        formatted = []

        for item in raw_results.get("results", []):
            formatted.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
            })

        return formatted

    def extract_author(self, result: Dict[str, Any]) -> str:
        """
        提取作者信息

        从搜索结果中尝试提取作者名称

        Args:
            result: 单条搜索结果

        Returns:
            作者名称，未找到则返回空字符串
        """
        content = result.get("content", "")
        title = result.get("title", "")

        # 常见作者模式
        patterns = [
            r"作者[：:]\s*(\S+)",
            r"出自[：:]\s*(\S+)",
            r"——\s*(\S+)",
            r"(\S+)曾说",
            r"(\S+)表示",
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, content + title)
            if match:
                return match.group(1)

        return ""
