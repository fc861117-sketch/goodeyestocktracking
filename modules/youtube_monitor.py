"""
YouTube RSS Feed Monitor for Gooaye channel.
Detects new video uploads by comparing RSS feed against processed videos in DB.
"""

import feedparser
import logging
from modules import database as db

logger = logging.getLogger(__name__)

RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


def check_new_videos(channel_id, max_initial=1):
    """
    Check YouTube RSS feed for new videos.
    
    Args:
        channel_id: YouTube channel ID
        max_initial: Max videos to process on first run (avoids bulk processing)
    
    Returns:
        List of dicts with keys: video_id, title, url, published_at
    """
    rss_url = RSS_URL_TEMPLATE.format(channel_id)
    logger.info("Checking RSS feed: %s", rss_url)

    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        logger.error("Failed to parse RSS feed: %s", e)
        return []

    if not feed.entries:
        logger.warning("No entries found in RSS feed. URL may be invalid.")
        return []

    logger.info("Found %d entries in RSS feed", len(feed.entries))

    new_videos = []
    for entry in feed.entries:
        video_id = entry.get('yt_videoid', '')
        if not video_id:
            # Try extracting from link
            link = entry.get('link', '')
            if 'v=' in link:
                video_id = link.split('v=')[-1].split('&')[0]

        if not video_id:
            continue

        if db.is_video_processed(video_id):
            logger.debug("Video already processed: %s", video_id)
            continue

        video_info = {
            'video_id': video_id,
            'title': entry.get('title', 'Unknown Title'),
            'url': entry.get('link', f'https://www.youtube.com/watch?v={video_id}'),
            'published_at': entry.get('published', ''),
        }
        new_videos.append(video_info)
        logger.info("New video detected: [%s] %s", video_id, video_info['title'])

    # On first run with empty DB, limit to most recent N videos
    if new_videos:
        total_in_db = len(db.get_all_videos())
        if total_in_db == 0 and len(new_videos) > max_initial:
            logger.info(
                "First run: limiting to %d most recent videos (out of %d new)",
                max_initial, len(new_videos)
            )
            new_videos = new_videos[:max_initial]
        elif total_in_db > 0 and len(new_videos) > max_initial:
            # If user explicitly passed a limit or we just want to limit batch size
            logger.info(
                "Limiting to %d most recent videos (out of %d new)",
                max_initial, len(new_videos)
            )
            new_videos = new_videos[:max_initial]

    return new_videos

def fetch_videos_since(channel_id, since_date_str, limit=None):
    """
    Fetch all videos since a specific date using yt-dlp.
    since_date_str format: YYYYMMDD (e.g., '20260501')
    """
    import yt_dlp
    
    logger.info("Fetching playlist metadata using yt-dlp since %s", since_date_str)
    
    url = f"https://www.youtube.com/channel/{channel_id}"
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': False,
        'dateafter': since_date_str,
    }
    
    videos_to_process = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    
                    if db.is_video_processed(video_id):
                        logger.debug("Video already processed: %s", video_id)
                        continue
                        
                    videos_to_process.append({
                        'video_id': video_id,
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('url', f'https://www.youtube.com/watch?v={video_id}'),
                        'published_at': entry.get('upload_date', '')
                    })
    except Exception as e:
        logger.error("Failed to fetch videos via yt-dlp: %s", e)
        
    videos_to_process = list(reversed(videos_to_process)) # oldest first
    
    if limit and len(videos_to_process) > limit:
        # If limiting, take the most recent ones up to limit
        videos_to_process = videos_to_process[-limit:]
        
    return videos_to_process

