"""
PostgreSQL database implementation for cloud deployment
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PostgresDatabase:
    """PostgreSQL database handler for cloud deployment"""
    
    def __init__(self, database_url=None):
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL not provided")
        
        # Fix for Render's postgres URL format
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        
        self.init_db()
    
    @contextmanager
    def get_conn(self):
        """Get database connection with context manager"""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                # Prices table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS prices (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        price DECIMAL(20, 8) NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Symbol info table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS symbol_info (
                        symbol VARCHAR(20) PRIMARY KEY,
                        base_asset VARCHAR(20),
                        quote_asset VARCHAR(20),
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Indicators table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS indicators (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        timeframe VARCHAR(10) NOT NULL,
                        indicators JSONB,
                        composite_score DECIMAL(5, 2),
                        signal VARCHAR(20),
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, timeframe, timestamp)
                    )
                """)
                
                # Create indexes
                cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_symbol_time ON prices(symbol, timestamp DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_indicators_composite ON indicators(composite_score DESC)")
                
        logger.info("PostgreSQL database initialized")
    
    def store_prices(self, prices_dict):
        """Store multiple prices in database"""
        if not prices_dict:
            return
        
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                values = [(symbol, price) for symbol, price in prices_dict.items()]
                cur.executemany(
                    "INSERT INTO prices (symbol, price) VALUES (%s, %s)",
                    values
                )
        
        logger.debug(f"Stored {len(prices_dict)} prices")
    
    def get_price_at_interval(self, symbol, minutes_ago):
        """Get price at specific interval ago"""
        target_time = datetime.now() - timedelta(minutes=minutes_ago)
        
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT price FROM prices
                    WHERE symbol = %s 
                    AND timestamp <= %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (symbol, target_time))
                
                result = cur.fetchone()
                return result[0] if result else None
    
    def get_price_history(self, symbol, hours=24):
        """Get price history for a symbol"""
        since = datetime.now() - timedelta(hours=hours)
        
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT timestamp, price
                    FROM prices
                    WHERE symbol = %s AND timestamp >= %s
                    ORDER BY timestamp ASC
                """, (symbol, since))
                
                results = cur.fetchall()
                return [(row['timestamp'], row['price']) for row in results]
    
    def get_latest_prices(self):
        """Get latest price for each symbol"""
        with self.get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (symbol) 
                        symbol, price, timestamp
                    FROM prices
                    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                    ORDER BY symbol, timestamp DESC
                """)
                
                results = cur.fetchall()
                return {row['symbol']: row['price'] for row in results}
    
    def update_symbol_info(self, symbol_info_list):
        """Update symbol information"""
        if not symbol_info_list:
            return
        
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                for info in symbol_info_list:
                    cur.execute("""
                        INSERT INTO symbol_info (symbol, base_asset, quote_asset)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (symbol) 
                        DO UPDATE SET 
                            base_asset = EXCLUDED.base_asset,
                            quote_asset = EXCLUDED.quote_asset,
                            last_updated = CURRENT_TIMESTAMP
                    """, (info['symbol'], info['baseAsset'], info['quoteAsset']))
    
    def store_indicators(self, symbol, timeframe, indicators, composite_result):
        """Store calculated indicators and signals"""
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO indicators 
                    (symbol, timeframe, indicators, composite_score, signal)
                    VALUES (%s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (symbol, timeframe, timestamp) 
                    DO UPDATE SET
                        indicators = EXCLUDED.indicators,
                        composite_score = EXCLUDED.composite_score,
                        signal = EXCLUDED.signal
                """, (
                    symbol,
                    timeframe,
                    psycopg2.extras.Json(indicators),
                    composite_result.get('composite_score'),
                    composite_result.get('signal')
                ))
    
    def cleanup_old_data(self, days_to_keep=7):
        """Remove old data to save space"""
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        with self.get_conn() as conn:
            with conn.cursor() as cur:
                # Clean prices
                cur.execute("DELETE FROM prices WHERE timestamp < %s", (cutoff,))
                deleted_prices = cur.rowcount
                
                # Clean indicators
                cur.execute("DELETE FROM indicators WHERE timestamp < %s", (cutoff,))
                deleted_indicators = cur.rowcount
                
        logger.info(f"Cleaned up {deleted_prices} price records and {deleted_indicators} indicator records")
        
        return deleted_prices + deleted_indicators