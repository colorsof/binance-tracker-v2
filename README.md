# Binance Tracker V2

A clean, efficient cryptocurrency tracker for Binance spot trading pairs.

## Features

- **Table View**: Professional table layout with sortable columns
- **Multiple Timeframes**: Tracks 1m, 30m, 1h, 2h, 3h, 4h, 5h, 6h, 7h changes
- **Bitcoin Correlation**: Shows correlation percentage with BTC
- **Smart Filtering**: 
  - Minimum growth threshold
  - Symbol search
  - Correlation filtering (High/Medium/Low)
- **Real-time Updates**: Auto-refresh every 30 seconds
- **Persistent Storage**: SQLite with WAL mode for concurrent access
- **Production Ready**: Proper process management and error handling

## Architecture

```
binance_tracker_v2/
├── core/
│   ├── database.py      # Database management with WAL mode
│   └── tracker.py       # Binance API integration
├── web/
│   └── app.py          # Flask application
├── static/
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript
├── templates/         # HTML templates
├── data/             # Database and logs
├── config.py         # Configuration
├── main.py          # Entry point with process management
└── start.sh         # Start script
```

## Key Improvements

1. **No Port Conflicts**: Automatic port management
2. **No Database Locks**: WAL mode + proper connection handling
3. **Single Instance**: File-based locking prevents duplicates
4. **Clean Shutdown**: Proper signal handling
5. **Production Server**: Uses Waitress instead of Flask dev server
6. **Efficient Updates**: Batch API calls, no rate limiting issues

## Usage

```bash
# Start the tracker
./start.sh

# Access web interface
http://127.0.0.1:5000

# Stop the tracker
Ctrl+C
```

## Configuration

Edit `config.py` to customize:
- Price range (default: $0.001 - $10)
- Update interval (default: 60 seconds)
- Time intervals for tracking
- Display settings

## Requirements

- Python 3.7+
- 100MB disk space
- Internet connection

## Performance

- Handles 500+ trading pairs efficiently
- Updates complete in < 5 seconds
- Low memory footprint (~100MB)
- Concurrent-safe database operations