"""
Gooaye Stock Analyzer - Main Entry Point

Usage:
    python main.py analyze          Check for new videos and analyze them
    python main.py update-prices    Update current prices for tracked stocks
    python main.py dashboard        Launch the Web Dashboard
    python main.py generate-static  Generate static HTML and data.json for GitHub Pages
    python main.py backfill <date>  Fetch and analyze all videos since YYYYMMDD (e.g. 20260501)
"""

import sys
import os
import json
import logging
import argparse
import webbrowser
from datetime import datetime

# Fix Windows console encoding for Unicode output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from modules import database as db
from modules import youtube_monitor
from modules import audio_downloader
from modules import transcriber
from modules import report_generator
from modules import performance_tracker
from modules import static_generator


def setup_logging():
    """Configure logging with both console and file output."""
    log_dir = os.path.join(PROJECT_ROOT, 'data')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'gooaye_analyzer.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8'),
        ]
    )


def load_config():
    """Load configuration from config.json."""
    config_path = os.path.join(PROJECT_ROOT, 'config.json')
    if not os.path.exists(config_path):
        print("ERROR: config.json not found. Please create it with your Gemini API key.")
        sys.exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    if config.get('gemini_api_key', '') in ('', 'YOUR_API_KEY_HERE'):
        print("ERROR: Please set your Gemini API key in config.json")
        sys.exit(1)

    return config


def process_video(video_info, config):
    """Process a single video: download → transcribe → analyze → report."""
    logger = logging.getLogger('main')
    video_id = video_info['video_id']

    logger.info("Processing video: [%s] %s", video_id, video_info['title'])

    # Step 1: Try to get subtitles first (faster than Whisper)
    logger.info("🔍 Attempting to download subtitles...")
    transcript = audio_downloader.download_subtitles(video_info['url'], video_id)

    if transcript:
        logger.info("✓ Subtitles found! (%d characters)", len(transcript))
    else:
        # Step 2: Download audio and transcribe with Whisper
        logger.info("📥 No subtitles found. Downloading audio...")
        try:
            audio_path = audio_downloader.download_audio(video_info['url'], video_id)
        except Exception as e:
            logger.error("❌ Failed to download audio: %s", e)
            return None

        logger.info("🎤 Transcribing with Whisper (model=%s, device=%s)...",
                     config['whisper_model'], config['whisper_device'])
        logger.info("⏳ This may take 5-15 minutes depending on audio length...")

        try:
            transcript = transcriber.transcribe(
                audio_path,
                model_name=config['whisper_model'],
                device=config['whisper_device'],
                language=config['language'],
            )
            logger.info("✓ Transcription complete! (%d characters)", len(transcript))
        except Exception as e:
            logger.error("❌ Transcription failed: %s", e)
            return None
        finally:
            # Clean up audio file
            audio_downloader.cleanup_audio(video_id)

    if not transcript or len(transcript.strip()) < 50:
        logger.error("❌ Transcript too short or empty. Skipping.")
        return None

    # Step 3: Generate report (AI analysis + stock data + investment advice)
    logger.info("🤖 Analyzing content and generating report...")
    try:
        report = report_generator.generate_report(
            video_info, transcript, config['gemini_api_key']
        )
        return report
    except Exception as e:
        logger.error("❌ Report generation failed: %s", e)
        return None


def cmd_analyze(config, limit=None):
    """Check for new videos and analyze them."""
    logger = logging.getLogger('main')

    logger.info("🔍 Checking for new videos from 股癌 (Gooaye)...")
    
    limit_val = limit if limit is not None else config.get('max_initial_videos', 1)

    new_videos = youtube_monitor.check_new_videos(
        config['youtube_channel_id'],
        max_initial=limit_val
    )

    if not new_videos:
        logger.info("✓ No new videos found. Everything is up to date!")
        return

    logger.info("📺 Found %d new video(s) to process:", len(new_videos))
    for v in new_videos:
        logger.info("  → %s", v['title'])

    for video_info in new_videos:
        report = process_video(video_info, config)
        if report:
            recs = report.get('recommendations', [])
            logger.info("")
            logger.info("📊 Report Summary for: %s", video_info['title'])
            logger.info("   Stocks identified: %d", len(recs))
            for rec in recs:
                sentiment_emoji = {
                    'bullish': '🟢',
                    'bearish': '🔴',
                    'neutral': '⚪'
                }.get(rec.get('sentiment'), '⚪')
                logger.info("   %s %s (%s) - Price: %s",
                             sentiment_emoji,
                             rec.get('stock_name'),
                             rec.get('stock_symbol'),
                             rec.get('current_price'))
            logger.info("")

    # Update prices for all tracked recommendations
    logger.info("📈 Updating performance tracking...")
    performance_tracker.update_all_prices()

    # Generate static site for GitHub pages
    logger.info("📄 Generating static site for GitHub Pages...")
    static_generator.generate_static_site()

    logger.info("✅ Analysis complete! Launch the dashboard to view reports:")
    logger.info("   python main.py dashboard")
    logger.info("   (Or open docs/index.html directly)")


