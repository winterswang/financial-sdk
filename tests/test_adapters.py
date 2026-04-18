"""测试适配器"""

import pytest

from financial_sdk.adapters import ASHareAdapter, HKAdapter, USAdapter
from financial_sdk.exceptions import InvalidStockCodeError


class TestASHareAdapter:
    """测试ASHareAdapter"""

    def test_adapter_name(self):
        """测试适配器名称"""
        adapter = ASHareAdapter()
        assert adapter.adapter_name == "akshare"

    def test_supported_markets(self):
        """测试支持的市场"""
        adapter = ASHareAdapter()
        assert "A" in adapter.supported_markets

    def test_validate_valid_code(self):
        """测试验证有效代码"""
        adapter = ASHareAdapter()
        assert adapter.validate_stock_code("600000.SH") is True
        assert adapter.validate_stock_code("000001.SZ") is True

    def test_validate_invalid_code(self):
        """测试验证无效代码"""
        adapter = ASHareAdapter()
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("INVALID")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("600000.HK")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("AAPL")


class TestHKAdapter:
    """测试HKAdapter"""

    def test_adapter_name(self):
        """测试适配器名称"""
        adapter = HKAdapter()
        assert adapter.adapter_name == "akshare_hk"

    def test_supported_markets(self):
        """测试支持的市场"""
        adapter = HKAdapter()
        assert "HK" in adapter.supported_markets

    def test_validate_valid_code(self):
        """测试验证有效代码"""
        adapter = HKAdapter()
        assert adapter.validate_stock_code("0700.HK") is True
        assert adapter.validate_stock_code("9988.HK") is True

    def test_validate_invalid_code(self):
        """测试验证无效代码"""
        adapter = HKAdapter()
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("INVALID")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("0700.SZ")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("AAPL")


class TestUSAdapter:
    """测试USAdapter"""

    def test_adapter_name(self):
        """测试适配器名称"""
        adapter = USAdapter()
        assert adapter.adapter_name == "akshare_us"

    def test_supported_markets(self):
        """测试支持的市场"""
        adapter = USAdapter()
        assert "US" in adapter.supported_markets

    def test_validate_valid_code(self):
        """测试验证有效代码"""
        adapter = USAdapter()
        assert adapter.validate_stock_code("AAPL") is True
        assert adapter.validate_stock_code("MSFT") is True
        assert adapter.validate_stock_code("GOOGL") is True

    def test_validate_invalid_code(self):
        """测试验证无效代码"""
        adapter = USAdapter()
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("INVALID")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("600000.SH")
        with pytest.raises(InvalidStockCodeError):
            adapter.validate_stock_code("0700.HK")


class TestBaseAdapter:
    """测试BaseAdapter接口"""

    def test_adapter_repr(self):
        """测试适配器字符串表示"""
        adapter = ASHareAdapter()
        r = repr(adapter)
        assert "ASHareAdapter" in r
        assert "akshare" in r
