#!/usr/bin/env python3
"""
Financial SDK CLI

Usage:
    financial-sdk get 9992.HK income_statement annual
    financial-sdk get 9992.HK all annual --force-refresh
    financial-sdk analyze 600000.SH
    financial-sdk health
    financial-sdk stocks --market HK
    financial-sdk cache
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

import pandas as pd

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent))

from financial_sdk import FinancialFacade
from financial_sdk.analytics import FinancialAnalytics
from financial_sdk.cache import clear_cache_stock

# 标准化的核心指标列表（跨市场统一）
STANDARD_FIELDS = {
    # 现金流
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "net_cash_flow",
    "beginning_cash",
    "ending_cash",
    "total_operating_inflow",
    "total_operating_outflow",
    "total_investing_inflow",
    "total_investing_outflow",
    "total_financing_inflow",
    "total_financing_outflow",
    "capex",
    "dividends_paid",
    "debt_repayment",
    "staff_cash_paid",
    "taxes_paid",
    "tax_refund_received",
    "depreciation_amortization",
    "profit_before_tax",
    # 资产负债表
    "total_assets",
    "total_liabilities",
    "total_equity",
    "current_assets",
    "non_current_assets",
    "current_liabilities",
    "non_current_liabilities",
    "fixed_assets",
    "intangible_assets",
    "goodwill",
    "accounts_receivable",
    "inventory",
    "accounts_payable",
    "short_term_debt",
    "long_term_debt",
    "cash_and_equivalents",
    # 利润表
    "revenue",
    "total_cost",
    "gross_profit",
    "operating_profit",
    "net_profit",
    "selling_expense",
    "admin_expense",
    "financial_expense",
    "rd_expense",
    "tax_expense",
    "eps",
    "diluted_eps",
    # 指标
    "roe",
    "roa",
    "gross_margin",
    "net_margin",
    "current_ratio",
    "quick_ratio",
    "debt_to_assets",
    "debt_to_equity",
    "bvps",
    "pe_ratio",
    "pb_ratio",
    # 其他
    "report_date",
    "stock_code",
}


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


def _transpose_for_display(
    df: pd.DataFrame, standard_only: bool = False
) -> pd.DataFrame:
    """
    转置 DataFrame 用于展示：
    - 每行一个指标（字段名）
    - 每列一个报告期（日期）
    - 日期从新到旧排序（最新在左）
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # 移除内部字段
    cols_to_drop = [c for c in df.columns if c.startswith("_")]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    if "report_date" not in df.columns:
        return df

    # 按日期排序（最新在前）
    df["_sort_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("_sort_date", ascending=False)
    df = df.drop(columns=["_sort_date"])

    # 转置：日期变列名，字段名变行
    df = df.set_index("report_date").T

    # 重命名日期列（去掉时间部分）
    df.columns = [pd.to_datetime(c).strftime("%Y-%m-%d") for c in df.columns]

    # 移除 stock_code 行
    if "stock_code" in df.index:
        df = df.drop(index=["stock_code"])

    # 过滤掉非关键字段（元数据列、YOY同比列等）
    rows_to_drop = []
    for idx in df.index:
        # 跳过元数据行
        if idx in [
            "SECUCODE",
            "SECURITY_NAME_ABBR",
            "ORG_CODE",
            "ORG_TYPE",
            "REPORT_TYPE",
            "REPORT_DATE_NAME",
            "SECURITY_TYPE_CODE",
            "NOTICE_DATE",
            "UPDATE_DATE",
            "CURRENCY",
        ]:
            rows_to_drop.append(idx)
            continue
        # 跳过 YOY 同比列
        if idx.endswith("_YOY") or "_YOY" in str(idx):
            rows_to_drop.append(idx)
            continue
        # 如果启用标准字段过滤，只保留标准化指标
        if standard_only and idx not in STANDARD_FIELDS:
            rows_to_drop.append(idx)
            continue
        # 跳过全为 NaN/- 的行
        # 注意：df.loc[idx] 可能因为重复索引返回 DataFrame，需处理
        try:
            row = df.loc[idx]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            if row.isna().all() or (row == "-").all():
                rows_to_drop.append(idx)
        except Exception:
            # 如果取值失败，跳过该行
            rows_to_drop.append(idx)

    df = df.drop(index=rows_to_drop, errors="ignore")

    # 格式化数字列
    for col in df.columns:
        df[col] = df[col].apply(
            lambda x: _format_number(x)
            if pd.notna(x) and isinstance(x, (int, float))
            else x
        )

    return df


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
            print("\n警告 (部分数据):")
            for w in bundle.warnings:
                print(f"  - {w}")

        # 输出各报表
        for report_name in [
            "balance_sheet",
            "income_statement",
            "cash_flow",
            "indicators",
        ]:
            df = getattr(bundle, report_name, None)
            if df is not None and not df.empty:
                # 按年份筛选
                if args.year:
                    df = _filter_by_year(df, args.year)

                if df.empty:
                    continue

                print(f"\n=== {report_name} ({len(df)} 行) ===")
                if args.format == "table":
                    # 转置格式：指标为行，日期为列（最新在左）
                    display_df = _transpose_for_display(
                        df, standard_only=args.standard_only
                    )
                    print(display_df.to_string())
                elif args.format == "wide":
                    # 宽表格式：原始横向展示
                    display_df = _format_dataframe_for_display(df)
                    print(display_df.to_string(index=False))
                else:
                    # JSON 友好格式（原始数据）
                    records = df.to_dict(orient="records")
                    print(
                        json.dumps(records, ensure_ascii=False, indent=2, default=str)
                    )

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
    """缓存管理"""
    if args.clear:
        from financial_sdk.cache import clear_cache
        clear_cache()
        print("所有缓存已清除")
        return 0

    if args.stock:
        deleted = clear_cache_stock(args.stock)
        print(f"已清除 {args.stock} 的 {deleted} 条缓存")
        return 0

    facade = FinancialFacade()
    stats = facade.get_cache_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _format_analysis_table(report, years_filter=None):
    """
    格式化分析报告为表格形式 (指标为行，日期为列)

    Args:
        report: FullAnalysisReport 对象
        years_filter: 年份列表过滤

    Returns:
        格式化的字符串
    """
    lines = []
    width = 80

    # 收集所有日期
    dates = []
    if report.valuation and report.valuation.report_date:
        dates.append(report.valuation.report_date)
    if report.profitability and report.profitability.report_date:
        if report.profitability.report_date not in dates:
            dates.append(report.profitability.report_date)
    if report.efficiency and report.efficiency.report_date:
        if report.efficiency.report_date not in dates:
            dates.append(report.efficiency.report_date)
    if report.growth and report.growth.report_date:
        if report.growth.report_date not in dates:
            dates.append(report.growth.report_date)
    if report.safety and report.safety.report_date:
        if report.safety.report_date not in dates:
            dates.append(report.safety.report_date)

    # 按日期排序（最新在前）
    dates = sorted(set(dates), reverse=True)

    # 过滤年份
    if years_filter:
        filtered_dates = []
        for d in dates:
            try:
                # 支持多种日期格式: FY 2025, 2025, 2025-12-31
                date_str = str(d)
                if date_str.startswith("FY "):
                    year = int(date_str[3:].strip())
                else:
                    year = int(date_str[:4])
                if year in years_filter:
                    filtered_dates.append(d)
            except (ValueError, IndexError):
                pass
        dates = filtered_dates

    if not dates:
        return "无可用数据"

    # 表头
    header = f"{'指标':<25}" + "".join([f"{d:>15}" for d in dates])
    lines.append("=" * width)
    lines.append(f"  Financial Analysis: {report.stock_code} (多期对比)")
    lines.append(f"  综合评分: {report.get_score():.1f}/100")
    lines.append("=" * width)
    lines.append(header)
    lines.append("-" * width)

    # Valuation 指标
    if report.valuation:
        lines.append("\n【估值指标 Valuation】")
        v = report.valuation
        metrics_map = [
            ("市盈率 (P/E)", v.pe_ratio, True),
            ("市净率 (P/B)", v.pb_ratio, True),
            ("市销率 (P/S)", v.ps_ratio, True),
            ("总市值", v.market_cap, False),
            ("股息率", v.dividend_yield, True),
            ("EPS", v.eps, False),
        ]
        for name, value, is_percent in metrics_map:
            if value is not None:
                if is_percent and abs(value) < 10:
                    val_str = f"{value * 100:.2f}%" if value else "-"
                else:
                    val_str = _format_number(value) if value else "-"
                lines.append(
                    f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates])
                )

    # Profitability 指标
    if report.profitability:
        lines.append("\n【盈利能力 Profitability】")
        p = report.profitability
        metrics_map = [
            ("ROE", p.roe, True),
            ("ROA", p.roa, True),
            ("ROIC", p.roic, True),
            ("毛利率", p.gross_margin, True),
            ("净利率", p.net_margin, True),
        ]
        for name, value, is_percent in metrics_map:
            if value is not None:
                val_str = (
                    f"{value * 100:.2f}%"
                    if is_percent
                    else (f"{value:.4f}" if value else "-")
                )
                lines.append(
                    f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates])
                )

    # Efficiency 指标
    if report.efficiency:
        lines.append("\n【运营效率 Efficiency】")
        e = report.efficiency
        metrics_map = [
            ("现金周转周期", e.cash_conversion_cycle, False),
            ("营业周期", e.operating_cycle, False),
            ("存货周转天数", e.dio, False),
            ("应收账款周转天数", e.dso, False),
            ("应付账款周转天数", e.dpo, False),
        ]
        for name, value, is_percent in metrics_map:
            if value is not None:
                val_str = f"{value:.1f}" if value else "-"
                lines.append(
                    f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates])
                )

    # Growth 指标
    if report.growth:
        lines.append("\n【成长性 Growth】")
        g = report.growth
        metrics_map = [
            ("营收增长率", g.revenue_growth_yoy, True),
            ("净利润增长率", g.profit_growth_yoy, True),
            ("可持续增长率", g.sustainable_growth_rate, True),
        ]
        for name, value, is_percent in metrics_map:
            if value is not None:
                val_str = (
                    f"{value * 100:.2f}%"
                    if is_percent
                    else (f"{value:.4f}" if value else "-")
                )
                lines.append(
                    f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates])
                )

    # Safety 指标
    if report.safety:
        lines.append("\n【财务安全 Safety】")
        s = report.safety
        metrics_map = [
            ("Altman Z-Score", s.altman_z_score, False),
            ("流动比率", s.current_ratio, False),
            ("速动比率", s.quick_ratio, False),
            ("利息保障倍数", s.interest_coverage, False),
            ("资产负债率", s.debt_to_equity, False),
        ]
        for name, value, is_percent in metrics_map:
            if value is not None:
                val_str = f"{value:.2f}" if value else "-"
                lines.append(
                    f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates])
                )

    lines.append("\n" + "=" * width)
    return "\n".join(lines)


