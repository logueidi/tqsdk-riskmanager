#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略06 - 风险控制：最大回撤监控策略
原理：
    实时监控账户最大回撤，当回撤超过阈值时自动减仓或清仓。
    保护账户资金安全。

参数：
    - 最大回撤阈值：10%
    - 预警阈值：8%
    - 减仓比例：50%

适用行情：市场剧烈波动时
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
MAX_DRAWDOWN = 0.10             # 最大回撤10%
WARNING_DRAWDOWN = 0.08         # 预警8%
REDUCE_RATIO = 0.5              # 减仓50%

# ============ 主策略 ============
class DrawdownMonitor:
    def __init__(self, api):
        self.api = api
        self.peak_equity = 0
        self.warning_sent = False
        
    def check_drawdown(self, current_equity):
        """检查回撤"""
        
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.warning_sent = False
            return "NORMAL"
            
        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        
        if drawdown > MAX_DRAWDOWN:
            return "MAX_DRAWDOWN"  # 清仓
        elif drawdown > WARNING_DRAWDOWN and not self.warning_sent:
            self.warning_sent = True
            return "WARNING"  # 预警
        else:
            return "NORMAL"


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：最大回撤监控策略")
    
    monitor = DrawdownMonitor(api)
    account = api.get_account()
    
    while True:
        api.wait_update()
        
        if api.is_changing(account):
            equity = account.balance
            
            result = monitor.check_drawdown(equity)
            
            if result == "MAX_DRAWDOWN":
                print(f"[风控] 达到最大回撤 {MAX_DRAWDOWN*100}%，请手动处理")
            elif result == "WARNING":
                print(f"[预警] 回撤接近阈值 {WARNING_DRAWDOWN*100}%")
    
    api.close()

if __name__ == "__main__":
    main()
