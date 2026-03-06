#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略10 - 风险价值(VaR)监控器
原理：
    使用历史模拟法计算组合的VaR值，监控风险暴露。
    当日VaR超过阈值时触发预警或自动减仓。

参数：
    - 置信水平：95%
    - 持有期限：1天
    - VaR阈值：2%
    - 回溯期：60天

适用行情：风险监控
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
CONFIDENCE_LEVEL = 0.95         # 置信水平
HOLDING_PERIOD = 1              # 持有期限（天）
VAR_THRESHOLD = 0.02            # VaR阈值 2%
LOOKBACK_PERIOD = 60            # 回溯期

# ============ VaR计算 ============
def calculate_var(returns, confidence_level=0.95):
    """
    使用历史模拟法计算VaR
    returns: 收益率序列
    confidence_level: 置信水平
    """
    if len(returns) < 10:
        return 0.0
    
    var = np.percentile(returns, (1 - confidence_level) * 100)
    return abs(var)

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：风险价值(VaR)监控器")
    
    # 模拟历史收益率数据（60天）
    # 实际应从数据库获取真实收益率
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.015, LOOKBACK_PERIOD)
    
    # 计算VaR
    var_1d = calculate_var(returns, CONFIDENCE_LEVEL)
    var_10d = var_1d * np.sqrt(HOLDING_PERIOD)  # 扩展到N天
    
    print(f"1天VaR ({CONFIDENCE_LEVEL*100:.0f}%): {var_1d*100:.2f}%")
    print(f"{HOLDING_PERIOD}天VaR: {var_10d*100:.2f}%")
    print(f"VaR阈值: {VAR_THRESHOLD*100:.1f}%")
    
    if var_10d > VAR_THRESHOLD:
        print(f"[警告] VaR超过阈值，风险过高！")
    else:
        print(f"[正常] VaR在可控范围内")
    
    # 持续监控
    account = api.get_account()
    
    while True:
        api.wait_update()
        
        # 可以定期更新VaR计算
        # 这里仅做示例
        
        current_equity = account.balance
        print(f"当前权益: {current_equity:.2f}")
        
        # 实际应定时更新VaR
    
    api.close()

if __name__ == "__main__":
    main()
