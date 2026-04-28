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
    US_STOCK_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?\.US$|^[A-Z]{1,5}(\.[A-Z])?$")
    CN_STOCK_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")

    # LongBridge 字段名到标准字段名的映射
    # 用于统一不同数据源的字段名
    FIELD_MAPPING = {
        # === 利润表字段 ===
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
        "利润总额(HKD)": "profit_before_tax",
        "利润总额(USD)": "profit_before_tax",
        "利润总额(CNY)": "profit_before_tax",
        "毛利率": "gross_margin",
        "净利率": "net_margin",
        "ROE": "roe",
        "ROA": "roa",
        "每股收益(HKD)": "eps",
        "每股收益(USD)": "eps",
        "每股收益(CNY)": "eps",
        "营业利润/经营现金流": "operating_profit_to_operating_cash_flow",
        "利息费用(HKD)": "interest_expense",
        "利息费用(USD)": "interest_expense",
        "利息费用(CNY)": "interest_expense",
        "税费(HKD)": "tax_expense",
        "税费(USD)": "tax_expense",
        "税费(CNY)": "tax_expense",
        "折旧与摊销(HKD)": "depreciation_amortization",
        "折旧与摊销(USD)": "depreciation_amortization",
        "折旧与摊销(CNY)": "depreciation_amortization",
        # === 资产负债表字段 ===
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
        "流动资产(USD)": "current_assets",
        "流动资产(CNY)": "current_assets",
        "流动负债(HKD)": "current_liabilities",
        "流动负债(USD)": "current_liabilities",
        "流动负债(CNY)": "current_liabilities",
        "非流动资产(HKD)": "non_current_assets",
        "非流动资产(USD)": "non_current_assets",
        "非流动资产(CNY)": "non_current_assets",
        "非流动负债(HKD)": "non_current_liabilities",
        "非流动负债(USD)": "non_current_liabilities",
        "非流动负债(CNY)": "non_current_liabilities",
        "现金及等价物(HKD)": "cash_and_equivalents",
        "现金及等价物(USD)": "cash_and_equivalents",
        "现金及等价物(CNY)": "cash_and_equivalents",
        "短期投资(HKD)": "short_term_investments",
        "短期投资(USD)": "short_term_investments",
        "短期投资(CNY)": "short_term_investments",
        "应收账款(HKD)": "accounts_receivable",
        "应收账款(USD)": "accounts_receivable",
        "应收账款(CNY)": "accounts_receivable",
        "应付账款(HKD)": "accounts_payable",
        "应付账款(USD)": "accounts_payable",
        "应付账款(CNY)": "accounts_payable",
        "存货(HKD)": "inventory",
        "存货(USD)": "inventory",
        "存货(CNY)": "inventory",
        "固定资产净值(HKD)": "fixed_assets",
        "固定资产净值(USD)": "fixed_assets",
        "固定资产净值(CNY)": "fixed_assets",
        "无形资产(HKD)": "intangible_assets",
        "无形资产(USD)": "intangible_assets",
        "无形资产(CNY)": "intangible_assets",
        "商誉(HKD)": "goodwill",
        "商誉(USD)": "goodwill",
        "商誉(CNY)": "goodwill",
        "长期投资(HKD)": "long_term_equity_investments",
        "长期投资(USD)": "long_term_equity_investments",
        "长期投资(CNY)": "long_term_equity_investments",
        "净债务(HKD)": "net_debt",
        "净债务(USD)": "net_debt",
        "净债务(CNY)": "net_debt",
        "短期债务(HKD)": "short_term_debt",
        "短期债务(USD)": "short_term_debt",
        "短期债务(CNY)": "short_term_debt",
        "长期债务(HKD)": "long_term_debt",
        "长期债务(USD)": "long_term_debt",
        "长期债务(CNY)": "long_term_debt",
        "每股净资产(HKD)": "bvps",
        "每股净资产(USD)": "bvps",
        "每股净资产(CNY)": "bvps",
        "股本(HKD)": "share_capital",
        "股本(USD)": "share_capital",
        "股本(CNY)": "share_capital",
        "留存收益(HKD)": "retained_earnings",
        "留存收益(USD)": "retained_earnings",
        "留存收益(CNY)": "retained_earnings",
        "资本支出(HKD)": "capex",
        "资本支出(USD)": "capex",
        "资本支出(CNY)": "capex",
        # === 现金流量表字段 ===
        "经营现金流(HKD)": "operating_cash_flow",
        "投资现金流(HKD)": "investing_cash_flow",
        "融资现金流(HKD)": "financing_cash_flow",
        "经营现金流(USD)": "operating_cash_flow",
        "投资现金流(USD)": "investing_cash_flow",
        "融资现金流(USD)": "financing_cash_flow",
        "经营现金流(CNY)": "operating_cash_flow",
        "投资现金流(CNY)": "investing_cash_flow",
        "融资现金流(CNY)": "financing_cash_flow",
    }

    # "及占比"后缀字段映射: 原始名 → 标准绝对值字段名
    # 这些字段在 LongBridge 中格式为 "XXX(HKD)及占比"，拆分为绝对值和占比
    RATIO_SUFFIX_FIELDS = {
        "固定资产净值": "fixed_assets",
        "存货": "inventory",
        "应收": "accounts_receivable",
        "现金及短期投资": "cash_and_equivalents",
        "长期投资": "long_term_equity_investments",
        "净债务": "net_debt",
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

    def _map_field_name(self, raw_name: str) -> str:
        """
        将 LongBridge 原始字段名映射为标准字段名

        处理策略:
        1. 精确匹配 FIELD_MAPPING
        2. "及占比"后缀字段: 拆分为绝对值和占比两个字段
        3. 尝试去掉货币后缀再匹配

        Args:
            raw_name: LongBridge 返回的原始字段名

        Returns:
            标准字段名
        """
        # 1. 精确匹配
        if raw_name in self.FIELD_MAPPING:
            return self.FIELD_MAPPING[raw_name]

        # 2. 处理 "及占比" 后缀: "固定资产净值(HKD)及占比" → "fixed_assets"
        if raw_name.endswith("及占比"):
            base = raw_name[:-3]  # 去掉 "及占比"
            # 去掉货币后缀
            for suffix in ("(HKD)", "(USD)", "(CNY)"):
                clean = base.replace(suffix, "")
                if clean in self.RATIO_SUFFIX_FIELDS:
                    return self.RATIO_SUFFIX_FIELDS[clean]
            # 回退: 尝试直接映射 base
            if base in self.FIELD_MAPPING:
                return self.FIELD_MAPPING[base]

        # 3. 去掉货币后缀再匹配
        for suffix in ("(HKD)", "(USD)", "(CNY)"):
            stripped = raw_name.replace(suffix, "")
            if stripped in self.FIELD_MAPPING:
                return self.FIELD_MAPPING[stripped]

        # 4. 未映射，保留原名
        return raw_name

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
            df = self._parse_financial_report(data, "balance_sheet")
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="balance_sheet",
                    reason="Longbridge CLI返回空数据",
                    adapter_name=self.adapter_name,
                )
            df = self._fill_balance_derived(df)
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="balance_sheet",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

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
            df = self._parse_financial_report(data, "income_statement")
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="income_statement",
                    reason="Longbridge CLI返回空数据",
                    adapter_name=self.adapter_name,
                )
            df = self._fill_income_derived(df)
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="income_statement",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

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
            df = self._parse_financial_report(data, "cash_flow")
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="cash_flow",
                    reason="Longbridge CLI返回空数据",
                    adapter_name=self.adapter_name,
                )
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="cash_flow",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

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
            df = self._parse_calc_indexes(data, stock_code)
            if df.empty:
                raise DataNotAvailableError(
                    stock_code=stock_code,
                    report_type="indicators",
                    reason="Longbridge CLI返回空数据",
                    adapter_name=self.adapter_name,
                )
            return df
        except DataNotAvailableError:
            raise
        except Exception as e:
            raise DataNotAvailableError(
                stock_code=stock_code,
                report_type="indicators",
                reason=str(e),
                adapter_name=self.adapter_name,
            )

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
                    field_name = self._map_field_name(raw_field_name)
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

        # 数值类型转换: 将字符串值转为 float
        for col in df_pivot.columns:
            if col in ("report_date", "_raw_data_source"):
                continue
            df_pivot[col] = pd.to_numeric(df_pivot[col], errors="coerce")

        return df_pivot

    def _fill_balance_derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        资产负债表数据自愈: 从已有字段推算缺失的标准字段

        推算规则:
        - total_equity = total_assets - total_liabilities (缺失时)
        - bvps = total_equity / share_capital (缺失时)
        - debt_to_equity = total_liabilities / total_equity (缺失时)

        Args:
            df: 宽格式 DataFrame

        Returns:
            补全后的 DataFrame
        """
        if df.empty:
            return df

        derived_fields = []

        # 推算 total_equity
        if "total_equity" not in df.columns or df["total_equity"].isna().all():
            if "total_assets" in df.columns and "total_liabilities" in df.columns:
                df["total_equity"] = df["total_assets"] - df["total_liabilities"]
                derived_fields.append("total_equity = total_assets - total_liabilities")

        # 推算 bvps = total_equity / share_capital
        if "bvps" not in df.columns or df["bvps"].isna().all():
            if (
                "total_equity" in df.columns
                and "share_capital" in df.columns
            ):
                mask = df["share_capital"].notna() & (df["share_capital"] != 0)
                df.loc[mask, "bvps"] = df.loc[mask, "total_equity"] / df.loc[mask, "share_capital"]
                derived_fields.append("bvps = total_equity / share_capital")

        # 推算 debt_to_equity = total_liabilities / total_equity
        if "debt_to_equity" not in df.columns or df["debt_to_equity"].isna().all():
            if "total_liabilities" in df.columns and "total_equity" in df.columns:
                mask = df["total_equity"].notna() & (df["total_equity"] != 0)
                df.loc[mask, "debt_to_equity"] = df.loc[mask, "total_liabilities"] / df.loc[mask, "total_equity"]
                derived_fields.append("debt_to_equity = total_liabilities / total_equity")

        # 记录推算信息
        if derived_fields:
            df["_derived_fields"] = "; ".join(derived_fields)
            for field in derived_fields:
                logger.info(f"Data self-healing: derived {field}")

        return df

    def _fill_income_derived(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        利润表数据自愈: 从已有字段推算缺失的标准字段

        推算规则:
        - gross_profit = revenue * gross_margin / 100 (缺失时)
        - total_cost = revenue - gross_profit (缺失时)

        Args:
            df: 宽格式 DataFrame

        Returns:
            补全后的 DataFrame
        """
        if df.empty:
            return df

        derived_fields = []

        # 推算 gross_profit
        if "gross_profit" not in df.columns or df["gross_profit"].isna().all():
            if "revenue" in df.columns and "gross_margin" in df.columns:
                df["gross_profit"] = df["revenue"] * df["gross_margin"] / 100
                derived_fields.append("gross_profit = revenue * gross_margin / 100")

        # 推算 total_cost = revenue - gross_profit
        if "total_cost" not in df.columns or df["total_cost"].isna().all():
            if "revenue" in df.columns and "gross_profit" in df.columns:
                df["total_cost"] = df["revenue"] - df["gross_profit"]
                derived_fields.append("total_cost = revenue - gross_profit")

        # 记录推算信息
        if derived_fields:
            df["_derived_fields"] = "; ".join(derived_fields)
            for field in derived_fields:
                logger.info(f"Data self-healing: derived {field}")

        return df

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
