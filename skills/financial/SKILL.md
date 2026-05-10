---
name: financial-sdk
description: 统一财务数据SDK，支持A股/港股/美股的财务报表获取、分析与报告生成。
metadata:
  { "openclaw": { "emoji": "📊", "requires": { "mcp": "financial-sdk" } } }
---

# Financial SDK

统一的财务数据 SDK，封装 A股、港股、美股的财务数据接口，提供标准化的三表（资产负债表、利润表、现金流量表）+ 财务指标获取，并支持高级财务分析和报告生成。

## 触发条件

用户意图是**分析/查看/比较财务数据、财务指标、生成财务报告**时使用本 skill。
关键词：分析、查看、对比、财务、指标、三表、估值、盈利、ROE、PE、报告、report 等。

> ⚠️ 如果用户说"下载报告/年报/季报/招股书/PDF"，走 unified-downloader skill，不走本 skill。

## ⚠️ 分析报告完整性约束（强制）

**问题根因**：AI 凭记忆选择性使用数据+手算错误，导致数据年份跳漏、符号颠倒等错误。

**强制流程**：
```
原始数据（API） → Python完整计算 → 打印全部数据 → 直接填入模板
```

**禁止行为**：
- ❌ 跳过年份（哪怕是"数值平淡"的年份）
- ❌ 在脑子里边算边写，凭记忆选择展示哪些年份
- ❌ 用原始字段直接手算而不程序化验证（如 NetCash 符号、FCF 公式）
- ❌ 用部分数据代替完整10年数据做判断

**必须动作**：
1. 拉取完整10年原始数据，先 Python 完整打印全部计算结果
2. 所有衍生指标（ROE、ROIC、FCF、净现金、周转率）必须用程序计算并输出到表格
3. 输出必须有"附录：完整X年数据总表"，每一行都要有数据，不得跳过任何年份
4. 只有在 API 原生字段就为 NaN 的情况下，才可以标"—"（说明数据源本身缺失）

**NetCash/净现金计算规则**：NetCash = Cash - STDebt - LTDebt（不是直接用 NetDebt 字段），零负债时 NetCash = Cash（为正直）

**FCF计算规则**：直接使用 API 提供的 `自由现金流(USD)` 字段，或用 OCF + Capex（CapEx为负数）计算，禁止用其他公式

---

## 数据市场

| 市场 | 股票代码格式 | 示例 |
|------|-------------|------|
| A 股 | `XXXXXX.SH` / `XXXXXX.SZ` | `600000.SH`, `000001.SZ`, `600036.SH` |
| 港股 | `XXXX.HK`（支持 0 前缀或标准格式） | `0700.HK` (腾讯), `9988.HK` (阿里) |
| 美股 | `AAPL` 或 `AAPL.US` | `AAPL`, `TSLA`, `NVDA` |

---

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

### get_supported_stocks

获取 SDK 内置支持的股票列表（用于快速验证股票代码格式）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `market` | string | 否 | 市场筛选: `A`(A股)、`HK`(港股)、`US`(美股)、`all`(全部，默认) |

### health_check

健康检查，返回各数据适配器和缓存的状态。

### get_cache_stats

获取缓存统计信息，包括缓存大小、命中率等。

---

## CLI 用法（直接执行）

项目路径: `/root/.openclaw/workspace/financial-sdk`

```bash
# 财务分析（推荐入口）
cd /root/.openclaw/workspace/financial-sdk
python3 -m src.financial_sdk_cli analyze <股票代码> --format table
python3 -m src.financial_sdk_cli analyze <股票代码> --format table -y 2023,2024,2025

# 获取原始报表
python3 -m src.financial_sdk_cli get <股票代码> <报表类型> <周期>
# 报表类型: income_statement, balance_sheet, cash_flow, indicators, all
# 周期: annual, quarterly

# 系统命令
python3 -m src.financial_sdk_cli health     # 健康检查
python3 -m src.financial_sdk_cli stocks --market HK  # 支持的股票列表
python3 -m src.financial_sdk_cli cache      # 缓存统计
```

---

## 分析维度

1. **估值 Valuation** — PE、PB、PS、市值等
2. **盈利 Profitability** — 毛利率、净利率、ROE、ROA、ROIC 等
3. **运营效率 Efficiency** — 存货周转(DIO)、应收周转(DSO)、应付周转(DPO)、现金周转周期(CCC)
4. **成长性 Growth** — 营收YoY、净利YoY、CAGR 等
5. **财务安全 Safety** — 流动比率、速动比率、Altman Z-Score、债务/权益比

---

## Python API

