#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略编号: 20
策略名称: 风险预算管理器
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
风险预算管理器基于整体风险预算框架，为每个交易策略或合约分配风险配额。
通过动态调整风险预算，实现风险敞口的精确控制，确保整体风险在可承受范围内。

【策略参数】
- TOTAL_BUDGET: 总风险预算（元）
- MAX_RISK_PER_TRADE: 单笔交易最大风险
- MAX_RISK_PER_CONTRACT: 单合约最大风险
- VOLATILITY_WINDOW: 波动率计算窗口
- RISK_ADJUSTMENT_FACTOR: 风险调整因子

【风险提示】
本策略需要根据账户规模和风险承受能力合理设置预算参数。
================================================================================
"""

from tqsdk import TqApi, TqAuth
import pandas as pd
from datetime import datetime

# ============ 参数配置 ============
TOTAL_BUDGET = 100000.0          # 总风险预算（元）
MAX_RISK_PER_TRADE = 5000.0      # 单笔交易最大风险（元）
MAX_RISK_PER_CONTRACT = 20000.0  # 单合约最大风险（元）
VOLATILITY_WINDOW = 20          # 波动率计算窗口（天）
RISK_ADJUSTMENT_FACTOR = 0.8    # 风险调整因子（保守系数）


class RiskBudgetManager:
    """风险预算管理器"""
    
    def __init__(self, api, total_budget=None):
        self.api = api
        self.total_budget = total_budget or TOTAL_BUDGET
        self.used_budget = 0.0
        self.contract_budgets = {}
        self.risk_history = []
        
    def calculate_volatility(self, symbol, period=20):
        """计算合约波动率"""
        try:
            klines = self.api.get_kline_serial(symbol, 86400, period)
            if len(klines) < period:
                return None
            
            returns = []
            for i in range(1, len(klines)):
                ret = (klines[i]['close'] - klines[i-1]['close']) / klines[i-1]['close']
                returns.append(ret)
            
            if returns:
                volatility = pd.Series(returns).std()
                return volatility
        except:
            pass
        return None
    
    def estimate_risk_per_lot(self, symbol):
        """估算每手风险"""
        try:
            quote = self.api.get_quote(symbol)
            volatility = self.calculate_volatility(symbol, VOLATILITY_WINDOW)
            
            if volatility:
                # 基于波动率估算风险
                risk = quote.last_price * volatility * quote.volume_multiple
                return risk
            else:
                # 使用固定止损估算
                atr = self.calculate_atr(symbol)
                if atr:
                    return atr * quote.volume_multiple
        except:
            pass
        return 0
    
    def calculate_atr(self, symbol, period=14):
        """计算平均真实波幅 ATR"""
        try:
            klines = self.api.get_kline_serial(symbol, 86400, period + 1)
            if len(klines) < period + 1:
                return None
            
            tr_list = []
            for i in range(1, len(klines)):
                high = klines[i]['high']
                low = klines[i]['low']
                prev_close = klines[i-1]['close']
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_list.append(tr)
            
            return sum(tr_list) / len(tr_list)
        except:
            return None
    
    def calculate_contract_risk_limit(self, symbol):
        """计算单合约风险限额"""
        risk_per_lot = self.estimate_risk_per_lot(symbol)
        if risk_per_lot:
            max_lots = (MAX_RISK_PER_CONTRACT * RISK_ADJUSTMENT_FACTOR) / risk_per_lot
            return int(max_lots)
        return 10  # 默认最大10手
    
    def allocate_budget(self, symbols):
        """分配风险预算"""
        budgets = {}
        remaining = self.total_budget
        
        # 按波动率分配预算
        volatilities = {}
        for symbol in symbols:
            vol = self.calculate_volatility(symbol)
            volatilities[symbol] = vol if vol else 0.02  # 默认2%波动率
        
        total_vol = sum(volatilities.values())
        
        for symbol, vol in volatilities.items():
            if total_vol > 0:
                allocation = (vol / total_vol) * self.total_budget
            else:
                allocation = self.total_budget / len(symbols)
            
            # 应用风险调整因子
            adjusted_allocation = allocation * RISK_ADJUSTMENT_FACTOR
            budgets[symbol] = adjusted_allocation
        
        self.contract_budgets = budgets
        return budgets
    
    def get_current_risk(self, symbol):
        """获取当前持仓风险"""
        try:
            positions = self.api.get_position()
            pos = positions.get(symbol)
            
            if not pos or (pos.volume_long_long == 0 and pos.volume_short == 0):
                return 0
            
            quote = self.api.get_quote(symbol)
            entry_price = pos.open_price_long if pos.volume_long_long > 0 else pos.open_price_short
            current_price = quote.last_price
            
            # 假设2%止损计算风险
            risk_per_lot = entry_price * 0.02 * quote.volume_multiple
            volume = abs(pos.volume_long_long - pos.volume_short)
            
            return risk_per_lot * volume
            
        except:
            return 0
    
    def calculate_remaining_budget(self):
        """计算剩余预算"""
        total_used = 0
        for symbol, pos in self.api.get_position().items():
            if pos.volume_long_long > 0 or pos.volume_short > 0:
                total_used += self.get_current_risk(symbol)
        
        self.used_budget = total_used
        return self.total_budget - total_used
    
    def can_open_position(self, symbol, lots):
        """检查是否可以开仓"""
        risk_per_lot = self.estimate_risk_per_lot(symbol)
        proposed_risk = risk_per_lot * lots
        
        # 检查单笔风险
        if proposed_risk > MAX_RISK_PER_TRADE:
            return False, f"单笔风险超限: {proposed_risk:.0f}元 (上限: {MAX_RISK_PER_TRADE:.0f}元)"
        
        # 检查单合约风险
        current_risk = self.get_current_risk(symbol)
        if current_risk + proposed_risk > MAX_RISK_PER_CONTRACT:
            return False, f"单合约风险超限: {current_risk + proposed_risk:.0f}元 (上限: {MAX_RISK_PER_CONTRACT:.0f}元)"
        
        # 检查总预算
        remaining = self.calculate_remaining_budget()
        if proposed_risk > remaining:
            return False, f"剩余预算不足: {remaining:.0f}元 (需要: {proposed_risk:.0f}元)"
        
        return True, "可以开仓"
    
    def rebalance_budgets(self):
        """重新平衡预算"""
        positions = self.api.get_position()
        
        for symbol, pos in positions.items():
            if pos.volume_long_long > 0 or pos.volume_short > 0:
                current_risk = self.get_current_risk(symbol)
                budget = self.contract_budgets.get(symbol, 0)
                
                if current_risk > budget * 1.2:
                    return {
                        'action': 'REDUCE',
                        'symbol': symbol,
                        'message': f"风险超预算，需要减仓 {symbol}"
                    }
                elif current_risk < budget * 0.5:
                    return {
                        'action': 'INCREASE',
                        'symbol': symbol,
                        'message': f"风险低于预算，可以加仓 {symbol}"
                    }
        
        return None
    
    def generate_budget_report(self):
        """生成预算报告"""
        remaining = self.calculate_remaining_budget()
        
        report = []
        report.append("=" * 60)
        report.append("风险预算管理报告")
        report.append("=" * 60)
        report.append(f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 总体预算
        report.append("【总体预算】")
        report.append(f"  总预算: {self.total_budget:.2f}元")
        report.append(f"  已使用: {self.used_budget:.2f}元")
        report.append(f"  剩余: {remaining:.2f}元")
        report.append(f"  使用率: {(self.used_budget/self.total_budget*100):.1f}%")
        report.append("")
        
        # 各合约预算
        report.append("【各合约预算】")
        positions = self.api.get_position()
        
        if self.contract_budgets:
            for symbol, budget in self.contract_budgets.items():
                current_risk = self.get_current_risk(symbol)
                status = "正常" if current_risk <= budget else "超限"
                report.append(f"  {symbol}:")
                report.append(f"    预算: {budget:.2f}元")
                report.append(f"    当前风险: {current_risk:.2f}元")
                report.append(f"    状态: {status}")
        else:
            report.append("  未分配预算")
        
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def get_recommended_position(self, symbol, available_capital):
        """获取推荐仓位"""
        risk_per_lot = self.estimate_risk_per_lot(symbol)
        
        if risk_per_lot <= 0:
            return 0
        
        remaining = self.calculate_remaining_budget()
        contract_limit = self.calculate_contract_risk_limit(symbol)
        
        # 取最小限制
        max_by_budget = int(remaining / risk_per_lot)
        max_by_contract = contract_limit
        max_by_capital = int(available_capital / (self.api.get_quote(symbol).last_price * 
                                                     self.api.get_quote(symbol).volume_multiple))
        
        recommended = min(max_by_budget, max_by_contract, max_by_capital, 10)  # 最多10手
        
        return max(0, recommended)


def main():
    """主函数 - 实盘监控模式"""
    api = TqApi(auth=TqAuth("用户名", "密码"))
    
    manager = RiskBudgetManager(api)
    
    # 监控的合约列表
    monitored_symbols = [
        "SHFE.rb2405",
        "SHFE.hc2405", 
        "DCE.m2405",
        "CZCE.rm2405",
        "CFFEX IF2405"
    ]
    
    # 分配预算
    manager.allocate_budget(monitored_symbols)
    
    print("风险预算管理器启动...")
    print(manager.generate_budget_report())
    print("按 Ctrl+C 退出")
    
    try:
        while True:
            api.wait_update(30)
            if api.is_changing():
                print(manager.generate_budget_report())
                
                # 检查是否需要重新平衡
                rebalance = manager.rebalance_budgets()
                if rebalance:
                    print(f"\n⚠️ {rebalance['message']}")
                    
    except KeyboardInterrupt:
        print("\n管理器已停止")
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
    
    manager = RiskBudgetManager(api)
    
    # 运行回测
    while True:
        api.wait_update()
        if api.is_changing():
            print(manager.generate_budget_report())


if __name__ == "__main__":
    # main()  # 实盘模式
    # backtest_demo()  # 回测模式
    print("风险预算管理器模块")
    print("请根据需要选择运行模式")
