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

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent))

from financial_sdk import FinancialFacade


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
                print(f"\n=== {report_name} ({len(df)} 行) ===")
                if args.format == "table":
                    print(df.to_string(index=False))
                else:
                    # JSON 友好格式
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
