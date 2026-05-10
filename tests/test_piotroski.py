"""测试 Piotroski F-Score 分析器"""

from unittest.mock import MagicMock
import pandas as pd

from financial_sdk.analytics import PiotroskiAnalyzer


class TestPiotroskiAnalyzer:
    """PiotroskiAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        analyzer = PiotroskiAnalyzer()
        assert analyzer.analyzer_name == "piotroski_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        # Mock FinancialFacade
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 利润表数据
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "net_profit": [800.0, 1000.0],
            "roa": [0.08, 0.10],
            "gross_margin": [0.90, 0.91],
            "revenue": [900.0, 1000.0],
        })

        # 资产负债表数据
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "total_assets": [18000.0, 20000.0],
            "total_equity": [9000.0, 10000.0],
            "total_liabilities": [9000.0, 10000.0],
            "current_assets": [5400.0, 6000.0],
            "current_liabilities": [3600.0, 4000.0],
            "bvps": [9.0, 10.0],
            "资产周转率": [0.05, 0.05],
        })

        # 现金流量表数据
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "operating_cash_flow": [850.0, 1100.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = PiotroskiAnalyzer(financial_facade=mock_facade)
        result = analyzer.analyze("600000.SH")

        assert result is not None
        assert result.stock_code == "600000.SH"
        assert isinstance(result.f_score, int)
        assert 0 <= result.f_score <= 9
        assert len(result.details) == 9
        assert result.assessment in ["strong", "good", "average", "weak"]

    def test_f_score_calculation(self):
        """测试 F-Score 计算"""
        # Mock FinancialFacade - 模拟一个高 F-Score 公司
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 利润表：净利润为正，ROA 提升
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "net_profit": [100.0, 200.0],
            "roa": [0.05, 0.10],
            "gross_margin": [0.30, 0.35],
            "revenue": [1000.0, 1200.0],
        })

        # 资产负债表：负债率下降，流动比率提升，BVPS 提升
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "total_assets": [2000.0, 2200.0],
            "total_equity": [1000.0, 1200.0],
            "total_liabilities": [1000.0, 1000.0],  # 负债不变，资产增加 -> 负债率下降
            "current_assets": [600.0, 700.0],
            "current_liabilities": [400.0, 350.0],  # 流动资产增加，流动负债减少 -> 比率提升
            "bvps": [1.0, 1.1],  # BVPS 提升
            "资产周转率": [0.50, 0.55],
        })

        # 现金流量表：OCF > 0 且 OCF > Net Income
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2023-12-31", "2024-12-31"],
            "operating_cash_flow": [150.0, 250.0],  # > Net Income
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = PiotroskiAnalyzer(financial_facade=mock_facade)
        result = analyzer.analyze("TEST.STOCK")

        assert result is not None
        # 预期高 F-Score
        assert result.f_score >= 6
        assert result.profitability_score >= 3
        assert result.leverage_score >= 1
        assert result.efficiency_score >= 1

    def test_get_f_score(self):
        """测试快捷方法"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "net_profit": [100.0],
            "roa": [0.10],
            "gross_margin": [0.30],
            "revenue": [1000.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_assets": [2000.0],
            "total_equity": [1000.0],
            "total_liabilities": [1000.0],
            "current_assets": [600.0],
            "current_liabilities": [400.0],
            "bvps": [1.0],
            "资产周转率": [0.50],
        })
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [150.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = PiotroskiAnalyzer(financial_facade=mock_facade)
        f_score = analyzer.get_f_score("TEST.STOCK")

        assert f_score is not None
        assert 0 <= f_score <= 9

    def test_single_period_fallback(self):
        """测试只有单期数据的情况"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 只有一期数据
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "net_profit": [100.0],
            "roa": [0.10],
            "gross_margin": [0.30],
            "revenue": [1000.0],
        })
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_assets": [2000.0],
            "total_equity": [1000.0],
            "total_liabilities": [500.0],
            "current_assets": [600.0],
            "current_liabilities": [400.0],
            "bvps": [1.0],
            "资产周转率": [0.50],
        })
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [150.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = PiotroskiAnalyzer(financial_facade=mock_facade)
        result = analyzer.analyze("TEST.STOCK")

        assert result is not None
        # 单期数据只能计算部分指标
        assert 0 <= result.f_score <= 9

    def test_health_check(self):
        """测试健康检查"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({"report_date": []})
        mock_bundle.balance_sheet = pd.DataFrame({"report_date": []})
        mock_bundle.cash_flow = pd.DataFrame({"report_date": []})
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = PiotroskiAnalyzer(financial_facade=mock_facade)
        health = analyzer.health_check()

        assert "facade_available" in health