def _format_multi_year_metrics(multi_year_data, years_filter=None):
    """
    格式化多年财务指标为表格形式 (指标为行，日期为列)

    Args:
        multi_year_data: get_multi_year_metrics 返回的数据
        years_filter: 年份列表过滤

    Returns:
        格式化的字符串
    """
    lines = []
    width = 100

    dates = multi_year_data.get("report_dates", [])

    # 过滤年份
    if years_filter:
        filtered_dates = []
        for d in dates:
            try:
                # 支持多种日期格式: FY 2025, 2025, 2025-12-31
                date_str = str(d)
                if date_str.startswith("FY "):
                    year = int(date_str[3:].strip())
                else:
                    year = int(date_str[:4])
                if year in years_filter:
                    filtered_dates.append(d)
            except (ValueError, IndexError):
                pass
        dates = filtered_dates

    if not dates:
        return "无可用数据"

    stock_code = multi_year_data.get("stock_code", "N/A")

    # 表头
    lines.append("=" * width)
    lines.append(f"  Financial Analysis: {stock_code} (多年对比)")
    lines.append("=" * width)
    header = f"{'指标':<28}" + "".join([f"{str(d):>16}" for d in dates])
    lines.append(header)
    lines.append("-" * width)

    # Valuation 指标（最新一期）
    valuation = multi_year_data.get("valuation")
    if valuation:
        lines.append("\n【估值指标 Valuation】(最新一期)")
        v = valuation
        metrics_map = [
            ("市盈率 (P/E)", v.pe_ratio, "ratio"),
            ("市净率 (P/B)", v.pb_ratio, "ratio"),
            ("市销率 (P/S)", v.ps_ratio, "ratio"),
            ("总市值 (亿)", v.market_cap, "market_cap"),
            ("股息率", v.dividend_yield, "percent"),
            ("EPS (元)", v.eps, "number"),
        ]
        for name, value, fmt in metrics_map:
            if value is not None:
                if fmt == "percent":
                    val_str = f"{value * 100:.2f}%"
                elif fmt == "market_cap":
                    val_str = f"{value / 1e8:.2f}" if value else "-"
                elif fmt == "ratio":
                    # PE/PB/PS 是比率，不是百分比
                    val_str = f"{value:.2f}" if value else "-"
                else:
                    val_str = f"{value:.4f}" if value else "-"
                # 估值只有最新一期数据，显示在第一列
                date_cols = [val_str if i == 0 else "-" for i in range(len(dates))]
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in date_cols]))
    else:
        lines.append("\n【估值指标 Valuation】")
        lines.append("  估值数据不可用（请检查股票代码或网络连接）")

    # Profitability 指标（多年）
    profitability = multi_year_data.get("profitability", {})
    if profitability:
        lines.append("\n【盈利能力 Profitability】")
        metrics_rows = {
            "ROE": [],
            "ROA": [],
            "ROIC": [],
            "毛利率": [],
            "净利率": [],
        }
        for date in dates:
            p = profitability.get(date)
            if p:
                metrics_rows["ROE"].append(p.roe)
                metrics_rows["ROA"].append(p.roa)
                metrics_rows["ROIC"].append(p.roic)
                metrics_rows["毛利率"].append(p.gross_margin)
                metrics_rows["净利率"].append(p.net_margin)
            else:
                for k in metrics_rows:
                    metrics_rows[k].append(None)

        for name, values in metrics_rows.items():
            if any(v is not None for v in values):
                formatted = []
                for v in values:
                    if v is not None:
                        formatted.append(f"{v * 100:.2f}%")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    # Efficiency 指标（多年）
    efficiency = multi_year_data.get("efficiency", {})
    if efficiency:
        lines.append("\n【运营效率 Efficiency】")
        metrics_rows = {
            "现金周转周期": [],
            "营业周期": [],
            "存货周转天数": [],
            "应收账款周转天数": [],
            "应付账款周转天数": [],
        }
        for date in dates:
            e = efficiency.get(date)
            if e:
                metrics_rows["现金周转周期"].append(e.cash_conversion_cycle)
                metrics_rows["营业周期"].append(e.operating_cycle)
                metrics_rows["存货周转天数"].append(e.dio)
                metrics_rows["应收账款周转天数"].append(e.dso)
                metrics_rows["应付账款周转天数"].append(e.dpo)
            else:
                for k in metrics_rows:
                    metrics_rows[k].append(None)

        for name, values in metrics_rows.items():
            if any(v is not None for v in values):
                formatted = []
                for v in values:
                    if v is not None:
                        formatted.append(f"{v:.1f}")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    # Growth 指标（多年）
    growth = multi_year_data.get("growth", {})
    if growth:
        lines.append("\n【成长性 Growth】")
        metrics_rows = {
            "营收增长率": [],
            "净利润增长率": [],
            "可持续增长率": [],
        }
        for date in dates:
            g = growth.get(date)
            if g:
                metrics_rows["营收增长率"].append(g.revenue_growth_yoy)
                metrics_rows["净利润增长率"].append(g.profit_growth_yoy)
                metrics_rows["可持续增长率"].append(g.sustainable_growth_rate)
            else:
                for k in metrics_rows:
                    metrics_rows[k].append(None)

        for name, values in metrics_rows.items():
            if any(v is not None for v in values):
                formatted = []
                for v in values:
                    if v is not None:
                        formatted.append(f"{v * 100:.2f}%")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    # Safety 指标（多年）
    safety = multi_year_data.get("safety", {})
    if safety:
        lines.append("\n【财务安全 Safety】")
        metrics_rows = {
            "Altman Z-Score": [],
            "流动比率": [],
            "速动比率": [],
            "利息保障倍数": [],
            "资产负债率": [],
        }
        for date in dates:
            s = safety.get(date)
            if s:
                metrics_rows["Altman Z-Score"].append(s.altman_z_score)
                metrics_rows["流动比率"].append(s.current_ratio)
                metrics_rows["速动比率"].append(s.quick_ratio)
                metrics_rows["利息保障倍数"].append(s.interest_coverage)
                metrics_rows["资产负债率"].append(s.debt_to_equity)
            else:
                for k in metrics_rows:
                    metrics_rows[k].append(None)

        for name, values in metrics_rows.items():
            if any(v is not None for v in values):
                formatted = []
                for v in values:
                    if v is not None:
                        formatted.append(f"{v:.2f}")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    lines.append("\n" + "=" * width)
    return "\n".join(lines)


