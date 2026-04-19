"""
财务分析模块

提供高级财务指标分析能力，包括：
- 估值指标 (ValuationAnalyzer)
- 盈利能力分析 (ProfitabilityAnalyzer)
- 运营效率分析 (EfficiencyAnalyzer)
- 成长性分析 (GrowthAnalyzer)
- 财务安全分析 (SafetyAnalyzer)
- 统一入口 (FinancialAnalytics)
"""

from .analytics_base import BaseAnalyzer
from .metrics_calculator import MetricsCalculator
from .valuation import ValuationAnalyzer, ValuationMetrics
from .profitability import ProfitabilityAnalyzer, ProfitabilityMetrics
from .efficiency import EfficiencyAnalyzer, EfficiencyMetrics
from .growth import GrowthAnalyzer, GrowthMetrics
from .safety import SafetyAnalyzer, SafetyMetrics
from .unified import FinancialAnalytics, FullAnalysisReport

__all__ = [
    # 基类
    "BaseAnalyzer",
    # 计算引擎
    "MetricsCalculator",
    # 估值分析
    "ValuationAnalyzer",
    "ValuationMetrics",
    # 盈利能力分析
    "ProfitabilityAnalyzer",
    "ProfitabilityMetrics",
    # 运营效率分析
    "EfficiencyAnalyzer",
    "EfficiencyMetrics",
    # 成长性分析
    "GrowthAnalyzer",
    "GrowthMetrics",
    # 财务安全分析
    "SafetyAnalyzer",
    "SafetyMetrics",
    # 统一入口
    "FinancialAnalytics",
    "FullAnalysisReport",
]
