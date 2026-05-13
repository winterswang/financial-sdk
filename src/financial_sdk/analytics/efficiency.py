"""
运营效率分析器

提供基于财务报表的运营效率分析，包括营业周期和现金周转周期。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .analytics_base import BaseAnalyzer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..facade import FinancialFacade  # noqa: F401


@dataclass
class EfficiencyMetrics:
    """
    运营效率指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 周转天数指标
        dio: 存货周转天数 (Days Inventory Outstanding)
        dso: 应收账款周转天数 (Days Sales Outstanding)
        dpo: 应付账款周转天数 (Days Payable Outstanding)
        operating_cycle: 营业周期 (DIO + DSO)
        cash_conversion_cycle: 现金周转周期 (DIO + DSO - DPO)

        # 周转率指标
        inventory_turnover: 存货周转率
        receivables_turnover: 应收账款周转率
        payables_turnover: 应付账款周转率
        asset_turnover: 资产周转率

        # 计算时间
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str

    # 周转天数指标
    dio: Optional[float] = None
    dso: Optional[float] = None
    dpo: Optional[float] = None
    operating_cycle: Optional[float] = None
    cash_conversion_cycle: Optional[float] = None

    # 周转率指标
    inventory_turnover: Optional[float] = None
    receivables_turnover: Optional[float] = None
    payables_turnover: Optional[float] = None
    asset_turnover: Optional[float] = None

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "dio": self.dio,
            "dso": self.dso,
            "dpo": self.dpo,
            "operating_cycle": self.operating_cycle,
            "cash_conversion_cycle": self.cash_conversion_cycle,
            "inventory_turnover": self.inventory_turnover,
            "receivables_turnover": self.receivables_turnover,
            "payables_turnover": self.payables_turnover,
            "asset_turnover": self.asset_turnover,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_interpretation(self) -> str:
        """
        获取运营效率解读

        Returns:
            解读字符串
        """
        if self.cash_conversion_cycle is None:
            return "数据不足"

        if self.cash_conversion_cycle < 0:
            cycle_level = "优秀 (负周期意味着占用供应商资金)"
        elif self.cash_conversion_cycle < 60:
            cycle_level = "良好"
        elif self.cash_conversion_cycle < 120:
            cycle_level = "一般"
        else:
            cycle_level = "较长 (资金周转较慢)"

        return f"现金周转周期: {self.cash_conversion_cycle:.1f} 天, 水平: {cycle_level}"


class EfficiencyAnalyzer(BaseAnalyzer):
    """
    运营效率分析器

    提供运营效率分析，包括：
    - 存货周转天数 (DIO)
    - 应收账款周转天数 (DSO)
    - 应付账款周转天数 (DPO)
    - 营业周期 (DIO + DSO)
    - 现金周转周期 (DIO + DSO - DPO)
    """

    # 默认一年天数
    DEFAULT_DAYS = 360

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        super().__init__(financial_facade=financial_facade)

    @property
    def analyzer_name(self) -> str:
        return "efficiency_analyzer"

    def get_efficiency_metrics(
        self,
        stock_code: str,
        period: str = "annual",
        days: int = DEFAULT_DAYS,
        *,
        _facade_override: Any = None,
    ) -> Optional[EfficiencyMetrics]:
        """
        获取完整运营效率指标

        Args:
            stock_code: 股票代码
            period: 报告期类型
            days: 一年天数 (默认360)
            _facade_override: 内部参数，用于多年分析时传入单期 facade

        Returns:
            EfficiencyMetrics 或 None
        """
        facade = _facade_override or self._facade
        try:
            bundle = facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )
            income = bundle.income_statement
            balance = bundle.balance_sheet
        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

        if balance is None or balance.empty:
            return None

        # 获取基础财务数据
        revenue = self._get_value(income, "revenue")
        total_cost = self._get_value(income, "total_cost")
        if total_cost is None:
            operating_cost = self._get_value(income, "operating_cost")
            if operating_cost is not None:
                total_cost = operating_cost

        inventory = self._get_value(balance, "inventory")
        accounts_receivable = self._get_value(balance, "accounts_receivable")
        accounts_payable = self._get_value(balance, "accounts_payable")
        total_assets = self._get_value(balance, "total_assets")

        # 计算周转天数
        dio = self._calculator.calculate_dio(inventory, total_cost, days)
        dso = self._calculator.calculate_dso(accounts_receivable, revenue, days)
        dpo = self._calculator.calculate_dpo(accounts_payable, total_cost, days)

        operating_cycle = self._calculator.calculate_operating_cycle(dio, dso)
        cash_conversion_cycle = self._calculator.calculate_cash_conversion_cycle(
            dio, dso, dpo
        )

        # 计算周转率
        inventory_turnover = None
        if inventory and total_cost and inventory > 0:
            inventory_turnover = total_cost / inventory

        receivables_turnover = None
        if accounts_receivable and revenue and accounts_receivable > 0:
            receivables_turnover = revenue / accounts_receivable

        payables_turnover = None
        if accounts_payable and total_cost and accounts_payable > 0:
            payables_turnover = total_cost / accounts_payable

        asset_turnover = self._calculator.calculate_asset_turnover(
            revenue, total_assets
        )

        return EfficiencyMetrics(
            stock_code=stock_code,
            report_date=self._get_latest_report_date(balance),
            dio=dio,
            dso=dso,
            dpo=dpo,
            operating_cycle=operating_cycle,
            cash_conversion_cycle=cash_conversion_cycle,
            inventory_turnover=inventory_turnover,
            receivables_turnover=receivables_turnover,
            payables_turnover=payables_turnover,
            asset_turnover=asset_turnover,
            calculation_timestamp=datetime.now().isoformat(),
        )

    # 保持向后兼容的别名
    def _get_metrics_with_facade(
        self, stock_code: str, facade: Any
    ) -> Optional[EfficiencyMetrics]:
        """使用指定门面获取运营效率指标（用于多年分析）"""
        return self.get_efficiency_metrics(
            stock_code, period="annual", _facade_override=facade
        )

    def get_dio(self, stock_code: str, period: str = "annual") -> Optional[float]:
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dio if metrics else None

    def get_dso(self, stock_code: str, period: str = "annual") -> Optional[float]:
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dso if metrics else None

    def get_dpo(self, stock_code: str, period: str = "annual") -> Optional[float]:
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dpo if metrics else None

    def get_operating_cycle(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.operating_cycle if metrics else None

    def get_cash_conversion_cycle(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.cash_conversion_cycle if metrics else None

    def health_check(self) -> Dict[str, Any]:
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
