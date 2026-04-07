"""
公开内容生成平台 - 缓存服务（性能优化）

策略：
1. 热数据内存缓存：行业、目标客户、模板配置
2. LRU缓存：最近使用的关键词、选题
3. 缓存预热：启动时加载热点数据
4. 自动过期：避免数据不一致
"""

import time
import threading
import logging
from functools import wraps
from typing import Any, Optional, Callable
from collections import OrderedDict

logger = logging.getLogger(__name__)


class LRUCache:
    """线程安全的 LRU 缓存"""

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self.maxsize = maxsize
        self.ttl = ttl  # 秒
        self._cache = OrderedDict()
        self._timestamps = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        with self._lock:
            if key not in self._cache:
                return None

            # 检查过期
            if time.time() - self._timestamps.get(key, 0) > self.ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None

            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """设置缓存"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                self._cache[key] = value
                # 超过容量，删除最旧的
                if len(self._cache) > self.maxsize:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._timestamps[oldest]

            self._timestamps[key] = time.time()

    def delete(self, key: str) -> None:
        """删除缓存"""
        with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        """获取缓存，不存在则调用工厂函数创建"""
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value)
        return value


class PublicCache:
    """
    公开平台缓存管理器

    分层缓存策略：
    - L1: 内存LRU缓存（毫秒级访问）
    - L2: 可扩展为Redis（分布式部署时）
    """

    # 类级别的缓存实例
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # 缓存配置
        self._cache_config = {
            'industries': {'maxsize': 100, 'ttl': 86400},      # 行业列表（24小时）
            'customers': {'maxsize': 200, 'ttl': 86400},       # 目标客户（24小时）
            'templates': {'maxsize': 500, 'ttl': 86400},       # 内容模板（24小时）
            'keywords': {'maxsize': 2000, 'ttl': 3600},        # 关键词（1小时）
            'topics': {'maxsize': 1000, 'ttl': 3600},           # 选题（1小时）
            'titles': {'maxsize': 500, 'ttl': 3600},            # 标题（1小时）
            'tags': {'maxsize': 500, 'ttl': 3600},             # 标签（1小时）
        }

        # 创建缓存实例
        self._caches = {}
        for name, config in self._cache_config.items():
            self._caches[name] = LRUCache(
                maxsize=config['maxsize'],
                ttl=config['ttl']
            )

        # 用户配额缓存（短期）
        self._quota_cache = LRUCache(maxsize=1000, ttl=60)  # 1分钟

        # 缓存预热状态
        self._warmed = False

    def get_cache(self, name: str) -> LRUCache:
        """获取指定名称的缓存"""
        return self._caches.get(name)

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """通用获取方法"""
        cache = self._caches.get(cache_name)
        if cache:
            return cache.get(key)
        return None

    def set(self, cache_name: str, key: str, value: Any) -> None:
        """通用设置方法"""
        cache = self._caches.get(cache_name)
        if cache:
            cache.set(key, value)

    def delete(self, cache_name: str, key: str) -> None:
        """通用删除方法"""
        cache = self._caches.get(cache_name)
        if cache:
            cache.delete(key)

    def invalidate_all(self, cache_name: str) -> None:
        """清空指定缓存"""
        cache = self._caches.get(cache_name)
        if cache:
            cache.clear()

    def invalidate_user_quota(self, user_id: int) -> None:
        """清除用户配额缓存"""
        self._quota_cache.delete(f'quota_{user_id}')

    # =========================================================================
    # 便捷方法
    # =========================================================================

    def get_industries(self) -> Optional[Any]:
        """获取行业列表"""
        return self.get('industries', 'all')

    def set_industries(self, data: Any) -> None:
        """设置行业列表"""
        self.set('industries', 'all', data)

    def get_customers(self, industry: str) -> Optional[Any]:
        """获取目标客户列表"""
        return self.get('customers', industry)

    def set_customers(self, industry: str, data: Any) -> None:
        """设置目标客户列表"""
        self.set('customers', industry, data)

    def get_templates(self, key: str) -> Optional[Any]:
        """获取内容模板"""
        return self.get('templates', key)

    def set_templates(self, key: str, data: Any) -> None:
        """设置内容模板"""
        self.set('templates', key, data)

    def get_keywords(self, industry: str, customer_type: str) -> Optional[Any]:
        """获取关键词"""
        return self.get('keywords', f'{industry}:{customer_type}')

    def set_keywords(self, industry: str, customer_type: str, data: Any) -> None:
        """设置关键词"""
        self.set('keywords', f'{industry}:{customer_type}', data)

    def get_topics(self, industry: str, customer_type: str) -> Optional[Any]:
        """获取选题"""
        return self.get('topics', f'{industry}:{customer_type}')

    def set_topics(self, industry: str, customer_type: str, data: Any) -> None:
        """设置选题"""
        self.set('topics', f'{industry}:{customer_type}', data)

    # =========================================================================
    # 缓存预热
    # =========================================================================

    def warm_up(self, app=None) -> None:
        """
        缓存预热 - 启动时加载热点数据

        Args:
            app: Flask应用实例（用于获取数据库连接）
        """
        if self._warmed:
            return

        with self._lock:
            if self._warmed:
                return

            def _do_warmup():
                try:
                    from models.public_models import (
                        PublicTargetCustomer,
                        PublicContentTemplate
                    )

                    # 预热目标客户
                    customers_query = PublicTargetCustomer.query.filter_by(
                        is_active=True
                    ).order_by(PublicTargetCustomer.priority.desc()).all()

                    # 按行业分组缓存
                    customer_groups = {}
                    for c in customers_query:
                        if c.applicable_industries:
                            for ind in c.applicable_industries:
                                if ind not in customer_groups:
                                    customer_groups[ind] = []
                                customer_groups[ind].append({
                                    'customer_type': c.customer_type,
                                    'customer_name': c.customer_name,
                                    'description': c.description,
                                    'icon': c.icon,
                                })

                    for ind, customers in customer_groups.items():
                        self.set_customers(ind, customers)

                    # 预热内容模板
                    templates_query = PublicContentTemplate.query.filter_by(
                        is_active=True
                    ).order_by(PublicContentTemplate.priority.desc()).limit(100).all()

                    self.set_templates('all_active', [
                        {'code': t.template_code, 'name': t.template_name}
                        for t in templates_query
                    ])

                    self._warmed = True
                    logger.info("[Cache] 缓存预热完成：%s 个行业，%s 个模板", len(customer_groups), len(templates_query))

                except Exception as e:
                    logger.error("[Cache] 缓存预热失败: %s", e)

            # 如果传入了 app，在其应用上下文中执行；否则假设已处于上下文中
            if app is not None:
                with app.app_context():
                    _do_warmup()
            else:
                _do_warmup()

    def refresh_cache(self, cache_name: str) -> None:
        """手动刷新指定缓存"""
        self.invalidate_all(cache_name)
        # 可在这里添加从数据库重新加载的逻辑


# 全局缓存实例
public_cache = PublicCache()


# =============================================================================
# 装饰器：缓存方法结果
# =============================================================================

def cached(cache_name: str, key_func: Callable = None, ttl: int = None):
    """
    缓存装饰器

    Args:
        cache_name: 缓存名称
        key_func: 缓存键生成函数，默认用所有参数
        ttl: 缓存时间（秒），None使用默认

    Usage:
        @cached('keywords')
        def get_keywords(industry, customer_type):
            return db.query(...)

        @cached('data', key_func=lambda x, y: f'{x}:{y}')
        def get_data(a, b):
            return db.query(...)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = public_cache.get_cache(cache_name)
            if cache is None:
                return func(*args, **kwargs)

            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = str(args) + str(kwargs)

            # 尝试获取缓存
            result = cache.get(cache_key)
            if result is not None:
                return result

            # 调用函数并缓存结果
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return wrapper
    return decorator


# =============================================================================
# 工具函数
# =============================================================================

def clear_all_caches():
    """清除所有缓存"""
    global public_cache
    for name in public_cache._caches:
        public_cache.invalidate_all(name)


def get_cache_stats() -> dict:
    """获取缓存统计"""
    stats = {}
    for name, cache in public_cache._caches.items():
        stats[name] = {
            'size': len(cache._cache),
            'maxsize': cache.maxsize,
            'ttl': cache.ttl,
        }
    return stats
