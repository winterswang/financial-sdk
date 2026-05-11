"""
盈利能力分析器

提供基于财务报表的盈利能力分析，包括 DuPont 分解和 ROIC。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .analytics_base import BaseAnalyzer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..facade import FinancialFacade  # noqa: F401


@dataclass
class ProfitabilityMetrics:
    """
    盈利能力指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 基础指标
        gross_profit: 毛利
        gross_margin: 毛利率
        operating_profit: 营业利润
        operating_margin: 营业利润率
        net_profit: 净利润
        net_margin: 净利率

        # 回报率指标
        roe: 股东权益回报率
        roa: 资产回报率
        roic: 投资资本回报率

        # DuPont 分解
        dupont_net_margin: 净利率 (DuPont)
        dupont_asset_turnover: 资产周转率 (DuPont)
        dupont_equity_multiplier: 权益乘数 (DuPont)
        dupont_roe: ROE (DuPont 计算)

        # 计算时间
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str

    # 基础指标
    gross_profit: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_profit: Optional[float] = None
    operating_margin: Optional[float] = None
    net_profit: Optional[float] = None
    net_margin: Optional[float] = None

    # 回报率指标
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None

    # DuPont 分解
    dupont_net_margin: Optional[float] = None
    dupont_asset_turnover: Optional[float] = None
    dupont_equity_multiplier: Optional[float] = None
    dupont_roe: Optional[float] = None

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "gross_profit": self.gross_profit,
            "gross_margin": self.gross_margin,
            "operating_profit": self.operating_profit,
            "operating_margin": self.operating_margin,
            "net_profit": self.net_profit,
            "net_margin": self.net_margin,
            "roe": self.roe,
            "roa": self.roa,
            "roic": self.roic,
            "dupont_net_margin": self.dupont_net_margin,
            "dupont_asset_turnover": self.dupont_asset_turnover,
            "dupont_equity_multiplier": self.dupont_equity_multiplier,
            "dupont_roe": self.dupont_roe,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_interpretation(self) -> str:
        """
        获取盈利能力解读

        Returns:
            解读字符串
        """
        if self.roe is None:
            return "数据不足"

        if self.roe > 0.20:
            roe_level = "优秀"
        elif self.roe > 0.10:
            roe_level = "良好"
        elif self.roe > 0.05:
            roe_level = "一般"
        else:
            roe_level = "较差"

        if self.net_margin is None:
            margin_level = "数据不足"
        elif self.net_margin > 0.20:
            margin_level = "优秀"
        elif self.net_margin > 0.10:
            margin_level = "良好"
        elif self.net_margin > 0.05:
            margin_level = "一般"
        else:
            margin_level = "较差"

        return f"ROE水平: {roe_level}, 净利率水平: {margin_level}"


