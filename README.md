# 📈 ChinaAQuant: 中国A股市场量化分析系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.7%2B-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Version-1.1.0-orange.svg" alt="Version">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  <img src="https://img.shields.io/badge/Code%20Style-PEP8-black.svg" alt="Code Style">
</p>

## 🌟 项目简介

**ChinaAQuant** 是一个专门针对中国A股市场设计的轻量化分析框架。本项目基于 2015-2024 年的海量历史数据（约 940 万条记录），深入探讨了因子投资的有效性以及重大财务事件对市场收益的影响。

本项目旨在为量化爱好者和研究人员提供一个“开箱即用”的工具集，通过简洁的代码实现复杂的因子回测和事件研究。

---

## ✨ 核心特性

- **多维度因子回测**：支持 `Past Performance` (动量/反转)、`MAX` (极端收益) 以及 `Volatility` (波动率) 三大核心因子的多空组合回测。
- **事件驱动研究**：自动化分析红利分配公告（Dividend Announcements）对股票异常收益（AR/CAAR）的影响，揭示信息泄露与市场反应规律。
- **高性能计算**：采用 Python 向量化处理技术，在单机环境下即可快速处理数百万行交易数据。
- **可视化报告**：一键生成累计收益率曲线、AAR/CAAR 统计图表，直观呈现研究结果。
- **模块化配置 (v1.1.0)**：引入全局 `CONFIG` 块，无需深入代码逻辑即可调整回测周期、采样上限及分红阈值。

---

## 🛠️ 快速开始

### 1. 环境准备

确保您的系统中已安装 Python 3.7+。

```bash
# 克隆仓库
git clone https://github.com/madbarasa/ChinaAQuant.git
cd ChinaAQuant

# 安装核心依赖
pip install pandas numpy matplotlib scipy
```

### 2. 运行分析

本项目提供了一个高度整合的主程序，推荐优先运行：

```bash
# 运行完整分析流程（因子分析 + 事件研究）
python complete_analysis.py
```

*预计运行时间：3-5 分钟（视硬件性能而定）。*

---

## ⚙️ 全局配置 (CONFIG)

在 `complete_analysis.py` 顶部，您可以根据研究需求调整以下参数：

| 参数类别 | 参数名 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| **因子参数** | `PAST_PERF_PERIOD` | 63 | 动量因子计算周期（交易日） |
| | `MAX_WINDOW` | 20 | MAX 因子窗口 |
| **事件研究** | `MAX_SAMPLES` | 500 | 随机采样事件数量（加速分析） |
| | `GOOD_EVENT_THRESHOLD` | 60 | 行业低分红比例阈值 |
| **回测设置** | `DATE_RANGE` | 2015-2024 | 数据筛选的时间跨度 |

---

## 📂 目录结构

```text
madbarasa/ChinaAQuant
├── price_data/               # 日度交易数据库 (TRD_Dalyr*.db)
├── Appendix3.db              # 分红预案原始数据
├── CD_CompOfDivProfitInd.db  # 行业分红比例参考表
├── STK_LISTEDCOINFOANL.db    # 上市公司行业映射表
├── complete_analysis.py      # ⭐ 核心：全自动分析主程序 (v1.1.0)
├── factor_analysis.py        # 因子投资专项分析脚本
├── event_study.py            # 事件研究专项分析脚本
├── 分析结果总结.md           # 详细的数据分析结论
└── README.md                 # 项目指南
```

---

## 📊 研究发现摘要

### 1. 因子投资分析 (Factor Investing)

| 因子 | 年化收益率 | 夏普比率 | 结论 |
| :--- | :--- | :--- | :--- |
| **Past Performance** | -45.73% | -1.44 | 显著的反转效应 |
| **MAX** | -21.73% | -0.72 | 追逐极端收益存在风险 |
| **Volatility** | -0.77% | -0.45 | 低波动效应不明显 |

> **结论**：A股市场存在显著的“反转效应”，追涨策略在长期回测中表现不佳，建议采取反向投资思路。

### 2. 事件研究 (Event Study)

- **利空事件**：在行业高分红背景下不分红的公司，T+10 日 CAAR 显著下降（约 **-2.23%**）。
- **信息提前**：研究发现公告日前存在明显的异常收益波动，暗示信息可能提前泄露。

---

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request 来改进本项目！
- 添加新的因子定义
- 引入更复杂的风险模型（如 Fama-French 三因子）
- 优化数据处理性能

---

## 📄 许可证

本项目采用 **MIT License** 许可。

## ⚠️ 免责声明

本系统仅供学术研究和量化爱好者学习使用。**市场有风险，投资需谨慎**。基于本项目策略产生的任何盈亏均由使用者自行承担。
