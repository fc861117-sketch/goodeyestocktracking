"""
SQLite Database Manager for Gooaye Stock Analyzer.
Manages three core tables: videos, recommendations, performance_tracking.
"""

import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Database path relative to project root
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'gooaye.db')


def get_connection():
    """Get a SQLite connection with row factory enabled."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables and indexes."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            published_at TEXT,
            processed_at TEXT,
            transcript TEXT,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT NOT NULL REFERENCES videos(video_id),
            stock_symbol TEXT NOT NULL,
            stock_name TEXT,
            market TEXT DEFAULT 'TW',
            sentiment TEXT DEFAULT 'neutral',
            gooaye_opinion TEXT,
            price_at_mention REAL,
            target_price REAL,
            buy_price REAL,
            stop_loss REAL,
            short_term_advice TEXT,
            mid_term_advice TEXT,
            long_term_advice TEXT,
            sector TEXT,
            analysis_detail TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS performance_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL REFERENCES recommendations(id),
            tracked_date TEXT NOT NULL,
            current_price REAL,
            price_change_pct REAL,
            UNIQUE(recommendation_id, tracked_date)
        );

        CREATE INDEX IF NOT EXISTS idx_rec_video ON recommendations(video_id);
        CREATE INDEX IF NOT EXISTS idx_rec_symbol ON recommendations(stock_symbol);
        CREATE INDEX IF NOT EXISTS idx_perf_rec ON performance_tracking(recommendation_id);
        CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_tracking(tracked_date);
    ''')

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", DB_PATH)


def is_video_processed(video_id):
    """Check if a video has already been processed."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM videos WHERE video_id = ?", (video_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_video(video_id, title, url, published_at, transcript, summary):
    """Save or update a processed video record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO videos
        (video_id, title, url, published_at, processed_at, transcript, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (video_id, title, url, published_at, datetime.now().isoformat(), transcript, summary))
    conn.commit()
    conn.close()
    logger.info("Saved video: %s - %s", video_id, title)


def save_recommendation(video_id, stock_symbol, stock_name, market, sentiment,
                        gooaye_opinion, price_at_mention, target_price, buy_price,
                        stop_loss, short_term_advice, mid_term_advice, long_term_advice,
                        sector, analysis_detail):
    """Save a stock recommendation extracted from a video."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO recommendations
        (video_id, stock_symbol, stock_name, market, sentiment, gooaye_opinion,
         price_at_mention, target_price, buy_price, stop_loss,
         short_term_advice, mid_term_advice, long_term_advice, sector, analysis_detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (video_id, stock_symbol, stock_name, market, sentiment, gooaye_opinion,
          price_at_mention, target_price, buy_price, stop_loss,
          short_term_advice, mid_term_advice, long_term_advice, sector, analysis_detail))
    rec_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info("Saved recommendation: %s (%s) from video %s", stock_name, stock_symbol, video_id)
    return rec_id


def save_performance(recommendation_id, tracked_date, current_price, price_change_pct):
    """Save or update a performance tracking record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO performance_tracking
        (recommendation_id, tracked_date, current_price, price_change_pct)
        VALUES (?, ?, ?, ?)
    ''', (recommendation_id, tracked_date, current_price, price_change_pct))
    conn.commit()
    conn.close()


def get_all_videos():
    """Get all processed videos, newest first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos ORDER BY published_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_video(video_id):
    """Get a single video by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recommendations_for_video(video_id):
    """Get all recommendations for a specific video."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM recommendations WHERE video_id = ? ORDER BY id",
        (video_id,)
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_all_recommendations():
    """Get all recommendations with latest performance data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*,
               v.title as video_title,
               v.published_at as video_date,
               pt.current_price as latest_price,
               pt.price_change_pct as latest_change_pct,
               pt.tracked_date as last_tracked
        FROM recommendations r
        LEFT JOIN videos v ON r.video_id = v.video_id
        LEFT JOIN performance_tracking pt ON pt.recommendation_id = r.id
            AND pt.tracked_date = (
                SELECT MAX(tracked_date)
                FROM performance_tracking
                WHERE recommendation_id = r.id
            )
        ORDER BY r.created_at DESC
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_recommendation(rec_id):
    """Get a single recommendation by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_performance_history(recommendation_id):
    """Get the performance tracking history for a recommendation."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT tracked_date, current_price, price_change_pct
        FROM performance_tracking
        WHERE recommendation_id = ?
        ORDER BY tracked_date ASC
    ''', (recommendation_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_dashboard_summary():
    """Get aggregated dashboard summary statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total videos
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    total_videos = cursor.fetchone()['count']

    # Total recommendations
    cursor.execute("SELECT COUNT(*) as count FROM recommendations")
    total_recs = cursor.fetchone()['count']

    # Average performance (latest tracking for each recommendation)
    cursor.execute('''
        SELECT AVG(pt.price_change_pct) as avg_change,
               MAX(pt.price_change_pct) as best_change,
               MIN(pt.price_change_pct) as worst_change
        FROM performance_tracking pt
        INNER JOIN (
            SELECT recommendation_id, MAX(tracked_date) as max_date
            FROM performance_tracking
            GROUP BY recommendation_id
        ) latest ON pt.recommendation_id = latest.recommendation_id
            AND pt.tracked_date = latest.max_date
    ''')
    perf = cursor.fetchone()

    # Best performer
    cursor.execute('''
        SELECT r.stock_name, r.stock_symbol, pt.price_change_pct
        FROM performance_tracking pt
        JOIN recommendations r ON r.id = pt.recommendation_id
        INNER JOIN (
            SELECT recommendation_id, MAX(tracked_date) as max_date
            FROM performance_tracking
            GROUP BY recommendation_id
        ) latest ON pt.recommendation_id = latest.recommendation_id
            AND pt.tracked_date = latest.max_date
        ORDER BY pt.price_change_pct DESC LIMIT 1
    ''')
    best = cursor.fetchone()

    # Worst performer
    cursor.execute('''
        SELECT r.stock_name, r.stock_symbol, pt.price_change_pct
        FROM performance_tracking pt
        JOIN recommendations r ON r.id = pt.recommendation_id
        INNER JOIN (
            SELECT recommendation_id, MAX(tracked_date) as max_date
            FROM performance_tracking
            GROUP BY recommendation_id
        ) latest ON pt.recommendation_id = latest.recommendation_id
            AND pt.tracked_date = latest.max_date
        ORDER BY pt.price_change_pct ASC LIMIT 1
    ''')
    worst = cursor.fetchone()

    # Sector distribution
    cursor.execute('''
        SELECT sector, COUNT(*) as count
        FROM recommendations
        WHERE sector IS NOT NULL AND sector != ''
        GROUP BY sector
        ORDER BY count DESC
    ''')
    sectors = [dict(r) for r in cursor.fetchall()]

    # Sentiment distribution
    cursor.execute('''
        SELECT sentiment, COUNT(*) as count
        FROM recommendations
        GROUP BY sentiment
    ''')
    sentiments = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        'total_videos': total_videos,
        'total_recommendations': total_recs,
        'avg_performance': round(perf['avg_change'], 2) if perf['avg_change'] else 0,
        'best_performance': round(perf['best_change'], 2) if perf['best_change'] else 0,
        'worst_performance': round(perf['worst_change'], 2) if perf['worst_change'] else 0,
        'best_performer': {
            'name': best['stock_name'],
            'symbol': best['stock_symbol'],
            'change': round(best['price_change_pct'], 2)
        } if best else None,
        'worst_performer': {
            'name': worst['stock_name'],
            'symbol': worst['stock_symbol'],
            'change': round(worst['price_change_pct'], 2)
        } if worst else None,
        'sectors': sectors,
        'sentiments': sentiments,
    }


def get_all_trackable_recommendations():
    """Get all recommendations with their price_at_mention for tracking."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, stock_symbol, market, price_at_mention
        FROM recommendations
        WHERE price_at_mention IS NOT NULL AND price_at_mention > 0
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
