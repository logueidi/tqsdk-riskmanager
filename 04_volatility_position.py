#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略04 - 波动率仓位管理策略
原理：
    根据市场波动率动态调整仓位：
    1. 高波动率 → 降低仓位
    2. 低波动率 → 增加仓位
    3. 使用ATR衡量波动率

参数：
    - 基础仓位：10手
    - ATR周期：14
    - 仓位调整系数：ATR > 2倍平均ATR时减半

适用行情：所有市场环境
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import ATR
import pandas as pd

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2405"       # 交易合约
KLINE_DURATION = 60 * 60     # 1小时K线
BASE_LOT = 10                # 基础仓位
ATR_PERIOD = 14              # ATR周期
ATR_THRESHOLD = 2.0          # ATR阈值倍数
LOT_SIZE = BASE_LOT          # 实际开仓手数

def calc_dynamic_lot(api, symbol, klines):
    """根据ATR计算动态仓位"""
    if len(klines) < ATR_PERIOD + 5:
        return BASE_LOT
    
    df = pd.DataFrame(klines)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    
    atr = ATR(df['high'], df['low'], df['close'], ATR_PERIOD)
    current_atr = atr.iloc[-1]
    
    # 计算历史ATR均值
    atr_mean = atr.iloc[-20:].mean()
    
    # 波动率高于阈值，减少仓位
    if current_atr > atr_mean * ATR_THRESHOLD:
        return BASE_LOT // 2
    
    return BASE_LOT

def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print(f"启动：波动率仓位管理策略 | 合约: {SYMBOL}")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=50)
    
    position = 0  # 1: 多头, -1: 空头, 0: 空仓
    
    while True:
        api.wait_update(klines)
        
        # 计算动态仓位
        current_lot = calc_dynamic_lot(api, SYMBOL, klines)
        
        if position == 0:
            # 示例信号逻辑
            # ...
            pass
    
    api.close()

if __name__ == "__main__":
    main()