```python
from financial_sdk import FinancialFacade
from financial_sdk.analytics import FinancialAnalytics

f = FinancialFacade()
analytics = FinancialAnalytics()

# 获取数据
bundle = f.get_financial_data("0700.HK", "all", "annual")

# 完整分析报告
report = analytics.get_full_report("0700.HK")

# 多年数据对比
multi_year = analytics.get_multi_year_metrics("0700.HK", years=[2023, 2024, 2025])

# 指定维度
metrics = analytics.get_valuation("0700.HK")
metrics = analytics.get_profitability("0700.HK")
metrics = analytics.get_efficiency("0700.HK")
metrics = analytics.get_growth("0700.HK")
metrics = analytics.get_safety("0700.HK")
```

---

## 报告生成（必须遵循模板）

当用户要求**生成财务分析报告**（关键词：报告、report、分析报告）时，必须遵循报告模板。

### 模板位置

`/root/.openclaw/workspace/openclaw-workspace/skills/financial-sdk/report_template.md`

### 使用流程

1. **读模板**：读取 `report_template.md`
2. **拉数据**：用 Python API 获取三表（balance_sheet, income_statement, cash_flow）
3. **算指标**：用 FinancialAnalytics 算五维度，同时自行计算模板要求的衍生指标：
   - ROE DuPont 三因子拆解（净利率 × 资产周转 × 权益乘数）
   - ROIC = operating_profit / (total_equity + 有息负债)
   - 增量资本回报率 = Δ净利润 / Δ投入资本
   - FCF = OCF + CapEx（CapEx为负）
   - Owner Earnings = 净利润 + D&A - CapEx（简化版）
   - 股份数 = 净利润 / EPS（反算），稀释率 = (稀释EPS股数-基本EPS股数)/基本EPS股数
   - 资本配置：分红/OCF、回购/OCF、CapEx/OCF
   - CapEx/营收、R&D/营收、销售费用/营收
   - 稳定性：CV = 标准差/均值
4. **按模板输出**：严格按模板8个章节顺序，每个表格、判断规则都必须遵守
5. **变化优先**：禁止纯静态描述，每条必须有变化方向+幅度+时间跨度

### 模板核心理念

- **看变化，看稳定**：禁止纯静态描述，每条必须有变化方向+幅度+时间跨度
- **稳定性量化**：用 CV 评级（⭐1-5星）
- **阶段划分**：自动识别转折点，划分阶段
- **驱动拆解**：ROE拆三因子、CCC拆三因子、增量资本回报
- **股东视角**：FCF/Owner Earnings 比会计利润更真实

---

## 关键字段说明

### 资产负债表 (balance_sheet)

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

### 利润表 (income_statement)

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `revenue` | 营业收入 |
| `gross_profit` | 毛利 |
| `gross_margin` | 毛利率 |
| `operating_profit` | 营业利润 |
| `net_profit` | 净利润 |
| `net_margin` | 净利率 |
| `eps` | 每股收益 |

### 现金流量表 (cash_flow)

| 字段 | 说明 |
|------|------|
| `report_date` | 报告期 |
| `operating_cash_flow` | 经营活动现金流 |
| `capex` | 资本支出（负数） |
| `investing_cash_flow` | 投资活动现金流 |
| `financing_cash_flow` | 筹资活动现金流 |

### 财务指标 (indicators)

| 字段 | 说明 |
|------|------|
| `roe` | 净资产收益率 |
| `roa` | 总资产收益率 |
| `pe_ratio` | 市盈率 |
| `pb_ratio` | 市净率 |

---

## 已知限制 (TODO)

- 港股分析维度数据缺失较严重（字段未标准化，缺 total_equity/current_assets 等）
- indicators 中部分字段类型为字符串而非 float
- 单期数据无法计算 YoY 成长指标
- Efficiency/Safety 分析器对港股基本返回 None
- 估值指标需要 EPS/价格数据，当前可能缺失

---

## 数据源架构

```
┌─────────────────────────────────────────────────────────────┐
│                    FinancialFacade                           │
│                  (统一入口，自动路由)                          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ LongBridgeCLI │   │  AkShare A股  │   │  AkShare HK   │
│  Adapter      │   │   Adapter     │   │   Adapter     │
│  (优先)       │   │   (备用)       │   │   (备用)       │
└───────────────┘   └───────────────┘   └───────────────┘
```

**适配器优先级**：
- A股：LongBridge CLI（优先）→ AkShare（备用）
- 港股：LongBridge CLI（优先）→ AkShare HK（备用）
- 美股：LongBridge CLI（优先）→ AkShare US（备用）