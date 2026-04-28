"""
财务分析统一入口

提供一站式的财务分析接口，整合所有分析器的能力。
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from .efficiency import EfficiencyAnalyzer, EfficiencyMetrics
from .growth import GrowthAnalyzer, GrowthMetrics
from .profitability import ProfitabilityAnalyzer, ProfitabilityMetrics
from .safety import SafetyAnalyzer, SafetyMetrics
from .valuation import ValuationAnalyzer, ValuationMetrics

logger = logging.getLogger(__name__)


@dataclass
class FullAnalysisReport:
    """
    完整财务分析报告

    整合所有维度的分析结果。
    """

    stock_code: str
    report_date: str
    valuation: Optional[ValuationMetrics]
    profitability: Optional[ProfitabilityMetrics]
    efficiency: Optional[EfficiencyMetrics]
    growth: Optional[GrowthMetrics]
    safety: Optional[SafetyMetrics]
    analysis_timestamp: str = ""
    failed_dimensions: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "valuation": self.valuation.to_dict() if self.valuation else None,
            "profitability": self.profitability.to_dict()
            if self.profitability
            else None,
            "efficiency": self.efficiency.to_dict() if self.efficiency else None,
            "growth": self.growth.to_dict() if self.growth else None,
            "safety": self.safety.to_dict() if self.safety else None,
            "analysis_timestamp": self.analysis_timestamp,
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        获取分析摘要

        Returns:
            关键指标摘要
        """
        summary = {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
        }

        if self.valuation:
            summary["pe"] = self.valuation.pe_ratio
            summary["pb"] = self.valuation.pb_ratio
            summary["market_cap"] = self.valuation.market_cap

        if self.profitability:
            summary["roe"] = self.profitability.roe
            summary["net_margin"] = self.profitability.net_margin
            summary["gross_margin"] = self.profitability.gross_margin

        if self.efficiency:
            summary["cash_conversion_cycle"] = self.efficiency.cash_conversion_cycle

        if self.growth:
            summary["revenue_growth"] = self.growth.revenue_growth_yoy
            summary["profit_growth"] = self.growth.profit_growth_yoy

        if self.safety:
            summary["current_ratio"] = self.safety.current_ratio
            summary["altman_z"] = self.safety.altman_z_score

        return summary

    def get_score(self) -> float:
        """
        计算综合评分 (0-100)

        基于各维度指标计算综合评分。
        仅作为参考。

        Returns:
            综合评分
        """
        score = 50.0  # 基础分

        # ROE 评分 (最高 +20)
        if self.profitability and self.profitability.roe:
            roe = self.profitability.roe
            if roe > 0.20:
                score += 20
            elif roe > 0.15:
                score += 15
            elif roe > 0.10:
                score += 10
            elif roe > 0.05:
                score += 5

        # 成长性评分 (最高 +15)
        if self.growth and self.growth.revenue_growth_yoy:
            growth = self.growth.revenue_growth_yoy
            if growth > 0.30:
                score += 15
            elif growth > 0.15:
                score += 10
            elif growth > 0:
                score += 5

        # 安全性评分 (最高 +15)
        if self.safety and self.safety.altman_z_score:
            z = self.safety.altman_z_score
            if z > 2.99:
                score += 15
            elif z > 1.81:
                score += 10

        return min(100.0, max(0.0, score))

    def pretty_print(self) -> str:
        """
        美观地打印分析报告

        Returns:
            格式化的报告字符串
        """
        lines = []
        width = 60

        # 头部
        lines.append("=" * width)
        lines.append(f"  Financial Analysis Report: {self.stock_code}")
        lines.append(f"  Report Date: {self.report_date}")
        lines.append(f"  Analysis Score: {self.get_score():.1f}/100")
        lines.append("=" * width)

        # 估值指标
        if self.valuation:
            lines.append("\n📊 VALUATION METRICS (估值指标)")
            lines.append("-" * width)
            v = self.valuation
            lines.append(
                f"  Current Price: {v.current_price} {v.currency}"
                if v.current_price
                else "  Current Price: N/A"
            )
            lines.append(
                f"  P/E Ratio: {v.pe_ratio:.2f}" if v.pe_ratio else "  P/E Ratio: N/A"
            )
            lines.append(
                f"  P/B Ratio: {v.pb_ratio:.2f}" if v.pb_ratio else "  P/B Ratio: N/A"
            )
            lines.append(
                f"  P/S Ratio: {v.ps_ratio:.2f}" if v.ps_ratio else "  P/S Ratio: N/A"
            )
            lines.append(
                f"  Market Cap: {self._format_market_cap(v.market_cap)}"
                if v.market_cap
                else "  Market Cap: N/A"
            )
            lines.append(
                f"  Dividend Yield: {v.dividend_yield * 100:.2f}%"
                if v.dividend_yield
                else "  Dividend Yield: N/A"
            )
        else:
            lines.append("\n📊 VALUATION METRICS (估值指标)")
            lines.append("-" * width)
            reason = self._get_dimension_reason("valuation")
            lines.append(f"  ⚠️ 数据不可用: {reason}")

        # 盈利能力
        if self.profitability:
            lines.append("\n📈 PROFITABILITY (盈利能力)")
            lines.append("-" * width)
            p = self.profitability
            lines.append(f"  ROE: {p.roe * 100:.2f}%" if p.roe else "  ROE: N/A")
            lines.append(f"  ROA: {p.roa * 100:.2f}%" if p.roa else "  ROA: N/A")
            lines.append(f"  ROIC: {p.roic * 100:.2f}%" if p.roic else "  ROIC: N/A")
            lines.append(
                f"  Gross Margin: {p.gross_margin * 100:.2f}%"
                if p.gross_margin
                else "  Gross Margin: N/A"
            )
            lines.append(
                f"  Net Margin: {p.net_margin * 100:.2f}%"
                if p.net_margin
                else "  Net Margin: N/A"
            )
            # DuPont 分解
            if p.dupont_roe is not None:
                lines.append("\n  DuPont Analysis:")
                lines.append(
                    f"    Net Margin: {p.dupont_net_margin * 100:.2f}%"
                    if p.dupont_net_margin
                    else "    Net Margin: N/A"
                )
                lines.append(
                    f"    Asset Turnover: {p.dupont_asset_turnover:.2f}"
                    if p.dupont_asset_turnover
                    else "    Asset Turnover: N/A"
                )
                lines.append(
                    f"    Equity Multiplier: {p.dupont_equity_multiplier:.2f}"
                    if p.dupont_equity_multiplier
                    else "    Equity Multiplier: N/A"
                )
        else:
            lines.append("\n📈 PROFITABILITY (盈利能力)")
            lines.append("-" * width)
            reason = self._get_dimension_reason("profitability")
            lines.append(f"  ⚠️ 数据不可用: {reason}")

        # 运营效率
        if self.efficiency:
            lines.append("\n⚡ EFFICIENCY (运营效率)")
            lines.append("-" * width)
            e = self.efficiency
            lines.append(
                f"  Cash Conversion Cycle: {e.cash_conversion_cycle:.1f} days"
                if e.cash_conversion_cycle
                else "  Cash Conversion Cycle: N/A"
            )
            lines.append(
                f"  Operating Cycle: {e.operating_cycle:.1f} days"
                if e.operating_cycle
                else "  Operating Cycle: N/A"
            )
            lines.append(f"  DIO: {e.dio:.1f} days" if e.dio else "  DIO: N/A")
            lines.append(f"  DSO: {e.dso:.1f} days" if e.dso else "  DSO: N/A")
            lines.append(f"  DPO: {e.dpo:.1f} days" if e.dpo else "  DPO: N/A")
        else:
            lines.append("\n⚡ EFFICIENCY (运营效率)")
            lines.append("-" * width)
            reason = self._get_dimension_reason("efficiency")
            lines.append(f"  ⚠️ 数据不可用: {reason}")

        # 成长性
        if self.growth:
            lines.append("\n📈 GROWTH (成长性)")
            lines.append("-" * width)
            g = self.growth
            lines.append(
                f"  Revenue Growth YoY: {g.revenue_growth_yoy * 100:.2f}%"
                if g.revenue_growth_yoy
                else "  Revenue Growth YoY: N/A"
            )
            lines.append(
                f"  Profit Growth YoY: {g.profit_growth_yoy * 100:.2f}%"
                if g.profit_growth_yoy
                else "  Profit Growth YoY: N/A"
            )
            lines.append(
                f"  Sustainable Growth: {g.sustainable_growth_rate * 100:.2f}%"
                if g.sustainable_growth_rate
                else "  Sustainable Growth: N/A"
            )
        else:
            lines.append("\n📈 GROWTH (成长性)")
            lines.append("-" * width)
            reason = self._get_dimension_reason("growth")
            lines.append(f"  ⚠️ 数据不可用: {reason}")

        # 财务安全
        if self.safety:
            lines.append("\n🛡️ SAFETY (财务安全)")
            lines.append("-" * width)
            s = self.safety
            lines.append(
                f"  Altman Z-Score: {s.altman_z_score:.2f}"
                if s.altman_z_score
                else "  Altman Z-Score: N/A"
            )
            if s.altman_z_interpretation:
                lines.append(f"    Interpretation: {s.altman_z_interpretation}")
            lines.append(
                f"  Current Ratio: {s.current_ratio:.2f}"
                if s.current_ratio
                else "  Current Ratio: N/A"
            )
            lines.append(
                f"  Quick Ratio: {s.quick_ratio:.2f}"
                if s.quick_ratio
                else "  Quick Ratio: N/A"
            )
            lines.append(
                f"  Interest Coverage: {s.interest_coverage:.2f}x"
                if s.interest_coverage
                else "  Interest Coverage: N/A"
            )
            lines.append(
                f"  Debt/Equity: {s.debt_to_equity:.2f}"
                if s.debt_to_equity
                else "  Debt/Equity: N/A"
            )
        else:
            lines.append("\n🛡️ SAFETY (财务安全)")
            lines.append("-" * width)
            reason = self._get_dimension_reason("safety")
            lines.append(f"  ⚠️ 数据不可用: {reason}")

        lines.append("\n" + "=" * width)
        return "\n".join(lines)

    @staticmethod
    def _format_market_cap(market_cap: Optional[float]) -> str:
        """格式化市值显示"""
        if market_cap is None:
            return "N/A"
        if market_cap >= 1e12:
            return f"{market_cap / 1e12:.2f}万亿"
        elif market_cap >= 1e8:
            return f"{market_cap / 1e8:.2f}亿"
        elif market_cap >= 1e4:
            return f"{market_cap / 1e4:.2f}万"
        else:
            return f"{market_cap:.2f}"

    _DIMENSION_REQUIRED_FIELDS = {
        "valuation": "需要 EPS/价格数据",
        "profitability": "需要 revenue/net_profit/total_equity 等利润表和资产负债表字段",
        "efficiency": "需要 inventory/accounts_receivable/accounts_payable 标准字段",
        "growth": "需要至少2期财务数据做 YoY 计算",
        "safety": "需要 current_assets/current_liabilities/total_equity 等资产负债表字段",
    }

    def _get_dimension_reason(self, dimension: str) -> str:
        """获取维度数据不可用的原因"""
        reason = self._DIMENSION_REQUIRED_FIELDS.get(dimension, "数据不完整")
        if self.failed_dimensions and dimension in self.failed_dimensions:
            return f"分析过程异常 ({reason})"
        return reason


