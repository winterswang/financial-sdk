"""
估值指标分析器

提供基于价格和财务数据的估值指标计算。
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
class ValuationMetrics:
    """
    估值指标数据类

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期
        current_price: 当前价格
        currency: 货币

        # 市值指标
        market_cap: 总市值
        enterprise_value: 企业价值
        pe_ratio: 市盈率
        pb_ratio: 市净率
        ps_ratio: 市销率
        peg_ratio: PEG比率
        ev_ebitda: EV/EBITDA

        # 股息指标
        dividend_yield: 股息率
        dps: 每股股息

        # 每股指标
        eps: 每股收益
        bvps: 每股净资产

        # 数据质量
        price_source: 价格数据源
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str
    current_price: float
    currency: str

    # 市值指标
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None

    # 股息指标
    dividend_yield: Optional[float] = None
    dps: Optional[float] = None

    # 每股指标
    eps: Optional[float] = None
    bvps: Optional[float] = None

    # 数据质量
    price_source: str = ""
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "current_price": self.current_price,
            "currency": self.currency,
            "market_cap": self.market_cap,
            "enterprise_value": self.enterprise_value,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "ps_ratio": self.ps_ratio,
            "peg_ratio": self.peg_ratio,
            "ev_ebitda": self.ev_ebitda,
            "dividend_yield": self.dividend_yield,
            "dps": self.dps,
            "eps": self.eps,
            "bvps": self.bvps,
            "price_source": self.price_source,
            "calculation_timestamp": self.calculation_timestamp,
        }


