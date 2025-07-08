"""
Indicator Manager for V2 - Calculate technical indicators based on profitable symbols' top features
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Universal features for symbols without proven patterns (based on frequency in profitable strategies)
UNIVERSAL_FEATURES = [
    'atr_ratio',        # 75% usage - Volatility relative to price
    'returns_std_50',   # 63% usage - 50-period return volatility
    'volume_mean_50',   # 57% usage - Average volume over 50 periods
    'volume_std_50',    # 51% usage - Volume volatility
    'volume_std_20',    # 29% usage - Short-term volume volatility
    'macd_signal',      # 27% usage - MACD signal line
    'returns_mean_50'   # 25% usage - 50-period average returns
]


class IndicatorManager:
    """Manages technical indicator calculation based on profitable symbols analysis"""
    
    def __init__(self, profitable_symbols_path: str = None):
        self.profitable_symbols = {}
        self.universal_features = UNIVERSAL_FEATURES
        
        if profitable_symbols_path:
            self._load_profitable_symbols(profitable_symbols_path)
    
    def _load_profitable_symbols(self, csv_path: str):
        """Load profitable symbols and their features from CSV"""
        try:
            df = pd.read_csv(csv_path)
            
            # Filter for profitable symbols (positive profitability score)
            profitable_df = df[df['profitability_score'] > 0].copy()
            
            for _, row in profitable_df.iterrows():
                key = f"{row['symbol']}_{row['timeframe']}"
                # Handle case where top_features might be NaN or float
                top_features = row['top_features']
                if pd.isna(top_features) or not isinstance(top_features, str):
                    continue
                features = [f.strip() for f in top_features.split(',')]
                
                self.profitable_symbols[key] = {
                    'symbol': row['symbol'],
                    'timeframe': row['timeframe'],
                    'features': features,
                    'win_rate': float(row['win_rate']) if pd.notna(row['win_rate']) else 0.0,
                    'sharpe_ratio': float(row['sharpe_ratio']) if pd.notna(row['sharpe_ratio']) else 0.0,
                    'profitability_score': float(row['profitability_score']) if pd.notna(row['profitability_score']) else 0.0
                }
            
            logger.info(f"Loaded {len(self.profitable_symbols)} profitable symbol configurations")
            
        except Exception as e:
            logger.error(f"Failed to load profitable symbols: {e}")
    
    def get_features_for_symbol(self, symbol: str, timeframe: str) -> List[str]:
        """Get the optimal features for a symbol-timeframe pair"""
        key = f"{symbol}_{timeframe}"
        
        if key in self.profitable_symbols:
            return self.profitable_symbols[key]['features']
        
        # Check if symbol exists with different timeframes
        symbol_configs = [k for k in self.profitable_symbols.keys() if k.startswith(f"{symbol}_")]
        if symbol_configs:
            # Use features from the most profitable configuration
            best_config = max(symbol_configs, 
                            key=lambda k: self.profitable_symbols[k]['profitability_score'])
            return self.profitable_symbols[best_config]['features']
        
        # Return universal features for unknown symbols
        return self.universal_features
    
    def calculate_indicators(self, df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
        """Calculate technical indicators based on symbol's optimal features"""
        if df.empty or len(df) < 50:
            return df
        
        # Get features for this symbol
        features = self.get_features_for_symbol(symbol, timeframe)
        
        # Calculate all base metrics that might be needed
        df = self._calculate_base_metrics(df)
        
        # Calculate only the required features
        for feature in features:
            if feature not in df.columns:
                df = self._calculate_feature(df, feature)
        
        return df
    
    def _calculate_base_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate base metrics that other features depend on"""
        # Returns
        df['returns'] = df['close'].pct_change()
        
        # High-Low ratio
        df['high_low_ratio'] = df['high'] / df['low']
        
        # Close-Open ratio
        df['close_open_ratio'] = df['close'] / df['open']
        
        # Volume ratio
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
        
        return df
    
    def _calculate_feature(self, df: pd.DataFrame, feature: str) -> pd.DataFrame:
        """Calculate a specific feature"""
        try:
            if feature == 'atr_ratio':
                # ATR calculation
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift(1))
                low_close = abs(df['low'] - df['close'].shift(1))
                
                true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = true_range.rolling(window=14).mean()
                df['atr_ratio'] = atr / df['close']
                
            elif feature == 'returns_std_50':
                df['returns_std_50'] = df['returns'].rolling(window=50).std()
                
            elif feature == 'returns_std_20':
                df['returns_std_20'] = df['returns'].rolling(window=20).std()
                
            elif feature == 'returns_std_10':
                df['returns_std_10'] = df['returns'].rolling(window=10).std()
                
            elif feature == 'returns_mean_50':
                df['returns_mean_50'] = df['returns'].rolling(window=50).mean()
                
            elif feature == 'returns_mean_20':
                df['returns_mean_20'] = df['returns'].rolling(window=20).mean()
                
            elif feature == 'returns_mean_10':
                df['returns_mean_10'] = df['returns'].rolling(window=10).mean()
                
            elif feature == 'volume_mean_50':
                df['volume_mean_50'] = df['volume'].rolling(window=50).mean()
                
            elif feature == 'volume_mean_20':
                df['volume_mean_20'] = df['volume'].rolling(window=20).mean()
                
            elif feature == 'volume_mean_10':
                df['volume_mean_10'] = df['volume'].rolling(window=10).mean()
                
            elif feature == 'volume_std_50':
                df['volume_std_50'] = df['volume'].rolling(window=50).std()
                
            elif feature == 'volume_std_20':
                df['volume_std_20'] = df['volume'].rolling(window=20).std()
                
            elif feature == 'volume_std_10':
                df['volume_std_10'] = df['volume'].rolling(window=10).std()
                
            elif feature == 'macd_signal':
                # MACD calculation
                ema_12 = df['close'].ewm(span=12, adjust=False).mean()
                ema_26 = df['close'].ewm(span=26, adjust=False).mean()
                macd = ema_12 - ema_26
                df['macd'] = macd
                df['macd_signal'] = macd.ewm(span=9, adjust=False).mean()
                
            elif feature == 'macd_hist':
                # Ensure MACD is calculated first
                if 'macd' not in df.columns:
                    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
                    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
                    df['macd'] = ema_12 - ema_26
                    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_hist'] = df['macd'] - df['macd_signal']
                
            elif feature == 'rsi':
                # RSI calculation
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['rsi'] = 100 - (100 / (1 + rs))
                
            elif feature == 'rsi_7':
                # RSI with period 7
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
                rs = gain / loss
                df['rsi_7'] = 100 - (100 / (1 + rs))
                
            elif feature == 'bb_width':
                # Bollinger Bands width
                sma_20 = df['close'].rolling(window=20).mean()
                std_20 = df['close'].rolling(window=20).std()
                upper_band = sma_20 + (2 * std_20)
                lower_band = sma_20 - (2 * std_20)
                df['bb_width'] = (upper_band - lower_band) / sma_20
                
            elif feature == 'bb_position':
                # Position within Bollinger Bands
                sma_20 = df['close'].rolling(window=20).mean()
                std_20 = df['close'].rolling(window=20).std()
                upper_band = sma_20 + (2 * std_20)
                lower_band = sma_20 - (2 * std_20)
                df['bb_position'] = (df['close'] - lower_band) / (upper_band - lower_band)
                
            elif feature == 'price_sma7_ratio':
                df['price_sma7_ratio'] = df['close'] / df['close'].rolling(window=7).mean()
                
            elif feature == 'price_sma25_ratio':
                df['price_sma25_ratio'] = df['close'] / df['close'].rolling(window=25).mean()
                
            elif feature == 'sma7_sma25_ratio':
                sma_7 = df['close'].rolling(window=7).mean()
                sma_25 = df['close'].rolling(window=25).mean()
                df['sma7_sma25_ratio'] = sma_7 / sma_25
                
            elif feature == 'trade_intensity':
                df['trade_intensity'] = df['trades'] / df['trades'].rolling(window=20).mean()
                
            elif feature == 'vol_percentile':
                df['vol_percentile'] = df['volume'].rolling(window=50).apply(
                    lambda x: (x.iloc[-1] > x).sum() / len(x) * 100
                )
                
            # Lag features
            elif feature.endswith('_lag1'):
                base_feature = feature.replace('_lag1', '')
                if base_feature not in df.columns:
                    df = self._calculate_feature(df, base_feature)
                df[feature] = df[base_feature].shift(1)
                
            elif feature.endswith('_lag3'):
                base_feature = feature.replace('_lag3', '')
                if base_feature not in df.columns:
                    df = self._calculate_feature(df, base_feature)
                df[feature] = df[base_feature].shift(3)
                
            elif feature.endswith('_lag5'):
                base_feature = feature.replace('_lag5', '')
                if base_feature not in df.columns:
                    df = self._calculate_feature(df, base_feature)
                df[feature] = df[base_feature].shift(5)
                
            elif feature.endswith('_lag10'):
                base_feature = feature.replace('_lag10', '')
                if base_feature not in df.columns:
                    df = self._calculate_feature(df, base_feature)
                df[feature] = df[base_feature].shift(10)
                
        except Exception as e:
            logger.warning(f"Failed to calculate feature {feature}: {e}")
        
        return df
    
    def get_profitable_symbols(self) -> List[str]:
        """Get list of all profitable symbols"""
        symbols = set()
        for key in self.profitable_symbols:
            symbol, _ = key.split('_')
            symbols.add(symbol)
        return list(symbols)