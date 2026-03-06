#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略05 - 风险控制：动态止盈止损策略
原理：
    根据账户权益动态调整止盈止损位。
    当账户创新高时提高止盈位，锁定更多利润。

参数：
    - 初始止损：2%
    - 移动止盈：盈利 3% 后启动
    - 回撤阈值：盈利回吐 50% 时平仓

适用行情：所有行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"
INITIAL_STOP = 0.02             # 初始止损2%
TRAIL_START = 0.03              # 移动止盈启动点3%
TRAIL_LOCK = 0.5                # 回吐50%时平仓

# ============ 主策略 ============
class RiskManager:
    def __init__(self, api, symbol):
        self.api = api
        self.symbol = symbol
        self.peak_equity = 0
        self.entry_price = 0
        self.position = 0
        
    def update(self, current_price, account_equity):
        """更新风险管理"""
        
        # 更新峰值权益
        if account_equity > self.peak_equity:
            self.peak_equity = account_equity
            
        if self.position == 0:
            return None
            
        pnl_ratio = (current_price - self.entry_price) / self.entry_price
        
        # 初始止损
        if pnl_ratio < -INITIAL_STOP:
            return "STOP_LOSS"
            
        # 移动止盈
        if pnl_ratio > TRAIL_START:
            # 计算回吐比例
            max_pnl = self.peak_equity / (self.entry_price * (1 + TRAIL_START)) - 1
            current_pnl = pnl_ratio
            
            if current_pnl < max_pnl * (1 - TRAIL_LOCK):
                return "TRAIL_STOP"
                
        return None


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：动态止盈止损策略")
    
    symbol = SYMBOL
    risk_mgr = RiskManager(api, symbol)
    
    klines = api.get_kline_serial(symbol, 60)
    account = api.get_account()
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            current_price = klines['close'].iloc[-1]
            equity = account.balance
            
            action = risk_mgr.update(current_price, equity)
            
            if action:
                print(f"[风控触发] {action}, 价格: {current_price}, 权益: {equity}")
    
    api.close()

if __name__ == "__main__":
    main()
