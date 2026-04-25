# Financial SDK

统一的财务数据 SDK，封装 A股、港股、美股的财务数据接口，提供标准化的三表（资产负债表、利润表、现金流量表）+ 财务指标获取，并提供高级财务分析和实时价格功能。

## 特性

- **统一接口**: 通过门面模式提供简洁的公共 API
- **多市场支持**: A股、港股、美股（统一适配器架构）
- **多数据源**: LongBridge CLI（优先）+ AkShare（备用）
- **数据标准化**: 统一的字段映射和数据格式
- **缓存机制**: LRU 缓存 + TTL 过期策略
- **监控统计**: P50/P90/P99 延迟统计、适配器健康状态
- **财务分析**: 估值、盈利、效率、成长、安全五大维度分析

## 支持的数据

| 市场 | 股票格式 | 数据类型 |
|------|----------|----------|
| A股 | `600000.SH`, `000001.SZ` | 资产负债表、利润表、现金流量表、财务指标 |
| 港股 | `0700.HK`, `9988.HK` | 资产负债表、利润表、现金流量表、财务指标 |
| 美股 | `AAPL`, `TSLA` | 资产负债表、利润表、现金流量表、财务指标 |

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

| 市场 | 优先 | 备用 |
|------|------|------|
| A股 | LongBridge CLI | AkShare |
| 港股 | LongBridge CLI | AkShare HK |
| 美股 | LongBridge CLI | AkShare US |

## 安装

### 1. 安装 Python 依赖

```bash
pip install -e .
```

### 2. (可选) 安装 LongBridge CLI

LongBridge CLI 提供更准确的港股/美股数据，建议安装：

```bash
# 安装
curl -sSL https://open.longbridge.com/install.sh | bash

# 或通过 Homebrew
brew install longbridge/longbridge-terminal/longbridge-terminal

# 认证 (首次需要)
longbridge auth login
```

安装后 SDK 会自动检测并优先使用 LongBridge CLI。

## CLI 命令行工具

### 财务分析 (推荐)

```bash
# 分析 A股
python -m src.financial_sdk_cli analyze 600000.SH --format table
python -m src.financial_sdk_cli analyze 600000.SH --format table -y 2023,2024,2025

# 分析港股
python -m src.financial_sdk_cli analyze 0700.HK --format table
python -m src.financial_sdk_cli analyze 9988.HK --format table -y 2024,2025

# 分析美股
python -m src.financial_sdk_cli analyze AAPL --format table
python -m src.financial_sdk_cli analyze TSLA --format table -y 2024,2025
```

### 获取财务报表

```bash
# 获取利润表
python -m src.financial_sdk_cli get 0700.HK income_statement annual
python -m src.financial_sdk_cli get 9988.HK income_statement annual --format json

# 获取资产负债表
python -m src.financial_sdk_cli get 600000.SH balance_sheet annual

# 获取所有报表
python -m src.financial_sdk_cli get AAPL all quarterly
```

### 系统命令

```bash
# 健康检查
python -m src.financial_sdk_cli health

# 获取支持的股票列表
python -m src.financial_sdk_cli stocks --market HK
python -m src.financial_sdk_cli stocks --market US

# 缓存统计
python -m src.financial_sdk_cli cache
```

### CLI 帮助

```bash
python -m src.financial_sdk_cli --help          # 查看所有命令
python -m src.financial_sdk_cli get --help      # 查看 get 命令帮助
python -m src.financial_sdk_cli analyze --help  # 查看 analyze 命令帮助
```

## Python API 使用

### 基础用法

```python
from financial_sdk import FinancialFacade

f = FinancialFacade()

# 获取 A 股数据
bundle = f.get_financial_data("600000.SH", "all", "annual")
print(f"市场: {bundle.market}")
print(f"货币: {bundle.currency}")
print(f"资产负债表: {bundle.balance_sheet.shape}")

# 获取港股数据
bundle = f.get_financial_data("0700.HK", "all", "annual")
print(f"利润表: {bundle.income_statement.shape}")

# 获取美股财务指标
bundle = f.get_financial_data("AAPL", "indicators", "annual")
print(f"指标数据: {bundle.indicators.shape}")
```

### 获取特定报表

```python
# 获取单一报表
income = f.get_financial_data("0700.HK", "income_statement", "annual")
balance = f.get_financial_data("9988.HK", "balance_sheet", "annual")
cash_flow = f.get_financial_data("AAPL", "cash_flow", "annual")

# 强制刷新 (跳过缓存)
bundle = f.get_financial_data("0700.HK", "all", "annual", force_refresh=True)
```

### 财务分析

```python
from financial_sdk.analytics import FinancialAnalytics

analytics = FinancialAnalytics()

# 完整分析报告
report = analytics.get_full_report("0700.HK")

# 获取多年数据（表格格式）
multi_year = analytics.get_multi_year_metrics("0700.HK", years=[2023, 2024, 2025])

# 指定维度分析
metrics = analytics.get_valuation("0700.HK")       # 估值指标
metrics = analytics.get_profitability("0700.HK")   # 盈利能力
metrics = analytics.get_efficiency("0700.HK")       # 运营效率
metrics = analytics.get_growth("0700.HK")           # 成长性
metrics = analytics.get_safety("0700.HK")          # 财务安全
```

