"""
自由现金流 (FCF) 分析器

提供自由现金流相关指标的计算和分析：
- FCF (Free Cash Flow) = Operating Cash Flow - CapEx
- FCF Yield = FCF / Market Cap
- FCF 趋势分析 (CAGR, 波动性)
- 利润质量指标 (FCF/Net Income, Cash Earnings Ratio, Accrual Ratio)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from .analytics_base import BaseAnalyzer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..facade import FinancialFacade  # noqa: F401

from ..price import get_price_provider


@dataclass
class FCFMetrics:
    """
    自由现金流指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 当前期指标
        fcf: 当前自由现金流
        fcf_yield: FCF收益率 (FCF / Market Cap)
        operating_cash_flow: 经营现金流
        capex: 资本支出

        # 趋势指标
        fcf_cagr_5y: 5年FCF复合增长率
        fcf_volatility: FCF波动性 (标准差/均值)
        fcf_stability_score: FCF稳定性评分 (0-100)

        # 利润质量指标
        fcf_to_net_income: FCF/净利润比率
        cash_earnings_ratio: 现金盈利比率 (OCF/Net Income)
        accrual_ratio: 应计比率

        # 评估
        quality_assessment: 质量评估
        quality_description: 质量描述

        # 计算时间
        calculation_timestamp: str
    """

    stock_code: str
    report_date: str

    # 当前期指标
    fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None

    # 趋势指标
    fcf_cagr_5y: Optional[float] = None
    fcf_volatility: Optional[float] = None
    fcf_stability_score: Optional[float] = None

    # 利润质量指标
    fcf_to_net_income: Optional[float] = None
    cash_earnings_ratio: Optional[float] = None
    accrual_ratio: Optional[float] = None

    # 评估
    quality_assessment: str = ""
    quality_description: str = ""

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "fcf": self.fcf,
            "fcf_yield": self.fcf_yield,
            "operating_cash_flow": self.operating_cash_flow,
            "capex": self.capex,
            "fcf_cagr_5y": self.fcf_cagr_5y,
            "fcf_volatility": self.fcf_volatility,
            "fcf_stability_score": self.fcf_stability_score,
            "fcf_to_net_income": self.fcf_to_net_income,
            "cash_earnings_ratio": self.cash_earnings_ratio,
            "accrual_ratio": self.accrual_ratio,
            "quality_assessment": self.quality_assessment,
            "quality_description": self.quality_description,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_summary(self) -> str:
        """
        获取摘要

        Returns:
            格式化的摘要字符串
        """
        lines = [
            f"FCF: {self._format_value(self.fcf)}",
            f"FCF Yield: {self._format_pct(self.fcf_yield)}",
            f"FCF/Net Income: {self._format_ratio(self.fcf_to_net_income)}",
            f"质量评估: {self.quality_assessment.upper()} ({self.quality_description})",
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_value(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        if abs(val) >= 1e8:
            return f"{val/1e8:.2f}亿"
        elif abs(val) >= 1e4:
            return f"{val/1e4:.2f}万"
        return f"{val:.2f}"

    @staticmethod
    def _format_pct(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val*100:.2f}%"

    @staticmethod
    def _format_ratio(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val:.2f}x"


class FCFAnalyzer(BaseAnalyzer):
    """
    自由现金流分析器

    提供 FCF 相关指标的计算：

    1. FCF 计算
       FCF = Operating Cash Flow - CapEx

    2. FCF Yield
       FCF Yield = FCF / Market Cap
       - > 8% 通常是低估信号
       - < 3% 可能是高估或资本支出过大

    3. 利润质量指标
       - FCF / Net Income: >1.2 优秀, <0.5 危险
       - Cash Earnings Ratio (OCF/Net Income): >1.2 优秀, <0.8 危险
       - Accrual Ratio: 高值是红旗信号

    4. 趋势分析
       - 5年 FCF CAGR
       - FCF 波动性 (标准差/均值)

    使用示例:
        analyzer = FCFAnalyzer()
        result = analyzer.analyze("600519.SH")
        print(f"FCF: {result.fcf}")
        print(f"FCF Yield: {result.fcf_yield}")
        print(result.get_summary())
    """

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        """
        初始化 FCF 分析器

        Args:
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)
        self._price_provider = get_price_provider()

    @property
    def analyzer_name(self) -> str:
        return "fcf_analyzer"

    def analyze(self, stock_code: str, period: str = "annual") -> Optional[FCFMetrics]:
        """
        分析自由现金流

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            FCFMetrics 或 None
        """
        try:
            # 获取财务数据
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )

            income = bundle.income_statement
            cash_flow = bundle.cash_flow
            balance = bundle.balance_sheet

            if income is None or income.empty:
                return None

            # 获取当前期数据
            dates = sorted(
                income["report_date"].dropna().unique().tolist(),
                reverse=True,
            )
            if not dates:
                return None

            current_date = dates[0]

            # 当前期指标
            curr_income = income[income["report_date"] == current_date]
            curr_cash_flow = cash_flow[cash_flow["report_date"] == current_date]
            curr_balance = balance[balance["report_date"] == current_date]

            net_profit = self._get_value_from_df(curr_income, "net_profit")
            operating_cash_flow = self._get_value_from_df(curr_cash_flow, "operating_cash_flow")

            # CapEx: 尝试多个字段名
            capex = self._get_value_from_df(curr_cash_flow, "capex")
            if capex is None:
                capex = self._get_value_from_df(curr_cash_flow, "capital_expenditure")
            if capex is None:
                capex = self._get_value_from_df(curr_cash_flow, "purchase_of_fixed_assets")
            if capex is None:
                capex = self._get_value_from_df(curr_cash_flow, "购建固定资产、无形资产和其他长期资产支付的现金")

            # FCF = OCF - CapEx (CapEx 取绝对值)
            fcf = None
            if operating_cash_flow is not None:
                if capex is not None:
                    fcf = operating_cash_flow - abs(capex)
                else:
                    fcf = operating_cash_flow  # 无 CapEx 数据时使用 OCF 作为近似

            # 市值
            market_cap = self._price_provider.get_market_cap(stock_code)

            # FCF Yield
            fcf_yield = None
            if fcf is not None and market_cap is not None and market_cap > 0:
                fcf_yield = fcf / market_cap

            # 利润质量指标
            fcf_to_net_income = None
            cash_earnings_ratio = None
            accrual_ratio = None

            if net_profit is not None and net_profit != 0:
                if fcf is not None:
                    fcf_to_net_income = fcf / net_profit
                if operating_cash_flow is not None:
                    cash_earnings_ratio = operating_cash_flow / net_profit

            # Accrual Ratio = (Net Income - OCF) / Total Assets
            total_assets = self._get_value_from_df(curr_balance, "total_assets")
            if net_profit is not None and operating_cash_flow is not None and total_assets and total_assets > 0:
                accrual_ratio = (net_profit - operating_cash_flow) / total_assets

            # 趋势分析（如果有多年数据）
            fcf_series: List[float] = []
            for date in dates[:10]:  # 最多取10年
                period_cf = cash_flow[cash_flow["report_date"] == date]
                period_ocf = self._get_value_from_df(period_cf, "operating_cash_flow")
                period_capex = self._get_value_from_df(period_cf, "capex")
                if period_capex is None:
                    period_capex = self._get_value_from_df(period_cf, "capital_expenditure")
                if period_capex is None:
                    period_capex = self._get_value_from_df(period_cf, "purchase_of_fixed_assets")

                if period_ocf is not None:
                    if period_capex is not None:
                        period_fcf = period_ocf - abs(period_capex)
                    else:
                        period_fcf = period_ocf
                    fcf_series.append(period_fcf)

            # 计算 CAGR 和波动性
            fcf_cagr_5y = None
            fcf_volatility = None
            fcf_stability_score = None

            if len(fcf_series) >= 2:
                # 计算 CAGR
                try:
                    years = min(len(fcf_series) - 1, 5)
                    if years > 0 and fcf_series[0] > 0 and fcf_series[-1] > 0:
                        fcf_cagr_5y = (fcf_series[0] / fcf_series[-1]) ** (1 / years) - 1
                except (ZeroDivisionError, ValueError):
                    pass

                # 计算波动性 (标准差/均值)
                try:
                    fcf_array = np.array(fcf_series)
                    mean_fcf = np.mean(fcf_array)
                    std_fcf = np.std(fcf_array, ddof=1)
                    if mean_fcf != 0:
                        fcf_volatility = std_fcf / abs(mean_fcf)
                        # 稳定性评分: 波动性越低分数越高
                        # 波动性 < 0.2 -> 100分, > 1.0 -> 0分
                        fcf_volatility_clamped = min(max(fcf_volatility, 0.2), 1.0)
                        fcf_stability_score = (1.0 - (fcf_volatility_clamped - 0.2) / 0.8) * 100
                except (ZeroDivisionError, ValueError):
                    pass

            # 评估
            quality_score = 0
            descriptions: List[str] = []

            # FCF Yield 评分
            if fcf_yield is not None:
                if fcf_yield > 0.08:
                    quality_score += 2
                    descriptions.append("FCF Yield > 8% (低估)")
                elif fcf_yield > 0.03:
                    quality_score += 1
                    descriptions.append("FCF Yield 3-8% (合理)")

            # FCF/Net Income 评分
            if fcf_to_net_income is not None:
                if fcf_to_net_income > 1.2:
                    quality_score += 2
                    descriptions.append("FCF/NI > 1.2 (优质)")
                elif fcf_to_net_income > 0.5:
                    quality_score += 1
                    descriptions.append("FCF/NI 0.5-1.2 (一般)")
                else:
                    descriptions.append("FCF/NI < 0.5 (利润质量差)")

            # Cash Earnings Ratio 评分
            if cash_earnings_ratio is not None:
                if cash_earnings_ratio > 1.2:
                    quality_score += 1
                    descriptions.append("现金盈利比率优秀")
                elif cash_earnings_ratio < 0.8:
                    descriptions.append("现金盈利比率偏低")

            # Accrual Ratio 评分
            if accrual_ratio is not None:
                if abs(accrual_ratio) < 0.05:
                    quality_score += 1
                    descriptions.append("应计比率低 (正常)")
                elif abs(accrual_ratio) > 0.10:
                    descriptions.append("应计比率高 (警告)")

            # 综合评估
            if quality_score >= 5:
                quality_assessment = "excellent"
                quality_description = "现金质量优秀"
            elif quality_score >= 3:
                quality_assessment = "good"
                quality_description = "现金质量良好"
            elif quality_score >= 1:
                quality_assessment = "warning"
                quality_description = "需关注"
            else:
                quality_assessment = "poor"
                quality_description = "利润质量差"

            return FCFMetrics(
                stock_code=stock_code,
                report_date=current_date,
                fcf=fcf,
                fcf_yield=fcf_yield,
                operating_cash_flow=operating_cash_flow,
                capex=capex,
                fcf_cagr_5y=fcf_cagr_5y,
                fcf_volatility=fcf_volatility,
                fcf_stability_score=fcf_stability_score,
                fcf_to_net_income=fcf_to_net_income,
                cash_earnings_ratio=cash_earnings_ratio,
                accrual_ratio=accrual_ratio,
                quality_assessment=quality_assessment,
                quality_description=quality_description,
                calculation_timestamp=datetime.now().isoformat(),
            )

        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

    def _get_value_from_df(self, df: Any, field: str) -> Optional[float]:
        """从 DataFrame 获取值"""
        if df is None or df.empty:
            return None
        if field not in df.columns:
            return None
        val = df[field].iloc[0] if len(df) > 0 else None
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def get_fcf(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取自由现金流

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            FCF 或 None
        """
        result = self.analyze(stock_code, period)
        return result.fcf if result else None

    def get_fcf_yield(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取 FCF 收益率

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            FCF Yield 或 None
        """
        result = self.analyze(stock_code, period)
        return result.fcf_yield if result else None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
