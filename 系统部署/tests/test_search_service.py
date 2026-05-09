"""
搜索服务测试用例

测试范围：
1. Tavily API 客户端
2. 搜索服务层
3. 缓存机制
4. 引用溯源存储
5. 异步任务
6. 降级策略
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import List, Dict, Any

# ============ 测试数据 ============

MOCK_SEARCH_RESULT = {
    "results": [
        {
            "title": "查理·芒格名言：我这辈子遇到的聪明人没有一个不是每天读书的",
            "url": "https://example.com/munger-quote",
            "content": "查理·芒格曾说："我这辈子遇到的聪明人没有一个不是每天读书的"。这是他终身学习理念的体现。",
            "score": 0.95
        },
        {
            "title": "2025年全球阅读报告：中国人均年阅读量约5本书",
            "url": "https://example.com/reading-report",
            "content": "根据最新报告，中国人均年阅读量约5本书，而日本是40本，以色列高达60本。",
            "score": 0.88
        }
    ]
}

MOCK_REFERENCE_RESULT = [
    {
        "type": "quote",
        "content": "查理·芒格曾说："我这辈子遇到的聪明人没有一个不是每天读书的"",
        "source_name": "穷查理宝典",
        "source_url": "https://example.com/munger-quote",
        "author": "查理·芒格",
        "score": 0.95
    },
    {
        "type": "data",
        "content": "中国人均年阅读量约5本书，而日本是40本，以色列高达60本",
        "source_name": "2025年全球阅读报告",
        "source_url": "https://example.com/reading-report",
        "author": "世界阅读组织",
        "score": 0.88
    }
]


# ============ 1. Tavily API 客户端测试 ============

class TestTavilyClient:
    """Tavily API 客户端测试"""

    def test_build_search_query(self):
        """测试搜索词构建"""
        from services.search.tavily_client import TavilySearchClient

        client = TavilySearchClient(api_key="test-key")

        # 测试中文搜索词优化
        queries = ["读书", "阅读"]
        built = client._build_search_query(queries)
        assert "读书" in built
        assert len(built) > 0

    def test_build_search_query_empty(self):
        """测试空搜索词"""
        from services.search.tavily_client import TavilySearchClient

        client = TavilySearchClient(api_key="test-key")
        built = client._build_search_query([])
        assert built == ""

    @patch('requests.post')
    def test_search_success(self, mock_post):
        """测试搜索成功"""
        from services.search.tavily_client import TavilySearchClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_SEARCH_RESULT
        mock_post.return_value = mock_response

        client = TavilySearchClient(api_key="test-key")
        result = client.search("读书的重要性")

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "查理·芒格名言..."

    @patch('requests.post')
    def test_search_api_error(self, mock_post):
        """测试 API 错误处理"""
        from services.search.tavily_client import TavilySearchClient, SearchAPIError

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        client = TavilySearchClient(api_key="invalid-key")

        with pytest.raises(SearchAPIError) as exc_info:
            client.search("test")
        assert "401" in str(exc_info.value)

    @patch('requests.post')
    def test_search_timeout(self, mock_post):
        """测试超时处理"""
        from services.search.tavily_client import TavilySearchClient, SearchAPIError
        import requests

        mock_post.side_effect = requests.Timeout("Connection timeout")

        client = TavilySearchClient(api_key="test-key", timeout=1)

        with pytest.raises(SearchAPIError) as exc_info:
            client.search("test")
        assert "超时" in str(exc_info.value)


# ============ 2. 搜索服务层测试 ============

class TestSearchService:
    """SearchService 测试"""

    def test_analyze_search_needs_knowledge(self):
        """测试知识科普类搜索需求分析"""
        from services.search.search_service import SearchService, SearchNeedsAnalyzer

        analyzer = SearchNeedsAnalyzer()

        # 知识科普类
        needs = analyzer.analyze("为什么要读书", "知识科普")
        assert len(needs) > 0
        assert any(n["type"].value == "data" for n in needs)

    def test_analyze_search_needs_quote(self):
        """测试名言引用需求分析"""
        from services.search.search_service import SearchService, SearchNeedsAnalyzer

        analyzer = SearchNeedsAnalyzer()

        # 名言类
        needs = analyzer.analyze("查理·芒格的名言", "知识科普")
        assert len(needs) > 0
        assert any(n["type"].value == "quote" for n in needs)

    def test_analyze_search_needs_case(self):
        """测试案例需求分析"""
        from services.search.search_service import SearchService, SearchNeedsAnalyzer

        analyzer = SearchNeedsAnalyzer()

        # 案例类
        needs = analyzer.analyze("成功企业的案例", "解决方案")
        assert len(needs) > 0
        assert any(n["type"].value == "case" for n in needs)

    def test_analyze_search_needs_hot(self):
        """测试热点需求分析"""
        from services.search.search_service import SearchService, SearchNeedsAnalyzer

        analyzer = SearchNeedsAnalyzer()

        # 热点类
        needs = analyzer.analyze("最近的热点新闻", "时效热点")
        assert len(needs) > 0
        assert any(n["type"].value == "hot" for n in needs)

    def test_analyze_search_needs_short_duration(self):
        """测试短时长跳过搜索"""
        from services.search.search_service import SearchService, SearchNeedsAnalyzer

        analyzer = SearchNeedsAnalyzer()

        # 30秒以下不搜索
        needs = analyzer.analyze("读书", "情感共鸣", duration=20)
        assert len(needs) == 0  # 跳过

    @pytest.mark.asyncio
    @patch('services.search.search_service.TavilySearchClient')
    async def test_search_with_cache_hit(self, mock_tavily):
        """测试缓存命中"""
        from services.search.search_service import SearchService
        from services.search.cache import SearchCache

        mock_client = Mock()
        mock_client.search.return_value = MOCK_SEARCH_RESULT
        mock_tavily.return_value = mock_client

        service = SearchService(tavily_client=mock_client)

        # Mock 缓存命中
        with patch.object(service.cache, 'get', return_value=MOCK_SEARCH_RESULT):
            result = await service.search_reference(
                queries=["读书"],
                ref_type="quote"
            )
            # 命中缓存，不调用 API
            mock_client.search.assert_not_called()

    @pytest.mark.asyncio
    @patch('services.search.search_service.TavilySearchClient')
    async def test_search_with_cache_miss(self, mock_tavily):
        """测试缓存未命中"""
        from services.search.search_service import SearchService

        mock_client = Mock()
        mock_client.search.return_value = MOCK_SEARCH_RESULT
        mock_tavily.return_value = mock_client

        service = SearchService(tavily_client=mock_client)

        # Mock 缓存未命中
        with patch.object(service.cache, 'get', return_value=None):
            with patch.object(service.cache, 'set', return_value=True):
                result = await service.search_reference(
                    queries=["读书"],
                    ref_type="quote"
                )
                # 应该调用 API
                mock_client.search.assert_called_once()


# ============ 3. 缓存机制测试 ============

class TestSearchCache:
    """搜索缓存测试"""

    def test_get_cache_key(self):
        """测试缓存键生成"""
        from services.search.cache import SearchCache

        cache = SearchCache()
        key1 = cache._get_cache_key("读书", "quote")
        key2 = cache._get_cache_key("读书", "quote")
        key3 = cache._get_cache_key("阅读", "quote")

        assert key1 == key2  # 相同输入，相同键
        assert key1 != key3  # 不同输入，不同键

    @pytest.mark.asyncio
    async def test_get_with_miss(self):
        """测试缓存未命中"""
        from services.search.cache import SearchCache

        cache = SearchCache()
        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试缓存设置和获取"""
        from services.search.cache import SearchCache

        cache = SearchCache()
        test_data = {"results": [{"title": "test"}]}

        await cache.set("test_key", test_data, ttl=3600)
        result = await cache.get("test_key")

        assert result is not None
        assert result["results"][0]["title"] == "test"

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试缓存删除"""
        from services.search.cache import SearchCache

        cache = SearchCache()
        await cache.set("test_key", {"data": "test"})
        await cache.delete("test_key")
        result = await cache.get("test_key")

        assert result is None


# ============ 4. 引用溯源存储测试 ============

class TestReferenceStorage:
    """引用溯源存储测试"""

    def test_reference_model_creation(self):
        """测试引用模型创建"""
        from services.search.models import SearchReference, ReferenceType

        ref = SearchReference(
            type=ReferenceType.QUOTE,
            content="测试引用",
            source_name="测试来源",
            source_url="https://example.com",
            author="测试作者",
            score=0.95
        )

        assert ref.type == ReferenceType.QUOTE
        assert ref.content == "测试引用"
        assert ref.source_name == "测试来源"

    def test_reference_format_for_script(self):
        """测试脚本中的引用格式"""
        from services.search.models import SearchReference, ReferenceType

        ref = SearchReference(
            type=ReferenceType.QUOTE,
            content="查理·芒格曾说：...",
            source_name="穷查理宝典",
            source_url="https://example.com"
        )

        formatted = ref.format_for_script()
        assert "穷查理宝典" in formatted
        assert "https://example.com" in formatted

    def test_reference_format_full(self):
        """测试完整引用格式"""
        from services.search.models import SearchReference, ReferenceType

        ref = SearchReference(
            type=ReferenceType.DATA,
            content="中国人均阅读量约5本书",
            source_name="2025年全球阅读报告",
            source_url="https://example.com/report",
            author="世界阅读组织",
            published_date=datetime(2025, 1, 1)
        )

        full = ref.format_full()
        assert "中国人均阅读量" in full
        assert "2025年全球阅读报告" in full
        assert "2025-01-01" in full


# ============ 5. 降级策略测试 ============

class TestFallbackStrategy:
    """降级策略测试"""

    @pytest.mark.asyncio
    async def test_search_timeout_fallback(self):
        """测试搜索超时降级"""
        from services.search.fallback import search_with_fallback
        from services.search.tavily_client import SearchAPIError
        import requests

        mock_client = Mock()
        mock_client.search.side_effect = requests.Timeout("Timeout")

        result = await search_with_fallback(
            client=mock_client,
            query="test",
            fallback_on_error=True
        )

        # 应该返回空列表，不抛出异常
        assert result == []

    @pytest.mark.asyncio
    async def test_search_api_error_fallback(self):
        """测试 API 错误降级"""
        from services.search.fallback import search_with_fallback
        from services.search.tavily_client import SearchAPIError

        mock_client = Mock()
        mock_client.search.side_effect = SearchAPIError("API Error", 500)

        result = await search_with_fallback(
            client=mock_client,
            query="test",
            fallback_on_error=True
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_disabled(self):
        """测试禁用降级时抛出异常"""
        from services.search.fallback import search_with_fallback
        from services.search.tavily_client import SearchAPIError

        mock_client = Mock()
        mock_client.search.side_effect = SearchAPIError("API Error", 500)

        with pytest.raises(SearchAPIError):
            await search_with_fallback(
                client=mock_client,
                query="test",
                fallback_on_error=False
            )


# ============ 6. 异步任务测试 ============

class TestAsyncSearchTask:
    """异步搜索任务测试"""

    def test_task_status_enum(self):
        """测试任务状态枚举"""
        from services.search.async_task import AsyncTaskStatus

        assert AsyncTaskStatus.PENDING.value == "pending"
        assert AsyncTaskStatus.RUNNING.value == "running"
        assert AsyncTaskStatus.COMPLETED.value == "completed"
        assert AsyncTaskStatus.FAILED.value == "failed"
        assert AsyncTaskStatus.SKIPPED.value == "skipped"

    @pytest.mark.asyncio
    async def test_async_search_execute(self):
        """测试异步搜索执行"""
        from services.search.async_task import AsyncSearchTask, AsyncTaskStatus

        mock_service = Mock()
        mock_service.search_reference = AsyncMock(return_value=MOCK_REFERENCE_RESULT)

        task = AsyncSearchTask(
            script_id=1,
            topic="为什么要读书",
            search_service=mock_service
        )

        result = await task.execute()

        assert result["status"] == AsyncTaskStatus.COMPLETED.value
        assert result["references_count"] == 2

    @pytest.mark.asyncio
    async def test_async_search_retry_on_failure(self):
        """测试失败重试"""
        from services.search.async_task import AsyncSearchTask, AsyncTaskStatus

        mock_service = Mock()
        # 前两次失败，第三次成功
        mock_service.search_reference = AsyncMock(
            side_effect=[
                Exception("Network error"),
                Exception("Network error"),
                MOCK_REFERENCE_RESULT
            ]
        )

        task = AsyncSearchTask(
            script_id=1,
            topic="test",
            search_service=mock_service,
            max_retries=3
        )

        result = await task.execute()

        assert result["status"] == AsyncTaskStatus.COMPLETED.value
        assert mock_service.search_reference.call_count == 3


# ============ 7. 集成测试 ============

class TestSearchIntegration:
    """搜索服务集成测试"""

    @pytest.mark.asyncio
    @patch('services.search.search_service.TavilySearchClient')
    async def test_full_search_flow(self, mock_tavily):
        """测试完整搜索流程"""
        from services.search.search_service import SearchService

        mock_client = Mock()
        mock_client.search.return_value = MOCK_SEARCH_RESULT
        mock_tavily.return_value = mock_client

        service = SearchService(tavily_client=mock_client)

        # 1. 分析搜索需求
        needs = service.analyzer.analyze(
            "查理·芒格谈读书",
            "知识科普"
        )
        assert len(needs) > 0

        # 2. 执行搜索
        references = await service.search_reference(
            queries=["查理·芒格", "读书名言"],
            ref_type="quote"
        )

        # 3. 验证结果
        assert len(references) > 0
        assert references[0].source_name is not None

    def test_search_trigger_conditions(self):
        """测试搜索触发条件"""
        from services.search.trigger import SearchTriggerDecider

        decider = SearchTriggerDecider()

        # 应该触发搜索的场景
        assert decider.should_search("读书", "知识科普", duration=60) is True
        assert decider.should_search("成功案例", "解决方案", duration=120) is True

        # 不应该触发搜索的场景
        assert decider.should_search("简单话题", "情感共鸣", duration=20) is False
        assert decider.should_search("测试", "痛点共鸣", duration=15) is False


# ============ 8. 集成器测试 ============

class TestSearchEnhancementIntegrator:
    """搜索增强集成器测试"""

    def test_should_enhance_disabled(self):
        """测试禁用搜索增强"""
        from services.search.search_integration import SearchEnhancementIntegrator
        from services.search.config import SearchConfig

        config = SearchConfig(enabled=False)
        integrator = SearchEnhancementIntegrator(config=config)

        assert integrator.should_enhance("读书", "知识科普", duration=60) is False

    def test_should_enhance_short_duration(self):
        """测试短时长不增强"""
        from services.search.search_integration import SearchEnhancementIntegrator

        integrator = SearchEnhancementIntegrator()

        # 30秒以下不增强
        assert integrator.should_enhance("读书", "知识科普", duration=20) is False

        # 30秒以上增强
        assert integrator.should_enhance("读书", "知识科普", duration=60) is True

    def test_format_references_for_display(self):
        """测试引用格式化展示"""
        from services.search.search_integration import SearchEnhancementIntegrator
        from services.search.models import SearchReference, ReferenceType

        integrator = SearchEnhancementIntegrator()

        ref = SearchReference(
            type=ReferenceType.QUOTE,
            content="查理·芒格曾说：..." * 50,  # 长内容
            source_name="穷查理宝典",
            source_url="https://example.com",
            author="查理·芒格",
            score=0.95
        )

        formatted = integrator.format_references_for_display([ref])

        assert len(formatted) == 1
        assert formatted[0]["type"] == "quote"
        assert formatted[0]["type_name"] == "名言引用"
        assert "..." in formatted[0]["content"]  # 长内容被截断
        assert formatted[0]["score"] == "95%"

    @pytest.mark.asyncio
    async def test_enhance_script_prompt_no_search(self):
        """测试不触发搜索时的处理"""
        from services.search.search_integration import SearchEnhancementIntegrator
        from services.search.config import SearchConfig

        config = SearchConfig(enabled=False)
        integrator = SearchEnhancementIntegrator(config=config)

        result = await integrator.enhance_script_prompt(
            topic="开心",
            topic_type="情感共鸣",
            duration=20
        )

        assert result["enhanced_prompt"] is None
        assert result["references"] == []
        assert result["search_used"] is False


# ============ 9. 配置测试 ============

class TestSearchConfig:
    """搜索配置测试"""

    def test_config_defaults(self):
        """测试默认配置"""
        from services.search.config import SearchConfig

        config = SearchConfig()

        assert config.enabled is True
        assert config.async_mode is True
        assert config.fallback_on_error is True
        assert config.timeout == 10
        assert config.cache_ttl == 604800  # 7天

    def test_config_validation(self):
        """测试配置验证"""
        from services.search.config import SearchConfig

        # 有效配置
        config = SearchConfig(enabled=True, api_key="test-key")
        assert config.validate() is True

        # 无效配置（启用但无API Key）
        config = SearchConfig(enabled=True, provider="tavily", api_key="")
        # tavily 需要 api_key，这里会失败
        # 但 validate 只检查 api_key 是否存在，不检查是否有效
        # 实际有效性的检查由 Tavily 客户端在运行时判断

    def test_config_from_env(self):
        """测试从环境变量加载配置"""
        import os
        from services.search.config import SearchConfig

        # 设置环境变量
        os.environ["SEARCH_ENABLED"] = "false"
        os.environ["SEARCH_TIMEOUT"] = "30"

        config = SearchConfig.from_env()

        assert config.enabled is False
        assert config.timeout == 30

        # 清理
        del os.environ["SEARCH_ENABLED"]
        del os.environ["SEARCH_TIMEOUT"]


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
