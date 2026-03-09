#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略15 - 风险预警系统
原理：
    多维度风险指标实时监控
    当风险超过阈值时自动报警并平仓

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - VaR置信度：95%
    - 最大回撤阈值：10%

适用行情：风险控制
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import pandas as pd
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"           # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
VOLUME = 1                       # 交易手数
DATA_LENGTH = 50                 # 历史K线数量
VAR_CONFIDENCE = 0.95            # VaR置信度
MAX_DRAWDOWN = 0.10              # 最大回撤阈值
RISK_LIMIT = 0.05                # 风险敞口限制


def calculate_var(returns, confidence=0.95):
    """计算VaR风险价值"""
    if len(returns) < 2:
        return 0
    var = np.percentile(returns, (1 - confidence) * 100)
    return abs(var)


def calculate_max_drawdown(equity_curve):
    """计算最大回撤"""
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    max_dd = drawdown.min()
    return abs(max_dd)


def calculate_sharpe_ratio(returns, risk_free_rate=0.03):
    """计算夏普比率"""
    if len(returns) < 2:
        return 0
    excess_returns = returns - risk_free_rate / 252
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：风险预警系统")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    account = api.get_account()
    target_pos = TargetPosTask(api, SYMBOL)
    
    # 初始开仓
    target_pos.set_target_volume(VOLUME)
    
    equity_curve = [account.balance]
    position = VOLUME
    
    print(f"初始账户权益: {account.balance:.2f}")
    print(f"风险监控参数:")
    print(f"  - VaR置信度: {VAR_CONFIDENCE*100}%")
    print(f"  - 最大回撤阈值: {MAX_DRAWDOWN*100}%")
    print(f"  - 风险敞口限制: {RISK_LIMIT*100}%")
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            price = klines["close"].iloc[-1]
            
            # 更新权益曲线
            current_equity = account.balance
            equity_curve.append(current_equity)
            
            if len(equity_curve) > 2:
                # 计算收益率序列
                returns = pd.Series(equity_curve).pct_change().dropna()
                
                # 计算各项风险指标
                var_95 = calculate_var(returns, VAR_CONFIDENCE)
                max_dd = calculate_max_drawdown(pd.Series(equity_curve))
                sharpe = calculate_sharpe_ratio(returns)
                
                # 计算当前风险敞口
                position_value = price * VOLUME * 10  # 螺纹钢乘数
                exposure = position_value / current_equity
                
                print(f"\n=== 风险监控 ===")
                print(f"价格: {price:.2f}")
                print(f"权益: {current_equity:.2f}")
                print(f"VaR(95%): {var_95*100:.2f}%")
                print(f"最大回撤: {max_dd*100:.2f}%")
                print(f"夏普比率: {sharpe:.2f}")
                print(f"风险敞口: {exposure*100:.2f}%")
                
                # 风险预警判断
                alerts = []
                
                if max_dd > MAX_DRAWDOWN:
                    alerts.append(f"⚠️ 最大回撤超限: {max_dd*100:.2f}%")
                
                if exposure > RISK_LIMIT:
                    alerts.append(f"⚠️ 风险敞口超限: {exposure*100:.2f}%")
                
                if var_95 > 0.03:
                    alerts.append(f"⚠️ VaR风险过高: {var_95*100:.2f}%")
                
                if sharpe < 0.5 and len(returns) > 10:
                    alerts.append(f"⚠️ 夏普比率过低: {sharpe:.2f}")
                
                if alerts:
                    print("\n🚨 风险预警:")
                    for alert in alerts:
                        print(f"  {alert}")
                    
                    # 执行风险控制
                    print("\n执行风险控制措施...")
                    target_pos.set_target_volume(0)
                    position = 0
                    print("已全部平仓")
                    break
                else:
                    print("✅ 风险指标正常")
    
    api.close()


if __name__ == "__main__":
    main()
