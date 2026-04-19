"""
财务分析模块单元测试
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

import pandas as pd

from src.financial_sdk.analytics import (
    BaseAnalyzer,
    MetricsCalculator,
    ValuationAnalyzer,
    ValuationMetrics,
)
from src.financial_sdk.price import PriceData, PriceResult


class TestMetricsCalculator:
    """MetricsCalculator 测试"""

    def test_calculate_pe_ratio(self):
        """测试 PE 计算"""
        # 正常情况
        pe = MetricsCalculator.calculate_pe_ratio(price=100.0, eps=5.0)
        assert pe == 20.0

        # EPS 为 0
        pe = MetricsCalculator.calculate_pe_ratio(price=100.0, eps=0)
        assert pe is None

        # EPS 为 None
        pe = MetricsCalculator.calculate_pe_ratio(price=100.0, eps=None)
        assert pe is None

    def test_calculate_pb_ratio(self):
        """测试 PB 计算"""
        # 正常情况: BVPS = 10, price = 100, PB = 10
        pb = MetricsCalculator.calculate_pb_ratio(
            price=100.0, total_equity=1000.0, shares=100.0
        )
        assert pb == 10.0

        # shares 为 0
        pb = MetricsCalculator.calculate_pb_ratio(price=100.0, total_equity=1000.0, shares=0)
        assert pb is None

    def test_calculate_ps_ratio(self):
        """测试 PS 计算"""
        # 正常情况: PS = price / (revenue/shares)
        # price=100, revenue=1000, shares=10 -> (revenue/shares)=100 -> PS = 100/100 = 1.0
        ps = MetricsCalculator.calculate_ps_ratio(
            price=100.0, revenue=1000.0, shares=10.0
        )
        assert ps == 1.0  # 100 / (1000/10) = 100/100 = 1.0

    def test_calculate_dividend_yield(self):
        """测试股息率计算"""
        dy = MetricsCalculator.calculate_dividend_yield(dps=2.0, price=100.0)
        assert dy == 0.02  # 2%

    def test_calculate_net_margin(self):
        """测试净利率计算"""
        margin = MetricsCalculator.calculate_net_margin(net_profit=100.0, revenue=1000.0)
        assert margin == 0.1  # 10%

    def test_calculate_gross_margin(self):
        """测试毛利率计算"""
        margin = MetricsCalculator.calculate_gross_margin(gross_profit=300.0, revenue=1000.0)
        assert margin == 0.3  # 30%

    def test_calculate_current_ratio(self):
        """测试流动比率计算"""
        ratio = MetricsCalculator.calculate_current_ratio(
            current_assets=150.0, current_liabilities=100.0
        )
        assert ratio == 1.5

    def test_calculate_quick_ratio(self):
        """测试速动比率计算"""
        ratio = MetricsCalculator.calculate_quick_ratio(
            current_assets=150.0, inventory=50.0, current_liabilities=100.0
        )
        assert ratio == 1.0  # (150-50)/100 = 1

    def test_calculate_yoy_growth(self):
        """测试同比增长率"""
        growth = MetricsCalculator.calculate_yoy_growth(current=120.0, previous=100.0)
        assert growth == 0.2  # 20%

        # 负增长
        growth = MetricsCalculator.calculate_yoy_growth(current=80.0, previous=100.0)
        assert growth == -0.2  # -20%

    def test_get_latest_value(self):
        """测试从 DataFrame 获取最新值"""
        df = pd.DataFrame(
            {"report_date": ["2023-12-31", "2024-12-31"], "eps": [1.0, 1.5]}
        )

        value = MetricsCalculator.get_latest_value(df, "eps")
        assert value == 1.5  # 最新的是 1.5


class TestValuationMetrics:
    """ValuationMetrics 测试"""

    def test_creation(self):
        """测试创建"""
        metrics = ValuationMetrics(
            stock_code="600000.SH",
            report_date="2024-12-31",
            current_price=9.86,
            currency="CNY",
            pe_ratio=8.5,
            pb_ratio=0.9,
        )

        assert metrics.stock_code == "600000.SH"
        assert metrics.pe_ratio == 8.5
        assert metrics.pb_ratio == 0.9

    def test_to_dict(self):
        """测试转换为字典"""
        metrics = ValuationMetrics(
            stock_code="600000.SH",
            report_date="2024-12-31",
            current_price=9.86,
            currency="CNY",
        )

        data = metrics.to_dict()
        assert data["stock_code"] == "600000.SH"
        assert data["current_price"] == 9.86


class TestValuationAnalyzer:
    """ValuationAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        analyzer = ValuationAnalyzer()
        assert analyzer.analyzer_name == "valuation_analyzer"

    def test_supported_markets(self):
        """测试支持的市场"""
        analyzer = ValuationAnalyzer()
        assert "A" in analyzer.supported_markets
        assert "HK" in analyzer.supported_markets
        assert "US" in analyzer.supported_markets


