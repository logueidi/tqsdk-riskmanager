#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略16 - 仓位动态平衡系统
原理：
    根据账户权益变化动态调整仓位
    保持风险敞口恒定，实现盈利保护

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 目标风险度：5%
    - 平衡阈值：10%

适用行情：仓位管理
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import pandas as pd

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"           # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
TARGET_RISK = 0.05               # 目标风险度 5%
BALANCE_THRESHOLD = 0.10         # 平衡阈值 10%
INITIAL_CAPITAL = 100000         # 初始资金
VOLUME_MULTIPLIER = 10           # 合约乘数
DATA_LENGTH = 30                 # 历史K线数量
ATR_PERIOD = 14                  # ATR周期


def calculate_atr(klines, period=14):
    """计算ATR"""
    high = klines["high"]
    low = klines["low"]
    close = klines["close"]
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_position_size(account_balance, atr, target_risk):
    """计算仓位数量"""
    risk_amount = account_balance * target_risk
    position_size = risk_amount / (atr * VOLUME_MULTIPLIER)
    return int(position_size)


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：仓位动态平衡系统")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    account = api.get_account()
    target_pos = TargetPosTask(api, SYMBOL)
    
    initial_balance = account.balance
    current_balance = account.balance
    
    print(f"初始资金: {initial_balance:.2f}")
    print(f"目标风险度: {TARGET_RISK*100}%")
    print(f"平衡阈值: {BALANCE_THRESHOLD*100}%")
    
    # 初始建仓
    atr = calculate_atr(klines, ATR_PERIOD)
    current_atr = atr.iloc[-1]
    initial_position = calculate_position_size(initial_balance, current_atr, TARGET_RISK)
    initial_position = max(1, min(initial_position, 10))  # 限制仓位1-10手
    
    target_pos.set_target_volume(initial_position)
    print(f"\n初始仓位: {initial_position} 手")
    
    current_position = initial_position
    last_balance = current_balance
    position_adjusted = True
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            current_balance = account.balance
            price = klines["close"].iloc[-1]
            current_atr = calculate_atr(klines, ATR_PERIOD).iloc[-1]
            
            # 计算资金变化率
            balance_change = (current_balance - initial_balance) / initial_balance
            
            # 计算应调整的仓位
            target_position = calculate_position_size(current_balance, current_atr, TARGET_RISK)
            target_position = max(1, min(target_position, 10))  # 限制仓位
            
            # 检查是否需要平衡
            position_change = abs(target_position - current_position) / current_position if current_position > 0 else 1
            
            print(f"\n=== 仓位平衡 ===")
            print(f"当前价格: {price:.2f}")
            print(f"ATR: {current_atr:.2f}")
            print(f"当前权益: {current_balance:.2f}")
            print(f"资金变化: {balance_change*100:+.2f}%")
            print(f"当前仓位: {current_position} 手")
            print(f"目标仓位: {target_position} 手")
            print(f"仓位变化: {position_change*100:.2f}%")
            
            # 盈利保护：只加仓不减仓
            if balance_change > BALANCE_THRESHOLD and position_change > 0.2:
                if target_position > current_position:
                    print(f"\n✅ 触发再平衡：加仓")
                    target_pos.set_target_volume(target_position)
                    current_position = target_position
                    position_adjusted = True
                else:
                    print(f"\n📊 盈利状态，暂不减仓")
            
            # 止损保护：资金回撤超过阈值时减仓
            elif balance_change < -BALANCE_THRESHOLD:
                reduce_ratio = min(abs(balance_change), 0.5)
                new_position = int(current_position * (1 - reduce_ratio))
                new_position = max(1, new_position)
                
                print(f"\n⚠️ 资金回撤，触发保护减仓")
                target_pos.set_target_volume(new_position)
                current_position = new_position
                position_adjusted = True
            
            # 定期平衡（每超过阈值一次）
            elif balance_change > 0 and position_change > 0.3:
                print(f"\n✅ 定期平衡仓位")
                target_pos.set_target_volume(target_position)
                current_position = target_position
                position_adjusted = True
            
            else:
                if position_adjusted:
                    print("✅ 仓位平衡，无需调整")
                position_adjusted = False
    
    api.close()


if __name__ == "__main__":
    main()
