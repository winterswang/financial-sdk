---
name: financial-sdk
description: 统一的财务数据SDK，支持A股、港股、美股的财务报表和财务指标查询。
metadata:
  { "openclaw": { "emoji": "📊", "requires": { "mcp": "financial-sdk" } } }
---

# Financial SDK

统一的财务数据 SDK，封装 A股、港股、美股的财务数据接口，提供标准化的三表（资产负债表、利润表、现金流量表）+ 财务指标获取。

## 数据市场

| 市场 | 股票代码格式 | 示例 |
|------|-------------|------|
| A 股 | `XXXXXX.SH` / `XXXXXX.SZ` | `600000.SH`, `000001.SZ`, `600036.SH` |
| 港股 | `XXXX.HK` | `0700.HK` (腾讯), `9988.HK` (阿里), `0941.HK` |
| 美股 | `AAPL` / `MSFT` | `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `TSLA` |

## 工具

### get_financial_data

获取股票财务报表数据（资产负债表、利润表、现金流量表、财务指标）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `stock_code` | string | 是 | 股票代码，如 `600000.SH`、`0700.HK`、`AAPL` |
| `report_type` | string | 否 | 报表类型: `balance_sheet`、`income_statement`、`cash_flow`、`indicators`、`all`（默认） |
| `period` | string | 否 | 报告期: `annual`（年度，默认）、`quarterly`（季度） |
| `force_refresh` | boolean | 否 | 是否强制刷新缓存（默认 false） |

**返回数据结构:**

```json
{
  "stock_code": "600000.SH",
  "stock_name": "",
  "market": "A",
  "currency": "CNY",
  "is_partial": false,
  "warnings": [],
  "report_periods": ["2023-12-31", "2022-12-31"],
  "available_reports": ["balance_sheet", "income_statement", "cash_flow", "indicators"],
  "balance_sheet": { "columns": [...], "data": [[...]], "row_count": 5 },
  "income_statement": { "columns": [...], "data": [[...]], "row_count": 5 },
  "cash_flow": { "columns": [...], "data": [[...]], "row_count": 5 },
  "indicators": { "columns": [...], "data": [[...]], "row_count": 5 }
}
```

**使用示例:**

```
获取A股浦发银行的完整财务数据:
get_financial_data(stock_code="600000.SH", report_type="all", period="annual")

获取美股苹果的利润表:
get_financial_data(stock_code="AAPL", report_type="income_statement", period="annual")

获取港股腾讯的财务指标:
get_financial_data(stock_code="0700.HK", report_type="indicators", period="quarterly")
```

### get_supported_stocks

获取 SDK 内置支持的股票列表（用于快速验证股票代码格式）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `market` | string | 否 | 市场筛选: `A`(A股)、`HK`(港股)、`US`(美股)、`all`(全部，默认) |

### health_check

健康检查，返回各数据适配器（AkShare A股/港股/美股）和缓存的状态。

### get_cache_stats

获取缓存统计信息，包括缓存大小、命中率等。

## 财务指标说明

### 资产负债表 (balance_sheet) 关键字段

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `total_assets` | 总资产 |
| `total_liabilities` | 总负债 |
| `total_equity` | 股东权益 |
| `current_assets` | 流动资产 |
| `non_current_assets` | 非流动资产 |
| `accounts_receivable` | 应收账款 |
| `inventory` | 存货 |

### 利润表 (income_statement) 关键字段

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `revenue` | 营业收入 |
| `gross_profit` | 毛利 |
| `operating_profit` | 营业利润 |
| `net_profit` | 净利润 |
| `eps` | 每股收益 |

### 现金流量表 (cash_flow) 关键字段

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `operating_cash_flow` | 经营活动现金流 |
| `investing_cash_flow` | 投资活动现金流 |
| `financing_cash_flow` | 筹资活动现金流 |
| `net_cash_flow` | 净现金流 |

### 财务指标 (indicators) 关键字段

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `roe` | 净资产收益率 |
| `roa` | 总资产收益率 |
| `gross_margin` | 毛利率 |
| `net_margin` | 净利率 |
| `pe_ratio` | 市盈率 |
| `pb_ratio` | 市净率 |
| `eps` | 每股收益 |
| `bvps` | 每股净资产 |

## 使用场景

1. **基本面分析**: 获取多市场股票的财务报表，计算盈利能力、负债水平
2. **财务对比**: 对比同行业不同公司的关键财务指标
3. **趋势分析**: 查询多年季度/年度数据，分析财务趋势
4. **价值投资**: 结合 PE、PB、ROE 等指标筛选被低估的股票

## 注意事项

- A股数据来源于 AkShare，港股和美股同样通过 AkShare 获取
- 数据会有一定延迟，不适合实时交易场景
- 建议启用缓存（默认启用）以减少 API 调用
- 部分股票可能缺少某些报表数据，返回的 `warnings` 字段会提示