class TestValuationAnalyzerWithMock:
    """带 Mock 的 ValuationAnalyzer 测试"""

    def test_get_pe_ratio_with_mock(self):
        """测试获取 PE 比率"""
        # Mock PriceProvider
        mock_price = PriceData(
            stock_code="600000.SH",
            market="A",
            current_price=9.86,
            currency="CNY",
        )
        mock_price_provider = MagicMock()
        mock_price_provider.get_price.return_value = PriceResult(
            success=True, price=mock_price
        )

        # Mock FinancialFacade - 模拟返回空的财务数据
        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = None
        mock_bundle.balance_sheet = None
        mock_bundle.cash_flow = None
        mock_bundle.indicators = None
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = ValuationAnalyzer(
            price_provider=mock_price_provider, financial_facade=mock_facade
        )

        # 由于财务数据为空，应该返回 None
        pe = analyzer.get_pe_ratio("600000.SH")
        assert pe is None  # 因为没有 EPS 数据

    def test_get_valuation_metrics_success(self):
        """测试获取完整估值指标"""
        # Mock PriceProvider
        mock_price = PriceData(
            stock_code="600000.SH",
            market="A",
            current_price=9.86,
            currency="CNY",
        )
        mock_price_provider = MagicMock()
        mock_price_provider.get_price.return_value = PriceResult(
            success=True, price=mock_price
        )

        # Mock FinancialFacade - 返回有数据的财务数据
        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame(
            {"report_date": ["2024-12-31"], "net_profit": [100.0], "revenue": [1000.0]}
        )
        mock_bundle.balance_sheet = pd.DataFrame(
            {
                "report_date": ["2024-12-31"],
                "total_equity": [1000.0],
                "total_assets": [5000.0],
            }
        )
        mock_bundle.cash_flow = pd.DataFrame(
            {"report_date": ["2024-12-31"], "depreciation_amortization": [50.0]}
        )
        mock_bundle.indicators = pd.DataFrame(
            {"report_date": ["2024-12-31"], "eps": [0.5]}
        )
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = ValuationAnalyzer(
            price_provider=mock_price_provider, financial_facade=mock_facade
        )

        metrics = analyzer.get_valuation_metrics("600000.SH")

        assert metrics is not None
        assert metrics.stock_code == "600000.SH"
        assert metrics.current_price == 9.86
        assert metrics.eps == 0.5


class TestBaseAnalyzer:
    """BaseAnalyzer 测试"""

    def test_abstract_class(self):
        """测试抽象类不能直接实例化"""

        class TestAnalyzer(BaseAnalyzer):
            @property
            def analyzer_name(self):
                return "test"

        analyzer = TestAnalyzer()
        assert analyzer.analyzer_name == "test"
        assert analyzer.health_check()["status"] == "healthy"


class TestMetricsCalculatorP1:
    """MetricsCalculator P1 盈利能力测试"""

    def test_calculate_asset_turnover(self):
        """测试资产周转率计算"""
        turnover = MetricsCalculator.calculate_asset_turnover(
            revenue=1000.0, total_assets=500.0
        )
        assert turnover == 2.0

    def test_calculate_equity_multiplier(self):
        """测试权益乘数计算"""
        multiplier = MetricsCalculator.calculate_equity_multiplier(
            total_assets=1000.0, total_equity=500.0
        )
        assert multiplier == 2.0

    def test_calculate_dupont_decomposition(self):
        """测试 DuPont 分解"""
        result = MetricsCalculator.calculate_dupont_decomposition(
            net_profit=100.0,
            revenue=1000.0,
            total_assets=2000.0,
            total_equity=1000.0,
        )

        assert result is not None
        assert result["net_margin"] == 0.1  # 100/1000
        assert result["asset_turnover"] == 0.5  # 1000/2000
        assert result["equity_multiplier"] == 2.0  # 2000/1000
        assert result["roe"] == 0.1  # 0.1 * 0.5 * 2.0 = 0.1

    def test_calculate_roic(self):
        """测试 ROIC 计算"""
        roic = MetricsCalculator.calculate_roic(
            ebit=200.0,
            tax_rate=0.25,
            total_debt=500.0,
            cash=100.0,
            total_equity=1000.0,
        )
        # Invested Capital = 500 + 1000 - 100 = 1400
        # NOPAT = 200 * (1 - 0.25) = 150
        # ROIC = 150 / 1400 = 0.107
        assert abs(roic - 0.107) < 0.001


