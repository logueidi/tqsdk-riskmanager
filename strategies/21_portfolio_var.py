#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
组合VaR计算器 (Portfolio VaR Calculator)
计算投资组合的Value at Risk，支持历史模拟法和蒙特卡洛方法

Author: TqSdk RiskManager
Update: 2026-03-12
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


class PortfolioVaR:
    """组合VaR计算器"""
    
    def __init__(self, confidence_levels: List[float] = [0.95, 0.99],
                 holding_period: int = 1):
        """
        初始化VaR计算器
        
        Args:
            confidence_levels: 置信水平列表
            holding_period: 持有期（天）
        """
        self.confidence_levels = confidence_levels
        self.holding_period = holding_period
        self.returns_history = {}
        self.positions = {}
        
    def add_position(self, symbol: str, position: float, price: float):
        """添加持仓"""
        self.positions[symbol] = {'position': position, 'price': price}
        
    def add_returns(self, symbol: str, returns: np.ndarray):
        """添加收益率历史"""
        self.returns_history[symbol] = returns
        
    def calculate_covariance_matrix(self) -> np.ndarray:
        """计算收益率协方差矩阵"""
        if not self.returns_history:
            raise ValueError("没有收益率数据")
            
        symbols = list(self.returns_history.keys())
        n = len(symbols)
        
        # 对齐收益率序列
        min_length = min(len(r) for r in self.returns_history.values())
        returns_array = np.zeros((min_length, n))
        
        for i, symbol in enumerate(symbols):
            returns_array[:, i] = self.returns_history[symbol][-min_length:]
            
        return np.cov(returns_array.T)
        
    def historical_var(self, portfolio_value: float,
                       returns: Optional[np.ndarray] = None) -> Dict[float, float]:
        """
        历史模拟法VaR
        
        Args:
            portfolio_value: 组合市值
            returns: 组合收益率序列
            
        Returns:
            各置信水平的VaR值
        """
        if returns is None:
            # 使用各品种收益率的加权组合
            symbols = list(self.returns_history.keys())
            if not symbols:
                raise ValueError("没有收益率数据")
                
            weights = np.array([
                self.positions.get(s, {}).get('position', 0) * 
                self.positions.get(s, {}).get('price', 1)
                for s in symbols
            ])
            weights = weights / weights.sum() if weights.sum() > 0 else np.ones(len(symbols)) / len(symbols)
            
            min_length = min(len(self.returns_history[s]) for s in symbols)
            weighted_returns = np.zeros(min_length)
            
            for i, symbol in enumerate(symbols):
                weighted_returns += weights[i] * self.returns_history[symbol][-min_length:]
                
            returns = weighted_returns
            
        var_results = {}
        for conf in self.confidence_levels:
            # 调整持有期
            adjusted_returns = returns * np.sqrt(self.holding_period)
            var_results[conf] = -np.percentile(adjusted_returns, 
                                                (1 - conf) * 100) * portfolio_value
            
        return var_results
        
    def parametric_var(self, portfolio_value: float,
                       mean_returns: Optional[np.ndarray] = None) -> Dict[float, float]:
        """
        参数法VaR（方差-协方差法）
        
        Args:
            portfolio_value: 组合市值
            mean_returns: 各品种平均收益率
            
        Returns:
            各置信水平的VaR值
        """
        cov_matrix = self.calculate_covariance_matrix()
        
        symbols = list(self.weights.keys())
        weights = np.array([self.weights.get(s, 0) for s in symbols])
        
        # 组合方差
        portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
        portfolio_std = np.sqrt(portfolio_variance)
        
        # 调整持有期
        adjusted_std = portfolio_std * np.sqrt(self.holding_period)
        
        var_results = {}
        for conf in self.confidence_levels:
            z_score = self._get_z_score(conf)
            var_results[conf] = z_score * adjusted_std * portfolio_value
            
        return var_results
        
    def monte_carlo_var(self, portfolio_value: float,
                        n_simulations: int = 10000,
                        random_state: Optional[int] = None) -> Dict[float, float]:
        """
        蒙特卡洛模拟VaR
        
        Args:
            portfolio_value: 组合市值
            n_simulations: 模拟次数
            random_state: 随机种子
            
        Returns:
            各置信水平的VaR值
        """
        if random_state:
            np.random.seed(random_state)
            
        cov_matrix = self.calculate_covariance_matrix()
        symbols = list(self.returns_history.keys())
        weights = np.array([
            self.positions.get(s, {}).get('position', 0) * 
            self.positions.get(s, {}).get('price', 1)
            for s in symbols
        ])
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(len(symbols)) / len(symbols)
        
        # 生成模拟收益率
        mean = np.zeros(len(symbols))
        simulated_returns = np.random.multivariate_normal(mean, cov_matrix, n_simulations)
        
        # 计算组合收益率
        portfolio_returns = np.dot(simulated_returns, weights)
        
        # 调整持有期
        portfolio_returns = portfolio_returns * np.sqrt(self.holding_period)
        
        var_results = {}
        for conf in self.confidence_levels:
            var_results[conf] = -np.percentile(portfolio_returns, 
                                                (1 - conf) * 100) * portfolio_value
            
        return var_results
        
    def calculate_cvar(self, portfolio_value: float,
                       returns: Optional[np.ndarray] = None) -> Dict[float, float]:
        """
        计算CVaR（条件VaR / Expected Shortfall）
        
        Args:
            portfolio_value: 组合市值
            returns: 收益率序列
            
        Returns:
            各置信水平的CVaR值
        """
        var_results = self.historical_var(portfolio_value, returns)
        
        if returns is None:
            symbols = list(self.returns_history.keys())
            min_length = min(len(self.returns_history[s]) for s in symbols)
            weights = np.ones(len(symbols)) / len(symbols)
            returns = np.zeros(min_length)
            for i, symbol in enumerate(symbols):
                returns += weights[i] * self.returns_history[symbol][-min_length:]
        
        cvar_results = {}
        for conf in self.confidence_levels:
            var_threshold = -var_results[conf] / portfolio_value
            tail_returns = returns[returns <= var_threshold]
            if len(tail_returns) > 0:
                cvar_results[conf] = -np.mean(tail_returns) * portfolio_value * np.sqrt(self.holding_period)
            else:
                cvar_results[conf] = var_results[conf]
                
        return cvar_results
        
    def risk_report(self, portfolio_value: float) -> Dict:
        """
        生成完整风险报告
        
        Args:
            portfolio_value: 组合市值
            
        Returns:
            风险报告字典
        """
        report = {
            'portfolio_value': portfolio_value,
            'holding_period': self.holding_period,
            'timestamp': datetime.now().isoformat(),
            'var': {},
            'cvar': {},
            'positions': self.positions
        }
        
        # 历史模拟法VaR
        report['var']['historical'] = self.historical_var(portfolio_value)
        
        # 蒙特卡洛VaR
        try:
            report['var']['monte_carlo'] = self.monte_carlo_var(portfolio_value)
        except Exception as e:
            report['var']['monte_carlo'] = {'error': str(e)}
            
        # CVaR
        report['cvar'] = self.calculate_cvar(portfolio_value)
        
        return report
        
    @staticmethod
    def _get_z_score(confidence: float) -> float:
        """获取正态分布分位数对应的z分数"""
        from scipy import stats
        return stats.norm.ppf(confidence)
        
    @property
    def weights(self) -> Dict[str, float]:
        """获取各品种权重"""
        total_value = sum(p['position'] * p['price'] 
                         for p in self.positions.values())
        if total_value == 0:
            return {s: 1/len(self.positions) if self.positions else 0 
                   for s in self.positions.keys()}
        return {s: (p['position'] * p['price']) / total_value 
                for s, p in self.positions.items()}


