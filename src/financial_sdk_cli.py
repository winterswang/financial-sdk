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
import json
import sys
from pathlib import Path

import pandas as pd

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent))

from financial_sdk import FinancialFacade
from financial_sdk.analytics import FinancialAnalytics

# 标准化的核心指标列表（跨市场统一）
STANDARD_FIELDS = {
    # 现金流
    "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
    "net_cash_flow", "beginning_cash", "ending_cash",
    "total_operating_inflow", "total_operating_outflow",
    "total_investing_inflow", "total_investing_outflow",
    "total_financing_inflow", "total_financing_outflow",
    "capex", "dividends_paid", "debt_repayment",
    "staff_cash_paid", "taxes_paid", "tax_refund_received",
    "depreciation_amortization", "profit_before_tax",
    # 资产负债表
    "total_assets", "total_liabilities", "total_equity",
    "current_assets", "non_current_assets",
    "current_liabilities", "non_current_liabilities",
    "fixed_assets", "intangible_assets", "goodwill",
    "accounts_receivable", "inventory", "accounts_payable",
    "short_term_debt", "long_term_debt", "cash_and_equivalents",
    # 利润表
    "revenue", "total_cost", "gross_profit",
    "operating_profit", "net_profit",
    "selling_expense", "admin_expense", "financial_expense", "rd_expense",
    "tax_expense", "eps", "diluted_eps",
    # 指标
    "roe", "roa", "gross_margin", "net_margin",
    "current_ratio", "quick_ratio", "debt_to_assets", "debt_to_equity",
    "bvps", "pe_ratio", "pb_ratio",
    # 其他
    "report_date", "stock_code",
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


def _transpose_for_display(df: pd.DataFrame, standard_only: bool = False) -> pd.DataFrame:
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
        if idx in ["SECUCODE", "SECURITY_NAME_ABBR", "ORG_CODE", "ORG_TYPE",
                   "REPORT_TYPE", "REPORT_DATE_NAME", "SECURITY_TYPE_CODE",
                   "NOTICE_DATE", "UPDATE_DATE", "CURRENCY"]:
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
            lambda x: _format_number(x) if pd.notna(x) and isinstance(x, (int, float)) else x
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
                    # 转置格式：指标为行，日期为列（最新在左）
                    display_df = _transpose_for_display(df, standard_only=args.standard_only)
                    print(display_df.to_string())
                elif args.format == "wide":
                    # 宽表格式：原始横向展示
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
                year = int(str(d)[:4])
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
                    val_str = f"{value*100:.2f}%" if value else "-"
                else:
                    val_str = _format_number(value) if value else "-"
                lines.append(f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates]))

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
                val_str = f"{value*100:.2f}%" if is_percent else (f"{value:.4f}" if value else "-")
                lines.append(f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates]))

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
                lines.append(f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates]))

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
                val_str = f"{value*100:.2f}%" if is_percent else (f"{value:.4f}" if value else "-")
                lines.append(f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates]))

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
                lines.append(f"  {name:<23}" + "".join([f"{val_str:>15}" for _ in dates]))

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
                year = int(str(d)[:4])
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
                    val_str = f"{value*100:.2f}%"
                elif fmt == "market_cap":
                    val_str = f"{value/1e8:.2f}" if value else "-"
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
            "ROE": [], "ROA": [], "ROIC": [],
            "毛利率": [], "净利率": [],
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
                        formatted.append(f"{v*100:.2f}%")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    # Efficiency 指标（多年）
    efficiency = multi_year_data.get("efficiency", {})
    if efficiency:
        lines.append("\n【运营效率 Efficiency】")
        metrics_rows = {
            "现金周转周期": [], "营业周期": [],
            "存货周转天数": [], "应收账款周转天数": [], "应付账款周转天数": [],
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
            "营收增长率": [], "净利润增长率": [], "可持续增长率": [],
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
                        formatted.append(f"{v*100:.2f}%")
                    else:
                        formatted.append("-")
                lines.append(f"  {name:<26}" + "".join([f"{s:>16}" for s in formatted]))

    # Safety 指标（多年）
    safety = multi_year_data.get("safety", {})
    if safety:
        lines.append("\n【财务安全 Safety】")
        metrics_rows = {
            "Altman Z-Score": [], "流动比率": [],
            "速动比率": [], "利息保障倍数": [], "资产负债率": [],
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
                    print(f"无法获取 {args.stock_code} 的估值数据", file=sys.stderr)
                    return 1

            elif dimension == "profitability":
                metrics = analytics.get_profitability(args.stock_code, args.period)
                if metrics:
                    print(f"=== 盈利能力分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的盈利能力数据", file=sys.stderr)
                    return 1

            elif dimension == "efficiency":
                metrics = analytics.get_efficiency(args.stock_code, args.period)
                if metrics:
                    print(f"=== 运营效率分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的运营效率数据", file=sys.stderr)
                    return 1

            elif dimension == "growth":
                metrics = analytics.get_growth(args.stock_code, args.period)
                if metrics:
                    print(f"=== 成长性分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的成长性数据", file=sys.stderr)
                    return 1

            elif dimension == "safety":
                metrics = analytics.get_safety(args.stock_code, args.period)
                if metrics:
                    print(f"=== 财务安全分析 ({args.stock_code}) ===")
                    data = metrics.to_dict()
                    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
                else:
                    print(f"无法获取 {args.stock_code} 的财务安全数据", file=sys.stderr)
                    return 1

            else:
                print(f"未知维度: {dimension}", file=sys.stderr)
                print("支持的维度: valuation, profitability, efficiency, growth, safety")
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
                    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str))
                elif args.format == "summary":
                    summary = report.get_summary()
                    print(f"=== 财务分析摘要 ({args.stock_code}) ===")
                    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
                else:
                    # pretty print 格式化输出
                    print(report.pretty_print())

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


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
  financial-sdk analyze 600000.SH -d profitability
  financial-sdk analyze 0700.HK -d efficiency
  financial-sdk analyze 600000.SH --format table
  financial-sdk analyze 600000.SH --format table -y 2023,2024

  # 系统命令
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
                           choices=["table", "wide", "json"],
                           help="输出格式: table=指标为行(默认), wide=横向表格, json=JSON")
    get_parser.add_argument("--standard-only",
                           action="store_true",
                           help="仅显示标准化的核心指标")

    # health 命令
    subparsers.add_parser("health", help="健康检查")

    # stocks 命令
    stocks_parser = subparsers.add_parser("stocks", help="获取支持的股票列表")
    stocks_parser.add_argument("--market", default="all",
                              choices=["A", "HK", "US", "all"],
                              help="市场筛选 (默认: all)")

    # cache 命令
    subparsers.add_parser("cache", help="缓存统计")

    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="财务分析")
    analyze_parser.add_argument("stock_code", help="股票代码 (如 9992.HK, AAPL, 600000.SH)")
    analyze_parser.add_argument("--period", default="annual",
                               choices=["annual", "quarterly"],
                               help="报告期类型 (默认: annual)")
    analyze_parser.add_argument("--dimension", "-d",
                               choices=["valuation", "profitability", "efficiency", "growth", "safety"],
                               help="分析维度，不指定则输出完整报告")
    analyze_parser.add_argument("--format", default="pretty",
                               choices=["pretty", "json", "summary", "table"],
                               help="输出格式: pretty=格式化报告(默认), json=JSON, summary=摘要, table=表格(多期)")
    analyze_parser.add_argument("--year", "-y",
                               help="指定年份筛选，支持: 2024 或 2023,2024 或 2020-2024 (仅table格式)")

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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
