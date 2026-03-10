#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略编号: 17
策略名称: 风险敞口监控系统
生成日期: 2026-03-10
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
风险敞口监控系统用于实时监控投资组合的总风险敞口，包括多头敞口、空头敞口和净敞口。
当敞口超过预设阈值时，系统会自动触发预警或采取风险控制措施。

【策略参数】
- MONITORED_SYMBOLS: 监控的合约列表
- MAX_NET_EXPOSURE: 最大净敞口比例（默认50%）
- MAX_GROSS_EXPOSURE: 最大总敞口比例（默认80%）
- ALERT_THRESHOLD: 预警阈值

【风险提示】
本策略仅用于风险监控，不进行实际交易操作。投资者需根据自身风险承受能力设置合理的阈值。
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqAccount
import pandas as pd
from datetime import datetime
import json

# ============ 参数配置 ============
MONITORED_SYMBOLS = [
    "SHFE.rb2405",  # 螺纹钢
    "SHFE.hc2405",  # 热卷
    "DCE.m2405",    # 豆粕
    "CZCE.rm2405",  # 菜粕
    "CFFEX IF2405"  # 股指期货
]
MAX_NET_EXPOSURE = 0.5      # 最大净敞口比例 50%
MAX_GROSS_EXPOSURE = 0.8    # 最大总敞口比例 80%
ALERT_THRESHOLD = 0.4       # 预警阈值 40%


class RiskExposureMonitor:
    """风险敞口监控类"""
    
    def __init__(self, api, symbols):
        self.api = api
        self.symbols = symbols
        self.positions = {}
        
    def get_position_data(self):
        """获取所有持仓数据"""
        positions = self.api.get_position()
        return positions
    
    def calculate_exposure(self, account_balance):
        """计算风险敞口"""
        long_exposure = 0.0
        short_exposure = 0.0
        
        for symbol in self.symbols:
            try:
                pos = self.api.get_position(symbol)
                if pos:
                    # 获取合约乘数和价格
                    quote = self.api.get_quote(symbol)
                    multiplier = quote.volume_multiple
                    
                    # 计算多头敞口
                    if pos.get("long_position", 0) > 0:
                        long_value = pos["long_position"] * multiplier * quote.last_price
                        long_exposure += long_value
                    
                    # 计算空头敞口
                    if pos.get("short_position", 0) > 0:
                        short_value = pos["short_position"] * multiplier * quote.last_price
                        short_exposure += short_value
            except Exception as e:
                print(f"获取{symbol}持仓失败: {e}")
        
        # 计算净敞口和总敞口
        net_exposure = abs(long_exposure - short_exposure) / account_balance
        gross_exposure = (long_exposure + short_exposure) / account_balance
        
        return {
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "net_exposure": net_exposure,
            "gross_exposure": gross_exposure,
            "account_balance": account_balance
        }
    
    def check_alerts(self, exposure_data):
        """检查是否触发预警"""
        alerts = []
        
        if exposure_data["net_exposure"] > MAX_NET_EXPOSURE:
            alerts.append(f"⚠️ 净敞口超限: {exposure_data['net_exposure']:.2%} > {MAX_NET_EXPOSURE:.2%}")
        
        if exposure_data["gross_exposure"] > MAX_GROSS_EXPOSURE:
            alerts.append(f"⚠️ 总敞口超限: {exposure_data['gross_exposure']:.2%} > {MAX_GROSS_EXPOSURE:.2%}")
        
        if exposure_data["net_exposure"] > ALERT_THRESHOLD:
            alerts.append(f"📊 净敞口预警: {exposure_data['net_exposure']:.2%} > {ALERT_THRESHOLD:.2%}")
        
        return alerts
    
    def generate_report(self, exposure_data, alerts):
        """生成风险报告"""
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║               风险敞口监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                 ║
╠══════════════════════════════════════════════════════════════╣
║ 账户余额: ¥{exposure_data['account_balance']:,.2f}                               ║
║ 多头敞口: ¥{exposure_data['long_exposure']:,.2f}                                ║
║ 空头敞口: ¥{exposure_data['short_exposure']:,.2f}                                ║
║ 净敞口比例: {exposure_data['net_exposure']:.2%}                                       ║
║ 总敞口比例: {exposure_data['gross_exposure']:.2%}                                       ║
╠══════════════════════════════════════════════════════════════╣"""
        
        if alerts:
            report += "\n║ 风险预警:                                                     ║"
            for alert in alerts:
                report += f"\n║   {alert:54s} ║"
        else:
            report += "\n║ 状态: ✅ 风险敞口正常                                         ║"
        
        report += "\n╚══════════════════════════════════════════════════════════════╝"
        return report


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("=" * 60)
    print("风险敞口监控系统启动")
    print("=" * 60)
    
    monitor = RiskExposureMonitor(api, MONITORED_SYMBOLS)
    
    # 获取账户信息
    account = api.get_account()
    account_balance = account.balance
    
    print(f"监控合约: {', '.join(MONITORED_SYMBOLS)}")
    print(f"账户余额: ¥{account_balance:,.2f}")
    print("-" * 60)
    
    # 计算敞口
    exposure_data = monitor.calculate_exposure(account_balance)
    
    # 检查预警
    alerts = monitor.check_alerts(exposure_data)
    
    # 生成报告
    report = monitor.generate_report(exposure_data, alerts)
    print(report)
    
    api.close()


if __name__ == "__main__":
    main()
