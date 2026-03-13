#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
尾部风险对冲策略 (Tail Risk Hedge Strategy)
基于极端市场条件预测的动态对冲策略，使用期权保护投资组合

Author: TqSdk RiskManager
Update: 2026-03-13
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats, optimize
import warnings
warnings.filterwarnings('ignore')


class TailRiskHedge:
    """尾部风险对冲策略"""
    
    def __init__(self, hedge_ratio: float = 0.3,
                 var_threshold: float = 0.95,
                 hedge_lookback: int = 60,
                 rebalance_threshold: float = 0.1):
        """
        初始化尾部风险对冲器
        
        Args:
            hedge_ratio: 对冲比例 (0-1)
            var_threshold: VaR阈值，用于触发对冲
            hedge_lookback: 回看周期（天）
            rebalance_threshold: 调仓阈值
        """
        self.hedge_ratio = hedge_ratio
        self.var_threshold = var_threshold
        self.hedge_lookback = hedge_lookback
        self.rebalance_threshold = rebalance_threshold
        
        self.returns_history = []
        self.current_hedge = 0.0
        self.last_rebalance = None
        self.garch_params = None
        
    def add_return(self, return_value: float):
        """添加收益率数据"""
        self.returns_history.append(return_value)
        if len(self.returns_history) > self.hedge_lookback * 2:
            self.returns_history.pop(0)
            
    def estimate_garch(self, returns: np.ndarray) -> Tuple[float, float, float]:
        """
        估计GARCH(1,1)模型参数
        
        Args:
            returns: 收益率序列
            
        Returns:
            (omega, alpha, beta) GARCH参数
        """
        from scipy.optimize import minimize
        
        def garch_likelihood(params):
            omega, alpha, beta = params
            if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
                return 1e10
            
            n = len(returns)
            h = np.var(returns)  # 初始化方差
            log_likelihood = 0
            
            for i in range(1, n):
                h = omega + alpha * returns[i-1]**2 + beta * h
                if h <= 0:
                    return 1e10
                log_likelihood += 0.5 * (np.log(2 * np.pi) + np.log(h) + returns[i]**2 / h)
                
            return log_likelihood
        
        # 初始参数
        initial_params = [0.01, 0.05, 0.9]
        bounds = [(1e-6, 1), (0.001, 0.5), (0.5, 0.99)]
        
        result = minimize(garch_likelihood, initial_params, method='L-BFGS-B', bounds=bounds)
        
        if result.success:
            return result.x
        return (0.01, 0.05, 0.9)  # 默认参数
        
    def calculate_conditional_vol(self, returns: np.ndarray) -> float:
        """计算条件波动率"""
        if len(returns) < 20:
            return np.std(returns) if len(returns) > 1 else 0.01
            
        omega, alpha, beta = self.estimate_garch(returns)
        
        # 计算最后期限的条件方差
        h = np.var(returns)
        for i in range(1, len(returns)):
            h = omega + alpha * returns[-i-1]**2 + beta * h
            
        return np.sqrt(h)
        
    def calculate_var(self, returns: np.ndarray, 
                     confidence: float = 0.95) -> float:
        """
        计算历史模拟法VaR
        
        Args:
            returns: 收益率序列
            confidence: 置信水平
            
        Returns:
            VaR值
        """
        if len(returns) < 20:
            return np.std(returns) * 1.645  # 简化估计
            
        var = np.percentile(returns, (1 - confidence) * 100)
        return abs(var)
        
    def calculate_cvar(self, returns: np.ndarray,
                      confidence: float = 0.95) -> float:
        """计算条件VaR (Expected Shortfall)"""
        var = self.calculate_var(returns, confidence)
        tail_returns = returns[returns <= -var]
        
        if len(tail_returns) == 0:
            return var
            
        return abs(np.mean(tail_returns))
        
    def calculate_tail_probability(self, returns: np.ndarray,
                                   threshold: float = -0.02) -> float:
        """
        计算收益率低于阈值的概率（使用GARCH模型）
        
        Args:
            returns: 收益率序列
            threshold: 阈值
            
        Returns:
            尾部概率
        """
        cond_vol = self.calculate_conditional_vol(returns)
        
        if cond_vol == 0:
            return 0.5
            
        # 计算标准化残差
        z_score = (threshold - np.mean(returns)) / cond_vol
        
        # 使用t分布计算尾部概率
        t_df = max(3, len(returns) - 1)  # t分布自由度
        tail_prob = stats.t.cdf(z_score, df=t_df)
        
        return tail_prob
        
    def calculate_hedge_signal(self) -> Dict:
        """
        计算对冲信号
        
        Returns:
            对冲信号字典
        """
        if len(self.returns_history) < 30:
            return {
                'hedge_position': 0.0,
                'var': 0.0,
                'cvar': 0.0,
                'tail_prob': 0.0,
                'volatility': 0.0,
                'signal': 'WARMUP'
            }
            
        returns = np.array(self.returns_history[-self.hedge_lookback:])
        
        var_95 = self.calculate_var(returns, 0.95)
        var_99 = self.calculate_var(returns, 0.99)
        cvar_95 = self.calculate_cvar(returns, 0.95)
        tail_prob = self.calculate_tail_probability(returns)
        volatility = self.calculate_conditional_vol(returns)
        
        # 生成对冲信号
        if var_99 > 0.05 or tail_prob > 0.1:
            signal = 'STRONG_HEDGE'
            hedge_position = min(self.hedge_ratio * 1.5, 1.0)
        elif var_95 > 0.03 or tail_prob > 0.05:
            signal = 'MODERATE_HEDGE'
            hedge_position = self.hedge_ratio
        elif var_95 > 0.02:
            signal = 'LIGHT_HEDGE'
            hedge_position = self.hedge_ratio * 0.5
        else:
            signal = 'NO_HEDGE'
            hedge_position = 0.0
            
        # 检查是否需要调仓
        if self.current_hedge > 0:
            change = abs(hedge_position - self.current_hedge) / max(self.current_hedge, 0.01)
            if change < self.rebalance_threshold:
                hedge_position = self.current_hedge
                signal = 'HOLD'
                
        self.current_hedge = hedge_position
        self.last_rebalance = datetime.now()
        
        return {
            'hedge_position': hedge_position,
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'tail_prob': tail_prob,
            'volatility': volatility,
            'signal': signal,
            'timestamp': datetime.now().isoformat()
        }
        
    def get_option_hedge_details(self, 
                                 underlying_price: float,
                                 risk_free_rate: float = 0.03) -> Dict:
        """
        计算期权对冲详细参数
        
        Args:
            underlying_price: 标的价格
            risk_free_rate: 无风险利率
            
        Returns:
            期权对冲参数
        """
        signal = self.calculate_hedge_signal()
        
        if signal['hedge_position'] == 0:
            return {
                'hedge_type': 'NONE',
                'option_type': None,
                'strike_ratio': None,
                'premium': 0.0,
                'protection_level': 0.0
            }
            
        # 简化：使用虚值看跌期权进行保护
        vol = signal['volatility']
        
        # 假设使用10%虚值看跌期权
        strike_ratio = 0.90
        
        # Black-Scholes 简化计算
        s = underlying_price
        k = underlying_price * strike_ratio
        t = 30 / 365  # 30天到期
        r = risk_free_rate
        sigma = vol
        
        d1 = (np.log(s/k) + (r + 0.5*sigma**2)*t) / (sigma * np.sqrt(t))
        d2 = d1 - sigma * np.sqrt(t)
        
        # 看跌期权价格
        put_price = k * np.exp(-r*t) * stats.norm.cdf(-d2) - s * stats.norm.cdf(-d1)
        
        # 需要的期权数量（简化计算）
        protection_level = signal['hedge_position'] * self.hedge_ratio
        contract_value = underlying_price * 10  # 假设每手10吨
        num_contracts = (underlying_price * protection_level * 100) / (put_price * 10)
        
        return {
            'hedge_type': 'PUT_OPTIONS',
            'option_type': 'PUT',
            'strike_ratio': strike_ratio,
            'expiry_days': 30,
            'premium': put_price,
            'num_contracts': int(num_contracts),
            'protection_level': protection_level,
            'estimated_cost': put_price * num_contracts * 10
        }
        
    def generate_risk_report(self) -> str:
        """生成风险报告"""
        signal = self.calculate_hedge_signal()
        
        report = f"""
========================================
        尾部风险对冲策略报告
========================================
生成时间: {signal.get('timestamp', 'N/A')}

【风险指标】
- 95% VaR: {signal.get('var_95', 0):.4f} ({signal.get('var_95', 0)*100:.2f}%)
- 99% VaR: {signal.get('var_99', 0):.4f} ({signal.get('var_99', 0)*100:.2f}%)
- 95% CVaR: {signal.get('cvar_95', 0):.4f} ({signal.get('cvar_95', 0)*100:.2f}%)
- 尾部概率: {signal.get('tail_prob', 0):.4f} ({signal.get('tail_prob', 0)*100:.2f}%)
- 条件波动率: {signal.get('volatility', 0):.4f} ({signal.get('volatility', 0)*100:.2f}%)

【对冲状态】
- 当前对冲比例: {signal.get('hedge_position', 0):.2%}
- 信号: {signal.get('signal', 'N/A')}
- 对冲仓位变化: {self.rebalance_threshold*100:.0f}% 阈值

========================================
"""
        return report


