"""
适配器管理器

负责管理多个适配器，实现自动路由和降级。
"""

import re
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from .adapters import (
    BaseAdapter,
    ASHareAdapter,
    HKAdapter,
    USAdapter,
    LongbridgeCLIAdapter,
)
from .exceptions import InvalidStockCodeError, NoAdapterAvailableError
from .monitor import FallbackStep, get_monitor


class AdapterManager:
    """
    适配器管理器

    负责:
    - 管理所有注册的适配器
    - 根据股票代码自动选择适配器
    - 实现适配器降级逻辑
    - 管理适配器健康状态
    """

    # 股票代码市场识别正则
    A_STOCK_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")
    HK_STOCK_PATTERN = re.compile(r"^\d{4,5}\.HK$")
    US_STOCK_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

    def __init__(self) -> None:
        """初始化适配器管理器"""
        self._adapters: Dict[str, BaseAdapter] = {}
        self._market_adapters: Dict[str, List[BaseAdapter]] = {
            "A": [],
            "HK": [],
            "US": [],
        }
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """注册默认适配器"""
        # Longbridge CLI 适配器 (优先级最高)
        try:
            lb_adapter = LongbridgeCLIAdapter()
            self.register_adapter(lb_adapter)
        except Exception:
            pass  # CLI 不可用时跳过

        # A股适配器
        ashare_adapter = ASHareAdapter()
        self.register_adapter(ashare_adapter)

        # 港股适配器
        hk_adapter = HKAdapter()
        self.register_adapter(hk_adapter)

        # 美股适配器
        us_adapter = USAdapter()
        self.register_adapter(us_adapter)

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """
        注册适配器

        Args:
            adapter: 适配器实例

        Raises:
            ValueError: 适配器已注册或无效时抛出
        """
        if adapter.adapter_name in self._adapters:
            raise ValueError(f"适配器 {adapter.adapter_name} 已注册")

        self._adapters[adapter.adapter_name] = adapter

        # 按市场分组并按优先级排序
        for market in adapter.supported_markets:
            if market not in self._market_adapters:
                self._market_adapters[market] = []
            self._market_adapters[market].append(adapter)
            self._market_adapters[market].sort(key=lambda a: a.priority)

    def unregister_adapter(self, adapter_name: str) -> None:
        """
        注销适配器

        Args:
            adapter_name: 适配器名称
        """
        if adapter_name not in self._adapters:
            return

        adapter = self._adapters[adapter_name]
        del self._adapters[adapter_name]

        for market in adapter.supported_markets:
            if market in self._market_adapters:
                self._market_adapters[market] = [
                    a
                    for a in self._market_adapters[market]
                    if a.adapter_name != adapter_name
                ]

    def get_market_for_stock(self, stock_code: str) -> str:
        """
        根据股票代码识别市场

        Args:
            stock_code: 股票代码

        Returns:
            str: 市场代码 ("A", "HK", "US")

        Raises:
            InvalidStockCodeError: 无法识别市场时抛出
        """
        if self.A_STOCK_PATTERN.match(stock_code):
            return "A"
        if self.HK_STOCK_PATTERN.match(stock_code):
            return "HK"
        if self.US_STOCK_PATTERN.match(stock_code):
            return "US"

        raise InvalidStockCodeError(
            stock_code=stock_code,
            expected_format="A股: 600000.SH, 港股: 0700.HK, 美股: AAPL",
        )

    def select_adapter(self, stock_code: str) -> BaseAdapter:
        """
        根据股票代码选择适配器

        Args:
            stock_code: 股票代码

        Returns:
            BaseAdapter: 选定的适配器实例

        Raises:
            NoAdapterAvailableError: 没有可用适配器时抛出
            InvalidStockCodeError: 股票代码格式无效时抛出
        """
        market = self.get_market_for_stock(stock_code)

        adapters = self._market_adapters.get(market, [])
        if not adapters:
            raise NoAdapterAvailableError(
                stock_code=stock_code,
                attempted_adapters=[],
                last_error=f"市场 {market} 没有可用的适配器",
            )

        # 返回优先级最高的适配器
        for adapter in adapters:
            if adapter.is_available():
                return adapter

        raise NoAdapterAvailableError(
            stock_code=stock_code,
            attempted_adapters=[a.adapter_name for a in adapters],
            last_error="所有适配器都不可用",
        )

    def get_adapter_with_fallback(
        self, stock_code: str, max_retries: int = 3
    ) -> Tuple[BaseAdapter, List[FallbackStep]]:
        """
        获取适配器，支持多级降级

        Args:
            stock_code: 股票代码
            max_retries: 最大重试次数

        Returns:
            Tuple[BaseAdapter, List[FallbackStep]]:
                - 可用的适配器
                - 降级历史记录列表

        Raises:
            NoAdapterAvailableError: 所有适配器都失败时抛出
        """
        market = self.get_market_for_stock(stock_code)
        adapters = self._market_adapters.get(market, [])
        fallback_history: List[FallbackStep] = []

        if not adapters:
            raise NoAdapterAvailableError(
                stock_code=stock_code,
                attempted_adapters=[],
                last_error=f"市场 {market} 没有可用的适配器",
            )

        for adapter in adapters:
            if not adapter.is_available():
                fallback_history.append(
                    FallbackStep(
                        adapter_name=adapter.adapter_name,
                        status="failed",
                        error_message="适配器不可用",
                    )
                )
                continue

            fallback_history.append(
                FallbackStep(
                    adapter_name=adapter.adapter_name,
                    status="success",
                )
            )

            # 记录降级历史
            monitor = get_monitor()
            monitor.record_fallback(stock_code, fallback_history)

            return adapter, fallback_history

        # 所有适配器都失败
        attempted = [step.adapter_name for step in fallback_history]
        last_error = (
            fallback_history[-1].error_message if fallback_history else "未知错误"
        )

        raise NoAdapterAvailableError(
            stock_code=stock_code,
            attempted_adapters=attempted,
            last_error=last_error or "所有适配器都失败",
            fallback_history=[step.__dict__ for step in fallback_history],
        )

    def get_all_adapters(self) -> Dict[str, BaseAdapter]:
        """
        获取所有注册的适配器

        Returns:
            Dict[str, BaseAdapter]: 适配器名称到实例的映射
        """
        return dict(self._adapters)

    def get_adapter_health(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有适配器的健康状态

        Returns:
            Dict[str, Dict]: 适配器健康状态映射
        """
        health = {}
        for name, adapter in self._adapters.items():
            health[name] = adapter.health_check()
        return health

    def get_adapters_by_market(self, market: str) -> List[BaseAdapter]:
        """
        获取指定市场的所有适配器

        Args:
            market: 市场代码

        Returns:
            List[BaseAdapter]: 适配器列表（按优先级排序）
        """
        adapters = self._market_adapters.get(market, [])
        return sorted(adapters, key=lambda a: a.priority)


# 全局适配器管理器实例
_global_manager: Optional[AdapterManager] = None
_manager_lock = Lock()


def get_adapter_manager() -> AdapterManager:
    """获取全局适配器管理器实例（线程安全）"""
    global _global_manager
    if _global_manager is None:
        with _manager_lock:
            if _global_manager is None:
                _global_manager = AdapterManager()
    return _global_manager


def reset_adapter_manager() -> None:
    """重置全局适配器管理器"""
    global _global_manager
    with _manager_lock:
        _global_manager = None
