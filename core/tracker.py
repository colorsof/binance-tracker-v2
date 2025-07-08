"""
Binance API integration and price tracking logic
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import logging
import numpy as np
import pandas as pd

from config import (
    BINANCE_API_URL, TARGET_STABLECOINS, PRICE_RANGE,
    API_RATE_LIMIT_DELAY, MAX_CONCURRENT_REQUESTS,
    TIME_INTERVALS, BATCH_SIZE, CONSISTENCY_THRESHOLD,
    CONSISTENCY_MAX_DIFF
)
from core.database import Database
from core.indicator_manager import IndicatorManager
from core.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


class BinanceTracker:
    """Handles Binance API calls and price tracking"""
    
    def __init__(self, database: Database, profitable_symbols_path: str = None):
        self.db = database
        self.base_url = BINANCE_API_URL
        self.session = requests.Session()
        self._symbol_cache = {}
        self._last_symbol_update = None
        
        # Initialize indicator manager
        if not profitable_symbols_path:
            profitable_symbols_path = '/home/bernard-gitau-ndegwa/lugarch/redundant/robust_6month_analysis_results.csv'
        
        self.indicator_manager = IndicatorManager(profitable_symbols_path)
        self.scoring_engine = ScoringEngine()
    
    def get_exchange_info(self) -> Dict:
        """Get exchange information from Binance"""
        try:
            response = self.session.get(f"{self.base_url}/exchangeInfo")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get exchange info: {e}")
            return {}
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all current prices in one API call"""
        try:
            response = self.session.get(f"{self.base_url}/ticker/price")
            response.raise_for_status()
            return {item['symbol']: float(item['price']) for item in response.json()}
        except Exception as e:
            logger.error(f"Failed to get prices: {e}")
            return {}
    
    def get_relevant_symbols(self) -> List[str]:
        """Get symbols that match our criteria"""
        # Use cache if available and recent
        if (self._symbol_cache and self._last_symbol_update and 
            (datetime.now() - self._last_symbol_update).seconds < 3600):
            return self._symbol_cache
        
        exchange_info = self.get_exchange_info()
        if not exchange_info:
            return []
        
        # Filter for USDT/USDC pairs
        relevant_symbols = []
        symbol_info = []
        
        for symbol in exchange_info.get('symbols', []):
            if (symbol['status'] == 'TRADING' and 
                symbol['quoteAsset'] in TARGET_STABLECOINS):
                relevant_symbols.append(symbol['symbol'])
                symbol_info.append({
                    'symbol': symbol['symbol'],
                    'baseAsset': symbol['baseAsset'],
                    'quoteAsset': symbol['quoteAsset']
                })
        
        # Update symbol info in database
        if symbol_info:
            self.db.update_symbol_info(symbol_info)
        
        # Get current prices to filter by price range
        all_prices = self.get_all_prices()
        filtered_symbols = []
        
        for symbol in relevant_symbols:
            price = all_prices.get(symbol, 0)
            if PRICE_RANGE[0] <= price <= PRICE_RANGE[1]:
                filtered_symbols.append(symbol)
        
        self._symbol_cache = filtered_symbols
        self._last_symbol_update = datetime.now()
        
        logger.info(f"Found {len(filtered_symbols)} symbols in target price range")
        return filtered_symbols
    
    def update_prices(self):
        """Update prices for all relevant symbols"""
        symbols = self.get_relevant_symbols()
        all_prices = self.get_all_prices()
        
        # Filter prices for our symbols
        relevant_prices = {s: all_prices.get(s, 0) for s in symbols if s in all_prices}
        
        # Store in database
        if relevant_prices:
            self.db.store_prices(relevant_prices)
            logger.info(f"Updated prices for {len(relevant_prices)} symbols")
    
    def calculate_growth_rate(self, symbol: str, interval_name: str, current_price: float) -> Optional[float]:
        """Calculate growth rate for a specific interval"""
        minutes = TIME_INTERVALS.get(interval_name)
        if not minutes:
            return None
        
        historical_price = self.db.get_price_at_interval(symbol, minutes)
        if historical_price and historical_price > 0:
            return ((current_price - historical_price) / historical_price) * 100
        
        return None
    
    def calculate_bitcoin_correlation(self, symbol: str, hours: int = 24) -> Optional[float]:
        """Calculate correlation with Bitcoin"""
        if symbol == 'BTCUSDT':
            return 100.0
        
        # Get price history for both symbols
        symbol_history = self.db.get_price_history(symbol, hours)
        btc_history = self.db.get_price_history('BTCUSDT', hours)
        
        if len(symbol_history) < 10 or len(btc_history) < 10:
            return None
        
        # Convert to hourly returns
        def calculate_returns(history):
            prices = [price for _, price in history]
            if len(prices) < 2:
                return []
            returns = [(prices[i] - prices[i-1]) / prices[i-1] * 100 
                      for i in range(1, len(prices))]
            return returns
        
        symbol_returns = calculate_returns(symbol_history)
        btc_returns = calculate_returns(btc_history)
        
        if not symbol_returns or not btc_returns:
            return None
        
        # Align lengths
        min_len = min(len(symbol_returns), len(btc_returns))
        symbol_returns = symbol_returns[-min_len:]
        btc_returns = btc_returns[-min_len:]
        
        if len(symbol_returns) < 3:
            return None
        
        # Calculate correlation
        try:
            correlation = np.corrcoef(symbol_returns, btc_returns)[0, 1]
            return correlation * 100  # Return as percentage
        except:
            return None
    
    def calculate_consistency_score(self, growth_rates: Dict[str, Optional[float]]) -> Optional[float]:
        """Calculate consistency score based on steady growth across timeframes"""
        # Get valid growth rates for hourly timeframes (1h to 12h)
        valid_rates = []
        for interval in ['1h', '2h', '4h', '7h', '12h']:
            rate = growth_rates.get(interval)
            if rate is not None and rate > 0:
                valid_rates.append(rate)
        
        # Need at least 4 positive timeframes to calculate consistency
        if len(valid_rates) < 4:
            return None
        
        # Calculate the maximum difference between consecutive timeframes
        valid_rates.sort()  # Sort to check progression
        max_diff = 0
        for i in range(1, len(valid_rates)):
            diff = abs(valid_rates[i] - valid_rates[i-1])
            max_diff = max(max_diff, diff)
        
        # Calculate consistency score
        # Start with 100% and reduce based on volatility
        if max_diff <= CONSISTENCY_MAX_DIFF:
            # If difference is within threshold, calculate score based on how steady the growth is
            avg_rate = sum(valid_rates) / len(valid_rates)
            if avg_rate <= 0:
                return None
            
            # Score based on how close rates are to each other
            variance = sum((rate - avg_rate) ** 2 for rate in valid_rates) / len(valid_rates)
            std_dev = variance ** 0.5
            
            # Convert to score (lower std_dev = higher score)
            consistency = max(0, 100 - (std_dev / avg_rate * 100))
            
            # Only return if above threshold
            if consistency >= CONSISTENCY_THRESHOLD:
                return round(consistency, 1)
        
        return None
    
    def calculate_overall_performance(self, growth_rates: Dict[str, Optional[float]]) -> Optional[float]:
        """Calculate overall performance score across all timeframes"""
        # Get all valid growth rates
        valid_rates = []
        weights = {
            '5m': 0.5,    # Lower weight for very short term
            '15m': 0.6,   # Lower weight for short term
            '30m': 0.7,   # Lower weight for short term
            '1h': 1.0,    # Full weight for hourly and above
            '2h': 1.0,
            '4h': 1.0,
            '7h': 1.0,
            '12h': 1.2    # Slightly higher weight for longest timeframe
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for interval, weight in weights.items():
            rate = growth_rates.get(interval)
            if rate is not None:
                weighted_sum += rate * weight
                total_weight += weight
        
        if total_weight > 0:
            return round(weighted_sum / total_weight, 2)
        
        return None
    
    def get_trending_data(self) -> List[Dict]:
        """Get all trending coin data for display"""
        # Get latest prices
        latest_prices = self.db.get_latest_prices()
        all_current_prices = self.get_all_prices()
        
        # Update with fresh prices
        for symbol, price in all_current_prices.items():
            if symbol in latest_prices or symbol in self.get_relevant_symbols():
                latest_prices[symbol] = price
        
        # Always include Bitcoin for correlation
        if 'BTCUSDT' not in latest_prices:
            btc_price = all_current_prices.get('BTCUSDT', 0)
            if btc_price > 0:
                latest_prices['BTCUSDT'] = btc_price
        
        trending_data = []
        
        for symbol, current_price in latest_prices.items():
            # Skip if not in our target range (except Bitcoin)
            if symbol != 'BTCUSDT' and not (PRICE_RANGE[0] <= current_price <= PRICE_RANGE[1]):
                continue
            
            # Calculate growth rates for all intervals
            growth_rates = {}
            for interval_name in TIME_INTERVALS.keys():
                rate = self.calculate_growth_rate(symbol, interval_name, current_price)
                growth_rates[interval_name] = rate
            
            # Skip if no valid growth data
            valid_rates = [r for r in growth_rates.values() if r is not None]
            if not valid_rates:
                continue
            
            # Calculate Bitcoin correlation
            btc_correlation = self.calculate_bitcoin_correlation(symbol, 24)
            
            # Calculate consistency score
            consistency_score = self.calculate_consistency_score(growth_rates)
            
            # Calculate overall performance
            overall_performance = self.calculate_overall_performance(growth_rates)
            
            # Build data entry
            entry = {
                'symbol': symbol,
                'price': current_price,
                'growth_rates': growth_rates,
                'btc_correlation': btc_correlation,
                'consistency_score': consistency_score,
                'overall_performance': overall_performance,
                'avg_growth': sum(valid_rates) / len(valid_rates) if valid_rates else 0
            }
            
            trending_data.append(entry)
        
        # Sort by overall performance by default
        def sort_key(item):
            perf = item.get('overall_performance')
            if perf is not None:
                return -perf  # Negative for descending sort
            # Fallback to 7h if no overall performance
            rate = item['growth_rates'].get('7h')
            if rate is not None:
                return -rate
            return 0
        
        trending_data.sort(key=sort_key)
        
        return trending_data
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch klines/candlestick data from Binance"""
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            response = self.session.get(f"{self.base_url}/klines", params=params)
            response.raise_for_status()
            
            # Convert to DataFrame
            data = response.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'count', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            df.rename(columns={'count': 'trades'}, inplace=True)
            
            # Convert to numeric
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'trades']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            return None
    
    def calculate_technical_indicators(self, symbol: str, interval: str = '15m') -> Optional[Dict]:
        """Calculate technical indicators for a symbol using its optimal features"""
        try:
            # Fetch klines data
            df = self.get_klines(symbol, interval, limit=100)
            if df is None or df.empty:
                return None
            
            # Calculate indicators based on symbol's top features
            df = self.indicator_manager.calculate_indicators(df, symbol, interval)
            
            # Get the latest values
            latest_row = df.iloc[-1]
            features = self.indicator_manager.get_features_for_symbol(symbol, interval)
            
            # Extract indicator values
            indicators = {}
            for feature in features:
                if feature in latest_row.index:
                    value = latest_row[feature]
                    if pd.notna(value):
                        indicators[feature] = float(value)
            
            # Add metadata
            indicators['symbol'] = symbol
            indicators['interval'] = interval
            indicators['timestamp'] = df.index[-1].isoformat()
            indicators['price'] = float(latest_row['close'])
            
            return indicators
            
        except Exception as e:
            logger.error(f"Failed to calculate indicators for {symbol}: {e}")
            return None
    
    def get_profitable_symbols(self) -> List[str]:
        """Get list of profitable symbols from the indicator manager"""
        return self.indicator_manager.get_profitable_symbols()
    
    def update_with_indicators(self):
        """Update prices and calculate indicators for profitable symbols"""
        # Get profitable symbols
        profitable_symbols = self.get_profitable_symbols()
        
        # Also get regular symbols in price range
        regular_symbols = self.get_relevant_symbols()
        
        # Combine both lists (unique)
        all_symbols = list(set(profitable_symbols + regular_symbols))
        
        logger.info(f"Updating {len(all_symbols)} symbols ({len(profitable_symbols)} profitable)")
        
        # Process in batches
        batch_size = 10
        for i in range(0, len(all_symbols), batch_size):
            batch = all_symbols[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
                futures = []
                
                for symbol in batch:
                    # Calculate indicators for multiple timeframes
                    for interval in ['5m', '15m', '30m', '1h']:
                        future = executor.submit(self.calculate_technical_indicators, symbol, interval)
                        futures.append((symbol, interval, future))
                
                # Process results
                for symbol, interval, future in futures:
                    try:
                        result = future.result(timeout=10)
                        if result:
                            # Store indicators in database (would need to add this method)
                            logger.debug(f"Calculated indicators for {symbol} {interval}: {list(result.keys())}")
                    except Exception as e:
                        logger.error(f"Failed to process {symbol} {interval}: {e}")
            
            # Rate limiting
            time.sleep(API_RATE_LIMIT_DELAY)
    
    def get_enhanced_trending_data(self) -> List[Dict]:
        """Get trending data with composite scores and trading signals"""
        # Get basic trending data
        trending_data = self.get_trending_data()
        
        # Enhance with technical indicators and composite scores
        enhanced_data = []
        
        for entry in trending_data:
            symbol = entry['symbol']
            
            try:
                # Calculate technical indicators for main timeframe (15m)
                indicators = self.calculate_technical_indicators(symbol, '15m')
                
                if indicators:
                    # Calculate composite score
                    composite_result = self.scoring_engine.calculate_composite_score(
                        entry, indicators
                    )
                    
                    # Merge all data
                    enhanced_entry = {
                        **entry,
                        'indicators': indicators,
                        **composite_result
                    }
                    
                    enhanced_data.append(enhanced_entry)
                else:
                    # No indicators available - add basic entry
                    enhanced_data.append(entry)
                    
            except Exception as e:
                logger.error(f"Failed to enhance data for {symbol}: {e}")
                enhanced_data.append(entry)
        
        # Sort by composite score (highest first)
        enhanced_data.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        
        return enhanced_data