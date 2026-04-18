"""测试异常类"""

from financial_sdk.exceptions import (
    FinancialSDKError,
    DataNotAvailableError,
    NoAdapterAvailableError,
    DataFormatError,
    InvalidStockCodeError,
    CacheError,
    NetworkError,
)


class TestFinancialSDKError:
    """测试FinancialSDKError基类"""

    def test_create_error(self):
        """测试创建错误"""
        error = FinancialSDKError("test error", {"key": "value"})
        assert error.message == "test error"
        assert error.details == {"key": "value"}
        assert str(error) == "test error"

    def test_to_dict(self):
        """测试转换为字典"""
        error = FinancialSDKError("test error", {"key": "value"})
        d = error.to_dict()
        assert d["error_type"] == "FinancialSDKError"
        assert d["message"] == "test error"
        assert d["details"] == {"key": "value"}


class TestDataNotAvailableError:
    """测试DataNotAvailableError"""

    def test_create_error(self):
        """测试创建错误"""
        error = DataNotAvailableError(
            stock_code="600000.SH",
            report_type="balance_sheet",
            reason="网络超时",
            adapter_name="akshare",
        )
        assert error.stock_code == "600000.SH"
        assert error.report_type == "balance_sheet"
        assert error.reason == "网络超时"
        assert error.adapter_name == "akshare"
        assert "数据不可用" in error.message
        assert "600000.SH" in error.message


class TestNoAdapterAvailableError:
    """测试NoAdapterAvailableError"""

    def test_create_error(self):
        """测试创建错误"""
        error = NoAdapterAvailableError(
            stock_code="AAPL",
            attempted_adapters=["akshare_us", "akshare"],
            last_error="连接超时",
            fallback_history=[
                {"adapter": "akshare_us", "status": "failed", "error": "timeout"},
                {"adapter": "akshare", "status": "failed", "error": "not available"},
            ],
        )
        assert error.stock_code == "AAPL"
        assert error.attempted_adapters == ["akshare_us", "akshare"]
        assert error.last_error == "连接超时"
        assert len(error.fallback_history) == 2


class TestDataFormatError:
    """测试DataFormatError"""

    def test_create_error(self):
        """测试创建错误"""
        error = DataFormatError(
            field_name="report_date",
            expected_format="YYYY-MM-DD",
            actual_value="2024/01/01",
            stock_code="600000.SH",
        )
        assert error.field_name == "report_date"
        assert error.expected_format == "YYYY-MM-DD"
        assert error.actual_value == "2024/01/01"
        assert error.stock_code == "600000.SH"


class TestInvalidStockCodeError:
    """测试InvalidStockCodeError"""

    def test_create_error(self):
        """测试创建错误"""
        error = InvalidStockCodeError(
            stock_code="INVALID",
            expected_format="6位数字.SH或.SZ",
            market="A",
        )
        assert error.stock_code == "INVALID"
        assert error.expected_format == "6位数字.SH或.SZ"
        assert error.market == "A"


class TestCacheError:
    """测试CacheError"""

    def test_create_error(self):
        """测试创建错误"""
        error = CacheError(
            operation="get",
            key="A_600000.SH_balance_sheet_annual",
            reason="key not found",
        )
        assert error.operation == "get"
        assert error.key == "A_600000.SH_balance_sheet_annual"
        assert error.reason == "key not found"


class TestNetworkError:
    """测试NetworkError"""

    def test_create_error(self):
        """测试创建错误"""
        error = NetworkError(
            message="连接超时",
            url="https://api.example.com",
            timeout=30,
            status_code=408,
            retry_count=3,
        )
        assert error.url == "https://api.example.com"
        assert error.timeout == 30
        assert error.status_code == 408
        assert error.retry_count == 3
