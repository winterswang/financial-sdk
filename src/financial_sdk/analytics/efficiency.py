"""
运营效率分析器

提供基于财务报表的运营效率分析，包括营业周期和现金周转周期。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .analytics_base import BaseAnalyzer


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

    使用示例:
        analyzer = EfficiencyAnalyzer()

        # 获取完整运营效率分析
        metrics = analyzer.get_efficiency_metrics("600000.SH")
        print(f"存货周转天数: {metrics.dio}")
        print(f"现金周转周期: {metrics.cash_conversion_cycle}")

        # 单独获取某个指标
        ccc = analyzer.get_cash_conversion_cycle("600000.SH")
    """

    # 默认一年天数
    DEFAULT_DAYS = 360

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        """
        初始化运营效率分析器

        Args:
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)

    @property
    def analyzer_name(self) -> str:
        return "efficiency_analyzer"

    def get_efficiency_metrics(
        self, stock_code: str, period: str = "annual", days: int = DEFAULT_DAYS
    ) -> Optional[EfficiencyMetrics]:
        """
        获取完整运营效率指标

        Args:
            stock_code: 股票代码
            period: 报告期类型
            days: 一年天数 (默认360)

        Returns:
            EfficiencyMetrics 或 None
        """
        fs_data = self._get_financial_data(stock_code, period)
        income = fs_data["income_statement"]
        balance = fs_data["balance_sheet"]

        if balance is None or balance.empty:
            return None

        # 获取基础财务数据
        # 营业收入 (用于 DSO)
        revenue = self._get_value(income, "revenue")

        # 营业成本/销售成本 (用于 DIO, DPO)
        total_cost = self._get_value(income, "total_cost")
        if total_cost is None:
            # 尝试从利润表获取
            operating_cost = self._get_value(income, "operating_cost")
            if operating_cost is not None:
                total_cost = operating_cost

        # 存货
        inventory = self._get_value(balance, "inventory")

        # 应收账款
        accounts_receivable = self._get_value(balance, "accounts_receivable")

        # 应付账款
        accounts_payable = self._get_value(balance, "accounts_payable")

        # 总资产 (用于资产周转率)
        total_assets = self._get_value(balance, "total_assets")

        # 计算周转天数
        dio = self._calculator.calculate_dio(inventory, total_cost, days)
        dso = self._calculator.calculate_dso(accounts_receivable, revenue, days)
        dpo = self._calculator.calculate_dpo(accounts_payable, total_cost, days)

        # 计算周期
        operating_cycle = self._calculator.calculate_operating_cycle(dio, dso)
        cash_conversion_cycle = self._calculator.calculate_cash_conversion_cycle(
            dio, dso, dpo
        )

        # 计算周转率
        inventory_turnover = None
        if inventory and total_cost:
            inventory_turnover = total_cost / inventory if inventory > 0 else None

        receivables_turnover = None
        if accounts_receivable and revenue:
            receivables_turnover = (
                revenue / accounts_receivable if accounts_receivable > 0 else None
            )

        payables_turnover = None
        if accounts_payable and total_cost:
            payables_turnover = (
                total_cost / accounts_payable if accounts_payable > 0 else None
            )

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

    def get_dio(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取存货周转天数

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            DIO 或 None
        """
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dio if metrics else None

    def get_dso(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取应收账款周转天数

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            DSO 或 None
        """
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dso if metrics else None

    def get_dpo(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取应付账款周转天数

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            DPO 或 None
        """
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.dpo if metrics else None

    def get_operating_cycle(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取营业周期

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            营业周期或 None
        """
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.operating_cycle if metrics else None

    def get_cash_conversion_cycle(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取现金周转周期

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            现金周转周期或 None
        """
        metrics = self.get_efficiency_metrics(stock_code, period)
        return metrics.cash_conversion_cycle if metrics else None

    def _get_metrics_with_facade(
        self, stock_code: str, facade: Any
    ) -> Optional[EfficiencyMetrics]:
        """使用指定门面获取运营效率指标（用于多年分析）"""
        try:
            bundle = facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period="annual",
            )

            income = bundle.income_statement
            balance = bundle.balance_sheet

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
            dio = self._calculator.calculate_dio(inventory, total_cost, self.DEFAULT_DAYS)
            dso = self._calculator.calculate_dso(accounts_receivable, revenue, self.DEFAULT_DAYS)
            dpo = self._calculator.calculate_dpo(accounts_payable, total_cost, self.DEFAULT_DAYS)
            operating_cycle = self._calculator.calculate_operating_cycle(dio, dso)
            cash_conversion_cycle = self._calculator.calculate_cash_conversion_cycle(
                dio, dso, dpo
            )

            # 计算周转率
            inventory_turnover = None
            if inventory and total_cost:
                inventory_turnover = total_cost / inventory if inventory > 0 else None

            receivables_turnover = None
            if accounts_receivable and revenue:
                receivables_turnover = revenue / accounts_receivable if accounts_receivable > 0 else None

            payables_turnover = None
            if accounts_payable and total_cost:
                payables_turnover = total_cost / accounts_payable if accounts_payable > 0 else None

            asset_turnover = self._calculator.calculate_asset_turnover(revenue, total_assets)

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
        except Exception:
            return None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
