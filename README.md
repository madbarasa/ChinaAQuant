# 中国A股市场量化分析项目

## 📋 项目概述

本项目基于2015-2024年中国A股市场数据，完成了两大核心量化分析：

1. **因子投资分析**：构建并回测Past Performance、MAX、Volatility三个因子的多空组合策略
2. **事件研究**：分析红利分配公告对股票异常收益的影响

## 🗂️ 文件结构

```
madbarasa/
├── 数据库文件/
│   ├── Appendix1.db                    # 沪深300成分股
│   ├── Appendix2.db                    # 中证500成分股
│   ├── Appendix3.db                    # 分红预案数据
│   ├── CD_CompOfDivProfitInd.db       # 行业分红比例
│   ├── STK_LISTEDCOINFOANL.db         # 公司行业代码
│   └── price_data/
│       ├── TRD_Dalyr.db ~ TRD_Dalyr9.db  # 日度交易数据
│
├── 分析代码/
│   ├── complete_analysis.py            # ⭐ 完整分析主程序（推荐）
│   ├── factor_analysis.py              # 因子投资详细分析
│   └── event_study.py                  # 事件研究详细分析
│
├── 结果文件/
│   ├── factor_analysis_results.png     # 因子策略累计收益率图
│   ├── event_study_results.png         # AAR和CAAR图表
│   ├── 分析报告.md                     # 详细分析报告（模板）
│   ├── 分析结果总结.md                 # ⭐ 完整结果总结
│   └── README.md                       # 本文件
```

## 🚀 快速开始

### 环境要求

- Python 3.7+
- 必需库：pandas, numpy, matplotlib, scipy

### 安装依赖

```bash
pip install pandas numpy matplotlib scipy
```

### 运行分析

#### 方式1：运行完整分析（推荐）

```bash
python complete_analysis.py
```

这将自动完成：
- ✅ 加载所有数据
- ✅ 计算三个因子
- ✅ 回测多空组合策略
- ✅ 分析事件驱动收益
- ✅ 生成图表和统计结果

**预计运行时间**：3-5分钟

#### 方式2：分别运行

```bash
# 仅运行因子分析
python factor_analysis.py

# 仅运行事件研究
python event_study.py
```

## 📊 主要结果

### 因子投资分析

| 因子 | 年化收益率 | 年化波动率 | 夏普比率 |
|------|-----------|-----------|---------|
| Past Performance | -45.73% | 43.53% | -1.44 |
| MAX | -21.73% | 38.05% | -0.72 |
| Volatility | -0.77% | 8.36% | -0.45 |

**关键发现**：
- 中国市场存在显著的**反转效应**
- 追涨策略（动量）在A股失效
- 建议采用**反向策略**

### 事件研究

**利好事件**（行业低分红率下公司分红）：
- T+0日AAR: 0.14%（不显著）
- T+10日CAAR: -0.29%

**利空事件**（行业高分红率下公司不分红）：
- T+0日AAR: 0.18%（异常：利空反涨）
- T+10日CAAR: -2.23%

**关键发现**：
- 信息提前泄露严重
- 公告日反应与基本面背离
- 短期事件驱动效应不明显

## 📈 查看结果

### 图表文件

1. **factor_analysis_results.png** - 展示三个因子的累计收益率曲线
2. **event_study_results.png** - 展示利好和利空事件的AAR/CAAR图表

### 报告文件

1. **分析结果总结.md** - ⭐ 包含完整的分析结果和投资建议
2. **分析报告.md** - 详细的方法论和理论框架

## 🔧 自定义分析

### 修改参数

在 `complete_analysis.py` 中可以调整：

```python
# 因子计算参数
past_perf_period = 63  # Past Performance周期（默认3个月）
max_window = 20        # MAX因子窗口（默认20天）
vol_window = 20        # Volatility窗口（默认20天）

# 事件研究参数
event_window = (-10, 10)       # 事件窗口
estimation_window = (-100, -11) # 估计窗口

# 组合构建参数
n_quintiles = 5        # 分组数量（默认5组）
rebalance_freq = 'M'   # 调仓频率（M=月度）
```

