"""
成长性分析器

提供基于财务报表的成长性分析，包括同比增长率和可持续增长率。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from .analytics_base import BaseAnalyzer
from ..facade import FinancialFacade
from .metrics_calculator import MetricsCalculator


@dataclass
class GrowthMetrics:
    """
    成长性指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 同比增长率
        revenue_growth_yoy: 营收同比增长率
        profit_growth_yoy: 净利润同比增长率
        gross_profit_growth_yoy: 毛利同比增长率
        operating_profit_growth_yoy: 营业利润同比增长率
        eps_growth_yoy: EPS同比增长率
        total_assets_growth_yoy: 总资产同比增长率
        equity_growth_yoy: 股东权益同比增长率

        # 环比增长率
        revenue_growth_qoq: 营收环比增长率
        profit_growth_qoq: 净利润环比增长率

        # 可持续增长
        sustainable_growth_rate: 可持续增长率
        retention_rate: 留存比率

        # 数据质量
        has_comparable_data: 是否有可比较的历史数据
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str

    # 同比增长率
    revenue_growth_yoy: Optional[float] = None
    profit_growth_yoy: Optional[float] = None
    gross_profit_growth_yoy: Optional[float] = None
    operating_profit_growth_yoy: Optional[float] = None
    eps_growth_yoy: Optional[float] = None
    total_assets_growth_yoy: Optional[float] = None
    equity_growth_yoy: Optional[float] = None

    # 环比增长率
    revenue_growth_qoq: Optional[float] = None
    profit_growth_qoq: Optional[float] = None

    # 可持续增长
    sustainable_growth_rate: Optional[float] = None
    retention_rate: Optional[float] = None

    # 数据质量
    has_comparable_data: bool = False
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "revenue_growth_yoy": self.revenue_growth_yoy,
            "profit_growth_yoy": self.profit_growth_yoy,
            "gross_profit_growth_yoy": self.gross_profit_growth_yoy,
            "operating_profit_growth_yoy": self.operating_profit_growth_yoy,
            "eps_growth_yoy": self.eps_growth_yoy,
            "total_assets_growth_yoy": self.total_assets_growth_yoy,
            "equity_growth_yoy": self.equity_growth_yoy,
            "revenue_growth_qoq": self.revenue_growth_qoq,
            "profit_growth_qoq": self.profit_growth_qoq,
            "sustainable_growth_rate": self.sustainable_growth_rate,
            "retention_rate": self.retention_rate,
            "has_comparable_data": self.has_comparable_data,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_interpretation(self) -> str:
        """
        获取成长性解读

        Returns:
            解读字符串
        """
        if not self.has_comparable_data:
            return "数据不足，无法进行成长性分析"

        if self.revenue_growth_yoy is None:
            return "营收数据不足"

        if self.revenue_growth_yoy > 0.30:
            growth_level = "高速增长"
        elif self.revenue_growth_yoy > 0.10:
            growth_level = "稳健增长"
        elif self.revenue_growth_yoy > 0:
            growth_level = "低速增长"
        elif self.revenue_growth_yoy > -0.10:
            growth_level = "小幅下滑"
        else:
            growth_level = "大幅下滑"

        return f"营收增长: {self.revenue_growth_yoy * 100:.1f}%, 水平: {growth_level}"