class ValuationAnalyzer(BaseAnalyzer):
    """
    估值指标分析器

    提供估值指标计算，包括：
    - PE (市盈率)
    - PB (市净率)
    - PS (市销率)
    - PEG (PEG比率)
    - EV/EBITDA
    - 股息率
    - 总市值
    - 每股指标 (EPS, BVPS)

    使用示例:
        analyzer = ValuationAnalyzer()

        # 获取完整估值指标
        metrics = analyzer.get_valuation_metrics("600000.SH")
        print(f"PE: {metrics.pe_ratio}")
        print(f"PB: {metrics.pb_ratio}")

        # 单独获取某个指标
        pe = analyzer.get_pe_ratio("600000.SH")
    """

    def __init__(
        self,
        price_provider: Optional[PriceProvider] = None,
        financial_facade: Optional[FinancialFacade] = None,
    ) -> None:
        """
        初始化估值分析器

        Args:
            price_provider: 价格提供者实例
            financial_facade: 财务门面实例
        """
        self._price_provider = price_provider or get_price_provider()
        self._facade = financial_facade or FinancialFacade()
        self._calculator = MetricsCalculator()

    @property
    def analyzer_name(self) -> str:
        return "valuation_analyzer"

    def _get_financial_data(
        self, stock_code: str, period: str = "annual"
    ) -> Dict[str, pd.DataFrame]:
        """
        获取财务报表数据

        Returns:
            Dict[str, DataFrame]: 包含各报表的字典
        """
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

    def _get_value(
        self, df: Optional[pd.DataFrame], field: str, period_index: int = 0
    ) -> Optional[float]:
        """
        从 DataFrame 获取指定字段的最新值

        Args:
            df: DataFrame
            field: 字段名
            period_index: 取第几期 (0=最新)

        Returns:
            值或 None
        """
        if df is None or df.empty:
            return None
        if field not in df.columns or "report_date" not in df.columns:
            return None

        # 按日期排序确保获取正确的数据
        df_sorted = df.sort_values("report_date", ascending=True)

        values = df_sorted[field].dropna()
        if values.empty:
            return None

        if period_index < len(values):
            return float(values.iloc[-(period_index + 1)])  # 最后一行是最新的
        return float(values.iloc[0])

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

    def get_valuation_metrics(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[ValuationMetrics]:
        """
        获取完整估值指标

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            ValuationMetrics 或 None
        """
        # 获取价格
        price_result = self._price_provider.get_price(stock_code)
        if not price_result.success or price_result.price is None:
            return None

        price_data = price_result.price
        current_price = price_data.current_price

        # 获取财务数据
        fs_data = self._get_financial_data(stock_code, period)
        income = fs_data["income_statement"]
        balance = fs_data["balance_sheet"]
        cash_flow = fs_data["cash_flow"]
        indicators = fs_data["indicators"]

        # 获取关键财务指标
        eps = self._get_value(income, "eps") or self._get_value(
            indicators, "eps"
        )  # 优先使用利润表的EPS
        bvps = self._get_value(indicators, "bvps")  # 从指标表获取每股净资产
        revenue = self._get_value(income, "revenue")
        net_profit = self._get_value(income, "net_profit")
        total_equity = self._get_value(balance, "total_equity")
        total_assets = self._get_value(balance, "total_assets")
        total_debt = self._get_value(balance, "total_liabilities")
        cash = self._get_value(balance, "cash_and_equivalents")
        depreciation = self._get_value(cash_flow, "depreciation_amortization")

        # 计算总股本 (总市值/价格 或 总权益/每股净资产)
        shares = None
        if total_equity and bvps and bvps > 0:
            shares = total_equity / bvps
        elif total_assets and total_equity:
            shares = total_assets  # 简化估算

        # 计算市值
        market_cap = None
        if shares and shares > 0:
            market_cap = current_price * shares

        # 计算股息 (简化)
        dps = self._get_value(indicators, "dps") or self._get_value(
            income, "dividends_paid"
        )

        # 计算 EBITDA
        ebitda = None
        if net_profit is not None:
            tax_expense = self._get_value(income, "tax_expense") or 0
            interest_expense = self._get_value(income, "interest_expense") or 0
            ebitda = net_profit + tax_expense + interest_expense + (depreciation or 0)

        # 计算指标
        pe_ratio = self._calculator.calculate_pe_ratio(current_price, eps)
        pb_ratio = self._calculator.calculate_pb_ratio(
            current_price, total_equity, shares
        )
        ps_ratio = self._calculator.calculate_ps_ratio(current_price, revenue, shares)
        ev_ebitda = self._calculator.calculate_ev_ebitda(
            market_cap, total_debt, cash, ebitda
        )
        dividend_yield = self._calculator.calculate_dividend_yield(dps, current_price)

        # 计算 PEG (需要增长率)
        peg_ratio = None
        if pe_ratio and period == "annual":
            # 简化: 使用净利润作为增长率估算
            yoy_growth = self._get_yoy_growth(stock_code, "net_profit")
            if yoy_growth:
                peg_ratio = self._calculator.calculate_peg_ratio(pe_ratio, yoy_growth)

        # 计算企业价值 (EV = 市值 + 债务 - 现金)
        enterprise_value = None
        if market_cap is not None and total_debt is not None:
            enterprise_value = market_cap + total_debt
            if cash is not None:
                enterprise_value = enterprise_value - cash

        return ValuationMetrics(
            stock_code=stock_code,
            report_date=self._get_latest_report_date(income),
            current_price=current_price,
            currency=price_data.currency,
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            ps_ratio=ps_ratio,
            peg_ratio=peg_ratio,
            ev_ebitda=ev_ebitda,
            dividend_yield=dividend_yield,
            dps=dps,
            eps=eps,
            bvps=bvps,
            price_source=price_data.source,
            calculation_timestamp=datetime.now().isoformat(),
        )

    def _get_yoy_growth(self, stock_code: str, field: str) -> Optional[float]:
        """
        获取同比增长率

        Args:
            stock_code: 股票代码
            field: 字段名

        Returns:
            增长率或 None
        """
        try:
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="income_statement",
                period="annual",
            )
            df = bundle.income_statement
            if df is None or df.empty:
                return None
            if field not in df.columns or "report_date" not in df.columns:
                return None

            # 按日期排序
            df = df.sort_values("report_date", ascending=False)
            values = df[field].dropna()

            if len(values) < 2:
                return None

            current = float(values.iloc[0])
            previous = float(values.iloc[1])

            return self._calculator.calculate_yoy_growth(current, previous)
        except Exception:
            return None

    def get_pe_ratio(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取市盈率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            市盈率或 None
        """
        metrics = self.get_valuation_metrics(stock_code, period)
        return metrics.pe_ratio if metrics else None

    def get_pb_ratio(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取市净率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            市净率或 None
        """
        metrics = self.get_valuation_metrics(stock_code, period)
        return metrics.pb_ratio if metrics else None

    def get_ps_ratio(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取市销率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            市销率或 None
        """
        metrics = self.get_valuation_metrics(stock_code, period)
        return metrics.ps_ratio if metrics else None

    def get_market_cap(self, stock_code: str) -> Optional[float]:
        """
        获取总市值

        Args:
            stock_code: 股票代码

        Returns:
            总市值或 None
        """
        metrics = self.get_valuation_metrics(stock_code)
        return metrics.market_cap if metrics else None

    def get_dividend_yield(self, stock_code: str) -> Optional[float]:
        """
        获取股息率

        Args:
            stock_code: 股票代码

        Returns:
            股息率或 None
        """
        metrics = self.get_valuation_metrics(stock_code)
        return metrics.dividend_yield if metrics else None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        price_healthy = True
        facade_healthy = True

        try:
            self._price_provider.get_price("600000.SH")
        except Exception:
            price_healthy = False

        try:
            FinancialFacade().health_check()
        except Exception:
            facade_healthy = False

        return {
            "name": self.analyzer_name,
            "status": "healthy" if (price_healthy and facade_healthy) else "degraded",
            "components": {
                "price_provider": "healthy" if price_healthy else "unhealthy",
                "financial_facade": "healthy" if facade_healthy else "unhealthy",
            },
        }
