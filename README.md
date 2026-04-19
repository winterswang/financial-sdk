# Financial SDK

统一的财务数据 SDK，封装 A股、港股、美股的财务数据接口，提供标准化的三表（资产负债表、利润表、现金流量表）+ 财务指标获取，并提供高级财务分析和实时价格功能。

## 特性

- **统一接口**: 通过门面模式提供简洁的公共 API
- **多市场支持**: A 股（AkShare）、港股/美股（Longbridge + Yahoo Finance）
- **数据标准化**: 统一的字段映射和数据格式
- **缓存机制**: LRU 缓存 + TTL 过期策略
- **监控统计**: P50/P90/P99 延迟统计、适配器健康状态
- **财务分析**: 估值、盈利、效率、成长、安全五大维度分析
- **实时价格**: 多数据源自动切换，支持自动 token 刷新

## 支持的数据

| 市场 | 股票格式 | 数据类型 |
|------|----------|----------|
| A 股 | `600000.SH`, `000001.SZ` | 资产负债表、利润表、现金流量表、财务指标 |
| 港股 | `0700.HK`, `9988.HK` | 资产负债表、利润表、现金流量表、财务指标 |
| 美股 | `AAPL`, `MSFT` | 资产负债表、利润表、现金流量表、财务指标 |

## 安装

```bash
pip install -e .
```

## CLI 命令行工具

安装后可用 `financial-sdk` 命令：

```bash
# 获取财务数据
financial-sdk get 9992.HK income_statement annual
financial-sdk get 0700.HK all quarterly --force-refresh
financial-sdk get AAPL balance_sheet annual --format json

# 财务分析
financial-sdk analyze 600000.SH                    # 完整分析报告
financial-sdk analyze 600000.SH -d valuation      # 指定维度分析
financial-sdk analyze 600000.SH --format table     # 多年对比表格
financial-sdk analyze 600000.SH --format table -y 2023,2024  # 筛选年份

# 健康检查
financial-sdk health

# 获取支持的股票
financial-sdk stocks --market HK

# 缓存统计
financial-sdk cache
```

### CLI 帮助

```bash
financial-sdk --help          # 查看所有命令
financial-sdk get --help      # 查看 get 命令帮助
financial-sdk analyze --help  # 查看 analyze 命令帮助
```

## 快速开始

```python
from financial_sdk import FinancialFacade

f = FinancialFacade()

# 获取 A 股数据
bundle = f.get_financial_data("600000.SH", "all", "annual")
print(f"市场: {bundle.market}")
print(f"货币: {bundle.currency}")
print(f"资产负债表: {bundle.balance_sheet.shape}")

# 获取港股数据
bundle = f.get_financial_data("0700.HK", "balance_sheet", "annual")

# 获取美股财务指标
bundle = f.get_financial_data("AAPL", "indicators", "annual")
print(f"指标数据: {bundle.indicators.shape}")

# 健康检查
health = f.health_check()
print(f"状态: {health.status}")

# 缓存统计
stats = f.get_cache_stats()
print(f"缓存大小: {stats['size']}")
```

## API 文档

### FinancialFacade

主入口类，提供统一的财务数据获取接口。

#### `get_financial_data(stock_code, report_type, period)`

获取财务报表数据

- `stock_code`: 股票代码
  - A 股: `600000.SH`, `000001.SZ`
  - 港股: `0700.HK`, `9988.HK`
  - 美股: `AAPL`, `MSFT`
- `report_type`: 报表类型
  - `balance_sheet`: 资产负债表
  - `income_statement`: 利润表
  - `cash_flow`: 现金流量表
  - `indicators`: 财务指标
  - `all`: 全部报表（默认）
- `period`: 报告期类型
  - `annual`: 年度报告（默认）
  - `quarterly`: 季度报告

返回 `FinancialBundle` 对象，包含标准化的 DataFrame 数据。

### FinancialBundle

标准化财务数据包

```python
bundle.stock_code      # 股票代码
bundle.market         # 市场 ("A", "HK", "US")
bundle.currency        # 货币 ("CNY", "HKD", "USD")
bundle.balance_sheet   # 资产负债表 DataFrame
bundle.income_statement  # 利润表 DataFrame
bundle.cash_flow       # 现金流量表 DataFrame
bundle.indicators      # 财务指标 DataFrame
bundle.is_partial      # 是否为部分数据
bundle.warnings        # 警告信息列表
```

### FinancialAnalytics

财务分析入口类，提供五大维度分析。