class GrowthAnalyzer(BaseAnalyzer):
    """
    成长性分析器

    提供成长性分析，包括：
    - 同比增长率 (YoY)
    - 环比增长率 (QoQ)
    - 可持续增长率 (Sustainable Growth Rate)

    使用示例:
        analyzer = GrowthAnalyzer()

        # 获取完整成长性分析
        metrics = analyzer.get_growth_metrics("600000.SH")
        print(f"营收增长: {metrics.revenue_growth_yoy}")
        print(f"净利润增长: {metrics.profit_growth_yoy}")

        # 单独获取某个指标
        revenue_growth = analyzer.get_revenue_growth("600000.SH")
    """

    def __init__(self, financial_facade: Optional[FinancialFacade] = None) -> None:
        """
        初始化成长性分析器

        Args:
            financial_facade: 财务门面实例
        """
        self._facade = financial_facade or FinancialFacade()
        self._calculator = MetricsCalculator()

    @property
    def analyzer_name(self) -> str:
        return "growth_analyzer"

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

    def _get_series(
        self, df: Optional[pd.DataFrame], field: str
    ) -> Optional[List[float]]:
        """
        获取时间序列数据

        Returns:
            按时间排序的值列表 (从旧到新)
        """
        if df is None or df.empty:
            return None
        if field not in df.columns or "report_date" not in df.columns:
            return None

        df = df.sort_values("report_date", ascending=True)
        values = df[field].dropna().tolist()
        return values if values else None

    def _calculate_yoy_growth(self, series: Optional[List[float]]) -> Optional[float]:
        """从时间序列计算同比增长率 (需要至少2期)"""
        if series is None or len(series) < 2:
            return None
        return self._calculator.calculate_yoy_growth(series[-1], series[-2])

    def _calculate_qoq_growth(self, series: Optional[List[float]]) -> Optional[float]:
        """从时间序列计算环比增长率 (需要至少2期)"""
        if series is None or len(series) < 2:
            return None
        return self._calculator.calculate_yoy_growth(series[-1], series[-2])

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

    def get_growth_metrics(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[GrowthMetrics]:
        """
        获取完整成长性指标

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            GrowthMetrics 或 None
        """
        fs_data = self._get_financial_data(stock_code, period)
        income = fs_data["income_statement"]
        balance = fs_data["balance_sheet"]
        indicators = fs_data["indicators"]

        if income is None or income.empty:
            return None

        # 获取时间序列数据
        revenue_series = self._get_series(income, "revenue")
        profit_series = self._get_series(income, "net_profit")
        gross_profit_series = self._get_series(income, "gross_profit")
        operating_profit_series = self._get_series(income, "operating_profit")
        total_assets_series = self._get_series(balance, "total_assets")
        equity_series = self._get_series(balance, "total_equity")
        eps_series = None
        if indicators is not None and "eps" in indicators.columns:
            eps_series = self._get_series(indicators, "eps")

        # 是否有可比较数据
        has_comparable = revenue_series is not None and len(revenue_series) >= 2

        # 计算同比增长率
        revenue_yoy = self._calculate_yoy_growth(revenue_series)
        profit_yoy = self._calculate_yoy_growth(profit_series)
        gross_profit_yoy = self._calculate_yoy_growth(gross_profit_series)
        operating_profit_yoy = self._calculate_yoy_growth(operating_profit_series)
        eps_yoy = self._calculate_yoy_growth(eps_series)
        total_assets_yoy = self._calculate_yoy_growth(total_assets_series)
        equity_yoy = self._calculate_yoy_growth(equity_series)

        # 计算环比增长率 (需要季度数据)
        revenue_qoq = self._calculate_qoq_growth(revenue_series)
        profit_qoq = self._calculate_qoq_growth(profit_series)

        # 计算可持续增长率
        sustainable_growth = None
        retention_rate = None

        if profit_series and len(profit_series) >= 1 and revenue_series:
            # 获取最新一期数据
            latest_net_profit = profit_series[-1]
            latest_revenue = revenue_series[-1]

            if latest_net_profit and latest_revenue and latest_revenue > 0:
                # 计算 ROE (简化版)
                if equity_series and len(equity_series) >= 1:
                    latest_equity = equity_series[-1]
                    if latest_equity and latest_equity > 0:
                        roe = latest_net_profit / latest_equity

                        # 计算留存比率 (简化: 1 - 分红率)
                        # 这里用净利润增长率作为留存收益的代理
                        # 实际应该用 (Net_Income - Dividends) / Net_Income
                        retention_rate = 0.7  # 默认留存率 70%
                        if profit_yoy is not None:
                            retention_rate = max(0.3, min(0.9, 1 - abs(profit_yoy)))

                        sustainable_growth = (
                            self._calculator.calculate_sustainable_growth_rate(
                                roe=roe,
                                retention_rate=retention_rate,
                            )
                        )

        return GrowthMetrics(
            stock_code=stock_code,
            report_date=self._get_latest_report_date(income),
            revenue_growth_yoy=revenue_yoy,
            profit_growth_yoy=profit_yoy,
            gross_profit_growth_yoy=gross_profit_yoy,
            operating_profit_growth_yoy=operating_profit_yoy,
            eps_growth_yoy=eps_yoy,
            total_assets_growth_yoy=total_assets_yoy,
            equity_growth_yoy=equity_yoy,
            revenue_growth_qoq=revenue_qoq,
            profit_growth_qoq=profit_qoq,
            sustainable_growth_rate=sustainable_growth,
            retention_rate=retention_rate,
            has_comparable_data=has_comparable,
            calculation_timestamp=datetime.now().isoformat(),
        )

    def get_revenue_growth(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取营收同比增长率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            营收同比增长率或 None
        """
        metrics = self.get_growth_metrics(stock_code, period)
        return metrics.revenue_growth_yoy if metrics else None

    def get_profit_growth(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取净利润同比增长率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            净利润同比增长率或 None
        """
        metrics = self.get_growth_metrics(stock_code, period)
        return metrics.profit_growth_yoy if metrics else None

    def get_sustainable_growth_rate(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取可持续增长率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            可持续增长率或 None
        """
        metrics = self.get_growth_metrics(stock_code, period)
        return metrics.sustainable_growth_rate if metrics else None

    def _get_metrics_with_facade(
        self, stock_code: str, facade: Any
    ) -> Optional[GrowthMetrics]:
        """使用指定门面获取成长性指标（用于多年分析）"""
        try:
            bundle = facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period="annual",
            )

            income = bundle.income_statement
            balance = bundle.balance_sheet
            indicators = bundle.indicators

            if income is None or income.empty:
                return None

            # 获取时间序列数据
            revenue_series = self._get_series(income, "revenue")
            profit_series = self._get_series(income, "net_profit")
            gross_profit_series = self._get_series(income, "gross_profit")
            operating_profit_series = self._get_series(income, "operating_profit")
            total_assets_series = self._get_series(balance, "total_assets")
            equity_series = self._get_series(balance, "total_equity")
            eps_series = None
            if indicators is not None and "eps" in indicators.columns:
                eps_series = self._get_series(indicators, "eps")

            # 是否有可比较数据
            has_comparable = revenue_series is not None and len(revenue_series) >= 2

            # 计算同比增长率
            revenue_yoy = self._calculate_yoy_growth(revenue_series)
            profit_yoy = self._calculate_yoy_growth(profit_series)
            gross_profit_yoy = self._calculate_yoy_growth(gross_profit_series)
            operating_profit_yoy = self._calculate_yoy_growth(operating_profit_series)
            eps_yoy = self._calculate_yoy_growth(eps_series)
            total_assets_yoy = self._calculate_yoy_growth(total_assets_series)
            equity_yoy = self._calculate_yoy_growth(equity_series)

            # 计算环比增长率
            revenue_qoq = self._calculate_qoq_growth(revenue_series)
            profit_qoq = self._calculate_qoq_growth(profit_series)

            # 计算可持续增长率
            sustainable_growth = None
            retention_rate = None

            if profit_series and len(profit_series) >= 1 and revenue_series:
                latest_net_profit = profit_series[-1]

                # 计算 ROE
                roe = None
                if balance is not None:
                    equity = self._get_series(balance, "total_equity")
                    if equity and len(equity) >= 1:
                        roe = latest_net_profit / equity[-1] if equity[-1] != 0 else None

                if roe is not None:
                    retention_rate = 0.7
                    if profit_yoy is not None:
                        retention_rate = max(0.3, min(0.9, 1 - abs(profit_yoy)))

                    sustainable_growth = self._calculator.calculate_sustainable_growth_rate(
                        roe=roe,
                        retention_rate=retention_rate,
                    )

            return GrowthMetrics(
                stock_code=stock_code,
                report_date=self._get_latest_report_date(income),
                revenue_growth_yoy=revenue_yoy,
                profit_growth_yoy=profit_yoy,
                gross_profit_growth_yoy=gross_profit_yoy,
                operating_profit_growth_yoy=operating_profit_yoy,
                eps_growth_yoy=eps_yoy,
                total_assets_growth_yoy=total_assets_yoy,
                equity_growth_yoy=equity_yoy,
                revenue_growth_qoq=revenue_qoq,
                profit_growth_qoq=profit_qoq,
                sustainable_growth_rate=sustainable_growth,
                retention_rate=retention_rate,
                has_comparable_data=has_comparable,
                calculation_timestamp=datetime.now().isoformat(),
            )
        except Exception:
            return None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        facade_healthy = True

        try:
            FinancialFacade().health_check()
        except Exception:
            facade_healthy = False

        return {
            "name": self.analyzer_name,
            "status": "healthy" if facade_healthy else "degraded",
            "facade_available": facade_healthy,
        }
