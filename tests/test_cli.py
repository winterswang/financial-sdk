"""
CLI 模块单元测试

测试 CLI 输出格式化函数，不依赖实际 API 调用。
"""

import pytest
from unittest.mock import MagicMock, patch

import pandas as pd

from src.financial_sdk_cli import (
    _format_number,
    _format_dataframe_for_display,
    _filter_by_year,
    _parse_year_filter,
    _report_to_markdown,
    _report_to_csv,
    _compare_to_markdown,
    _compare_to_csv,
    _compare_to_table,
)
from src.financial_sdk.analytics.unified import FullAnalysisReport
from src.financial_sdk.analytics.valuation import ValuationMetrics
from src.financial_sdk.analytics.profitability import ProfitabilityMetrics
from src.financial_sdk.analytics.efficiency import EfficiencyMetrics
from src.financial_sdk.analytics.growth import GrowthMetrics
from src.financial_sdk.analytics.safety import SafetyMetrics


class TestFormatNumber:
    """测试数字格式化"""

    def test_billions(self):
        assert _format_number(1.5e9) == "1.50B"

    def test_millions(self):
        assert _format_number(1.5e6) == "1.50M"

    def test_thousands(self):
        assert _format_number(1500) == "1.50K"

    def test_small_number(self):
        assert _format_number(1.23) == "1.23"

    def test_tiny_number(self):
        assert _format_number(0.001) == "1.00e-03"


class TestFilterByYear:
    """测试年份过滤"""

    def test_single_year(self):
        df = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "value": [100, 200],
        })
        result = _filter_by_year(df, "2024")
        assert len(result) == 1
        assert result["value"].iloc[0] == 200

    def test_multiple_years(self):
        df = pd.DataFrame({
            "report_date": ["2022-12-31", "2023-12-31", "2024-12-31"],
            "value": [100, 200, 300],
        })
        result = _filter_by_year(df, "2023,2024")
        assert len(result) == 2

    def test_year_range(self):
        df = pd.DataFrame({
            "report_date": ["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31"],
            "value": [100, 200, 300, 400],
        })
        result = _filter_by_year(df, "2022-2023")
        assert len(result) == 2

    def test_empty_df(self):
        df = pd.DataFrame()
        result = _filter_by_year(df, "2024")
        assert result.empty


class TestParseYearFilter:
    """测试年份解析"""

    def test_single_year(self):
        assert _parse_year_filter("2024") == {2024}

    def test_multiple_years(self):
        assert _parse_year_filter("2023,2024") == {2023, 2024}

    def test_year_range(self):
        assert _parse_year_filter("2022-2024") == {2022, 2023, 2024}

    def test_none(self):
        assert _parse_year_filter(None) is None


class TestReportToMarkdown:
    """测试 Markdown 输出格式"""

    def test_full_report(self):
        report = FullAnalysisReport(
            stock_code="600000.SH",
            report_date="2024-12-31",
            valuation=ValuationMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                current_price=10.0,
                currency="CNY",
                pe_ratio=12.0,
                pb_ratio=1.0,
                market_cap=1e10,
            ),
            profitability=ProfitabilityMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                roe=0.15,
                net_margin=0.10,
                gross_margin=0.30,
            ),
            efficiency=None,
            growth=None,
            safety=None,
        )
        md = _report_to_markdown(report)
        assert "# 财务分析报告: 600000.SH" in md
        assert "估值指标" in md
        assert "12.00" in md  # PE
        assert "盈利能力" in md
        assert "运营效率" in md
        assert "数据不可用" in md

    def test_empty_report(self):
        report = FullAnalysisReport(
            stock_code="9992.HK",
            report_date="N/A",
            valuation=None,
            profitability=None,
            efficiency=None,
            growth=None,
            safety=None,
        )
        md = _report_to_markdown(report)
        assert "数据不可用" in md


class TestReportToCsv:
    """测试 CSV 输出格式"""

    def test_full_report_csv(self):
        report = FullAnalysisReport(
            stock_code="600000.SH",
            report_date="2024-12-31",
            valuation=ValuationMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                current_price=10.0,
                currency="CNY",
                pe_ratio=12.0,
            ),
            profitability=None,
            efficiency=None,
            growth=None,
            safety=None,
        )
        csv_output = _report_to_csv(report)
        assert "维度" in csv_output
        assert "Valuation" in csv_output
        assert "P/E" in csv_output


class TestCompareOutput:
    """测试对比输出格式"""

    def _make_report(self, code, pe=None, roe=None):
        return FullAnalysisReport(
            stock_code=code,
            report_date="2024-12-31",
            valuation=ValuationMetrics(
                stock_code=code, report_date="2024-12-31",
                current_price=10.0, currency="HKD",
                pe_ratio=pe,
            ) if pe else None,
            profitability=ProfitabilityMetrics(
                stock_code=code, report_date="2024-12-31",
                roe=roe,
            ) if roe else None,
            efficiency=None,
            growth=None,
            safety=None,
        )

    def test_compare_table(self):
        r1 = self._make_report("0700.HK", pe=25.0, roe=0.20)
        r2 = self._make_report("9988.HK", pe=15.0, roe=0.10)
        output = _compare_to_table(["0700.HK", "9988.HK"], {"0700.HK": r1, "9988.HK": r2})
        assert "0700.HK" in output
        assert "9988.HK" in output

    def test_compare_markdown(self):
        r1 = self._make_report("0700.HK", pe=25.0)
        output = _compare_to_markdown(["0700.HK"], {"0700.HK": r1})
        assert "0700.HK" in output
        assert "|" in output

    def test_compare_csv(self):
        r1 = self._make_report("0700.HK", pe=25.0)
        output = _compare_to_csv(["0700.HK"], {"0700.HK": r1})
        assert "0700.HK" in output

    def test_compare_with_none(self):
        r1 = self._make_report("0700.HK", pe=25.0)
        output = _compare_to_table(["0700.HK", "9999.HK"], {"0700.HK": r1, "9999.HK": None})
        assert "0700.HK" in output
        assert "N/A" in output


class TestDimensionReason:
    """测试维度数据不可用原因显示"""

    def test_pretty_print_shows_reason(self):
        report = FullAnalysisReport(
            stock_code="9992.HK",
            report_date="N/A",
            valuation=None,
            profitability=None,
            efficiency=None,
            growth=None,
            safety=None,
            failed_dimensions=["valuation", "efficiency"],
        )
        output = report.pretty_print()
        assert "数据不可用" in output
        # 应该显示具体原因
        assert "需要" in output or "异常" in output

    def test_pretty_print_with_failed_dims(self):
        report = FullAnalysisReport(
            stock_code="9992.HK",
            report_date="N/A",
            valuation=None,
            profitability=ProfitabilityMetrics(
                stock_code="9992.HK", report_date="N/A", roe=0.15,
            ),
            efficiency=None,
            growth=None,
            safety=None,
            failed_dimensions=["efficiency"],
        )
        output = report.pretty_print()
        # 盈利能力有数据
        assert "PROFITABILITY" in output
        # 运营效率无数据
        assert "EFFICIENCY" in output
        assert "数据不可用" in output