def _parse_year_filter(year_spec):
    """解析年份过滤参数"""
    if not year_spec:
        return None
    years = set()
    for part in year_spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(part))
    return years


def cmd_analyze(args):
    """财务分析"""
    analytics = FinancialAnalytics()

    try:
        # 解析年份过滤
        years_filter = _parse_year_filter(args.year) if args.year else None

        if args.dimension:
            # 获取特定维度分析
            dimension = args.dimension.lower()

            if dimension == "valuation":
                metrics = analytics.get_valuation(args.stock_code, args.period)
                if metrics:
                    print(f"=== 估值分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的估值数据: 需要 EPS/价格数据", file=sys.stderr)
                    return 1

            elif dimension == "profitability":
                metrics = analytics.get_profitability(args.stock_code, args.period)
                if metrics:
                    print(f"=== 盈利能力分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的盈利能力数据: 需要 revenue/net_profit/total_equity 等字段", file=sys.stderr)
                    return 1

            elif dimension == "efficiency":
                metrics = analytics.get_efficiency(args.stock_code, args.period)
                if metrics:
                    print(f"=== 运营效率分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的运营效率数据: 需要 inventory/accounts_receivable/accounts_payable 标准字段", file=sys.stderr)
                    return 1

            elif dimension == "growth":
                metrics = analytics.get_growth(args.stock_code, args.period)
                if metrics:
                    print(f"=== 成长性分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的成长性数据: 需要至少2期财务数据做 YoY 计算", file=sys.stderr)
                    return 1

            elif dimension == "safety":
                metrics = analytics.get_safety(args.stock_code, args.period)
                if metrics:
                    print(f"=== 财务安全分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的财务安全数据: 需要 current_assets/current_liabilities/total_equity 等字段", file=sys.stderr)
                    return 1

            else:
                print(f"未知维度: {dimension}", file=sys.stderr)
                print(
                    "支持的维度: valuation, profitability, efficiency, growth, safety"
                )
                return 1

        else:
            # 获取完整分析报告
            if args.format == "table":
                # 多年表格格式
                multi_year_data = analytics.get_multi_year_metrics(
                    args.stock_code, args.period
                )
                if not multi_year_data or not multi_year_data.get("report_dates"):
                    print(f"无法获取 {args.stock_code} 的多年数据", file=sys.stderr)
                    return 1
                print(_format_multi_year_metrics(multi_year_data, years_filter))
            else:
                # 其他格式使用完整报告
                report = analytics.get_full_report(args.stock_code, args.period)

                if report is None:
                    print(f"无法获取 {args.stock_code} 的分析数据", file=sys.stderr)
                    return 1

                if args.format == "json":
                    print(
                        json.dumps(
                            report.to_dict(), ensure_ascii=False, indent=2, default=str
                        )
                    )
                elif args.format == "summary":
                    summary = report.get_summary()
                    print(f"=== 财务分析摘要 ({args.stock_code}) ===")
                    print(
                        json.dumps(summary, ensure_ascii=False, indent=2, default=str)
                    )
                elif args.format == "markdown":
                    print(_report_to_markdown(report))
                elif args.format == "csv":
                    print(_report_to_csv(report))
                else:
                    # pretty print 格式化输出
                    print(report.pretty_print())

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


