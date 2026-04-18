"""
FinancialDataSDK - 统一财务数据SDK

提供标准化的财务数据接口，封装A股、港股、美股的财务数据接口。
"""

__version__ = "0.1.0"

from .facade import FinancialFacade
from .models import FinancialBundle, HealthStatus, ValidationResult
from .exceptions import (
    FinancialSDKError,
    DataNotAvailableError,
    NoAdapterAvailableError,
    DataFormatError,
    InvalidStockCodeError,
    CacheError,
    NetworkError,
)

__all__ = [
    "FinancialFacade",
    "FinancialBundle",
    "HealthStatus",
    "ValidationResult",
    "FinancialSDKError",
    "DataNotAvailableError",
    "NoAdapterAvailableError",
    "DataFormatError",
    "InvalidStockCodeError",
    "CacheError",
    "NetworkError",
]
