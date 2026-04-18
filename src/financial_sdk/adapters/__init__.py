"""适配器模块"""

from ..base_adapter import BaseAdapter
from .ashare_adapter import ASHareAdapter
from .hk_adapter import HKAdapter
from .us_adapter import USAdapter

__all__ = [
    "BaseAdapter",
    "ASHareAdapter",
    "HKAdapter",
    "USAdapter",
]
