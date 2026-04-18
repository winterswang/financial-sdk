"""
财务SDK异常类定义

提供完整的异常类体系，支持错误追溯和降级链路记录。
"""

from typing import Any, Dict, List, Optional


class FinancialSDKError(Exception):
    """
    SDK基础异常类

    所有SDK异常的基类，提供统一的异常处理接口
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，便于日志和监控"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message})"


class DataNotAvailableError(FinancialSDKError):
    """
    数据不可用异常

    当指定股票代码和报表类型无法获取数据时抛出

    Attributes:
        stock_code: 股票代码
        report_type: 报表类型
        reason: 失败原因
        adapter_name: 尝试的适配器名称
    """

    def __init__(
        self,
        stock_code: str,
        report_type: str,
        reason: Optional[str] = None,
        adapter_name: Optional[str] = None,
    ) -> None:
        self.stock_code = stock_code
        self.report_type = report_type
        self.reason = reason
        self.adapter_name = adapter_name

        message = f"数据不可用: {stock_code} {report_type}"
        if reason:
            message += f", 原因: {reason}"
        if adapter_name:
            message += f" (Adapter: {adapter_name})"

        details: Dict[str, Any] = {
            "stock_code": stock_code,
            "report_type": report_type,
            "reason": reason,
            "adapter_name": adapter_name,
        }
        super().__init__(message, details)


class NoAdapterAvailableError(FinancialSDKError):
    """
    无可用适配器异常

    当所有适配器都失败时抛出，包含完整的降级链路信息

    Attributes:
        stock_code: 股票代码
        attempted_adapters: 已尝试的适配器列表
        last_error: 最后失败的错误信息
        fallback_history: 降级历史记录
    """

    def __init__(
        self,
        stock_code: str,
        attempted_adapters: List[str],
        last_error: str,
        fallback_history: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.stock_code = stock_code
        self.attempted_adapters = attempted_adapters
        self.last_error = last_error
        self.fallback_history = fallback_history or []

        message = (
            f"无可用适配器: {stock_code}, "
            f"已尝试: {attempted_adapters}, "
            f"最后错误: {last_error}"
        )

        details = {
            "stock_code": stock_code,
            "attempted_adapters": attempted_adapters,
            "last_error": last_error,
            "fallback_history": self.fallback_history,
        }
        super().__init__(message, details)


class DataFormatError(FinancialSDKError):
    """
    数据格式异常

    当数据格式不符合预期时抛出

    Attributes:
        field_name: 字段名
        expected_format: 期望的格式
        actual_value: 实际的值
        stock_code: 股票代码
    """

    def __init__(
        self,
        field_name: str,
        expected_format: str,
        actual_value: Any,
        stock_code: Optional[str] = None,
    ) -> None:
        self.field_name = field_name
        self.expected_format = expected_format
        self.actual_value = actual_value
        self.stock_code = stock_code

        message = f"数据格式错误: 字段 {field_name}"
        if stock_code:
            message += f" (股票: {stock_code})"
        message += f", 期望: {expected_format}, 实际: {actual_value}"

        details = {
            "field_name": field_name,
            "expected_format": expected_format,
            "actual_value": str(actual_value),
            "stock_code": stock_code,
        }
        super().__init__(message, details)


class InvalidStockCodeError(FinancialSDKError):
    """
    无效股票代码异常

    当股票代码格式不正确时抛出

    Attributes:
        stock_code: 无效的股票代码
        expected_format: 期望的格式
        market: 市场标识
    """

    def __init__(
        self,
        stock_code: str,
        expected_format: Optional[str] = None,
        market: Optional[str] = None,
    ) -> None:
        self.stock_code = stock_code
        self.expected_format = expected_format
        self.market = market

        message = f"无效的股票代码: {stock_code}"
        if expected_format:
            message += f", 期望格式: {expected_format}"
        if market:
            message += f", 市场: {market}"

        details = {
            "stock_code": stock_code,
            "expected_format": expected_format,
            "market": market,
        }
        super().__init__(message, details)


class CacheError(FinancialSDKError):
    """
    缓存操作异常

    当缓存操作失败时抛出

    Attributes:
        operation: 操作类型 (get/set/clear)
        key: 缓存键
        reason: 失败原因
    """

    def __init__(
        self,
        operation: str,
        key: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.operation = operation
        self.key = key
        self.reason = reason

        message = f"缓存操作失败: {operation}"
        if key:
            message += f", 键: {key}"
        if reason:
            message += f", 原因: {reason}"

        details = {
            "operation": operation,
            "key": key,
            "reason": reason,
        }
        super().__init__(message, details)


class NetworkError(FinancialSDKError):
    """
    网络异常

    当网络请求失败时抛出

    Attributes:
        url: 请求URL
        timeout: 超时时间
        status_code: HTTP状态码
        retry_count: 重试次数
    """

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        timeout: Optional[int] = None,
        status_code: Optional[int] = None,
        retry_count: int = 0,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.status_code = status_code
        self.retry_count = retry_count

        details = {
            "url": url,
            "timeout": timeout,
            "status_code": status_code,
            "retry_count": retry_count,
        }
        super().__init__(message, details)
