#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略07 - 风险控制：动态止盈止损策略
原理：
    根据市场波动率动态调整止盈止损位置。
    ATR增大时扩大止损范围，ATR减小时收紧止损。

参数：
    - 初始止损：2%
    - ATR倍数：2.0
    - 止盈止损比：2:1

适用行情：所有行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import ATR
import numpy as np

# ============ 参数配置 ============
INITIAL_STOP_LOSS = 0.02        # 初始止损2%
ATR_MULTI = 2.0                 # ATR倍数
PROFIT_RATIO = 2.0              # 止盈止损比

# ============ 主策略 ============
class DynamicStopStrategy:
    def __init__(self, api, symbol):
        self.api = api
        self.symbol = symbol
        self.position = 0
        self.entry_price = 0
        self.atr = 0
        
    def calculate_dynamic_stops(self, entry_price, klines):
        """计算动态止盈止损"""
        self.atr = ATR(klines, 14).iloc[-1]
        
        # 动态止损 = 价格 * (ATR/收盘价)
        pct_atr = self.atr / klines['close'].iloc[-1]
        stop_loss = max(INITIAL_STOP_LOSS, pct_atr * ATR_MULTI)
        
        # 止盈 = 止损 * 倍数
        take_profit = stop_loss * PROFIT_RATIO
        
        return stop_loss, take_profit
    
    def update_position(self, klines):
        """更新仓位检查"""
        if self.position == 0:
            return
            
        current_price = klines['close'].iloc[-1]
        stop_loss, take_profit = self.calculate_dynamic_stops(self.entry_price, klines)
        
        if self.position == 1:  # 多头
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            
            if pnl_pct < -stop_loss:
                print(f"[止损] 动态止损: {stop_loss*100:.2f}%, 价格: {current_price}")
                self.position = 0
            elif pnl_pct > take_profit:
                print(f"[止盈] 动态止盈: {take_profit*100:.2f}%, 价格: {current_price}")
                self.position = 0
                
        elif self.position == -1:  # 空头
            pnl_pct = (self.entry_price - current_price) / self.entry_price
            
            if pnl_pct < -stop_loss:
                print(f"[止损] 动态止损: {stop_loss*100:.2f}%, 价格: {current_price}")
                self.position = 0
            elif pnl_pct > take_profit:
                print(f"[止盈] 动态止盈: {take_profit*100:.2f}%, 价格: {current_price}")
                self.position = 0


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：动态止盈止损策略")
    
    # 这里需要结合具体策略使用
    # 示例代码结构
    
    api.close()

if __name__ == "__main__":
    main()
