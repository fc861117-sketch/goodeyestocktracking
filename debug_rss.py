"""Verify the correct channel ID."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import feedparser

channel_id = "UC23rnlQU_qE3cec9x709peA"
url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
print(f"Testing: {url}")
feed = feedparser.parse(url)
print(f"Entries: {len(feed.entries)}")
print(f"Feed title: {feed.feed.get('title', 'N/A')}")
if feed.entries:
    for e in feed.entries[:5]:
        vid = e.get('yt_videoid', 'N/A')
        print(f"  [{vid}] {e.get('title', 'N/A')}")
        print(f"    Published: {e.get('published', 'N/A')}")
