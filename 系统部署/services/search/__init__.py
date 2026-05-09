"""
搜索服务模块

包含：
- Tavily API 客户端
- 搜索服务层
- 缓存机制
- 引用溯源
- 异步任务处理
"""

from services.search.tavily_client import TavilySearchClient, SearchAPIError
from services.search.models import (
    SearchReference,
    ReferenceType,
    SearchTriggerDecision,
    SearchResult,
)
from services.search.config import SearchConfig, get_default_config
from services.search.search_service import SearchService, SearchNeedsAnalyzer
from services.search.cache import SearchCache
from services.search.fallback import search_with_fallback, FallbackPolicy
from services.search.async_task import (
    AsyncSearchTask,
    AsyncTaskStatus,
    AsyncTaskQueue,
    get_task_queue,
)
from services.search.trigger import SearchTriggerDecider
from services.search.search_integration import (
    SearchEnhancementIntegrator,
    get_search_integrator,
)

__all__ = [
    # 客户端
    'TavilySearchClient',
    'SearchAPIError',
    # 模型
    'SearchReference',
    'ReferenceType',
    'SearchTriggerDecision',
    'SearchResult',
    # 配置
    'SearchConfig',
    'get_default_config',
    # 服务
    'SearchService',
    'SearchNeedsAnalyzer',
    # 缓存
    'SearchCache',
    # 降级
    'search_with_fallback',
    'FallbackPolicy',
    # 异步
    'AsyncSearchTask',
    'AsyncTaskStatus',
    'AsyncTaskQueue',
    'get_task_queue',
    # 触发
    'SearchTriggerDecider',
    # 集成
    'SearchEnhancementIntegrator',
    'get_search_integrator',
]
