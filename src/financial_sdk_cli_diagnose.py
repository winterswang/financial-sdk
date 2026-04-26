#!/usr/bin/env python3
"""
财务数据诊断脚本

用于验证 SDK 计算的数据是否正确，显示计算公式的分子和分母。

使用方法:
    python src/financial_sdk_cli_diagnose.py 0700.HK
    python src/financial_sdk_cli_diagnose.py AAPL
"""

import argparse
import sys
from typing import Any, Dict, Optional

import pandas as pd


def get_value_from_df(df: Optional[pd.DataFrame], field: str, index: int = -1) -> Optional[float]:
    """从 DataFrame 获取字段值"""
    if df is None or df.empty:
        return None
    if field not in df.columns:
        return None
    values = df[field].dropna()
    if values.empty:
        return None
    try:
        return float(values.iloc[index])
    except (ValueError, TypeError):
        return None


def format_currency(value: float, currency: str) -> str:
    """格式化货币值"""
    if abs(value) >= 1e12:
        return f"{value / 1e12:.2f}万亿 {currency}"
    elif abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿 {currency}"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.2f}万 {currency}"
    else:
        return f"{value:.2f} {currency}"


def diagnose_stock(stock_code: str) -> Dict[str, Any]:
    """
    诊断股票数据，计算公式验证

    Returns:
        包含原始数据和计算公式的字典
    """
    # 延迟导入避免循环依赖
    from financial_sdk import FinancialFacade
    from financial_sdk.price import get_price_provider

    facade = FinancialFacade()
    price_provider = get_price_provider()

    result = {
        "stock_code": stock_code,
        "raw_data": {},
        "calculated_metrics": {},
        "warnings": [],
    }

    # 获取价格
    price_result = price_provider.get_price(stock_code)
    if price_result.success and price_result.price:
        result["raw_data"]["current_price"] = {
            "value": price_result.price.current_price,
            "currency": price_result.price.currency,
            "source": price_result.price.source,
        }
    else:
        result["warnings"].append(f"无法获取价格: {price_result.error}")

    # 获取财务数据
    try:
        bundle = facade.get_financial_data(stock_code, "all", "annual")
    except Exception as e:
        result["warnings"].append(f"无法获取财务数据: {e}")
        return result

    # 提取原始数据
    income = bundle.income_statement
    balance = bundle.balance_sheet
    cash_flow = bundle.cash_flow
    indicators = bundle.indicators

    # 从利润表提取
    revenue = get_value_from_df(income, "revenue")
    gross_profit = get_value_from_df(income, "gross_profit")
    net_profit = get_value_from_df(income, "net_profit")
    operating_profit = get_value_from_df(income, "operating_profit")
    eps = get_value_from_df(income, "eps")
    total_cost = get_value_from_df(income, "total_cost")
    tax_expense = get_value_from_df(income, "tax_expense")

    # 从资产负债表提取
    total_assets = get_value_from_df(balance, "total_assets")
    total_liabilities = get_value_from_df(balance, "total_liabilities")
    total_equity = get_value_from_df(balance, "total_equity")
    current_assets = get_value_from_df(balance, "current_assets")
    current_liabilities = get_value_from_df(balance, "current_liabilities")
    cash_and_equivalents = get_value_from_df(balance, "cash_and_equivalents")
    fixed_assets = get_value_from_df(balance, "fixed_assets")
    intangible_assets = get_value_from_df(balance, "intangible_assets")

    # 从现金流量表提取
    operating_cash_flow = get_value_from_df(cash_flow, "operating_cash_flow")
    investing_cash_flow = get_value_from_df(cash_flow, "investing_cash_flow")
    financing_cash_flow = get_value_from_df(cash_flow, "financing_cash_flow")
    depreciation = get_value_from_df(cash_flow, "depreciation_amortization")
    capex = get_value_from_df(cash_flow, "capex")

    # 从指标表提取
    indicators_eps = get_value_from_df(indicators, "eps")
    bvps = get_value_from_df(indicators, "bvps")
    roe = get_value_from_df(indicators, "roe")
    roa = get_value_from_df(indicators, "roa")
    gross_margin = get_value_from_df(indicators, "gross_margin")
    net_margin = get_value_from_df(indicators, "net_margin")
    current_ratio = get_value_from_df(indicators, "current_ratio")
    quick_ratio = get_value_from_df(indicators, "quick_ratio")
    debt_to_assets = get_value_from_df(indicators, "debt_to_assets")
    dps = get_value_from_df(indicators, "dps")

    # 使用指标表的 EPS（如果利润表没有）
    if eps is None:
        eps = indicators_eps

    # 存储原始数据
    currency = bundle.currency

    def store(key: str, value: Optional[float], unit: str = ""):
        if value is not None:
            result["raw_data"][key] = {
                "value": value,
                "unit": unit,
                "currency": currency,
            }

    store("revenue", revenue, "HKD")
    store("gross_profit", gross_profit, currency)
    store("net_profit", net_profit, currency)
    store("operating_profit", operating_profit, currency)
    store("total_cost", total_cost, currency)
    store("tax_expense", tax_expense, currency)
    store("total_assets", total_assets, currency)
    store("total_liabilities", total_liabilities, currency)
    store("total_equity", total_equity, currency)
    store("current_assets", current_assets, currency)
    store("current_liabilities", current_liabilities, currency)
    store("cash_and_equivalents", cash_and_equivalents, currency)
    store("fixed_assets", fixed_assets, currency)
    store("intangible_assets", intangible_assets, currency)
    store("operating_cash_flow", operating_cash_flow, currency)
    store("investing_cash_flow", investing_cash_flow, currency)
    store("financing_cash_flow", financing_cash_flow, currency)
    store("depreciation_amortization", depreciation, currency)
    store("capex", capex, currency)
    store("eps", eps, "HKD/share")
    store("bvps", bvps, "HKD/share")
    store("dps", dps, "HKD/share")

    # 获取当前价格
    current_price = None
    if price_result.success and price_result.price:
        current_price = price_result.price.current_price

    # 计算指标
    metrics = {}

    # 毛利率 = 毛利 / 营收 * 100
    if gross_profit is not None and revenue is not None and revenue > 0:
        calc_gross_margin = gross_profit / revenue * 100
        metrics["gross_margin"] = {
            "formula": f"{gross_profit:.2f} / {revenue:.2f} * 100",
            "numerator": gross_profit,
            "denominator": revenue,
            "calculated": calc_gross_margin,
            "source_value": gross_margin,
            "unit": "%",
            "note": "毛利率 = 毛利 / 营收",
        }

    # 净利率 = 净利润 / 营收 * 100
    if net_profit is not None and revenue is not None and revenue > 0:
        calc_net_margin = net_profit / revenue * 100
        metrics["net_margin"] = {
            "formula": f"{net_profit:.2f} / {revenue:.2f} * 100",
            "numerator": net_profit,
            "denominator": revenue,
            "calculated": calc_net_margin,
            "source_value": net_margin,
            "unit": "%",
            "note": "净利率 = 净利润 / 营收",
        }

    # ROE = 净利润 / 股东权益 * 100
    if net_profit is not None and total_equity is not None and total_equity > 0:
        calc_roe = net_profit / total_equity * 100
        metrics["roe"] = {
            "formula": f"{net_profit:.2f} / {total_equity:.2f} * 100",
            "numerator": net_profit,
            "denominator": total_equity,
            "calculated": calc_roe,
            "source_value": roe,
            "unit": "%",
            "note": "ROE = 净利润 / 股东权益",
        }

    # ROA = 净利润 / 总资产 * 100
    if net_profit is not None and total_assets is not None and total_assets > 0:
        calc_roa = net_profit / total_assets * 100
        metrics["roa"] = {
            "formula": f"{net_profit:.2f} / {total_assets:.2f} * 100",
            "numerator": net_profit,
            "denominator": total_assets,
            "calculated": calc_roa,
            "source_value": roa,
            "unit": "%",
            "note": "ROA = 净利润 / 总资产",
        }

    # PE = 市价 / EPS
    if current_price is not None and eps is not None and eps > 0:
        calc_pe = current_price / eps
        metrics["pe_ratio"] = {
            "formula": f"{current_price:.2f} / {eps:.4f}",
            "numerator": current_price,
            "denominator": eps,
            "calculated": calc_pe,
            "unit": "x",
            "note": "PE = 市价 / 每股收益",
        }

    # PB = 市价 / 每股净资产
    # BVPS 来自指标数据源
    if current_price is not None and bvps is not None and bvps > 0:
        calc_pb = current_price / bvps
        metrics["pb_ratio"] = {
            "formula": f"{current_price:.2f} / {bvps:.4f}",
            "numerator": current_price,
            "denominator": bvps,
            "calculated": calc_pb,
            "source_value": bvps,  # 数据源直接提供 BVPS
            "unit": "x",
            "note": "PB = 市价 / 每股净资产 (BVPS)",
        }
    elif current_price is not None and total_equity is not None and total_equity > 0:
        # 备选方案：通过 BVPS 反推股本再计算
        if bvps is not None and bvps > 0:
            shares = total_equity / bvps
            calc_pb = current_price / bvps
            metrics["pb_ratio"] = {
                "formula": f"{current_price:.2f} / (总权益/股本)",
                "numerator": current_price,
                "denominator": calc_bvps,
                "calculated": calc_pb,
                "source_value": bvps,
                "unit": "x",
                "note": "PB = 市价 / 每股净资产",
            }

    # EV = 市值 + 总债务 - 现金
    # 总股本 = 总权益 / 每股净资产
    shares = None
    if total_equity is not None and bvps is not None and bvps > 0:
        shares = total_equity / bvps
    if current_price is not None and shares is not None and shares > 0:
        market_cap = current_price * shares
        enterprise_value = market_cap + (total_liabilities or 0) - (cash_and_equivalents or 0)
        metrics["enterprise_value"] = {
            "formula": f"市值({market_cap:.2f}) + 债务({total_liabilities or 0:.2f}) - 现金({cash_and_equivalents or 0:.2f})",
            "numerator_value": market_cap + (total_liabilities or 0),
            "denominator_value": cash_and_equivalents or 0,
            "calculated": enterprise_value,
            "unit": currency,
            "note": "EV = 市值 + 债务 - 现金",
        }

        # EV/EBITDA
        if net_profit is not None:
            ebitda = net_profit + (depreciation or 0)
            if ebitda > 0:
                calc_ev_ebitda = enterprise_value / ebitda
                metrics["ev_ebitda"] = {
                    "formula": f"EV({enterprise_value:.2f}) / EBITDA({ebitda:.2f})",
                    "numerator": enterprise_value,
                    "denominator": ebitda,
                    "calculated": calc_ev_ebitda,
                    "unit": "x",
                    "note": "EV/EBITDA = 企业价值 / EBITDA (EBITDA = 净利润 + 折旧)",
                }

    # 股息率 = 每股股息 / 市价 * 100
    if dps is not None and current_price is not None and current_price > 0:
        calc_dividend_yield = dps / current_price * 100
        metrics["dividend_yield"] = {
            "formula": f"{dps:.4f} / {current_price:.2f} * 100",
            "numerator": dps,
            "denominator": current_price,
            "calculated": calc_dividend_yield,
            "unit": "%",
            "note": "股息率 = 每股股息 / 市价",
        }

    # 流动比率 = 流动资产 / 流动负债
    if current_assets is not None and current_liabilities is not None and current_liabilities > 0:
        calc_current_ratio = current_assets / current_liabilities
        metrics["current_ratio"] = {
            "formula": f"{current_assets:.2f} / {current_liabilities:.2f}",
            "numerator": current_assets,
            "denominator": current_liabilities,
            "calculated": calc_current_ratio,
            "source_value": current_ratio,
            "unit": "x",
            "note": "流动比率 = 流动资产 / 流动负债",
        }

    # 资产负债率 = 总负债 / 总资产 * 100
    if total_liabilities is not None and total_assets is not None and total_assets > 0:
        calc_debt_ratio = total_liabilities / total_assets * 100
        metrics["debt_to_assets"] = {
            "formula": f"{total_liabilities:.2f} / {total_assets:.2f} * 100",
            "numerator": total_liabilities,
            "denominator": total_assets,
            "calculated": calc_debt_ratio,
            "source_value": debt_to_assets,
            "unit": "%",
            "note": "资产负债率 = 总负债 / 总资产",
        }

    result["calculated_metrics"] = metrics

    return result


