#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
流动性风险管理器 (Liquidity Risk Manager)
监控投资组合流动性风险，支持持仓限额、流动性预警和自动减仓

Author: TqSdk RiskManager
Update: 2026-03-13
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


class LiquidityRiskManager:
    """流动性风险管理器"""
    
    def __init__(self, 
                 daily_volume_threshold: float = 0.05,
                 position_limit_pct: float = 0.1,
                 liquidation_window: int = 5):
        """
        初始化流动性风险管理器
        
        Args:
            daily_volume_threshold: 日成交量阈值（持仓不超过日均成交量的此比例）
            position_limit_pct: 单品种持仓上限（占组合百分比）
            liquidation_window: 减仓窗口期（天）
        """
        self.daily_volume_threshold = daily_volume_threshold
        self.position_limit_pct = position_limit_pct
        self.liquidation_window = liquidation_window
        
        self.positions = {}  # 当前持仓
        self.volume_history = defaultdict(list)  # 成交量历史
        self.liquidity_warnings = []
        self.position_limits = {}
        
    def add_position(self, symbol: str, quantity: float, 
                     current_price: float):
        """添加持仓"""
        self.positions[symbol] = {
            'quantity': quantity,
            'current_price': current_price,
            'value': quantity * current_price
        }
        
    def add_volume_data(self, symbol: str, volumes: List[float]):
        """添加成交量数据"""
        self.volume_history[symbol] = volumes
        
    def calculate_average_daily_volume(self, symbol: str, 
                                        lookback: int = 20) -> float:
        """计算平均日成交量"""
        if symbol not in self.volume_history:
            return 0.0
            
        volumes = self.volume_history[symbol][-lookback:]
        return np.mean(volumes) if volumes else 0.0
        
    def calculate_position_liquidity_ratio(self, symbol: str) -> float:
        """
        计算持仓流动性比率
        
        Returns:
            流动性比率（持仓量/日均成交量）
        """
        if symbol not in self.positions:
            return 0.0
            
        position_qty = abs(self.positions[symbol]['quantity'])
        adv = self.calculate_average_daily_volume(symbol)
        
        if adv == 0:
            return float('inf')  # 无成交量数据
            
        return position_qty / adv
        
    def calculate_days_to_liquidate(self, symbol: str) -> float:
        """
        计算清仓所需天数
        
        Returns:
            预计清仓天数
        """
        liquidity_ratio = self.calculate_position_liquidity_ratio(symbol)
        
        if liquidity_ratio == float('inf'):
            return -1  # 无法估算
            
        # 考虑流动性窗口
        return liquidity_ratio * self.daily_volume_threshold
        
    def calculate_slippage_estimate(self, symbol: str,
                                    quantity: Optional[float] = None) -> float:
        """
        估计滑点
        
        Args:
            quantity: 平仓数量（默认当前持仓）
            
        Returns:
            预估滑点（百分比）
        """
        if symbol not in self.positions:
            return 0.0
            
        qty = quantity if quantity is not None else abs(self.positions[symbol]['quantity'])
        liquidity_ratio = qty / max(self.calculate_average_daily_volume(symbol), 1)
        
        # 简化的滑点模型
        if liquidity_ratio < 0.01:
            slippage = 0.001  # 0.1%
        elif liquidity_ratio < 0.05:
            slippage = 0.002  # 0.2%
        elif liquidity_ratio < 0.1:
            slippage = 0.005  # 0.5%
        elif liquidity_ratio < 0.2:
            slippage = 0.01  # 1%
        elif liquidity_ratio < 0.5:
            slippage = 0.02  # 2%
        else:
            slippage = 0.05  # 5%
            
        return slippage
        
    def check_position_limits(self, portfolio_value: float) -> Dict[str, Dict]:
        """
        检查持仓限额
        
        Args:
            portfolio_value: 组合总市值
            
        Returns:
            限额检查结果
        """
        results = {}
        
        for symbol, pos in self.positions.items():
            position_value = pos['value']
            position_pct = position_value / max(portfolio_value, 1)
            
            adv = self.calculate_average_daily_volume(symbol)
            liquidity_ratio = self.calculate_position_liquidity_ratio(symbol)
            
            # 检查各种限制
            limit_status = 'OK'
            warnings = []
            
            if position_pct > self.position_limit_pct:
                limit_status = 'OVER_LIMIT'
                warnings.append(f"持仓占比 {position_pct:.2%} 超过限制 {self.position_limit_pct:.2%}")
                
            if liquidity_ratio > self.daily_volume_threshold * 10:
                limit_status = 'LIQUIDITY_RISK'
                warnings.append(f"流动性比率 {liquidity_ratio:.2f} 过高")
                
            days_to_liquidate = self.calculate_days_to_liquidate(symbol)
            if days_to_liquidate > self.liquidation_window:
                limit_status = 'LIQUIDATION_RISK'
                warnings.append(f"预计清仓天数 {days_to_liquidate:.1f} 天超过窗口期 {self.liquidation_window}")
                
            results[symbol] = {
                'position_value': position_value,
                'position_pct': position_pct,
                'avg_daily_volume': adv,
                'liquidity_ratio': liquidity_ratio,
                'days_to_liquidate': days_to_liquidate,
                'slippage_estimate': self.calculate_slippage_estimate(symbol),
                'status': limit_status,
                'warnings': warnings
            }
            
        return results
        
    def calculate_liquidation_cost(self, 
                                   portfolio_value: float,
                                   urgency_level: str = 'NORMAL') -> Dict:
        """
        计算整体清仓成本
        
        Args:
            portfolio_value: 组合市值
            urgency_level: 紧急程度 (NORMAL, HIGH, EXTREME)
            
        Returns:
            清仓成本分析
        """
        total_slippage = 0
        total_value = 0
        high_risk_positions = []
        
        slippage_multiplier = {
            'NORMAL': 1.0,
            'HIGH': 1.5,
            'EXTREME': 2.0
        }.get(urgency_level, 1.0)
        
        for symbol, pos in self.positions.items():
            slippage = self.calculate_slippage_estimate(symbol)
            position_value = pos['value']
            
            total_slippage += position_value * slippage * slippage_multiplier
            total_value += position_value
            
            if slippage > 0.01:
                high_risk_positions.append({
                    'symbol': symbol,
                    'value': position_value,
                    'slippage': slippage
                })
                
        liquidation_cost_pct = total_slippage / max(total_value, 1)
        
        return {
            'total_value': total_value,
            'estimated_slippage': total_slippage,
            'liquidation_cost_pct': liquidation_cost_pct,
            'liquidation_cost_value': total_value * liquidation_cost_pct,
            'high_risk_positions': high_risk_positions,
            'urgency_level': urgency_level,
            'positions_count': len(self.positions)
        }
        
    def generate_rebalancing_recommendations(self, 
                                             portfolio_value: float) -> List[Dict]:
        """
        生成调仓建议
        
        Args:
            portfolio_value: 组合市值
            
        Returns:
            调仓建议列表
        """
        recommendations = []
        
        # 检查流动性风险
        for symbol, pos in self.positions.items():
            adv = self.calculate_average_daily_volume(symbol)
            
            if adv == 0:
                recommendations.append({
                    'symbol': symbol,
                    'action': 'REDUCE',
                    'reason': '无成交量数据，无法评估流动性',
                    'priority': 'HIGH',
                    'suggested_reduction': 1.0  # 建议全部平仓
                })
                continue
                
            liquidity_ratio = self.calculate_position_liquidity_ratio(symbol)
            
            if liquidity_ratio > self.daily_volume_threshold * 10:
                # 严重流动性风险
                reduction = min(1.0, (liquidity_ratio - self.daily_volume_threshold * 5) / liquidity_ratio)
                recommendations.append({
                    'symbol': symbol,
                    'action': 'REDUCE',
                    'reason': f'流动性比率 {liquidity_ratio:.2f} 过高',
                    'priority': 'HIGH',
                    'suggested_reduction': reduction
                })
            elif liquidity_ratio > self.daily_volume_threshold * 5:
                recommendations.append({
                    'symbol': symbol,
                    'action': 'MONITOR',
                    'reason': f'流动性比率 {liquidity_ratio:.2f} 需关注',
                    'priority': 'MEDIUM',
                    'suggested_reduction': 0.0
                })
                
        # 检查持仓集中度
        for symbol, pos in self.positions.items():
            position_pct = pos['value'] / max(portfolio_value, 1)
            
            if position_pct > self.position_limit_pct * 1.5:
                recommendations.append({
                    'symbol': symbol,
                    'action': 'REDUCE',
                    'reason': f'持仓占比 {position_pct:.2%} 远超限制',
                    'priority': 'HIGH',
                    'suggested_reduction': (position_pct - self.position_limit_pct) / position_pct
                })
            elif position_pct > self.position_limit_pct:
                recommendations.append({
                    'symbol': symbol,
                    'action': 'REDUCE',
                    'reason': f'持仓占比 {position_pct:.2%} 超过限制',
                    'priority': 'MEDIUM',
                    'suggested_reduction': (position_pct - self.position_limit_pct) / position_pct
                })
                
        return recommendations
        
    def get_liquidity_score(self) -> float:
        """
        获取整体流动性评分 (0-100)
        
        Returns:
            流动性评分
        """
        if not self.positions:
            return 100.0
            
        scores = []
        
        for symbol in self.positions.keys():
            ratio = self.calculate_position_liquidity_ratio(symbol)
            
            if ratio < 0.01:
                score = 100
            elif ratio < 0.05:
                score = 90 - (ratio - 0.01) * 250
            elif ratio < 0.1:
                score = 80 - (ratio - 0.05) * 600
            elif ratio < 0.2:
                score = 70 - (ratio - 0.1) * 400
            elif ratio < 0.5:
                score = 50 - (ratio - 0.2) * 100
            else:
                score = max(0, 30 - (ratio - 0.5) * 40)
                
            scores.append(score)
            
        return np.mean(scores)
        
    def generate_risk_report(self, portfolio_value: float) -> str:
        """生成流动性风险报告"""
        score = self.get_liquidity_score()
        limits = self.check_position_limits(portfolio_value)
        liquidation = self.calculate_liquidation_cost(portfolio_value)
        recommendations = self.generate_rebalancing_recommendations(portfolio_value)
        
        report = f"""
========================================
      流动性风险管理报告
========================================
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

【流动性评分】
- 综合评分: {score:.1f}/100
- 评级: {'优秀' if score >= 80 else '良好' if score >= 60 else '一般' if score >= 40 else '危险'}

【持仓流动性分析】
"""
        
        for symbol, info in limits.items():
            report += f"""
{symbol}:
  - 持仓市值: ¥{info['position_value']:,.0f}
  - 持仓占比: {info['position_pct']:.2%}
  - 日均成交量: {info['avg_daily_volume']:,.0f}
  - 流动性比率: {info['liquidity_ratio']:.2f}
  - 预计清仓天数: {info['days_to_liquidate']:.1f}天
  - 预估滑点: {info['slippage_estimate']:.2%}
  - 状态: {info['status']}
"""
        
        report += f"""
【清仓成本分析】
- 组合总市值: ¥{liquidation['total_value']:,.0f}
- 预估滑点成本: ¥{liquidation['estimated_slippage']:,.0f}
- 清仓成本比例: {liquidation['liquidation_cost_pct']:.2%}
- 紧急程度: {liquidation['urgency_level']}

【调仓建议】
"""
        
        for rec in recommendations:
            report += f"- {rec['symbol']}: {rec['action']} - {rec['reason']} (优先级: {rec['priority']})\n"
            
        report += "========================================\n"
        
        return report


