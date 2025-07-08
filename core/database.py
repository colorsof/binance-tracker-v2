"""
Database management with proper connection handling and WAL mode
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

from config import DATABASE_PATH, DATABASE_TIMEOUT, DATA_RETENTION_DAYS

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe database manager with connection pooling and retry logic"""
    
    def __init__(self):
        self.path = DATABASE_PATH
        self.timeout = DATABASE_TIMEOUT
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database with WAL mode and create tables"""
        with self._get_connection() as conn:
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            
            # Create tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    timestamp DATETIME NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbol_info (
                    symbol TEXT PRIMARY KEY,
                    base_asset TEXT NOT NULL,
                    quote_asset TEXT NOT NULL,
                    last_update DATETIME NOT NULL
                )
            """)
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timestamp 
                ON price_history(symbol, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON price_history(timestamp DESC)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.path,
                timeout=self.timeout,
                isolation_level=None  # autocommit mode
            )
            self._local.conn.row_factory = sqlite3.Row
        
        try:
            yield self._local.conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.error("Database locked, retrying...")
                time.sleep(0.1)
                raise
            else:
                raise
    
    def store_prices(self, prices: Dict[str, float]):
        """Store multiple prices in a single transaction"""
        timestamp = datetime.now()
        data = [(symbol, price, timestamp) for symbol, price in prices.items() if price > 0]
        
        with self._lock:
            with self._get_connection() as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO price_history (symbol, price, timestamp) VALUES (?, ?, ?)",
                    data
                )
    
    def get_price_history(self, symbol: str, hours: float) -> List[Tuple[datetime, float]]:
        """Get price history for a symbol"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT timestamp, price 
                FROM price_history 
                WHERE symbol = ? AND timestamp >= ?
                ORDER BY timestamp
            """, (symbol, cutoff))
            
            return [(datetime.fromisoformat(row['timestamp']), row['price']) 
                    for row in cursor.fetchall()]
    
    def get_latest_prices(self) -> Dict[str, float]:
        """Get the latest price for all symbols"""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT symbol, price
                FROM price_history
                WHERE timestamp IN (
                    SELECT MAX(timestamp)
                    FROM price_history
                    GROUP BY symbol
                )
            """)
            
            return {row['symbol']: row['price'] for row in cursor.fetchall()}
    
    def get_price_at_interval(self, symbol: str, minutes_ago: int) -> Optional[float]:
        """Get price from N minutes ago"""
        target_time = datetime.now() - timedelta(minutes=minutes_ago)
        window = timedelta(minutes=2)  # 2 minute window
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT price 
                FROM price_history 
                WHERE symbol = ? 
                AND timestamp BETWEEN ? AND ?
                ORDER BY ABS(julianday(timestamp) - julianday(?))
                LIMIT 1
            """, (symbol, target_time - window, target_time + window, target_time))
            
            row = cursor.fetchone()
            return row['price'] if row else None
    
    def update_symbol_info(self, symbols: List[Dict]):
        """Update symbol information"""
        timestamp = datetime.now()
        data = [(s['symbol'], s['baseAsset'], s['quoteAsset'], timestamp) 
                for s in symbols]
        
        with self._lock:
            with self._get_connection() as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO symbol_info 
                    (symbol, base_asset, quote_asset, last_update) 
                    VALUES (?, ?, ?, ?)
                """, data)
    
    def cleanup_old_data(self):
        """Remove old price data"""
        cutoff = datetime.now() - timedelta(days=DATA_RETENTION_DAYS)
        
        with self._lock:
            with self._get_connection() as conn:
                deleted = conn.execute(
                    "DELETE FROM price_history WHERE timestamp < ?",
                    (cutoff,)
                ).rowcount
                
                if deleted > 0:
                    conn.execute("VACUUM")
                    logger.info(f"Cleaned up {deleted} old price records")
    
    def close(self):
        """Close the database connection"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None