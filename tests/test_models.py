"""测试数据模型"""

import pytest

import pandas as pd

from financial_sdk.models import (
    FinancialBundle,
    HealthStatus,
    ValidationResult,
)


class TestValidationResult:
    """测试ValidationResult"""

    def test_valid_result(self):
        """测试有效结果"""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert bool(result) is True

    def test_invalid_result(self):
        """测试无效结果"""
        result = ValidationResult(is_valid=True)
        result.add_error("缺少必需字段")
        assert result.is_valid is False
        assert "缺少必需字段" in result.errors

    def test_add_warning(self):
        """测试添加警告"""
        result = ValidationResult(is_valid=True)
        result.add_warning("数据可能不完整")
        assert "数据可能不完整" in result.warnings


class TestHealthStatus:
    """测试HealthStatus"""

    def test_create_healthy_status(self):
        """测试创建健康状态"""
        status = HealthStatus(status="healthy")
        assert status.status == "healthy"
        assert status.is_healthy() is True
        assert status.timestamp != ""

    def test_get_failed_adapters(self):
        """测试获取失败的适配器"""
        status = HealthStatus(
            status="degraded",
            adapters={
                "akshare": {"status": "healthy"},
                "akshare_us": {"status": "unhealthy"},
            },
        )
        failed = status.get_failed_adapters()
        assert "akshare_us" in failed
        assert "akshare" not in failed

    def test_to_dict(self):
        """测试转换为字典"""
        status = HealthStatus(status="healthy")
        d = status.to_dict()
        assert d["status"] == "healthy"
        assert "timestamp" in d


class TestFinancialBundle:
    """测试FinancialBundle"""

    def test_create_bundle(self):
        """测试创建bundle"""
        bundle = FinancialBundle(
            stock_code="600000.SH",
            stock_name="浦发银行",
            market="A",
            currency="CNY",
        )
        assert bundle.stock_code == "600000.SH"
        assert bundle.stock_name == "浦发银行"
        assert bundle.market == "A"
        assert bundle.currency == "CNY"
        assert bundle.is_partial is False
        assert len(bundle.warnings) == 0

    def test_get_report(self):
        """测试获取报表"""
        bundle = FinancialBundle(stock_code="600000.SH")
        df = pd.DataFrame({"report_date": ["2024-01-01"], "total_assets": [100]})
        bundle.balance_sheet = df

        result = bundle.get_report("balance_sheet")
        assert result is df
        assert not result.empty

    def test_get_report_alias(self):
        """测试获取报表的别名"""
        bundle = FinancialBundle(stock_code="600000.SH")
        df = pd.DataFrame({"report_date": ["2024-01-01"], "total_assets": [100]})
        bundle.balance_sheet = df

        # 测试别名
        result = bundle.get_report("balance")
        assert result is df

    def test_get_report_invalid(self):
        """测试获取无效报表"""
        bundle = FinancialBundle(stock_code="600000.SH")
        with pytest.raises(ValueError, match="Invalid report_type"):
            bundle.get_report("invalid_type")

    def test_get_available_reports(self):
        """测试获取可用报表"""
        bundle = FinancialBundle(stock_code="600000.SH")
        bundle.balance_sheet = pd.DataFrame()
        bundle.income_statement = pd.DataFrame()
        bundle.cash_flow = None
        bundle.indicators = None

        reports = bundle.get_available_reports()
        assert "balance_sheet" in reports
        assert "income_statement" in reports
        assert "cash_flow" not in reports
        assert "indicators" not in reports

    def test_add_warning(self):
        """测试添加警告"""
        bundle = FinancialBundle(stock_code="600000.SH")
        bundle.add_warning("测试警告")
        assert bundle.is_partial is True
        assert "测试警告" in bundle.warnings

    def test_validate(self):
        """测试数据验证"""
        bundle = FinancialBundle(stock_code="600000.SH")
        bundle.balance_sheet = pd.DataFrame(
            {
                "report_date": ["2024-01-01"],
                "total_assets": [100],
                "total_liabilities": [50],
                "total_equity": [50],
            }
        )

        result = bundle.validate()
        assert result.is_valid is True

    def test_validate_missing_required_fields(self):
        """测试验证缺少必需字段"""
        bundle = FinancialBundle(stock_code="600000.SH")
        bundle.balance_sheet = pd.DataFrame(
            {
                "report_date": ["2024-01-01"],
                "total_assets": [100],
                # 缺少 total_liabilities 和 total_equity
            }
        )

        result = bundle.validate()
        assert len(result.warnings) > 0

    def test_to_dict(self):
        """测试转换为字典"""
        bundle = FinancialBundle(stock_code="600000.SH", market="A")
        d = bundle.to_dict()
        assert d["stock_code"] == "600000.SH"
        assert d["market"] == "A"
        assert "available_reports" in d

    def test_repr(self):
        """测试字符串表示"""
        bundle = FinancialBundle(stock_code="600000.SH", market="A")
        r = repr(bundle)
        assert "600000.SH" in r
        assert "A" in r
