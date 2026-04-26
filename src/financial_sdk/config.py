"""
配置管理模块

管理SDK配置，支持YAML配置文件和环境变量。
"""

from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

import yaml


class Config:
    """配置管理类"""

    DEFAULT_CONFIG_PATH = (
        Path(__file__).parent.parent.parent / "config" / "default.yaml"
    )

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        初始化配置

        Args:
            config_path: 配置文件路径
        """
        self._config: Dict[str, Any] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None) -> None:
        """加载配置文件"""
        if config_path is None:
            config_path = self.DEFAULT_CONFIG_PATH
        else:
            config_path = Path(config_path)

        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "cache": {
                "enabled": True,
                "max_size": 1000,
                "ttl_static": 24 * 60 * 60,  # 24小时
                "ttl_dynamic": 60 * 60,  # 1小时
            },
            "adapter": {
                "ashare": {
                    "enabled": True,
                    "priority": 1,
                },
                "hk": {
                    "enabled": True,
                    "priority": 1,
                },
                "us": {
                    "enabled": True,
                    "priority": 1,
                    "use_easymoney_fallback": True,
                },
            },
            "monitor": {
                "enabled": True,
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔的路径 (如 "cache.enabled")
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键，支持点号分隔的路径
            value: 配置值
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def to_dict(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config.copy()


# 全局配置实例
_global_config: Optional[Config] = None
_config_lock = Lock()


def get_config() -> Config:
    """获取全局配置实例（线程安全）"""
    global _global_config
    if _global_config is None:
        with _config_lock:
            if _global_config is None:
                _global_config = Config()
    return _global_config


def set_config(config: Config) -> None:
    """设置全局配置实例"""
    global _global_config
    with _config_lock:
        _global_config = config
