"""
指标计算引擎

提供财务指标的统一计算逻辑。
"""

from typing import Optional

import pandas as pd


class MetricsCalculator:
    """
    财务指标计算引擎

    提供基于财务报表数据计算各种财务指标的方法。
    """

    @staticmethod
    def calculate_pe_ratio(price: float, eps: Optional[float]) -> Optional[float]:
        """
        计算市盈率 (P/E Ratio)

        Args:
            price: 当前股价
            eps: 每股收益

        Returns:
            市盈率或 None
        """
        if eps is None or eps == 0:
            return None
        return price / eps

    @staticmethod
    def calculate_pb_ratio(
        price: float, total_equity: Optional[float], shares: Optional[float]
    ) -> Optional[float]:
        """
        计算市净率 (P/B Ratio)

        Args:
            price: 当前股价
            total_equity: 股东权益合计
            shares: 流通股本

        Returns:
            市净率或 None
        """
        if total_equity is None or shares is None or shares == 0:
            return None
        bvps = total_equity / shares
        if bvps == 0:
            return None
        return price / bvps

    @staticmethod
    def calculate_ps_ratio(
        price: float, revenue: Optional[float], shares: Optional[float]
    ) -> Optional[float]:
        """
        计算市销率 (P/S Ratio)

        Args:
            price: 当前股价
            revenue: 营业收入
            shares: 流通股本

        Returns:
            市销率或 None
        """
        if revenue is None or shares is None or shares == 0:
            return None
        ps = revenue / shares
        if ps == 0:
            return None
        return price / ps

    @staticmethod
    def calculate_peg_ratio(
        pe_ratio: Optional[float], growth_rate: Optional[float]
    ) -> Optional[float]:
        """
        计算PEG比率

        Args:
            pe_ratio: 市盈率
            growth_rate: 净利润增长率 (如 0.2 表示 20%)

        Returns:
            PEG比率或 None
        """
        if pe_ratio is None or growth_rate is None or growth_rate == 0:
            return None
        return pe_ratio / (growth_rate * 100)

    @staticmethod
    def calculate_ev_ebitda(
        market_cap: Optional[float],
        total_debt: Optional[float],
        cash: Optional[float],
        ebitda: Optional[float],
    ) -> Optional[float]:
        """
        计算 EV/EBITDA

        Args:
            market_cap: 总市值
            total_debt: 总债务
            cash: 现金及等价物
            ebitda: EBITDA

        Returns:
            EV/EBITDA 或 None
        """
        if ebitda is None or ebitda == 0:
            return None

        ev = (market_cap or 0) + (total_debt or 0) - (cash or 0)
        return ev / ebitda

    @staticmethod
    def calculate_dividend_yield(dps: Optional[float], price: float) -> Optional[float]:
        """
        计算股息率

        Args:
            dps: 每股股息
            price: 当前股价

        Returns:
            股息率或 None
        """
        if dps is None or price is None or price == 0:
            return None
        return dps / price

    @staticmethod
    def calculate_dupont_roa(
        net_profit: Optional[float], total_assets: Optional[float]
    ) -> Optional[float]:
        """
        计算资产回报率 (ROA)

        Args:
            net_profit: 净利润
            total_assets: 总资产

        Returns:
            ROA 或 None
        """
        if net_profit is None or total_assets is None or total_assets == 0:
            return None
        return net_profit / total_assets

    @staticmethod
    def calculate_dupont_roe(
        net_profit: Optional[float], total_equity: Optional[float]
    ) -> Optional[float]:
        """
        计算股东权益回报率 (ROE)

        Args:
            net_profit: 净利润
            total_equity: 股东权益

        Returns:
            ROE 或 None
        """
        if net_profit is None or total_equity is None or total_equity == 0:
            return None
        return net_profit / total_equity

    @staticmethod
    def calculate_net_margin(
        net_profit: Optional[float], revenue: Optional[float]
    ) -> Optional[float]:
        """
        计算净利率

        Args:
            net_profit: 净利润
            revenue: 营业收入

        Returns:
            净利率或 None
        """
        if net_profit is None or revenue is None or revenue == 0:
            return None
        return net_profit / revenue

    @staticmethod
    def calculate_gross_margin(
        gross_profit: Optional[float], revenue: Optional[float]
    ) -> Optional[float]:
        """
        计算毛利率

        Args:
            gross_profit: 毛利
            revenue: 营业收入

        Returns:
            毛利率或 None
        """
        if gross_profit is None or revenue is None or revenue == 0:
            return None
        return gross_profit / revenue

    @staticmethod
    def calculate_current_ratio(
        current_assets: Optional[float], current_liabilities: Optional[float]
    ) -> Optional[float]:
        """
        计算流动比率

        Args:
            current_assets: 流动资产
            current_liabilities: 流动负债

        Returns:
            流动比率或 None
        """
        if (
            current_assets is None
            or current_liabilities is None
            or current_liabilities == 0
        ):
            return None
        return current_assets / current_liabilities

    @staticmethod
    def calculate_quick_ratio(
        current_assets: Optional[float],
        inventory: Optional[float],
        current_liabilities: Optional[float],
    ) -> Optional[float]:
        """
        计算速动比率

        Args:
            current_assets: 流动资产
            inventory: 存货
            current_liabilities: 流动负债

        Returns:
            速动比率或 None
        """
        if (
            current_assets is None
            or current_liabilities is None
            or current_liabilities == 0
        ):
            return None
        quick_assets = current_assets - (inventory or 0)
        return quick_assets / current_liabilities

    @staticmethod
    def calculate_yoy_growth(
        current: Optional[float], previous: Optional[float]
    ) -> Optional[float]:
        """
        计算同比增长率

        Args:
            current: 本期值
            previous: 上期值

        Returns:
            增长率 (如 0.2 表示 20%) 或 None
        """
        if current is None or previous is None or previous == 0:
            return None
        return (current - previous) / abs(previous)

    @staticmethod
    def get_latest_value(df: pd.DataFrame, field: str) -> Optional[float]:
        """
        从 DataFrame 获取最新一期指定字段的值

        Args:
            df: 财务报表 DataFrame
            field: 字段名

        Returns:
            最新值或 None
        """
        if df is None or df.empty:
            return None

        if field not in df.columns:
            return None

        # 按日期排序，取最新一期
        if "report_date" in df.columns:
            df = df.sort_values("report_date", ascending=False)

        values = df[field].dropna()
        if values.empty:
            return None

        return float(values.iloc[0])

    # ==================== P1: 盈利能力分析 ====================

    @staticmethod
    def calculate_asset_turnover(
        revenue: Optional[float], total_assets: Optional[float]
    ) -> Optional[float]:
        """
        计算资产周转率

        Args:
            revenue: 营业收入
            total_assets: 总资产

        Returns:
            资产周转率或 None
        """
        if revenue is None or total_assets is None or total_assets == 0:
            return None
        return revenue / total_assets

    @staticmethod
    def calculate_equity_multiplier(
        total_assets: Optional[float], total_equity: Optional[float]
    ) -> Optional[float]:
        """
        计算权益乘数

        Args:
            total_assets: 总资产
            total_equity: 股东权益

        Returns:
            权益乘数或 None
        """
        if total_assets is None or total_equity is None or total_equity == 0:
            return None
        return total_assets / total_equity

    @staticmethod
    def calculate_dupont_decomposition(
        net_profit: Optional[float],
        revenue: Optional[float],
        total_assets: Optional[float],
        total_equity: Optional[float],
    ) -> Optional[dict]:
        """
        DuPont 分解

        ROE = 净利率 × 资产周转率 × 权益乘数
             = (Net_Profit/Revenue) × (Revenue/Assets) × (Assets/Equity)

        Args:
            net_profit: 净利润
            revenue: 营业收入
            total_assets: 总资产
            total_equity: 股东权益

        Returns:
            Dict 包含 net_margin, asset_turnover, equity_multiplier, roe 或 None
        """
        if any(v is None for v in [net_profit, revenue, total_assets, total_equity]):
            return None
        if total_equity == 0 or revenue == 0 or total_assets == 0:
            return None

        net_margin = net_profit / revenue
        asset_turnover = revenue / total_assets
        equity_multiplier = total_assets / total_equity
        roe = net_margin * asset_turnover * equity_multiplier

        return {
            "net_margin": net_margin,
            "asset_turnover": asset_turnover,
            "equity_multiplier": equity_multiplier,
            "roe": roe,
        }

    @staticmethod
    def calculate_roic(
        ebit: Optional[float],
        tax_rate: Optional[float],
        total_debt: Optional[float],
        cash: Optional[float],
        total_equity: Optional[float],
    ) -> Optional[float]:
        """
        计算 ROIC (投资资本回报率)

        ROIC = EBIT(1 - Tax_Rate) / Invested_Capital
             = EBIT(1 - Tax_Rate) / (Debt + Equity - Cash)

        Args:
            ebit: 息税前利润
            tax_rate: 税率 (如 0.25 表示 25%)
            total_debt: 总债务
            cash: 现金及等价物
            total_equity: 股东权益

        Returns:
            ROIC 或 None
        """
        if ebit is None or total_debt is None or total_equity is None:
            return None

        if tax_rate is None:
            tax_rate = 0.25  # 默认税率

        invested_capital = total_debt + total_equity - (cash or 0)
        if invested_capital == 0:
            return None

        return ebit * (1 - tax_rate) / invested_capital

    # ==================== P2: 运营效率分析 ====================

    @staticmethod
    def calculate_dio(
        inventory: Optional[float], cogs: Optional[float], days: int = 360
    ) -> Optional[float]:
        """
        计算存货周转天数 (Days Inventory Outstanding)

        DIO = Inventory / COGS × Days

        Args:
            inventory: 存货
            cogs: 营业成本
            days: 天数 (默认360)

        Returns:
            存货周转天数或 None
        """
        if inventory is None or cogs is None or cogs == 0:
            return None
        return (inventory / cogs) * days

    @staticmethod
    def calculate_dso(
        accounts_receivable: Optional[float], revenue: Optional[float], days: int = 360
    ) -> Optional[float]:
        """
        计算应收账款周转天数 (Days Sales Outstanding)

        DSO = Accounts_Receivable / Revenue × Days

        Args:
            accounts_receivable: 应收账款
            revenue: 营业收入
            days: 天数 (默认360)

        Returns:
            应收账款周转天数或 None
        """
        if accounts_receivable is None or revenue is None or revenue == 0:
            return None
        return (accounts_receivable / revenue) * days

    @staticmethod
    def calculate_dpo(
        accounts_payable: Optional[float], cogs: Optional[float], days: int = 360
    ) -> Optional[float]:
        """
        计算应付账款周转天数 (Days Payable Outstanding)

        DPO = Accounts_Payable / COGS × Days

        Args:
            accounts_payable: 应付账款
            cogs: 营业成本
            days: 天数 (默认360)

        Returns:
            应付账款周转天数或 None
        """
        if accounts_payable is None or cogs is None or cogs == 0:
            return None
        return (accounts_payable / cogs) * days

    @staticmethod
    def calculate_operating_cycle(
        dio: Optional[float], dso: Optional[float]
    ) -> Optional[float]:
        """
        计算营业周期 (Operating Cycle)

        Operating_Cycle = DIO + DSO

        Args:
            dio: 存货周转天数
            dso: 应收账款周转天数

        Returns:
            营业周期或 None
        """
        if dio is None or dso is None:
            return None
        return dio + dso

    @staticmethod
    def calculate_cash_conversion_cycle(
        dio: Optional[float], dso: Optional[float], dpo: Optional[float]
    ) -> Optional[float]:
        """
        计算现金周转周期 (Cash Conversion Cycle)

        CCC = DIO + DSO - DPO

        Args:
            dio: 存货周转天数
            dso: 应收账款周转天数
            dpo: 应付账款周转天数

        Returns:
            现金周转周期或 None
        """
        if dio is None or dso is None or dpo is None:
            return None
        return dio + dso - dpo

    # ==================== P2: 财务安全分析 ====================

    @staticmethod
    def calculate_altman_z_score(
        working_capital: Optional[float],
        total_assets: Optional[float],
        retained_earnings: Optional[float],
        ebit: Optional[float],
        market_cap: Optional[float],
        total_liabilities: Optional[float],
        revenue: Optional[float],
    ) -> Optional[float]:
        """
        计算 Altman Z-Score (简化版)

        Z = 1.2×(WorkingCapital/Assets)
          + 1.4×(RetainedEarnings/Assets)
          + 3.3×(EBIT/Assets)
          + 0.6×(MarketCap/TotalLiabilities)
          + 1.0×(Sales/Assets)

        判读:
        - Z > 2.99: 安全区
        - 1.81 < Z < 2.99: 灰色区
        - Z < 1.81: 危险区

        Args:
            working_capital: 营运资本 (流动资产-流动负债)
            total_assets: 总资产
            retained_earnings: 留存收益
            ebit: 息税前利润
            market_cap: 市值
            total_liabilities: 总负债
            revenue: 营业收入

        Returns:
            Z-Score 或 None
        """
        if any(
            v is None for v in [working_capital, total_assets, retained_earnings, ebit]
        ):
            return None

        if total_assets == 0:
            return None

        x1 = 1.2 * (working_capital / total_assets)
        x2 = 1.4 * (retained_earnings / total_assets)
        x3 = 3.3 * (ebit / total_assets)

        if total_liabilities and total_liabilities > 0 and market_cap:
            x4 = 0.6 * (market_cap / total_liabilities)
        else:
            x4 = 0

        x5 = 1.0 * (revenue / total_assets) if revenue else 0

        return x1 + x2 + x3 + x4 + x5

    @staticmethod
    def calculate_interest_coverage(
        ebit: Optional[float], interest_expense: Optional[float]
    ) -> Optional[float]:
        """
        计算利息保障倍数 (Interest Coverage Ratio)

        Interest_Coverage = EBIT / Interest_Expense

        Args:
            ebit: 息税前利润
            interest_expense: 利息支出

        Returns:
            利息保障倍数或 None
        """
        if ebit is None or interest_expense is None or interest_expense == 0:
            return None
        return ebit / interest_expense

    @staticmethod
    def calculate_debt_to_equity(
        total_liabilities: Optional[float], total_equity: Optional[float]
    ) -> Optional[float]:
        """
        计算资产负债率

        Args:
            total_liabilities: 总负债
            total_equity: 股东权益

        Returns:
            资产负债率或 None
        """
        if total_liabilities is None or total_equity is None:
            return None
        if total_equity == 0:
            return None
        return total_liabilities / total_equity

    @staticmethod
    def calculate_debt_to_assets(
        total_liabilities: Optional[float], total_assets: Optional[float]
    ) -> Optional[float]:
        """
        计算负债资产比

        Args:
            total_liabilities: 总负债
            total_assets: 总资产

        Returns:
            负债资产比或 None
        """
        if total_liabilities is None or total_assets is None or total_assets == 0:
            return None
        return total_liabilities / total_assets

    @staticmethod
    def calculate_operating_profit_margin(
        operating_profit: Optional[float], revenue: Optional[float]
    ) -> Optional[float]:
        """
        计算营业利润率

        Args:
            operating_profit: 营业利润
            revenue: 营业收入

        Returns:
            营业利润率或 None
        """
        if operating_profit is None or revenue is None or revenue == 0:
            return None
        return operating_profit / revenue

    @staticmethod
    def calculate_sustainable_growth_rate(
        roe: Optional[float], retention_rate: Optional[float]
    ) -> Optional[float]:
        """
        计算可持续增长率 (Sustainable Growth Rate)

        SGR = ROE × Retention_Rate
            = ROE × (1 - Dividend_Payout_Rate)

        Args:
            roe: 股东权益回报率
            retention_rate: 留存比率 (如 0.3 表示 30% 留存)

        Returns:
            可持续增长率或 None
        """
        if roe is None or retention_rate is None:
            return None
        return roe * retention_rate