# ===== Markdown / CSV 输出格式 =====

def _format_market_cap(market_cap):
    """格式化市值显示"""
    if market_cap is None:
        return "-"
    if market_cap >= 1e12:
        return f"{market_cap / 1e12:.2f}万亿"
    elif market_cap >= 1e8:
        return f"{market_cap / 1e8:.2f}亿"
    elif market_cap >= 1e4:
        return f"{market_cap / 1e4:.2f}万"
    else:
        return f"{market_cap:.2f}"


def _report_to_markdown(report) -> str:
    """将 FullAnalysisReport 转为 Markdown 表格"""
    lines = []
    lines.append(f"# 财务分析报告: {report.stock_code}")
    lines.append(f"报告日期: {report.report_date} | 综合评分: {report.get_score():.1f}/100")
    lines.append("")

    def _add_dimension_table(title, rows):
        lines.append(f"## {title}")
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        for name, val in rows:
            lines.append(f"| {name} | {val} |")
        lines.append("")

    # Valuation
    if report.valuation:
        v = report.valuation
        _add_dimension_table("估值指标 Valuation", [
            ("市盈率 (P/E)", f"{v.pe_ratio:.2f}" if v.pe_ratio else "-"),
            ("市净率 (P/B)", f"{v.pb_ratio:.2f}" if v.pb_ratio else "-"),
            ("市销率 (P/S)", f"{v.ps_ratio:.2f}" if v.ps_ratio else "-"),
            ("总市值", _format_market_cap(v.market_cap) if v.market_cap else "-"),
            ("股息率", f"{v.dividend_yield * 100:.2f}%" if v.dividend_yield else "-"),
            ("EPS", f"{v.eps:.2f}" if v.eps else "-"),
        ])
    else:
        lines.append("## 估值指标 Valuation")
        lines.append("⚠️ 数据不可用")
        lines.append("")

    # Profitability
    if report.profitability:
        p = report.profitability
        _add_dimension_table("盈利能力 Profitability", [
            ("ROE", f"{p.roe * 100:.2f}%" if p.roe else "-"),
            ("ROA", f"{p.roa * 100:.2f}%" if p.roa else "-"),
            ("ROIC", f"{p.roic * 100:.2f}%" if p.roic else "-"),
            ("毛利率", f"{p.gross_margin * 100:.2f}%" if p.gross_margin else "-"),
            ("净利率", f"{p.net_margin * 100:.2f}%" if p.net_margin else "-"),
        ])
    else:
        lines.append("## 盈利能力 Profitability")
        lines.append("⚠️ 数据不可用")
        lines.append("")

    # Efficiency
    if report.efficiency:
        e = report.efficiency
        _add_dimension_table("运营效率 Efficiency", [
            ("现金周转周期", f"{e.cash_conversion_cycle:.1f} 天" if e.cash_conversion_cycle else "-"),
            ("存货周转天数", f"{e.dio:.1f} 天" if e.dio else "-"),
            ("应收账款周转天数", f"{e.dso:.1f} 天" if e.dso else "-"),
            ("应付账款周转天数", f"{e.dpo:.1f} 天" if e.dpo else "-"),
        ])
    else:
        lines.append("## 运营效率 Efficiency")
        lines.append("⚠️ 数据不可用")
        lines.append("")

    # Growth
    if report.growth:
        g = report.growth
        _add_dimension_table("成长性 Growth", [
            ("营收增长率", f"{g.revenue_growth_yoy * 100:.2f}%" if g.revenue_growth_yoy else "-"),
            ("净利润增长率", f"{g.profit_growth_yoy * 100:.2f}%" if g.profit_growth_yoy else "-"),
            ("可持续增长率", f"{g.sustainable_growth_rate * 100:.2f}%" if g.sustainable_growth_rate else "-"),
        ])
    else:
        lines.append("## 成长性 Growth")
        lines.append("⚠️ 数据不可用")
        lines.append("")

    # Safety
    if report.safety:
        s = report.safety
        _add_dimension_table("财务安全 Safety", [
            ("Altman Z-Score", f"{s.altman_z_score:.2f}" if s.altman_z_score else "-"),
            ("流动比率", f"{s.current_ratio:.2f}" if s.current_ratio else "-"),
            ("速动比率", f"{s.quick_ratio:.2f}" if s.quick_ratio else "-"),
            ("利息保障倍数", f"{s.interest_coverage:.2f}x" if s.interest_coverage else "-"),
            ("资产负债率", f"{s.debt_to_equity:.2f}" if s.debt_to_equity else "-"),
        ])
    else:
        lines.append("## 财务安全 Safety")
        lines.append("⚠️ 数据不可用")
        lines.append("")

    return "\n".join(lines)


