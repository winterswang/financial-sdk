# Financial SDK

统一的财务数据 SDK，封装 A股、港股、美股的财务数据接口，提供标准化的三表（资产负债表、利润表、现金流量表）+ 财务指标获取。

## 特性

- **统一接口**: 通过门面模式提供简洁的公共 API
- **多市场支持**: A 股（AkShare）、港股（AkShare）、美股（AkShare）
- **数据标准化**: 统一的字段映射和数据格式
- **缓存机制**: LRU 缓存 + TTL 过期策略
- **监控统计**: P50/P90/P99 延迟统计、适配器健康状态

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

## 开发

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

## 许可证

MIT License
