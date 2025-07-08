"""
Flask web application with proper server setup
"""

from flask import Flask, render_template, jsonify
from datetime import datetime
import threading
import time
import logging
from queue import Queue

from config import (
    WEB_HOST, WEB_PORT, WEB_DEBUG, UPDATE_INTERVAL,
    CLEANUP_INTERVAL, CACHE_TTL
)
from core.database import Database
from core.tracker import BinanceTracker

logger = logging.getLogger(__name__)

# Global state
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
db = Database()
tracker = BinanceTracker(db)
update_queue = Queue(maxsize=1)
cache = {'data': [], 'last_update': None}
cache_lock = threading.Lock()


def background_updater():
    """Background thread for price updates"""
    last_cleanup = time.time()
    
    while True:
        try:
            # Update prices
            logger.info("Updating prices...")
            tracker.update_prices()
            
            # Get trending data with composite scores
            trending_data = tracker.get_enhanced_trending_data()
            
            # Update cache
            with cache_lock:
                cache['data'] = trending_data
                cache['last_update'] = datetime.now()
            
            logger.info(f"Updated {len(trending_data)} coins")
            
            # Periodic cleanup
            if time.time() - last_cleanup > CLEANUP_INTERVAL:
                db.cleanup_old_data()
                last_cleanup = time.time()
            
        except Exception as e:
            logger.error(f"Error in background updater: {e}")
        
        # Wait for next update
        time.sleep(UPDATE_INTERVAL)


@app.route('/')
def index():
    """Main page with enhanced signals"""
    return render_template('index_enhanced.html')

@app.route('/classic')
def classic():
    """Classic view without signals"""
    return render_template('index.html')


@app.route('/api/data')
def get_data():
    """API endpoint for table data"""
    with cache_lock:
        data = cache.get('data', [])
        last_update = cache.get('last_update')
    
    return jsonify({
        'data': data,
        'last_update': last_update.isoformat() if last_update else None,
        'total_coins': len(data)
    })


@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Force a data refresh"""
    try:
        # Queue an update (non-blocking)
        if update_queue.empty():
            update_queue.put(True)
            
            # Run update in thread
            def update():
                tracker.update_prices()
                trending_data = tracker.get_enhanced_trending_data()
                with cache_lock:
                    cache['data'] = trending_data
                    cache['last_update'] = datetime.now()
                update_queue.get()
            
            threading.Thread(target=update, daemon=True).start()
        
        return jsonify({'status': 'success', 'message': 'Refresh queued'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


def initialize():
    """Initialize the application"""
    # Start background updater
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    
    # Initial data load
    logger.info("Loading initial data...")
    tracker.update_prices()
    trending_data = tracker.get_trending_data()
    
    with cache_lock:
        cache['data'] = trending_data
        cache['last_update'] = datetime.now()
    
    logger.info(f"Initial load complete: {len(trending_data)} coins")


if __name__ == '__main__':
    # This should not be run directly
    raise RuntimeError("Please run main.py instead")