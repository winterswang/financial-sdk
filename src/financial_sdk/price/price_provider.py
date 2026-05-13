"""
价格提供者

从多个数据源获取股票价格：
- AkShare (A股主要源)
- Longbridge (港股、美股主要源)
- Yahoo Finance API (备用)
"""

import importlib
import json
import logging
import os
import re
import shutil
import subprocess
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


from ..cache import FinancialCache, get_cache
from ..exceptions import DataNotAvailableError, InvalidStockCodeError
from .price_models import PriceData, PriceResult


# 市场股票代码正则
A_STOCK_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")
HK_STOCK_PATTERN = re.compile(r"^\d{4,5}\.HK$")
US_STOCK_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")

# 市场到货币的映射
MARKET_CURRENCY = {
    "A": "CNY",
    "HK": "HKD",
    "US": "USD",
}

# 缓存 TTL (秒) - 5分钟
PRICE_CACHE_TTL = 5 * 60

# Yahoo Finance API 配置
YAHOO_FINANCE_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# SOCKS Proxy configuration (from environment)
SOCKS_PROXY_HOST = os.environ.get("SOCKS_PROXY_HOST", "127.0.0.1")
SOCKS_PROXY_PORT = int(os.environ.get("SOCKS_PROXY_PORT", "7890"))

# Longbridge 配置路径 (from environment)
LONGBRIDGE_CONFIG_PATH = os.environ.get("LONGBRIDGE_CONFIG_PATH", "")

logger = logging.getLogger(__name__)


def _get_socks_session() -> Any:
    """
    获取使用 SOCKS 代理的请求会话

    Returns:
        SOCKSProxyManager 实例
    """
    from urllib3.contrib.socks import SOCKSProxyManager

    proxy_url = f"socks5://{SOCKS_PROXY_HOST}:{SOCKS_PROXY_PORT}"
    return SOCKSProxyManager(proxy_url)


