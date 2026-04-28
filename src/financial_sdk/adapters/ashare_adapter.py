"""
A股适配器

封装AkShare接口，获取A股财务数据。
"""

import importlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from ..base_adapter import BaseAdapter
from ..exceptions import DataNotAvailableError, InvalidStockCodeError


class ASHareAdapter(BaseAdapter):
    """
    A股适配器

    封装AkShare接口，获取A股财务报表和财务指标。

    支持的股票代码格式:
    - 600000.SH (上海证券交易所)
    - 000001.SZ (深圳证券交易所)
    """

    # A股股票代码正则: 6位数字 + .SH 或 .SZ
    STOCK_CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化A股适配器

        Args:
            config_path: 字段映射配置文件路径
        """
        self._akshare: Optional[Any] = None
        self._field_mapping: Dict[str, Dict[str, str]] = {}
        self._load_field_mapping(config_path)

    def _load_field_mapping(self, config_path: Optional[str] = None) -> None:
        """加载字段映射配置"""
        if config_path is None:
            # 使用默认配置
            # 项目结构: financial-sdk/src/financial_sdk/adapters/ashare_adapter.py
            #           financial-sdk/config/field_mapping.yaml
            # src/financial_sdk/adapters/ -> 3 levels up to project root
            config_path = (
                Path(__file__).resolve().parent.parent.parent
                / "config"
                / "field_mapping.yaml"
            )
        else:
            config_path = Path(config_path)

        if config_path.exists():
            import yaml

            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self._field_mapping = config or {}
        else:
            # 使用内嵌的默认映射（AkShare 返回英文字段名）
            self._field_mapping = {
                "balance_sheet": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "TOTAL_CURRENT_ASSETS": "current_assets",
                    "TOTAL_NONCURRENT_ASSETS": "non_current_assets",
                    "TOTAL_ASSETS": "total_assets",
                    "TOTAL_CURRENT_LIAB": "current_liabilities",
                    "TOTAL_NONCURRENT_LIAB": "non_current_liabilities",
                    "TOTAL_LIABILITIES": "total_liabilities",
                    "TOTAL_EQUITY": "total_equity",
                    "TOTAL_PARENT_EQUITY": "total_parent_equity",
                    "FIXED_ASSET": "fixed_assets",
                    "INTANGIBLE_ASSETS": "intangible_assets",
                    "ACCOUNTS_RECE": "accounts_receivable",
                    "INVENTORY": "inventory",
                    "ACCOUNTS_PAYABLE": "accounts_payable",
                    "SHORT_LOAN": "short_term_debt",
                    "LONG_LOAN": "long_term_debt",
                    "MONETARYFUNDS": "cash_and_equivalents",
                    "SURPLUS_RESERVE": "surplus_reserve",
                    "CAPITAL_RESERVE": "capital_reserve",
                    "SPECIAL_RESERVE": "special_reserve",
                    "MINORITY_EQUITY": "minority_interest",
                },
                "income_statement": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "OPERATE_INCOME": "revenue",
                    "OPERATE_COST": "total_cost",
                    "OPERATE_PROFIT": "operating_profit",
                    "TOTAL_PROFIT": "profit_before_tax",
                    "NETPROFIT": "net_profit",
                    "PARENT_NETPROFIT": "parent_net_profit",
                    "BASIC_EPS": "eps",
                    "SALE_EXPENSE": "selling_expense",
                    "MANAGE_EXPENSE": "admin_expense",
                    "FINANCE_EXPENSE": "financial_expense",
                    "RESEARCH_EXPENSE": "rd_expense",
                    "OPERATE_TAX_ADD": "tax_expense",
                    "INTEREST_EXPENSE": "interest_expense",
                    "ASSET_IMPAIRMENT_LOSS": "asset_impairment_loss",
                },
                "cash_flow": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "NETCASH_OPERATE": "operating_cash_flow",
                    "NETCASH_INVEST": "investing_cash_flow",
                    "NETCASH_FINANCE": "financing_cash_flow",
                    "CCE_ADD": "net_cash_flow",
                    "BEGIN_CASH": "beginning_cash",
                    "END_CASH": "ending_cash",
                    "TOTAL_OPERATE_INFLOW": "total_operating_inflow",
                    "TOTAL_OPERATE_OUTFLOW": "total_operating_outflow",
                    "TOTAL_INVEST_INFLOW": "total_investing_inflow",
                    "TOTAL_INVEST_OUTFLOW": "total_investing_outflow",
                    "TOTAL_FINANCE_INFLOW": "total_financing_inflow",
                    "TOTAL_FINANCE_OUTFLOW": "total_financing_outflow",
                    "PAY_STAFF_CASH": "staff_cash_paid",
                    "PAY_ALL_TAX": "taxes_paid",
                    "CONSTRUCT_LONG_ASSET": "construction_in_progress",
                    "CAPEX": "capex",
                    "INVEST_PAY_CASH": "investment_cash_paid",
                    "ASSIGN_DIVIDEND_PORFIT": "dividends_paid",
                    "PAY_DEBT_CASH": "debt_repayment",
                    "RECEIVE_TAX_REFUND": "tax_refund_received",
                    "DEPRECIATION_AMORTIZATION": "depreciation_amortization",
                },
                "indicators": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "ROE_AVG": "roe",
                    "ROA": "roa",
                    "GROSS_PROFIT_RATIO": "gross_margin",
                    "NET_PROFIT_RATIO": "net_margin",
                    "BASIC_EPS": "eps",
                    "CURRENT_RATIO": "current_ratio",
                    "QUICK_RATIO": "quick_ratio",
                    "DEBT_ASSET_RATIO": "debt_to_assets",
                },
            }

    @property
    def adapter_name(self) -> str:
        return "akshare"

    @property
    def supported_markets(self) -> List[str]:
        return ["A"]

    @property
    def priority(self) -> int:
        return 1

    def _get_akshare(self) -> Any:
        """懒加载akshare模块"""
        if self._akshare is None:
            try:
                self._akshare = importlib.import_module("akshare")
            except ImportError:
                raise DataNotAvailableError(
                    stock_code="N/A",
                    report_type="all",
                    reason="akshare模块未安装",
                    adapter_name=self.adapter_name,
                )
        return self._akshare

    def validate_stock_code(self, stock_code: str) -> bool:
        """
        验证A股股票代码格式

        Args:
            stock_code: 股票代码

        Returns:
            bool: 是否有效

        Raises:
            InvalidStockCodeError: 股票代码格式无效时抛出
        """
        if not self.STOCK_CODE_PATTERN.match(stock_code):
            raise InvalidStockCodeError(
                stock_code=stock_code,
                expected_format="6位数字.SH 或 6位数字.SZ (如 600000.SH)",
                market="A",
            )
        return True

    def _extract_stock_code(self, stock_code: str) -> str:
        """从标准格式提取 AkShare 需要的代码格式 (如 600000.SH -> SH600000)"""
        code, market = stock_code.split(".")
        # AkShare 需要 SH600000 或 SZ000001 格式
        return f"{market.upper()}{code}"

    def _map_fields(self, df: pd.DataFrame, report_type: str) -> pd.DataFrame:
        """
        映射字段名

        Args:
            df: 原始DataFrame
            report_type: 报表类型

        Returns:
            pd.DataFrame: 字段名标准化后的DataFrame
        """
        if df is None or df.empty:
            return df

        mapping = self._field_mapping.get(report_type, {})
        unmapped_columns: Set[str] = set()

        # 重命名列
        renamed_columns = {}
        for col in df.columns:
            if col in mapping:
                renamed_columns[col] = mapping[col]
            else:
                unmapped_columns.add(col)

        df = df.rename(columns=renamed_columns)

        # 删除 _YOY 同比列 (AkShare 每个字段都带 _YOY 列，不需要)
        yoy_cols = [c for c in df.columns if str(c).endswith("_YOY")]
        if yoy_cols:
            df = df.drop(columns=yoy_cols)

        # 添加原始数据源标识
        df["_raw_data_source"] = self.adapter_name

        # 记录原始字段映射
        df["_raw_field_names"] = str({v: k for k, v in renamed_columns.items()})

        return df

    def _validate_not_empty(
        self, df: pd.DataFrame, stock_code: str, report_type: str
    ) -> None:
        """
        验证数据非空

        Args:
            df: DataFrame
            stock_code: 股票代码
            report_type: 报表类型

        Raises:
            DataNotAvailableError: 数据为空时抛出
        """
        if df is None or df.empty:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type=report_type,
                reason="AkShare返回空数据",
                adapter_name=self.adapter_name,
            )

    def _filter_by_period(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """
        按报告期类型过滤 DataFrame

        AkShare 返回年报+季报数据，根据 period 参数过滤。
        年度报告日期通常以 12-31 或 1231 结尾。

        Args:
            df: 原始 DataFrame（含 REPORT_DATE 列）
            period: "annual" 或 "quarterly"

        Returns:
            过滤后的 DataFrame
        """
        if df.empty or "REPORT_DATE" not in df.columns:
            return df

        date_str = df["REPORT_DATE"].astype(str)
        is_annual = date_str.str.contains(
            r"(?:1231|12-31|12/31)\s*(?:00:00:00)?$", regex=True
        )
        if period == "annual":
            return df[is_annual]
        else:
            return df[~is_annual]

    def get_balance_sheet(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取A股资产负债表

        Args:
            stock_code: 股票代码 (如 600000.SH)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的资产负债表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        try:
            # AkShare的资产负债表接口
            df = akshare.stock_balance_sheet_by_report_em(
                symbol=self._extract_stock_code(stock_code)
            )
            self._validate_not_empty(df, stock_code, "balance_sheet")
            # 按 period 过滤: 年度=12月31日, 季度=其他
            df = self._filter_by_period(df, period)
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="balance_sheet",
                    reason=f"AkShare无{period}数据",
                    adapter_name=self.adapter_name,
                )
            df = self._map_fields(df, "balance_sheet")
            df = self._standardize_date_column(df, "report_date")
            df = self._fill_balance_derived(df)
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="balance_sheet",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

    def get_income_statement(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取A股利润表

        Args:
            stock_code: 股票代码 (如 600000.SH)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的利润表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        try:
            # AkShare的利润表接口
            df = akshare.stock_profit_sheet_by_report_em(
                symbol=self._extract_stock_code(stock_code)
            )
            self._validate_not_empty(df, stock_code, "income_statement")
            df = self._filter_by_period(df, period)
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="income_statement",
                    reason=f"AkShare无{period}数据",
                    adapter_name=self.adapter_name,
                )
            df = self._map_fields(df, "income_statement")
            df = self._standardize_date_column(df, "report_date")
            df = self._fill_income_derived(df)
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="income_statement",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

    def get_cash_flow(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取A股现金流量表

        Args:
            stock_code: 股票代码 (如 600000.SH)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的现金流量表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        try:
            # AkShare的现金流量表接口
            df = akshare.stock_cash_flow_sheet_by_report_em(
                symbol=self._extract_stock_code(stock_code)
            )
            self._validate_not_empty(df, stock_code, "cash_flow")
            df = self._filter_by_period(df, period)
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="cash_flow",
                    reason=f"AkShare无{period}数据",
                    adapter_name=self.adapter_name,
                )
            df = self._map_fields(df, "cash_flow")
            df = self._standardize_date_column(df, "report_date")
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="cash_flow",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

    def get_indicators(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取A股财务指标

        Args:
            stock_code: 股票代码 (如 600000.SH)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的财务指标

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        try:
            # 使用 stock_financial_abstract 接口获取财务指标
            # stock_financial_abstract 需要6位纯数字代码（如 "600000"）
            code, market = stock_code.split(".")
            df = akshare.stock_financial_abstract(
                symbol=code,
                indicator="按报告期" if period == "quarterly" else "按年度",
            )
            self._validate_not_empty(df, stock_code, "indicators")

            # 转换数据格式：从长格式转为宽格式
            # stock_financial_abstract 返回的格式是：
            # 选项 | 指标 | 20251231 | 20250930 | ...
            # 需要转换为：
            # REPORT_DATE | SECURITY_CODE | 指标1 | 指标2 | ...

            df = self._pivot_indicators(df, period)
            df = self._map_fields(df, "indicators")
            df = self._standardize_date_column(df, "report_date")
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="indicators",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

    def _pivot_indicators(
        self, df: pd.DataFrame, period: str = "annual"
    ) -> pd.DataFrame:
        """
        将 stock_financial_abstract 返回的长格式数据透视为宽格式

        Args:
            df: 原始 DataFrame
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 透视后的宽格式 DataFrame
        """
        if df is None or df.empty:
            return df

        # 列名：选项、指标、然后是日期列
        all_date_columns = [c for c in df.columns if c not in ["选项", "指标"]]

        # 根据 period 过滤日期列
        # 年度报告: MMDD = 1231
        # 季度报告: MMDD = 0331, 0630, 0930
        if period == "annual":
            date_columns = [c for c in all_date_columns if c.endswith("1231")]
        else:  # quarterly
            date_columns = [c for c in all_date_columns if not c.endswith("1231")]

        # 为每个日期创建一个行
        rows = []
        for date_col in date_columns:
            row_data = {"report_date": date_col}
            for idx, row in df.iterrows():
                indicator_name = row["指标"]
                value = row[date_col]
                row_data[indicator_name] = value
            rows.append(row_data)

        result_df = pd.DataFrame(rows)

        return result_df

    def _fill_balance_derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """资产负债表数据自愈: 推算缺失的标准字段"""
        if df is None or df.empty:
            return df

        # 推算 total_equity = total_assets - total_liabilities
        if "total_equity" not in df.columns or df["total_equity"].isna().all():
            if "total_assets" in df.columns and "total_liabilities" in df.columns:
                df["total_equity"] = df["total_assets"] - df["total_liabilities"]

        # 推算 current_liabilities = total_liabilities - non_current_liabilities
        if "current_liabilities" not in df.columns or df["current_liabilities"].isna().all():
            if "total_liabilities" in df.columns and "non_current_liabilities" in df.columns:
                df["current_liabilities"] = df["total_liabilities"] - df["non_current_liabilities"]

        return df

    def _fill_income_derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """利润表数据自愈: 推算缺失的标准字段"""
        if df is None or df.empty:
            return df

        # 推算 gross_profit = revenue - total_cost
        if "gross_profit" not in df.columns or df["gross_profit"].isna().all():
            if "revenue" in df.columns and "total_cost" in df.columns:
                df["gross_profit"] = df["revenue"] - df["total_cost"]

        # 推算 revenue = operating_profit + total_cost (如果revenue缺失)
        if "revenue" not in df.columns or df["revenue"].isna().all():
            if "operating_profit" in df.columns and "total_cost" in df.columns:
                df["revenue"] = df["operating_profit"] + df["total_cost"]

        # 推算 net_profit = profit_before_tax * (1 - approximate_tax_rate)
        if "net_profit" not in df.columns or df["net_profit"].isna().all():
            if "profit_before_tax" in df.columns:
                df["net_profit"] = df["profit_before_tax"] * 0.75  # 假设25%税率

        return df

    def is_available(self) -> bool:
        """检查akshare是否可用"""
        try:
            self._get_akshare()
            return True
        except Exception:
            return False
