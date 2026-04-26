"""
分析器基类

提供财务分析器的通用基类和接口定义。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..facade import FinancialFacade
from .metrics_calculator import MetricsCalculator


class BaseAnalyzer(ABC):
    """
    分析器基类

    所有财务分析器都应继承此类，提供通用的数据获取和辅助方法。
    """

    def __init__(
        self,
        financial_facade: Optional[FinancialFacade] = None,
    ) -> None:
        """
        初始化分析器

        Args:
            financial_facade: 财务门面实例
        """
        self._facade = financial_facade or FinancialFacade()
        self._calculator = MetricsCalculator()

    @property
    @abstractmethod
    def analyzer_name(self) -> str:
        """分析器名称"""
        pass

    @property
    def supported_markets(self) -> List[str]:
        """支持的市场"""
        return ["A", "HK", "US"]

    def _get_financial_data(
        self, stock_code: str, period: str = "annual"
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        获取财务报表数据

        Args:
            stock_code: 股票代码
            period: 报告期类型

        Returns:
            Dict[str, Optional[DataFrame]]: 包含各报表的字典
        """
        try:
            bundle = self._facade.get_financial_data(
                stock_code=stock_code,
                report_type="all",
                period=period,
            )
            return {
                "income_statement": bundle.income_statement,
                "balance_sheet": bundle.balance_sheet,
                "cash_flow": bundle.cash_flow,
                "indicators": bundle.indicators,
            }
        except Exception:
            return {
                "income_statement": None,
                "balance_sheet": None,
                "cash_flow": None,
                "indicators": None,
            }

    def _get_value(
        self, df: Optional[pd.DataFrame], field: str, period_index: int = 0
    ) -> Optional[float]:
        """
        从 DataFrame 获取指定字段的值

        Args:
            df: DataFrame
            field: 字段名
            period_index: 取第几期 (0=最新)

        Returns:
            值或 None
        """
        if df is None or df.empty:
            return None
        if field not in df.columns:
            return None

        # 按日期排序确保获取正确的数据
        if "report_date" in df.columns:
            df_sorted = df.sort_values("report_date", ascending=True)
        else:
            df_sorted = df

        values = df_sorted[field].dropna()
        if values.empty:
            return None

        if period_index < len(values):
            return float(values.iloc[-(period_index + 1)])
        return float(values.iloc[0])

    def _get_latest_report_date(self, df: Optional[pd.DataFrame]) -> str:
        """获取最新报告日期"""
        if df is None or df.empty:
            return datetime.now().strftime("%Y-%m-%d")
        if "report_date" not in df.columns:
            return datetime.now().strftime("%Y-%m-%d")
        dates = df["report_date"].dropna()
        if dates.empty:
            return datetime.now().strftime("%Y-%m-%d")
        return str(dates.iloc[-1])

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康状态信息
        """
        facade_healthy = True
        try:
            self._facade.health_check()
        except Exception:
            facade_healthy = False

        return {
            "name": self.analyzer_name,
            "status": "healthy" if facade_healthy else "degraded",
            "supported_markets": self.supported_markets,
        }
