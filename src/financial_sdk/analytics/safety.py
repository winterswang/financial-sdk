"""
财务安全分析器

提供基于财务报表的财务安全分析，包括 Altman Z-Score、利息保障倍数等。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from .analytics_base import BaseAnalyzer
from ..facade import FinancialFacade
from ..price import PriceProvider, get_price_provider
from .metrics_calculator import MetricsCalculator


@dataclass
class SafetyMetrics:
    """
    财务安全指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 流动性指标
        current_ratio: 流动比率
        quick_ratio: 速动比率
        cash_ratio: 现金比率

        # 偿债能力
        debt_to_equity: 资产负债率 (Debt/Equity)
        debt_to_assets: 负债资产比
        interest_coverage: 利息保障倍数

        # Altman Z-Score
        altman_z_score: Altman Z-Score
        altman_z_interpretation: Z-Score 解读

        # 资本结构
        equity_ratio: 股东权益比率
        debt_ratio: 债务比率

        # 计算时间
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str

    # 流动性指标
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    cash_ratio: Optional[float] = None

    # 偿债能力
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None

    # Altman Z-Score
    altman_z_score: Optional[float] = None
    altman_z_interpretation: str = ""

    # 资本结构
    equity_ratio: Optional[float] = None
    debt_ratio: Optional[float] = None

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "current_ratio": self.current_ratio,
            "quick_ratio": self.quick_ratio,
            "cash_ratio": self.cash_ratio,
            "debt_to_equity": self.debt_to_equity,
            "debt_to_assets": self.debt_to_assets,
            "interest_coverage": self.interest_coverage,
            "altman_z_score": self.altman_z_score,
            "altman_z_interpretation": self.altman_z_interpretation,
            "equity_ratio": self.equity_ratio,
            "debt_ratio": self.debt_ratio,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_overall_assessment(self) -> str:
        """
        获取综合财务安全评估

        Returns:
            评估字符串
        """
        if self.altman_z_score is None:
            z_assessment = "数据不足"
        elif self.altman_z_score > 2.99:
            z_assessment = "财务状况安全"
        elif self.altman_z_score > 1.81:
            z_assessment = "财务状况一般 (灰色区域)"
        else:
            z_assessment = "财务状况危险"

        if self.interest_coverage is None:
            ic_assessment = "利息保障: 数据不足"
        elif self.interest_coverage > 5:
            ic_assessment = "利息保障充足"
        elif self.interest_coverage > 3:
            ic_assessment = "利息保障适中"
        elif self.interest_coverage > 1:
            ic_assessment = "利息保障不足"
        else:
            ic_assessment = "利息保障严重不足"

        return f"{z_assessment}, {ic_assessment}"


