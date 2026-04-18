"""测试缓存模块"""

from datetime import datetime, timedelta

from financial_sdk.cache import (
    CacheEntry,
    CacheStats,
    FinancialCache,
    get_cache,
    clear_cache,
)


class TestCacheEntry:
    """测试CacheEntry"""

    def test_create_entry(self):
        """测试创建缓存条目"""
        entry = CacheEntry(
            value={"data": "test"}, created_at=datetime.now(), ttl_seconds=3600
        )
        assert entry.value == {"data": "test"}
        assert entry.access_count == 0

    def test_is_expired(self):
        """测试过期检查"""
        entry = CacheEntry(
            value="test",
            created_at=datetime.now() - timedelta(hours=2),
            ttl_seconds=3600,
        )
        assert entry.is_expired is True

        entry2 = CacheEntry(value="test", created_at=datetime.now(), ttl_seconds=3600)
        assert entry2.is_expired is False

    def test_touch(self):
        """测试更新访问"""
        entry = CacheEntry(value="test", created_at=datetime.now(), ttl_seconds=3600)
        entry.touch()
        assert entry.access_count == 1


class TestCacheStats:
    """测试CacheStats"""

    def test_create_stats(self):
        """测试创建统计"""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total_requests == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate(self):
        """测试命中率"""
        stats = CacheStats()
        stats.hits = 80
        stats.misses = 20
        assert stats.hit_rate == 0.8

    def test_to_dict(self):
        """测试转换为字典"""
        stats = CacheStats()
        d = stats.to_dict()
        assert "hits" in d
        assert "misses" in d
        assert "hit_rate" in d


class TestFinancialCache:
    """测试FinancialCache"""

    def test_make_cache_key(self):
        """测试生成缓存键"""
        key = FinancialCache.make_cache_key("A", "600000.SH", "balance_sheet", "annual")
        assert key == "A_600000.SH_balance_sheet_annual"

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = FinancialCache(max_size=100)
        cache.set("test_key", {"data": "value"})
        hit, value = cache.get("test_key")
        assert hit is True
        assert value == {"data": "value"}

    def test_get_miss(self):
        """测试缓存未命中"""
        cache = FinancialCache()
        hit, value = cache.get("nonexistent")
        assert hit is False
        assert value is None

    def test_delete(self):
        """测试删除"""
        cache = FinancialCache()
        cache.set("test_key", "value")
        assert cache.delete("test_key") is True
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        """测试清空"""
        cache = FinancialCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert len(cache) == 0

    def test_lru_eviction(self):
        """测试LRU淘汰"""
        cache = FinancialCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # 应该淘汰key1
        hit, _ = cache.get("key1")
        assert hit is False
        hit, value = cache.get("key3")
        assert hit is True
        assert value == "value3"

    def test_get_stats(self):
        """测试获取统计"""
        cache = FinancialCache(max_size=100)
        cache.set("key1", "value1")
        cache.get("key1")  # 命中
        cache.get("key2")  # 未命中
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_invalidate_pattern(self):
        """测试模式失效"""
        cache = FinancialCache()
        cache.set("A_600000.SH_balance_sheet_annual", "data1")
        cache.set("A_000001.SZ_balance_sheet_annual", "data2")
        cache.set("HK_0700.HK_balance_sheet_annual", "data3")
        count = cache.invalidate_pattern("A_*")
        assert count == 2
        assert len(cache) == 1

    def test_contains(self):
        """测试包含检查"""
        cache = FinancialCache()
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "key2" not in cache


class TestGlobalCache:
    """测试全局缓存"""

    def test_get_cache(self):
        """测试获取全局缓存"""
        cache = get_cache()
        assert cache is not None
        assert isinstance(cache, FinancialCache)

    def test_clear_cache(self):
        """测试清空全局缓存"""
        cache = get_cache()
        cache.set("test_key", "test_value")
        clear_cache()
        hit, _ = cache.get("test_key")
        assert hit is False
