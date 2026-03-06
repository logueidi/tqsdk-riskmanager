#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略13 - 账户风控仪表盘
原理：
    实时监控账户风险指标
    包括：持仓风险、资金使用率、盈亏情况、保证金占用

参数：
    - 监控频率：10秒
    - 告警阈值：保证金率 < 20%

适用行情：全天候监控
作者：logueidi / tqsdk-riskmanager
"""

from tqsdk import TqApi, TqAuth, TqSim
import time

# ============ 参数配置 ============
CHECK_INTERVAL = 10               # 检查间隔（秒）
MARGIN_ALERT = 0.20               # 保证金率告警阈值
POSITION_LIMIT = 10               # 最大持仓合约数


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print("启动：账户风控仪表盘")
    
    while True:
        try:
            account = api.get_account()
            positions = api.get_position()
            
            # 计算关键指标
            margin_ratio = account["margin_ratio"]
            available = account["available"]
            balance = account["balance"]
            float_profit = account["float_profit"]
            
            # 持仓统计
            position_count = len([p for p in positions.values() if p.get("volume_long", 0) > 0 or p.get("volume_short", 0) > 0])
            
            # 资金使用率
            used_ratio = (balance - available) / balance if balance > 0 else 0
            
            print(f"\n{'='*40}")
            print(f"账户风控仪表盘")
            print(f"{'='*40}")
            print(f"账户权益: {balance:.2f}")
            print(f"可用资金: {available:.2f}")
            print(f"浮动盈亏: {float_profit:.2f}")
            print(f"资金使用率: {used_ratio*100:.2f}%")
            print(f"保证金率: {margin_ratio*100:.2f}%")
            print(f"持仓合约数: {position_count}/{POSITION_LIMIT}")
            
            # 风控告警
            if margin_ratio < MARGIN_ALERT:
                print(f"\n⚠️ 告警：保证金率低于 {MARGIN_ALERT*100}%！")
            
            if position_count > POSITION_LIMIT:
                print(f"\n⚠️ 告警：持仓合约数超过限制！")
            
            print(f"{'='*40}\n")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(CHECK_INTERVAL)
    
    api.close()


if __name__ == "__main__":
    main()