def cmd_generate_static(config):
    """Generate static site from current database."""
    logger = logging.getLogger('main')
    logger.info("📄 Generating static site...")
    static_generator.generate_static_site()
    logger.info("✅ Static site generated in docs/ folder.")

def cmd_backfill(config, since_date, limit=None):
    """Fetch and process old videos using yt-dlp from a specific date."""
    logger = logging.getLogger('main')
    logger.info(f"⏪ Backfilling videos since {since_date}...")
    
    videos = youtube_monitor.fetch_videos_since(
        config['youtube_channel_id'],
        since_date,
        limit=limit
    )
    
    if not videos:
        logger.info("No videos found to backfill.")
        return
        
    logger.info(f"Found {len(videos)} videos to backfill.")
    for v in videos:
        logger.info(f"  → [{v['video_id']}] {v['title']}")
        
    # Process them one by one
    for i, video_info in enumerate(videos):
        logger.info(f"=== Processing Backfill {i+1}/{len(videos)} ===")
        process_video(video_info, config)
        
    logger.info("📈 Updating performance tracking...")
    performance_tracker.update_all_prices()
    
    logger.info("📄 Generating static site...")
    static_generator.generate_static_site()
    
    logger.info("✅ Backfill complete!")


def cmd_update_prices(config):
    """Update current prices for all tracked recommendations."""
    logger = logging.getLogger('main')
    logger.info("📈 Updating stock prices for all tracked recommendations...")

    stats = performance_tracker.update_all_prices()

    logger.info("✅ Price update complete:")
    logger.info("   Updated: %d", stats['updated'])
    logger.info("   Failed:  %d", stats['failed'])
    logger.info("   Total:   %d", stats['total'])


def cmd_dashboard(config):
    """Launch the Flask web dashboard."""
    logger = logging.getLogger('main')
    port = config.get('dashboard_port', 5000)

    logger.info("🌐 Starting Web Dashboard on http://localhost:%d", port)

    # Open browser
    webbrowser.open(f'http://localhost:{port}')

    # Import and run Flask app
    from server import create_app
    app = create_app(config)
    app.run(host='0.0.0.0', port=port, debug=False)


def main():
    setup_logging()
    logger = logging.getLogger('main')

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='股癌 (Gooaye) 自動影片分析 & 股票推薦系統',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  analyze         Check for new videos and generate analysis reports
  update-prices   Update current prices for all tracked stocks
  dashboard       Launch the Web Dashboard (http://localhost:5000)
  generate-static Generate static site to docs/ for GitHub Pages
  backfill        Analyze all videos since a given date

Examples:
  python main.py analyze
  python main.py dashboard
  python main.py generate-static
  python main.py backfill 20260501
        """
    )
    parser.add_argument('command', choices=['analyze', 'update-prices', 'dashboard', 'generate-static', 'backfill'],
                        help='Command to execute')
    parser.add_argument('date', nargs='?', default=None, help='Date for backfill (YYYYMMDD)')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of videos to process')

    args = parser.parse_args()

    # Load config
    config = load_config()

    # Initialize database
    db.init_db()

    logger.info("=" * 60)
    logger.info("股癌 (Gooaye) Stock Analyzer v1.0")
    logger.info("Time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)

    # Execute command
    if args.command == 'analyze':
        cmd_analyze(config, args.limit)
    elif args.command == 'update-prices':
        cmd_update_prices(config)
    elif args.command == 'dashboard':
        cmd_dashboard(config)
    elif args.command == 'generate-static':
        cmd_generate_static(config)
    elif args.command == 'backfill':
        if not args.date:
            logger.error("❌ backfill command requires a date argument (YYYYMMDD). Example: python main.py backfill 20260501")
            sys.exit(1)
        cmd_backfill(config, args.date, args.limit)


if __name__ == '__main__':
    main()
