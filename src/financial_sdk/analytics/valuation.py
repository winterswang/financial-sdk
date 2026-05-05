"""
估值指标分析器

提供基于价格和财务数据的估值指标计算。
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .analytics_base import BaseAnalyzer
from ..price import PriceProvider, get_price_provider

logger = logging.getLogger(__name__)

# 缓存汇率，避免重复调用
_exchange_rate_cache: Dict[str, float] = {}


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
        financial_facade: Optional["FinancialFacade"] = None,
    ) -> None:
        """
        初始化估值分析器

        Args:
            price_provider: 价格提供者实例
            financial_facade: 财务门面实例
        """
        super().__init__(financial_facade=financial_facade)
        self._price_provider = price_provider or get_price_provider()

    @property
    def analyzer_name(self) -> str:
        return "valuation_analyzer"

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

        # 判断市场
        from ..adapter_manager import get_adapter_manager
        market = get_adapter_manager().get_market_for_stock(stock_code)

        # 获取关键财务指标
        eps = self._get_value(income, "eps") or self._get_value(
            indicators, "eps"
        )  # 优先使用利润表的EPS
        # 美股: 优先使用 ADS EPS (与股价同币种、同单位)
        ads_eps = self._get_value(income, "ads_eps") or self._get_value(
            indicators, "ads_eps"
        )
        if market == "US" and ads_eps:
            eps = ads_eps  # 用 ADS EPS 替代普通股 EPS

        bvps = self._get_value(indicators, "bvps")  # 从指标表获取每股净资产
        revenue = self._get_value(income, "revenue")
        net_profit = self._get_value(income, "net_profit")
        total_equity = self._get_value(balance, "total_equity")
        total_assets = self._get_value(balance, "total_assets")
        total_debt = self._get_value(balance, "total_liabilities")
        cash = self._get_value(balance, "cash_and_equivalents")
        depreciation = self._get_value(cash_flow, "depreciation_amortization")

        # 计算总股本
        # 美股: 优先用加权平均股数推算 ADS 数量
        weighted_avg_shares = self._get_value(income, "weighted_avg_shares")
        shares = None
        if market == "US" and weighted_avg_shares and weighted_avg_shares > 0:
            # ADS ratio 推断: ads_eps / eps (如果都有值)
            ordinary_eps = self._get_value(income, "eps")
            if ordinary_eps and ads_eps and ordinary_eps != 0:
                ads_ratio = ads_eps / ordinary_eps
                if ads_ratio > 0:
                    shares = weighted_avg_shares / ads_ratio  # ADS 数量
            # 如果推断不出 ads_ratio，用常见默认值
            if shares is None:
                # 大多数中概股 1 ADS = 4 或 5 普通股
                # 用 bvps 反推
                if total_equity and bvps and bvps > 0:
                    shares = total_equity / bvps
                else:
                    # 无法确定 ADS ratio，用普通股数直接算（PE会不准）
                    # 但后面会用 Market Cap / Net Profit 方式修正
                    shares = weighted_avg_shares  # 暂用普通股数

        if shares is None and total_equity and bvps and bvps > 0:
            shares = total_equity / bvps

        # 计算市值
        # 优先使用价格提供商返回的市值 (最准确，已考虑 ADS)
        market_cap = price_data.market_cap
        if market_cap is None:
            # 尝试从价格提供商的 get_market_cap 获取 (Yahoo quoteSummary / AkShare)
            market_cap = self._price_provider.get_market_cap(stock_code)
        if market_cap is None and shares and shares > 0:
            market_cap = current_price * shares

        # 计算每股股息: 优先使用指标表的每股股息，不使用分红总额
        dps = self._get_value(indicators, "dps")

        # 计算 EBITDA
        ebitda = None
        if net_profit is not None:
            tax_expense = self._get_value(income, "tax_expense") or 0
            interest_expense = self._get_value(income, "interest_expense") or 0
            ebitda = net_profit + tax_expense + interest_expense + (depreciation or 0)

        # 计算 PE
        # 策略优先级:
        # 1. Market Cap / Net Profit (最准确，自动处理 ADS 和币种)
        # 2. 美股 + 有 ADS EPS: Price / ADS_EPS (需同币种)
        # 3. 回退: Price / EPS (需同币种转换)
        pe_ratio = None
        price_currency = price_data.currency  # e.g. "USD"
        financial_currency = self._infer_financial_currency(indicators)

        # 1. Market Cap / Net Profit (需同币种)
        if market_cap and net_profit and net_profit > 0:
            if price_currency == financial_currency:
                pe_ratio = market_cap / net_profit
            else:
                rate = self._get_exchange_rate(financial_currency, price_currency)
                if rate:
                    pe_ratio = market_cap / (net_profit * rate)

        # 2. 美股 + 有 ADS EPS
        if pe_ratio is None and market == "US" and ads_eps and ads_eps > 0:
            if price_currency == financial_currency:
                pe_ratio = current_price / ads_eps
            else:
                rate = self._get_exchange_rate(financial_currency, price_currency)
                if rate:
                    pe_ratio = current_price / (ads_eps * rate)

        # 3. 回退: Price / EPS (需币种转换)
        if pe_ratio is None and eps and eps > 0:
            if price_currency == financial_currency:
                pe_ratio = self._calculator.calculate_pe_ratio(current_price, eps)
            else:
                rate = self._get_exchange_rate(financial_currency, price_currency)
                if rate:
                    eps_converted = eps * rate
                    pe_ratio = current_price / eps_converted
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

    def _infer_financial_currency(self, df: Optional[Any]) -> str:
        """
        推断财务数据的货币单位

        AkShare 返回的美股数据可能是 USD 或 CNY（取决于公司注册地），
        港股数据是 HKD，A股是 CNY。
        通过检查 CURRENCY 列、列名中的货币后缀或数据源来推断。

        Args:
            df: DataFrame

        Returns:
            货币代码 ("CNY", "USD", "HKD")
        """
        if df is None or df.empty:
            return "CNY"

        # 1. 优先检查 CURRENCY 列 (AkShare indicators 中有此列)
        if "CURRENCY" in df.columns:
            curr = str(df["CURRENCY"].iloc[0])
            currency_map = {
                "美元": "USD",
                "人民币": "CNY",
                "港币": "HKD",
                "USD": "USD",
                "CNY": "CNY",
                "HKD": "HKD",
            }
            if curr in currency_map:
                return currency_map[curr]

        # 2. 检查列名中的货币后缀 (LongBridge 数据)
        for col in df.columns:
            if "(USD)" in col:
                return "USD"
            if "(HKD)" in col:
                return "HKD"
            if "(CNY)" in col:
                return "CNY"

        # 3. 根据 _raw_data_source 标识推断
        if "_raw_data_source" in df.columns:
            source = str(df["_raw_data_source"].iloc[0])
            # AkShare A 股是人民币
            if source == "akshare":
                return "CNY"
            # AkShare 港股是港币
            if source == "akshare_hk":
                return "HKD"
            # AkShare 美股可能是 USD 或 CNY，无法仅从 source 判断
            # 需要依赖 CURRENCY 列或其他信号

        return "CNY"

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        获取汇率

        Args:
            from_currency: 源货币
            to_currency: 目标货币

        Returns:
            汇率 (1 from_currency = N to_currency)，如果同币种返回 1.0
        """
        if from_currency == to_currency:
            return 1.0

        cache_key = f"{from_currency}_{to_currency}"
        if cache_key in _exchange_rate_cache:
            return _exchange_rate_cache[cache_key]

        try:
            import akshare as ak
            # 使用 currency_boc_safe 获取中行汇率 (更稳定)
            df = ak.currency_boc_safe()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                # 中行汇率: 100外币 = N 人民币
                usd_cny = float(latest["美元"]) / 100.0  # 1 USD = N CNY
                hkd_cny = float(latest["港元"]) / 100.0  # 1 HKD = N CNY

                rates = {
                    "CNY_USD": 1.0 / usd_cny if usd_cny > 0 else None,
                    "USD_CNY": usd_cny,
                    "CNY_HKD": usd_cny / hkd_cny if hkd_cny > 0 else None,
                    "HKD_CNY": hkd_cny,
                    "HKD_USD": hkd_cny / usd_cny if usd_cny > 0 else None,
                    "USD_HKD": usd_cny / hkd_cny if hkd_cny > 0 else None,
                }
                rate = rates.get(cache_key)
                if rate:
                    _exchange_rate_cache[cache_key] = rate
                    # 缓存反向
                    reverse_key = f"{to_currency}_{from_currency}"
                    reverse_rate = rates.get(reverse_key)
                    if reverse_rate:
                        _exchange_rate_cache[reverse_key] = reverse_rate
                    return rate
        except Exception as e:
            logger.warning(f"Failed to get exchange rate {from_currency}->{to_currency}: {e}")

        # 硬编码的备用汇率
        fallback_rates = {
            "CNY_USD": 0.138,   # 1 CNY ≈ 0.138 USD
            "USD_CNY": 7.24,    # 1 USD ≈ 7.24 CNY
            "HKD_USD": 0.128,   # 1 HKD ≈ 0.128 USD
            "USD_HKD": 7.81,    # 1 USD ≈ 7.81 HKD
            "CNY_HKD": 1.085,   # 1 CNY ≈ 1.085 HKD
            "HKD_CNY": 0.922,   # 1 HKD ≈ 0.922 CNY
        }
        rate = fallback_rates.get(cache_key)
        if rate:
            _exchange_rate_cache[cache_key] = rate
        return rate

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
        result = super().health_check()
        price_healthy = True
        try:
            self._price_provider.get_price("600000.SH")
        except Exception:
            price_healthy = False

        facade_healthy = result["status"] == "healthy"
        result["status"] = "healthy" if (facade_healthy and price_healthy) else "degraded"
        result["components"] = {
            "price_provider": "healthy" if price_healthy else "unhealthy",
            "financial_facade": "healthy" if facade_healthy else "unhealthy",
        }
        result.pop("supported_markets", None)
        return result
