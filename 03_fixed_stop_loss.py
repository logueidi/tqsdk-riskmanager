#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略03 - 固定比例止损策略
原理：
    固定比例止损是最简单的风控方式：
    1. 开仓时设定固定止损比例
    2. 价格反向移动触及止损位时自动平仓
    3. 可叠加追踪止损优化

参数：
    - 止损比例：2%
    - 止盈比例：4%
    - 是否启用追踪止损：True

适用行情：所有趋势行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2405"       # 交易合约
STOP_LOSS_PCT = 0.02         # 止损比例 2%
TAKE_PROFIT_PCT = 0.04       # 止盈比例 4%
TRAILING_STOP = True         # 启用追踪止损
TRAILING_PCT = 0.015         # 追踪止损比例 1.5%
LOT_SIZE = 1                 # 开仓手数

def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print(f"启动：固定比例止损策略 | 合约: {SYMBOL}")
    
    quote = api.get_quote(SYMBOL)
    klines = api.get_kline_serial(SYMBOL, 60, data_length=10)
    
    position = 0  # 1: 多头, -1: 空头, 0: 空仓
    entry_price = 0
    highest_price = 0
    lowest_price = float('inf')
    
    while True:
        api.wait_update(klines)
        
        current_price = quote.last_price
        
        if position == 0:
            # 示例：简单均线金叉做多，死叉做空
            # 实际需要更复杂的信号逻辑
            pass
        
        elif position == 1:
            # 更新最高价（追踪止损用）
            if current_price > highest_price:
                highest_price = current_price
            
            # 止损
            if current_price < entry_price * (1 - STOP_LOSS_PCT):
                print(f"止损 | 入场: {entry_price}, 当前: {current_price}, 止损: {entry_price * (1 - STOP_LOSS_PCT):.2f}")
                api.insert_order(symbol=SYMBOL, direction="short", offset="close", volume=LOT_SIZE)
                position = 0
            
            # 止盈
            elif current_price > entry_price * (1 + TAKE_PROFIT_PCT):
                print(f"止盈 | 入场: {entry_price}, 当前: {current_price}")
                api.insert_order(symbol=SYMBOL, direction="short", offset="close", volume=LOT_SIZE)
                position = 0
            
            # 追踪止损
            elif TRAILING_STOP and current_price < highest_price * (1 - TRAILING_PCT):
                print(f"追踪止损 | 最高: {highest_price}, 当前: {current_price}")
                api.insert_order(symbol=SYMBOL, direction="short", offset="close", volume=LOT_SIZE)
                position = 0
        
        elif position == -1:
            if current_price < lowest_price:
                lowest_price = current_price
            
            # 止损
            if current_price > entry_price * (1 + STOP_LOSS_PCT):
                print(f"止损 | 入场: {entry_price}, 当前: {current_price}, 止损: {entry_price * (1 + STOP_LOSS_PCT):.2f}")
                api.insert_order(symbol=SYMBOL, direction="long", offset="close", volume=LOT_SIZE)
                position = 0
            
            # 止盈
            elif current_price < entry_price * (1 - TAKE_PROFIT_PCT):
                print(f"止盈 | 入场: {entry_price}, 当前: {current_price}")
                api.insert_order(symbol=SYMBOL, direction="long", offset="close", volume=LOT_SIZE)
                position = 0
            
            # 追踪止损
            elif TRAILING_STOP and current_price > lowest_price * (1 + TRAILING_PCT):
                print(f"追踪止损 | 最低: {lowest_price}, 当前: {current_price}")
                api.insert_order(symbol=SYMBOL, direction="long", offset="close", volume=LOT_SIZE)
                position = 0
    
    api.close()

if __name__ == "__main__":
    main()
