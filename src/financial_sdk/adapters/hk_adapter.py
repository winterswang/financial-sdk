"""
港股适配器

封装AkShare接口，获取港股财务数据。
"""

import importlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..base_adapter import BaseAdapter
from ..exceptions import DataNotAvailableError, InvalidStockCodeError


class HKAdapter(BaseAdapter):
    """
    港股适配器

    封装AkShare接口，获取港股财务报表和财务指标。

    支持的股票代码格式:
    - 0700.HK (腾讯控股)
    - 9988.HK (阿里巴巴)
    """

    # 港股股票代码正则: 4-5位数字 + .HK
    STOCK_CODE_PATTERN = re.compile(r"^\d{4,5}\.HK$")

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化港股适配器

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
            # AkShare HK 报表数据字段映射（长格式数据的 STD_ITEM_NAME -> 标准字段名）
            self._field_mapping = {
                "balance_sheet": {
                    "STD_REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "流动资产合计": "current_assets",
                    "非流动资产合计": "non_current_assets",
                    "总资产": "total_assets",
                    "流动负债合计": "current_liabilities",
                    "非流动负债合计": "non_current_liabilities",
                    "总负债": "total_liabilities",
                    "总权益": "total_equity",
                    "股东权益": "total_equity",
                    "净资产": "total_equity",
                    "物业厂房及设备": "fixed_assets",
                    "固定资产": "fixed_assets",
                    "在建工程": "construction_in_progress",
                    "无形资产": "intangible_assets",
                    "商誉": "goodwill",
                    "土地使用权": "land_use_rights",
                    "投资物业": "investment_properties",
                    "存货": "inventory",
                    "应收帐款": "accounts_receivable",
                    "应付帐款": "accounts_payable",
                    "短期存款": "short_term_deposits",
                    "短期贷款": "short_term_debt",
                    "长期贷款": "long_term_debt",
                    "融资租赁负债": "lease_liabilities",
                    "现金及等价物": "cash_and_equivalents",
                    "受限制存款及现金": "restricted_cash",
                    "中长期存款": "long_term_deposits",
                    "可供出售投资": "available_for_sale_investments",
                    "持有至到期投资": "held_to_maturity_investments",
                    "联营公司权益": "investments_in_associates",
                    "合营公司权益": "investments_in_joint_ventures",
                    "递延税项资产": "deferred_tax_assets",
                    "递延税项负债": "deferred_tax_liabilities",
                    "应付税项": "tax_payable",
                    "应付股利": "dividends_payable",
                    "应付关联方款项": "due_to_related_parties",
                    "应收关联方款项": "due_from_related_parties",
                    "储备": "reserves",
                    "保留溢利(累计亏损)": "retained_earnings",
                    "股本": "share_capital",
                    "股本溢价": "share_premium",
                    "少数股东权益": "minority_interests",
                },
                "income_statement": {
                    "STD_REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "营业额": "revenue",
                    "营运收入": "revenue",
                    "毛利": "gross_profit",
                    "经营溢利": "operating_profit",
                    "除税前溢利": "profit_before_tax",
                    "除税后溢利": "net_profit",
                    "税项": "tax_expense",
                    "持续经营业务税后利润": "net_profit_from_continuing_operations",
                    "股东应占溢利": "net_profit",
                    "少数股东损益": "minority_interests",
                    "应占联营公司溢利": "share_of_profit_from_associates",
                    "应占合营公司溢利": "share_of_profit_from_joint_ventures",
                    "每股基本盈利": "eps",
                    "每股摊薄盈利": "diluted_eps",
                    "每股股息": "dps",
                    "股息": "dividends",
                    "融资成本": "financing_costs",
                    "利息收入": "interest_income",
                    "利息支出": "interest_expense",
                    "其他收入": "other_income",
                    "其他收益": "other_gains",
                    "行政开支": "admin_expense",
                    "销售及分销费用": "selling_expense",
                    "营运支出": "operating_expense",
                    "全面收益总额": "total_comprehensive_income",
                    "其他全面收益": "other_comprehensive_income",
                },
                "cash_flow": {
                    "STD_REPORT_DATE": "report_date",
                    "SECURITY_CODE": "stock_code",
                    "经营业务现金净额": "operating_cash_flow",
                    "经营产生现金": "operating_cash_flow",
                    "投资业务现金净额": "investing_cash_flow",
                    "融资业务现金净额": "financing_cash_flow",
                    "融资前现金净额": "net_cash_flow_before_financing",
                    "现金净额": "net_cash_flow",
                    "期初现金": "beginning_cash",
                    "期末现金": "ending_cash",
                    "除税前溢利(业务利润)": "profit_before_tax",
                    "营运资金变动前经营溢利": "operating_profit_before_working_capital",
                    "加:折旧及摊销": "depreciation_amortization",
                    "加:减值及拨备": "impairment_provisions",
                    "加:利息支出": "interest_expense",
                    "减:利息收入": "interest_income",
                    "已付利息(经营)": "interest_paid_operating",
                    "已付利息(融资)": "interest_paid_financing",
                    "已付税项": "tax_paid",
                    "存货(增加)减少": "inventory_change",
                    "应收帐款减少": "accounts_receivable_change",
                    "应付帐款及应计费用增加(减少)": "accounts_payable_change",
                    "预付款项、按金及其他应收款项减少(增加)": "other_current_assets_change",
                    "预收账款、按金及其他应付款增加(减少)": "other_current_liabilities_change",
                    "购建固定资产": "capex",
                    "购建无形资产及其他资产": "intangible_asset_acquisition",
                    "处置固定资产": "proceeds_from_disposal_of_fixed_assets",
                    "投资支付现金": "investment_expenditure",
                    "收回投资所得现金": "proceeds_from_investment",
                    "已收利息(投资)": "interest_received_investing",
                    "已收股息(投资)": "dividends_received_investing",
                    "新增借款": "proceeds_from_borrowings",
                    "偿还借款": "repayment_of_borrowings",
                    "发行股份": "proceeds_from_issuance_of_shares",
                    "回购股份": "share_repurchase",
                    "已付股息(融资)": "dividends_paid",
                    "发行债券": "proceeds_from_bonds",
                    "赎回债券": "repayment_of_bonds",
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
                    "CURRENTDEBT_DEBT": "quick_ratio",
                    "DEBT_ASSET_RATIO": "debt_to_equity",
                    "OPERATE_INCOME": "revenue",
                    "GROSS_PROFIT": "gross_profit",
                    "BPS": "bvps",
                    "PER_OI": "pe_ratio",
                    "PER_NETCASH_OPERATE": "pb_ratio",
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
        return "akshare_hk"

    @property
    def supported_markets(self) -> List[str]:
        return ["HK"]

    @property
    def priority(self) -> int:
        return 1

    def validate_stock_code(self, stock_code: str) -> bool:
        """
        验证港股股票代码格式

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
                expected_format="4-5位数字.HK (如 0700.HK)",
                market="HK",
            )
        return True

    def _extract_stock_code(self, stock_code: str) -> str:
        """从标准格式提取 AkShare 需要的代码格式 (如 0700.HK -> 00700)"""
        return stock_code.replace(".HK", "")

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

        # 检查是否为长格式数据（包含 ITEM_NAME/STD_ITEM_NAME 和 AMOUNT 列）
        if "ITEM_NAME" in df.columns or "STD_ITEM_NAME" in df.columns:
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

        AkShare HK/US 报表返回的是长格式：
        - STD_ITEM_NAME: 标准科目名称
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
        item_col = "STD_ITEM_NAME" if "STD_ITEM_NAME" in df.columns else "ITEM_NAME"
        date_col = (
            "STD_REPORT_DATE" if "STD_REPORT_DATE" in df.columns else "REPORT_DATE"
        )

        # 创建标准化的科目名到字段名的映射（反向）
        # mapping 是 {原始科目名: 标准字段名}，我们需要反向它
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
                reason="AkShare HK返回空数据",
                adapter_name=self.adapter_name,
            )

    def get_balance_sheet(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取港股资产负债表

        Args:
            stock_code: 股票代码 (如 0700.HK)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的资产负债表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        # AkShare HK: indicator = "年度" 或 "报告期"
        indicator = "年度" if period == "annual" else "报告期"

        try:
            df = akshare.stock_financial_hk_report_em(
                stock=self._extract_stock_code(stock_code),
                symbol="资产负债表",
                indicator=indicator,
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
        获取港股利润表

        Args:
            stock_code: 股票代码 (如 0700.HK)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的利润表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        indicator = "年度" if period == "annual" else "报告期"

        try:
            df = akshare.stock_financial_hk_report_em(
                stock=self._extract_stock_code(stock_code),
                symbol="利润表",
                indicator=indicator,
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
        获取港股现金流量表

        Args:
            stock_code: 股票代码 (如 0700.HK)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的现金流量表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        indicator = "年度" if period == "annual" else "报告期"

        try:
            df = akshare.stock_financial_hk_report_em(
                stock=self._extract_stock_code(stock_code),
                symbol="现金流量表",
                indicator=indicator,
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
        获取港股财务指标

        Args:
            stock_code: 股票代码 (如 0700.HK)
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的财务指标

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        self.validate_stock_code(stock_code)
        akshare = self._get_akshare()

        # AkShare HK: indicator = "年度" 或 "报告期"
        indicator = "年度" if period == "annual" else "报告期"

        try:
            df = akshare.stock_financial_hk_analysis_indicator_em(
                symbol=self._extract_stock_code(stock_code),
                indicator=indicator,
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