class ProfitabilityAnalyzer(BaseAnalyzer):
    """
    盈利能力分析器

    提供盈利能力分析，包括：
    - 毛利率、营业利润率、净利率
    - ROE、ROA、ROIC
    - DuPont 分解

    使用示例:
        analyzer = ProfitabilityAnalyzer()

        # 获取完整盈利能力分析
        metrics = analyzer.get_profitability_metrics("600000.SH")
        print(f"ROE: {metrics.roe}")
        print(f"毛利率: {metrics.gross_margin}")

        # DuPont 分解
        dupont = analyzer.get_dupont_analysis("600000.SH")
        print(f"净利率: {dupont['net_margin']}")
        print(f"资产周转率: {dupont['asset_turnover']}")
        print(f"权益乘数: {dupont['equity_multiplier']}")
        print(f"ROE: {dupont['roe']}")
    """

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        """
        初始化盈利能力分析器

        Args:
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)

    @property
    def analyzer_name(self) -> str:
        return "profitability_analyzer"

    def get_profitability_metrics(
        self, stock_code: str, period: str = "annual", *, _facade_override: Any = None
    ) -> Optional[ProfitabilityMetrics]:
        """
        获取完整盈利能力指标

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            ProfitabilityMetrics 或 None
        """
        if _facade_override:
            try:
                bundle = _facade_override.get_financial_data(
                    stock_code=stock_code, report_type="all", period=period
                )
                fs_data = {
                    "income_statement": bundle.income_statement,
                    "balance_sheet": bundle.balance_sheet,
                    "cash_flow": bundle.cash_flow,
                    "indicators": bundle.indicators,
                }
            except Exception:
                return None
        else:
            fs_data = self._get_financial_data(stock_code, period)
        income = fs_data["income_statement"]
        balance = fs_data["balance_sheet"]

        if income is None or income.empty:
            return None

        # 获取基础财务数据
        revenue = self._get_value(income, "revenue")
        gross_profit = self._get_value(income, "gross_profit")
        operating_profit = self._get_value(income, "operating_profit")
        net_profit = self._get_value(income, "net_profit")
        total_assets = self._get_value(balance, "total_assets")
        total_equity = self._get_value(balance, "total_equity")
        total_liabilities = self._get_value(balance, "total_liabilities")
        cash = self._get_value(balance, "cash_and_equivalents")
        if cash is None:
            cash = self._get_value(balance, "cash_and_short_term_deposits")

        # 利息费用 (用于 ROIC)
        interest_expense = self._get_value(income, "interest_expense")
        if interest_expense is None:
            interest_expense = self._get_value(income, "financing_costs")

        # 计算基础利润率
        gross_margin = self._calculator.calculate_gross_margin(gross_profit, revenue)
        operating_margin = self._calculator.calculate_operating_profit_margin(
            operating_profit, revenue
        )
        net_margin = self._calculator.calculate_net_margin(net_profit, revenue)

        # 计算回报率
        roe = self._calculator.calculate_dupont_roe(net_profit, total_equity)
        roa = self._calculator.calculate_dupont_roa(net_profit, total_assets)

        # ROIC 计算 (需要 EBIT)
        roic = None
        if operating_profit is not None:
            tax_rate = 0.25  # 默认税率
            if net_profit is not None and revenue is not None and revenue > 0:
                # 估算税率: 税率 = 税费 / 税前利润
                tax_expense = self._get_value(income, "tax_expense")
                profit_before_tax = self._get_value(income, "profit_before_tax")
                if tax_expense and profit_before_tax and profit_before_tax > 0:
                    tax_rate = min(tax_expense / profit_before_tax, 0.50)

            # ROIC 计算: 需要找到带息债务 (interest-bearing debt)
            # 不使用 total_liabilities，因为其中包含应付账款等非带息负债
            interest_bearing_debt = None

            # 优先尝试获取带息债务字段
            for debt_field in [
                "long_term_debt",
                "short_term_debt",
                "bonds_payable",
                "lease_liabilities",
                "capital_lease",
                "long_term_borrowings",
                "short_term_borrowings",
            ]:
                val = self._get_value(balance, debt_field)
                if val is not None and val > 0:
                    if interest_bearing_debt is None:
                        interest_bearing_debt = 0
                    interest_bearing_debt += val

            # 如果没有找到带息债务，尝试heuristic:
            # 对于科技/互联网公司，债务通常很少，可以用 total_liabilities 作为近似
            # 但要排除主要的非带息负债类别 (accounts_payable, customer_deposits, deferred_revenue)
            if interest_bearing_debt is None and total_liabilities is not None:
                # 估算: 总负债 - 主要非带息负债
                accounts_payable = self._get_value(balance, "accounts_payable") or 0
                customer_deposits = 0
                for field in [
                    "customer_deposits",
                    "customer_deposits_and_placements",
                    "客户存款及垫款",
                ]:
                    val = self._get_value(balance, field)
                    if val:
                        customer_deposits = val
                        break
                deferred_revenue = 0
                for field in [
                    "deferred_revenue",
                    "advance_from_customers",
                    "预收及预提费用",
                ]:
                    val = self._get_value(balance, field)
                    if val:
                        deferred_revenue = val
                        break

                interest_bearing_debt = max(
                    0,
                    total_liabilities
                    - accounts_payable
                    - customer_deposits
                    - deferred_revenue,
                )

            roic = self._calculator.calculate_roic(
                ebit=operating_profit,
                tax_rate=tax_rate,
                total_debt=interest_bearing_debt if interest_bearing_debt else 0,
                cash=cash,
                total_equity=total_equity,
            )

        # DuPont 分解
        dupont = self._calculator.calculate_dupont_decomposition(
            net_profit=net_profit,
            revenue=revenue,
            total_assets=total_assets,
            total_equity=total_equity,
        )

        return ProfitabilityMetrics(
            stock_code=stock_code,
            report_date=self._get_latest_report_date(income),
            gross_profit=gross_profit,
            gross_margin=gross_margin,
            operating_profit=operating_profit,
            operating_margin=operating_margin,
            net_profit=net_profit,
            net_margin=net_margin,
            roe=roe,
            roa=roa,
            roic=roic,
            dupont_net_margin=dupont.get("net_margin") if dupont else None,
            dupont_asset_turnover=dupont.get("asset_turnover") if dupont else None,
            dupont_equity_multiplier=dupont.get("equity_multiplier")
            if dupont
            else None,
            dupont_roe=dupont.get("roe") if dupont else None,
            calculation_timestamp=datetime.now().isoformat(),
        )

    def get_dupont_analysis(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[Dict[str, float]]:
        """
        获取 DuPont 分解结果

        ROE = 净利率 × 资产周转率 × 权益乘数

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            Dict 包含 net_margin, asset_turnover, equity_multiplier, roe
        """
        metrics = self.get_profitability_metrics(stock_code, period)
        if metrics is None:
            return None

        if metrics.dupont_roe is None:
            return None

        return {
            "net_margin": metrics.dupont_net_margin,
            "asset_turnover": metrics.dupont_asset_turnover,
            "equity_multiplier": metrics.dupont_equity_multiplier,
            "roe": metrics.dupont_roe,
        }

    def get_roe(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取 ROE

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            ROE 或 None
        """
        metrics = self.get_profitability_metrics(stock_code, period)
        return metrics.roe if metrics else None

    def get_roic(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取 ROIC

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            ROIC 或 None
        """
        metrics = self.get_profitability_metrics(stock_code, period)
        return metrics.roic if metrics else None

    def get_gross_margin(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取毛利率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            毛利率或 None
        """
        metrics = self.get_profitability_metrics(stock_code, period)
        return metrics.gross_margin if metrics else None

    def get_net_margin(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取净利率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            净利率或 None
        """
        metrics = self.get_profitability_metrics(stock_code, period)
        return metrics.net_margin if metrics else None

    def _get_metrics_with_facade(
        self, stock_code: str, facade: Any
    ) -> Optional[ProfitabilityMetrics]:
        """使用指定门获取盈利能力指标（用于多年分析）"""
        try:
            bundle = facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period="annual",
            )

            income = bundle.income_statement
            balance = bundle.balance_sheet

            if income is None or income.empty:
                return None

            # 获取基础财务数据
            revenue = self._get_value(income, "revenue")
            gross_profit = self._get_value(income, "gross_profit")
            operating_profit = self._get_value(income, "operating_profit")
            net_profit = self._get_value(income, "net_profit")
            total_assets = self._get_value(balance, "total_assets")
            total_equity = self._get_value(balance, "total_equity")
            total_liabilities = self._get_value(balance, "total_liabilities")
            cash = self._get_value(balance, "cash_and_equivalents")
            if cash is None:
                cash = self._get_value(balance, "cash_and_short_term_deposits")

            # 计算基础利润率
            gross_margin = self._calculator.calculate_gross_margin(
                gross_profit, revenue
            )
            operating_margin = self._calculator.calculate_operating_profit_margin(
                operating_profit, revenue
            )
            net_margin = self._calculator.calculate_net_margin(net_profit, revenue)

            # 计算回报率
            roe = self._calculator.calculate_dupont_roe(net_profit, total_equity)
            roa = self._calculator.calculate_dupont_roa(net_profit, total_assets)

            # ROIC 计算: 需要找到带息债务 (interest-bearing debt)
            # 不使用 total_liabilities，因为其中包含应付账款等非带息负债
            interest_bearing_debt = None
            for debt_field in [
                "long_term_debt",
                "short_term_debt",
                "bonds_payable",
                "lease_liabilities",
                "capital_lease",
                "long_term_borrowings",
                "short_term_borrowings",
            ]:
                val = self._get_value(balance, debt_field)
                if val is not None and val > 0:
                    if interest_bearing_debt is None:
                        interest_bearing_debt = 0
                    interest_bearing_debt += val

            # 也尝试中文字段名
            for debt_field in [
                "资本租赁债务(流动)",
                "资本租赁债务(非流动)",
            ]:
                val = self._get_value(balance, debt_field)
                if val is not None and val > 0:
                    if interest_bearing_debt is None:
                        interest_bearing_debt = 0
                    interest_bearing_debt += val

            # 如果没有找到带息债务，尝试heuristic
            if interest_bearing_debt is None and total_liabilities is not None:
                accounts_payable = self._get_value(balance, "accounts_payable") or 0
                customer_deposits = 0
                for field in [
                    "customer_deposits",
                    "customer_deposits_and_placements",
                    "客户存款及垫款",
                ]:
                    val = self._get_value(balance, field)
                    if val:
                        customer_deposits = val
                        break
                deferred_revenue = 0
                for field in [
                    "deferred_revenue",
                    "advance_from_customers",
                    "预收及预提费用",
                ]:
                    val = self._get_value(balance, field)
                    if val:
                        deferred_revenue = val
                        break
                interest_bearing_debt = max(
                    0,
                    total_liabilities
                    - accounts_payable
                    - customer_deposits
                    - deferred_revenue,
                )

            if cash is None:
                cash = self._get_value(balance, "cash_and_short_term_deposits")

            tax_rate = 0.25  # 默认税率
            if net_profit is not None and revenue is not None and revenue > 0:
                tax_expense = self._get_value(income, "tax_expense")
                profit_before_tax = self._get_value(income, "profit_before_tax")
                if tax_expense and profit_before_tax and profit_before_tax > 0:
                    tax_rate = min(tax_expense / profit_before_tax, 0.50)

            roic = self._calculator.calculate_roic(
                ebit=operating_profit,
                tax_rate=tax_rate,
                total_debt=interest_bearing_debt if interest_bearing_debt else 0,
                cash=cash,
                total_equity=total_equity,
            )

            # DuPont 分解
            dupont = self._calculator.calculate_dupont_decomposition(
                net_profit=net_profit,
                revenue=revenue,
                total_assets=total_assets,
                total_equity=total_equity,
            )

            return ProfitabilityMetrics(
                stock_code=stock_code,
                report_date=self._get_latest_report_date(income),
                gross_profit=gross_profit,
                gross_margin=gross_margin,
                operating_profit=operating_profit,
                operating_margin=operating_margin,
                net_profit=net_profit,
                net_margin=net_margin,
                roe=roe,
                roa=roa,
                roic=roic,
                dupont_net_margin=dupont.get("net_margin") if dupont else None,
                dupont_asset_turnover=dupont.get("asset_turnover") if dupont else None,
                dupont_equity_multiplier=dupont.get("equity_multiplier")
                if dupont
                else None,
                dupont_roe=dupont.get("roe") if dupont else None,
                calculation_timestamp=datetime.now().isoformat(),
            )
        except Exception:
            return None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