class PositionSizeOptimizer:
    """基于流动性的仓位优化器"""
    
    def __init__(self, target_liquidity_ratio: float = 0.1):
        self.target_liquidity_ratio = target_liquidity_ratio
        self.volume_estimates = {}
        
    def estimate_optimal_position(self, symbol: str,
                                  avg_daily_volume: float,
                                  risk_per_trade: float = 0.02) -> Dict:
        """
        估算最优持仓
        
        Args:
            symbol: 品种代码
            avg_daily_volume: 平均日成交量
            risk_per_trade: 每笔交易风险比例
            
        Returns:
            最优持仓建议
        """
        # 基于流动性的仓位限制
        max_position_by_volume = avg_daily_volume * self.target_liquidity_ratio
        
        # 基于风险的仓位
        # 假设风险以金额表示
        max_position_by_risk = risk_per_trade * 1000000  # 简化
        
        optimal_position = min(max_position_by_volume, max_position_by_risk)
        
        # 计算建议分批建仓
        batches = max(1, int(optimal_position / max_position_by_volume) + 1)
        
        return {
            'symbol': symbol,
            'avg_daily_volume': avg_daily_volume,
            'max_position_by_volume': max_position_by_volume,
            'optimal_position': optimal_position,
            'recommended_batches': batches,
            'days_to_build': batches
        }