class PriceProvider:
    """
    价格数据统一提供者

    支持从以下来源获取价格：
    - A股: AkShare (主), Yahoo Finance (备)
    - 港股: Yahoo Finance (主), AkShare (备)
    - 美股: Yahoo Finance (主)

    使用示例:
        provider = PriceProvider()

        # 获取单只股票价格
        result = provider.get_price("600000.SH")
        if result.success:
            print(f"价格: {result.price.current_price}")

        # 批量获取
        results = provider.get_price_batch(["600000.SH", "0700.HK", "AAPL"])
    """

    def __init__(self, cache: Optional[FinancialCache] = None) -> None:
        """
        初始化价格提供者

        Args:
            cache: 缓存实例，默认使用全局缓存
        """
        self._cache = cache or get_cache()
        self._akshare: Optional[Any] = None

    def _get_akshare(self) -> Any:
        """懒加载akshare模块"""
        if self._akshare is None:
            try:
                self._akshare = importlib.import_module("akshare")
            except ImportError:
                raise DataNotAvailableError(
                    stock_code="N/A",
                    report_type="price",
                    reason="akshare模块未安装",
                    adapter_name="price_provider",
                )
        return self._akshare

    def _get_market(self, stock_code: str) -> str:
        """
        从股票代码识别市场

        Args:
            stock_code: 股票代码

        Returns:
            市场代码 (A, HK, US)

        Raises:
            InvalidStockCodeError: 无法识别市场时抛出
        """
        if A_STOCK_PATTERN.match(stock_code):
            return "A"
        elif HK_STOCK_PATTERN.match(stock_code):
            return "HK"
        elif US_STOCK_PATTERN.match(stock_code):
            return "US"
        else:
            raise InvalidStockCodeError(
                stock_code=stock_code,
                expected_format="A股: 600000.SH, 港股: 0700.HK, 美股: AAPL",
                market="unknown",
            )

    def _get_price_from_yahoo(
        self, stock_code: str, market: str
    ) -> Optional[PriceData]:
        """
        从 Yahoo Finance API 获取价格

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            PriceData 或 None
        """
        # 转换为 Yahoo Finance 格式
        yahoo_symbol = self._to_yahoo_symbol(stock_code, market)
        if not yahoo_symbol:
            return None

        url = f"{YAHOO_FINANCE_BASE_URL}{yahoo_symbol}?interval=1d&range=5d"

        try:
            # 使用 SOCKS 代理会话 (解决代理环境下 Yahoo Finance 连接被重置的问题)
            session = _get_socks_session()
            resp = session.request("GET", url, headers=YAHOO_HEADERS, timeout=10)
            if resp.status != 200:
                return None
            data = resp.json()

            result = data.get("chart", {}).get("result", [])
            if not result:
                return None

            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice") or meta.get("previousClose")
            currency = meta.get("currency", MARKET_CURRENCY.get(market, "USD"))

            if price is None:
                return None

            # 获取最近交易日
            timestamps = result[0].get("timestamp", [])
            if timestamps:
                from datetime import timezone

                dt = datetime.fromtimestamp(timestamps[-1], tz=timezone.utc)
                price_date = dt.strftime("%Y-%m-%d")
            else:
                price_date = datetime.now().strftime("%Y-%m-%d")

            # 获取市值 (Yahoo Finance meta 中可能包含)
            market_cap = meta.get("marketCap")

            return PriceData(
                stock_code=stock_code,
                market=market,
                current_price=float(price),
                currency=currency,
                price_date=price_date,
                source="yahoo",
                market_cap=float(market_cap) if market_cap else None,
            )

        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

    def _to_yahoo_symbol(self, stock_code: str, market: str) -> Optional[str]:
        """
        将标准股票代码转换为 Yahoo Finance 格式

        Args:
            stock_code: 标准股票代码
            market: 市场代码

        Returns:
            Yahoo Finance 格式的股票代码
        """
        if market == "A":
            # A股: 600000.SH -> 600000.SS, 000001.SZ -> 000001.SZ
            code, suffix = stock_code.split(".")
            if suffix == "SH":
                return f"{code}.SS"
            else:
                return f"{code}.SZ"
        elif market == "HK":
            # 港股: 0700.HK -> 0700.HK (4位数字，补前导零)
            code = stock_code.replace(".HK", "")
            # 补齐4位
            code = code.lstrip("0").zfill(4)
            return f"{code}.HK"
        elif market == "US":
            # 美股直接返回
            return stock_code
        return None

    def _get_price_from_akshare(
        self, stock_code: str, market: str
    ) -> Optional[PriceData]:
        """
        从 AkShare 获取价格

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            PriceData 或 None
        """
        akshare = self._get_akshare()

        try:
            if market == "A":
                # A股: 使用 spot 接口获取所有股票，再筛选
                df = akshare.stock_zh_a_spot()
                # 匹配股票代码 (格式: sh600000 或 sz000001)
                search_code = stock_code.replace(".", "").lower()
                if search_code.startswith("sh") or search_code.startswith("sz"):
                    matches = df[df["代码"].str.lower() == search_code]
                else:
                    # 尝试直接匹配
                    matches = df[df["代码"].str.contains(stock_code.split(".")[0])]
                    # 进一步筛选上海/深圳
                    suffix = stock_code.split(".")[1]
                    if suffix == "SH":
                        matches = matches[matches["代码"].str.startswith("sh")]
                    else:
                        matches = matches[matches["代码"].str.startswith("sz")]

                if matches.empty:
                    return None

                row = matches.iloc[0]
                return PriceData(
                    stock_code=stock_code,
                    market=market,
                    current_price=float(row["最新价"]),
                    currency="CNY",
                    price_date=datetime.now().strftime("%Y-%m-%d"),
                    source="akshare",
                )

            elif market == "HK":
                # 港股: 使用 spot 接口
                df = akshare.stock_hk_spot_em()
                # 匹配股票代码 (格式如 00700)
                code = stock_code.replace(".HK", "").lstrip("0")
                if len(code) < 4:
                    code = code.zfill(4)
                matches = df[df["代码"] == code]
                if matches.empty:
                    return None

                row = matches.iloc[0]
                return PriceData(
                    stock_code=stock_code,
                    market=market,
                    current_price=float(row["最新价"]),
                    currency="HKD",
                    price_date=datetime.now().strftime("%Y-%m-%d"),
                    source="akshare",
                )

        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

        return None

    def _get_market_cap_from_longbridge_sdk(
        self, stock_code: str, market: str
    ) -> Optional[float]:
        """
        从 Longbridge OpenAPI SDK 获取市值

        Longbridge static_info 返回 total_shares/outstanding_shares，
        结合实时报价计算市值。

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            市值（价格货币单位）或 None
        """
        try:
            from longport.openapi import Config, QuoteContext
            import json

            # 1. 尝试从 LONGBRIDGE_CONFIG_PATH 环境变量
            config_path = LONGBRIDGE_CONFIG_PATH

            # 2. 尝试从 Longbridge Terminal token 文件自动发现
            if not config_path:
                token_dir = Path.home() / ".longbridge" / "openapi" / "tokens"
                if token_dir.exists():
                    token_files = list(token_dir.iterdir())
                    if token_files:
                        # 使用最新的 token 文件
                        token_file = max(token_files, key=lambda p: p.stat().st_mtime)
                        with open(token_file, "r") as f:
                            token_data = json.load(f)

                        client_id = token_data.get("client_id", "")
                        access_token = token_data.get("access_token", "")

                        if client_id and access_token:
                            config = Config(
                                app_key=client_id,
                                app_secret="",
                                access_token=access_token,
                            )
                            ctx = QuoteContext(config)

                            # 转换代码格式
                            lb_symbol = self._to_longbridge_symbol(stock_code, market)
                            if not lb_symbol:
                                return None

                            # 获取静态信息 (含 total_shares)
                            static_info = ctx.static_info([lb_symbol])
                            if static_info:
                                info = static_info[0]
                                total_shares = getattr(
                                    info, "total_shares", None
                                ) or getattr(info, "outstanding_shares", None)
                                if total_shares and total_shares > 0:
                                    # 获取实时价格
                                    quotes = ctx.quote([lb_symbol])
                                    if quotes:
                                        price = float(quotes[0].last_done)
                                        return price * total_shares

            # 3. 尝试从 YAML 配置
            if config_path and Path(config_path).exists():
                with open(config_path, "r") as f:
                    config_data = yaml.safe_load(f)
                config = Config(
                    app_key=config_data["app_key"],
                    app_secret=config_data["app_secret"],
                    access_token=config_data["access_token"],
                )
                ctx = QuoteContext(config)
                lb_symbol = self._to_longbridge_symbol(stock_code, market)
                if lb_symbol:
                    static_info = ctx.static_info([lb_symbol])
                    if static_info:
                        info = static_info[0]
                        total_shares = getattr(info, "total_shares", None) or getattr(
                            info, "outstanding_shares", None
                        )
                        if total_shares and total_shares > 0:
                            quotes = ctx.quote([lb_symbol])
                            if quotes:
                                price = float(quotes[0].last_done)
                                return price * total_shares

        except Exception as e:
            error_msg = str(e)
            # 如果是 token 过期，尝试刷新
            if "401004" in error_msg or "token invalid" in error_msg.lower():
                refreshed = self._refresh_longbridge_token_file()
                if refreshed:
                    # 重试一次
                    try:
                        from longport.openapi import Config, QuoteContext
                        import json

                        token_dir = Path.home() / ".longbridge" / "openapi" / "tokens"
                        if token_dir.exists():
                            token_files = list(token_dir.iterdir())
                            if token_files:
                                token_file = max(
                                    token_files, key=lambda p: p.stat().st_mtime
                                )
                                with open(token_file, "r") as f:
                                    token_data = json.load(f)
                                client_id = token_data.get("client_id", "")
                                access_token = token_data.get("access_token", "")
                                if client_id and access_token:
                                    config = Config(
                                        app_key=client_id,
                                        app_secret="",
                                        access_token=access_token,
                                    )
                                    ctx = QuoteContext(config)
                                    lb_symbol = self._to_longbridge_symbol(
                                        stock_code, market
                                    )
                                    if lb_symbol:
                                        static_info = ctx.static_info([lb_symbol])
                                        if static_info:
                                            info = static_info[0]
                                            total_shares = getattr(
                                                info, "total_shares", None
                                            ) or getattr(
                                                info, "outstanding_shares", None
                                            )
                                            if total_shares and total_shares > 0:
                                                quotes = ctx.quote([lb_symbol])
                                                if quotes:
                                                    price = float(quotes[0].last_done)
                                                    return price * total_shares
                    except Exception as e2:
                        logger.debug("Longbridge SDK retry failed for %s: %s", stock_code, e2)
            else:
                logger.debug("Longbridge SDK market cap failed for %s: %s", stock_code, e)

        return None

    def _refresh_longbridge_token_file(self) -> bool:
        """
        刷新 Longbridge Terminal token 文件中的 access_token

        Returns:
            是否刷新成功
        """
        import base64

        try:
            token_dir = Path.home() / ".longbridge" / "openapi" / "tokens"
            if not token_dir.exists():
                return False

            token_files = list(token_dir.iterdir())
            if not token_files:
                return False

            token_file = max(token_files, key=lambda p: p.stat().st_mtime)
            with open(token_file, "r") as f:
                token_data = json.load(f)

            access_token = token_data.get("access_token", "")
            if not access_token:
                return False

            # 解析 JWT 获取过期时间
            payload = access_token.split(".")[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            expired_at = str(decoded.get("exp", ""))

            # 通过 HTTP API 刷新
            import requests as req

            base_url = "https://openapi.lbkrs.com"
            url = f"{base_url}/v1/token/refresh?expired_at={expired_at}"
            headers = {"Authorization": access_token}

            # 尝试直连
            try:
                resp = req.get(url, headers=headers, timeout=10)
            except Exception:
                logger.debug("Direct connection failed, trying proxy", exc_info=True)
                # 直连失败，尝试 SOCKS 代理
                try:
                    session = _get_socks_session()
                    resp = session.request("GET", url, headers=headers, timeout=10)
                except Exception:
                    logger.debug("Check failed, returning False", exc_info=True)
                    return False

            if not hasattr(resp, "status_code"):
                # SOCKS 响应
                if getattr(resp, "status", 0) != 200:
                    return False
                result = resp.json()
            else:
                if resp.status_code != 200:
                    return False
                result = resp.json()

            if result.get("code") != 0:
                return False

            new_token = result.get("data", {}).get("access_token")
            if not new_token:
                return False

            # 更新 token 文件
            token_data["access_token"] = new_token
            new_payload = new_token.split(".")[1]
            np = 4 - len(new_payload) % 4
            if np != 4:
                new_payload += "=" * np
            new_decoded = json.loads(base64.urlsafe_b64decode(new_payload))
            token_data["expires_at"] = new_decoded.get("exp", 0)

            with open(token_file, "w") as f:
                json.dump(token_data, f, indent=2)

            logger.info("Longbridge token refreshed successfully")
            return True

        except Exception as e:
            logger.debug("Failed to refresh Longbridge token: %s", e)
            return False

    def _get_market_cap_from_eastmoney(
        self, stock_code: str, market: str
    ) -> Optional[float]:
        """
        从东方财富个股API获取市值

        东方财富的 push2 API 返回个股详情，包括总市值 (f116)。
        这是获取美股/港股/A股市值最可靠的方式之一。

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            市值（价格货币单位）或 None
        """
        try:
            session = _get_socks_session()

            if market == "US":
                # 东方财富美股代码格式: 105.CODE (纳斯达克) 或 106.CODE (纽交所)
                code = stock_code.replace(".US", "")
                # 尝试纳斯达克(105)和纽交所(106)
                for prefix in ["105", "106"]:
                    secid = f"{prefix}.{code}"
                    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f116,f117"
                    resp = session.request(
                        "GET", url, headers=YAHOO_HEADERS, timeout=10
                    )
                    if resp.status == 200:
                        data = resp.json()
                        market_cap = data.get("data", {}).get("f116")
                        if market_cap and market_cap > 0:
                            return float(market_cap)

            elif market == "A":
                # 东方财富A股代码: 1.CODE(SH) 或 0.CODE(SZ)
                parts = stock_code.split(".")
                code = parts[0]
                suffix = parts[1] if len(parts) > 1 else ""
                prefix = "1" if suffix == "SH" else "0"
                secid = f"{prefix}.{code}"
                url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f116,f117"
                resp = session.request("GET", url, headers=YAHOO_HEADERS, timeout=10)
                if resp.status == 200:
                    data = resp.json()
                    market_cap = data.get("data", {}).get("f116")
                    if market_cap and market_cap > 0:
                        return float(market_cap)

            elif market == "HK":
                # 东方财富港股代码: 116.CODE
                code = stock_code.replace(".HK", "").lstrip("0").zfill(5)
                secid = f"116.{code}"
                url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f57,f116,f117"
                resp = session.request("GET", url, headers=YAHOO_HEADERS, timeout=10)
                if resp.status == 200:
                    data = resp.json()
                    market_cap = data.get("data", {}).get("f116")
                    if market_cap and market_cap > 0:
                        return float(market_cap)

        except Exception:
            logger.debug("Silently skipped", exc_info=True)
            pass

        return None

    def _get_market_cap_from_yahoo(
        self, stock_code: str, market: str
    ) -> Optional[float]:
        """
        从 Yahoo Finance quoteSummary API 获取市值

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            市值（USD）或 None
        """
        yahoo_symbol = self._to_yahoo_symbol(stock_code, market)
        if not yahoo_symbol:
            return None

        url = (
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
            f"{yahoo_symbol}?modules=defaultKeyStatistics"
        )

        try:
            session = _get_socks_session()
            resp = session.request("GET", url, headers=YAHOO_HEADERS, timeout=10)
            if resp.status != 200:
                return None
            data = resp.json()

            result_list = data.get("quoteSummary", {}).get("result", [])
            if not result_list:
                return None

            stats = result_list[0].get("defaultKeyStatistics", {})
            market_cap_raw = stats.get("marketCap", {}).get("raw")
            if market_cap_raw:
                return float(market_cap_raw)
        except Exception:
            logger.debug("Silently skipped", exc_info=True)
            pass

        return None

    def _get_market_cap_from_longbridge_cli(
        self, stock_code: str, market: str
    ) -> Optional[float]:
        """
        从 LongBridge CLI static 命令获取市值

        LongBridge CLI 的 static 命令返回 total_shares，
        结合实时报价计算市值。

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            市值（价格货币单位）或 None
        """
        # 转换代码格式
        lb_symbol = self._to_longbridge_symbol(stock_code, market)
        if not lb_symbol:
            return None

        # 查找 LongBridge CLI 路径
        cli_paths = [
            "longbridge",
            "/Users/wangguangchao/bin/longbridge",
            "/usr/local/bin/longbridge",
            "/opt/homebrew/bin/longbridge",
            os.path.expanduser("~/bin/longbridge"),
        ]
        cli_path = None
        for path in cli_paths:
            if shutil.which(path):
                cli_path = path
                break

        if not cli_path:
            return None

        try:
            # 获取静态信息（含 total_shares）
            result = subprocess.run(
                [cli_path, "static", lb_symbol, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return None

            static_data = json.loads(result.stdout)
            if not static_data:
                return None

            info = static_data[0]
            total_shares = info.get("total_shares")
            if not total_shares:
                return None

            total_shares = float(total_shares)
            if total_shares <= 0:
                return None

            # 获取实时价格
            price_result = subprocess.run(
                [cli_path, "quote", lb_symbol, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if price_result.returncode != 0:
                return None

            quote_data = json.loads(price_result.stdout)
            if not quote_data:
                return None

            last_price = quote_data[0].get("last")
            if not last_price:
                return None

            return float(last_price) * total_shares

        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

    def get_market_cap(self, stock_code: str) -> Optional[float]:
        """
        获取股票市值

        Args:
            stock_code: 股票代码

        Returns:
            市值（价格货币单位）或 None
        """
        market = self._get_market(stock_code)

        # 1. 先从价格缓存中获取
        result = self.get_price(stock_code, market=market)
        if result.success and result.price and result.price.market_cap:
            return result.price.market_cap

        # 2. 从东方财富个股API获取 (最可靠，支持US/A/HK)
        market_cap = self._get_market_cap_from_eastmoney(stock_code, market)
        if market_cap:
            return market_cap

        # 3. 从 Longbridge SDK 获取 (含 total_shares)
        market_cap = self._get_market_cap_from_longbridge_sdk(stock_code, market)
        if market_cap:
            return market_cap

        # 3.5. 从 LongBridge CLI static 命令获取 (含 total_shares)
        market_cap = self._get_market_cap_from_longbridge_cli(stock_code, market)
        if market_cap:
            return market_cap

        # 4. 从 Yahoo quoteSummary API 获取
        market_cap = self._get_market_cap_from_yahoo(stock_code, market)
        if market_cap:
            return market_cap

        # 5. 从 AkShare 行情获取
        try:
            akshare = self._get_akshare()

            if market == "US":
                df = akshare.stock_us_spot_em()
                # AkShare 美股代码格式: "105.PDD", 匹配后缀
                code = stock_code.replace(".US", "")
                matches = df[df["代码"].str.endswith(f".{code}")]
                if matches.empty:
                    # 也尝试直接匹配
                    matches = df[df["代码"] == code]
                if not matches.empty:
                    row = matches.iloc[0]
                    for col in ["总市值", "市值"]:
                        if col in df.columns:
                            val = row.get(col)
                            if val and str(val) != "nan":
                                return float(val)
            elif market == "A":
                df = akshare.stock_zh_a_spot()
                search_code = stock_code.replace(".", "").lower()
                matches = df[df["代码"].str.lower() == search_code]
                if not matches.empty:
                    row = matches.iloc[0]
                    for col in ["总市值"]:
                        if col in df.columns:
                            val = row.get(col)
                            if val and str(val) != "nan":
                                return float(val)
            elif market == "HK":
                df = akshare.stock_hk_spot_em()
                code = stock_code.replace(".HK", "").lstrip("0").zfill(4)
                matches = df[df["代码"] == code]
                if not matches.empty:
                    row = matches.iloc[0]
                    for col in ["总市值"]:
                        if col in df.columns:
                            val = row.get(col)
                            if val and str(val) != "nan":
                                return float(val)
        except Exception:
            logger.debug("Silently skipped", exc_info=True)
            pass

        return None

    def _get_longbridge_context(self) -> Any:
        """
        获取 Longbridge QuoteContext

        Returns:
            QuoteContext 实例或 None
        """
        try:
            from longport.openapi import Config, QuoteContext
            import yaml

            with open(LONGBRIDGE_CONFIG_PATH, "r") as f:
                config_data = yaml.safe_load(f)

            lp_config = Config(
                app_key=config_data["app_key"],
                app_secret=config_data["app_secret"],
                access_token=config_data["access_token"],
            )
            return QuoteContext(lp_config)
        except Exception:
            logger.debug("Analysis failed, returning None", exc_info=True)
            return None

    def _refresh_longbridge_token(self) -> bool:
        """
        刷新 Longbridge access token

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            import requests
            import base64
            import json

            # Load current config
            with open(LONGBRIDGE_CONFIG_PATH, "r") as f:
                config_data = yaml.safe_load(f)

            # Parse JWT to get expired_at
            token = config_data["access_token"]
            parts = token.split(".")
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            expired_at = datetime.fromtimestamp(
                decoded["exp"], tz=timezone.utc
            ).isoformat()

            # Call refresh API
            base_url = config_data.get("http_url", "https://openapi.lbkrs.com").rstrip(
                "/"
            )
            url = f"{base_url}/v1/token/refresh"

            headers = {"Authorization": token}
            params = {"expired_at": expired_at}

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                return False

            new_token = result["data"].get("access_token")
            if new_token:
                # Update config file
                config_data["access_token"] = new_token
                with open(LONGBRIDGE_CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.dump(config_data, f, sort_keys=False, allow_unicode=True)
                return True

            return False

        except Exception:
            logger.debug("Check failed, returning False", exc_info=True)
            return False

    def _get_price_from_longbridge(
        self, stock_code: str, market: str
    ) -> Optional[PriceData]:
        """
        从 Longbridge 获取价格

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            PriceData 或 None
        """
        ctx = self._get_longbridge_context()
        if not ctx:
            return None

        try:
            # 转换为 Longbridge 格式
            lb_symbol = self._to_longbridge_symbol(stock_code, market)
            if not lb_symbol:
                return None

            # 获取实时报价
            quotes = ctx.quote([lb_symbol])
            if not quotes:
                return None

            quote = quotes[0]
            static_info = ctx.static_info([lb_symbol])
            if not static_info:
                return None

            return PriceData(
                stock_code=stock_code,
                market=market,
                current_price=float(quote.last_done),
                currency=str(static_info[0].currency)
                if hasattr(static_info[0], "currency")
                else MARKET_CURRENCY.get(market, "USD"),
                price_date=datetime.now().strftime("%Y-%m-%d"),
                source="longbridge",
            )

        except Exception as e:
            # 检查是否是认证错误，尝试刷新 token 后重试
            error_msg = str(e)
            if any(
                keyword in error_msg.lower()
                for keyword in ["unauthorized", "401", "403", "token", "auth"]
            ):
                if self._refresh_longbridge_token():
                    # 重新创建 context 并重试
                    ctx = self._get_longbridge_context()
                    if ctx:
                        try:
                            quotes = ctx.quote([lb_symbol])
                            if quotes:
                                quote = quotes[0]
                                static_info = ctx.static_info([lb_symbol])
                                if static_info:
                                    return PriceData(
                                        stock_code=stock_code,
                                        market=market,
                                        current_price=float(quote.last_done),
                                        currency=str(static_info[0].currency)
                                        if hasattr(static_info[0], "currency")
                                        else MARKET_CURRENCY.get(market, "USD"),
                                        price_date=datetime.now().strftime("%Y-%m-%d"),
                                        source="longbridge",
                                    )
                        except Exception:
                            logger.debug("Silently skipped", exc_info=True)
                            pass
            return None

    def _to_longbridge_symbol(self, stock_code: str, market: str) -> Optional[str]:
        """
        将标准股票代码转换为 Longbridge 格式

        Args:
            stock_code: 标准股票代码
            market: 市场代码

        Returns:
            Longbridge 格式的股票代码
        """
        if market == "A":
            # A股: 600000.SH -> 600000.SH
            return stock_code
        elif market == "HK":
            # 港股: 0700.HK -> 700.HK (去掉前导零)
            code = stock_code.replace(".HK", "").lstrip("0")
            return f"{code}.HK"
        elif market == "US":
            # 美股: AAPL -> AAPL.US
            return f"{stock_code}.US"
        return None

    def _get_price_with_cache(self, stock_code: str, market: str) -> PriceResult:
        """
        带缓存的价格获取

        Args:
            stock_code: 股票代码
            market: 市场代码

        Returns:
            PriceResult
        """
        cache_key = f"price_{market}_{stock_code}"

        # 尝试从缓存获取
        hit, cached = self._cache.get(cache_key)
        if hit and cached:
            return PriceResult(success=True, price=cached)

        # 根据市场选择数据源策略
        if market == "A":
            # A股: AkShare 主, Yahoo 备, Longbridge 备
            price = self._get_price_from_akshare(stock_code, market)
            if not price:
                price = self._get_price_from_yahoo(stock_code, market)
            if not price:
                price = self._get_price_from_longbridge(stock_code, market)
        elif market == "HK":
            # 港股: Longbridge 主, Yahoo 备
            price = self._get_price_from_longbridge(stock_code, market)
            if not price:
                price = self._get_price_from_yahoo(stock_code, market)
            if not price:
                price = self._get_price_from_akshare(stock_code, market)
        elif market == "US":
            # 美股: Longbridge 主, Yahoo 备
            price = self._get_price_from_longbridge(stock_code, market)
            if not price:
                price = self._get_price_from_yahoo(stock_code, market)
        else:
            price = None

        if price:
            # 如果没有市值，尝试补充获取
            if price.market_cap is None:
                # 东方财富个股API (最可靠)
                market_cap = self._get_market_cap_from_eastmoney(stock_code, market)
                if not market_cap:
                    # Longbridge SDK (含 total_shares)
                    market_cap = self._get_market_cap_from_longbridge_sdk(
                        stock_code, market
                    )
                if not market_cap:
                    # Yahoo quoteSummary
                    market_cap = self._get_market_cap_from_yahoo(stock_code, market)
                if market_cap:
                    price.market_cap = market_cap
            # 存入缓存
            self._cache.set(cache_key, price, PRICE_CACHE_TTL)
            return PriceResult(success=True, price=price)
        else:
            return PriceResult(
                success=False,
                error=f"无法获取 {stock_code} 的价格数据",
            )

    def get_price(self, stock_code: str, market: Optional[str] = None) -> PriceResult:
        """
        获取股票价格

        Args:
            stock_code: 股票代码
                - A股: 600000.SH, 000001.SZ
                - 港股: 0700.HK, 0992.HK
                - 美股: AAPL, MSFT
            market: 市场代码，可选 (会自动识别)

        Returns:
            PriceResult: 包含价格数据或错误信息
        """
        # 识别市场
        if market is None:
            market = self._get_market(stock_code)

        try:
            return self._get_price_with_cache(stock_code, market)
        except InvalidStockCodeError as e:
            return PriceResult(success=False, error=str(e))
        except DataNotAvailableError as e:
            return PriceResult(success=False, error=str(e))
        except Exception as e:
            return PriceResult(success=False, error=f"获取价格失败: {e}")

    def get_price_batch(self, stock_codes: List[str]) -> Dict[str, PriceResult]:
        """
        批量获取股票价格

        Args:
            stock_codes: 股票代码列表

        Returns:
            Dict[str, PriceResult]: 股票代码到结果的映射
        """
        results = {}
        for code in stock_codes:
            results[code] = self.get_price(code)
        return results

    def get_historical_price(
        self, stock_code: str, market: Optional[str] = None, days: int = 1
    ) -> Optional[float]:
        """
        获取历史收盘价

        Args:
            stock_code: 股票代码
            market: 市场代码
            days: 往前取多少天的数据 (默认1天)

        Returns:
            收盘价或 None
        """
        if market is None:
            market = self._get_market(stock_code)

        yahoo_symbol = self._to_yahoo_symbol(stock_code, market)
        if not yahoo_symbol:
            return None

        url = f"{YAHOO_FINANCE_BASE_URL}{yahoo_symbol}?interval=1d&range={days + 5}d"

        try:
            session = _get_socks_session()
            resp = session.request("GET", url, headers=YAHOO_HEADERS, timeout=10)
            if resp.status != 200:
                return None
            data = resp.json()

            result = data.get("chart", {}).get("result", [])
            if not result:
                return None

            quotes = result[0].get("indicators", {}).get("quote", [{}])
            if not quotes:
                return None

            closes = quotes[0].get("close", [])
            if closes:
                # 返回最近的非空收盘价
                for price in reversed(closes):
                    if price is not None:
                        return float(price)

        except Exception:
            logger.debug("Silently skipped", exc_info=True)
            pass

        return None

    def invalidate_cache(self, stock_code: Optional[str] = None) -> None:
        """
        使缓存失效

        Args:
            stock_code: 特定股票代码或 None (全部)
        """
        if stock_code:
            market = self._get_market(stock_code)
            cache_key = f"price_{market}_{stock_code}"
            self._cache.delete(cache_key)
        else:
            # 清除所有价格缓存
            self._cache.invalidate_pattern("price_*")


# 全局单例
_global_provider: Optional[PriceProvider] = None


def get_price_provider() -> PriceProvider:
    """获取全局价格提供者实例"""
    global _global_provider
    if _global_provider is None:
        _global_provider = PriceProvider()
    return _global_provider


def reset_price_provider() -> None:
    """重置全局价格提供者"""
    global _global_provider
    _global_provider = None
