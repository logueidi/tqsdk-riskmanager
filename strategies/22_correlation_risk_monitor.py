#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
相关性风险监控器 (Correlation Risk Monitor)
实时监控投资组合内各品种相关性变化，预警相关性风险

Author: TqSdk RiskManager
Update: 2026-03-12
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import warnings


class CorrelationRiskMonitor:
    """相关性风险监控器"""
    
    def __init__(self, lookback_period: int = 60,
                 alert_threshold: float = 0.7,
                 change_threshold: float = 0.2):
        """
        初始化监控器
        
        Args:
            lookback_period: 历史回看期（天）
            alert_threshold: 相关性预警阈值
            change_threshold: 相关性变化预警阈值
        """
        self.lookback_period = lookback_period
        self.alert_threshold = alert_threshold
        self.change_threshold = change_threshold
        
        self.price_history = {}  # 价格历史
        self.returns_history = {}  # 收益率历史
        self.correlation_matrix = None  # 当前相关矩阵
        self.baseline_correlation = None  # 基线相关矩阵
        self.alerts = []  # 预警记录
        
    def add_price_data(self, symbol: str, prices: List[float]):
        """添加价格数据"""
        self.price_history[symbol] = np.array(prices)
        
    def add_return(self, symbol: str, price: float):
        """添加单个价格数据点"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
            
        self.price_history[symbol].append(price)
        
        # 保持历史长度
        if len(self.price_history[symbol]) > self.lookback_period:
            self.price_history[symbol] = self.price_history[symbol][-self.lookback_period:]
            
    def calculate_returns(self) -> bool:
        """计算收益率序列"""
        self.returns_history = {}
        
        for symbol, prices in self.price_history.items():
            if len(prices) < 2:
                continue
            returns = np.diff(prices) / prices[:-1]
            self.returns_history[symbol] = returns
            
        return len(self.returns_history) >= 2
    
    def calculate_correlation_matrix(self) -> np.ndarray:
        """计算当前相关矩阵"""
        if not self.calculate_returns():
            raise ValueError("数据不足以计算相关性")
            
        symbols = list(self.returns_history.keys())
        n = len(symbols)
        
        # 对齐收益率序列
        min_length = min(len(r) for r in self.returns_history.values())
        returns_array = np.zeros((min_length, n))
        
        for i, symbol in enumerate(symbols):
            returns_array[:, i] = self.returns_history[symbol][-min_length:]
            
        self.correlation_matrix = np.corrcoef(returns_array.T)
        self.symbols = symbols
        
        return self.correlation_matrix
    
    def set_baseline_correlation(self):
        """设置基线相关矩阵（用于对比）"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
        self.baseline_correlation = self.correlation_matrix.copy()
        
    def get_correlation(self, symbol1: str, symbol2: str) -> Optional[float]:
        """获取两个品种的相关性"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
            
        try:
            i = self.symbols.index(symbol1)
            j = self.symbols.index(symbol2)
            return self.correlation_matrix[i, j]
        except (ValueError, IndexError):
            return None
            
    def detect_extreme_correlations(self) -> List[Dict]:
        """检测极端相关性（高相关或负相关）"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
            
        alerts = []
        n = len(self.symbols)
        
        for i in range(n):
            for j in range(i + 1, n):
                corr = self.correlation_matrix[i, j]
                
                # 高相关预警
                if abs(corr) >= self.alert_threshold:
                    alerts.append({
                        'type': 'extreme_correlation',
                        'symbols': (self.symbols[i], self.symbols[j]),
                        'correlation': corr,
                        'direction': 'positive' if corr > 0 else 'negative',
                        'severity': 'high' if abs(corr) > 0.9 else 'medium',
                        'timestamp': datetime.now().isoformat()
                    })
                    
        return alerts
    
    def detect_correlation_changes(self) -> List[Dict]:
        """检测相关性变化"""
        if self.baseline_correlation is None:
            return []
            
        alerts = []
        n = len(self.symbols)
        
        for i in range(n):
            for j in range(i + 1, n):
                current = self.correlation_matrix[i, j]
                baseline = self.baseline_correlation[i, j]
                change = current - baseline
                
                if abs(change) >= self.change_threshold:
                    alerts.append({
                        'type': 'correlation_change',
                        'symbols': (self.symbols[i], self.symbols[j]),
                        'current': current,
                        'baseline': baseline,
                        'change': change,
                        'direction': 'increased' if change > 0 else 'decreased',
                        'severity': 'high' if abs(change) > 0.4 else 'medium',
                        'timestamp': datetime.now().isoformat()
                    })
                    
        return alerts
    
    def detect_clustering(self) -> List[Dict]:
        """检测品种聚类（高度相关的品种群）"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
            
        # 使用聚类方法检测
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform
        
        # 转换为距离矩阵
        distance_matrix = 1 - np.abs(self.correlation_matrix)
        np.fill_diagonal(distance_matrix, 0)
        
        # 层次聚类
        dist_condensed = squareform(distance_matrix)
        linkage_matrix = linkage(dist_condensed, method='average')
        
        # 切割成若干类
        clusters = fcluster(linkage_matrix, t=0.3, criterion='distance')
        
        cluster_groups = {}
        for idx, cluster_id in enumerate(clusters):
            if cluster_id not in cluster_groups:
                cluster_groups[cluster_id] = []
            cluster_groups[cluster_id].append(self.symbols[idx])
            
        # 只返回包含多个品种的聚类
        significant_clusters = [
            {
                'cluster_id': cid,
                'symbols': symbols,
                'avg_correlation': np.mean([
                    self.correlation_matrix[
                        self.symbols.index(s1), 
                        self.symbols.index(s2)
                    ] 
                    for s1 in symbols 
                    for s2 in symbols 
                    if s1 != s2
                ])
            }
            for cid, symbols in cluster_groups.items()
            if len(symbols) >= 2
        ]
        
        return significant_clusters
    
    def calculate_portfolio_correlation_risk(self, weights: Dict[str, float]) -> Dict:
        """计算投资组合的总体相关性风险"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
            
        symbols = list(weights.keys())
        w = np.array([weights.get(s, 0) for s in self.symbols])
        
        # 归一化权重
        if w.sum() > 0:
            w = w / w.sum()
        
        # 组合相关性（加权平均相关性）
        n = len(self.symbols)
        total_corr = 0
        count = 0
        
        for i in range(n):
            for j in range(i + 1, n):
                total_corr += abs(self.correlation_matrix[i, j]) * w[i] * w[j]
                count += 1
        
        avg_correlation = total_corr / count if count > 0 else 0
        
        # 相关性集中度（最大相关品种占比）
        max_corr_per_symbol = np.max(np.abs(self.correlation_matrix), axis=1)
        max_correlation_concentration = np.sum(w * max_corr_per_symbol)
        
        return {
            'average_correlation': avg_correlation,
            'correlation_concentration': max_correlation_concentration,
            'diversification_potential': 1 - avg_correlation,
            'risk_level': self._assess_risk_level(avg_correlation, max_correlation_concentration)
        }
    
    def _assess_risk_level(self, avg_corr: float, concentration: float) -> str:
        """评估风险等级"""
        if avg_corr > 0.7 or concentration > 0.8:
            return 'high'
        elif avg_corr > 0.5 or concentration > 0.6:
            return 'medium'
        else:
            return 'low'
            
    def generate_risk_report(self, weights: Optional[Dict[str, float]] = None) -> Dict:
        """生成完整风险报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'symbols': list(self.symbols) if hasattr(self, 'symbols') else [],
            'lookback_period': self.lookback_period,
            'thresholds': {
                'alert': self.alert_threshold,
                'change': self.change_threshold
            },
            'correlation_matrix': self.correlation_matrix.tolist() if self.correlation_matrix is not None else None,
            'extreme_correlations': self.detect_extreme_correlations(),
            'correlation_changes': self.detect_correlation_changes() if self.baseline_correlation is not None else [],
            'clusters': self.detect_clustering()
        }
        
        if weights:
            report['portfolio_risk'] = self.calculate_portfolio_correlation_risk(weights)
            
        return report
        
    def get_heatmap_data(self) -> Tuple[List[str], np.ndarray]:
        """获取热力图数据"""
        if self.correlation_matrix is None:
            self.calculate_correlation_matrix()
        return self.symbols, self.correlation_matrix


def demo():
    """演示用法"""
    # 创建监控器
    monitor = CorrelationRiskMonitor(
        lookback_period=60,
        alert_threshold=0.7,
        change_threshold=0.2
    )
    
    # 模拟价格数据
    np.random.seed(42)
    n_days = 100
    
    # 相关品种（螺纹钢和热卷）
    rb_prices = 5000 + np.cumsum(np.random.normal(0, 50, n_days))
    hc_prices = 4500 + np.cumsum(np.random.normal(0, 45, n_days))
    
    # 不太相关的品种（铁矿石）
    i_prices = 1200 + np.cumsum(np.random.normal(0, 30, n_days))
    
    # 负相关品种（黄金）
    au_prices = 400 + np.cumsum(np.random.normal(0, 5, n_days))
    
    monitor.add_price_data('SHFE.rb', rb_prices)
    monitor.add_price_data('SHFE.hc', hc_prices)
    monitor.add_price_data('DCE.i', i_prices)
    monitor.add_price_data('AU.au', au_prices)
    
    # 设置基线
    monitor.calculate_correlation_matrix()
    monitor.set_baseline_correlation()
    
    # 添加新的价格数据点（模拟实时更新）
    monitor.add_return('SHFE.rb', 5100)
    monitor.add_return('SHFE.hc', 4600)
    monitor.add_return('DCE.i', 1250)
    monitor.add_return('AU.au', 395)
    
    # 重新计算
    monitor.calculate_correlation_matrix()
    
    # 生成报告
    report = monitor.generate_risk_report()
    
    print("=" * 60)
    print("相关性风险监控报告")
    print("=" * 60)
    print(f"监控品种: {', '.join(report['symbols'])}")
    print(f"分析时间: {report['timestamp']}")
    print()
    
    # 相关矩阵
    print("相关矩阵:")
    print("-" * 40)
    symbols = report['symbols']
    corr_matrix = np.array(report['correlation_matrix'])
    
    header = "        " + " ".join([f"{s:>8}" for s in symbols])
    print(header)
    for i, symbol in enumerate(symbols):
        row = f"{symbol:>8}" + " ".join([f"{corr_matrix[i,j]:>8.3f}" for j in range(len(symbols))])
        print(row)
    print()
    
    # 极端相关性
    if report['extreme_correlations']:
        print("⚠️ 极端相关性预警:")
        for alert in report['extreme_correlations']:
            print(f"  {alert['symbols'][0]} vs {alert['symbols'][1]}: {alert['correlation']:.3f} ({alert['direction']})")
    print()
    
    # 聚类
    if report['clusters']:
        print("📊 品种聚类:")
        for cluster in report['clusters']:
            print(f"  聚类{cluster['cluster_id']}: {', '.join(cluster['symbols'])} (平均相关: {cluster['avg_correlation']:.3f})")
    print()
    
    # 组合风险
    weights = {'SHFE.rb': 0.3, 'SHFE.hc': 0.3, 'DCE.i': 0.2, 'AU.au': 0.2}
    report_with_weights = monitor.generate_risk_report(weights)
    if 'portfolio_risk' in report_with_weights:
        pr = report_with_weights['portfolio_risk']
        print("📈 组合相关性风险:")
        print(f"  平均相关性: {pr['average_correlation']:.3f}")
        print(f"  相关集中度: {pr['correlation_concentration']:.3f}")
        print(f"  多样化潜力: {pr['diversification_potential']:.3f}")
        print(f"  风险等级: {pr['risk_level']}")
        
    print("=" * 60)
    
    return report


if __name__ == '__main__':
    demo()