def demo():
    """演示用法"""
    # 创建VaR计算器
    var_calculator = PortfolioVaR(
        confidence_levels=[0.95, 0.99],
        holding_period=1
    )
    
    # 添加持仓
    var_calculator.add_position('SHFE.rb2105', 100, 5000)
    var_calculator.add_position('SHFE.hc2105', 50, 4500)
    var_calculator.add_position('DCE.i2105', 200, 1200)
    
    # 模拟收益率数据（实际使用时从TqAPI获取）
    np.random.seed(42)
    returns_rb = np.random.normal(0.001, 0.02, 252)
    returns_hc = np.random.normal(0.0008, 0.018, 252)
    returns_i = np.random.normal(0.0005, 0.025, 252)
    
    var_calculator.add_returns('SHFE.rb2105', returns_rb)
    var_calculator.add_returns('SHFE.hc2105', returns_hc)
    var_calculator.add_returns('DCE.i2105', returns_i)
    
    # 组合市值
    portfolio_value = 1000000  # 100万
    
    # 生成风险报告
    report = var_calculator.risk_report(portfolio_value)
    
    print("=" * 50)
    print("投资组合VaR风险报告")
    print("=" * 50)
    print(f"组合市值: ¥{report['portfolio_value']:,.2f}")
    print(f"持有期: {report['holding_period']}天")
    print(f"报告时间: {report['timestamp']}")
    print()
    print("各品种权重:")
    for symbol, weight in var_calculator.weights.items():
        print(f"  {symbol}: {weight:.2%}")
    print()
    print("VaR (Value at Risk):")
    for method, var_vals in report['var'].items():
        if isinstance(var_vals, dict):
            print(f"  {method}:")
            for conf, var in var_vals.items():
                print(f"    {conf*100:.0f}%置信度: ¥{var:,.2f}")
    print()
    print("CVaR (Conditional VaR):")
    for conf, cvar in report['cvar'].items():
        print(f"  {conf*100:.0f}%置信度: ¥{cvar:,.2f}")
    print("=" * 50)
    
    return report


if __name__ == '__main__':
    demo()
