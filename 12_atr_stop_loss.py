#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略12 - ATR动态止损策略
原理：
    使用ATR（平均真实波幅）计算动态止损位
    止损距离随市场波动性自动调整

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - ATR周期：14
    - ATR倍数：2.5

适用行情：所有行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"           # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
ATR_PERIOD = 14                  # ATR周期
ATR_MULTI = 2.5                  # ATR倍数
VOLUME = 1                       # 每次交易手数
DATA_LENGTH = 100                # 历史K线数量


def calc_atr(high, low, close, period):
    """计算ATR"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr


def main():
    import pandas as pd
    
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：ATR动态止损策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    target_pos = TargetPosTask(api, SYMBOL)
    
    # 初始开仓
    target_pos.set_target_volume(VOLUME)
    
    position = 1  # 做多
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            high = klines["high"]
            low = klines["low"]
            close = klines["close"]
            
            atr = calc_atr(high, low, close, ATR_PERIOD)
            atr_val = atr.iloc[-1]
            price = close.iloc[-1]
            
            # 动态止损位
            stop_price = price - atr_val * ATR_MULTI
            
            print(f"价格: {price:.2f}, ATR: {atr_val:.2f}, 止损位: {stop_price:.2f}")
            
            # 触发止损
            if price < stop_price:
                print(f"[止损] 触发ATR动态止损")
                target_pos.set_target_volume(0)
                position = 0
                break
    
    api.close()


if __name__ == "__main__":
    main()