### 健康检查与缓存

```python
# 健康检查
health = f.health_check()
print(f"状态: {health.status}")
for adapter_name, status in health.adapters.items():
    print(f"  {adapter_name}: {status}")

# 缓存统计
stats = f.get_cache_stats()
print(f"缓存大小: {stats['size']}")
print(f"命中率: {stats['hit_rate']}")
```

## API 文档

### FinancialFacade

主入口类，提供统一的财务数据获取接口。

#### `get_financial_data(stock_code, report_type, period, force_refresh)`

获取财务报表数据

- `stock_code`: 股票代码
  - A股: `600000.SH`, `000001.SZ`
  - 港股: `0700.HK`, `9988.HK`
  - 美股: `AAPL`, `TSLA`
- `report_type`: 报表类型
  - `balance_sheet`: 资产负债表
  - `income_statement`: 利润表
  - `cash_flow`: 现金流量表
  - `indicators`: 财务指标
  - `all`: 全部报表（默认）
- `period`: 报告期类型
  - `annual`: 年度报告（默认）
  - `quarterly`: 季度报告
- `force_refresh`: 是否跳过缓存强制刷新

返回 `FinancialBundle` 对象。

### FinancialBundle

标准化财务数据包

```python
bundle.stock_code       # 股票代码
bundle.market          # 市场 ("A", "HK", "US")
bundle.currency         # 货币 ("CNY", "HKD", "USD")
bundle.balance_sheet   # 资产负债表 DataFrame
bundle.income_statement # 利润表 DataFrame
bundle.cash_flow       # 现金流量表 DataFrame
bundle.indicators      # 财务指标 DataFrame
bundle.is_partial      # 是否为部分数据
bundle.warnings        # 警告信息列表
```

### 分析维度

| 维度 | 方法 | 指标 |
|------|------|------|
| 估值 | `get_valuation()` | PE、PB、PS、PEG、EV/EBITDA、市值 |
| 盈利 | `get_profitability()` | ROE、ROA、ROIC，毛利率、净利率 |
| 效率 | `get_efficiency()` | DIO、DSO、DPO、营业周期、现金周转周期 |
| 成长 | `get_growth()` | YoY/QoQ增长率、可持续增长率 |
| 安全 | `get_safety()` | Altman Z-Score、流动比率、偿债能力 |

## 项目结构

```
financial-sdk/
├── src/financial_sdk/
│   ├── __init__.py              # 包入口
│   ├── facade.py                # 门面模式统一入口
│   ├── adapter_manager.py       # 适配器管理器
│   ├── base_adapter.py          # 适配器抽象基类
│   ├── models.py               # FinancialBundle 等数据模型
│   ├── cache.py                # LRU 缓存（支持 TTL）
│   ├── monitor.py              # 监控（P50/P90/P99 统计）
│   ├── config.py               # 配置管理
│   ├── exceptions.py           # 异常类定义
│   ├── analytics/              # 财务分析模块
│   │   ├── analytics_base.py   # 分析器基类
│   │   ├── metrics_calculator.py # 指标计算引擎
│   │   ├── valuation.py        # 估值分析器
│   │   ├── profitability.py    # 盈利能力分析器
│   │   ├── efficiency.py       # 运营效率分析器
│   │   ├── growth.py           # 成长性分析器
│   │   ├── safety.py           # 财务安全分析器
│   │   └── unified.py          # 统一分析入口
│   ├── price/                  # 价格获取模块
│   │   ├── price_models.py     # 价格数据模型
│   │   └── price_provider.py   # 多数据源价格提供者
│   └── adapters/
│       ├── ashare_adapter.py   # A股适配器 (AkShare)
│       ├── hk_adapter.py       # 港股适配器 (AkShare)
│       ├── us_adapter.py        # 美股适配器 (AkShare)
│       └── longbridge_cli_adapter.py  # LongBridge CLI 适配器
├── src/financial_sdk_cli.py         # CLI 命令行工具
├── src/financial_sdk_mcp_server.py # MCP Server 入口
├── tests/                      # 测试文件
├── config/                     # 配置文件
├── pyproject.toml
└── README.md
```

## 依赖

- pandas >= 2.0.0
- akshare >= 1.12.0
- cachetools >= 5.0.0
- PyYAML >= 6.0
- requests >= 2.28.0
- longbridge >= 3.0.0 (可选，用于港股/美股实时行情)
- pyjwt >= 2.0.0 (Token 解析)

## 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/ -x --tb=short

# 查看测试覆盖率
pytest tests/ --cov=src/financial_sdk --cov-report=html
```

## 代码质量

```bash
# Lint 检查
ruff check src/ tests/

# 自动修复 lint 问题
ruff check src/ tests/ --fix

# 格式化代码
ruff format src/ tests/
```

## 常见问题

### Q: 为什么港股代码前面有 0？

港股代码支持两种格式：
- `0700.HK` (标准格式)
- `700.HK` (简化格式，SDK 会自动处理)

### Q: LongBridge CLI 安装后不生效？

```bash
# 检查是否安装
longbridge --version

# 检查认证状态
longbridge auth status

# 重新认证
longbridge auth login
```

### Q: 如何强制使用特定数据源？

目前 SDK 会自动选择最优数据源，不支持手动指定。

## 许可证

MIT License
