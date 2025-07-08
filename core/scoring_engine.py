"""
Composite Scoring Engine for Buy/Hold/Sell Signals
Uses frequency-weighted technical indicators from profitable strategies
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Feature weights based on frequency in profitable strategies
FEATURE_WEIGHTS = {
    'atr_ratio': 0.75,           # 75% frequency
    'returns_std_50': 0.63,      # 63% frequency
    'volume_mean_50': 0.57,      # 57% frequency
    'volume_std_50': 0.51,       # 51% frequency
    'volume_std_20': 0.29,       # 29% frequency
    'macd_signal': 0.27,         # 27% frequency
    'returns_mean_50': 0.25,     # 25% frequency
    'macd_hist': 0.20,           # 20% frequency
    'returns_std_20': 0.13,      # 13% frequency
    'rsi': 0.10,                 # 10% frequency
    'rsi_7': 0.10,               # 10% frequency
    'high_low_ratio': 0.12,      # 12% frequency
    'close_open_ratio': 0.08,    # 8% frequency
    'bb_width': 0.08,            # 8% frequency
    'bb_position': 0.08,         # 8% frequency
    'volume_mean_20': 0.15,      # 15% frequency
    'volume_mean_10': 0.15,      # 15% frequency
    'returns_mean_20': 0.10,     # 10% frequency
    'price_sma7_ratio': 0.08,    # 8% frequency
    'price_sma25_ratio': 0.08,   # 8% frequency
    'trade_intensity': 0.06,     # 6% frequency
    'returns': 0.05,             # 5% frequency
    'volume_ratio': 0.05,        # 5% frequency
    'macd': 0.08,                # 8% frequency
    'volume_std_10': 0.10,       # 10% frequency
    'returns_mean_10': 0.08,     # 8% frequency
    'returns_std_10': 0.08       # 8% frequency
}

# Indicator thresholds for bullish signals
INDICATOR_THRESHOLDS = {
    'atr_ratio': {'bullish': 0.02, 'bearish': 0.005},          # Higher ATR = more volatility/opportunity
    'returns_std_50': {'bullish': 0.02, 'bearish': 0.001},     # Higher volatility
    'volume_mean_50': {'bullish': 1.2, 'bearish': 0.8},        # Above average volume (ratio)
    'volume_std_50': {'bullish': 0.3, 'bearish': 0.1},         # Volume volatility
    'macd_signal': {'bullish': 0, 'bearish': -0.5},            # Positive MACD signal
    'rsi': {'bullish': 50, 'bearish': 30, 'overbought': 70},   # RSI levels
    'bb_position': {'bullish': 0.5, 'bearish': 0.2},           # Position in Bollinger Bands
    'volume_ratio': {'bullish': 1.5, 'bearish': 0.5},          # Current vs average volume
    'trade_intensity': {'bullish': 1.2, 'bearish': 0.8}        # Trading activity
}


class ScoringEngine:
    """Calculate composite scores for trading signals"""
    
    def __init__(self):
        self.feature_weights = FEATURE_WEIGHTS
        self.thresholds = INDICATOR_THRESHOLDS
    
    def calculate_technical_strength(self, indicators: Dict[str, float]) -> float:
        """
        Calculate technical indicator strength using frequency-based weights
        Returns a score from 0-100
        """
        total_score = 0
        total_weight = 0
        
        for feature, weight in self.feature_weights.items():
            if feature in indicators and pd.notna(indicators[feature]):
                value = indicators[feature]
                
                # Calculate feature score based on thresholds
                feature_score = self._score_indicator(feature, value)
                
                # Apply frequency-based weight
                weighted_score = feature_score * weight
                total_score += weighted_score
                total_weight += weight
        
        # Normalize to 0-100 scale
        if total_weight > 0:
            normalized_score = (total_score / total_weight) * 100
            return min(100, max(0, normalized_score))
        
        return 0
    
    def _score_indicator(self, feature: str, value: float) -> float:
        """Score individual indicator (0-1 scale)"""
        if feature not in self.thresholds:
            # For features without specific thresholds, use generic scoring
            return self._generic_score(feature, value)
        
        thresholds = self.thresholds[feature]
        
        # Special handling for RSI (bounded indicator)
        if feature == 'rsi':
            if value >= thresholds['overbought']:
                return 0.3  # Overbought - caution
            elif value >= thresholds['bullish']:
                return 0.8  # Bullish range
            elif value >= thresholds['bearish']:
                return 0.5  # Neutral
            else:
                return 0.2  # Oversold
        
        # For other indicators
        if 'bullish' in thresholds and 'bearish' in thresholds:
            if value >= thresholds['bullish']:
                return 1.0
            elif value >= thresholds['bearish']:
                # Linear interpolation between bearish and bullish
                range_size = thresholds['bullish'] - thresholds['bearish']
                if range_size > 0:
                    return (value - thresholds['bearish']) / range_size
                return 0.5
            else:
                return 0.2
        
        return 0.5  # Default neutral score
    
    def _generic_score(self, feature: str, value: float) -> float:
        """Generic scoring for indicators without specific thresholds"""
        # Volume-related features - higher is generally better
        if 'volume' in feature and 'std' not in feature:
            if value > 1.5:
                return 1.0
            elif value > 1.0:
                return 0.7
            elif value > 0.5:
                return 0.5
            else:
                return 0.2
        
        # Volatility features - moderate is best
        elif 'std' in feature or 'atr' in feature:
            if 0.01 < value < 0.05:
                return 1.0  # Optimal volatility range
            elif 0.005 < value < 0.1:
                return 0.7
            else:
                return 0.3  # Too low or too high volatility
        
        # Ratio features - close to 1 is neutral
        elif 'ratio' in feature:
            if 0.95 < value < 1.05:
                return 0.5  # Neutral
            elif value > 1.05:
                return min(1.0, (value - 1) * 2)  # Bullish
            else:
                return max(0.2, value)  # Bearish
        
        return 0.5  # Default neutral
    
    def calculate_growth_score(self, growth_rates: Dict[str, Optional[float]]) -> Tuple[float, int]:
        """
        Calculate growth score with dead coin penalties
        Returns: (score, dead_count)
        """
        score = 0
        dead_count = 0
        
        # Growth thresholds and penalties
        thresholds = {
            '5m': {'min': 3, 'zero_penalty': -20, 'weight': 20},
            '15m': {'min': 5, 'zero_penalty': -25, 'weight': 25},
            '30m': {'min': 7, 'zero_penalty': -30, 'weight': 30},
            '1h': {'min': 10, 'zero_penalty': -35, 'weight': 25}
        }
        
        for timeframe, config in thresholds.items():
            rate = growth_rates.get(timeframe)
            
            if rate is None:
                continue
            
            if rate == 0:
                # Dead coin penalty
                score += config['zero_penalty']
                dead_count += 1
            elif rate < 0:
                # Negative growth - half penalty
                score += config['zero_penalty'] * 0.5
            elif rate < config['min']:
                # Below threshold - partial score
                partial_score = (rate / config['min']) * config['weight']
                score += partial_score
            else:
                # Above threshold - full score
                score += config['weight']
        
        # Cap score if dead periods detected
        if dead_count > 0:
            score = min(score, 20)
        
        return max(0, score), dead_count
    
    def calculate_consistency_score(self, growth_rates: Dict[str, Optional[float]]) -> float:
        """
        Calculate consistency score across timeframes
        Checks for steady, progressive growth
        """
        # Extract rates for consistency check
        timeframes = ['5m', '15m', '30m', '1h']
        rates = []
        
        for tf in timeframes:
            rate = growth_rates.get(tf)
            if rate is not None:
                rates.append(rate)
        
        if len(rates) < 3:
            return 0  # Not enough data
        
        # Check all positive
        if any(r <= 0 for r in rates):
            return 0  # Consistency broken by negative/zero growth
        
        # Calculate consistency metrics
        score = 100
        
        # 1. Check progressive growth (each timeframe > previous)
        for i in range(1, len(rates)):
            if rates[i] <= rates[i-1]:
                score -= 20  # Penalty for non-progressive growth
        
        # 2. Check volatility between timeframes
        for i in range(1, len(rates)):
            diff = abs(rates[i] - rates[i-1])
            if diff > 10:  # Large jump
                score -= 15
            elif diff > 5:  # Moderate jump
                score -= 10
        
        # 3. Reward steady growth
        avg_rate = sum(rates) / len(rates)
        std_dev = np.std(rates)
        if std_dev < avg_rate * 0.3:  # Low volatility relative to average
            score += 10
        
        return max(0, min(100, score))
    
    def calculate_composite_score(self, 
                                symbol_data: Dict,
                                indicators: Dict[str, float]) -> Dict:
        """
        Calculate composite score and generate trading signal
        """
        # Extract growth rates
        growth_rates = symbol_data.get('growth_rates', {})
        
        # Calculate component scores
        tech_score = self.calculate_technical_strength(indicators)
        growth_score, dead_count = self.calculate_growth_score(growth_rates)
        consistency_score = self.calculate_consistency_score(growth_rates)
        
        # Activity multiplier based on dead periods
        if dead_count == 0:
            activity_multiplier = 1.0
        elif dead_count == 1:
            activity_multiplier = 0.5
        else:
            activity_multiplier = 0.1
        
        # Calculate weighted composite score
        composite_score = (
            tech_score * 0.4 +
            growth_score * 0.3 +
            consistency_score * 0.3
        ) * activity_multiplier
        
        # Generate signal
        signal = self._generate_signal(composite_score, dead_count, growth_rates)
        
        return {
            'composite_score': round(composite_score, 2),
            'technical_score': round(tech_score, 2),
            'growth_score': round(growth_score, 2),
            'consistency_score': round(consistency_score, 2),
            'dead_count': dead_count,
            'signal': signal['type'],
            'signal_strength': signal['strength'],
            'reasons': signal['reasons']
        }
    
    def _generate_signal(self, composite_score: float, dead_count: int, 
                        growth_rates: Dict) -> Dict:
        """Generate trading signal based on composite score"""
        reasons = []
        
        # Check for dead coin first
        if dead_count > 0:
            return {
                'type': 'DEAD',
                'strength': 0,
                'reasons': [f'{dead_count} timeframe(s) with 0% growth - inactive coin']
            }
        
        # Check for negative growth
        negative_count = sum(1 for r in growth_rates.values() if r is not None and r < 0)
        if negative_count > 1:
            reasons.append(f'{negative_count} timeframes showing negative growth')
        
        # Generate signal based on composite score
        if composite_score >= 80:
            signal_type = 'STRONG_BUY'
            strength = 5
            reasons.append('Exceptional technical and growth metrics')
        elif composite_score >= 70:
            signal_type = 'BUY'
            strength = 4
            reasons.append('Strong positive indicators across metrics')
        elif composite_score >= 60:
            signal_type = 'WEAK_BUY'
            strength = 3
            reasons.append('Moderately positive signals')
        elif composite_score >= 50:
            signal_type = 'HOLD'
            strength = 2
            reasons.append('Mixed signals - monitor closely')
        elif composite_score >= 30:
            signal_type = 'WEAK_SELL'
            strength = 1
            reasons.append('Predominantly negative indicators')
        else:
            signal_type = 'STRONG_SELL'
            strength = 0
            reasons.append('Poor performance across all metrics')
        
        return {
            'type': signal_type,
            'strength': strength,
            'reasons': reasons
        }