"""
门面模式入口

作为系统的唯一入口，提供简洁的公共API。
"""

import uuid
from typing import Any, Dict, List, Optional, Set

import pandas as pd

from .adapter_manager import get_adapter_manager
from .cache import FinancialCache, get_cache
from .exceptions import (
    DataNotAvailableError,
    NoAdapterAvailableError,
)
from .models import FinancialBundle, HealthStatus
from .monitor import get_monitor


class FinancialFacade:
    """
    财务SDK门面类，提供统一的财务数据获取接口

    示例用法:
        facade = FinancialFacade()

        # 获取A股数据
        data = facade.get_financial_data("600000.SH", "all", "annual")

        # 获取美股数据
        data = facade.get_financial_data("AAPL", "balance_sheet", "quarterly")

        # 健康检查
        health = facade.health_check()
    """

    # 支持的报告类型
    REPORT_TYPES: Set[str] = {
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "indicators",
        "all",
    }

    # 支持的期间类型
    PERIOD_TYPES: Set[str] = {"annual", "quarterly"}

    # 支持的市场
    MARKET_TYPES: Set[str] = {"A", "HK", "US", "all"}

    # OOM 防护默认值
    DEFAULT_MEMORY_THRESHOLD = 500  # 总行数阈值
    DEFAULT_MAX_YEARS = 10  # 截断时保留最近N年

    def __init__(
        self,
        config_path: Optional[str] = None,
        cache_size: int = 1000,
        enable_cache: bool = True,
        memory_threshold: int = DEFAULT_MEMORY_THRESHOLD,
        max_years: int = DEFAULT_MAX_YEARS,
    ) -> None:
        """
        初始化FinancialFacade

        Args:
            config_path: 配置文件路径
            cache_size: 缓存大小
            enable_cache: 是否启用缓存
            memory_threshold: OOM防护行数阈值，总行数超过此值触发截断
            max_years: 截断时保留最近N年数据
        """
        self._adapter_manager = get_adapter_manager()
        if enable_cache:
            self._cache = get_cache()
            # 同步缓存大小设置
            if hasattr(self._cache, "_max_size") and self._cache._max_size < cache_size:
                self._cache._max_size = cache_size
        else:
            self._cache = FinancialCache(max_size=cache_size)
        self._monitor = get_monitor()
        self._enable_cache = enable_cache
        self._memory_threshold = memory_threshold
        self._max_years = max_years

    def get_financial_data(
        self,
        stock_code: str,
        report_type: str = "all",
        period: str = "annual",
        force_refresh: bool = False,
    ) -> FinancialBundle:
        """
        获取财务报表数据

        Args:
            stock_code: 股票代码，支持以下格式:
                - A股: 600000.SH、000001.SZ
                - 港股: 0700.HK、9988.HK
                - 美股: AAPL、MSFT（自动识别）
            report_type: 报表类型
                - "balance_sheet": 资产负债表
                - "income_statement": 利润表
                - "cash_flow": 现金流量表
                - "indicators": 财务指标
                - "all": 全部报表（默认）
            period: 报告期类型
                - "annual": 年度报告（默认）
                - "quarterly": 季度报告
            force_refresh: 是否强制刷新缓存，默认False

        Returns:
            FinancialBundle: 标准化财务数据包

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            NoAdapterAvailableError: 所有适配器都失败时抛出
            InvalidStockCodeError: 股票代码格式无效时抛出
        """
        # 参数验证
        if report_type not in self.REPORT_TYPES:
            raise ValueError(
                f"无效的report_type: {report_type}，支持的类型: {self.REPORT_TYPES}"
            )
        if period not in self.PERIOD_TYPES:
            raise ValueError(f"无效的period: {period}，支持的类型: {self.PERIOD_TYPES}")

        # 确定市场
        market = self._adapter_manager.get_market_for_stock(stock_code)

        # 生成缓存键（不含数据源，因为缓存应在适配器选择前检查）
        cache_key = FinancialCache.make_cache_key(
            market, stock_code, report_type, period
        )

        # 尝试从缓存获取
        if not force_refresh and self._enable_cache:
            cache_hit, cached = self._cache.get(cache_key)
            if cache_hit and cached is not None:
                return cached

        # 选择适配器
        adapter = self._adapter_manager.select_adapter(stock_code)

        # 生成请求ID用于追踪
        request_id = str(uuid.uuid4())
        self._monitor.start_request(
            request_id, stock_code, adapter.adapter_name, report_type
        )

        # 构建结果
        bundle = FinancialBundle(
            stock_code=stock_code,
            market=market,
            currency=self._get_currency(market),
            data_period=period,
        )

        warnings: List[str] = []
        is_partial = False
        successful_reports: List[str] = []

        # 获取报表
        report_types_to_fetch = self._get_report_types_to_fetch(report_type)

        for rtype in report_types_to_fetch:
            try:
                df = self._fetch_report(adapter, stock_code, rtype, period)
                self._attach_report(bundle, rtype, df)
                successful_reports.append(rtype)
                # 检查适配器自愈推算的字段，记录到 warnings
                if df is not None and not df.empty and "_derived_fields" in df.columns:
                    derived = df["_derived_fields"].dropna().unique()
                    for d in derived:
                        warnings.append(f"{rtype} 自愈推算: {d}")
            except DataNotAvailableError as e:
                # 尝试 fallback 到下一个适配器
                fallback_df = self._try_fallback_adapter(
                    stock_code, market, rtype, period, adapter.adapter_name
                )
                if fallback_df is not None:
                    self._attach_report(bundle, rtype, fallback_df)
                    successful_reports.append(rtype)
                    warnings.append(f"{rtype}通过备用适配器获取")
                else:
                    warnings.append(f"{rtype}获取失败: {e.reason}")
                    is_partial = True
            except Exception as e:
                # 尝试 fallback
                fallback_df = self._try_fallback_adapter(
                    stock_code, market, rtype, period, adapter.adapter_name
                )
                if fallback_df is not None:
                    self._attach_report(bundle, rtype, fallback_df)
                    successful_reports.append(rtype)
                    warnings.append(f"{rtype}通过备用适配器获取")
                else:
                    warnings.append(f"{rtype}获取异常: {str(e)}")
                    is_partial = True

        # Issue #10 fix: 跨报表 fallback 计算
        # income_statement 的 roe 可能为空，但有 net_profit + balance_sheet 的 total_equity
        self._cross_report_fallback(bundle)

        # 更新bundle状态
        bundle.warnings = warnings
        bundle.is_partial = is_partial

        # 如果所有报表都失败
        if not successful_reports:
            raise NoAdapterAvailableError(
                stock_code=stock_code,
                attempted_adapters=[adapter.adapter_name],
                last_error="所有报表获取失败",
            )

        # 更新请求监控
        self._monitor.end_request(request_id, success=True, from_cache=False)

        # 缓存结果
        if self._enable_cache and successful_reports:
            ttl = (
                FinancialCache.TTL_ANNUAL
                if period == "annual"
                else FinancialCache.TTL_QUARTERLY
            )
            self._cache.set(cache_key, bundle, ttl)

        # 内存保护：当同时拉取多个报表时检查数据量
        if len(report_types_to_fetch) > 1:
            self._check_bundle_memory(bundle, stock_code)

        return bundle

    def _check_bundle_memory(self, bundle: FinancialBundle, stock_code: str) -> None:
        """
        OOM 防护：检查 bundle 内存占用，主动截断过大 DataFrame

        当所有报表总行数超过阈值时，truncate 每个 DataFrame 保留最近 N 年数据，
        并在 bundle.warnings 中记录截断信息。

        Args:
            bundle: 财务数据包
            stock_code: 股票代码
        """
        import logging
        import warnings as _warnings

        logger = logging.getLogger(__name__)

        total_rows = 0
        report_attrs = ["balance_sheet", "income_statement", "cash_flow", "indicators"]
        for attr in report_attrs:
            df = getattr(bundle, attr, None)
            if df is not None and not (hasattr(df, "empty") and df.empty):
                total_rows += len(df)

        if total_rows <= self._memory_threshold:
            return

        # 主动截断：保留最近 N 年
        max_years = self._max_years
        for attr in report_attrs:
            df = getattr(bundle, attr, None)
            if df is None or (hasattr(df, "empty") and df.empty):
                continue
            if "report_date" not in df.columns:
                # 无日期列，保留最后 max_years 行
                if len(df) > max_years:
                    original_len = len(df)
                    setattr(bundle, attr, df.tail(max_years).copy())
                    msg = (
                        f"OOM 截断: {stock_code} {attr} 无 report_date，"
                        f"保留最近 {max_years} 行 (原 {original_len} 行)"
                    )
                    logger.warning(msg)
                    bundle.warnings.append(msg)
                continue

            # 按年份截断
            try:
                dates = pd.to_datetime(df["report_date"], errors="coerce")
                latest_year = dates.dt.year.max()
                if pd.isna(latest_year):
                    continue
                cutoff_year = latest_year - max_years + 1
                mask = dates.dt.year >= cutoff_year
                if mask.sum() < len(df):
                    original_len = len(df)
                    setattr(bundle, attr, df[mask].copy())
                    kept = mask.sum()
                    msg = (
                        f"OOM 截断: {stock_code} {attr} 保留 {cutoff_year}+ 年数据 "
                        f"({kept}/{original_len} 行)"
                    )
                    logger.warning(msg)
                    bundle.warnings.append(msg)
            except Exception as e:
                logger.warning(f"OOM 截断失败: {stock_code} {attr}: {e}")

        # 发出 Python warning
        _warnings.warn(
            f"{stock_code}: bundle 总行数 {total_rows} 超过阈值 {self._memory_threshold}，"
            f"已截断至最近 {max_years} 年",
            stacklevel=3,
        )

    def _fetch_report(
        self, adapter, stock_code: str, report_type: str, period: str
    ) -> pd.DataFrame:
        """
        从适配器获取报表

        Args:
            adapter: 适配器
            stock_code: 股票代码
            report_type: 报表类型
            period: 期间类型

        Returns:
            pd.DataFrame: 报表数据
        """
        if report_type == "balance_sheet":
            return adapter.get_balance_sheet(stock_code, period)
        elif report_type == "income_statement":
            return adapter.get_income_statement(stock_code, period)
        elif report_type == "cash_flow":
            return adapter.get_cash_flow(stock_code, period)
        elif report_type == "indicators":
            return adapter.get_indicators(stock_code, period)
        else:
            raise ValueError(f"不支持的报表类型: {report_type}")

    def _attach_report(
        self, bundle: FinancialBundle, report_type: str, df: pd.DataFrame
    ) -> None:
        """
        将报表附加到bundle

        Args:
            bundle: FinancialBundle
            report_type: 报表类型
            df: DataFrame
        """
        if report_type == "balance_sheet":
            bundle.balance_sheet = df
        elif report_type == "income_statement":
            bundle.income_statement = df
        elif report_type == "cash_flow":
            bundle.cash_flow = df
        elif report_type == "indicators":
            bundle.indicators = df

    def _try_fallback_adapter(
        self,
        stock_code: str,
        market: str,
        report_type: str,
        period: str,
        failed_adapter_name: str,
    ) -> Optional[pd.DataFrame]:
        """
        当主适配器失败时，尝试使用下一个适配器获取数据

        Args:
            stock_code: 股票代码
            market: 市场代码
            report_type: 报表类型
            period: 期间类型
            failed_adapter_name: 失败的适配器名称

        Returns:
            DataFrame 或 None
        """
        adapters = self._adapter_manager._market_adapters.get(market, [])
        for adapter in adapters:
            if adapter.adapter_name == failed_adapter_name:
                continue
            if not adapter.is_available():
                continue
            try:
                df = self._fetch_report(adapter, stock_code, report_type, period)
                return df
            except Exception:
                continue
        return None

    def _cross_report_fallback(self, bundle: FinancialBundle) -> None:
        """跨报表 fallback: 用已有字段推算缺失指标

        Issue #10: 当 income_statement.roe 为空但 net_profit 和 total_equity 有值时，
        自动计算 roe = net_profit / total_equity * 100。
        同理 net_margin = net_profit / revenue * 100 (补充 income_statement 自愈未覆盖的场景)。
        """
        is_df = bundle.income_statement
        bs_df = bundle.balance_sheet

        if is_df is None or is_df.empty:
            return

        # 推算 net_margin (如果 income_statement 自愈未覆盖)
        if (
            "net_margin" in is_df.columns
            and "net_profit" in is_df.columns
            and "revenue" in is_df.columns
        ):
            mask = (
                is_df["net_margin"].isna()
                & is_df["net_profit"].notna()
                & is_df["revenue"].notna()
                & (is_df["revenue"] != 0)
            )
            if mask.any():
                is_df.loc[mask, "net_margin"] = (
                    is_df.loc[mask, "net_profit"] / is_df.loc[mask, "revenue"]
                ) * 100
                bundle.warnings.append(
                    f"income_statement 自愈推算: net_margin = net_profit / revenue * 100 ({int(mask.sum())} rows)"
                )

        # 推算 roe: 需要 income_statement.net_profit + balance_sheet.total_equity
        if "roe" in is_df.columns and bs_df is not None and not bs_df.empty:
            if "net_profit" in is_df.columns and "total_equity" in bs_df.columns:
                # 按 report_date 对齐
                if "report_date" in is_df.columns and "report_date" in bs_df.columns:
                    roe_mask = is_df["roe"].isna()
                    if roe_mask.any():
                        equity_map = bs_df.set_index("report_date")[
                            "total_equity"
                        ].to_dict()
                        for idx in is_df[roe_mask].index:
                            date = is_df.loc[idx, "report_date"]
                            equity = equity_map.get(date)
                            np_val = is_df.loc[idx, "net_profit"]
                            if equity and np_val and equity != 0:
                                is_df.loc[idx, "roe"] = (np_val / equity) * 100
                        filled = roe_mask & is_df["roe"].notna()
                        if filled.any():
                            bundle.warnings.append(
                                f"income_statement 自愈推算: roe = net_profit / total_equity * 100 ({int(filled.sum())} rows)"
                            )

    def _get_report_types_to_fetch(self, report_type: str) -> List[str]:
        """
        获取需要获取的报表类型列表

        Args:
            report_type: 报表类型

        Returns:
            List[str]: 报表类型列表
        """
        if report_type == "all":
            return ["balance_sheet", "income_statement", "cash_flow", "indicators"]
        return [report_type]

    def _get_currency(self, market: str) -> str:
        """
        获取市场对应的货币

        Args:
            market: 市场代码

        Returns:
            str: 货币代码
        """
        currency_map = {
            "A": "CNY",
            "HK": "HKD",
            "US": "USD",
        }
        return currency_map.get(market, "CNY")

    def get_supported_stocks(self, market: str = "all") -> List[str]:
        """
        获取支持的股票列表

        Args:
            market: 市场筛选
                - "all": 所有市场（默认）
                - "A": A股
                - "HK": 港股
                - "US": 美股

        Returns:
            List[str]: 股票代码列表

        Note:
            此方法返回SDK内置支持的部分股票列表
            对于大多数场景，用户应自行管理股票代码
        """
        if market == "all":
            return [
                # A股示例
                "600000.SH",
                "000001.SZ",
                "600036.SH",
                "601318.SH",
                "000002.SZ",
                # 港股示例
                "0700.HK",
                "9988.HK",
                "0941.HK",
                "3690.HK",
                "9618.HK",
                # 美股示例
                "AAPL",
                "MSFT",
                "GOOGL",
                "AMZN",
                "TSLA",
            ]

        stock_map = {
            "A": ["600000.SH", "000001.SZ", "600036.SH", "601318.SH", "000002.SZ"],
            "HK": ["0700.HK", "9988.HK", "0941.HK", "3690.HK", "9618.HK"],
            "US": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        }

        return stock_map.get(market, [])

    def health_check(self) -> HealthStatus:
        """
        健康检查

        Returns:
            HealthStatus: 包含各适配器健康状态的对象
        """
        cache_stats = self._cache.get_stats()
        return self._monitor.get_health_status(cache_stats)

    def clear_cache(self) -> None:
        """
        清除所有缓存

        用于强制刷新数据的场景
        """
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict包含: size, max_size, hit_rate, miss_rate等
        """
        return self._cache.get_stats()
