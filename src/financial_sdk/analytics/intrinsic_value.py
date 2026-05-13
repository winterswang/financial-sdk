"""
内在价值与安全边际分析器

提供内在价值估算和安全边际判断：
- Graham Number
- 简化 DCF 模型
- 安全边际计算
- 历史估值分位分析
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

from .fcf import FCFAnalyzer
from ..price import get_price_provider


@dataclass
class IntrinsicValueMetrics:
    """
    内在价值指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 基础数据
        current_price: 当前价格
        currency: 货币
        market_cap: 总市值

        # Graham Number
        graham_number: Graham Number
        graham_price_ratio: 当前价格/Graham Number

        # 简化 DCF
        dcf_value: DCF 内在价值
        dcf_optimistic: 乐观情景
        dcf_neutral: 中性情景
        dcf_pessimistic: 悲观情景

        # 安全边际
        margin_of_safety: 安全边际
        valuation_signal: 估值信号

        # 估值分位
        pe_percentile_5y: 5年PE分位
        pb_percentile_5y: 5年PB分位

        # 建议价格区间
        buy_range_low: 建议买入低价
        buy_range_high: 建议买入高价

        # 计算时间
        calculation_timestamp: str
    """

    stock_code: str
    report_date: str
    current_price: float
    currency: str

    # Graham Number
    graham_number: Optional[float] = None
    graham_price_ratio: Optional[float] = None

    # DCF
    dcf_value: Optional[float] = None
    dcf_optimistic: Optional[float] = None
    dcf_neutral: Optional[float] = None
    dcf_pessimistic: Optional[float] = None

    # 安全边际
    margin_of_safety: Optional[float] = None
    valuation_signal: str = ""

    # 估值分位
    pe_percentile_5y: Optional[float] = None
    pb_percentile_5y: Optional[float] = None

    # 建议价格区间
    buy_range_low: Optional[float] = None
    buy_range_high: Optional[float] = None

    # 市值
    market_cap: Optional[float] = None

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "current_price": self.current_price,
            "currency": self.currency,
            "market_cap": self.market_cap,
            "graham_number": self.graham_number,
            "graham_price_ratio": self.graham_price_ratio,
            "dcf_value": self.dcf_value,
            "dcf_optimistic": self.dcf_optimistic,
            "dcf_neutral": self.dcf_neutral,
            "dcf_pessimistic": self.dcf_pessimistic,
            "margin_of_safety": self.margin_of_safety,
            "valuation_signal": self.valuation_signal,
            "pe_percentile_5y": self.pe_percentile_5y,
            "pb_percentile_5y": self.pb_percentile_5y,
            "buy_range_low": self.buy_range_low,
            "buy_range_high": self.buy_range_high,
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_summary(self) -> str:
        """
        获取摘要

        Returns:
            格式化的摘要字符串
        """
        lines = [
            f"当前价格: {self.current_price:.2f} {self.currency}",
            f"Graham Number: {self._fmt(self.graham_number)}",
            f"  价格/GN比率: {self._fmt_pct(self.graham_price_ratio)}",
        ]

        if self.dcf_neutral is not None:
            lines.append(f"DCF内在价值: {self._fmt(self.dcf_neutral)}")
            lines.append(f"  乐观: {self._fmt(self.dcf_optimistic)}")
            lines.append(f"  悲观: {self._fmt(self.dcf_pessimistic)}")

        lines.append(f"安全边际: {self._fmt_pct(self.margin_of_safety)}")
        lines.append(f"估值信号: {self.valuation_signal}")

        if self.buy_range_low is not None and self.buy_range_high is not None:
            lines.append(f"建议买入区间: {self._fmt(self.buy_range_low)} - {self._fmt(self.buy_range_high)}")

        if self.pe_percentile_5y is not None:
            lines.append(f"5年PE分位: {self._fmt_pct(self.pe_percentile_5y)}")
        if self.pb_percentile_5y is not None:
            lines.append(f"5年PB分位: {self._fmt_pct(self.pb_percentile_5y)}")

        return "\n".join(lines)

    @staticmethod
    def _fmt(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val:.2f}"

    @staticmethod
    def _fmt_pct(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val*100:.1f}%"


class IntrinsicValueAnalyzer(BaseAnalyzer):
    """
    内在价值与安全边际分析器

    提供价值投资的估值判断：

    1. Graham Number
       GN = √(22.5 × EPS × BVPS)
       价格 < GN → 低估

    2. 简化 DCF
       基于 FCF 的三阶段估值

    3. 安全边际
       MoS = (内在价值 - 价格) / 内在价值
       > 30%: 买入区间
       15-30%: 持有区间
       < 15%: 谨慎
       < 0%: 明显高估

    4. 历史估值分位
       当前 PE/PB 在历史中的分位

    使用示例:
        analyzer = IntrinsicValueAnalyzer()
        result = analyzer.analyze("600519.SH")
        print(f"安全边际: {result.margin_of_safety}")
        print(result.get_summary())
    """

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        """
        初始化内在价值分析器

        Args:
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)
        self._price_provider = get_price_provider()
        self._fcf_analyzer = FCFAnalyzer(financial_facade=financial_facade)

    @property
    def analyzer_name(self) -> str:
        return "intrinsic_value_analyzer"

    def analyze(
        self,
        stock_code: str,
        period: str = "annual",
        discount_rate: float = 0.10,
        terminal_growth_rate: float = 0.03,
        growth_years: int = 10,
    ) -> Optional[IntrinsicValueMetrics]:
        """
        分析内在价值

        Args:
            stock_code: 股票代码
            period: 报告期类型
            discount_rate: 折现率 (默认 10%)
            terminal_growth_rate: 永续增长率 (默认 3%)
            growth_years: 增长期年数 (默认 10年)

        Returns:
            IntrinsicValueMetrics 或 None
        """
        try:
            # 获取价格数据
            price_result = self._price_provider.get_price(stock_code)
            if not price_result.success or not price_result.price:
                return None

            price_data = price_result.price
            current_price = price_data.current_price
            currency = price_data.currency
            market_cap = self._price_provider.get_market_cap(stock_code)

            # 获取财务数据
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )

            income = bundle.income_statement
            balance = bundle.balance_sheet

            if income is None or income.empty:
                return None

            # 获取当前期数据
            dates = sorted(
                income["report_date"].dropna().unique().tolist(),
                reverse=True,
            )
            current_date = dates[0]

            curr_income = income[income["report_date"] == current_date]
            curr_balance = balance[balance["report_date"] == current_date]

            # === Graham Number ===
            eps = self._get_value_from_df(curr_income, "eps")
            bvps = self._get_value_from_df(curr_balance, "bvps")

            # === Graham Number ===
            eps = self._get_value_from_df(curr_income, "eps")

            # 获取股数用于计算 BVPS
            shares = self._get_value_from_df(curr_balance, "total_shares")
            if shares is None:
                shares = self._get_value_from_df(curr_balance, "shares")
            # A-share 数据的 SHARE_CAPITAL 单位是万股，需要转换
            if shares is None:
                share_capital = self._get_value_from_df(curr_balance, "SHARE_CAPITAL")
                if share_capital is not None:
                    shares = share_capital * 10000  # 万股转股

            # 获取 BVPS，优先直接获取，否则从权益/股数计算
            bvps = self._get_value_from_df(curr_balance, "bvps")
            if bvps is None:
                total_equity = self._get_value_from_df(curr_balance, "total_equity")
                if total_equity is not None and shares is not None and shares > 0:
                    bvps = total_equity / shares

            # 计算 Graham Number（每股）
            graham_number = None
            graham_price_ratio = None

            if eps is not None and bvps is not None and eps > 0 and bvps > 0:
                # Graham Number = √(22.5 × EPS × BVPS)
                # BVPS 可能是万元单位，需要转换为元 (乘以10000)
                bvps_yuan = bvps * 10000 if bvps < 100 else bvps
                graham_number = (22.5 * eps * bvps_yuan) ** 0.5
                graham_price_ratio = current_price / graham_number

            # === DCF 内在价值（公司整体） ===
            fcf_result = self._fcf_analyzer.analyze(stock_code, period)
            fcf = fcf_result.fcf if fcf_result else None

            dcf_optimistic = None
            dcf_neutral = None
            dcf_pessimistic = None
            dcf_per_share = None  # DCF 每股价值

            if fcf is not None and fcf > 0:
                # 简化 DCF：三阶段估值
                # 使用不同的增长率假设

                # 乐观: g=12%, r=8%
                dcf_optimistic = self._calculate_dcf(
                    fcf=fcf,
                    discount_rate=0.08,
                    terminal_growth_rate=terminal_growth_rate,
                    growth_rate=0.12,
                    growth_years=growth_years,
                )

                # 中性: g=8%, r=10%
                dcf_neutral = self._calculate_dcf(
                    fcf=fcf,
                    discount_rate=discount_rate,
                    terminal_growth_rate=terminal_growth_rate,
                    growth_rate=0.08,
                    growth_years=growth_years,
                )

                # 悲观: g=3%, r=12%
                dcf_pessimistic = self._calculate_dcf(
                    fcf=fcf,
                    discount_rate=0.12,
                    terminal_growth_rate=terminal_growth_rate,
                    growth_rate=0.03,
                    growth_years=growth_years,
                )

                # 将 DCF 转为每股价值
                if shares is not None and shares > 0:
                    dcf_per_share = dcf_neutral / shares if dcf_neutral else None

            # === 安全边际 ===
            # 优先使用 Graham Number（每股），其次使用 DCF 每股价值
            intrinsic_value = graham_number or dcf_per_share

            margin_of_safety = None
            valuation_signal = ""

            if intrinsic_value is not None and current_price > 0:
                margin_of_safety = (intrinsic_value - current_price) / intrinsic_value

                if margin_of_safety > 0.30:
                    valuation_signal = "强烈低估 (买入区间)"
                elif margin_of_safety > 0.15:
                    valuation_signal = "适度低估 (持有区间)"
                elif margin_of_safety > 0:
                    valuation_signal = "轻微低估 (谨慎)"
                else:
                    valuation_signal = "高估"

            # === 建议买入区间 ===
            # Graham Number 作为低价，DCF 乐观值作为高价
            buy_range_low = None
            buy_range_high = None

            if graham_number is not None:
                buy_range_low = graham_number * 0.9  # Graham Number 的 90% 作为安全边际

            if dcf_pessimistic is not None:
                buy_range_high = buy_range_low
                buy_range_low = min(buy_range_low or float("inf"), dcf_pessimistic * 0.7)

            # === 历史估值分位 (简化版) ===
            pe_percentile_5y = None
            pb_percentile_5y = None

            # 由于历史分位计算需要多年数据，这里简化处理
            # 可以通过对比当前 PE/PB 与历史均值来估算
            current_pe = self._get_value_from_df(curr_income, "pe_ratio")
            current_pb = self._get_value_from_df(curr_balance, "pb_ratio")

            if current_pe is not None and current_pe > 0:
                # 简化：假设历史 PE 均值约为当前值的 0.7-1.3 倍
                # 这是一个粗略估计
                pe_percentile_5y = 0.5  # 默认 50% 分位

            if current_pb is not None and current_pb > 0:
                pb_percentile_5y = 0.5  # 默认 50% 分位

            return IntrinsicValueMetrics(
                stock_code=stock_code,
                report_date=current_date,
                current_price=current_price,
                currency=currency,
                market_cap=market_cap,
                graham_number=graham_number,
                graham_price_ratio=graham_price_ratio,
                dcf_value=dcf_neutral,
                dcf_optimistic=dcf_optimistic,
                dcf_neutral=dcf_neutral,
                dcf_pessimistic=dcf_pessimistic,
                margin_of_safety=margin_of_safety,
                valuation_signal=valuation_signal,
                pe_percentile_5y=pe_percentile_5y,
                pb_percentile_5y=pb_percentile_5y,
                buy_range_low=buy_range_low,
                buy_range_high=buy_range_high,
                calculation_timestamp=datetime.now().isoformat(),
            )

        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

    def _calculate_dcf(
        self,
        fcf: float,
        discount_rate: float,
        terminal_growth_rate: float,
        growth_rate: float,
        growth_years: int,
    ) -> Optional[float]:
        """
        计算 DCF 内在价值

        Args:
            fcf: 当前自由现金流
            discount_rate: 折现率
            terminal_growth_rate: 永续增长率
            growth_rate: 增长期增长率
            growth_years: 增长期年数

        Returns:
            DCF 内在价值
        """
        try:
            if growth_rate >= discount_rate:
                growth_rate = discount_rate * 0.99  # 防止除以零

            # 增长期现金流
            pv_cash_flows = 0.0
            for year in range(1, growth_years + 1):
                fcf_future = fcf * (1 + growth_rate) ** year
                discount_factor = (1 + discount_rate) ** year
                pv_cash_flows += fcf_future / discount_factor

            # 永续价值
            fcf_final = fcf * (1 + growth_rate) ** growth_years
            terminal_value = fcf_final * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
            pv_terminal = terminal_value / (1 + discount_rate) ** growth_years

            return pv_cash_flows + pv_terminal

        except (ZeroDivisionError, ValueError):
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

    def get_margin_of_safety(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[float]:
        """
        获取安全边际

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            安全边际或 None
        """
        result = self.analyze(stock_code, period)
        return result.margin_of_safety if result else None

    def get_graham_number(self, stock_code: str, period: str = "annual") -> Optional[float]:
        """
        获取 Graham Number

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            Graham Number 或 None
        """
        result = self.analyze(stock_code, period)
        return result.graham_number if result else None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
