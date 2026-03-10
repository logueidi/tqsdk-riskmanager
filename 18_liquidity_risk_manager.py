#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略编号: 18
策略名称: 流动性风险管理器
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
流动性风险管理器用于监控合约的流动性状况，包括成交量、持仓量、买卖盘深度等指标。
当合约流动性不足时，系统会发出预警，避免在流动性不足时进行大额交易。

【策略参数】
- MONITORED_SYMBOLS: 监控的合约列表
- MIN_VOLUME: 最小成交量要求
- MIN_OPEN_INTEREST: 最小持仓量要求
- MIN_SPREAD: 最小买卖价差比例

【风险提示】
本策略仅用于流动性监控，不进行实际交易操作。投资者需根据自身需求设置合理的阈值。
================================================================================
"""

from tqsdk import TqApi, TqAuth
import pandas as pd
from datetime import datetime

# ============ 参数配置 ============
MONITORED_SYMBOLS = [
    "SHFE.rb2405",  # 螺纹钢
    "SHFE.hc2405",  # 热卷
    "DCE.m2405",    # 豆粕
    "CZCE.rm2405",  # 菜粕
    "CFFEX IF2405"  # 股指期货
]
MIN_VOLUME = 10000         # 最小成交量要求
MIN_OPEN_INTEREST = 50000  # 最小持仓量要求
MIN_SPREAD_RATIO = 0.005   # 最小买卖价差比例 (0.5%)


class LiquidityRiskManager:
    """流动性风险管理器"""
    
    def __init__(self, api, symbols):
        self.api = api
        self.symbols = symbols
        self.liquidity_data = {}
        
    def check_liquidity(self, symbol):
        """检查单个合约的流动性"""
        try:
            quote = self.api.get_quote(symbol)
            
            # 获取行情数据
            volume = quote.volume  # 成交量
            open_interest = quote.open_interest  # 持仓量
            bid_price = quote.bid_price1  # 买价
            ask_price = quote.ask_price1  # 卖价
            
            # 计算买卖价差
            if bid_price > 0 and ask_price > 0:
                spread = (ask_price - bid_price) / bid_price
            else:
                spread = float('inf')
            
            # 计算流动性得分
            liquidity_score = 0
            issues = []
            
            if volume < MIN_VOLUME:
                issues.append(f"成交量不足: {volume} < {MIN_VOLUME}")
                liquidity_score -= 1
            else:
                liquidity_score += 1
            
            if open_interest < MIN_OPEN_INTEREST:
                issues.append(f"持仓量不足: {open_interest} < {MIN_OPEN_INTEREST}")
                liquidity_score -= 1
            else:
                liquidity_score += 1
            
            if spread > MIN_SPREAD_RATIO:
                issues.append(f"买卖价差过大: {spread:.2%} > {MIN_SPREAD_RATIO:.2%}")
                liquidity_score -= 1
            else:
                liquidity_score += 1
            
            return {
                "symbol": symbol,
                "volume": volume,
                "open_interest": open_interest,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "spread": spread,
                "liquidity_score": liquidity_score,
                "issues": issues,
                "status": "✅ 正常" if liquidity_score >= 2 else "⚠️ 警告" if liquidity_score >= 0 else "❌ 危险"
            }
            
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "status": "❌ 错误"
            }
    
    def generate_report(self):
        """生成流动性报告"""
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║          流动性风险管理报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}             ║
╠══════════════════════════════════════════════════════════════╣
║ 合约           成交量     持仓量      买卖价差    状态          ║
╠══════════════════════════════════════════════════════════════╣"""
        
        all_issues = []
        
        for symbol in self.symbols:
            data = self.check_liquidity(symbol)
            
            if "error" in data:
                report += f"\n║ {symbol:14s} 获取数据失败                           ║"
            else:
                vol = data.get("volume", 0)
                oi = data.get("open_interest", 0)
                spread = data.get("spread", 0)
                status = data.get("status", "未知")
                
                report += f"\n║ {symbol:14s} {vol:9.0f} {oi:10.0f} {spread:8.2%} {status:12s}║"
                
                if data.get("issues"):
                    all_issues.extend(data["issues"])
        
        report += "\n╠══════════════════════════════════════════════════════════════╣"
        
        if all_issues:
            report += "\n║ 风险提示:                                                     ║"
            for issue in all_issues[:5]:  # 最多显示5条
                report += f"\n║   • {issue:52s} ║"
        else:
            report += "\n║ 状态: ✅ 所有合约流动性正常                                   ║"
        
        report += "\n╚══════════════════════════════════════════════════════════════╝"
        return report


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("=" * 60)
    print("流动性风险管理系统启动")
    print("=" * 60)
    
    manager = LiquidityRiskManager(api, MONITORED_SYMBOLS)
    
    print(f"监控合约: {', '.join(MONITORED_SYMBOLS)}")
    print(f"最小成交量: {MIN_VOLUME:,}")
    print(f"最小持仓量: {MIN_OPEN_INTEREST:,}")
    print(f"最大买卖价差: {MIN_SPREAD_RATIO:.2%}")
    print("-" * 60)
    
    # 生成流动性报告
    report = manager.generate_report()
    print(report)
    
    api.close()


if __name__ == "__main__":
    main()
