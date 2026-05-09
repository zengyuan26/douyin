"""
搜索服务配置

配置项说明：
- search.enabled: 是否启用搜索
- search.provider: 搜索服务商 (tavily)
- search.api_key: Tavily API 密钥
- search.cache_enabled: 是否启用缓存
- search.cache_ttl: 缓存有效期（秒）
- search.max_results: 每次搜索最大结果数
- search.batch_size: 批量搜索最大词数
- search.timeout: 搜索超时（秒）
- search.max_retries: 最大重试次数
- search.async_mode: 是否启用异步模式
- search.fallback_on_error: 错误时是否降级
"""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class SearchConfig:
    """搜索服务配置"""

    # 启用开关
    enabled: bool = True

    # 服务商
    provider: str = "tavily"

    # API 配置
    api_key: str = ""
    base_url: str = "https://api.tavily.com"

    # 缓存配置
    cache_enabled: bool = True
    cache_ttl: int = 604800  # 7天

    # 搜索配置
    max_results: int = 5  # 每次搜索最大结果数
    batch_size: int = 5   # 批量搜索最大词数
    timeout: int = 10    # 搜索超时（秒）
    max_retries: int = 2  # 最大重试次数

    # 异步配置
    async_mode: bool = True

    # 降级配置
    fallback_on_error: bool = True

    # 触发条件
    min_duration_for_search: int = 30  # 启用搜索的最小视频时长（秒）

    # 来源配置
    ref_source_visible: bool = True  # 是否在脚本中显示来源

    @classmethod
    def from_env(cls) -> "SearchConfig":
        """从环境变量加载配置"""
        return cls(
            enabled=os.environ.get("SEARCH_ENABLED", "true").lower() == "true",
            provider=os.environ.get("SEARCH_PROVIDER", "tavily"),
            api_key=os.environ.get("TAVILY_API_KEY", ""),
            base_url=os.environ.get("TAVILY_BASE_URL", "https://api.tavily.com"),
            cache_enabled=os.environ.get("SEARCH_CACHE_ENABLED", "true").lower() == "true",
            cache_ttl=int(os.environ.get("SEARCH_CACHE_TTL", "604800")),
            max_results=int(os.environ.get("SEARCH_MAX_RESULTS", "5")),
            batch_size=int(os.environ.get("SEARCH_BATCH_SIZE", "5")),
            timeout=int(os.environ.get("SEARCH_TIMEOUT", "10")),
            max_retries=int(os.environ.get("SEARCH_MAX_RETRIES", "2")),
            async_mode=os.environ.get("SEARCH_ASYNC_MODE", "true").lower() == "true",
            fallback_on_error=os.environ.get("SEARCH_FALLBACK_ON_ERROR", "true").lower() == "true",
            min_duration_for_search=int(os.environ.get("SEARCH_MIN_DURATION", "30")),
            ref_source_visible=os.environ.get("SEARCH_REF_VISIBLE", "true").lower() == "true",
        )

    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.enabled:
            return True

        if self.provider == "tavily" and not self.api_key:
            return False

        if self.timeout <= 0:
            return False

        return True


# 默认配置实例
_default_config: Optional[SearchConfig] = None


def get_default_config() -> SearchConfig:
    """获取默认配置"""
    global _default_config
    if _default_config is None:
        _default_config = SearchConfig.from_env()
    return _default_config


def update_config(config: SearchConfig) -> None:
    """更新默认配置"""
    global _default_config
    _default_config = config
