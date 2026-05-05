"""测试内在价值分析器"""

import pytest
from unittest.mock import MagicMock
import pandas as pd

from financial_sdk.analytics import IntrinsicValueAnalyzer, IntrinsicValueMetrics


class TestIntrinsicValueAnalyzer:
    """IntrinsicValueAnalyzer 测试"""

    def test_analyzer_name(self):
        """测试分析器名称"""
        analyzer = IntrinsicValueAnalyzer()
        assert analyzer.analyzer_name == "intrinsic_value_analyzer"

    def test_with_mock_data(self):
        """测试带 Mock 数据"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # 利润表数据
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [5.0],
            "net_profit": [100000000.0],
            "revenue": [500000000.0],
        })

        # 资产负债表数据（包含 SHARE_CAPITAL，单位是万股）
        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [2000000000.0],  # 20亿
            "SHARE_CAPITAL": [100000.0],  # 10亿股（万股）
            "bvps": None,  # 不提供，需要计算
        })

        # 现金流量表数据
        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [150000000.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)

        # Mock 价格
        mock_price = MagicMock()
        mock_price.success = True
        mock_price.price = MagicMock()
        mock_price.price.current_price = 50.0
        mock_price.price.currency = "CNY"

        analyzer._price_provider.get_price = MagicMock(return_value=mock_price)
        analyzer._price_provider.get_market_cap = MagicMock(return_value=5000000000.0)

        result = analyzer.analyze("600000.SH")

        assert result is not None
        assert result.stock_code == "600000.SH"
        assert result.current_price == 50.0
        # BVPS = 20亿 / 10亿 = 2.0, BVPS_yuan = 2.0 * 10000 = 20000
        # Graham Number = √(22.5 * 5.0 * 20000) = √2250000 ≈ 1500
        if result.graham_number:
            assert result.graham_number > 1000  # 应该大于1000

    def test_graham_number_calculation(self):
        """测试 Graham Number 计算"""
        # total_equity = 50亿, shares = 10亿股
        # BVPS = 50亿 / 10亿 = 5 (元)
        # BVPS_yuan = 5 * 10000 = 50000 (因为 BVPS < 100，被当作万元单位)
        # GN = √(22.5 * 10 * 50000) = √11250000 ≈ 3354.1
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [10.0],
        })

        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [5000000000.0],  # 50亿
            "SHARE_CAPITAL": [100000.0],  # 10亿股（万股）
        })

        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [200000000.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)

        mock_price = MagicMock()
        mock_price.success = True
        mock_price.price = MagicMock()
        mock_price.price.current_price = 80.0  # 股价80元
        mock_price.price.currency = "CNY"

        analyzer._price_provider.get_price = MagicMock(return_value=mock_price)
        analyzer._price_provider.get_market_cap = MagicMock(return_value=8000000000.0)

        result = analyzer.analyze("TEST.STOCK")

        assert result is not None
        assert result.graham_number is not None
        # BVPS = 50亿 / 10亿 = 5, BVPS_yuan = 5 * 10000 = 50000
        # GN = √(22.5 * 10 * 50000) ≈ 3354
        assert result.graham_number > 3000  # Graham Number 应该很大
        # 股价80 << Graham Number 3354，表明强烈低估
        assert result.margin_of_safety > 0.9
        assert result.valuation_signal == "强烈低估 (买入区间)"

    def test_margin_of_safety_calculation(self):
        """测试安全边际计算"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        # total_equity = 50亿, shares = 10亿股
        # BVPS = 50亿 / 10亿 = 5, BVPS_yuan = 50000
        # GN = √(22.5 * 5 * 50000) = √5625000 ≈ 2371.7
        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [5.0],
        })

        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [5000000000.0],
            "SHARE_CAPITAL": [100000.0],  # 10亿股
        })

        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [200000000.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)

        mock_price = MagicMock()
        mock_price.success = True
        mock_price.price = MagicMock()
        mock_price.price.current_price = 100.0  # 股价100元，远低于 GN
        mock_price.price.currency = "CNY"

        analyzer._price_provider.get_price = MagicMock(return_value=mock_price)
        analyzer._price_provider.get_market_cap = MagicMock(return_value=1000000000.0)

        result = analyzer.analyze("TEST.STOCK")

        assert result is not None
        assert result.graham_number is not None
        assert result.margin_of_safety is not None
        # 100 < 2371 -> (2371 - 100) / 2371 ≈ 95.8%
        assert result.margin_of_safety > 0.9

    def test_get_graham_number(self):
        """测试快捷方法"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [8.0],
        })

        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [1000000000.0],  # 10亿
            "SHARE_CAPITAL": [100000.0],  # 10亿股
        })

        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [100000000.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)

        mock_price = MagicMock()
        mock_price.success = True
        mock_price.price = MagicMock()
        mock_price.price.current_price = 50.0
        mock_price.price.currency = "CNY"

        analyzer._price_provider.get_price = MagicMock(return_value=mock_price)
        analyzer._price_provider.get_market_cap = MagicMock(return_value=500000000.0)

        gn = analyzer.get_graham_number("TEST.STOCK")

        # BVPS = 10亿 / 10亿 = 1, BVPS_yuan = 1 * 10000 = 10000
        # GN = √(22.5 * 8 * 10000) = √1800000 ≈ 1341.6
        assert gn is not None
        assert gn > 1000

    def test_get_margin_of_safety(self):
        """测试获取安全边际快捷方法"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()

        mock_bundle.income_statement = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "eps": [10.0],
        })

        mock_bundle.balance_sheet = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "total_equity": [1000000000.0],
            "SHARE_CAPITAL": [100000.0],
        })

        mock_bundle.cash_flow = pd.DataFrame({
            "report_date": ["2024-12-31"],
            "operating_cash_flow": [100000000.0],
        })

        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)

        mock_price = MagicMock()
        mock_price.success = True
        mock_price.price = MagicMock()
        mock_price.price.current_price = 100.0
        mock_price.price.currency = "CNY"

        analyzer._price_provider.get_price = MagicMock(return_value=mock_price)
        analyzer._price_provider.get_market_cap = MagicMock(return_value=1000000000.0)

        mos = analyzer.get_margin_of_safety("TEST.STOCK")

        assert mos is not None

    def test_metrics_to_dict(self):
        """测试指标转字典"""
        metrics = IntrinsicValueMetrics(
            stock_code="TEST",
            report_date="2024-12-31",
            current_price=100.0,
            currency="CNY",
            graham_number=150.0,
            margin_of_safety=-0.5,
            valuation_signal="高估",
        )

        data = metrics.to_dict()

        assert data["stock_code"] == "TEST"
        assert data["graham_number"] == 150.0
        assert data["valuation_signal"] == "高估"

    def test_health_check(self):
        """测试健康检查"""
        mock_facade = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.income_statement = pd.DataFrame({"report_date": []})
        mock_bundle.balance_sheet = pd.DataFrame({"report_date": []})
        mock_bundle.cash_flow = pd.DataFrame({"report_date": []})
        mock_facade.get_financial_data.return_value = mock_bundle

        analyzer = IntrinsicValueAnalyzer(financial_facade=mock_facade)
        health = analyzer.health_check()

        assert "facade_available" in health