# tqsdk-riskmanager

> 基于 **TqSdk** 的风险管理策略模块，持续更新中。

## 项目简介

本仓库专注于**量化交易风险管理**，涵盖仓位管理、止损策略、风险监控等方向。  
所有策略使用 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现，可直接对接实盘账户。

## 策略列表

| # | 策略名称 | 类型 | 文件 |
|---|---------|------|------|
| 01 | ATR 动态仓位管理策略 | 仓位管理 | [01_atr_position_sizer.py](strategies/01_atr_position_sizer.py) |
| 02 | 回撤保护策略 | 风险控制 | [02_drawdown_guard.py](strategies/02_drawdown_guard.py) |
| 03 | 固定止损策略 | 止损策略 | [03_fixed_stop_loss.py](strategies/03_fixed_stop_loss.py) |
| 04 | 波动率仓位管理策略 | 仓位管理 | [04_volatility_position.py](strategies/04_volatility_position.py) |
| 05 | 动态止盈止损策略 | 止损策略 | [05_dynamic_stop.py](strategies/05_dynamic_stop.py) |
| 06 | 移动止损策略 | 止损策略 | [06_trailing_stop.py](strategies/06_trailing_stop.py) |
| 07 | 动态止盈策略 | 止盈策略 | [07_dynamic_stop_profit.py](strategies/07_dynamic_stop_profit.py) |
| 08 | 波动率止损策略 | 止损策略 | [08_volatility_stop.py](strategies/08_volatility_stop.py) |
| 09 | Kelly 仓位管理策略 | 仓位管理 | [09_kelly_position.py](strategies/09_kelly_position.py) |
| 10 | VaR 风险监控策略 | 风险监控 | [10_var_monitor.py](strategies/10_var_monitor.py) |
| 11 | 移动止盈策略 | 止盈策略 | [11_trailing_stop.py](strategies/11_trailing_stop.py) |
| 12 | ATR 止损策略 | 止损策略 | [12_atr_stop_loss.py](strategies/12_atr_stop_loss.py) |
| 13 | 风险仪表盘策略 | 风险监控 | [13_risk_dashboard.py](strategies/13_risk_dashboard.py) |
| 14 | 智能止损策略 | 止损策略 | [14_smart_stop_loss.py](strategies/14_smart_stop_loss.py) |
| 15 | 仓位规模计算器 | 仓位管理 | [15_position_sizer.py](strategies/15_position_sizer.py) |
| 16 | 风险预算策略 | 仓位管理 | [16_risk_budget.py](strategies/16_risk_budget.py) |
| 17 | 最大回撤监控 | 风险监控 | [17_max_drawdown.py](strategies/17_max_drawdown.py) |
| 18 | 波动率调整策略 | 仓位管理 | [18_vol_adj_position.py](strategies/18_vol_adj_position.py) |
| 19 | 风险收益比优化策略 | 风险控制 | [19_risk_reward_opt.py](strategies/19_risk_reward_opt.py) |
| 20 | 多策略风控策略 | 风险控制 | [20_multi_strategy_risk.py](strategies/20_multi_strategy_risk.py) |

## 策略分类

### 📊 仓位管理（Position Sizing）
基于 ATR、波动率、Kelly 公式等计算最优仓位。

### 🛡️ 止损策略（Stop Loss）
固定止损、移动止损、ATR 止损等策略。

### 📈 风险监控（Risk Monitoring）
VaR 计算、回撤监控、风险仪表盘等。

## 环境要求

```bash
pip install tqsdk numpy pandas scipy
```

## 使用说明

1. 可作为模块导入其他策略使用
2. 根据自身风险偏好调整参数
3. 建议结合主策略一起使用

## 风险提示

- 风险管理不能完全消除风险
- 历史数据回测结果不代表未来表现
- 本仓库策略仅供学习研究，不构成投资建议

---

**持续更新中，欢迎 Star ⭐ 关注**

*更新时间：2026-03-11*
