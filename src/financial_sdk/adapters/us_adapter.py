"""
美股适配器

封装AkShare接口，获取美股财务数据。
"""

import importlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..base_adapter import BaseAdapter
from ..exceptions import DataNotAvailableError, InvalidStockCodeError


class USAdapter(BaseAdapter):
    """
    美股适配器

    封装AkShare接口，获取美股财务报表和财务指标。

    支持的股票代码格式:
    - AAPL (苹果)
    - MSFT (微软)
    """

    # 美股股票代码正则: 1-5个大写字母
    STOCK_CODE_PATTERN = re.compile(r"^[A-Z]{1,5}$")

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化美股适配器

        Args:
            config_path: 字段映射配置文件路径
        """
        self._akshare: Optional[Any] = None
        self._field_mapping: Dict[str, Dict[str, str]] = {}
        self._load_field_mapping(config_path)

    def _load_field_mapping(self, config_path: Optional[str] = None) -> None:
        """加载字段映射配置"""
        if config_path is None:
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
            # 使用内嵌的默认映射
            # AkShare US 报表数据字段映射（长格式数据的 ITEM_NAME -> 标准字段名）
            self._field_mapping = {
                "balance_sheet": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "流动资产合计": "current_assets",
                    "非流动资产合计": "non_current_assets",
                    "资产总计": "total_assets",
                    "流动负债合计": "current_liabilities",
                    "非流动负债合计": "non_current_liabilities",
                    "总负债": "total_liabilities",
                    "股东权益合计": "total_equity",
                    "归属于母公司股东权益": "total_equity",
                    "物业、厂房及设备": "fixed_assets",
                    "无形资产": "intangible_assets",
                    "商誉": "goodwill",
                    "应收账款": "accounts_receivable",
                    "存货": "inventory",
                    "应付账款": "accounts_payable",
                    "短期债务": "short_term_debt",
                    "长期负债": "long_term_debt",
                    "现金及现金等价物": "cash_and_equivalents",
                    "短期投资": "short_term_investments",
                    "长期投资": "long_term_investments",
                    "应付票据(流动)": "notes_payable",
                    "其他流动资产": "other_current_assets",
                    "其他非流动资产": "other_non_current_assets",
                },
                "income_statement": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "营业收入": "revenue",
                    "主营收入": "revenue",
                    "营业成本": "total_cost",
                    "主营成本": "total_cost",
                    "毛利": "gross_profit",
                    "营业利润": "operating_profit",
                    "持续经营税前利润": "profit_before_tax",
                    "所得税": "tax_expense",
                    "净利润": "net_profit",
                    "归属于母公司股东净利润": "net_profit",
                    "基本每股收益-普通股": "eps",
                    "摊薄每股收益-普通股": "diluted_eps",
                    "营业费用": "operating_expense",
                    "营销费用": "selling_expense",
                    "管理费用": "admin_expense",
                    "研发费用": "rd_expense",
                    "其他收入(支出)": "other_income_expense",
                },
                "cash_flow": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "经营活动产生的现金流量净额": "operating_cash_flow",
                    "投资活动产生的现金流量净额": "investing_cash_flow",
                    "筹资活动产生的现金流量净额": "financing_cash_flow",
                    "现金及现金等价物增加(减少)额": "net_cash_flow",
                    "现金及现金等价物期初余额": "beginning_cash",
                    "现金及现金等价物期末余额": "ending_cash",
                    "折旧及摊销": "depreciation_amortization",
                    "购买固定资产": "capex",
                    "存货": "inventory_change",
                    "应付账款及票据": "accounts_payable_change",
                    "应收账款及票据": "accounts_receivable_change",
                    "股息支付": "dividends_paid",
                    "回购股份": "share_repurchase",
                    "发行股份": "stock_issuance",
                    "发行债券": "debt_issuance",
                    "赎回债券": "debt_repayment",
                },
                "indicators": {
                    "REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "ROE_AVG": "roe",
                    "ROA": "roa",
                    "GROSS_PROFIT_RATIO": "gross_margin",
                    "NET_PROFIT_RATIO": "net_margin",
                    "BASIC_EPS": "eps",
                    "DILUTED_EPS": "diluted_eps",
                    "CURRENT_RATIO": "current_ratio",
                    "DEBT_ASSET_RATIO": "debt_to_equity",
                    "OPERATE_INCOME": "revenue",
                    "GROSS_PROFIT": "gross_profit",
                },
            }

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

    @property
    def adapter_name(self) -> str:
        return "akshare_us"

    @property
    def supported_markets(self) -> List[str]:
        return ["US"]

    @property
    def priority(self) -> int:
        return 1

    def validate_stock_code(self, stock_code: str) -> bool:
        """
        验证美股股票代码格式

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
                expected_format="1-5个大写字母 (如 AAPL)",
                market="US",
            )
        return True

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

        # 检查是否为长格式数据（包含 ITEM_NAME 列）
        if "ITEM_NAME" in df.columns:
            return self._pivot_long_to_wide(df, report_type, mapping)

        renamed_columns = {}
        for col in df.columns:
            if col in mapping:
                renamed_columns[col] = mapping[col]

        df = df.rename(columns=renamed_columns)

        # 添加原始数据源标识
        df["_raw_data_source"] = self.adapter_name

        # 记录原始字段映射
        df["_raw_field_names"] = str({v: k for k, v in renamed_columns.items()})

        return df

    def _pivot_long_to_wide(
        self, df: pd.DataFrame, report_type: str, mapping: Dict[str, str]
    ) -> pd.DataFrame:
        """
        将长格式数据透视为宽格式

        AkShare US 报表返回的是长格式：
        - ITEM_NAME: 科目名称
        - AMOUNT: 金额

        Args:
            df: 原始DataFrame
            report_type: 报表类型
            mapping: 字段映射

        Returns:
            pd.DataFrame: 透视后的宽格式DataFrame
        """
        if df is None or df.empty:
            return df

        # 确定科目名称列和日期列
        item_col = "ITEM_NAME"
        date_col = "REPORT_DATE"

        # 创建标准化的科目名到字段名的映射（反向）
        item_to_field: Dict[str, str] = {}
        for orig_name, std_name in mapping.items():
            if orig_name not in ["REPORT_DATE", "SECURITY_CODE"]:
                item_to_field[orig_name] = std_name

        # 映射科目名称
        df = df.copy()
        df["_std_item_name"] = df[item_col].map(lambda x: item_to_field.get(x, x))

        # 透视数据
        pivot_df = df.pivot_table(
            index=[date_col, "SECURITY_CODE"],
            columns="_std_item_name",
            values="AMOUNT",
            aggfunc="first",
        ).reset_index()

        # 整理列名
        pivot_df.columns.name = None
        pivot_df = pivot_df.rename(
            columns={
                date_col: "report_date",
                "SECURITY_CODE": "stock_code",
            }
        )

        # 添加原始数据源标识
        pivot_df["_raw_data_source"] = self.adapter_name

        return pivot_df

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
                reason="AkShare US返回空数据",
                adapter_name=self.adapter_name,
            )

    def get_balance_sheet(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取美股资产负债表

        Args:
            stock_code: 股票代码 (如 AAPL)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的资产负债表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        # AkShare US 报告期参数: "年报" 或 "季报"
        period_str = "年报" if period == "annual" else "季报"

        try:
            df = akshare.stock_financial_us_report_em(
                stock=stock_code,
                symbol="资产负债表",
                indicator=period_str,
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
        获取美股利润表

        Args:
            stock_code: 股票代码 (如 AAPL)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的利润表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        period_str = "年报" if period == "annual" else "季报"

        try:
            df = akshare.stock_financial_us_report_em(
                stock=stock_code,
                symbol="综合损益表",
                indicator=period_str,
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
        获取美股现金流量表

        Args:
            stock_code: 股票代码 (如 AAPL)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的现金流量表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        period_str = "年报" if period == "annual" else "季报"

        try:
            df = akshare.stock_financial_us_report_em(
                stock=stock_code,
                symbol="现金流量表",
                indicator=period_str,
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
        获取美股财务指标

        Args:
            stock_code: 股票代码 (如 AAPL)
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
            df = akshare.stock_financial_us_analysis_indicator_em(symbol=stock_code)
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
