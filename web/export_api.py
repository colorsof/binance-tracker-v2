"""
API endpoints for data export
"""

from flask import Blueprint, jsonify, send_file
import pandas as pd
import io
from datetime import datetime

export_bp = Blueprint('export', __name__)

@export_bp.route('/api/export/signals/csv')
def export_signals_csv():
    """Export current signals as CSV"""
    from web.app import cache, cache_lock
    
    with cache_lock:
        data = cache.get('data', [])
    
    if not data:
        return jsonify({'error': 'No data available'}), 404
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Select relevant columns
    columns = ['symbol', 'signal', 'composite_score', 'price', 
               'technical_score', 'growth_score', 'consistency_score']
    df = df[columns]
    
    # Create CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    # Convert to bytes
    output_bytes = io.BytesIO(output.getvalue().encode())
    output_bytes.seek(0)
    
    filename = f"binance_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return send_file(
        output_bytes,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@export_bp.route('/api/export/signals/json')
def export_signals_json():
    """Export current signals as JSON"""
    from web.app import cache, cache_lock
    
    with cache_lock:
        data = cache.get('data', [])
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'count': len(data),
        'signals': data
    })