class TestMetricsCalculatorP2:
    """MetricsCalculator P2 运营效率测试"""

    def test_calculate_dio(self):
        """测试存货周转天数"""
        dio = MetricsCalculator.calculate_dio(
            inventory=100.0, cogs=360.0, days=360
        )
        assert dio == 100.0  # 100/360 * 360 = 100

    def test_calculate_dso(self):
        """测试应收账款周转天数"""
        dso = MetricsCalculator.calculate_dso(
            accounts_receivable=90.0, revenue=360.0, days=360
        )
        assert dso == 90.0  # 90/360 * 360 = 90

    def test_calculate_dpo(self):
        """测试应付账款周转天数"""
        dpo = MetricsCalculator.calculate_dpo(
            accounts_payable=60.0, cogs=360.0, days=360
        )
        assert dpo == 60.0  # 60/360 * 360 = 60

    def test_calculate_operating_cycle(self):
        """测试营业周期"""
        oc = MetricsCalculator.calculate_operating_cycle(dio=100.0, dso=90.0)
        assert oc == 190.0

    def test_calculate_cash_conversion_cycle(self):
        """测试现金周转周期"""
        ccc = MetricsCalculator.calculate_cash_conversion_cycle(
            dio=100.0, dso=90.0, dpo=60.0
        )
        assert ccc == 130.0  # 100 + 90 - 60


class TestMetricsCalculatorSafety:
    """MetricsCalculator 财务安全测试"""

    def test_calculate_altman_z_score(self):
        """测试 Altman Z-Score"""
        z = MetricsCalculator.calculate_altman_z_score(
            working_capital=200.0,
            total_assets=1000.0,
            retained_earnings=300.0,
            ebit=200.0,
            market_cap=1500.0,
            total_liabilities=500.0,
            revenue=1000.0,
        )

        assert z is not None
        # Z = 1.2*(200/1000) + 1.4*(300/1000) + 3.3*(200/1000) + 0.6*(1500/500) + 1.0*(1000/1000)
        #   = 0.24 + 0.42 + 0.66 + 1.8 + 1.0 = 4.12
        assert abs(z - 4.12) < 0.01

    def test_calculate_interest_coverage(self):
        """测试利息保障倍数"""
        ic = MetricsCalculator.calculate_interest_coverage(
            ebit=300.0, interest_expense=100.0
        )
        assert ic == 3.0

    def test_calculate_debt_to_equity(self):
        """测试资产负债率"""
        de = MetricsCalculator.calculate_debt_to_equity(
            total_liabilities=500.0, total_equity=1000.0
        )
        assert de == 0.5

    def test_calculate_sustainable_growth(self):
        """测试可持续增长率"""
        sgr = MetricsCalculator.calculate_sustainable_growth_rate(
            roe=0.20, retention_rate=0.7
        )
        assert abs(sgr - 0.14) < 0.001  # 20% * 70% = 14%


class TestProfitabilityAnalyzer:
    """ProfitabilityAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        from src.financial_sdk.analytics import ProfitabilityAnalyzer

        analyzer = ProfitabilityAnalyzer()
        assert analyzer.analyzer_name == "profitability_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        from src.financial_sdk.analytics import ProfitabilityAnalyzer

        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "revenue": [1000.0],
            "gross_profit": [300.0],
            "operating_profit": [150.0],
            "net_profit": [100.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_assets": [2000.0],
            "total_equity": [1000.0],
            "total_liabilities": [1000.0],
            "current_assets": [800.0],
            "current_liabilities": [400.0],
        })
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "depreciation_amortization": [50.0],
        })
        mock_bundle.indicators = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [0.5],
        })
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = ProfitabilityAnalyzer(financial_facade=mock_facade)
        metrics = analyzer.get_profitability_metrics("600000.SH")

        assert metrics is not None
        assert metrics.gross_margin == 0.3
        assert metrics.net_margin == 0.1


class TestEfficiencyAnalyzer:
    """EfficiencyAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        from src.financial_sdk.analytics import EfficiencyAnalyzer

        analyzer = EfficiencyAnalyzer()
        assert analyzer.analyzer_name == "efficiency_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        from src.financial_sdk.analytics import EfficiencyAnalyzer

        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "revenue": [1000.0],
            "total_cost": [600.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "inventory": [100.0],
            "accounts_receivable": [90.0],
            "accounts_payable": [60.0],
            "total_assets": [2000.0],
        })
        mock_bundle.cash_flow = None
        mock_bundle.indicators = None
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = EfficiencyAnalyzer(financial_facade=mock_facade)
        metrics = analyzer.get_efficiency_metrics("600000.SH")

        assert metrics is not None
        assert metrics.dio == 60.0  # 100/600 * 360 = 60
        assert metrics.dso == 32.4  # 90/1000 * 360 = 32.4


