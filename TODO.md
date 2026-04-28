# Financial SDK TODO

基于实际使用（分析泡泡玛特 9992.HK）发现的问题和改进方向。

---

## 🔴 P0 - 数据完整性（影响核心功能）

### 1. 资产负债表字段未标准化
- **问题**: Balance Sheet 的列名混用中英文，部分字段带 `(HKD)` 后缀
  - 当前: `净债务(HKD)`, `固定资产净值(HKD)及占比`, `存货(HKD)及占比`, `应收(HKD)及占比`, `每股净资产(HKD)`, `现金及短期投资(HKD)及占比`, `长期投资(HKD)及占比`
  - 期望: `net_debt`, `fixed_assets`, `inventory`, `accounts_receivable`, `bvps`, `cash_and_equivalents`, `long_term_investments`
- **影响**: 下游分析器（Profitability/Efficiency/Safety）依赖这些标准字段名，找不到就直接返回 None

### 2. 利润表缺少 gross_profit 字段
- **问题**: income_statement 有 `gross_margin`(百分比) 但没有 `gross_profit`(绝对值)
- **影响**: ProfitabilityAnalyzer 的 `gross_margin` 返回 None，因为计算公式是 `gross_profit / revenue`，找不到 gross_profit
- **修复方案**: 适配器层应该从 `revenue * gross_margin%` 反推 gross_profit，或从 LongBridge 原始数据中提取

### 3. 资产负债表缺少 total_equity / current_assets / current_liabilities
- **问题**: LongBridge 适配器只映射了 `total_assets` 和 `total_liabilities`，缺少:
  - `total_equity` — 可从 total_assets - total_liabilities 计算
  - `current_assets` / `current_liabilities` — 流动/非流动资产分类
  - `accounts_receivable`, `inventory` 的标准英文名
- **影响**:
  - ROE 计算失败（需要 total_equity 做分母）
  - EfficiencyAnalyzer 全部返回 None（需要 inventory、receivable、payable）
  - SafetyAnalyzer 的 current_ratio / quick_ratio / Altman Z-Score 全部 None

### 4. FinancialAnalytics.get_full_report() 静默返回 None
- **问题**: 当内部任何一个分析器抛异常时，整个方法返回 None 而不报错
- **影响**: 用户调用 `analyze 9992.HK` 时，CLI 只能输出部分数据，无法知道是哪些分析器失败了
- **修复方案**: 至少 log 异常信息，或改为返回部分成功的 report

---

## 🟡 P1 - 分析能力增强

### 5. 指标数值类型不一致
- **问题**: indicators DataFrame 中 pe_ratio / pb_ratio / market_cap 等字段是字符串类型，而非 float
- **影响**: 格式化输出时报错 `ValueError: Unknown format code 'f' for object of type 'str'`
- **修复**: 适配器层应做类型转换 `pd.to_numeric()`

### 6. 港股分析维度严重缺失
- **问题**: `analyze 9992.HK` 输出中，估值/效率/成长/安全4个维度全部为空
- **根因**: 
  - 估值: 价格获取失败（需检查 PriceProvider 对港股的支持）
  - 效率: 缺 inventory / receivable / payable 标准字段
  - 成长: 需要多年数据做 YoY 计算，可能数据不够或计算逻辑有 bug
  - 安全: 缺 current_assets / current_liabilities / interest_expense

### 7. GrowthAnalyzer 需要多期数据
- **问题**: 当前 get_growth_metrics 似乎需要至少2期数据做 YoY 计算，但逻辑可能有 bug
- **验证**: 单独测试 `analytics.get_growth('9992.HK')` 返回什么

### 8. 增加 ROE 的 DuPont 分解自动计算
- **问题**: 当前 DuPont 分解依赖 `dupont_net_margin` / `dupont_asset_turnover` / `dupont_equity_multiplier`，但这些字段也需要 total_equity 等基础数据
- **修复**: 先解决 P0 的字段缺失问题

---

## 🟢 P2 - 体验优化

### 9. CLI analyze 输出改进
- 当某个维度数据不可用时，显示原因而非空白
  - 当前: `【运营效率 Efficiency】` （空白）
  - 期望: `【运营效率 Efficiency】⚠️ 数据不可用：缺少 inventory/accounts_receivable 标准字段`

### 10. 增加 `compare` 子命令
- 用法: `financial-sdk compare 0700.HK 9992.HK 3690.HK`
- 输出: 多股并列对比表格，方便横向比较
- 优先对比: 营收、净利润、毛利率、净利率、ROE、PE、PB

### 11. 增加 `screen` 子命令（选股筛选）
- 用法: `financial-sdk screen --market HK --min-roe 15 --max-pe 30 --min-growth 20`
- 基于预置的股票列表批量获取并筛选

### 12. 输出格式增强
- `--format markdown`: 输出 Markdown 表格，方便复制到笔记/文档
- `--format csv`: CSV 输出，方便导入 Excel

### 13. 缓存粒度优化
- 当前缓存 key 是 `market:stock:report_type:period`
- 建议: annual 数据缓存 24h，quarterly 缓存 4h，价格数据缓存 5min
- 增加 `cache clear --stock 9992.HK` 单只股票缓存清除

---

## 🔵 P3 - 架构改进

### 14. LongBridge 适配器字段映射完善
- 当前 FIELD_MAPPING 覆盖不完整，大量字段保留中文原名
- 建议: 
  - 补全所有中文字段到英文标准字段的映射
  - 对带货币后缀的字段 `(HKD)` `(USD)` `(CNY)` 做统一处理
  - 对带"及占比"后缀的字段拆分为绝对值和占比两个标准字段

### 15. 适配器层数据自愈
- 当标准字段缺失时，自动从已有数据推算:
  - `total_equity = total_assets - total_liabilities`
  - `gross_profit = revenue * gross_margin / 100`
  - `debt_to_equity = total_liabilities / total_equity`
- 在 bundle.warnings 中记录哪些字段是推算的

### 16. MCP Server 增强
- 增加 `analyze` tool，暴露分析能力
- 增加 `diagnose` tool，暴露诊断能力
- 当前 MCP 只有 get_financial_data / get_supported_stocks / health_check / get_cache_stats

### 17. 单元测试补充
- tests/ 中缺少对港股/美股适配器的集成测试
- 缺少对 FinancialAnalytics 的端到端测试
- 建议增加 fixture 数据，避免测试依赖网络

---

## 📋 优先级排序

| 优先级 | 编号 | 预估工作量 |
|--------|------|-----------|
| P0 | #1 资产负债表字段标准化 | 中 |
| P0 | #2 补充 gross_profit 字段 | 小 |
| P0 | #3 补充 total_equity 等 | 小 |
| P0 | #4 full_report 异常处理 | 小 |
| P1 | #5 指标数值类型转换 | 小 |
| P1 | #6 港股分析维度修复 | 中(依赖P0) |
| P1 | #7 GrowthAnalyzer 修复 | 小 |
| P2 | #9 CLI 输出改进 | 小 |
| P2 | #10 compare 子命令 | 中 |
| P2 | #14 LongBridge 映射完善 | 大 |

**建议先解决 P0 的 #1-#4**，这4个问题修复后，港股的 analyze 功能就能完整输出5个维度了。
