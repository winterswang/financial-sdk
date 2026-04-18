"""测试门面"""

import pytest

from financial_sdk.facade import FinancialFacade


class TestFinancialFacade:
    """测试FinancialFacade"""

    def test_create_facade(self):
        """测试创建门面"""
        facade = FinancialFacade()
        assert facade is not None

    def test_create_facade_no_cache(self):
        """测试创建禁用缓存的门面"""
        facade = FinancialFacade(enable_cache=False)
        assert facade._enable_cache is False

    def test_get_supported_stocks_all(self):
        """测试获取所有市场的股票"""
        facade = FinancialFacade()
        stocks = facade.get_supported_stocks("all")
        assert len(stocks) > 0
        assert "600000.SH" in stocks
        assert "0700.HK" in stocks
        assert "AAPL" in stocks

    def test_get_supported_stocks_a(self):
        """测试获取A股股票"""
        facade = FinancialFacade()
        stocks = facade.get_supported_stocks("A")
        assert all(".SH" in s or ".SZ" in s for s in stocks)

    def test_get_supported_stocks_hk(self):
        """测试获取港股股票"""
        facade = FinancialFacade()
        stocks = facade.get_supported_stocks("HK")
        assert all(".HK" in s for s in stocks)

    def test_get_supported_stocks_us(self):
        """测试获取美股股票"""
        facade = FinancialFacade()
        stocks = facade.get_supported_stocks("US")
        assert all(s.isupper() for s in stocks)

    def test_health_check(self):
        """测试健康检查"""
        facade = FinancialFacade()
        health = facade.health_check()
        assert health.status in ["healthy", "degraded", "unhealthy"]
        # adapters可能为空（未发起请求时）或包含已记录的适配器
        assert isinstance(health.adapters, dict)
        assert "cache_stats" in health.to_dict()

    def test_clear_cache(self):
        """测试清除缓存"""
        facade = FinancialFacade()
        facade._cache.set("test_key", "test_value")
        facade.clear_cache()
        assert len(facade._cache) == 0

    def test_get_cache_stats(self):
        """测试获取缓存统计"""
        facade = FinancialFacade()
        stats = facade.get_cache_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "hit_rate" in stats

    def test_invalid_report_type(self):
        """测试无效的报表类型"""
        facade = FinancialFacade()
        with pytest.raises(ValueError, match="无效的report_type"):
            facade.get_financial_data("600000.SH", "invalid", "annual")

    def test_invalid_period(self):
        """测试无效的期间类型"""
        facade = FinancialFacade()
        with pytest.raises(ValueError, match="无效的period"):
            facade.get_financial_data("600000.SH", "all", "invalid")
