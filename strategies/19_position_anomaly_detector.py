#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略编号: 19
策略名称: 仓位异常检测器
生成日期: 2026-03-11
仓库地址: tqsdk-riskmanager
================================================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【TqSdk 简介】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TqSdk（天勤量化 SDK）是由信易科技（北京）有限公司开发的专业期货量化交易框架，
完全免费开源（Apache 2.0 协议），基于 Python 语言设计，支持 Python 3.6+ 环境。
TqSdk 已服务于数万名国内期货量化投资者，是国内使用最广泛的期货量化框架之一。

TqSdk 核心能力包括：

1. **统一行情接口**：对接国内全部7大期货交易所（SHFE/DCE/CZCE/CFFEX/INE/GFEX）
   及主要期权品种，统一的 get_quote / get_kline_serial 接口，告别繁琐的协议适配；

2. **高性能数据推送**：天勤服务器行情推送延迟通常在5ms以内，Tick 级数据实时到达，
   K线自动合并，支持自定义周期（秒/分钟/小时/日/周/月）；

3. **同步式编程范式**：独特的 wait_update() + is_changing() 设计，策略代码像
   写普通Python一样自然流畅，无需掌握异步编程，大幅降低开发门槛；

4. **完整回测引擎**：内置 TqBacktest 回测模式，历史数据精确到Tick级别，
   支持滑点、手续费等真实市场参数，回测结果可信度高；

5. **实盘/模拟一键切换**：代码结构不变，仅替换 TqApi 初始化参数即可从
   模拟盘切换至实盘，极大降低策略上线风险；

6. **多账户并发**：支持同时连接多个期货账户，适合机构投资者和量化团队；

7. **活跃生态**：官方提供策略示例库、在线文档、量化社区论坛，更新维护活跃。

官网: https://www.shinnytech.com/tianqin/
文档: https://doc.shinnytech.com/tqsdk/latest/
GitHub: https://github.com/shinnytech/tqsdk-python
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】
仓位异常检测器用于实时监控账户持仓状态，检测异常情况如：
- 仓位超过预设上限
- 单一合约仓位占比过高
- 持仓数量异常变化（非计划交易）
- 保证金占用超过预算

【策略参数】
- MAX_POSITION_PERCENT: 单合约最大仓位占比
- MAX_TOTAL_POSITION: 总仓位上限
- MAX_MARGIN_RATIO: 最大保证金占比
- POSITION_CHANGE_THRESHOLD: 仓位变化阈值

