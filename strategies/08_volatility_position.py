#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略08 - 风险控制：波动率仓位管理策略
原理：
    根据市场波动率动态调整仓位大小。
    高波动时减仓，低波动时加仓。

参数：
    - 基准仓位：10手
    - 波动率上限：3%
    - 波动率下限：0.5%
    - 最大仓位：20手
    - 最小仓位：5手

适用行情：所有行情
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import ATR
import numpy as np

# ============ 参数配置 ============
BASE_LOT = 10                   # 基准仓位
MAX_LOT = 20                    # 最大仓位
MIN_LOT = 5                     # 最小仓位
VOL_LOW = 0.005                 # 波动率下限0.5%
VOL_HIGH = 0.03                 # 波动率上限3%

# ============ 主策略 ============
class VolatilityPositionSizer:
    def __init__(self, api, symbol):
        self.api = api
        self.symbol = symbol
        
    def calculate_position_size(self, klines):
        """根据波动率计算仓位"""
        current_price = klines['close'].iloc[-1]
        atr = ATR(klines, 14).iloc[-1]
        
        # 计算波动率（ATR/价格）
        volatility = atr / current_price
        
        # 根据波动率计算仓位
        if volatility < VOL_LOW:
            # 低波动，加仓
            lot = min(BASE_LOT * 2, MAX_LOT)
            print(f"[仓位调整] 低波动 {volatility*100:.2f}%, 仓位: {lot}手")
        elif volatility > VOL_HIGH:
            # 高波动，减仓
            lot = max(BASE_LOT // 2, MIN_LOT)
            print(f"[仓位调整] 高波动 {volatility*100:.2f}%, 仓位: {lot}手")
        else:
            # 正常波动
            lot = BASE_LOT
            print(f"[仓位调整] 正常波动 {volatility*100:.2f}%, 仓位: {lot}手")
            
        return lot


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：波动率仓位管理策略")
    
    # 这里需要结合具体策略使用
    # 示例代码结构
    
    api.close()

if __name__ == "__main__":
    main()
