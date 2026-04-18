"""
缓存模块

提供LRU缓存实现，支持TTL过期策略。
缓存键格式: {market}_{stock_code}_{report_type}_{period}
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from cachetools import LRUCache


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: datetime = None

    def __post_init__(self) -> None:
        if self.last_accessed is None:
            self.last_accessed = self.created_at

    @property
    def is_expired(self) -> bool:
        """检查是否已过期"""
        age = datetime.now() - self.created_at
        return age.total_seconds() > self.ttl_seconds

    def touch(self) -> None:
        """更新访问时间"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class CacheStats:
    """缓存统计信息"""

    def __init__(self) -> None:
        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size": 0,  # 动态更新
            "max_size": 0,  # 动态更新
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "evictions": self.evictions,
        }


class FinancialCache:
    """
    财务数据缓存

    特性:
    - LRU淘汰策略
    - TTL过期支持
    - 静态数据24小时TTL，动态数据1小时TTL
    - 缓存键格式: {market}_{stock_code}_{report_type}_{period}
    """

    # TTL常量（秒）
    TTL_STATIC = 24 * 60 * 60  # 24小时
    TTL_DYNAMIC = 60 * 60  # 1小时

    # 默认缓存大小
    DEFAULT_MAX_SIZE = 1000

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self._cache: LRUCache[str, CacheEntry] = LRUCache(maxsize=max_size)
        self._max_size = max_size
        self._stats = CacheStats()

    @staticmethod
    def make_cache_key(
        market: str, stock_code: str, report_type: str, period: str
    ) -> str:
        """
        生成缓存键

        Args:
            market: 市场标识 (A, HK, US)
            stock_code: 股票代码
            report_type: 报表类型 (balance_sheet, income_statement, cash_flow, indicators, all)
            period: 报告期类型 (annual, quarterly)

        Returns:
            str: 缓存键，格式: {market}_{stock_code}_{report_type}_{period}
        """
        return f"{market}_{stock_code}_{report_type}_{period}"

    def get(self, key: str) -> Tuple[bool, Optional[Any]]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            Tuple[bool, Optional[Any]]: (是否命中, 缓存值)
        """
        entry = self._cache.get(key)
        if entry is None:
            self._stats.misses += 1
            return False, None

        if entry.is_expired:
            del self._cache[key]
            self._stats.misses += 1
            return False, None

        entry.touch()
        self._stats.hits += 1
        return True, entry.value

    def set(self, key: str, value: Any, ttl: int = TTL_STATIC) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认24小时
        """
        # 如果缓存已满，触发LRU淘汰
        if len(self._cache) >= self._max_size and key not in self._cache:
            # 移除最旧的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats.evictions += 1

        entry = CacheEntry(value=value, created_at=datetime.now(), ttl_seconds=ttl)
        self._cache[key] = entry

    def delete(self, key: str) -> bool:
        """
        删除缓存值

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """清除所有缓存"""
        self._cache.clear()

    def invalidate_pattern(self, pattern: str) -> int:
        """
        使匹配模式的缓存失效

        Args:
            pattern: 匹配模式（如 "A_*" 匹配所有A股缓存）

        Returns:
            int: 删除的缓存数量
        """
        # 将通配符模式转为检查逻辑
        prefix = pattern.replace("*", "")

        keys_to_delete = [
            k for k in self._cache.keys() if k.startswith(prefix.rstrip("_"))
        ]

        for key in keys_to_delete:
            del self._cache[key]

        return len(keys_to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict: 统计信息
        """
        stats_dict = self._stats.to_dict()
        stats_dict["size"] = len(self._cache)
        stats_dict["max_size"] = self._max_size
        return stats_dict

    def get_all_keys(self) -> List[str]:
        """获取所有缓存键"""
        return list(self._cache.keys())

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache and not self._cache[key].is_expired


# 全局缓存实例
_global_cache: Optional[FinancialCache] = None


def get_cache() -> FinancialCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = FinancialCache()
    return _global_cache


def set_cache(cache: FinancialCache) -> None:
    """设置全局缓存实例"""
    global _global_cache
    _global_cache = cache


def clear_cache() -> None:
    """清除全局缓存"""
    if _global_cache is not None:
        _global_cache.clear()


def clear_cache_pattern(pattern: str) -> int:
    """清除匹配模式的全局缓存"""
    if _global_cache is not None:
        return _global_cache.invalidate_pattern(pattern)
    return 0
