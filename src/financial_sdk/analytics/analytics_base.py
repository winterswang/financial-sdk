"""
分析器基类

提供财务分析器的通用基类和接口定义。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseAnalyzer(ABC):
    """
    分析器基类

    所有财务分析器都应继承此类。
    """

    @property
    @abstractmethod
    def analyzer_name(self) -> str:
        """分析器名称"""
        pass

    @property
    def supported_markets(self) -> List[str]:
        """支持的市场"""
        return ["A", "HK", "US"]

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康状态信息
        """
        return {
            "name": self.analyzer_name,
            "status": "healthy",
            "supported_markets": self.supported_markets,
        }
