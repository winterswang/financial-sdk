"""
Piotroski F-Score 财务健康度评分

Piotroski F-Score 是价值投资者最常用的财务健康度评分系统，
用 9 个简单指标判断一家公司财务是否健康。分数 0-9，>7 为健康，<3 为危险。

参考: Piotroski, Joseph D. (2000) "Value Investing: The Use of Historical Financial
Statement Information to Separate Winners from Losers", Journal of Accounting Research.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .analytics_base import BaseAnalyzer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..facade import FinancialFacade  # noqa: F401



@dataclass
class PiotroskiDetail:
    """Piotroski 评分详情"""

    metric: str
    name: str
    score: int  # 0 或 1
    value: Optional[float] = None
    previous_value: Optional[float] = None
    condition: str = ""


@dataclass
class PiotroskiMetrics:
    """
    Piotroski F-Score 指标

    Attributes:
        stock_code: 股票代码
        report_date: 报告日期

        # 总分
        f_score: 总分 (0-9)

        # 分项得分
        profitability_score: 盈利能力得分 (0-4)
        leverage_score: 杠杆得分 (0-2)
        efficiency_score: 效率得分 (0-3)

        # 评估
        assessment: 评估结果 ("strong", "good", "average", "weak")
        assessment_description: 评估描述

        # 详细指标
        details: 评分详情列表

        # 计算时间
        calculation_timestamp: 计算时间
    """

    stock_code: str
    report_date: str

    # 总分
    f_score: int = 0

    # 分项得分
    profitability_score: int = 0
    leverage_score: int = 0
    efficiency_score: int = 0

    # 评估
    assessment: str = ""
    assessment_description: str = ""

    # 详细指标
    details: Optional[List[PiotroskiDetail]] = None

    # 计算时间
    calculation_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "report_date": self.report_date,
            "f_score": self.f_score,
            "profitability_score": self.profitability_score,
            "leverage_score": self.leverage_score,
            "efficiency_score": self.efficiency_score,
            "assessment": self.assessment,
            "assessment_description": self.assessment_description,
            "details": [
                {
                    "metric": d.metric,
                    "name": d.name,
                    "score": d.score,
                    "value": d.value,
                    "previous_value": d.previous_value,
                    "condition": d.condition,
                }
                for d in (self.details or [])
            ],
            "calculation_timestamp": self.calculation_timestamp,
        }

    def get_summary(self) -> str:
        """
        获取评分摘要

        Returns:
            格式化的摘要字符串
        """
        lines = [
            f"Piotroski F-Score: {self.f_score}/9",
            f"  - 盈利能力: {self.profitability_score}/4",
            f"  - 杠杆: {self.leverage_score}/2",
            f"  - 效率: {self.efficiency_score}/3",
            f"  - 评估: {self.assessment.upper()} ({self.assessment_description})",
        ]
        return "\n".join(lines)


class PiotroskiAnalyzer(BaseAnalyzer):
    """
    Piotroski F-Score 分析器

    使用 9 个财务指标评估公司财务健康度：

    盈利能力指标 (Profitability, 0-4分):
    1. Net Income > 0
    2. Operating Cash Flow > 0
    3. ROA 当年 > ROA 上年
    4. Operating Cash Flow > Net Income

    杠杆/流动性指标 (Leverage/ Liquidity, 0-2分):
    5. 长期负债/总资产 当年 < 上年
    6. Current Ratio 当年 > 上年 (需要 current_assets/current_liabilities)

    运营效率指标 (Efficiency, 0-3分):
    7. 股数未增加 (shares outstanding 未增加)
    8. Gross Margin 当年 > 上年
    9. Asset Turnover 当年 > 上年

    评分结果:
    - 8-9: Strong (强烈推荐)
    - 6-7: Good (推荐)
    - 4-5: Average (中性)
    - 0-3: Weak (不推荐)

    使用示例:
        analyzer = PiotroskiAnalyzer()
        result = analyzer.analyze("600519.SH")
        print(f"F-Score: {result.f_score}")
        print(result.get_summary())
    """

    def __init__(self, financial_facade: Optional["FinancialFacade"] = None) -> None:
        """
        初始化 Piotroski 分析器

        Args:
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)

    @property
    def analyzer_name(self) -> str:
        return "piotroski_analyzer"

    def analyze(
        self, stock_code: str, period: str = "annual"
    ) -> Optional[PiotroskiMetrics]:
        """
        分析 Piotroski F-Score

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            PiotroskiMetrics 或 None
        """
        try:
            # 获取多年财务数据用于对比
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )

            income = bundle.income_statement
            balance = bundle.balance_sheet
            cash_flow = bundle.cash_flow

            if income is None or income.empty:
                return None

            # 获取当前期和上期数据
            dates = sorted(
                income["report_date"].dropna().unique().tolist(),
                reverse=True,
            )
            if len(dates) < 2:
                # 只有一期数据，只能计算部分指标
                current_date = dates[0] if dates else "N/A"
                return self._analyze_single_period(
                    stock_code, current_date, income, balance, cash_flow
                )

            current_date = dates[0]
            previous_date = dates[1]

            return self._analyze_with_comparison(
                stock_code, current_date, previous_date, income, balance, cash_flow
            )

        except Exception:
            return None

    def _analyze_single_period(
        self,
        stock_code: str,
        report_date: str,
        income: Any,
        balance: Any,
        cash_flow: Any,
    ) -> Optional[PiotroskiMetrics]:
        """单期分析（无法做年度对比）"""
        details: List[PiotroskiDetail] = []
        profitability_score = 0
        leverage_score = 0
        efficiency_score = 0

        # 1. Net Income > 0
        net_profit = self._get_value(income, "net_profit")
        if net_profit and net_profit > 0:
            profitability_score += 1
            details.append(
                PiotroskiDetail(
                    metric="net_income_positive",
                    name="净利润为正",
                    score=1,
                    value=net_profit,
                    condition="Net Income > 0",
                )
            )
        else:
            details.append(
                PiotroskiDetail(
                    metric="net_income_positive",
                    name="净利润为正",
                    score=0,
                    value=net_profit,
                    condition="Net Income > 0",
                )
            )

        # 2. Operating Cash Flow > 0
        ocf = self._get_value(cash_flow, "operating_cash_flow")
        if ocf and ocf > 0:
            profitability_score += 1
            details.append(
                PiotroskiDetail(
                    metric="ocf_positive",
                    name="经营现金流为正",
                    score=1,
                    value=ocf,
                    condition="OCF > 0",
                )
            )
        else:
            details.append(
                PiotroskiDetail(
                    metric="ocf_positive",
                    name="经营现金流为正",
                    score=0,
                    value=ocf,
                    condition="OCF > 0",
                )
            )

        # 3-4. 需要上期数据，无法计算

        # 5. 杠杆指标（单期无法判断变化）
        total_assets = self._get_value(balance, "total_assets")
        total_liabilities = self._get_value(balance, "total_liabilities")
        if total_liabilities is not None and total_assets is not None and total_assets > 0:
            leverage_ratio = total_liabilities / total_assets
            if leverage_ratio < 0.5:  # 简单判断：负债率<50%
                leverage_score += 1
                details.append(
                    PiotroskiDetail(
                        metric="low_leverage",
                        name="低负债率",
                        score=1,
                        value=leverage_ratio,
                        condition="Debt/Assets < 0.5 (单期)",
                    )
                )
            else:
                details.append(
                    PiotroskiDetail(
                        metric="low_leverage",
                        name="低负债率",
                        score=0,
                        value=leverage_ratio,
                        condition="Debt/Assets < 0.5 (单期)",
                    )
                )

        # 6-9. 需要上期数据，无法计算

        f_score = profitability_score + leverage_score + efficiency_score

        return self._create_metrics(
            stock_code=stock_code,
            report_date=report_date,
            f_score=f_score,
            profitability_score=profitability_score,
            leverage_score=leverage_score,
            efficiency_score=efficiency_score,
            details=details,
        )

    def _analyze_with_comparison(
        self,
        stock_code: str,
        current_date: str,
        previous_date: str,
        income: Any,
        balance: Any,
        cash_flow: Any,
    ) -> Optional[PiotroskiMetrics]:
        """带年度对比的分析"""
        details: List[PiotroskiDetail] = []
        profitability_score = 0
        leverage_score = 0
        efficiency_score = 0

        # 获取当前期数据
        curr_income = income[income["report_date"] == current_date]
        curr_balance = balance[balance["report_date"] == current_date]
        curr_cash_flow = cash_flow[cash_flow["report_date"] == current_date]

        # 获取上期数据
        prev_income = income[income["report_date"] == previous_date]
        prev_balance = balance[balance["report_date"] == previous_date]

        # === 盈利能力指标 (0-4分) ===

        # 1. Net Income > 0
        curr_net_profit = self._get_value_from_df(curr_income, "net_profit")
        if curr_net_profit is not None and curr_net_profit > 0:
            profitability_score += 1
            score = 1
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="net_income_positive",
                name="净利润为正",
                score=score,
                value=curr_net_profit,
                condition="Net Income > 0",
            )
        )

        # 2. Operating Cash Flow > 0
        curr_ocf = self._get_value_from_df(curr_cash_flow, "operating_cash_flow")
        if curr_ocf is not None and curr_ocf > 0:
            profitability_score += 1
            score = 1
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="ocf_positive",
                name="经营现金流为正",
                score=score,
                value=curr_ocf,
                condition="OCF > 0",
            )
        )

        # 3. ROA 当年 > ROA 上年
        curr_roa = self._get_value_from_df(curr_income, "roa")
        if curr_roa is None:
            # 尝试计算 ROA
            curr_net_profit_val = self._get_value_from_df(curr_income, "net_profit")
            curr_assets = self._get_value_from_df(curr_balance, "total_assets")
            if curr_net_profit_val is not None and curr_assets is not None and curr_assets > 0:
                curr_roa = curr_net_profit_val / curr_assets

        prev_roa = self._get_value_from_df(prev_income, "roa")
        if prev_roa is None:
            prev_net_profit = self._get_value_from_df(prev_income, "net_profit")
            prev_assets = self._get_value_from_df(prev_balance, "total_assets")
            if prev_net_profit is not None and prev_assets is not None and prev_assets > 0:
                prev_roa = prev_net_profit / prev_assets

        if curr_roa is not None and prev_roa is not None and curr_roa > prev_roa:
            profitability_score += 1
            score = 1
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="roa_improved",
                name="ROA提升",
                score=score,
                value=curr_roa,
                previous_value=prev_roa,
                condition="ROA current > ROA previous",
            )
        )

        # 4. Operating Cash Flow > Net Income
        if curr_ocf is not None and curr_net_profit is not None:
            if curr_ocf > curr_net_profit:
                profitability_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="ocf_gt_net_income",
                name="现金流优于净利润",
                score=score,
                value=curr_ocf,
                previous_value=curr_net_profit,
                condition="OCF > Net Income",
            )
        )

        # === 杠杆/流动性指标 (0-2分) ===

        # 5. 长期负债/总资产 当年 < 上年
        curr_debt_ratio = None
        prev_debt_ratio = None

        curr_liabilities = self._get_value_from_df(curr_balance, "total_liabilities")
        curr_assets = self._get_value_from_df(curr_balance, "total_assets")
        prev_liabilities = self._get_value_from_df(prev_balance, "total_liabilities")
        prev_assets = self._get_value_from_df(prev_balance, "total_assets")

        if curr_liabilities is not None and curr_assets is not None and curr_assets > 0:
            curr_debt_ratio = curr_liabilities / curr_assets
        if prev_liabilities is not None and prev_assets is not None and prev_assets > 0:
            prev_debt_ratio = prev_liabilities / prev_assets

        if curr_debt_ratio is not None and prev_debt_ratio is not None:
            if curr_debt_ratio < prev_debt_ratio:
                leverage_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="leverage_improved",
                name="负债率下降",
                score=score,
                value=curr_debt_ratio,
                previous_value=prev_debt_ratio,
                condition="Debt ratio decreased",
            )
        )

        # 6. Current Ratio 当年 > 上年 (如果数据可用)
        curr_current_ratio = None
        prev_current_ratio = None

        curr_current_assets = self._get_value_from_df(curr_balance, "current_assets")
        curr_current_liab = self._get_value_from_df(curr_balance, "current_liabilities")
        prev_current_assets = self._get_value_from_df(prev_balance, "current_assets")
        prev_current_liab = self._get_value_from_df(prev_balance, "current_liabilities")

        if curr_current_assets is not None and curr_current_liab is not None and curr_current_liab > 0:
            curr_current_ratio = curr_current_assets / curr_current_liab
        if prev_current_assets is not None and prev_current_liab is not None and prev_current_liab > 0:
            prev_current_ratio = prev_current_assets / prev_current_liab

        if curr_current_ratio is not None and prev_current_ratio is not None:
            if curr_current_ratio > prev_current_ratio:
                leverage_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0  # 数据不可用，得0分
        details.append(
            PiotroskiDetail(
                metric="current_ratio_improved",
                name="流动比率提升",
                score=score,
                value=curr_current_ratio,
                previous_value=prev_current_ratio,
                condition="Current Ratio improved (may lack data)",
            )
        )

        # === 运营效率指标 (0-3分) ===

        # 7. 股数未增加（使用 equity_per_share 估算）
        curr_bvps = self._get_value_from_df(curr_balance, "bvps")
        prev_bvps = self._get_value_from_df(prev_balance, "bvps")

        # 如果 BVPS 提升，说明股数未增加（权益增加但股数不变）
        if curr_bvps is not None and prev_bvps is not None and prev_bvps > 0:
            if curr_bvps >= prev_bvps:
                efficiency_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="no_share_dilution",
                name="无股份稀释",
                score=score,
                value=curr_bvps,
                previous_value=prev_bvps,
                condition="BVPS increased (no dilution)",
            )
        )

        # 8. Gross Margin 当年 > 上年
        curr_gross_margin = self._get_value_from_df(curr_income, "gross_margin")
        prev_gross_margin = self._get_value_from_df(prev_income, "gross_margin")

        if curr_gross_margin is not None and prev_gross_margin is not None:
            if curr_gross_margin > prev_gross_margin:
                efficiency_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="gross_margin_improved",
                name="毛利率提升",
                score=score,
                value=curr_gross_margin,
                previous_value=prev_gross_margin,
                condition="Gross Margin improved",
            )
        )

        # 9. Asset Turnover 当年 > 上年
        curr_asset_turnover = self._get_value_from_df(curr_balance, "资产周转率")
        if curr_asset_turnover is None:
            # 尝试从 income 计算
            curr_revenue = self._get_value_from_df(curr_income, "revenue")
            if curr_revenue is not None and curr_assets is not None and curr_assets > 0:
                curr_asset_turnover = curr_revenue / curr_assets

        prev_asset_turnover = self._get_value_from_df(prev_balance, "资产周转率")
        if prev_asset_turnover is None:
            prev_revenue = self._get_value_from_df(prev_income, "revenue")
            if prev_revenue is not None and prev_assets is not None and prev_assets > 0:
                prev_asset_turnover = prev_revenue / prev_assets

        if curr_asset_turnover is not None and prev_asset_turnover is not None:
            if curr_asset_turnover > prev_asset_turnover:
                efficiency_score += 1
                score = 1
            else:
                score = 0
        else:
            score = 0
        details.append(
            PiotroskiDetail(
                metric="asset_turnover_improved",
                name="资产周转率提升",
                score=score,
                value=curr_asset_turnover,
                previous_value=prev_asset_turnover,
                condition="Asset Turnover improved",
            )
        )

        f_score = profitability_score + leverage_score + efficiency_score

        return self._create_metrics(
            stock_code=stock_code,
            report_date=current_date,
            f_score=f_score,
            profitability_score=profitability_score,
            leverage_score=leverage_score,
            efficiency_score=efficiency_score,
            details=details,
        )

    def _create_metrics(
        self,
        stock_code: str,
        report_date: str,
        f_score: int,
        profitability_score: int,
        leverage_score: int,
        efficiency_score: int,
        details: List[PiotroskiDetail],
    ) -> PiotroskiMetrics:
        """创建 PiotroskiMetrics 对象"""
        # 评估
        if f_score >= 8:
            assessment = "strong"
            assessment_description = "强烈推荐"
        elif f_score >= 6:
            assessment = "good"
            assessment_description = "推荐"
        elif f_score >= 4:
            assessment = "average"
            assessment_description = "中性"
        else:
            assessment = "weak"
            assessment_description = "不推荐"

        return PiotroskiMetrics(
            stock_code=stock_code,
            report_date=report_date,
            f_score=f_score,
            profitability_score=profitability_score,
            leverage_score=leverage_score,
            efficiency_score=efficiency_score,
            assessment=assessment,
            assessment_description=assessment_description,
            details=details,
            calculation_timestamp=datetime.now().isoformat(),
        )

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

    def get_f_score(self, stock_code: str, period: str = "annual") -> Optional[int]:
        """
        获取 F-Score

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            F-Score (0-9) 或 None
        """
        result = self.analyze(stock_code, period)
        return result.f_score if result else None

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        result = super().health_check()
        result["facade_available"] = result["status"] == "healthy"
        return result
