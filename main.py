#!/usr/bin/env python3
"""
Main entry point with proper process management
"""

import os
import sys
import signal
import logging
import fcntl
from pathlib import Path
import psutil
import argparse

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    PID_FILE, LOCK_FILE, LOG_FILE, LOG_LEVEL, LOG_FORMAT,
    WEB_HOST, WEB_PORT, WEB_DEBUG
)

# Set up logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TrackerManager:
    """Manages the tracker process lifecycle"""
    
    def __init__(self):
        self.pid_file = PID_FILE
        self.lock_file = LOCK_FILE
        self.lock_fd = None
        
    def acquire_lock(self):
        """Acquire exclusive lock to prevent multiple instances"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            return True
        except IOError:
            logger.error("Another instance is already running")
            return False
    
    def release_lock(self):
        """Release the lock"""
        if self.lock_fd:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            self.lock_fd.close()
            if self.lock_file.exists():
                self.lock_file.unlink()
    
    def check_port(self):
        """Check if port is available"""
        for conn in psutil.net_connections():
            if conn.laddr.port == WEB_PORT and conn.status == 'LISTEN':
                logger.warning(f"Port {WEB_PORT} is already in use")
                return False
        return True
    
    def kill_existing(self):
        """Kill any existing processes on our port"""
        killed = False
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == WEB_PORT and conn.status == 'LISTEN':
                        logger.info(f"Killing process {proc.pid} using port {WEB_PORT}")
                        proc.terminate()
                        proc.wait(timeout=5)
                        killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return killed
    
    def cleanup(self, signum=None, frame=None):
        """Clean up resources"""
        logger.info("Shutting down...")
        self.release_lock()
        if self.pid_file.exists():
            self.pid_file.unlink()
        sys.exit(0)
    
    def run(self):
        """Run the tracker"""
        # Check if we can acquire lock
        if not self.acquire_lock():
            return 1
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        # Check port availability
        if not self.check_port():
            if self.kill_existing():
                import time
                time.sleep(1)
            else:
                logger.error(f"Cannot bind to port {WEB_PORT}")
                self.cleanup()
                return 1
        
        # Write PID file
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            # Import and run the web app
            from web.app import app, initialize
            
            logger.info("Initializing tracker...")
            initialize()
            
            # Use Waitress for production
            if not WEB_DEBUG:
                from waitress import serve
                logger.info(f"Starting production server on {WEB_HOST}:{WEB_PORT}")
                serve(app, host=WEB_HOST, port=WEB_PORT, threads=4)
            else:
                logger.info(f"Starting development server on {WEB_HOST}:{WEB_PORT}")
                app.run(host=WEB_HOST, port=WEB_PORT, debug=True, use_reloader=False)
                
        except Exception as e:
            logger.error(f"Failed to start tracker: {e}")
            self.cleanup()
            return 1
        
        return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Binance Tracker V2')
    parser.add_argument('--kill', action='store_true', help='Kill existing instance')
    args = parser.parse_args()
    
    manager = TrackerManager()
    
    if args.kill:
        manager.kill_existing()
        return 0
    
    return manager.run()


if __name__ == '__main__':
    sys.exit(main())