def main():
    """主函数 - 演示用法"""
    # 创建流动性风险管理器
    lrm = LiquidityRiskManager(
        daily_volume_threshold=0.05,
        position_limit_pct=0.1,
        liquidation_window=5
    )
    
    # 模拟添加持仓
    lrm.add_position('SHFE.rb2405', 100, 3800)
    lrm.add_position('DCE.m2405', 200, 2800)
    lrm.add_position('CZCE.CF2405', 50, 15000)
    
    # 模拟成交量数据
    np.random.seed(42)
    for symbol in ['SHFE.rb2405', 'DCE.m2405', 'CZCE.CF2405']:
        volumes = np.random.randint(50000, 200000, 60)
        lrm.add_volume_data(symbol, volumes.tolist())
    
    # 组合市值
    portfolio_value = 10000000  # 1000万
    
    # 生成报告
    report = lrm.generate_risk_report(portfolio_value)
    print(report)
    
    # 获取调仓建议
    recommendations = lrm.generate_rebalancing_recommendations(portfolio_value)
    print(f"调仓建议数量: {len(recommendations)}")
    
    # 仓位优化器
    optimizer = PositionSizeOptimizer(target_liquidity_ratio=0.1)
    optimal = optimizer.estimate_optimal_position(
        'SHFE.rb2405',
        avg_daily_volume=100000,
        risk_per_trade=0.02
    )
    print(f"最优持仓建议: {optimal}")


if __name__ == "__main__":
    main()
