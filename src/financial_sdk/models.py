"""
财务SDK数据模型

定义FinancialBundle、HealthStatus、ValidationResult等核心数据结构，
以及四个报表的标准字段常量。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd


# ============== 标准字段常量 ==============

# 资产负债表标准字段
BALANCE_SHEET_STANDARD_FIELDS: Set[str] = {
    "report_date",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "current_assets",
    "non_current_assets",
    "current_liabilities",
    "non_current_liabilities",
    "fixed_assets",
    "intangible_assets",
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "short_term_debt",
    "long_term_debt",
    "_raw_data_source",
    "_raw_field_names",
}

# 利润表标准字段
INCOME_STATEMENT_STANDARD_FIELDS: Set[str] = {
    "report_date",
    "revenue",
    "total_cost",
    "gross_profit",
    "operating_profit",
    "profit_before_tax",
    "net_profit",
    "eps",
    "operating_cost",
    "selling_expense",
    "admin_expense",
    "financial_expense",
    "rd_expense",
    "tax_expense",
    "_raw_data_source",
    "_raw_field_names",
}

# 现金流量表标准字段
CASH_FLOW_STANDARD_FIELDS: Set[str] = {
    "report_date",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "net_cash_flow",
    "beginning_cash",
    "ending_cash",
    "cfo_to_revenue",
    "capex",
    "_raw_data_source",
    "_raw_field_names",
}

# 财务指标标准字段
INDICATORS_STANDARD_FIELDS: Set[str] = {
    "report_date",
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_equity",
    "debt_to_assets",
    "asset_turnover",
    "inventory_turnover",
    "receivables_turnover",
    "eps",
    "bvps",
    "pe_ratio",
    "pb_ratio",
    "_raw_data_source",
    "_raw_field_names",
}

# 必需字段（用于验证）
BALANCE_SHEET_REQUIRED_FIELDS: Set[str] = {
    "report_date",
    "total_assets",
    "total_liabilities",
    "total_equity",
}

INCOME_STATEMENT_REQUIRED_FIELDS: Set[str] = {
    "report_date",
    "revenue",
    "total_cost",
    "gross_profit",
    "operating_profit",
    "profit_before_tax",
    "net_profit",
}

CASH_FLOW_REQUIRED_FIELDS: Set[str] = {
    "report_date",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "net_cash_flow",
}

INDICATORS_REQUIRED_FIELDS: Set[str] = {
    "report_date",
    "roe",
    "gross_margin",
    "net_margin",
    "eps",
}

# 报表类型到必需字段的映射
REPORT_TYPE_REQUIRED_FIELDS: Dict[str, Set[str]] = {
    "balance_sheet": BALANCE_SHEET_REQUIRED_FIELDS,
    "income_statement": INCOME_STATEMENT_REQUIRED_FIELDS,
    "cash_flow": CASH_FLOW_REQUIRED_FIELDS,
    "indicators": INDICATORS_REQUIRED_FIELDS,
}


# ============== 数据类定义 ==============


@dataclass
class ValidationResult:
    """数据验证结果"""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid

    def add_error(self, error: str) -> None:
        """添加错误信息"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """添加警告信息"""
        self.warnings.append(warning)


@dataclass
class HealthStatus:
    """健康状态数据类"""

    # 总体状态: "healthy", "degraded", "unhealthy"
    status: str = "unknown"

    # 各适配器状态详情
    adapters: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 缓存统计
    cache_stats: Dict[str, Any] = field(default_factory=dict)

    # 监控指标
    metrics: Dict[str, Any] = field(default_factory=dict)

    # 检查时间戳
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def is_healthy(self) -> bool:
        """检查是否健康"""
        return self.status == "healthy"

    def get_failed_adapters(self) -> List[str]:
        """获取失败的适配器列表"""
        return [
            name
            for name, info in self.adapters.items()
            if info.get("status") != "healthy"
        ]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "status": self.status,
            "adapters": self.adapters,
            "cache_stats": self.cache_stats,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
        }


@dataclass
class FinancialBundle:
    """
    标准化财务数据包

    这是SDK的核心数据结构，封装了股票财务数据的完整信息

    Attributes:
        stock_code: 股票代码（标准化格式，如600000.SH、AAPL）
        stock_name: 股票名称
        market: 市场标识 ("A", "HK", "US")
        currency: 货币单位 (CNY, HKD, USD)

        balance_sheet: 资产负债表DataFrame
        income_statement: 利润表DataFrame
        cash_flow: 现金流量表DataFrame
        indicators: 财务指标DataFrame

        is_partial: 是否为部分数据（某些报表获取失败）
        warnings: 警告信息列表
        report_periods: 报告期列表

        _raw_data_source: 原始数据源标识
        _raw_field_names: 原始字段名映射
    """

    # === 元数据 ===
    stock_code: str
    stock_name: str = ""
    market: str = ""
    currency: str = "CNY"

    # === 报表数据 ===
    balance_sheet: Optional[pd.DataFrame] = None
    income_statement: Optional[pd.DataFrame] = None
    cash_flow: Optional[pd.DataFrame] = None
    indicators: Optional[pd.DataFrame] = None

    # === 数据质量标识 ===
    is_partial: bool = False
    warnings: List[str] = field(default_factory=list)
    report_periods: List[str] = field(default_factory=list)

    # === 原始数据追溯 ===
    _raw_data_source: Optional[str] = None
    _raw_field_names: Optional[Dict[str, Dict[str, str]]] = field(default=None)

    # === 时间戳 ===
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_period: str = "annual"  # "annual" or "quarterly"

    def __post_init__(self) -> None:
        if self._raw_field_names is None:
            self._raw_field_names = {}
        self._update_report_periods()

    def _update_report_periods(self) -> None:
        """从各报表中提取报告期列表"""
        periods: Set[str] = set()
        for df in [
            self.balance_sheet,
            self.income_statement,
            self.cash_flow,
            self.indicators,
        ]:
            if df is not None and not df.empty:
                if "report_date" in df.columns:
                    periods.update(df["report_date"].astype(str).tolist())
        self.report_periods = sorted(list(periods))

    def get_report(self, report_type: str) -> Optional[pd.DataFrame]:
        """
        获取指定类型的报表

        Args:
            report_type: 报表类型
                - "balance_sheet" 或 "balance"
                - "income_statement" 或 "income"
                - "cash_flow" 或 "cash"
                - "indicators" 或 "indicator"

        Returns:
            pd.DataFrame: 指定类型的报表，None表示未获取

        Raises:
            ValueError: report_type无效时抛出
        """
        report_map = {
            "balance_sheet": self.balance_sheet,
            "balance": self.balance_sheet,
            "income_statement": self.income_statement,
            "income": self.income_statement,
            "cash_flow": self.cash_flow,
            "cash": self.cash_flow,
            "indicators": self.indicators,
            "indicator": self.indicators,
        }

        result = report_map.get(report_type)
        if result is None:
            raise ValueError(f"Invalid report_type: {report_type}")
        return result

    def get_available_reports(self) -> List[str]:
        """
        获取已获取的报表类型列表

        Returns:
            List[str]: 可用报表类型列表
        """
        reports = []
        if self.balance_sheet is not None:
            reports.append("balance_sheet")
        if self.income_statement is not None:
            reports.append("income_statement")
        if self.cash_flow is not None:
            reports.append("cash_flow")
        if self.indicators is not None:
            reports.append("indicators")
        return reports

    def validate(self) -> ValidationResult:
        """
        验证数据完整性

        Returns:
            ValidationResult: 验证结果
        """
        result = ValidationResult(is_valid=True)

        # 检查元数据
        if not self.stock_code:
            result.add_error("stock_code不能为空")

        if not self.market:
            result.add_warning("market未设置")

        # 检查至少有一个报表
        if not any(
            df is not None
            for df in [
                self.balance_sheet,
                self.income_statement,
                self.cash_flow,
                self.indicators,
            ]
        ):
            result.add_error("没有任何报表数据")

        # 验证各报表的数据质量
        self._validate_report(
            "balance_sheet", self.balance_sheet, BALANCE_SHEET_REQUIRED_FIELDS, result
        )
        self._validate_report(
            "income_statement",
            self.income_statement,
            INCOME_STATEMENT_REQUIRED_FIELDS,
            result,
        )
        self._validate_report(
            "cash_flow", self.cash_flow, CASH_FLOW_REQUIRED_FIELDS, result
        )
        self._validate_report(
            "indicators", self.indicators, INDICATORS_REQUIRED_FIELDS, result
        )

        return result

    def _validate_report(
        self,
        report_type: str,
        df: Optional[pd.DataFrame],
        required_fields: Set[str],
        result: ValidationResult,
    ) -> None:
        """验证单个报表的数据质量"""
        if df is None:
            return

        if df.empty:
            result.add_warning(f"{report_type}为空DataFrame")
            return

        # 检查必需字段
        missing_fields = required_fields - set(df.columns)
        if missing_fields:
            result.add_warning(f"{report_type}缺少必需字段: {missing_fields}")

        # 检查日期格式
        if "report_date" in df.columns:
            invalid_dates = 0
            for val in df["report_date"].head():
                if not self._is_valid_date_format(val):
                    invalid_dates += 1
            if invalid_dates > 0:
                result.add_warning(f"{report_type}存在无效日期格式")

    @staticmethod
    def _is_valid_date_format(val: Any) -> bool:
        """检查是否为有效的日期格式"""
        if val is None:
            return False
        val_str = str(val)
        # 支持的格式: YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD
        if len(val_str) == 10 and ("-" in val_str or "/" in val_str):
            return True
        if len(val_str) == 8 and val_str.isdigit():
            return True
        return False

    def add_warning(self, warning: str) -> None:
        """
        添加警告信息

        Args:
            warning: 警告信息
        """
        self.warnings.append(warning)
        self.is_partial = True
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            Dict: 字典表示
        """
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "market": self.market,
            "currency": self.currency,
            "is_partial": self.is_partial,
            "warnings": self.warnings,
            "report_periods": self.report_periods,
            "available_reports": self.get_available_reports(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"FinancialBundle("
            f"stock_code={self.stock_code}, "
            f"market={self.market}, "
            f"reports={self.get_available_reports()}, "
            f"is_partial={self.is_partial})"
        )