class TestGrowthAnalyzer:
    """GrowthAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        from src.financial_sdk.analytics import GrowthAnalyzer

        analyzer = GrowthAnalyzer()
        assert analyzer.analyzer_name == "growth_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        from src.financial_sdk.analytics import GrowthAnalyzer

        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "revenue": [900.0, 1000.0],
            "net_profit": [80.0, 100.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "total_assets": [1800.0, 2000.0],
            "total_equity": [900.0, 1000.0],
        })
        mock_bundle.cash_flow = None
        mock_bundle.indicators = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "eps": [0.4, 0.5],
        })
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = GrowthAnalyzer(financial_facade=mock_facade)
        metrics = analyzer.get_growth_metrics("600000.SH")

        assert metrics is not None
        assert metrics.has_comparable_data is True
        assert abs(metrics.revenue_growth_yoy - 0.111) < 0.01  # 11.1% growth
        assert abs(metrics.profit_growth_yoy - 0.25) < 0.01  # 25% growth


class TestSafetyAnalyzer:
    """SafetyAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        from src.financial_sdk.analytics import SafetyAnalyzer

        analyzer = SafetyAnalyzer()
        assert analyzer.analyzer_name == "safety_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        from src.financial_sdk.analytics import SafetyAnalyzer
        from src.financial_sdk.price import PriceData

        # Mock PriceProvider
        mock_price = PriceData(
            stock_code="600000.SH",
            market="A",
            current_price=10.0,
            currency="CNY",
        )
        mock_price_provider = MagicMock()
        mock_price_provider.get_price.return_value = PriceResult(
            success=True, price=mock_price
        )

        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_profit": [200.0],
            "net_profit": [100.0],
            "revenue": [1000.0],
            "interest_expense": [50.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "current_assets": [600.0],
            "current_liabilities": [400.0],
            "total_assets": [2000.0],
            "total_equity": [1000.0],
            "total_liabilities": [1000.0],
            "cash_and_equivalents": [200.0],
        })
        mock_bundle.cash_flow = None
        mock_bundle.indicators = None
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = SafetyAnalyzer(
            financial_facade=mock_facade,
            price_provider=mock_price_provider,
        )
        metrics = analyzer.get_safety_metrics("600000.SH")

        assert metrics is not None
        assert metrics.current_ratio == 1.5  # 600/400
        # quick_ratio = (600 - 0) / 400 = 1.5 (inventory is None, treated as 0)
        assert metrics.quick_ratio == 1.5
        assert metrics.interest_coverage == 4.0  # 200/50