def format_metric_value(val: Any) -> str:
    """格式化指标值"""
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        return f"{val:,.4f}"
    return str(val)


def print_raw_data_for_verification(result: Dict[str, Any]) -> None:
    """只打印原始数据，方便用户去网站核对"""
    stock_code = result["stock_code"]
    raw = result.get("raw_data", {})

    print(f"# {stock_code} 原始数据（用于网站核对）")
    print("=" * 60)

    # 关键数据
    print("\n## 利润表数据")
    print("-" * 40)
    for key in ["revenue", "gross_profit", "net_profit", "operating_profit", "eps"]:
        if key in raw:
            val = raw[key]["value"]
            print(f"  {key}: {val:,.4f}")

    # 资产负债表数据
    print("\n## 资产负债表数据")
    print("-" * 40)
    for key in ["total_assets", "total_liabilities", "total_equity",
                "current_assets", "current_liabilities", "cash_and_equivalents"]:
        if key in raw:
            val = raw[key]["value"]
            print(f"  {key}: {val:,.4f}")

    # 现金流量表数据
    print("\n## 现金流量表数据")
    print("-" * 40)
    for key in ["operating_cash_flow", "depreciation_amortization"]:
        if key in raw:
            val = raw[key]["value"]
            print(f"  {key}: {val:,.4f}")

    # 指标数据（来自数据源）
    print("\n## 指标数据")
    print("-" * 40)
    for key in ["bvps", "roe", "roa", "gross_margin", "net_margin", "dps"]:
        if key in raw:
            val = raw[key]["value"]
            print(f"  {key}: {val:,.4f}")

    # 价格数据
    print("\n## 价格数据")
    print("-" * 40)
    if "current_price" in raw:
        print(f"  current_price: {raw['current_price']['value']:,.4f}")

    # 计算公式
    print("\n" + "=" * 60)
    print("## 计算公式（请用网站数据验证）")
    print("-" * 40)

    metrics = result.get("calculated_metrics", {})
    for metric_name, metric_data in sorted(metrics.items()):
        print(f"\n【{metric_name}】")
        print(f"  公式: {metric_data['formula']}")
        print(f"  分子 = {format_metric_value(metric_data.get('numerator'))}")
        print(f"  分母 = {format_metric_value(metric_data.get('denominator'))}")
        if 'note' in metric_data:
            print(f"  说明: {metric_data['note']}")


