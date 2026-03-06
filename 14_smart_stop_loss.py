#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略14 - 智能止损系统
原理：
    结合ATR和波动率自适应调整止损
    根据市场状态动态调整止损幅度

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - ATR倍数：2.0
    - 波动率调整：启用

适用行情：波动性较大的行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"           # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
ATR_MULTI = 2.0                  # ATR倍数
VOLUME = 1                       # 每次交易手数
DATA_LENGTH = 50                 # 历史K线数量
USE_VOLATILITY = True            # 启用波动率调整


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


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：智能止损系统")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    account = api.get_account()
    target_pos = TargetPosTask(api, SYMBOL)
    
    # 初始开仓
    target_pos.set_target_volume(VOLUME)
    
    import pandas as pd
    
    entry_price = None
    position = 1
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            price = klines["close"].iloc[-1]
            
            if entry_price is None:
                entry_price = price
            
            # 计算ATR
            atr = calculate_atr(klines)
            current_atr = atr.iloc[-1]
            
            # 基础止损
            base_stop = current_atr * ATR_MULTI
            
            # 波动率调整
            if USE_VOLATILITY:
                volatility = klines["close"].pct_change().std()
                # 高波动增加止损幅度
                volatility_factor = 1 + (volatility * 10)
                stop_distance = base_stop * min(volatility_factor, 2.0)
            else:
                stop_distance = base_stop
            
            stop_price = entry_price - stop_distance
            
            print(f"价格: {price:.2f}, ATR: {current_atr:.2f}, 止损: {stop_price:.2f}")
            
            # 触发止损
            if price < stop_price:
                print(f"[止损] 触发智能止损，价格: {stop_price:.2f}")
                target_pos.set_target_volume(0)
                position = 0
                break
    
    api.close()


if __name__ == "__main__":
    main()