class TestFinancialAnalytics:
    """FinancialAnalytics 集成测试"""

    def test_analytics_name(self):
        """测试统一入口名称"""
        from src.financial_sdk.analytics import FinancialAnalytics

        analytics = FinancialAnalytics()
        assert analytics.valuation_analyzer.analyzer_name == "valuation_analyzer"
        assert analytics.profitability_analyzer.analyzer_name == "profitability_analyzer"
        assert analytics.efficiency_analyzer.analyzer_name == "efficiency_analyzer"
        assert analytics.growth_analyzer.analyzer_name == "growth_analyzer"
        assert analytics.safety_analyzer.analyzer_name == "safety_analyzer"

    def test_full_report_with_mock(self):
        """测试获取完整分析报告"""
        from src.financial_sdk.analytics import FinancialAnalytics
        from src.financial_sdk.price import PriceData, PriceResult

        # Mock PriceProvider
        mock_price = PriceData(
            stock_code="600000.SH",
            market="A",
            current_price=10.0,
            currency="CNY",
        )
        mock_price_provider = MagicMock()
        mock_price_provider.get_price.return_value = PriceResult(
            success=True, price=mock_price
        )

        # Mock FinancialFacade
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 利润表数据
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "revenue": [900.0, 1000.0],
            "gross_profit": [270.0, 300.0],
            "operating_profit": [135.0, 150.0],
            "net_profit": [80.0, 100.0],
            "total_cost": [540.0, 600.0],
            "interest_expense": [40.0, 50.0],
        })

        # 资产负债表数据
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "total_assets": [1800.0, 2000.0],
            "total_equity": [900.0, 1000.0],
            "total_liabilities": [900.0, 1000.0],
            "current_assets": [540.0, 600.0],
            "current_liabilities": [360.0, 400.0],
            "inventory": [90.0, 100.0],
            "accounts_receivable": [81.0, 90.0],
            "accounts_payable": [54.0, 60.0],
            "cash_and_equivalents": [180.0, 200.0],
        })

        # 现金流量表数据
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "depreciation_amortization": [45.0],
        })

        # 财务指标数据
        mock_bundle.indicators = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "eps": [0.4, 0.5],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analytics = FinancialAnalytics(
            price_provider=mock_price_provider,
            financial_facade=mock_facade,
        )

        # 获取完整报告
        report = analytics.get_full_report("600000.SH")

        assert report is not None
        assert report.stock_code == "600000.SH"
        assert report.valuation is not None
        assert report.profitability is not None
        assert report.efficiency is not None
        assert report.growth is not None
        assert report.safety is not None

    def test_get_score(self):
        """测试综合评分计算"""
        from src.financial_sdk.analytics import FinancialAnalytics, FullAnalysisReport
        from src.financial_sdk.analytics.profitability import ProfitabilityMetrics
        from src.financial_sdk.analytics.growth import GrowthMetrics
        from src.financial_sdk.analytics.safety import SafetyMetrics

        # 创建只有部分数据的报告
        report = FullAnalysisReport(
            stock_code="600000.SH",
            report_date="2024-12-31",
            valuation=None,
            profitability=ProfitabilityMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                roe=0.21,  # 高 ROE，+20分 (> 0.20)
            ),
            efficiency=None,
            growth=GrowthMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                revenue_growth_yoy=0.35,  # 高成长，+15分
            ),
            safety=SafetyMetrics(
                stock_code="600000.SH",
                report_date="2024-12-31",
                altman_z_score=3.5,  # 安全区，+15分
            ),
        )

        # 基础分50 + ROE20 + 成长15 + 安全15 = 100
        assert report.get_score() == 100.0

    def test_get_summary(self):
        """测试获取分析摘要"""
        from src.financial_sdk.analytics import FinancialAnalytics, FullAnalysisReport
        from src.financial_sdk.analytics.valuation import ValuationMetrics
        from src.financial_sdk.analytics.profitability import ProfitabilityMetrics

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

        summary = report.get_summary()
        assert summary["stock_code"] == "600000.SH"
        assert summary["pe"] == 12.0
        assert summary["pb"] == 1.0
        assert summary["roe"] == 0.15
        assert summary["net_margin"] == 0.10

    def test_pretty_print(self):
        """测试报告打印功能"""
        from src.financial_sdk.analytics import FullAnalysisReport
        from src.financial_sdk.analytics.valuation import ValuationMetrics

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
                dividend_yield=0.03,
            ),
            profitability=None,
            efficiency=None,
            growth=None,
            safety=None,
        )

        output = report.pretty_print()
        assert "600000.SH" in output
        assert "VALUATION METRICS" in output
        assert "P/E Ratio: 12.00" in output

    def test_health_check(self):
        """测试健康检查"""
        from src.financial_sdk.analytics import FinancialAnalytics

        analytics = FinancialAnalytics()
        health = analytics.health_check()

        assert "valuation_analyzer" in health
        assert "profitability_analyzer" in health
        assert "efficiency_analyzer" in health
        assert "growth_analyzer" in health
        assert "safety_analyzer" in health

    def test_shortcut_methods(self):
        """测试快捷方法"""
        from src.financial_sdk.analytics import FinancialAnalytics

        # Mock PriceProvider
        mock_price = MagicMock()
        mock_price.get_price.return_value = PriceResult(
            success=True,
            price=PriceData(
                stock_code="600000.SH",
                market="A",
                current_price=10.0,
                currency="CNY",
            )
        )

        # Mock FinancialFacade
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 利润表
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "revenue": [1000.0],
            "gross_profit": [300.0],
            "net_profit": [100.0],
        })

        # 资产负债表
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [1000.0],
            "total_assets": [2000.0],
        })

        # 现金流量表
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "depreciation_amortization": [50.0],
        })

        # 财务指标
        mock_bundle.indicators = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [0.5],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analytics = FinancialAnalytics(
            price_provider=mock_price,
            financial_facade=mock_facade,
        )

        # 测试快捷方法
        pe = analytics.get_pe_ratio("600000.SH")
        roe = analytics.get_roe("600000.SH")
        gross_margin = analytics.get_gross_margin("600000.SH")

        # PE = 10 / 0.5 = 20
        assert pe == 20.0
        # ROE = 100/1000 = 0.1
        assert roe == 0.1
        # Gross Margin = 300/1000 = 0.3
        assert gross_margin == 0.3
