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
