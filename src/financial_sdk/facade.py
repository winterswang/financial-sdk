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

    def __init__(
        self,
        config_path: Optional[str] = None,
        cache_size: int = 1000,
        enable_cache: bool = True,
    ) -> None:
        """
        初始化FinancialFacade

        Args:
            config_path: 配置文件路径
            cache_size: 缓存大小
            enable_cache: 是否启用缓存
        """
        self._adapter_manager = get_adapter_manager()
        self._cache = (
            get_cache() if enable_cache else FinancialCache(max_size=cache_size)
        )
        self._monitor = get_monitor()
        self._enable_cache = enable_cache

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

        # 生成缓存键
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
            except DataNotAvailableError as e:
                warnings.append(f"{rtype}获取失败: {e.reason}")
                is_partial = True
            except Exception as e:
                warnings.append(f"{rtype}获取异常: {str(e)}")
                is_partial = True

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
                FinancialCache.TTL_STATIC
                if period == "annual"
                else FinancialCache.TTL_DYNAMIC
            )
            self._cache.set(cache_key, bundle, ttl)

        return bundle

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
