"""
搜索降级策略

确保搜索失败时不影响主流程
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from services.search.tavily_client import TavilySearchClient, SearchAPIError

logger = logging.getLogger(__name__)


async def search_with_fallback(
    client: TavilySearchClient,
    query: str,
    max_results: int = 5,
    fallback_on_error: bool = True,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    带降级的搜索函数

    核心原则：搜索失败不影响脚本生成

    Args:
        client: Tavily 客户端
        query: 搜索词
        max_results: 最大结果数
        fallback_on_error: 是否启用降级
        timeout: 超时时间（秒）

    Returns:
        搜索结果，失败时返回空结果

    Raises:
        SearchAPIError: 当 fallback_on_error=False 时
    """
    try:
        # 带超时的搜索
        if timeout:
            result = await asyncio.wait_for(
                asyncio.to_thread(client.search, query, max_results),
                timeout=timeout
            )
        else:
            result = await asyncio.to_thread(client.search, query, max_results)

        return result

    except asyncio.TimeoutError:
        # 超时降级
        logger.warning(f"搜索超时，降级返回空结果: query={query[:30]}...")
        if fallback_on_error:
            return {"results": [], "answer": None, "error": "timeout"}
        else:
            raise SearchAPIError(f"搜索超时（{timeout}秒）", 0)

    except SearchAPIError as e:
        # API 错误降级
        logger.warning(f"搜索API错误，降级返回空结果: {e}")
        if fallback_on_error:
            return {"results": [], "answer": None, "error": str(e)}
        else:
            raise

    except Exception as e:
        # 未知错误降级
        logger.error(f"搜索未知错误，降级返回空结果: {e}", exc_info=True)
        if fallback_on_error:
            return {"results": [], "answer": None, "error": str(e)}
        else:
            raise SearchAPIError(f"搜索失败: {str(e)}", 0)


class FallbackPolicy:
    """
    降级策略配置

    可根据不同场景配置不同的降级行为
    """

    # 降级策略类型
    STRICT = "strict"      # 严格模式，失败抛出异常
    GRACEFUL = "graceful"  # 优雅降级，返回空结果
    RETRY = "retry"        # 重试模式，多次重试后降级

    @classmethod
    def get_policy(cls, policy_type: str = "graceful") -> Dict[str, Any]:
        """
        获取降级策略配置

        Args:
            policy_type: 策略类型

        Returns:
            策略配置字典
        """
        policies = {
            cls.STRICT: {
                "fallback_on_error": False,
                "max_retries": 0,
                "timeout": 5,
            },
            cls.GRACEFUL: {
                "fallback_on_error": True,
                "max_retries": 1,
                "timeout": 10,
            },
            cls.RETRY: {
                "fallback_on_error": True,
                "max_retries": 3,
                "timeout": 15,
            },
        }

        return policies.get(policy_type, policies[cls.GRACEFUL])
