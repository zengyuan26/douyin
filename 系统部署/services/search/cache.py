"""
搜索结果缓存

使用内存缓存 + Redis 双层缓存
"""

import json
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchCache:
    """
    搜索缓存

    支持：
    - 内存缓存（默认）
    - Redis 缓存（可选）
    """

    def __init__(self, redis_client=None, ttl: int = 604800):
        """
        初始化缓存

        Args:
            redis_client: Redis 客户端实例（可选）
            ttl: 默认缓存有效期（秒），默认7天
        """
        self.redis = redis_client
        self.ttl = ttl
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

        if self.redis:
            logger.info("搜索缓存已启用 Redis")
        else:
            logger.info("搜索缓存使用内存存储")

    def _get_cache_key(self, query: str, ref_type: str) -> str:
        """
        生成缓存键

        Args:
            query: 搜索词
            ref_type: 引用类型

        Returns:
            缓存键
        """
        # 标准化查询
        normalized = query.strip().lower()
        key_input = f"{ref_type}:{normalized}"

        # MD5 哈希（保持键长度可控）
        key_hash = hashlib.md5(key_input.encode()).hexdigest()

        return f"search:{key_hash}"

    async def get(self, query: str, ref_type: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存

        Args:
            query: 搜索词
            ref_type: 引用类型

        Returns:
            缓存数据或 None
        """
        key = self._get_cache_key(query, ref_type)

        # 1. 尝试 Redis
        if self.redis:
            try:
                cached = self.redis.get(key)
                if cached:
                    data = json.loads(cached)
                    logger.debug(f"Redis缓存命中: {key}")
                    return data
            except Exception as e:
                logger.warning(f"Redis获取失败: {e}")

        # 2. 尝试内存缓存
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            # 检查是否过期
            if datetime.now().timestamp() < entry.get("expires_at", 0):
                logger.debug(f"内存缓存命中: {key}")
                return entry["data"]
            else:
                # 已过期，删除
                del self._memory_cache[key]

        return None

    async def set(
        self,
        query: str,
        ref_type: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        设置缓存

        Args:
            query: 搜索词
            ref_type: 引用类型
            data: 缓存数据
            ttl: 缓存有效期（秒）

        Returns:
            是否成功
        """
        key = self._get_cache_key(query, ref_type)
        ttl = ttl or self.ttl

        # 1. 保存到 Redis
        if self.redis:
            try:
                self.redis.setex(
                    key,
                    ttl,
                    json.dumps(data, ensure_ascii=False)
                )
                logger.debug(f"Redis缓存设置成功: {key}")
            except Exception as e:
                logger.warning(f"Redis设置失败: {e}")

        # 2. 保存到内存缓存
        expires_at = datetime.now().timestamp() + ttl
        self._memory_cache[key] = {
            "data": data,
            "expires_at": expires_at,
            "created_at": datetime.now().isoformat(),
        }

        return True

    async def delete(self, query: str, ref_type: str) -> bool:
        """
        删除缓存

        Args:
            query: 搜索词
            ref_type: 引用类型

        Returns:
            是否成功
        """
        key = self._get_cache_key(query, ref_type)

        # 1. 删除 Redis
        if self.redis:
            try:
                self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis删除失败: {e}")

        # 2. 删除内存缓存
        if key in self._memory_cache:
            del self._memory_cache[key]

        return True

    async def clear(self) -> int:
        """
        清空所有缓存

        Returns:
            清空的缓存数量
        """
        count = 0

        # 清空内存缓存
        count = len(self._memory_cache)
        self._memory_cache.clear()

        # 清空 Redis（谨慎使用）
        if self.redis:
            try:
                pattern = "search:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
                    count += len(keys)
            except Exception as e:
                logger.warning(f"Redis清空失败: {e}")

        logger.info(f"缓存已清空: {count}条")

        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计

        Returns:
            缓存统计信息
        """
        # 计算内存缓存
        now = datetime.now().timestamp()
        valid_count = sum(
            1 for entry in self._memory_cache.values()
            if entry.get("expires_at", 0) > now
        )

        return {
            "memory_cache_total": len(self._memory_cache),
            "memory_cache_valid": valid_count,
            "redis_enabled": self.redis is not None,
        }
