"""
价格数据模型

定义价格查询的结果数据模型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PriceData:
    """
    价格数据模型

    Attributes:
        stock_code: 股票代码 (标准格式，如 600000.SH, 0700.HK, AAPL)
        market: 市场代码 (A, HK, US)
        current_price: 当前价格
        currency: 货币代码 (CNY, HKD, USD)
        price_date: 价格日期 (YYYY-MM-DD)
        source: 数据源 ("yahoo", "akshare")
        timestamp: 数据获取时间戳
    """

    stock_code: str
    market: str
    current_price: float
    currency: str
    price_date: Optional[str] = None
    source: str = "yahoo"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "stock_code": self.stock_code,
            "market": self.market,
            "current_price": self.current_price,
            "currency": self.currency,
            "price_date": self.price_date,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class PriceResult:
    """
    价格查询结果

    Attributes:
        success: 查询是否成功
        price: 价格数据 (成功时)
        error: 错误信息 (失败时)
    """

    success: bool
    price: Optional[PriceData] = None
    error: Optional[str] = None

    def __bool__(self) -> bool:
        """支持 bool(result) 判断成功与否"""
        return self.success