【风险提示】
本策略仅用于监控和预警，不执行实际交易。需配合人工干预或风控系统使用。
================================================================================
"""

from tqsdk import TqApi, TqAuth
import pandas as pd
from datetime import datetime

# ============ 参数配置 ============
MAX_POSITION_PERCENT = 30.0    # 单合约最大仓位占比 (%)
MAX_TOTAL_POSITION = 80.0      # 总仓位上限 (%)
MAX_MARGIN_RATIO = 70.0        # 最大保证金占比 (%)
POSITION_CHANGE_THRESHOLD = 50 # 仓位变化预警阈值 (手)


class PositionAnomalyDetector:
    """仓位异常检测器"""
    
    def __init__(self, api, account_id=None):
        self.api = api
        self.account_id = account_id
        self.baseline_positions = {}
        self.alerts = []
        
    def get_account_info(self):
        """获取账户信息"""
        account = self.api.get_account()
        return {
            'balance': account.balance,
            'available': account.available,
            'margin': account.margin,
            'position_profit': account.position_profit,
            'total_profit': account.float_profit + account.position_profit
        }
    
    def get_positions(self):
        """获取当前持仓"""
        positions = self.api.get_position()
        position_info = {}
        
        for symbol, pos in positions.items():
            if pos.volume_long_long != 0 or pos.volume_short != 0:
                position_info[symbol] = {
                    'long_volume': pos.volume_long_long,
                    'short_volume': pos.volume_short,
                    'net_volume': pos.volume_long_long - pos.volume_short,
                    'open_price': pos.open_price_long if pos.volume_long_long > pos.volume_short else pos.open_price_short,
                    'position_profit': pos.position_profit
                }
        return position_info
    
    def calculate_position_percent(self, positions):
        """计算各合约仓位占比"""
        account = self.api.get_account()
        total_equity = account.balance + account.position_profit
        
        if total_equity <= 0:
            return {}
        
        position_percent = {}
        for symbol, pos in positions.items():
            quote = self.api.get_quote(symbol)
            contract_value = quote.last_price * quote.volume_multiple
            position_value = contract_value * abs(pos['net_volume'])
            position_percent[symbol] = (position_value / total_equity) * 100
            
        return position_percent
    
    def check_total_position(self, position_percent):
        """检查总仓位是否超限"""
        total = sum(position_percent.values())
        if total > MAX_TOTAL_POSITION:
            return {
                'level': 'HIGH',
                'message': f"总仓位超限: {total:.1f}% (上限: {MAX_TOTAL_POSITION}%)"
            }
        elif total > MAX_TOTAL_POSITION * 0.8:
            return {
                'level': 'WARNING',
                'message': f"总仓位接近上限: {total:.1f}% (上限: {MAX_TOTAL_POSITION}%)"
            }
        return None
    
    def check_single_position(self, position_percent):
        """检查单合约仓位是否超限"""
        alerts = []
        for symbol, percent in position_percent.items():
            if percent > MAX_POSITION_PERCENT:
                alerts.append({
                    'level': 'HIGH',
                    'message': f"单合约仓位超限 {symbol}: {percent:.1f}% (上限: {MAX_POSITION_PERCENT}%)"
                })
            elif percent > MAX_POSITION_PERCENT * 0.8:
                alerts.append({
                    'level': 'WARNING',
                    'message': f"单合约仓位偏高 {symbol}: {percent:.1f}% (上限: {MAX_POSITION_PERCENT}%)"
                })
        return alerts
    
    def check_margin_ratio(self):
        """检查保证金占比"""
        account = self.api.get_account()
        total_equity = account.balance + account.position_profit
        
        if total_equity <= 0:
            return None
            
        margin_ratio = (account.margin / total_equity) * 100
        
        if margin_ratio > MAX_MARGIN_RATIO:
            return {
                'level': 'HIGH',
                'message': f"保证金占比超限: {margin_ratio:.1f}% (上限: {MAX_MARGIN_RATIO}%)"
            }
        elif margin_ratio > MAX_MARGIN_RATIO * 0.8:
            return {
                'level': 'WARNING',
                'message': f"保证金占比偏高: {margin_ratio:.1f}% (上限: {MAX_MARGIN_RATIO}%)"
            }
        return None
    
    def check_position_change(self, current_positions):
        """检查仓位异常变化"""
        alerts = []
        for symbol, pos in current_positions.items():
            current_vol = abs(pos['net_volume'])
            baseline_vol = self.baseline_positions.get(symbol, 0)
            change = current_vol - baseline_vol
            
            if abs(change) > POSITION_CHANGE_THRESHOLD:
                direction = "增加" if change > 0 else "减少"
                alerts.append({
                    'level': 'HIGH',
                    'message': f"仓位异常变化 {symbol}: {direction} {abs(change)}手"
                })
        return alerts
    
    def save_baseline(self, positions):
        """保存当前持仓作为基准"""
        self.baseline_positions = {symbol: abs(pos['net_volume']) 
                                     for symbol, pos in positions.items()}
    
    def detect_all(self):
        """执行全面检测"""
        alerts = []
        
        # 获取账户和持仓信息
        account_info = self.get_account_info()
        positions = self.get_positions()
        
        # 计算仓位占比
        position_percent = self.calculate_position_percent(positions)
        
        # 执行各项检测
        total_check = self.check_total_position(position_percent)
        if total_check:
            alerts.append(total_check)
            
        single_check = self.check_single_position(position_percent)
        alerts.extend(single_check)
        
        margin_check = self.check_margin_ratio()
        if margin_check:
            alerts.append(margin_check)
        
        # 如果有基准仓位，进行变化检测
        if self.baseline_positions:
            change_check = self.check_position_change(positions)
            alerts.extend(change_check)
        
        # 保存当前持仓作为基准
        self.save_baseline(positions)
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'account': account_info,
            'positions': positions,
            'position_percent': position_percent,
            'alerts': alerts
        }
    
    def generate_report(self):
        """生成检测报告"""
        result = self.detect_all()
        
        report = []
        report.append("=" * 60)
        report.append("仓位异常检测报告")
        report.append("=" * 60)
        report.append(f"检测时间: {result['timestamp']}")
        report.append("")
        
        # 账户信息
        report.append("【账户概览】")
        account = result['account']
        report.append(f"  账户权益: {account['balance']:.2f}")
        report.append(f"  可用资金: {account['available']:.2f}")
        report.append(f"  占用保证金: {account['margin']:.2f}")
        report.append(f"  持仓盈亏: {account['position_profit']:.2f}")
        report.append("")
        
        # 持仓信息
        report.append("【当前持仓】")
        if result['positions']:
            for symbol, pos in result['positions'].items():
                percent = result['position_percent'].get(symbol, 0)
                report.append(f"  {symbol}: {pos['net_volume']:+d}手 (占比: {percent:.1f}%)")
        else:
            report.append("  无持仓")
        report.append("")
        
        # 告警信息
        report.append("【告警信息】")
        if result['alerts']:
            for alert in result['alerts']:
                level_symbol = "⚠️" if alert['level'] == 'WARNING' else "🚨"
                report.append(f"  {level_symbol} [{alert['level']}] {alert['message']}")
        else:
            report.append("  无告警")
        report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)


def main():
    """主函数 - 实盘监控模式"""
    api = TqApi(auth=TqAuth("用户名", "密码"))
    
    detector = PositionAnomalyDetector(api)
    
    print("仓位异常检测器启动...")
    print("按 Ctrl+C 退出")
    print()
    
    try:
        while True:
            report = detector.generate_report()
            print(report)
            
            # 等待30秒后再次检测
            api.wait_update(30)
            
    except KeyboardInterrupt:
        print("\n检测器已停止")
    finally:
        api.close()


def backtest_demo():
    """回测模式演示"""
    from tqsdk import TqBacktest
    
    api = TqBacktest(
        front_broker="经纪商代码",
        broker_id="经纪商ID",
        auth=TqAuth("用户名", "密码")
    )
    
    detector = PositionAnomalyDetector(api)
    
    # 运行回测
    while True:
        api.wait_update()
        if api.is_changing():
            report = detector.generate_report()
            print(report)


if __name__ == "__main__":
    # main()  # 实盘模式
    # backtest_demo()  # 回测模式
    print("仓位异常检测器模块")
    print("请根据需要选择运行模式")
