#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略11 - 移动止损策略
原理：
    追踪止损：当盈利达到一定幅度后，启动移动止损
    保护已有利润

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 激活盈利：2%
    - 止损回撤：1%

适用行情：有趋势的行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"           # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
PROFIT_ACTIVATE = 0.02           # 激活移动止损的盈利幅度（2%）
TRAIL_STOP = 0.01                # 移动止损回撤幅度（1%）
VOLUME = 1                       # 每次交易手数
DATA_LENGTH = 50                 # 历史K线数量


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：移动止损策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    account = api.get_account()
    target_pos = TargetPosTask(api, SYMBOL)
    
    # 初始开仓
    target_pos.set_target_volume(VOLUME)
    
    entry_price = None
    highest_price = None
    lowest_price = None
    trail_activated = False
    position = 1  # 假设做多
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines.iloc[-1], "datetime"):
            price = klines["close"].iloc[-1]
            
            if entry_price is None:
                entry_price = price
                highest_price = price
                lowest_price = price
            
            profit_ratio = (price - entry_price) / entry_price
            
            print(f"价格: {price:.2f}, 盈亏: {profit_ratio*100:.2f}%")
            
            # 更新最高价
            if price > highest_price:
                highest_price = price
            
            # 激活移动止损
            if profit_ratio > PROFIT_ACTIVATE and not trail_activated:
                trail_activated = True
                print(f"[激活] 移动止损已激活")
            
            # 执行移动止损
            if trail_activated:
                stop_price = highest_price * (1 - TRAIL_STOP)
                if price < stop_price:
                    print(f"[止损] 触发移动止损，价格: {stop_price:.2f}")
                    target_pos.set_target_volume(0)
                    position = 0
                    break
    
    api.close()


if __name__ == "__main__":
    main()