class FinancialAnalytics:
    """
    财务分析统一入口

    整合 ValuationAnalyzer, ProfitabilityAnalyzer, EfficiencyAnalyzer,
    GrowthAnalyzer, SafetyAnalyzer，提供一站式财务分析服务。

    使用示例:
        analytics = FinancialAnalytics()

        # 获取完整分析报告
        report = analytics.get_full_report("600000.SH")
        print(f"综合评分: {report.get_score()}")

        # 获取特定维度分析
        valuation = analytics.get_valuation("600000.SH")
        profitability = analytics.get_profitability("600000.SH")

        # 获取单一指标
        pe = analytics.get_pe_ratio("600000.SH")
        roe = analytics.get_roe("600000.SH")
    """

    def __init__(
        self,
        price_provider=None,
        financial_facade=None,
    ) -> None:
        """
        初始化财务分析器

        Args:
            price_provider: 价格提供者
            financial_facade: 财务门面
        """
        self._valuation = ValuationAnalyzer(
            price_provider=price_provider,
            financial_facade=financial_facade,
        )
        self._profitability = ProfitabilityAnalyzer(
            financial_facade=financial_facade,
        )
        self._efficiency = EfficiencyAnalyzer(
            financial_facade=financial_facade,
        )
        self._growth = GrowthAnalyzer(
            financial_facade=financial_facade,
        )
        self._safety = SafetyAnalyzer(
            financial_facade=financial_facade,
            price_provider=price_provider,
        )

    @property
    def valuation_analyzer(self) -> ValuationAnalyzer:
        """获取估值分析器"""
        return self._valuation

    @property
    def profitability_analyzer(self) -> ProfitabilityAnalyzer:
        """获取盈利能力分析器"""
        return self._profitability

    @property
    def efficiency_analyzer(self) -> EfficiencyAnalyzer:
        """获取运营效率分析器"""
        return self._efficiency

    @property
    def growth_analyzer(self) -> GrowthAnalyzer:
        """获取成长性分析器"""
        return self._growth

    @property
    def safety_analyzer(self) -> SafetyAnalyzer:
        """获取财务安全分析器"""
        return self._safety

    def get_full_report(
        self,
        stock_code: str,
        period: str = "annual",
    ) -> Optional[FullAnalysisReport]:
        """
        获取完整财务分析报告

        当某个维度分析失败时，该维度返回 None 但不影响其他维度。

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            FullAnalysisReport 或 None (仅当所有维度都失败时返回 None)
        """
        failed_dims: List[str] = []

        valuation = None
        try:
            valuation = self._valuation.get_valuation_metrics(stock_code, period)
        except Exception:
            failed_dims.append("valuation")

        profitability = None
        try:
            profitability = self._profitability.get_profitability_metrics(
                stock_code, period
            )
        except Exception:
            failed_dims.append("profitability")

        efficiency = None
        try:
            efficiency = self._efficiency.get_efficiency_metrics(stock_code, period)
        except Exception:
            failed_dims.append("efficiency")

        growth = None
        try:
            growth = self._growth.get_growth_metrics(stock_code, period)
        except Exception:
            failed_dims.append("growth")

        safety = None
        try:
            safety = self._safety.get_safety_metrics(stock_code, period)
        except Exception:
            failed_dims.append("safety")

        # 所有维度都失败时返回 None
        if all(m is None for m in [valuation, profitability, efficiency, growth, safety]):
            logger.warning(
                f"Stock {stock_code} analysis failed for ALL dimensions: {failed_dims}"
            )
            return None

        # 确定报告日期
        report_date = "N/A"
        for m in [valuation, profitability, efficiency, growth, safety]:
            if m and hasattr(m, "report_date"):
                report_date = m.report_date
                break

        report = FullAnalysisReport(
            stock_code=stock_code,
            report_date=report_date,
            valuation=valuation,
            profitability=profitability,
            efficiency=efficiency,
            growth=growth,
            safety=safety,
            analysis_timestamp=datetime.now().isoformat(),
            failed_dimensions=failed_dims if failed_dims else None,
        )

        if failed_dims:
            logger.warning(
                f"Stock {stock_code} analysis failed for dimensions: {failed_dims}"
            )

        return report

    def get_multi_year_metrics(
        self,
        stock_code: str,
        period: str = "annual",
        years: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        获取多年财务指标（表格形式，指标为行，日期为列）

        估值指标只返回最新一期（因为需要实时价格）。
        财务报表指标（盈利能力、运营效率、成长性、财务安全）返回多年数据。

        Args:
            stock_code: 股票代码
            period: 报告期类型
            years: 要分析的年份列表，如 [2020, 2021, 2022, 2023, 2024]
                  如果为 None，则返回所有可用年份

        Returns:
            Dict with keys:
              - valuation: 最新估值指标
              - profitability: Dict[date, metrics]
              - efficiency: Dict[date, metrics]
              - growth: Dict[date, metrics]
              - safety: Dict[date, metrics]
              - report_dates: 所有可用日期列表
        """
        try:
            # 获取完整财务数据
            bundle = self._valuation._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )

            if bundle.income_statement is None or bundle.income_statement.empty:
                return {}

            # 获取所有可用日期
            if "report_date" not in bundle.income_statement.columns:
                return {}

            all_dates = sorted(
                bundle.income_statement["report_date"].dropna().unique().tolist(),
                reverse=True
            )

            # 过滤年份
            if years:
                filtered_dates = []
                for d in all_dates:
                    try:
                        year = int(str(d)[:4])
                        if year in years:
                            filtered_dates.append(d)
                    except (ValueError, IndexError):
                        pass
                all_dates = filtered_dates

            if not all_dates:
                return {}

            # 准备结果
            result: Dict[str, Any] = {
                "stock_code": stock_code,
                "report_dates": all_dates,
                "valuation": None,
                "profitability": {},
                "efficiency": {},
                "growth": {},
                "safety": {},
            }

            # 获取最新估值指标（只需要最新）
            result["valuation"] = self._valuation.get_valuation_metrics(stock_code, period)

            # 对每个日期分别计算财务报表指标
            for date in all_dates:
                # 为每个分析器创建单期数据
                period_bundle = self._create_period_bundle(bundle, date)
                if period_bundle is None:
                    continue

                # 创建临时门面来提供单期数据
                period_facade = _SinglePeriodFacade(period_bundle)

                # 盈利能力
                period_profitability = self._profitability._get_metrics_with_facade(
                    stock_code, period_facade
                )
                if period_profitability:
                    result["profitability"][date] = period_profitability

                # 运营效率
                period_efficiency = self._efficiency._get_metrics_with_facade(
                    stock_code, period_facade
                )
                if period_efficiency:
                    result["efficiency"][date] = period_efficiency

                # 成长性
                period_growth = self._growth._get_metrics_with_facade(
                    stock_code, period_facade
                )
                if period_growth:
                    result["growth"][date] = period_growth

                # 财务安全
                period_safety = self._safety._get_metrics_with_facade(
                    stock_code, period_facade
                )
                if period_safety:
                    result["safety"][date] = period_safety

            return result

        except Exception:
            return {}

    def _create_period_bundle(
        self, bundle: Any, date: str
    ) -> Optional[Any]:
        """从完整bundle中提取单个时期的数据"""
        try:
            from ..models import FinancialBundle

            period_bundle = FinancialBundle(
                stock_code=bundle.stock_code,
                market=bundle.market,
                currency=bundle.currency,
                data_period=bundle.data_period,
            )

            # 过滤每个DataFrame到指定日期
            for attr_name in ["income_statement", "balance_sheet", "cash_flow", "indicators"]:
                df = getattr(bundle, attr_name, None)
                if df is not None and not df.empty and "report_date" in df.columns:
                    filtered = df[df["report_date"] == date]
                    if not filtered.empty:
                        setattr(period_bundle, attr_name, filtered)

            return period_bundle
        except Exception:
            return None

    def get_valuation(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[ValuationMetrics]:
        """获取估值指标"""
        return self._valuation.get_valuation_metrics(stock_code, period)

    def get_profitability(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[ProfitabilityMetrics]:
        """获取盈利能力指标"""
        return self._profitability.get_profitability_metrics(stock_code, period)

    def get_efficiency(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[EfficiencyMetrics]:
        """获取运营效率指标"""
        return self._efficiency.get_efficiency_metrics(stock_code, period)

    def get_growth(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[GrowthMetrics]:
        """获取成长性指标"""
        return self._growth.get_growth_metrics(stock_code, period)

    def get_safety(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[SafetyMetrics]:
        """获取财务安全指标"""
        return self._safety.get_safety_metrics(stock_code, period)

    # 单一指标快捷方法

    def get_pe_ratio(self, stock_code: str) -> Optional[float]:
        """获取市盈率"""
        return self._valuation.get_pe_ratio(stock_code)

    def get_pb_ratio(self, stock_code: str) -> Optional[float]:
        """获取市净率"""
        return self._valuation.get_pb_ratio(stock_code)

    def get_market_cap(self, stock_code: str) -> Optional[float]:
        """获取总市值"""
        return self._valuation.get_market_cap(stock_code)

    def get_roe(self, stock_code: str) -> Optional[float]:
        """获取 ROE"""
        return self._profitability.get_roe(stock_code)

    def get_roic(self, stock_code: str) -> Optional[float]:
        """获取 ROIC"""
        return self._profitability.get_roic(stock_code)

    def get_gross_margin(self, stock_code: str) -> Optional[float]:
        """获取毛利率"""
        return self._profitability.get_gross_margin(stock_code)

    def get_cash_conversion_cycle(self, stock_code: str) -> Optional[float]:
        """获取现金周转周期"""
        return self._efficiency.get_cash_conversion_cycle(stock_code)

    def get_revenue_growth(self, stock_code: str) -> Optional[float]:
        """获取营收同比增长率"""
        return self._growth.get_revenue_growth(stock_code)

    def get_profit_growth(self, stock_code: str) -> Optional[float]:
        """获取净利润同比增长率"""
        return self._growth.get_profit_growth(stock_code)

    def get_current_ratio(self, stock_code: str) -> Optional[float]:
        """获取流动比率"""
        return self._safety.get_current_ratio(stock_code)

    def get_altman_z_score(self, stock_code: str) -> Optional[float]:
        """获取 Altman Z-Score"""
        return self._safety.get_altman_z_score(stock_code)

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "valuation_analyzer": self._valuation.health_check(),
            "profitability_analyzer": self._profitability.health_check(),
            "efficiency_analyzer": self._efficiency.health_check(),
            "growth_analyzer": self._growth.health_check(),
            "safety_analyzer": self._safety.health_check(),
        }


class _SinglePeriodFacade:
    """
    单期数据门面（用于多年分析）

    包装一个 FinancialBundle，仅返回指定时期的数据。
    """

    def __init__(self, bundle: Any) -> None:
        self._bundle = bundle

    def get_financial_data(
        self,
        stock_code: str,
        report_type: str = "all",
        period: str = "annual",
        force_refresh: bool = False,
    ) -> Any:
        """返回单期财务数据"""
        return self._bundle