### 扩展分析

可以添加：
- 新的因子定义
- 不同的事件类型
- 更多的绩效指标
- 子样本分析（按年份、行业、市值）

## 📚 数据说明

### 核心数据表

| 数据库 | 表名 | 主要字段 | 用途 |
|-------|------|---------|------|
| TRD_Dalyr*.db | TRD_Dalyr | Stkcd, Trddt, Clsprc, Dsmvosd | 日度价格和流通市值 |
| Appendix3.db | Appendix3 | Stkcd, Finyear, Ppdadt, Ppcont | 分红预案公告 |
| CD_CompOfDivProfitInd.db | CD_CompOfDivProfitInd | IndustryCode, DivdendToProfitableRate | 行业分红比例 |

### 数据时间范围

- 价格数据：2015-01-01 至 2024-12-31
- 分红数据：2015年 至 2024年
- 总记录数：约940万条

## 💡 投资建议

基于分析结果，我们提出以下建议：

### ✅ 推荐策略

1. **反向因子策略**
   - 做空高Past Performance股票
   - 规避高MAX值股票
   - 定期再平衡

2. **基本面价值策略**
   - 关注被市场忽视的价值股
   - 重视持续分红能力
   - 长期持有优质股票

3. **风险控制优先**
   - 避免追涨杀跌
   - 分散投资
   - 设置止损纪律

### ❌ 不推荐策略

1. ~~追涨策略~~ - 动量因子失效
2. ~~极端收益追逐~~ - MAX因子负向
3. ~~短期事件套利~~ - 效应不显著

## 🔍 技术细节

### 因子计算方法

```python
# Past Performance: 3个月持有期收益率
PastPerf = (Price_t / Price_{t-63}) - 1

# MAX: 20日最高日收益率
MAX = max(Return_{t-20}, ..., Return_t)

# Volatility: 20日收益率标准差
Volatility = std(Return_{t-20}, ..., Return_t)
```

### 多空组合构建

1. 每月末按因子值分成5组（quintiles）
2. 下月初：做多Q5（最高组），做空Q1（最低组）
3. 持有一个月，月末再平衡

### 异常收益计算

```python
# 估计期望收益（估计窗口平均）
E(R_i) = mean(R_{t-100}, ..., R_{t-11})

# 异常收益
AR_{i,t} = R_{i,t} - E(R_i)

# 平均异常收益
AAR_t = mean(AR_{1,t}, ..., AR_{N,t})

# 累积平均异常收益
CAAR_t = sum(AAR_{-10}, ..., AAR_t)
```

## 📞 常见问题

### Q: 为什么因子收益是负的？

A: 这反映了中国市场的特殊性：
- 投资者追涨杀跌行为严重
- 市场存在显著反转效应
- 传统因子需要反向操作

### Q: 事件研究为什么不显著？

A: 可能原因：
- 信息提前泄露
- 市场对分红政策不敏感
- 样本中包含多种情况，平均效应被削弱

### Q: 如何提高策略收益？

A: 建议：
- 结合多个因子（多因子模型）
- 加入基本面筛选
- 考虑交易成本和流动性
- 动态调整因子权重

### Q: 数据可以更新吗？

A: 可以，只需：
1. 用新数据替换对应的.db文件
2. 保持表结构不变
3. 重新运行分析脚本

## 📖 参考文献

1. Fama & French (1993) - 因子投资理论
2. Jegadeesh & Titman (1993) - 动量效应
3. Bali et al. (2011) - MAX因子
4. MacKinlay (1997) - 事件研究方法论

## 📝 更新日志

- **2024-12-07**: 初始版本发布
  - 完成因子投资分析
  - 完成事件研究分析
  - 生成分析报告和图表

## 📄 许可

本项目仅供学术研究使用。

## ⚠️ 免责声明

本分析结果仅供参考，不构成投资建议。
投资有风险，入市需谨慎。
过往业绩不代表未来表现。

---

**项目完成时间**: 2025年12月7日  
**联系方式**: 请通过GitHub Issues反馈问题

