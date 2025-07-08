"""
Cloud configuration that automatically switches between SQLite and PostgreSQL
"""

import os
from config import *  # Import all existing config

# Detect if we're in cloud environment
IS_CLOUD = os.environ.get('DATABASE_URL') is not None

if IS_CLOUD:
    # Override database settings for cloud
    print("Running in cloud mode with PostgreSQL")
    
    # Use PostgreSQL in cloud
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Adjust intervals for cloud
    UPDATE_INTERVAL = 60  # Update every minute instead of 30 seconds
    CLEANUP_INTERVAL = 3600 * 6  # Cleanup every 6 hours
    CACHE_TTL = 300  # Cache for 5 minutes
    
    # Reduce batch sizes for free tier
    BATCH_SIZE = 20  # Reduced from 50
    MAX_CONCURRENT_REQUESTS = 3  # Reduced from 5
else:
    print("Running in local mode with SQLite")


def get_database():
    """Factory function to get appropriate database instance"""
    if IS_CLOUD:
        from core.database_postgres import PostgresDatabase
        return PostgresDatabase(DATABASE_URL)
    else:
        from core.database import Database
        return Database()