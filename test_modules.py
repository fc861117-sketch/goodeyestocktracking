"""Quick test script to verify all modules work."""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("Gooaye Stock Analyzer - Module Test")
print("=" * 50)

# Test 1: Database
print("\n[1] Testing database...")
from modules import database as db
db.init_db()
print("    OK - Database initialized")

# Test 2: YouTube Monitor
print("\n[2] Testing YouTube RSS monitor...")
from modules import youtube_monitor
vids = youtube_monitor.check_new_videos('UC_f21h7gV5bF022tM-t7_sw', max_initial=1)
print(f"    OK - Found {len(vids)} new video(s)")
for v in vids:
    print(f"      -> [{v['video_id']}] {v['title']}")

# Test 3: Config loading
print("\n[3] Testing config...")
import json
with open('config.json', 'r') as f:
    config = json.load(f)
print(f"    OK - Config loaded (channel: {config['youtube_channel_id']})")

# Test 4: Gemini API connectivity
print("\n[4] Testing Gemini API...")
try:
    from google import genai
    client = genai.Client(api_key=config['gemini_api_key'])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with just OK"
    )
    print(f"    OK - Gemini API response: {response.text.strip()}")
except Exception as e:
    print(f"    FAIL - Gemini API error: {e}")

# Test 5: yfinance
print("\n[5] Testing yfinance (TSMC 2330.TW)...")
try:
    import yfinance as yf
    ticker = yf.Ticker("2330.TW")
    info = ticker.info
    price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
    print(f"    OK - TSMC price: {price}")
except Exception as e:
    print(f"    FAIL - yfinance error: {e}")

# Test 6: Flask
print("\n[6] Testing Flask server import...")
try:
    from server import create_app
    app = create_app(config)
    print("    OK - Flask app created successfully")
except Exception as e:
    print(f"    FAIL - Flask error: {e}")

print("\n" + "=" * 50)
print("All tests completed!")
print("=" * 50)
