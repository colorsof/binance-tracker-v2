"""
Configuration settings for Binance Tracker V2
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database
DATABASE_PATH = DATA_DIR / "tracker.db"
DATABASE_TIMEOUT = 30.0  # seconds

# Binance API
BINANCE_API_URL = "https://api.binance.com/api/v3"
API_RATE_LIMIT_DELAY = 0.1  # seconds between API calls

# Trading pairs
TARGET_STABLECOINS = ['USDT', 'USDC']
PRICE_RANGE = (0.001, 10.0)  # USD

# Time intervals for tracking (in minutes)
TIME_INTERVALS = {
    '5m': 5,
    '15m': 15,
    '30m': 30,
    '1h': 60,
    '2h': 120,
    '4h': 240,
    '7h': 420,
    '12h': 720
}

# Consistency scoring
CONSISTENCY_THRESHOLD = 55  # minimum score to be considered consistent
CONSISTENCY_MAX_DIFF = 5.0  # max % difference between periods for consistency

# Update settings
UPDATE_INTERVAL = 60  # seconds between price updates
CLEANUP_INTERVAL = 3600  # seconds between database cleanup
DATA_RETENTION_DAYS = 7  # days to keep historical data

# Web server
WEB_HOST = '127.0.0.1'
WEB_PORT = 5000
WEB_DEBUG = False

# Process management
PID_FILE = DATA_DIR / "tracker.pid"
LOCK_FILE = DATA_DIR / "tracker.lock"

# Logging
LOG_FILE = DATA_DIR / "tracker.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance
MAX_CONCURRENT_REQUESTS = 10  # for API calls
BATCH_SIZE = 50  # symbols per batch
CACHE_TTL = 30  # seconds to cache calculations

# Display settings
DEFAULT_SORT_COLUMN = '7h'  # sort by 7 hour change by default
DEFAULT_SORT_ORDER = 'desc'
MIN_GROWTH_THRESHOLD = 0.0  # minimum % to display