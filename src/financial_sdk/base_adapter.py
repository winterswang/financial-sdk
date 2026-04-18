"""
适配器基类

定义所有数据源适配器必须实现的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd

from .exceptions import DataFormatError


class BaseAdapter(ABC):
    """
    适配器抽象基类

    所有数据源适配器必须实现此接口

    示例:
        class MyAdapter(BaseAdapter):
            @property
            def adapter_name(self) -> str:
                return "my_adapter"

            @property
            def supported_markets(self) -> List[str]:
                return ["US"]

            def validate_stock_code(self, stock_code: str) -> bool:
                # 实现验证逻辑
                pass

            def get_balance_sheet(self, stock_code: str, period: str) -> pd.DataFrame:
                # 实现获取资产负债表
                pass

            # ... 其他抽象方法
    """

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """
        适配器名称

        Returns:
            str: 适配器唯一标识名称
        """
        pass

    @property
    @abstractmethod
    def supported_markets(self) -> List[str]:
        """
        支持的市场列表

        Returns:
            List[str]: 支持的市场代码列表，如["A", "HK", "US"]
        """
        pass

    @property
    def priority(self) -> int:
        """
        适配器优先级

        数值越小优先级越高，用于多适配器场景

        Returns:
            int: 优先级数值，默认为100
        """
        return 100

    @abstractmethod
    def validate_stock_code(self, stock_code: str) -> bool:
        """
        验证股票代码格式

        Args:
            stock_code: 股票代码

        Returns:
            bool: 是否为有效格式

        Raises:
            InvalidStockCodeError: 股票代码格式无效时抛出
        """
        pass

    @abstractmethod
    def get_balance_sheet(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取资产负债表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的资产负债表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        pass

    @abstractmethod
    def get_income_statement(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取利润表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的利润表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        pass

    @abstractmethod
    def get_cash_flow(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取现金流量表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的现金流量表

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        pass

    @abstractmethod
    def get_indicators(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取财务指标

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 标准化的财务指标

        Raises:
            DataNotAvailableError: 数据不可用时抛出
            DataFormatError: 数据格式错误时抛出
        """
        pass

    def is_available(self) -> bool:
        """
        检查适配器是否可用

        用于健康检查和降级决策

        Returns:
            bool: 适配器是否可用
        """
        return True

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康状态信息，包含status、latency_ms等
        """
        return {
            "status": "healthy" if self.is_available() else "unavailable",
            "adapter": self.adapter_name,
            "supported_markets": self.supported_markets,
            "priority": self.priority,
        }

    def _validate_dataframe(self, df: pd.DataFrame, report_type: str) -> None:
        """
        验证DataFrame数据质量

        Args:
            df: 待验证的DataFrame
            report_type: 报表类型

        Raises:
            DataFormatError: 数据格式错误时抛出
        """
        if df is None or df.empty:
            raise DataFormatError(
                field_name=report_type,
                expected_format="非空DataFrame",
                actual_value="空DataFrame或None",
            )

    def _standardize_date_column(
        self, df: pd.DataFrame, date_column: str = "report_date"
    ) -> pd.DataFrame:
        """
        标准化日期列格式

        Args:
            df: DataFrame
            date_column: 日期列名

        Returns:
            pd.DataFrame: 日期标准化后的DataFrame
        """
        if date_column not in df.columns:
            return df

        df = df.copy()

        # 处理日期格式
        def parse_date(val: Any) -> str:
            if val is None:
                raise DataFormatError(
                    field_name=date_column,
                    expected_format="YYYY-MM-DD",
                    actual_value="None",
                )

            val_str = str(val)

            # 如果包含空格或T，说明是 datetime 格式
            if " " in val_str or "T" in val_str:
                # 处理 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS
                parts = val_str.replace("T", " ").split()[0]
                if "-" in parts:
                    return parts

            # 已经是 YYYY-MM-DD 格式
            if len(val_str) == 10 and ("-" in val_str):
                return val_str

            # YYYY/MM/DD 格式
            if "/" in val_str:
                parts = val_str.split("/")
                if len(parts) == 3:
                    year, month, day = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            # YYYYMMDD 格式
            if len(val_str) == 8 and val_str.isdigit():
                return f"{val_str[:4]}-{val_str[4:6]}-{val_str[6:8]}"

            raise DataFormatError(
                field_name=date_column,
                expected_format="YYYY-MM-DD",
                actual_value=val_str,
            )

        try:
            df[date_column] = df[date_column].apply(parse_date)
        except DataFormatError:
            raise
        except Exception as e:
            raise DataFormatError(
                field_name=date_column,
                expected_format="YYYY-MM-DD",
                actual_value=str(type(e)),
            )

        return df

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.adapter_name}, markets={self.supported_markets})"
