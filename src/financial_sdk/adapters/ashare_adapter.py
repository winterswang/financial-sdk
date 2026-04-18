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
            config_path = (
                Path(__file__).parent.parent.parent / "config" / "field_mapping.yaml"
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
                    "TOTAL_NON_CURRENT_ASSETS": "non_current_assets",
                    "TOTAL_ASSETS": "total_assets",
                    "TOTAL_CURRENT_LIABILITIES": "current_liabilities",
                    "TOTAL_NON_CURRENT_LIABILITIES": "non_current_liabilities",
                    "TOTAL_LIABILITIES": "total_liabilities",
                    "TOTAL_EQUITY": "total_equity",
                    "FIXED_ASSETS": "fixed_assets",
                    "INTANGIBLE_ASSETS": "intangible_assets",
                    "ACCOUNTS_RECEIVABLE": "accounts_receivable",
                    "INVENTORIES": "inventory",
                    "ACCOUNTS_PAYABLE": "accounts_payable",
                    "SHORT_TERM_BORROWINGS": "short_term_debt",
                    "LONG_TERM_BORROWINGS": "long_term_debt",
                },
                "income_statement": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "OPERATING_REVENUE": "revenue",
                    "OPERATING_COST": "total_cost",
                    "GROSS_PROFIT": "gross_profit",
                    "OPERATING_PROFIT": "operating_profit",
                    "TOTAL_PROFIT": "profit_before_tax",
                    "NET_PROFIT": "net_profit",
                    "BASIC_EPS": "eps",
                    "SELLING_EXPENSE": "selling_expense",
                    "ADMINISTRATIVE_EXPENSE": "admin_expense",
                    "FINANCIAL_EXPENSE": "financial_expense",
                    "RD_EXPENSE": "rd_expense",
                    "TAX_EXPENSE": "tax_expense",
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
            df = self._map_fields(df, "balance_sheet")
            df = self._standardize_date_column(df, "report_date")
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
            # AkShare的利润表接口 (与资产负债表相同接口)
            df = akshare.stock_profit_sheet_by_report_em(
                symbol=self._extract_stock_code(stock_code)
            )
            self._validate_not_empty(df, stock_code, "income_statement")
            df = self._map_fields(df, "income_statement")
            df = self._standardize_date_column(df, "report_date")
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
            # AkShare的财务指标接口
            df = akshare.stock_financial_analysis_indicator(
                symbol=self._extract_stock_code(stock_code)
            )
            self._validate_not_empty(df, stock_code, "indicators")
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

    def is_available(self) -> bool:
        """检查akshare是否可用"""
        try:
            self._get_akshare()
            return True
        except Exception:
            return False
