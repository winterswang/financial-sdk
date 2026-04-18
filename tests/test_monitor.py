"""测试监控模块"""

import time

from financial_sdk.monitor import (
    Monitor,
    PercentileCalculator,
    FallbackStep,
    get_monitor,
    reset_monitor,
)


class TestPercentileCalculator:
    """测试PercentileCalculator"""

    def test_empty(self):
        """测试空数据"""
        calc = PercentileCalculator()
        assert calc.get_percentile(50) == 0.0

    def test_single_value(self):
        """测试单值"""
        calc = PercentileCalculator()
        calc.add(100.0)
        assert calc.get_percentile(50) == 100.0
        assert calc.get_percentile(99) == 100.0

    def test_percentiles(self):
        """测试百分位数"""
        calc = PercentileCalculator()
        for i in range(100):
            calc.add(float(i))

        p50 = calc.get_percentile(50)
        p90 = calc.get_percentile(90)
        p99 = calc.get_percentile(99)

        assert 45 <= p50 <= 55
        assert 85 <= p90 <= 95
        assert 95 <= p99 <= 99


class TestFallbackStep:
    """测试FallbackStep"""

    def test_create_step(self):
        """测试创建降级步骤"""
        step = FallbackStep(
            adapter_name="akshare",
            status="success",
            latency_ms=150.5,
        )
        assert step.adapter_name == "akshare"
        assert step.status == "success"
        assert step.latency_ms == 150.5

    def test_failed_step(self):
        """测试失败的步骤"""
        step = FallbackStep(
            adapter_name="akshare_us",
            status="failed",
            error_message="timeout",
        )
        assert step.status == "failed"
        assert step.error_message == "timeout"


class TestMonitor:
    """测试Monitor"""

    def test_start_end_request(self):
        """测试请求记录"""
        monitor = Monitor()
        request_id = "test-123"
        monitor.start_request(request_id, "600000.SH", "akshare", "balance_sheet")
        time.sleep(0.01)
        monitor.end_request(request_id, success=True, from_cache=False)

        stats = monitor.get_adapter_stats()
        assert "akshare" in stats
        assert stats["akshare"]["calls"] == 1
        assert stats["akshare"]["errors"] == 0  # end_request called with success=True

    def test_get_latency_stats(self):
        """测试延迟统计"""
        monitor = Monitor()
        for i in range(100):
            monitor._request_times_no_cache.add(float(i))

        stats = monitor.get_latency_stats(from_cache=False)
        assert "p50_ms" in stats
        assert "p90_ms" in stats
        assert "p99_ms" in stats

    def test_record_fallback(self):
        """测试降级记录"""
        monitor = Monitor()
        steps = [
            FallbackStep(
                adapter_name="akshare_us", status="failed", error_message="timeout"
            ),
            FallbackStep(adapter_name="akshare", status="success"),
        ]
        monitor.record_fallback("AAPL", steps)

        history = monitor.get_fallback_history("AAPL")
        assert len(history) == 2
        assert history[0].adapter_name == "akshare_us"
        assert history[1].adapter_name == "akshare"

    def test_get_health_status(self):
        """测试健康状态"""
        monitor = Monitor()
        monitor._adapter_calls["akshare"] = 100
        monitor._adapter_errors["akshare"] = 5
        monitor._adapter_calls["akshare_hk"] = 50
        monitor._adapter_errors["akshare_hk"] = 10

        health = monitor.get_health_status({"size": 10, "max_size": 1000})
        # 错误率 15/150 = 0.1，0.05 <= 0.1 < 0.2，所以是 "degraded"
        assert health.status == "degraded"

    def test_get_summary(self):
        """测试摘要"""
        monitor = Monitor()
        monitor._request_times_no_cache.add(100.0)
        monitor._adapter_calls["test"] = 10
        monitor._adapter_errors["test"] = 1

        summary = monitor.get_summary()
        assert "total_requests" in summary
        assert summary["total_requests"] == 10


class TestGlobalMonitor:
    """测试全局监控"""

    def test_get_monitor(self):
        """测试获取全局监控"""
        reset_monitor()
        monitor = get_monitor()
        assert monitor is not None
        assert isinstance(monitor, Monitor)

    def test_reset_monitor(self):
        """测试重置监控"""
        monitor = get_monitor()
        monitor._adapter_calls["test"] = 100
        reset_monitor()
        assert len(monitor._adapter_calls) == 0