def print_diagnosis(result: Dict[str, Any]) -> None:
    """打印完整诊断结果"""
    print("=" * 80)
    print(f"财务数据诊断报告: {result['stock_code']}")
    print("=" * 80)

    # 警告信息
    if result.get("warnings"):
        print("\n## 警告信息")
        print("-" * 40)
        for warning in result["warnings"]:
            print(f"  ⚠️ {warning}")

    # 原始数据
    print("\n## 原始数据 (来自财务表)")
    print("-" * 40)

    raw = result.get("raw_data", {})
    if not raw:
        print("  无原始数据")
    else:
        for name, data in sorted(raw.items()):
            value = data.get("value")
            unit = data.get("unit", "")
            currency = data.get("currency", "")
            if value is not None:
                print(f"  {name}: {value:,.4f} {unit} {currency}")

    # 计算公式验证
    print("\n## 计算公式验证")
    print("-" * 40)

    metrics = result.get("calculated_metrics", {})
    if not metrics:
        print("  无法计算指标")
    else:
        for metric_name, metric_data in sorted(metrics.items()):
            print(f"\n  【{metric_name}】 {metric_data.get('unit', '')}")
            print(f"    公式: {metric_data['formula']}")
            print(f"    分子 (Numerator): {format_metric_value(metric_data.get('numerator'))}")
            print(f"    分母 (Denominator): {format_metric_value(metric_data.get('denominator'))}")
            print(f"    计算结果: {metric_data['calculated']:.4f}")

            # 如果有数据源的原始值，进行对比
            source_val = metric_data.get("source_value")
            if source_val is not None:
                diff = abs(metric_data['calculated'] - source_val)
                print(f"    数据源原始值: {source_val:.4f}")
                print(f"    差异: {diff:.4f}")
                if diff < 0.01:
                    print(f"    ✅ 验证通过")
                else:
                    print(f"    ⚠️ 存在差异 (差异 {diff:.2f})")

            print(f"    说明: {metric_data.get('note', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(
        description="财务数据诊断工具 - 显示计算公式的分子和分母",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 简化模式：只显示原始数据供您去网站核对
    python src/financial_sdk_cli_diagnose.py 0700.HK --verify

    # 完整诊断模式：显示计算结果对比
    python src/financial_sdk_cli_diagnose.py 0700.HK
        """
    )
    parser.add_argument("stock_code", help="股票代码 (如 0700.HK, AAPL, 600000.SH)")
    parser.add_argument("--verify", action="store_true",
                        help="简化模式：只显示原始数据，方便去网站核对")
    args = parser.parse_args()

    print(f"正在获取 {args.stock_code} 的数据并分析...")
    print()

    try:
        result = diagnose_stock(args.stock_code)
        if args.verify:
            print_raw_data_for_verification(result)
        else:
            print_diagnosis(result)
    except Exception as e:
        print(f"诊断失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()