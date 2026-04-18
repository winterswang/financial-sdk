"""
监控模块

提供请求时间统计、适配器调用追踪、降级链路日志等功能。
支持P50/P90/P99计算。
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import HealthStatus


@dataclass
class RequestMetrics:
    """单次请求指标"""

    stock_code: str
    adapter_name: str
    report_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    latency_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    from_cache: bool = False


@dataclass
class FallbackStep:
    """降级链路中的单次尝试"""

    adapter_name: str
    status: str  # "success", "failed"
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class PercentileCalculator:
    """百分位数计算器"""

    def __init__(self) -> None:
        self._values: List[float] = []
        self._lock = threading.Lock()

    def add(self, value: float) -> None:
        with self._lock:
            self._values.append(value)

    def get_percentile(self, percentile: int) -> float:
        """获取百分位数

        Args:
            percentile: 百分位 (0-100)，如50表示P50

        Returns:
            float: 百分位数值
        """
        with self._lock:
            if not self._values:
                return 0.0
            sorted_values = sorted(self._values)
            index = int(len(sorted_values) * percentile / 100)
            index = min(index, len(sorted_values) - 1)
            return sorted_values[index]

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class Monitor:
    """
    监控模块

    功能:
    - 记录每次请求的响应时间
    - 计算P50/P90/P99
    - 记录适配器调用次数和错误率
    - 记录降级链路信息
    - 导出监控指标
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # 请求时间记录（按缓存状态分组）
        self._request_times_cache: PercentileCalculator = PercentileCalculator()
        self._request_times_no_cache: PercentileCalculator = PercentileCalculator()

        # 适配器调用统计
        self._adapter_calls: Dict[str, int] = defaultdict(int)
        self._adapter_errors: Dict[str, int] = defaultdict(int)

        # 降级链路记录
        self._fallback_histories: Dict[str, List[FallbackStep]] = defaultdict(list)

        # 当前进行中的请求
        self._active_requests: Dict[str, RequestMetrics] = {}

    def start_request(
        self, request_id: str, stock_code: str, adapter_name: str, report_type: str
    ) -> None:
        """
        开始记录请求

        Args:
            request_id: 请求唯一标识
            stock_code: 股票代码
            adapter_name: 适配器名称
            report_type: 报表类型
        """
        metrics = RequestMetrics(
            stock_code=stock_code,
            adapter_name=adapter_name,
            report_type=report_type,
            start_time=datetime.now(),
        )
        with self._lock:
            self._active_requests[request_id] = metrics

    def end_request(
        self,
        request_id: str,
        success: bool,
        from_cache: bool = False,
        error_message: Optional[str] = None,
    ) -> None:
        """
        结束请求记录

        Args:
            request_id: 请求唯一标识
            success: 是否成功
            from_cache: 是否来自缓存
            error_message: 错误信息
        """
        with self._lock:
            if request_id not in self._active_requests:
                return

            metrics = self._active_requests.pop(request_id)
            metrics.end_time = datetime.now()
            metrics.success = success
            metrics.from_cache = from_cache
            metrics.error_message = error_message

            # 计算延迟
            delta = metrics.end_time - metrics.start_time
            metrics.latency_ms = delta.total_seconds() * 1000

            # 记录到对应的计算器
            if from_cache:
                self._request_times_cache.add(metrics.latency_ms)
            else:
                self._request_times_no_cache.add(metrics.latency_ms)

            # 更新适配器统计
            self._adapter_calls[metrics.adapter_name] += 1
            if not success:
                self._adapter_errors[metrics.adapter_name] += 1

    def record_fallback(self, stock_code: str, steps: List[FallbackStep]) -> None:
        """
        记录降级链路

        Args:
            stock_code: 股票代码
            steps: 降级步骤列表
        """
        with self._lock:
            self._fallback_histories[stock_code] = steps

    def add_fallback_step(
        self,
        stock_code: str,
        adapter_name: str,
        status: str,
        latency_ms: float = 0.0,
        error_message: Optional[str] = None,
    ) -> None:
        """
        添加降级链路步骤

        Args:
            stock_code: 股票代码
            adapter_name: 适配器名称
            status: 状态 ("success" 或 "failed")
            latency_ms: 延迟
            error_message: 错误信息
        """
        step = FallbackStep(
            adapter_name=adapter_name,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        with self._lock:
            self._fallback_histories[stock_code].append(step)

    def get_latency_stats(self, from_cache: bool = False) -> Dict[str, float]:
        """
        获取延迟统计

        Args:
            from_cache: 是否来自缓存

        Returns:
            Dict: 包含P50/P90/P99的字典
        """
        calculator = (
            self._request_times_cache if from_cache else self._request_times_no_cache
        )
        return {
            "p50_ms": round(calculator.get_percentile(50), 2),
            "p90_ms": round(calculator.get_percentile(90), 2),
            "p99_ms": round(calculator.get_percentile(99), 2),
        }

    def get_adapter_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取适配器统计

        Returns:
            Dict: 各适配器的调用次数、错误率等
        """
        result = {}
        with self._lock:
            for adapter_name in self._adapter_calls:
                calls = self._adapter_calls[adapter_name]
                errors = self._adapter_errors[adapter_name]
                result[adapter_name] = {
                    "calls": calls,
                    "errors": errors,
                    "error_rate": round(errors / calls, 4) if calls > 0 else 0.0,
                }
        return result

    def get_fallback_history(self, stock_code: str) -> List[FallbackStep]:
        """
        获取降级历史

        Args:
            stock_code: 股票代码

        Returns:
            List[FallbackStep]: 降级步骤列表
        """
        with self._lock:
            return list(self._fallback_histories.get(stock_code, []))

    def get_health_status(self, cache_stats: Dict[str, Any]) -> HealthStatus:
        """
        获取健康状态

        Args:
            cache_stats: 缓存统计

        Returns:
            HealthStatus: 健康状态对象
        """
        # 计算总体状态
        adapter_stats = self.get_adapter_stats()
        total_calls = sum(s["calls"] for s in adapter_stats.values())
        total_errors = sum(s["errors"] for s in adapter_stats.values())
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0

        if error_rate < 0.05:
            status = "healthy"
        elif error_rate < 0.2:
            status = "degraded"
        else:
            status = "unhealthy"

        # 构建适配器状态
        adapters = {}
        for adapter_name, stats in adapter_stats.items():
            adapters[adapter_name] = {
                "status": "healthy" if stats["error_rate"] < 0.1 else "unhealthy",
                "latency_ms": 0,  # 简化实现
                "calls": stats["calls"],
                "errors": stats["errors"],
                "error_rate": stats["error_rate"],
            }

        # 获取延迟统计
        no_cache_stats = self.get_latency_stats(from_cache=False)
        cache_latency_stats = self.get_latency_stats(from_cache=True)

        return HealthStatus(
            status=status,
            adapters=adapters,
            cache_stats=cache_stats,
            metrics={
                "latency_no_cache": no_cache_stats,
                "latency_cache": cache_latency_stats,
                "total_requests": total_calls,
                "total_errors": total_errors,
            },
            timestamp=datetime.now().isoformat(),
        )

    def get_summary(self) -> Dict[str, Any]:
        """
        获取监控摘要

        Returns:
            Dict: 监控摘要
        """
        adapter_stats = self.get_adapter_stats()
        total_calls = sum(s["calls"] for s in adapter_stats.values())
        total_errors = sum(s["errors"] for s in adapter_stats.values())

        return {
            "total_requests": total_calls,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_calls, 4)
            if total_calls > 0
            else 0.0,
            "latency_no_cache": self.get_latency_stats(from_cache=False),
            "latency_cache": self.get_latency_stats(from_cache=True),
            "adapters": adapter_stats,
        }

    def clear(self) -> None:
        """清除所有监控数据"""
        with self._lock:
            self._request_times_cache.clear()
            self._request_times_no_cache.clear()
            self._adapter_calls.clear()
            self._adapter_errors.clear()
            self._fallback_histories.clear()
            self._active_requests.clear()


# 全局监控实例
_global_monitor: Optional[Monitor] = None
_monitor_lock = threading.Lock()


def get_monitor() -> Monitor:
    """获取全局监控实例"""
    global _global_monitor
    if _global_monitor is None:
        with _monitor_lock:
            if _global_monitor is None:
                _global_monitor = Monitor()
    return _global_monitor


def reset_monitor() -> None:
    """重置全局监控"""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.clear()
