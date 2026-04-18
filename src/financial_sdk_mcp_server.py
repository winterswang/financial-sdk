#!/usr/bin/env python3
"""
Financial SDK MCP Server

Exposes the financial-sdk functionality as MCP tools for OpenClaw integration.

Usage:
    pip install mcp
    openclaw mcp set financial-sdk '{"command": "python3", "args": ["/path/to/financial_sdk_mcp_server.py"]}'
"""

import json
import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, CallToolResult, TextContent

from financial_sdk import FinancialFacade, NoAdapterAvailableError


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
            result[report_name] = {
                "columns": list(df.columns),
                "data": df.head(10).values.tolist(),
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