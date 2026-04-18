#!/usr/bin/env python3
"""
Financial SDK CLI

Usage:
    financial-sdk get 9992.HK income_statement annual
    financial-sdk get 9992.HK all annual --force-refresh
    financial-sdk health
    financial-sdk stocks --market HK
    financial-sdk cache
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent))

from financial_sdk import FinancialFacade


def _format_dataframe_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """
    格式化 DataFrame 用于展示：
    1. 移除内部字段（以 _ 开头）
    2. 格式化日期列
    3. 格式化数字列（太大或太小的数字用科学计数，其他保留合理小数位）
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # 移除内部字段
    cols_to_drop = [c for c in df.columns if c.startswith("_")]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # 格式化日期列
    if "report_date" in df.columns:
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.strftime("%Y-%m-%d")

    # 格式化数字列
    for col in df.columns:
        if col in ["report_date", "stock_code"]:
            continue
        if df[col].dtype in ["float64", "float32"]:
            # 格式化大数字和科学计数
            df[col] = df[col].apply(lambda x: _format_number(x) if pd.notna(x) else "-")

    return df


def _format_number(x: float) -> str:
    """格式化数字，太大用 B/M/K 后缀，太小用科学计数"""
    if pd.isna(x):
        return "-"
    if abs(x) >= 1e9:
        return f"{x / 1e9:.2f}B"
    elif abs(x) >= 1e6:
        return f"{x / 1e6:.2f}M"
    elif abs(x) >= 1e3:
        return f"{x / 1e3:.2f}K"
    elif abs(x) < 0.01 and x != 0:
        return f"{x:.2e}"
    else:
        return f"{x:.2f}"


def _filter_by_year(df: pd.DataFrame, year_spec: str) -> pd.DataFrame:
    """
    按年份筛选数据

    Args:
        df: DataFrame，需包含 report_date 列
        year_spec: 年份规格，支持:
            - "2024" (单个年份)
            - "2023,2024" (多个年份)
            - "2020-2024" (年份范围)

    Returns:
        筛选后的 DataFrame
    """
    if df is None or df.empty:
        return df

    if "report_date" not in df.columns:
        return df

    # 转换日期列
    df = df.copy()
    df["_year_col"] = pd.to_datetime(df["report_date"]).dt.year

    # 解析年份规格
    years = set()
    for part in year_spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(part))

    # 筛选
    df = df[df["_year_col"].isin(years)]
    df = df.drop(columns=["_year_col"])

    return df


def cmd_get(args):
    """获取财务数据"""
    facade = FinancialFacade()

    try:
        bundle = facade.get_financial_data(
            stock_code=args.stock_code,
            report_type=args.report_type,
            period=args.period,
            force_refresh=args.force_refresh,
        )

        # 输出基本信息
        print(f"股票代码: {bundle.stock_code}")
        print(f"市场: {bundle.market}")
        print(f"货币: {bundle.currency}")
        print(f"可用报表: {bundle.get_available_reports()}")
        print(f"数据年份: {bundle.report_periods}")

        if bundle.is_partial:
            print(f"\n警告 (部分数据):")
            for w in bundle.warnings:
                print(f"  - {w}")

        # 输出各报表
        for report_name in ["balance_sheet", "income_statement", "cash_flow", "indicators"]:
            df = getattr(bundle, report_name, None)
            if df is not None and not df.empty:
                # 按年份筛选
                if args.year:
                    df = _filter_by_year(df, args.year)

                if df.empty:
                    continue

                print(f"\n=== {report_name} ({len(df)} 行) ===")
                if args.format == "table":
                    # 格式化数据用于展示
                    display_df = _format_dataframe_for_display(df)
                    print(display_df.to_string(index=False))
                else:
                    # JSON 友好格式（原始数据）
                    records = df.to_dict(orient="records")
                    print(json.dumps(records, ensure_ascii=False, indent=2, default=str))

        return 0
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


def cmd_health(args):
    """健康检查"""
    facade = FinancialFacade()
    health = facade.health_check()
    print(json.dumps(health.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_stocks(args):
    """获取支持的股票列表"""
    facade = FinancialFacade()
    stocks = facade.get_supported_stocks(market=args.market)
    print(f"市场: {args.market}")
    print(f"支持 {len(stocks)} 只股票:")
    for s in stocks:
        print(f"  {s}")
    return 0


def cmd_cache(args):
    """缓存统计"""
    facade = FinancialFacade()
    stats = facade.get_cache_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Financial SDK CLI - 财务数据获取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  financial-sdk get 9992.HK income_statement annual
  financial-sdk get 9992.HK income_statement annual --year 2024
  financial-sdk get 9992.HK income_statement annual --year 2023,2024
  financial-sdk get 9992.HK income_statement annual -y 2020-2024
  financial-sdk get 0700.HK all quarterly --force-refresh
  financial-sdk get AAPL balance_sheet annual --format json
  financial-sdk health
  financial-sdk stocks --market HK
  financial-sdk cache
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # get 命令
    get_parser = subparsers.add_parser("get", help="获取股票财务数据")
    get_parser.add_argument("stock_code", help="股票代码 (如 9992.HK, AAPL, 600000.SH)")
    get_parser.add_argument("report_type", nargs="?", default="all",
                           choices=["balance_sheet", "income_statement", "cash_flow", "indicators", "all"],
                           help="报表类型 (默认: all)")
    get_parser.add_argument("period", nargs="?", default="annual",
                           choices=["annual", "quarterly"],
                           help="报告期类型 (默认: annual)")
    get_parser.add_argument("--force-refresh", action="store_true",
                           help="强制刷新缓存")
    get_parser.add_argument("--year", "-y",
                           help="指定年份筛选，支持: 2024 或 2023,2024 或 2020-2024")
    get_parser.add_argument("--format", default="table",
                           choices=["table", "json"],
                           help="输出格式 (默认: table)")

    # health 命令
    subparsers.add_parser("health", help="健康检查")

    # stocks 命令
    stocks_parser = subparsers.add_parser("stocks", help="获取支持的股票列表")
    stocks_parser.add_argument("--market", default="all",
                              choices=["A", "HK", "US", "all"],
                              help="市场筛选 (默认: all)")

    # cache 命令
    subparsers.add_parser("cache", help="缓存统计")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "get":
        return cmd_get(args)
    elif args.command == "health":
        return cmd_health(args)
    elif args.command == "stocks":
        return cmd_stocks(args)
    elif args.command == "cache":
        return cmd_cache(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
