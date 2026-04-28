#!/usr/bin/env python3
"""
Financial SDK MCP Server

Exposes the financial-sdk functionality as MCP tools for OpenClaw integration.

Usage:
    pip install mcp
    openclaw mcp set financial-sdk '{"command": "python3", "args": ["/path/to/financial_sdk_mcp_server.py"]}'
"""

import json
import math
import re
import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, CallToolResult, TextContent

from financial_sdk import FinancialFacade, NoAdapterAvailableError
from financial_sdk.analytics import FinancialAnalytics


# 股票代码格式校验
STOCK_CODE_PATTERN = re.compile(r"^(\d{6}\.(SH|SZ)|\d{4,5}\.HK|[A-Z]{1,5}(\.[A-Z])?)$")


def _sanitize_value(val: Any) -> Any:
    """将 NaN/Inf 替换为 None，确保 JSON 可序列化"""
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
    return val


server = Server("financial-sdk")


def _bundle_to_dict(bundle) -> dict:
    result = {
        "stock_code": bundle.stock_code,
        "stock_name": bundle.stock_name,
        "market": bundle.market,
        "currency": bundle.currency,
        "is_partial": bundle.is_partial,
        "warnings": bundle.warnings,
        "report_periods": bundle.report_periods,
        "available_reports": bundle.get_available_reports(),
    }
    for report_name in ["balance_sheet", "income_statement", "cash_flow", "indicators"]:
        df = getattr(bundle, report_name, None)
        if df is not None and not df.empty:
            data_rows = []
            for row in df.head(10).values.tolist():
                data_rows.append([_sanitize_value(v) for v in row])
            result[report_name] = {
                "columns": list(df.columns),
                "data": data_rows,
                "row_count": len(df),
            }
    return result


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_financial_data",
            description="获取股票财务报表数据，支持A股、港股、美股的三表和财务指标",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码，支持格式: A股(600000.SH)、港股(0700.HK)、美股(AAPL)"},
                    "report_type": {"type": "string", "default": "all"},
                    "period": {"type": "string", "default": "annual"},
                    "force_refresh": {"type": "boolean", "default": False},
                },
                "required": ["stock_code"],
            },
        ),
        Tool(
            name="analyze",
            description="对股票进行全面的财务分析，包括估值、盈利能力、运营效率、成长性、财务安全五个维度",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码，支持格式: A股(600000.SH)、港股(0700.HK)、美股(AAPL)"},
                    "period": {"type": "string", "default": "annual"},
                    "dimension": {"type": "string", "description": "分析维度: valuation/profitability/efficiency/growth/safety，不指定则输出完整报告", "default": None},
                },
                "required": ["stock_code"],
            },
        ),
        Tool(
            name="diagnose",
            description="诊断股票分析数据完整性，检查各维度所需字段是否可用，帮助定位分析失败原因",
            inputSchema={
                "type": "object",
                "properties": {
                    "stock_code": {"type": "string", "description": "股票代码"},
                },
                "required": ["stock_code"],
            },
        ),
        Tool(
            name="get_supported_stocks",
            description="获取SDK支持的股票列表",
            inputSchema={
                "type": "object",
                "properties": {"market": {"type": "string", "default": "all"}},
            },
        ),
        Tool(
            name="health_check",
            description="健康检查，返回SDK各适配器和缓存的状态",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_cache_stats",
            description="获取缓存统计信息",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> CallToolResult:
    try:
        facade = FinancialFacade()

        if name == "get_financial_data":
            stock_code = arguments.get("stock_code")
            if not stock_code:
                return CallToolResult(content=[TextContent(type="text", text="Error: stock_code is required")], isError=True)
            if not isinstance(stock_code, str) or len(stock_code) > 20 or not STOCK_CODE_PATTERN.match(stock_code):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: invalid stock_code format: {stock_code}")], isError=True)
            try:
                bundle = facade.get_financial_data(
                    stock_code=stock_code,
                    report_type=arguments.get("report_type", "all"),
                    period=arguments.get("period", "annual"),
                    force_refresh=arguments.get("force_refresh", False),
                )
                return CallToolResult(content=[TextContent(type="text", text=json.dumps(_bundle_to_dict(bundle), ensure_ascii=False, indent=2))])
            except NoAdapterAvailableError as e:
                return CallToolResult(content=[TextContent(type="text", text=json.dumps({"error": "NoAdapterAvailableError", "stock_code": stock_code, "message": str(e)}, ensure_ascii=False))], isError=True)

        elif name == "analyze":
            stock_code = arguments.get("stock_code")
            if not stock_code:
                return CallToolResult(content=[TextContent(type="text", text="Error: stock_code is required")], isError=True)
            if not isinstance(stock_code, str) or len(stock_code) > 20 or not STOCK_CODE_PATTERN.match(stock_code):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: invalid stock_code format: {stock_code}")], isError=True)
            try:
                analytics = FinancialAnalytics()
                dimension = arguments.get("dimension")
                period = arguments.get("period", "annual")

                if dimension:
                    dim_map = {
                        "valuation": analytics.get_valuation,
                        "profitability": analytics.get_profitability,
                        "efficiency": analytics.get_efficiency,
                        "growth": analytics.get_growth,
                        "safety": analytics.get_safety,
                    }
                    func = dim_map.get(dimension)
                    if func is None:
                        return CallToolResult(content=[TextContent(type="text", text=f"Error: unknown dimension '{dimension}'. Use: valuation/profitability/efficiency/growth/safety")], isError=True)
                    metrics = func(stock_code, period)
                    if metrics is None:
                        return CallToolResult(content=[TextContent(type="text", text=json.dumps({"stock_code": stock_code, "dimension": dimension, "result": None, "message": "该维度数据不可用"}, ensure_ascii=False))])
                    return CallToolResult(content=[TextContent(type="text", text=json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2, default=str))])
                else:
                    report = analytics.get_full_report(stock_code, period)
                    if report is None:
                        return CallToolResult(content=[TextContent(type="text", text=json.dumps({"stock_code": stock_code, "result": None, "message": "所有维度分析均失败"}, ensure_ascii=False))])
                    result = report.to_dict()
                    result["score"] = report.get_score()
                    if report.failed_dimensions:
                        result["failed_dimensions"] = report.failed_dimensions
                    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2, default=str))])
            except Exception as e:
                return CallToolResult(content=[TextContent(type="text", text=json.dumps({"error": str(e), "stock_code": stock_code}, ensure_ascii=False))], isError=True)

        elif name == "diagnose":
            stock_code = arguments.get("stock_code")
            if not stock_code:
                return CallToolResult(content=[TextContent(type="text", text="Error: stock_code is required")], isError=True)
            if not isinstance(stock_code, str) or len(stock_code) > 20 or not STOCK_CODE_PATTERN.match(stock_code):
                return CallToolResult(content=[TextContent(type="text", text=f"Error: invalid stock_code format: {stock_code}")], isError=True)
            try:
                bundle = facade.get_financial_data(
                    stock_code=stock_code,
                    report_type="all",
                    period="annual",
                )

                diagnosis = {
                    "stock_code": stock_code,
                    "market": bundle.market,
                    "available_reports": bundle.get_available_reports(),
                    "is_partial": bundle.is_partial,
                    "warnings": bundle.warnings,
                    "dimensions": {},
                }

                # 检查各维度所需字段
                balance = bundle.balance_sheet
                income = bundle.income_statement
                indicators = bundle.indicators

                def _check_field(df, field_name):
                    if df is None or df.empty:
                        return "missing: 无数据"
                    if field_name not in df.columns:
                        return "missing: 字段不存在"
                    if df[field_name].isna().all():
                        return "missing: 值全为空"
                    return "ok"

                # Valuation
                diagnosis["dimensions"]["valuation"] = {
                    "status": "ok" if (_check_field(indicators, "eps") == "ok" or _check_field(income, "eps") == "ok") else "degraded",
                    "required_fields": {
                        "eps": _check_field(indicators, "eps") if indicators is not None else "missing: 无数据",
                        "pe_ratio": _check_field(indicators, "pe_ratio") if indicators is not None else "missing: 无数据",
                        "pb_ratio": _check_field(indicators, "pb_ratio") if indicators is not None else "missing: 无数据",
                    },
                }

                # Profitability
                prof_fields = {"revenue": _check_field(income, "revenue"), "net_profit": _check_field(income, "net_profit"), "total_equity": _check_field(balance, "total_equity"), "gross_profit": _check_field(income, "gross_profit")}
                prof_ok = all(v == "ok" for v in prof_fields.values())
                diagnosis["dimensions"]["profitability"] = {"status": "ok" if prof_ok else "degraded", "required_fields": prof_fields}

                # Efficiency
                eff_fields = {"inventory": _check_field(balance, "inventory"), "accounts_receivable": _check_field(balance, "accounts_receivable"), "accounts_payable": _check_field(balance, "accounts_payable")}
                eff_ok = all(v == "ok" for v in eff_fields.values())
                diagnosis["dimensions"]["efficiency"] = {"status": "ok" if eff_ok else "degraded", "required_fields": eff_fields}

                # Growth - need 2+ periods
                has_multi_period = False
                if income is not None and not income.empty and "report_date" in income.columns:
                    has_multi_period = income["report_date"].nunique() >= 2
                diagnosis["dimensions"]["growth"] = {
                    "status": "ok" if has_multi_period else "degraded",
                    "required_fields": {"multi_period_data": "ok" if has_multi_period else "missing: 需要至少2期数据"},
                }

                # Safety
                safety_fields = {"current_assets": _check_field(balance, "current_assets"), "current_liabilities": _check_field(balance, "current_liabilities"), "total_equity": _check_field(balance, "total_equity")}
                safety_ok = all(v == "ok" for v in safety_fields.values())
                diagnosis["dimensions"]["safety"] = {"status": "ok" if safety_ok else "degraded", "required_fields": safety_fields}

                return CallToolResult(content=[TextContent(type="text", text=json.dumps(diagnosis, ensure_ascii=False, indent=2))])
            except Exception as e:
                return CallToolResult(content=[TextContent(type="text", text=json.dumps({"error": str(e), "stock_code": stock_code}, ensure_ascii=False))], isError=True)

        elif name == "get_supported_stocks":
            stocks = facade.get_supported_stocks(market=arguments.get("market", "all"))
            return CallToolResult(content=[TextContent(type="text", text=json.dumps({"market": arguments.get("market", "all"), "stocks": stocks}, ensure_ascii=False, indent=2))])

        elif name == "health_check":
            health = facade.health_check()
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(health.to_dict(), ensure_ascii=False, indent=2))])

        elif name == "get_cache_stats":
            stats = facade.get_cache_stats()
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))])

        else:
            return CallToolResult(content=[TextContent(type="text", text=f"Unknown tool: {name}")], isError=True)

    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {str(e)}")], isError=True)


if __name__ == "__main__":
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())