```python
from financial_sdk.analytics import FinancialAnalytics

analytics = FinancialAnalytics()

# 完整分析报告
report = analytics.get_full_report("0700.HK")

# 获取多年数据（表格格式）
multi_year = analytics.get_multi_year_metrics("0700.HK", years=[2023, 2024, 2025])

# 指定维度分析
metrics = analytics.get_valuation("0700.HK")
metrics = analytics.get_profitability("0700.HK")
metrics = analytics.get_efficiency("0700.HK")
metrics = analytics.get_growth("0700.HK")
metrics = analytics.get_safety("0700.HK")
```

**分析维度：**

| 维度 | 类 | 指标 |
|------|-----|------|
| 估值 | ValuationAnalyzer | PE、PB、PS、PEG、EV/EBITDA、市值 |
| 盈利 | ProfitabilityAnalyzer | ROE、ROA、ROIC、毛利率、净利率 |
| 效率 | EfficiencyAnalyzer | DIO、DSO、DPO、营业周期、现金周转周期 |
| 成长 | GrowthAnalyzer | YoY/QoQ增长率、可持续增长率 |
| 安全 | SafetyAnalyzer | Altman Z-Score、流动比率、偿债能力 |

### PriceProvider

实时价格获取，支持多数据源自动切换。

```python
from financial_sdk import PriceProvider, get_price_provider

provider = get_price_provider()

# 获取价格
result = provider.get_price("0700.HK")
if result.success:
    print(f"价格: {result.price.current_price} {result.price.currency}")
    print(f"来源: {result.price.source}")  # longbridge / akshare / yahoo
```

**数据源优先级：**

| 市场 | 主数据源 | 备用数据源 |
|------|----------|------------|
| A股 | AkShare | Yahoo Finance → Longbridge |
| 港股 | Longbridge | Yahoo Finance → AkShare |
| 美股 | Longbridge | Yahoo Finance |

**Longbridge Token 刷新：**
- Token 过期时自动刷新（方案C）
- 无需手动干预

## MCP Server

SDK 已发布为 MCP Server，可在 OpenClaw 中使用：

```bash
pip install mcp
openclaw mcp set financial-sdk '{"command": "python3", "args": ["/path/to/financial_sdk_mcp_server.py"]}'
```

### MCP 工具

| 工具 | 描述 | 参数 |
|------|------|------|
| `get_financial_data` | 获取股票财务报表，支持 A股/港股/美股 | `stock_code`, `report_type`, `period`, `force_refresh` |
| `get_supported_stocks` | 获取支持的股票列表 | `market` |
| `health_check` | SDK 健康状态检查 | 无 |
| `get_cache_stats` | 缓存命中率统计 | 无 |

### 使用示例

```
# 获取泡泡玛特财务数据
get_financial_data(stock_code="9992.HK", report_type="income_statement", period="annual")

# 获取腾讯健康检查
health_check()

# 获取缓存统计
get_cache_stats()
```

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
│   │   ├── profitability.py     # 盈利能力分析器
│   │   ├── efficiency.py        # 运营效率分析器
│   │   ├── growth.py            # 成长性分析器
│   │   ├── safety.py            # 财务安全分析器
│   │   └── unified.py           # 统一分析入口
│   ├── price/                  # 价格获取模块
│   │   ├── price_models.py      # 价格数据模型
│   │   └── price_provider.py    # 多数据源价格提供者
│   └── adapters/
│       ├── ashare_adapter.py   # A股适配器
│       ├── hk_adapter.py       # 港股适配器
│       └── us_adapter.py       # 美股适配器
├── src/financial_sdk_cli.py         # CLI 命令行工具
├── src/financial_sdk_mcp_server.py  # MCP Server 入口
├── tests/                      # 测试文件
├── config/                     # 配置文件
├── pyproject.toml
└── requirements.txt
```

## 依赖

- pandas >= 2.0.0
- akshare >= 1.12.0
- cachetools >= 5.0.0
- PyYAML >= 6.0
- requests >= 2.28.0
- longport >= 3.0.0 (港股/美股实时行情)
- pyjwt >= 2.0.0 (Token 解析)

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/ -x --tb=short

# 查看测试覆盖率
pytest tests/ --cov=src/financial_sdk --cov-report=html
```

### 代码质量

```bash
# Lint 检查
ruff check src/ tests/

# 自动修复 lint 问题
ruff check src/ tests/ --fix

# 格式化代码
ruff format src/ tests/
```

## 依赖

- pandas >= 2.0.0
- akshare >= 1.12.0
- cachetools >= 5.0.0
- PyYAML >= 6.0
- requests >= 2.28.0
- longport >= 3.0.0 (港股/美股实时行情)
- pyjwt >= 2.0.0 (Token 解析)

## 许可证

MIT License
