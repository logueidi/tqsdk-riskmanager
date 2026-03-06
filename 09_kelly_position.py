#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略09 - 凯利公式仓位管理器
原理：
    根据历史胜率和盈亏比，使用凯利公式计算最优仓位比例。
    f* = (bp - q) / b，其中 b=盈亏比，p=胜率，q=1-p

参数：
    - 基础仓位：10%
    - 凯利系数：0.5（半凯利）
    - 最大仓位：30%
    - 最小仓位：5%

适用行情：仓位管理
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth

# ============ 参数配置 ============
BASE_KELLY = 0.5                # 凯利系数（半凯利）
MIN_POSITION = 0.05             # 最小仓位
MAX_POSITION = 0.30             # 最大仓位
INITIAL_CAPITAL = 1000000       # 初始资金

# ============ 凯利公式 ============
def calculate_kelly(win_rate, profit_loss_ratio):
    """
    计算凯利公式仓位
    win_rate: 胜率 (0-1)
    profit_loss_ratio: 盈亏比
    """
    q = 1 - win_rate
    kelly = (profit_loss_ratio * win_rate - q) / profit_loss_ratio
    
    # 应用凯利系数
    kelly = kelly * BASE_KELLY
    
    # 限制仓位范围
    kelly = max(MIN_POSITION, min(MAX_POSITION, kelly))
    
    return kelly

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：凯利公式仓位管理器")
    
    # 模拟历史数据（实际应从数据库获取）
    # 示例：胜率 45%，盈亏比 2.0
    win_rate = 0.45
    profit_loss_ratio = 2.0
    
    # 计算推荐仓位
    recommended_kelly = calculate_kelly(win_rate, profit_loss_ratio)
    recommended_lots = int(INITIAL_CAPITAL * recommended_kelly / 4000)  # 假设螺纹钢每手4000元
    
    print(f"历史胜率: {win_rate*100:.1f}%")
    print(f"盈亏比: {profit_loss_ratio:.2f}")
    print(f"凯利仓位: {recommended_kelly*100:.1f}%")
    print(f"推荐手数: {recommended_lots}手")
    
    # 持续监控并更新仓位建议
    account = api.get_account()
    
    while True:
        api.wait_update()
        
        # 可以定期根据实际交易结果更新仓位
        # 这里仅做示例展示
        
        current_equity = account.balance
        equity_change = (current_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL
        
        print(f"当前权益: {current_equity:.2f}, 变化: {equity_change*100:.2f}%")
    
    api.close()

if __name__ == "__main__":
    main()
