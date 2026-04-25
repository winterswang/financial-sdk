"""
Longbridge CLI 适配器

通过子进程调用 longbridge CLI 获取财务数据。
需要提前安装 longbridge CLI 并完成认证。

安装方式:
    curl -sSL https://github.com/longbridge/longbridge-terminal/raw/main/install | sh

认证方式:
    longbridge auth login
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from ..base_adapter import BaseAdapter
from ..exceptions import DataNotAvailableError, InvalidStockCodeError

logger = logging.getLogger(__name__)


class LongbridgeCLIAdapter(BaseAdapter):
    """
    Longbridge CLI 适配器

    通过子进程调用 longbridge CLI 获取财务数据。

    支持的市场和功能:
    - HK (港股): 财务报表、实时行情、估值指标、资金流向、分红、机构评级等
    - US (美股): 财务报表、实时行情、估值指标、分红、机构评级等
    - CN (A股): 实时行情、估值指标等

    股票代码格式:
    - 港股: 0700.HK, 9988.HK
    - 美股: AAPL.US, TSLA.US
    - A股: 600519.SH, 000001.SZ
    """

    # 股票代码正则
    HK_STOCK_PATTERN = re.compile(r"^\d{4,5}\.HK$")
    US_STOCK_PATTERN = re.compile(r"^[A-Z]{1,5}\.US$|^[A-Z]{1,5}$")
    CN_STOCK_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")

    # LongBridge 字段名到标准字段名的映射
    # 用于统一不同数据源的字段名
    FIELD_MAPPING = {
        # 利润表字段
        "营业收入(HKD)": "revenue",
        "营业收入(USD)": "revenue",
        "营业收入(CNY)": "revenue",
        "净利润(HKD)": "net_profit",
        "净利润(USD)": "net_profit",
        "净利润(CNY)": "net_profit",
        "毛利(HKD)": "gross_profit",
        "毛利(USD)": "gross_profit",
        "毛利(CNY)": "gross_profit",
        "营业利润(HKD)": "operating_profit",
        "营业利润(USD)": "operating_profit",
        "营业利润(CNY)": "operating_profit",
        "毛利率": "gross_margin",
        "净利率": "net_margin",
        "ROE": "roe",
        "每股收益(HKD)": "eps",
        "每股收益(USD)": "eps",
        "每股收益(CNY)": "eps",
        "营业利润/经营现金流": "operating_profit_to_operating_cash_flow",
        # 资产负债表字段
        "总资产(HKD)": "total_assets",
        "总资产(USD)": "total_assets",
        "总资产(CNY)": "total_assets",
        "总负债(HKD)": "total_liabilities",
        "总负债(USD)": "total_liabilities",
        "总负债(CNY)": "total_liabilities",
        "总权益(HKD)": "total_equity",
        "总权益(USD)": "total_equity",
        "总权益(CNY)": "total_equity",
        "流动资产(HKD)": "current_assets",
        "流动负债(HKD)": "current_liabilities",
        "现金及等价物(HKD)": "cash_and_equivalents",
        "现金及等价物(USD)": "cash_and_equivalents",
        "现金及等价物(CNY)": "cash_and_equivalents",
        "应收账款(HKD)": "accounts_receivable",
        "应付账款(HKD)": "accounts_payable",
        "存货(HKD)": "inventory",
        # 现金流量表字段
        "经营现金流(HKD)": "operating_cash_flow",
        "投资现金流(HKD)": "investing_cash_flow",
        "融资现金流(HKD)": "financing_cash_flow",
        "经营现金流(USD)": "operating_cash_flow",
        "投资现金流(USD)": "investing_cash_flow",
        "融资现金流(USD)": "financing_cash_flow",
    }

    def __init__(self, cli_path: str = "longbridge") -> None:
        """
        初始化 Longbridge CLI 适配器

        Args:
            cli_path: longbridge CLI 路径，默认 "longbridge"
        """
        self._cli_path = cli_path
        self._check_cli()

    def _normalize_stock_code(self, stock_code: str) -> str:
        """
        标准化股票代码

        LongBridge API 格式要求:
        - 港股: 0700.HK -> 700.HK (去除前导零)
        - 美股: AAPL -> AAPL.US (添加后缀)

        Args:
            stock_code: 原始股票代码

        Returns:
            str: 标准化后的股票代码
        """
        # 港股: 0700.HK -> 700.HK
        if self.HK_STOCK_PATTERN.match(stock_code):
            code = stock_code.split(".")[0]
            # 去除前导零
            code_without_zeros = str(int(code))
            return f"{code_without_zeros}.HK"

        # 美股: AAPL -> AAPL.US (如果已经是 AAPL.US 格式则不处理)
        if self.US_STOCK_PATTERN.match(stock_code):
            if stock_code.endswith(".US"):
                return stock_code
            return f"{stock_code}.US"

        return stock_code

    def _check_cli(self) -> bool:
        """检查 CLI 是否可用"""
        cli = shutil.which(self._cli_path)
        if cli is None:
            return False
        # 尝试执行 version 命令
        try:
            result = subprocess.run(
                [self._cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_command(self, args: List[str]) -> Dict[str, Any]:
        """
        执行 longbridge CLI 命令

        Args:
            args: 命令参数列表

        Returns:
            Dict: JSON 解析后的结果

        Raises:
            DataNotAvailableError: 命令执行失败时抛出
        """
        try:
            result = subprocess.run(
                [self._cli_path] + args,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise DataNotAvailableError(
                    stock_code="N/A",
                    report_type="cli",
                    reason=f"CLI error: {result.stderr}",
                    adapter_name=self.adapter_name,
                )
            return json.loads(result.stdout)
        except subprocess.TimeoutExpired:
            raise DataNotAvailableError(
                stock_code="N/A",
                report_type="cli",
                reason="Command timeout",
                adapter_name=self.adapter_name,
            )
        except json.JSONDecodeError as e:
            raise DataNotAvailableError(
                stock_code="N/A",
                report_type="cli",
                reason=f"Failed to parse JSON: {e}",
                adapter_name=self.adapter_name,
            )
        except FileNotFoundError:
            raise DataNotAvailableError(
                stock_code="N/A",
                report_type="cli",
                reason=f"CLI not found at {self._cli_path}",
                adapter_name=self.adapter_name,
            )

    @property
    def adapter_name(self) -> str:
        return "longbridge_cli"

    @property
    def supported_markets(self) -> List[str]:
        return ["HK", "US", "A"]

    @property
    def priority(self) -> int:
        return 1

    def is_available(self) -> bool:
        """检查适配器是否可用"""
        return self._check_cli()

    def validate_stock_code(self, stock_code: str) -> bool:
        """
        验证股票代码格式

        Args:
            stock_code: 股票代码

        Returns:
            bool: 是否有效

        Raises:
            InvalidStockCodeError: 股票代码格式无效时抛出
        """
        if not any(
            pattern.match(stock_code)
            for pattern in [
                self.HK_STOCK_PATTERN,
                self.US_STOCK_PATTERN,
                self.CN_STOCK_PATTERN,
            ]
        ):
            raise InvalidStockCodeError(
                stock_code=stock_code,
                expected_format="港股: 0700.HK, 美股: AAPL.US, A股: 600519.SH",
            )
        return True

    def _convert_period(self, period: str) -> str:
        """
        转换报告期格式

        Args:
            period: "annual" 或 "quarterly"

        Returns:
            Longbridge CLI 使用的格式: "af" (annual) 或 "qf" (quarterly)
        """
        mapping = {"annual": "af", "quarterly": "qf"}
        return mapping.get(period, "af")

    def _parse_timestamp(self, ts: Any) -> str:
        """解析 Unix 时间戳"""
        if ts is None:
            return ""
        try:
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            return str(ts)
        except Exception:
            return str(ts)

    def get_balance_sheet(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取资产负债表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 资产负债表
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)
        period_code = self._convert_period(period)

        try:
            data = self._run_command(
                [
                    "financial-report",
                    stock_code,
                    "--kind",
                    "BS",
                    "--report",
                    period_code,
                    "--format",
                    "json",
                ]
            )
            return self._parse_financial_report(data, "balance_sheet")
        except Exception as e:
            logger.warning(f"Failed to get balance sheet for {stock_code}: {e}")
            return pd.DataFrame()

    def get_income_statement(
        self, stock_code: str, period: str = "annual"
    ) -> pd.DataFrame:
        """
        获取利润表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 利润表
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)
        period_code = self._convert_period(period)

        try:
            data = self._run_command(
                [
                    "financial-report",
                    stock_code,
                    "--kind",
                    "IS",
                    "--report",
                    period_code,
                    "--format",
                    "json",
                ]
            )
            return self._parse_financial_report(data, "income_statement")
        except Exception as e:
            logger.warning(f"Failed to get income statement for {stock_code}: {e}")
            return pd.DataFrame()

    def get_cash_flow(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取现金流量表

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 现金流量表
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)
        period_code = self._convert_period(period)

        try:
            data = self._run_command(
                [
                    "financial-report",
                    stock_code,
                    "--kind",
                    "CF",
                    "--report",
                    period_code,
                    "--format",
                    "json",
                ]
            )
            return self._parse_financial_report(data, "cash_flow")
        except Exception as e:
            logger.warning(f"Failed to get cash flow for {stock_code}: {e}")
            return pd.DataFrame()

    def get_indicators(self, stock_code: str, period: str = "annual") -> pd.DataFrame:
        """
        获取财务指标

        Args:
            stock_code: 股票代码
            period: 报告期类型 ("annual" 或 "quarterly")

        Returns:
            pd.DataFrame: 财务指标
        """
        # Longbridge calc-index 不直接支持历史财务指标
        # 这里使用 calc-index 获取当前估值指标
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                [
                    "calc-index",
                    stock_code,
                    "--fields",
                    "pe,pb,dps_rate,turnover_rate,total_market_value",
                    "--format",
                    "json",
                ]
            )
            return self._parse_calc_indexes(data, stock_code)
        except Exception as e:
            logger.warning(f"Failed to get indicators for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_financial_report(
        self, data: Dict[str, Any], report_type: str
    ) -> pd.DataFrame:
        """
        解析财务报表数据

        Args:
            data: CLI 返回的 JSON 数据
            report_type: 报表类型 (balance_sheet, income_statement, cash_flow)

        Returns:
            pd.DataFrame: 解析后的 DataFrame
        """
        records = []
        report_key = {
            "balance_sheet": "BS",
            "income_statement": "IS",
            "cash_flow": "CF",
        }.get(report_type, report_type.upper())

        try:
            report_data = data.get("list", {}).get(report_key, {})
            indicators = report_data.get("indicators", [])

            for indicator in indicators:
                accounts = indicator.get("accounts", [])
                for account in accounts:
                    raw_field_name = account.get("name", "")
                    # 映射到标准字段名
                    field_name = self.FIELD_MAPPING.get(raw_field_name, raw_field_name)
                    values = account.get("values", [])
                    for value_entry in values:
                        record = {
                            "report_date": value_entry.get("period", ""),
                            "field_name": field_name,
                            "value": value_entry.get("value", ""),
                            "yoy": value_entry.get("yoy", ""),
                            "_raw_data_source": self.adapter_name,
                        }
                        records.append(record)

            if records:
                df = pd.DataFrame(records)
                # 转换为宽格式
                return self._pivot_to_wide(df)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _pivot_to_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将长格式数据透视为宽格式

        Args:
            df: 包含 field_name, value, report_date 的 DataFrame

        Returns:
            pd.DataFrame: 宽格式 DataFrame
        """
        if df.empty:
            return df

        # 按日期和字段名分组，取最后一个值
        df_sorted = df.sort_values(["report_date", "field_name"])
        df_pivot = df_sorted.pivot_table(
            index="report_date", columns="field_name", values="value", aggfunc="last"
        )
        df_pivot = df_pivot.reset_index()
        return df_pivot

    def _parse_calc_indexes(
        self, data: Dict[str, Any], stock_code: str
    ) -> pd.DataFrame:
        """
        解析 calc-index 数据

        Args:
            data: CLI 返回的 JSON 数据
            stock_code: 股票代码

        Returns:
            pd.DataFrame: 估值指标
        """
        records = []
        try:
            results = data if isinstance(data, list) else data.get("data", [data])
            for result in results:
                record = {
                    "report_date": datetime.now().strftime("%Y-%m-%d"),
                    "stock_code": stock_code,
                    "pe_ratio": result.get("pe"),
                    "pb_ratio": result.get("pb"),
                    "dividend_yield": result.get("dps_rate"),
                    "turnover_rate": result.get("turnover_rate"),
                    "market_cap": result.get("total_market_value"),
                    "symbol": result.get("symbol", stock_code),
                    "_raw_data_source": self.adapter_name,
                }
                records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_dividend(self, stock_code: str) -> pd.DataFrame:
        """
        获取分红历史

        Args:
            stock_code: 股票代码

        Returns:
            pd.DataFrame: 分红历史
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(["dividend", stock_code, "--format", "json"])
            return self._parse_dividend(data)
        except Exception as e:
            logger.warning(f"Failed to get dividend for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_dividend(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析分红数据"""
        records = []
        try:
            dividend_list = data.get("list", [])
            for item in dividend_list:
                record = {
                    "ex_date": item.get("ex_date", ""),
                    "payment_date": item.get("payment_date", ""),
                    "record_date": item.get("record_date", ""),
                    "description": item.get("desc", ""),
                    "_raw_data_source": self.adapter_name,
                }
                records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_institution_rating(self, stock_code: str) -> pd.DataFrame:
        """
        获取机构评级

        Args:
            stock_code: 股票代码

        Returns:
            pd.DataFrame: 机构评级
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                ["institution-rating", stock_code, "--format", "json"]
            )
            return self._parse_institution_rating(data)
        except Exception as e:
            logger.warning(f"Failed to get institution rating for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_institution_rating(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析机构评级数据"""
        records = []
        try:
            analyst = data.get("analyst", {})
            instratings = data.get("instratings", {})

            record = {
                "recommend": instratings.get("recommend", ""),
                "target_price": instratings.get("target", ""),
                "target_change": instratings.get("change", ""),
                "strong_buy": instratings.get("evaluate", {}).get("strong_buy", 0),
                "buy": instratings.get("evaluate", {}).get("buy", 0),
                "hold": instratings.get("evaluate", {}).get("hold", 0),
                "sell": instratings.get("evaluate", {}).get("sell", 0),
                "industry": analyst.get("industry_name", ""),
                "industry_rank": analyst.get("industry_rank", ""),
                "industry_total": analyst.get("industry_total", ""),
                "_raw_data_source": self.adapter_name,
            }
            records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_valuation(self, stock_code: str) -> pd.DataFrame:
        """
        获取估值数据

        Args:
            stock_code: 股票代码

        Returns:
            pd.DataFrame: 估值数据
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(["valuation", stock_code, "--format", "json"])
            return self._parse_valuation(data)
        except Exception as e:
            logger.warning(f"Failed to get valuation for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_valuation(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析估值数据"""
        records = []
        try:
            history = data.get("history", {})
            metrics = history.get("metrics", {})

            for metric_name, metric_data in metrics.items():
                for item in metric_data.get("list", []):
                    record = {
                        "metric": metric_name,
                        "date": self._parse_timestamp(item.get("timestamp")),
                        "value": item.get("value", ""),
                        "high": metric_data.get("high", ""),
                        "low": metric_data.get("low", ""),
                        "median": metric_data.get("median", ""),
                        "_raw_data_source": self.adapter_name,
                    }
                    records.append(record)

            if records:
                df = pd.DataFrame(records)
                # 转换为宽格式
                df_pivot = df.pivot_table(
                    index="date", columns="metric", values="value", aggfunc="last"
                )
                return df_pivot.reset_index()
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_fund_holder(self, stock_code: str, count: int = 20) -> pd.DataFrame:
        """
        获取基金持股

        Args:
            stock_code: 股票代码
            count: 返回数量

        Returns:
            pd.DataFrame: 基金持股
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                ["fund-holder", stock_code, "--count", str(count), "--format", "json"]
            )
            return self._parse_fund_holder(data)
        except Exception as e:
            logger.warning(f"Failed to get fund holder for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_fund_holder(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析基金持股数据"""
        records = []
        try:
            lists = data.get("lists", [])
            for item in lists:
                record = {
                    "fund_code": item.get("code", ""),
                    "fund_name": item.get("name", ""),
                    "position_ratio": item.get("position_ratio", ""),
                    "report_date": item.get("report_date", ""),
                    "currency": item.get("currency", ""),
                    "_raw_data_source": self.adapter_name,
                }
                records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_shareholder(self, stock_code: str, range_: str = "all") -> pd.DataFrame:
        """
        获取股东信息

        Args:
            stock_code: 股票代码
            range_: 范围 (all, inc, dec)

        Returns:
            pd.DataFrame: 股东信息
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                ["shareholder", stock_code, "--range", range_, "--format", "json"]
            )
            return self._parse_shareholder(data)
        except Exception as e:
            logger.warning(f"Failed to get shareholder for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_shareholder(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析股东数据"""
        records = []
        try:
            shareholder_list = data.get("shareholder_list", [])
            for item in shareholder_list:
                record = {
                    "shareholder_name": item.get("shareholder_name", ""),
                    "percent_of_shares": item.get("percent_of_shares", ""),
                    "shares_changed": item.get("shares_changed", ""),
                    "report_date": item.get("report_date", ""),
                    "_raw_data_source": self.adapter_name,
                }
                records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        获取实时行情

        Args:
            stock_code: 股票代码

        Returns:
            Dict: 实时行情数据
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(["quote", stock_code, "--format", "json"])
            return data[0] if data else {}
        except Exception as e:
            logger.warning(f"Failed to get quote for {stock_code}: {e}")
            return {}

    def get_calc_indexes(
        self, stock_code: str, fields: str = "pe,pb,dps_rate"
    ) -> pd.DataFrame:
        """
        获取计算指标

        Args:
            stock_code: 股票代码
            fields: 指标字段，逗号分隔

        Returns:
            pd.DataFrame: 计算指标
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                ["calc-index", stock_code, "--fields", fields, "--format", "json"]
            )
            return self._parse_calc_indexes(data, stock_code)
        except Exception as e:
            logger.warning(f"Failed to get calc indexes for {stock_code}: {e}")
            return pd.DataFrame()

    def get_capital_flow(self, stock_code: str) -> pd.DataFrame:
        """
        获取资金流向

        Args:
            stock_code: 股票代码

        Returns:
            pd.DataFrame: 资金流向数据
        """
        self.validate_stock_code(stock_code)
        stock_code = self._normalize_stock_code(stock_code)

        try:
            data = self._run_command(
                ["capital", stock_code, "--flow", "--format", "json"]
            )
            return self._parse_capital_flow(data)
        except Exception as e:
            logger.warning(f"Failed to get capital flow for {stock_code}: {e}")
            return pd.DataFrame()

    def _parse_capital_flow(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析资金流向数据"""
        records = []
        try:
            if isinstance(data, list):
                for item in data:
                    record = {
                        "timestamp": item.get("timestamp", ""),
                        "inflow": item.get("inflow", ""),
                        "_raw_data_source": self.adapter_name,
                    }
                    records.append(record)
            elif isinstance(data, dict):
                # 解析 capital flow time series
                flow_data = data.get("list", data.get("data", []))
                for item in flow_data:
                    record = {
                        "timestamp": item.get("timestamp", ""),
                        "inflow": item.get("inflow", ""),
                        "_raw_data_source": self.adapter_name,
                    }
                    records.append(record)

            if records:
                return pd.DataFrame(records)
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康状态信息
        """
        is_available = self._check_cli()
        status = "healthy" if is_available else "unavailable"

        return {
            "status": status,
            "adapter": self.adapter_name,
            "supported_markets": self.supported_markets,
            "priority": self.priority,
            "cli_path": self._cli_path,
            "cli_found": shutil.which(self._cli_path) is not None,
        }