def _report_to_csv(report) -> str:
    """将 FullAnalysisReport 转为 CSV 格式"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["维度", "指标", "值"])

    if report.valuation:
        v = report.valuation
        writer.writerow(["Valuation", "P/E", v.pe_ratio])
        writer.writerow(["Valuation", "P/B", v.pb_ratio])
        writer.writerow(["Valuation", "P/S", v.ps_ratio])
        writer.writerow(["Valuation", "Market Cap", v.market_cap])
        writer.writerow(["Valuation", "Dividend Yield", v.dividend_yield])
        writer.writerow(["Valuation", "EPS", v.eps])

    if report.profitability:
        p = report.profitability
        writer.writerow(["Profitability", "ROE", p.roe])
        writer.writerow(["Profitability", "ROA", p.roa])
        writer.writerow(["Profitability", "ROIC", p.roic])
        writer.writerow(["Profitability", "Gross Margin", p.gross_margin])
        writer.writerow(["Profitability", "Net Margin", p.net_margin])

    if report.efficiency:
        e = report.efficiency
        writer.writerow(["Efficiency", "CCC", e.cash_conversion_cycle])
        writer.writerow(["Efficiency", "DIO", e.dio])
        writer.writerow(["Efficiency", "DSO", e.dso])
        writer.writerow(["Efficiency", "DPO", e.dpo])

    if report.growth:
        g = report.growth
        writer.writerow(["Growth", "Revenue Growth", g.revenue_growth_yoy])
        writer.writerow(["Growth", "Profit Growth", g.profit_growth_yoy])
        writer.writerow(["Growth", "Sustainable Growth", g.sustainable_growth_rate])

    if report.safety:
        s = report.safety
        writer.writerow(["Safety", "Altman Z", s.altman_z_score])
        writer.writerow(["Safety", "Current Ratio", s.current_ratio])
        writer.writerow(["Safety", "Quick Ratio", s.quick_ratio])
        writer.writerow(["Safety", "Interest Coverage", s.interest_coverage])
        writer.writerow(["Safety", "Debt/Equity", s.debt_to_equity])

    return output.getvalue()


# ===== Compare 子命令 =====

def cmd_compare(args):
    """多股并列对比"""
    analytics = FinancialAnalytics()
    stock_codes = args.stock_codes
    fmt = args.format

    results = {}
    for code in stock_codes:
        try:
            report = analytics.get_full_report(code, args.period)
            if report is not None:
                results[code] = report
            else:
                results[code] = None
        except Exception as e:
            print(f"⚠️ {code} 分析失败: {e}", file=sys.stderr)
            results[code] = None

    valid_codes = [c for c in stock_codes if results.get(c) is not None]
    if not valid_codes:
        print("所有股票分析均失败", file=sys.stderr)
        return 1

    if fmt == "markdown":
        print(_compare_to_markdown(stock_codes, results))
    elif fmt == "csv":
        print(_compare_to_csv(stock_codes, results))
    elif fmt == "json":
        data = {}
        for code in valid_codes:
            data[code] = results[code].to_dict()
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        # 默认 pretty table 格式
        print(_compare_to_table(stock_codes, results))

    return 0


def _compare_to_table(stock_codes, results) -> str:
    """多股对比 - 文本表格"""
    lines = []
    width = 20 + 16 * len(stock_codes)
    lines.append("=" * width)
    header = f"{'指标':<20}" + "".join(f"{c:>16}" for c in stock_codes)
    lines.append(header)
    lines.append("-" * width)

    def _add_row(name, values):
        row = f"{name:<20}" + "".join(f"{v:>16}" for v in values)
        lines.append(row)

    # 核心指标
    metrics = [
        ("PE", lambda r: f"{r.valuation.pe_ratio:.1f}" if r.valuation and r.valuation.pe_ratio else "-"),
        ("PB", lambda r: f"{r.valuation.pb_ratio:.2f}" if r.valuation and r.valuation.pb_ratio else "-"),
        ("市值", lambda r: _format_market_cap(r.valuation.market_cap) if r.valuation and r.valuation.market_cap else "-"),
        ("营收(亿)", lambda r: f"{_get_revenue(r) / 1e8:.1f}" if _get_revenue(r) else "-"),
        ("净利润(亿)", lambda r: f"{_get_net_profit(r) / 1e8:.1f}" if _get_net_profit(r) else "-"),
        ("毛利率", lambda r: f"{r.profitability.gross_margin * 100:.1f}%" if r.profitability and r.profitability.gross_margin else "-"),
        ("净利率", lambda r: f"{r.profitability.net_margin * 100:.1f}%" if r.profitability and r.profitability.net_margin else "-"),
        ("ROE", lambda r: f"{r.profitability.roe * 100:.1f}%" if r.profitability and r.profitability.roe else "-"),
        ("营收增长", lambda r: f"{r.growth.revenue_growth_yoy * 100:.1f}%" if r.growth and r.growth.revenue_growth_yoy else "-"),
        ("Z-Score", lambda r: f"{r.safety.altman_z_score:.2f}" if r.safety and r.safety.altman_z_score else "-"),
        ("流动比率", lambda r: f"{r.safety.current_ratio:.2f}" if r.safety and r.safety.current_ratio else "-"),
        ("评分", lambda r: f"{r.get_score():.0f}/100"),
    ]

    for name, getter in metrics:
        values = []
        for code in stock_codes:
            r = results.get(code)
            if r is None:
                values.append("N/A")
            else:
                try:
                    values.append(getter(r))
                except Exception:
                    values.append("-")
        _add_row(name, values)

    lines.append("=" * width)
    return "\n".join(lines)


def _get_revenue(report):
    """从报告中获取营收"""
    if report.profitability:
        # 从 full_report dict 获取
        d = report.to_dict()
        inc = d.get("profitability")
        if inc and inc.get("revenue"):
            return inc["revenue"]
    return None


def _get_net_profit(report):
    """从报告中获取净利润"""
    if report.profitability:
        d = report.to_dict()
        inc = d.get("profitability")
        if inc and inc.get("net_profit"):
            return inc["net_profit"]
    return None


def _compare_to_markdown(stock_codes, results) -> str:
    """多股对比 - Markdown 表格"""
    lines = []
    header = "| 指标 |" + "".join(f" {c} |" for c in stock_codes)
    sep = "|------|" + "".join("------|" for _ in stock_codes)
    lines.append(header)
    lines.append(sep)

    metrics = [
        ("PE", lambda r: f"{r.valuation.pe_ratio:.1f}" if r.valuation and r.valuation.pe_ratio else "-"),
        ("PB", lambda r: f"{r.valuation.pb_ratio:.2f}" if r.valuation and r.valuation.pb_ratio else "-"),
        ("市值", lambda r: _format_market_cap(r.valuation.market_cap) if r.valuation and r.valuation.market_cap else "-"),
        ("毛利率", lambda r: f"{r.profitability.gross_margin * 100:.1f}%" if r.profitability and r.profitability.gross_margin else "-"),
        ("净利率", lambda r: f"{r.profitability.net_margin * 100:.1f}%" if r.profitability and r.profitability.net_margin else "-"),
        ("ROE", lambda r: f"{r.profitability.roe * 100:.1f}%" if r.profitability and r.profitability.roe else "-"),
        ("营收增长", lambda r: f"{r.growth.revenue_growth_yoy * 100:.1f}%" if r.growth and r.growth.revenue_growth_yoy else "-"),
        ("Z-Score", lambda r: f"{r.safety.altman_z_score:.2f}" if r.safety and r.safety.altman_z_score else "-"),
        ("评分", lambda r: f"{r.get_score():.0f}"),
    ]

    for name, getter in metrics:
        vals = []
        for code in stock_codes:
            r = results.get(code)
            if r is None:
                vals.append("N/A")
            else:
                try:
                    vals.append(getter(r))
                except Exception:
                    vals.append("-")
        lines.append(f"| {name} |" + "".join(f" {v} |" for v in vals))

    return "\n".join(lines)


def _compare_to_csv(stock_codes, results) -> str:
    """多股对比 - CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["指标"] + stock_codes)

    metrics = [
        ("PE", lambda r: r.valuation.pe_ratio if r.valuation and r.valuation.pe_ratio else None),
        ("PB", lambda r: r.valuation.pb_ratio if r.valuation and r.valuation.pb_ratio else None),
        ("毛利率", lambda r: r.profitability.gross_margin if r.profitability and r.profitability.gross_margin else None),
        ("净利率", lambda r: r.profitability.net_margin if r.profitability and r.profitability.net_margin else None),
        ("ROE", lambda r: r.profitability.roe if r.profitability and r.profitability.roe else None),
        ("营收增长", lambda r: r.growth.revenue_growth_yoy if r.growth and r.growth.revenue_growth_yoy else None),
        ("Z-Score", lambda r: r.safety.altman_z_score if r.safety and r.safety.altman_z_score else None),
    ]

    for name, getter in metrics:
        vals = []
        for code in stock_codes:
            r = results.get(code)
            if r is None:
                vals.append("")
            else:
                try:
                    vals.append(getter(r))
                except Exception:
                    vals.append("")
        writer.writerow([name] + vals)

    return output.getvalue()