class SafetyAnalyzer(BaseAnalyzer):
    """
    财务安全分析器

    提供财务安全分析，包括：
    - 流动性指标 (流动比率、速动比率、现金比率)
    - 偿债能力 (资产负债率、利息保障倍数)
    - Altman Z-Score
    - 资本结构

    使用示例:
        analyzer = SafetyAnalyzer()

        # 获取完整财务安全分析
        metrics = analyzer.get_safety_metrics("600000.SH")
        print(f"流动比率: {metrics.current_ratio}")
        print(f"Altman Z-Score: {metrics.altman_z_score}")
        print(f"评估: {metrics.get_overall_assessment()}")
    """

    def __init__(
        self,
        financial_facade: Optional[FinancialFacade] = None,
        price_provider: Optional[PriceProvider] = None,
    ) -> None:
        """
        初始化财务安全分析器

        Args:
            financial_facade: 财务门面实例
            price_provider: 价格提供者实例
        """
        self._facade = financial_facade or FinancialFacade()
        self._price_provider = price_provider or get_price_provider()
        self._calculator = MetricsCalculator()

    @property
    def analyzer_name(self) -> str:
        return "safety_analyzer"

    def _get_financial_data(
        self, stock_code: str, period: str = "annual"
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """获取财务报表数据"""
        try:
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )
            return {
                "income_statement": bundle.income_statement,
                "balance_sheet": bundle.balance_sheet,
                "cash_flow": bundle.cash_flow,
                "indicators": bundle.indicators,
            }
        except Exception:
            return {
                "income_statement": None,
                "balance_sheet": None,
                "cash_flow": None,
                "indicators": None,
            }

    def _get_value(self, df: Optional[pd.DataFrame], field: str) -> Optional[float]:
        """从 DataFrame 获取最新值"""
        return self._calculator.get_latest_value(df, field)

    def _get_latest_report_date(self, df: Optional[pd.DataFrame]) -> str:
        """获取最新报告日期"""
        if df is None or df.empty:
            return datetime.now().strftime("%Y-%m-%d")
        if "report_date" not in df.columns:
            return datetime.now().strftime("%Y-%m-%d")
        dates = df["report_date"].dropna()
        if dates.empty:
            return datetime.now().strftime("%Y-%m-%d")
        return str(dates.iloc[-1])

    def get_safety_metrics(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[SafetyMetrics]:
        """
        获取完整财务安全指标

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            SafetyMetrics 或 None
        """
        fs_data = self._get_financial_data(stock_code, period)
        income = fs_data["income_statement"]
        balance = fs_data["balance_sheet"]

        if balance is None or balance.empty:
            return None

        # 获取基础财务数据
        # 流动资产/负债
        current_assets = self._get_value(balance, "current_assets")
        current_liabilities = self._get_value(balance, "current_liabilities")

        # 存货
        inventory = self._get_value(balance, "inventory")

        # 现金及等价物
        cash = self._get_value(balance, "cash_and_equivalents")

        # 负债和权益
        total_liabilities = self._get_value(balance, "total_liabilities")
        total_equity = self._get_value(balance, "total_equity")
        total_assets = self._get_value(balance, "total_assets")

        # 利润数据
        operating_profit = self._get_value(income, "operating_profit")
        net_profit = self._get_value(income, "net_profit")

        # 利息支出
        interest_expense = self._get_value(income, "interest_expense")
        if interest_expense is None:
            interest_expense = self._get_value(income, "financing_costs")

        # 营运资本
        working_capital = None
        if current_assets is not None and current_liabilities is not None:
            working_capital = current_assets - current_liabilities

        # 计算流动性指标
        current_ratio = self._calculator.calculate_current_ratio(
            current_assets, current_liabilities
        )
        quick_ratio = self._calculator.calculate_quick_ratio(
            current_assets, inventory, current_liabilities
        )
        cash_ratio = None
        if (
            cash is not None
            and current_liabilities is not None
            and current_liabilities > 0
        ):
            cash_ratio = cash / current_liabilities

        # 计算偿债能力
        debt_to_equity = self._calculator.calculate_debt_to_equity(
            total_liabilities, total_equity
        )
        debt_to_assets = self._calculator.calculate_debt_to_assets(
            total_liabilities, total_assets
        )
        interest_coverage = self._calculator.calculate_interest_coverage(
            operating_profit, interest_expense
        )

        # 计算 Altman Z-Score
        # 需要市值
        market_cap = None
        price_result = self._price_provider.get_price(stock_code)
        if price_result.success and price_result.price:
            # 市值 = 股价 × 估算股本
            current_price = price_result.price.current_price
            if total_equity and current_price and current_price > 0:
                # 估算股本
                shares = total_equity / (
                    self._get_value(balance, "total_equity") / total_equity
                    if total_equity > 0
                    else 1
                )
                if shares and shares > 0:
                    market_cap = current_price * shares

        # 留存收益 (简化: 使用净利润累加的近似)
        # 实际应该用利润表中的分配后利润
        retained_earnings = net_profit  # 简化处理

        # EBIT (使用营业利润作为近似)
        ebit = operating_profit

        # 计算 Z-Score
        altman_z = self._calculator.calculate_altman_z_score(
            working_capital=working_capital,
            total_assets=total_assets,
            retained_earnings=retained_earnings,
            ebit=ebit,
            market_cap=market_cap,
            total_liabilities=total_liabilities,
            revenue=self._get_value(income, "revenue"),
        )

        # Z-Score 解读
        altman_interpretation = ""
        if altman_z is not None:
            if altman_z > 2.99:
                altman_interpretation = "安全区 (Z > 2.99)"
            elif altman_z > 1.81:
                altman_interpretation = "灰色区 (1.81 < Z < 2.99)"
            else:
                altman_interpretation = "危险区 (Z < 1.81)"

        # 资本结构
        equity_ratio = None
        debt_ratio = None
        if total_assets and total_assets > 0:
            if total_equity:
                equity_ratio = total_equity / total_assets
            if total_liabilities:
                debt_ratio = total_liabilities / total_assets

        return SafetyMetrics(
            stock_code=stock_code,
            report_date=self._get_latest_report_date(balance),
            current_ratio=current_ratio,
            quick_ratio=quick_ratio,
            cash_ratio=cash_ratio,
            debt_to_equity=debt_to_equity,
            debt_to_assets=debt_to_assets,
            interest_coverage=interest_coverage,
            altman_z_score=altman_z,
            altman_z_interpretation=altman_interpretation,
            equity_ratio=equity_ratio,
            debt_ratio=debt_ratio,
            calculation_timestamp=datetime.now().isoformat(),
        )

    def get_current_ratio(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取流动比率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            流动比率或 None
        """
        metrics = self.get_safety_metrics(stock_code, period)
        return metrics.current_ratio if metrics else None

    def get_quick_ratio(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取速动比率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            速动比率或 None
        """
        metrics = self.get_safety_metrics(stock_code, period)
        return metrics.quick_ratio if metrics else None

    def get_altman_z_score(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取 Altman Z-Score

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            Z-Score 或 None
        """
        metrics = self.get_safety_metrics(stock_code, period)
        return metrics.altman_z_score if metrics else None

    def get_interest_coverage(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取利息保障倍数

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            利息保障倍数或 None
        """
        metrics = self.get_safety_metrics(stock_code, period)
        return metrics.interest_coverage if metrics else None

    def _get_metrics_with_facade(
        self, stock_code: str, facade: Any
    ) -> Optional[SafetyMetrics]:
        """使用指定门面获取财务安全指标（用于多年分析）"""
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
            current_assets = self._get_value(balance, "current_assets")
            current_liabilities = self._get_value(balance, "current_liabilities")
            inventory = self._get_value(balance, "inventory")
            cash = self._get_value(balance, "cash_and_equivalents")
            total_assets = self._get_value(balance, "total_assets")
            total_equity = self._get_value(balance, "total_equity")
            total_liabilities = self._get_value(balance, "total_liabilities")
            revenue = self._get_value(income, "revenue")

            # 计算流动性指标
            current_ratio = self._calculator.calculate_current_ratio(
                current_assets, current_liabilities
            )
            quick_ratio = self._calculator.calculate_quick_ratio(
                current_assets, inventory, current_liabilities
            )
            cash_ratio = None
            if cash is not None and current_liabilities is not None and current_liabilities > 0:
                cash_ratio = cash / current_liabilities

            # 计算偿债能力
            debt_to_equity = self._calculator.calculate_debt_to_equity(
                total_liabilities, total_equity
            )
            debt_to_assets = self._calculator.calculate_debt_to_assets(
                total_liabilities, total_assets
            )

            # 利息保障倍数
            operating_profit = self._get_value(income, "operating_profit")
            interest_expense = self._get_value(income, "interest_expense")
            interest_coverage = self._calculator.calculate_interest_coverage(
                operating_profit, interest_expense
            )

            # 留存收益
            net_profit = self._get_value(income, "net_profit")
            retained_earnings = net_profit  # 简化处理

            # Altman Z-Score (不需要市值，使用总资产代替)
            altman_z_score = None
            if (
                current_assets is not None
                and total_assets is not None
                and retained_earnings is not None
                and operating_profit is not None
                and total_liabilities is not None
                and revenue is not None
            ):
                altman_z_score = self._calculator.calculate_altman_z_score(
                    working_capital=current_assets - current_liabilities if current_assets and current_liabilities else None,
                    total_assets=total_assets,
                    retained_earnings=retained_earnings,
                    ebit=operating_profit,
                    market_cap=None,  # 历史数据不使用市值
                    total_liabilities=total_liabilities,
                    revenue=revenue,
                )

            # 股权比率和负债比率
            equity_ratio = None
            if total_equity is not None and total_assets is not None and total_assets > 0:
                equity_ratio = total_equity / total_assets

            debt_ratio = None
            if debt_to_assets is not None:
                debt_ratio = debt_to_assets

            return SafetyMetrics(
                stock_code=stock_code,
                report_date=self._get_latest_report_date(balance),
                current_ratio=current_ratio,
                quick_ratio=quick_ratio,
                cash_ratio=cash_ratio,
                debt_to_equity=debt_to_equity,
                debt_to_assets=debt_to_assets,
                interest_coverage=interest_coverage,
                altman_z_score=altman_z_score,
                equity_ratio=equity_ratio,
                debt_ratio=debt_ratio,
                calculation_timestamp=datetime.now().isoformat(),
            )
        except Exception:
            return None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        facade_healthy = True
        price_healthy = True

        try:
            FinancialFacade().health_check()
        except Exception:
            facade_healthy = False

        try:
            from ..price import get_price_provider

            provider = get_price_provider()
            provider.get_price("600000.SH")
        except Exception:
            price_healthy = False

        return {
            "name": self.analyzer_name,
            "status": "healthy" if (facade_healthy and price_healthy) else "degraded",
            "facade_available": facade_healthy,
            "price_provider_available": price_healthy,
        }
