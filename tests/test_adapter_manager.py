"""测试适配器管理器"""

import pytest

from financial_sdk.adapter_manager import AdapterManager, get_adapter_manager
from financial_sdk.exceptions import InvalidStockCodeError


class TestAdapterManager:
    """测试AdapterManager"""

    def test_create_manager(self):
        """测试创建管理器"""
        manager = AdapterManager()
        adapters = manager.get_all_adapters()
        assert len(adapters) >= 3  # 默认注册了3个适配器

    def test_get_market_a_stock(self):
        """测试识别A股"""
        manager = AdapterManager()
        assert manager.get_market_for_stock("600000.SH") == "A"
        assert manager.get_market_for_stock("000001.SZ") == "A"

    def test_get_market_hk(self):
        """测试识别港股"""
        manager = AdapterManager()
        assert manager.get_market_for_stock("0700.HK") == "HK"
        assert manager.get_market_for_stock("9988.HK") == "HK"

    def test_get_market_us(self):
        """测试识别美股"""
        manager = AdapterManager()
        assert manager.get_market_for_stock("AAPL") == "US"
        assert manager.get_market_for_stock("MSFT") == "US"

    def test_get_market_invalid(self):
        """测试无效代码"""
        manager = AdapterManager()
        with pytest.raises(InvalidStockCodeError):
            manager.get_market_for_stock("INVALID")

    def test_select_adapter_a(self):
        """测试选择A股适配器"""
        manager = AdapterManager()
        adapter = manager.select_adapter("600000.SH")
        assert adapter.adapter_name == "akshare"

    def test_select_adapter_hk(self):
        """测试选择港股适配器"""
        manager = AdapterManager()
        adapter = manager.select_adapter("0700.HK")
        assert adapter.adapter_name == "akshare_hk"

    def test_select_adapter_us(self):
        """测试选择美股适配器"""
        manager = AdapterManager()
        adapter = manager.select_adapter("AAPL")
        assert adapter.adapter_name == "akshare_us"

    def test_get_adapters_by_market(self):
        """测试按市场获取适配器"""
        manager = AdapterManager()
        adapters = manager.get_adapters_by_market("A")
        assert len(adapters) >= 1
        assert all("A" in a.supported_markets for a in adapters)

    def test_get_adapter_health(self):
        """测试获取适配器健康状态"""
        manager = AdapterManager()
        health = manager.get_adapter_health()
        assert "akshare" in health
        assert "akshare_hk" in health
        assert "akshare_us" in health


class TestGlobalAdapterManager:
    """测试全局适配器管理器"""

    def test_get_manager(self):
        """测试获取全局管理器"""
        manager = get_adapter_manager()
        assert manager is not None
        assert isinstance(manager, AdapterManager)
