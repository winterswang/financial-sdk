"""
LongBridge 适配器单元测试

使用 fixture 数据，不依赖网络。
"""

import pytest

from financial_sdk.adapters.longbridge_cli_adapter import LongbridgeCLIAdapter


class TestFieldMapping:
    """测试字段映射"""

    def test_exact_match(self):
        """测试精确匹配"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter._map_field_name("营业收入(HKD)") == "revenue"
        assert adapter._map_field_name("净利润(HKD)") == "net_profit"
        assert adapter._map_field_name("毛利(HKD)") == "gross_profit"
        assert adapter._map_field_name("总资产(HKD)") == "total_assets"

    def test_currency_suffix_usd(self):
        """测试USD货币后缀"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter._map_field_name("营业收入(USD)") == "revenue"
        assert adapter._map_field_name("总资产(USD)") == "total_assets"

    def test_currency_suffix_cny(self):
        """测试CNY货币后缀"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter._map_field_name("营业收入(CNY)") == "revenue"
        assert adapter._map_field_name("总资产(CNY)") == "total_assets"

    def test_ratio_suffix(self):
        """测试'及占比'后缀"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        # "固定资产净值(HKD)及占比" -> "fixed_assets"
        assert adapter._map_field_name("固定资产净值(HKD)及占比") == "fixed_assets"
        assert adapter._map_field_name("存货(HKD)及占比") == "inventory"
        assert adapter._map_field_name("应收(HKD)及占比") == "accounts_receivable"

    def test_unmapped_field_preserved(self):
        """测试未映射字段保留原名"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        result = adapter._map_field_name("未知字段")
        assert result == "未知字段"

    def test_balance_sheet_key_fields(self):
        """测试资产负债表关键字段映射"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter._map_field_name("总资产(HKD)") == "total_assets"
        assert adapter._map_field_name("总负债(HKD)") == "total_liabilities"
        assert adapter._map_field_name("总权益(HKD)") == "total_equity"
        assert adapter._map_field_name("流动资产(HKD)") == "current_assets"
        assert adapter._map_field_name("流动负债(HKD)") == "current_liabilities"
        assert adapter._map_field_name("存货(HKD)") == "inventory"
        assert adapter._map_field_name("应收账款(HKD)") == "accounts_receivable"
        assert adapter._map_field_name("应付账款(HKD)") == "accounts_payable"
        assert adapter._map_field_name("现金及等价物(HKD)") == "cash_and_equivalents"
        assert adapter._map_field_name("每股净资产(HKD)") == "bvps"

    def test_income_statement_key_fields(self):
        """测试利润表关键字段映射"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter._map_field_name("营业收入(HKD)") == "revenue"
        assert adapter._map_field_name("毛利(HKD)") == "gross_profit"
        assert adapter._map_field_name("净利润(HKD)") == "net_profit"
        assert adapter._map_field_name("营业利润(HKD)") == "operating_profit"
        assert adapter._map_field_name("利息费用(HKD)") == "interest_expense"
        assert adapter._map_field_name("毛利率") == "gross_margin"
        assert adapter._map_field_name("净利率") == "net_margin"
        assert adapter._map_field_name("ROE") == "roe"


class TestDataSelfHealing:
    """测试数据自愈"""

    def test_fill_balance_derived_total_equity(self):
        """测试推算 total_equity"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "total_assets": [1000.0, 2000.0],
            "total_liabilities": [400.0, 800.0],
        })
        result = adapter._fill_balance_derived(df)
        assert "total_equity" in result.columns
        assert result["total_equity"].iloc[0] == 600.0
        assert result["total_equity"].iloc[1] == 1200.0

    def test_fill_balance_derived_debt_to_equity(self):
        """测试推算 debt_to_equity"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "total_assets": [1000.0],
            "total_liabilities": [400.0],
        })
        result = adapter._fill_balance_derived(df)
        assert "debt_to_equity" in result.columns
        # total_equity = 600, debt_to_equity = 400/600 = 0.667
        assert abs(result["debt_to_equity"].iloc[0] - 0.667) < 0.01

    def test_fill_balance_derived_no_overwrite(self):
        """测试已有字段不被覆盖"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "total_assets": [1000.0],
            "total_liabilities": [400.0],
            "total_equity": [700.0],  # 已有值
        })
        result = adapter._fill_balance_derived(df)
        assert result["total_equity"].iloc[0] == 700.0  # 不应被覆盖

    def test_fill_income_derived_gross_profit(self):
        """测试推算 gross_profit"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "revenue": [1000.0],
            "gross_margin": [30.0],  # 30%
        })
        result = adapter._fill_income_derived(df)
        assert "gross_profit" in result.columns
        assert result["gross_profit"].iloc[0] == 300.0  # 1000 * 30 / 100

    def test_fill_income_derived_total_cost(self):
        """测试推算 total_cost"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "revenue": [1000.0],
            "gross_margin": [30.0],
        })
        result = adapter._fill_income_derived(df)
        assert "total_cost" in result.columns
        assert result["total_cost"].iloc[0] == 700.0  # 1000 - 300

    def test_fill_balance_derived_records_warnings(self):
        """测试推算字段记录警告"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame({
            "total_assets": [1000.0],
            "total_liabilities": [400.0],
        })
        result = adapter._fill_balance_derived(df)
        assert "_derived_fields" in result.columns

    def test_fill_empty_df(self):
        """测试空 DataFrame 不出错"""
        import pandas as pd
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        df = pd.DataFrame()
        result = adapter._fill_balance_derived(df)
        assert result.empty
        result = adapter._fill_income_derived(df)
        assert result.empty


class TestStockCodeValidation:
    """测试股票代码验证"""

    def test_hk_stock_pattern(self):
        """测试港股代码格式"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter.HK_STOCK_PATTERN.match("0700.HK")
        assert adapter.HK_STOCK_PATTERN.match("9988.HK")
        assert adapter.HK_STOCK_PATTERN.match("9992.HK")
        assert not adapter.HK_STOCK_PATTERN.match("0700")

    def test_us_stock_pattern(self):
        """测试美股代码格式"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        assert adapter.US_STOCK_PATTERN.match("AAPL.US")
        assert adapter.US_STOCK_PATTERN.match("AAPL")
        assert adapter.US_STOCK_PATTERN.match("BRK.B.US")
        assert not adapter.US_STOCK_PATTERN.match("aapl")

    def test_normalize_hk_stock_code(self):
        """测试港股代码标准化"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        adapter._cli_path = "longbridge"
        assert adapter._normalize_stock_code("0700.HK") == "700.HK"
        assert adapter._normalize_stock_code("9992.HK") == "9992.HK"

    def test_normalize_us_stock_code(self):
        """测试美股代码标准化"""
        adapter = LongbridgeCLIAdapter.__new__(LongbridgeCLIAdapter)
        adapter._cli_path = "longbridge"
        assert adapter._normalize_stock_code("AAPL") == "AAPL.US"
        assert adapter._normalize_stock_code("AAPL.US") == "AAPL.US"