class DynamicHedgeOptimizer:
    """动态对冲优化器"""
    
    def __init__(self, target_cvar: float = 0.05):
        self.target_cvar = target_cvar
        self.hedge_strategies = {}
        self.optimization_history = []
        
    def add_strategy_returns(self, strategy_name: str, returns: np.ndarray):
        """添加策略收益率"""
        self.hedge_strategies[strategy_name] = returns
        
    def optimize_hedge_ratio(self) -> Tuple[float, Dict]:
        """
        优化对冲比例
        
        Returns:
            (最优对冲比例, 优化详情)
        """
        if len(self.hedge_strategies) < 2:
            return 0.3, {}
            
        strategies = list(self.hedge_strategies.keys())
        
        # 假设使用期货对冲
        hedge_returns = np.zeros(len(self.hedge_strategies[strategies[0]]))
        
        for strategy in strategies:
            hedge_returns += self.hedge_strategies[strategy]
            
        hedge_returns /= len(strategies)
        
        # 计算不同对冲比例下的CVaR
        best_ratio = 0.3
        best_cvar = float('inf')
        
        for ratio in np.arange(0, 1.05, 0.05):
            hedged_returns = (1 - ratio) * hedge_returns
            
            if len(hedged_returns) > 20:
                var = np.percentile(hedged_returns, 5)
                cvar = abs(np.mean(hedged_returns[hedged_returns <= var]))
                
                if cvar <= self.target_cvar and cvar < best_cvar:
                    best_cvar = cvar
                    best_ratio = ratio
                    
        self.optimization_history.append({
            'timestamp': datetime.now(),
            'best_ratio': best_ratio,
            'best_cvar': best_cvar
        })
        
        details = {
            'strategies': strategies,
            'optimization_steps': len(np.arange(0, 1.05, 0.05)),
            'target_cvar': self.target_cvar,
            'achieved_cvar': best_cvar
        }
        
        return best_ratio, details


def main():
    """主函数 - 演示用法"""
    # 创建尾部风险对冲器
    hedge = TailRiskHedge(
        hedge_ratio=0.3,
        var_threshold=0.95,
        hedge_lookback=60
    )
    
    # 模拟添加收益率数据
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 100)
    
    for ret in returns:
        hedge.add_return(ret)
        
    # 获取对冲信号
    signal = hedge.calculate_hedge_signal()
    print(f"对冲信号: {signal}")
    
    # 生成风险报告
    report = hedge.generate_risk_report()
    print(report)
    
    # 计算期权对冲详情
    option_details = hedge.get_option_hedge_details(underlying_price=4000)
    print(f"期权对冲详情: {option_details}")
    
    # 优化器示例
    optimizer = DynamicHedgeOptimizer(target_cvar=0.03)
    optimizer.add_strategy_returns('strategy_1', returns)
    optimizer.add_strategy_returns('strategy_2', np.random.normal(0.002, 0.015, 100))
    
    best_ratio, details = optimizer.optimize_hedge_ratio()
    print(f"最优对冲比例: {best_ratio:.2%}")
    print(f"优化详情: {details}")


if __name__ == "__main__":
    main()
