"""
Flask Web Server for Gooaye Stock Analyzer Dashboard.
Serves the dashboard UI and provides REST API endpoints.
"""

import os
import sys
import json
import logging
from flask import Flask, render_template, jsonify, request

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from modules import database as db
from modules import performance_tracker

logger = logging.getLogger(__name__)


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, 'templates'),
        static_folder=os.path.join(PROJECT_ROOT, 'static'),
    )

    if config is None:
        config_path = os.path.join(PROJECT_ROOT, 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    app.config['GOOAYE_CONFIG'] = config

    # Initialize database
    db.init_db()

    # --- Routes ---

    @app.route('/')
    def dashboard():
        """Serve the main dashboard page."""
        return render_template('dashboard.html')

    @app.route('/api/dashboard-summary')
    def api_dashboard_summary():
        """Get dashboard summary statistics."""
        try:
            summary = db.get_dashboard_summary()
            return jsonify(summary)
        except Exception as e:
            logger.error("Error getting dashboard summary: %s", e)
            return jsonify({
                'total_videos': 0,
                'total_recommendations': 0,
                'avg_performance': 0,
                'best_performance': 0,
                'worst_performance': 0,
                'best_performer': None,
                'worst_performer': None,
                'sectors': [],
                'sentiments': [],
            })

    @app.route('/api/reports')
    def api_reports():
        """Get all video reports."""
        videos = db.get_all_videos()
        # Attach recommendations count to each video
        for v in videos:
            recs = db.get_recommendations_for_video(v['video_id'])
            v['recommendation_count'] = len(recs)
        return jsonify(videos)

    @app.route('/api/report/<video_id>')
    def api_report_detail(video_id):
        """Get detailed report for a specific video."""
        video = db.get_video(video_id)
        if not video:
            return jsonify({'error': 'Video not found'}), 404

        recs = db.get_recommendations_for_video(video_id)

        # Get latest performance for each recommendation
        for rec in recs:
            perf = db.get_performance_history(rec['id'])
            rec['performance_history'] = perf
            if perf:
                latest = perf[-1]
                rec['latest_price'] = latest['current_price']
                rec['latest_change_pct'] = latest['price_change_pct']
            else:
                rec['latest_price'] = rec.get('price_at_mention')
                rec['latest_change_pct'] = 0

        return jsonify({
            'video': video,
            'recommendations': recs,
        })

    @app.route('/api/recommendations')
    def api_recommendations():
        """Get all stock recommendations with latest performance."""
        recs = db.get_all_recommendations()
        return jsonify(recs)

    @app.route('/api/performance/<int:rec_id>')
    def api_performance(rec_id):
        """Get performance tracking history for a recommendation."""
        rec = db.get_recommendation(rec_id)
        if not rec:
            return jsonify({'error': 'Recommendation not found'}), 404

        history = db.get_performance_history(rec_id)

        return jsonify({
            'recommendation': rec,
            'history': history,
        })

    @app.route('/api/performance-by-symbol/<symbol>')
    def api_performance_by_symbol(symbol):
        """Get consolidated performance and all recommendation records for a symbol."""
        try:
            # Find all recommendations for this symbol
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.*, v.published_at as video_date, v.title as video_title,
                       pt.current_price as latest_price, pt.price_change_pct as latest_change_pct
                FROM recommendations r
                JOIN videos v ON r.video_id = v.video_id
                LEFT JOIN performance_tracking pt ON pt.recommendation_id = r.id
                    AND pt.tracked_date = (
                        SELECT MAX(tracked_date)
                        FROM performance_tracking
                        WHERE recommendation_id = r.id
                    )
                WHERE r.stock_symbol = ?
                ORDER BY r.id DESC
            ''', (symbol,))
            recs = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            if recs:
                latest_rec = recs[0]
                history = db.get_performance_history(latest_rec['id'])
                return jsonify({
                    'recommendation': latest_rec,
                    'all_mentions': recs,
                    'history': history
                })
            else:
                # Check if it's a custom stock
                clean_sym = symbol.strip()
                is_tw = any(c.isdigit() for c in clean_sym) or clean_sym.endswith('.TW') or clean_sym.endswith('.TWO')
                market = 'TW' if is_tw else 'US'
                from modules import stock_data
                stock_info = stock_data.get_stock_data(clean_sym, market)
                hist_prices = stock_data.get_historical_prices(clean_sym, market, period="3mo")
                if stock_info and not stock_info.get('error') and stock_info.get('current_price') is not None:
                    price_at_mention = hist_prices[0][1] if hist_prices else stock_info['current_price']
                    latest_price = stock_info['current_price']
                    latest_change_pct = 0.0
                    if price_at_mention > 0:
                        latest_change_pct = ((latest_price - price_at_mention) / price_at_mention) * 100
                    custom_rec = {
                        'stock_symbol': clean_sym,
                        'stock_name': stock_info['fundamentals'].get('company_name', clean_sym),
                        'market': market,
                        'price_at_mention': price_at_mention,
                        'latest_price': latest_price,
                        'latest_change_pct': latest_change_pct,
                        'is_custom': True
                    }
                    custom_history = [{'tracked_date': h[0], 'current_price': h[1], 'price_change_pct': 0.0} for h in hist_prices]
                    return jsonify({
                        'recommendation': custom_rec,
                        'all_mentions': [],
                        'history': custom_history
                    })
                return jsonify({'error': 'Stock not found'}), 404
        except Exception as e:
            logger.error("Error in performance-by-symbol for %s: %s", symbol, e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/update-prices', methods=['POST'])
    def api_update_prices():
        """Trigger manual price update for all tracked stocks."""
        try:
            stats = performance_tracker.update_all_prices()
            return jsonify({
                'success': True,
                'stats': stats,
            })
        except Exception as e:
            logger.error("Price update failed: %s", e)
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    config_path = os.path.join(PROJECT_ROOT, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    app = create_app(config)
    app.run(host='0.0.0.0', port=config.get('dashboard_port', 5000), debug=True)