# ===== Screen 子命令 =====

# 预置的港股热门股票列表
DEFAULT_HK_STOCKS = [
    "0700.HK", "9988.HK", "0005.HK", "1299.HK", "0941.HK",
    "2318.HK", "0388.HK", "9999.HK", "1810.HK", "2020.HK",
    "9961.HK", "9618.HK", "3690.HK", "9992.HK", "0241.HK",
]

DEFAULT_US_STOCKS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK.B", "JPM", "V",
]

DEFAULT_A_STOCKS = [
    "600519.SH", "000858.SZ", "601318.SH", "600036.SH", "000001.SZ",
]


def cmd_screen(args):
    """选股筛选"""
    analytics = FinancialAnalytics()

    # 确定股票列表
    market = args.market
    if market == "HK":
        stock_list = DEFAULT_HK_STOCKS
    elif market == "US":
        stock_list = DEFAULT_US_STOCKS
    elif market == "A":
        stock_list = DEFAULT_A_STOCKS
    else:
        stock_list = DEFAULT_HK_STOCKS + DEFAULT_US_STOCKS + DEFAULT_A_STOCKS

    # 筛选条件
    min_roe = args.min_roe / 100.0 if args.min_roe else None
    max_pe = args.max_pe if args.max_pe else None
    min_growth = args.min_growth / 100.0 if args.min_growth else None

    passed = []
    failed = []

    for code in stock_list:
        try:
            report = analytics.get_full_report(code, args.period)
            if report is None:
                failed.append((code, "无分析数据"))
                continue

            reasons = []
            # PE 筛选
            if max_pe is not None:
                if report.valuation and report.valuation.pe_ratio:
                    if report.valuation.pe_ratio > max_pe:
                        reasons.append(f"PE={report.valuation.pe_ratio:.1f}>{max_pe}")
                # PE 为 None 不排除

            # ROE 筛选
            if min_roe is not None:
                if report.profitability and report.profitability.roe is not None:
                    if report.profitability.roe < min_roe:
                        reasons.append(f"ROE={report.profitability.roe * 100:.1f}%<{min_roe * 100:.1f}%")
                else:
                    reasons.append("ROE=无数据")

            # 成长性筛选
            if min_growth is not None:
                if report.growth and report.growth.revenue_growth_yoy is not None:
                    if report.growth.revenue_growth_yoy < min_growth:
                        reasons.append(f"增长={report.growth.revenue_growth_yoy * 100:.1f}%<{min_growth * 100:.1f}%")
                else:
                    reasons.append("增长=无数据")

            if reasons:
                failed.append((code, ", ".join(reasons)))
            else:
                pe = f"{report.valuation.pe_ratio:.1f}" if report.valuation and report.valuation.pe_ratio else "-"
                roe = f"{report.profitability.roe * 100:.1f}%" if report.profitability and report.profitability.roe else "-"
                growth = f"{report.growth.revenue_growth_yoy * 100:.1f}%" if report.growth and report.growth.revenue_growth_yoy else "-"
                score = f"{report.get_score():.0f}"
                passed.append((code, pe, roe, growth, score))

        except Exception as e:
            failed.append((code, str(e)))

    # 输出结果
    if args.format == "json":
        result = {"passed": [], "failed": [(c, r) for c, r in failed]}
        for code, pe, roe, growth, score in passed:
            result["passed"].append({"code": code, "pe": pe, "roe": roe, "growth": growth, "score": score})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n📊 选股筛选结果 (市场: {market})")
        print(f"筛选条件: PE<={max_pe or '不限'}, ROE>={min_roe * 100 if min_roe else '不限'}%, 增长>={min_growth * 100 if min_growth else '不限'}%")
        print()

        if passed:
            print(f"✅ 通过 ({len(passed)} 只):")
            print(f"  {'代码':<12} {'PE':>8} {'ROE':>10} {'增长':>10} {'评分':>8}")
            print("  " + "-" * 50)
            for code, pe, roe, growth, score in passed:
                print(f"  {code:<12} {pe:>8} {roe:>10} {growth:>10} {score:>8}")
        else:
            print("✅ 通过: 无")

        if failed:
            print(f"\n❌ 未通过 ({len(failed)} 只):")
            for code, reason in failed:
                print(f"  {code}: {reason}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Financial SDK CLI - 财务数据获取和分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取财务数据
  financial-sdk get 9992.HK income_statement annual
  financial-sdk get 0700.HK all quarterly --force-refresh
  financial-sdk get AAPL balance_sheet annual --format json

  # 财务分析
  financial-sdk analyze 600000.SH
  financial-sdk analyze 600000.SH --format json
  financial-sdk analyze 600000.SH -d valuation
  financial-sdk analyze 600000.SH --format markdown
  financial-sdk analyze 600000.SH --format csv
  financial-sdk analyze 600000.SH --format table -y 2023,2024

  # 多股对比
  financial-sdk compare 0700.HK 9992.HK 3690.HK
  financial-sdk compare 0700.HK 9988.HK --format markdown

  # 选股筛选
  financial-sdk screen --market HK --min-roe 15 --max-pe 30 --min-growth 20

  # 系统命令
  financial-sdk health
  financial-sdk stocks --market HK
  financial-sdk cache
  financial-sdk cache --clear
  financial-sdk cache --stock 9992.HK
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # get 命令
    get_parser = subparsers.add_parser("get", help="获取股票财务数据")
    get_parser.add_argument("stock_code", help="股票代码 (如 9992.HK, AAPL, 600000.SH)")
    get_parser.add_argument(
        "report_type",
        nargs="?",
        default="all",
        choices=["balance_sheet", "income_statement", "cash_flow", "indicators", "all"],
        help="报表类型 (默认: all)",
    )
    get_parser.add_argument(
        "period",
        nargs="?",
        default="annual",
        choices=["annual", "quarterly"],
        help="报告期类型 (默认: annual)",
    )
    get_parser.add_argument("--force-refresh", action="store_true", help="强制刷新缓存")
    get_parser.add_argument(
        "--year", "-y", help="指定年份筛选，支持: 2024 或 2023,2024 或 2020-2024"
    )
    get_parser.add_argument(
        "--format",
        default="table",
        choices=["table", "wide", "json"],
        help="输出格式: table=指标为行(默认), wide=横向表格, json=JSON",
    )
    get_parser.add_argument(
        "--standard-only", action="store_true", help="仅显示标准化的核心指标"
    )

    # health 命令
    subparsers.add_parser("health", help="健康检查")

    # stocks 命令
    stocks_parser = subparsers.add_parser("stocks", help="获取支持的股票列表")
    stocks_parser.add_argument(
        "--market",
        default="all",
        choices=["A", "HK", "US", "all"],
        help="市场筛选 (默认: all)",
    )

    # cache 命令
    cache_parser = subparsers.add_parser("cache", help="缓存管理")
    cache_parser.add_argument("--clear", action="store_true", help="清除所有缓存")
    cache_parser.add_argument("--stock", help="清除指定股票的缓存 (如 9992.HK)")

    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="财务分析")
    analyze_parser.add_argument(
        "stock_code", help="股票代码 (如 9992.HK, AAPL, 600000.SH)"
    )
    analyze_parser.add_argument(
        "--period",
        default="annual",
        choices=["annual", "quarterly"],
        help="报告期类型 (默认: annual)",
    )
    analyze_parser.add_argument(
        "--dimension",
        "-d",
        choices=["valuation", "profitability", "efficiency", "growth", "safety"],
        help="分析维度，不指定则输出完整报告",
    )
    analyze_parser.add_argument(
        "--format",
        default="pretty",
        choices=["pretty", "json", "summary", "table", "markdown", "csv"],
        help="输出格式: pretty=格式化报告(默认), json=JSON, summary=摘要, table=表格(多期), markdown=Markdown表格, csv=CSV",
    )
    analyze_parser.add_argument(
        "--year",
        "-y",
        help="指定年份筛选，支持: 2024 或 2023,2024 或 2020-2024 (仅table格式)",
    )

    # compare 命令
    compare_parser = subparsers.add_parser("compare", help="多股并列对比")
    compare_parser.add_argument(
        "stock_codes", nargs="+", help="股票代码列表 (如 0700.HK 9992.HK 3690.HK)"
    )
    compare_parser.add_argument(
        "--period", default="annual", choices=["annual", "quarterly"],
        help="报告期类型 (默认: annual)",
    )
    compare_parser.add_argument(
        "--format", default="table", choices=["table", "markdown", "csv", "json"],
        help="输出格式 (默认: table)",
    )

    # screen 命令
    screen_parser = subparsers.add_parser("screen", help="选股筛选")
    screen_parser.add_argument(
        "--market", default="HK", choices=["A", "HK", "US"],
        help="市场 (默认: HK)",
    )
    screen_parser.add_argument("--min-roe", type=float, default=None, help="最低 ROE (百分比，如 15)")
    screen_parser.add_argument("--max-pe", type=float, default=None, help="最高 PE (如 30)")
    screen_parser.add_argument("--min-growth", type=float, default=None, help="最低营收增长率 (百分比，如 20)")
    screen_parser.add_argument(
        "--period", default="annual", choices=["annual", "quarterly"],
        help="报告期类型 (默认: annual)",
    )
    screen_parser.add_argument(
        "--format", default="pretty", choices=["pretty", "json"],
        help="输出格式 (默认: pretty)",
    )

    args = parser.parse_args()

    if args.command is None:
        print("""
╔══════════════════════════════════════════════════════════════╗
║          Financial SDK CLI - 财务数据获取和分析工具           ║
╠══════════════════════════════════════════════════════════════╣
║  使用 help 查看详细帮助:                                     ║
║                                                              ║
║    financial-sdk --help              查看全局帮助             ║
║    financial-sdk get --help          查看 get 命令帮助        ║
║    financial-sdk analyze --help      查看 analyze 命令帮助   ║
║                                                              ║
║  快速开始:                                                   ║
║                                                              ║
║    financial-sdk get 9992.HK income_statement annual         ║
║    financial-sdk analyze 600000.SH                           ║
║    financial-sdk analyze 600000.SH -d valuation              ║
║    financial-sdk health                                      ║
║                                                              ║
║  支持市场: A股(600000.SH)  港股(9992.HK)  美股(AAPL)         ║
╚══════════════════════════════════════════════════════════════╝
        """)
        return 0

    if args.command == "get":
        return cmd_get(args)
    elif args.command == "health":
        return cmd_health(args)
    elif args.command == "stocks":
        return cmd_stocks(args)
    elif args.command == "cache":
        return cmd_cache(args)
    elif args.command == "analyze":
        return cmd_analyze(args)
    elif args.command == "compare":
        return cmd_compare(args)
    elif args.command == "screen":
        return cmd_screen(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
