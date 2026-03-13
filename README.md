# tqsdk-riskmanager

> 基于 **TqSdk** 的风险管理工具，持续更新中。

## 项目简介

本仓库专注于**量化风险管理工具**，涵盖仓位管理、止损策略、VaR计算、流动性风险等领域。  
所有策略使用 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现。

## 策略列表

| # | 策略名称 | 类型 | 文件 |
|---|---------|------|------|
| 01 | ATR仓位管理器 | 仓位管理 | [01_atr_position_sizer.py](01_atr_position_sizer.py) |
| 02 | 回撤保护器 | 风险控制 | [02_drawdown_guard.py](02_drawdown_guard.py) |
| 03 | 固定止损策略 | 止损策略 | [03_fixed_stop_loss.py](03_fixed_stop_loss.py) |
| 04 | 波动率仓位管理 | 仓位管理 | [04_volatility_position.py](04_volatility_position.py) |
| 05 | 动态止损策略 | 止损策略 | [05_dynamic_stop.py](05_dynamic_stop.py) |
| 06 | 回撤监控器 | 风险监控 | [06_drawdown_monitor.py](06_drawdown_monitor.py) |
| 07 | 动态止盈止损 | 止损策略 | [07_dynamic_stop_profit.py](07_dynamic_stop_profit.py) |
| 08 | 波动率仓位 | 仓位管理 | [08_volatility_position.py](08_volatility_position.py) |
| 09 | Kelly仓位计算 | 仓位管理 | [09_kelly_position.py](09_kelly_position.py) |
| 10 | VaR监控器 | 风险监控 | [10_var_monitor.py](10_var_monitor.py) |
| 11 | 追踪止损 | 止损策略 | [11_trailing_stop.py](11_trailing_stop.py) |
| 12 | ATR止损策略 | 止损策略 | [12_atr_stop_loss.py](12_atr_stop_loss.py) |
| 13 | 风险仪表盘 | 风险监控 | [13_risk_dashboard.py](13_risk_dashboard.py) |
| 14 | 智能止损 | 止损策略 | [14_smart_stop_loss.py](14_smart_stop_loss.py) |
| 15 | 风险预警系统 | 风险监控 | [15_risk_alert_system.py](15_risk_alert_system.py) |
| 16 | 动态仓位平衡 | 仓位管理 | [16_dynamic_position_balancing.py](16_dynamic_position_balancing.py) |
| 17 | 风险敞口监控 | 风险监控 | [17_risk_exposure_monitor.py](17_risk_exposure_monitor.py) |
| 18 | 流动性风险管理 | 流动性风险 | [18_liquidity_risk_manager.py](18_liquidity_risk_manager.py) |
| 19 | 持仓异常检测 | 风险监控 | [19_position_anomaly_detector.py](19_position_anomaly_detector.py) |
| 20 | 风险预算管理 | 仓位管理 | [20_risk_budget_manager.py](20_risk_budget_manager.py) |
| 21 | 组合VaR计算 | 风险监控 | [21_portfolio_var.py](21_portfolio_var.py) |
| 22 | 相关性风险监控 | 风险监控 | [22_correlation_risk_monitor.py](22_correlation_risk_monitor.py) |
| 23 | 尾部风险对冲 | 对冲策略 | [23_tail_risk_hedge.py](23_tail_risk_hedge.py) |
| 24 | 流动性风险管理器 | 流动性风险 | [24_liquidity_risk_manager.py](24_liquidity_risk_manager.py) |

## 策略分类

### 📊 仓位管理
ATR仓位管理、波动率仓位、Kelly公式、动态平衡、风险预算等。

### 🛡️ 止损策略
固定止损、动态止损、ATR止损、追踪止损、智能止损等。

### 📈 风险监控
VaR监控、回撤监控、风险仪表盘、敞口监控、相关性风险等。

### 💧 流动性风险
流动性风险管理、持仓限制、清仓成本分析等。

### 🛡️ 对冲策略
尾部风险对冲、期权保护等。

## 环境要求

```bash
pip install tqsdk numpy pandas scipy
```

## 风险提示

- 本仓库仅供研究学习使用
- 过往业绩不代表未来表现

---

**持续更新中，欢迎 Star ⭐ 关注**

*更新时间：2026-03-13*
