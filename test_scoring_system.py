#!/usr/bin/env python3
"""
Test script for the new composite scoring system
"""

import json
from datetime import datetime
from core.database import Database
from core.tracker import BinanceTracker
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_signal(data):
    """Format trading signal for display"""
    symbol = data['symbol']
    price = data['price']
    signal = data.get('signal', 'N/A')
    composite = data.get('composite_score', 0)
    
    # Color coding for signals
    signal_colors = {
        'STRONG_BUY': '\033[92m',  # Bright green
        'BUY': '\033[32m',         # Green
        'WEAK_BUY': '\033[33m',    # Yellow
        'HOLD': '\033[93m',        # Bright yellow
        'WEAK_SELL': '\033[91m',   # Light red
        'STRONG_SELL': '\033[31m', # Red
        'DEAD': '\033[90m'         # Gray
    }
    
    color = signal_colors.get(signal, '\033[0m')
    reset = '\033[0m'
    
    return f"{color}{symbol:12} ${price:8.4f} | {signal:12} | Score: {composite:6.2f}{reset}"


def main():
    """Test the enhanced scoring system"""
    print("=== Binance Tracker V2 - Enhanced Scoring System Test ===\n")
    
    # Initialize components
    db = Database()
    tracker = BinanceTracker(db)
    
    print("Fetching market data and calculating signals...")
    print("This may take a minute...\n")
    
    try:
        # Get enhanced trending data with composite scores
        enhanced_data = tracker.get_enhanced_trending_data()
        
        if not enhanced_data:
            print("No data available")
            return
        
        # Display results by signal type
        print(f"Found {len(enhanced_data)} symbols\n")
        
        # Group by signal
        signals_grouped = {}
        for entry in enhanced_data:
            signal = entry.get('signal', 'UNKNOWN')
            if signal not in signals_grouped:
                signals_grouped[signal] = []
            signals_grouped[signal].append(entry)
        
        # Display in order of importance
        signal_order = ['STRONG_BUY', 'BUY', 'WEAK_BUY', 'HOLD', 'WEAK_SELL', 'STRONG_SELL', 'DEAD']
        
        for signal_type in signal_order:
            if signal_type in signals_grouped:
                entries = signals_grouped[signal_type]
                print(f"\n=== {signal_type} ({len(entries)} symbols) ===")
                
                # Show top 5 for each category
                for entry in entries[:5]:
                    print(format_signal(entry))
                    
                    # Show details for buy signals
                    if 'BUY' in signal_type:
                        growth = entry.get('growth_rates', {})
                        print(f"  Growth: 5m: {growth.get('5m', 0):.1f}%, "
                              f"15m: {growth.get('15m', 0):.1f}%, "
                              f"30m: {growth.get('30m', 0):.1f}%, "
                              f"1h: {growth.get('1h', 0):.1f}%")
                        print(f"  Scores: Tech: {entry.get('technical_score', 0):.1f}, "
                              f"Growth: {entry.get('growth_score', 0):.1f}, "
                              f"Consistency: {entry.get('consistency_score', 0):.1f}")
                        
                        # Show key indicators
                        indicators = entry.get('indicators', {})
                        if indicators:
                            atr = indicators.get('atr_ratio', 0)
                            volume = indicators.get('volume_mean_50', 0)
                            print(f"  Key Indicators: ATR: {atr:.4f}, Volume Ratio: {volume:.2f}")
                        
                        reasons = entry.get('reasons', [])
                        if reasons:
                            print(f"  Reasons: {', '.join(reasons)}")
                        print()
                
                if len(entries) > 5:
                    print(f"  ... and {len(entries) - 5} more")
        
        # Summary statistics
        print("\n=== Summary Statistics ===")
        total = len(enhanced_data)
        for signal_type in signal_order:
            count = len(signals_grouped.get(signal_type, []))
            if count > 0:
                percentage = (count / total) * 100
                print(f"{signal_type:12}: {count:4} ({percentage:5.1f}%)")
        
        # Find strongest signals
        print("\n=== Top 10 Strongest Signals ===")
        top_signals = sorted(enhanced_data, key=lambda x: x.get('composite_score', 0), reverse=True)[:10]
        
        for i, entry in enumerate(top_signals, 1):
            print(f"{i:2}. {format_signal(entry)}")
            if entry.get('composite_score', 0) > 70:
                print(f"    Growth rates: {entry.get('growth_rates', {})}")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()