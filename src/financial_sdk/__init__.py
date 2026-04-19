"""
FinancialDataSDK - 统一财务数据SDK

提供标准化的财务数据接口，封装A股、港股、美股的财务数据接口。
"""

__version__ = "0.2.0"

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

# 价格模块
from .price import (
    PriceData,
    PriceResult,
    PriceProvider,
    get_price_provider,
)

# 财务分析模块
from .analytics import (
    BaseAnalyzer,
    MetricsCalculator,
    ValuationAnalyzer,
    ValuationMetrics,
    ProfitabilityAnalyzer,
    ProfitabilityMetrics,
    EfficiencyAnalyzer,
    EfficiencyMetrics,
    GrowthAnalyzer,
    GrowthMetrics,
    SafetyAnalyzer,
    SafetyMetrics,
    FinancialAnalytics,
    FullAnalysisReport,
)

__all__ = [
    # 核心
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
    # 价格模块
    "PriceData",
    "PriceResult",
    "PriceProvider",
    "get_price_provider",
    # 分析模块
    "BaseAnalyzer",
    "MetricsCalculator",
    "ValuationAnalyzer",
    "ValuationMetrics",
    "ProfitabilityAnalyzer",
    "ProfitabilityMetrics",
    "EfficiencyAnalyzer",
    "EfficiencyMetrics",
    "GrowthAnalyzer",
    "GrowthMetrics",
    "SafetyAnalyzer",
    "SafetyMetrics",
    "FinancialAnalytics",
    "FullAnalysisReport",
]
