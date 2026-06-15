import os
import json
import shutil
import logging
from datetime import datetime
from modules import database as db
from modules import stock_data

logger = logging.getLogger(__name__)

def generate_static_site():
    """Generates a static version of the dashboard in the docs/ directory."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, 'docs')
    
    # Create docs dir
    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(os.path.join(docs_dir, 'static'), exist_ok=True)
    
    # Gather all data needed by app.js
    summary_data = db.get_dashboard_summary()
    videos = db.get_all_videos()
    recs = db.get_all_recommendations()
    
    # Prepare data payload
    data = {
        'summary': summary_data,
        'reports': [dict(v) for v in videos],
        'recommendations': [dict(r) for r in recs],
        'details': {},
        'performance': {},
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    }
    
    # Precompute details for each video
    for v in videos:
        v_recs = db.get_recommendations_for_video(v['video_id'])
        data['details'][v['video_id']] = {
            'video': dict(v),
            'recommendations': [dict(r) for r in v_recs]
        }
        
    # Group recommendations by symbol to precompute performance
    symbol_recs = {}
    for r in recs:
        symbol_recs.setdefault(r['stock_symbol'], []).append(r)
        
    for symbol, s_recs in symbol_recs.items():
        s_recs.sort(key=lambda x: x['id'], reverse=True)
        latest_rec = s_recs[0]
        history = db.get_performance_history(latest_rec['id'])
        
        # Gather all mentions details
        all_mentions = []
        for r in s_recs:
            v_info = db.get_video(r['video_id'])
            all_mentions.append({
                'id': r['id'],
                'video_id': r['video_id'],
                'video_title': v_info['title'] if v_info else '',
                'video_date': v_info['published_at'] if v_info else '',
                'sentiment': r['sentiment'],
                'gooaye_opinion': r['gooaye_opinion'],
                'price_at_mention': r['price_at_mention'],
                'target_price': r['target_price'],
                'buy_price': r['buy_price'],
                'stop_loss': r['stop_loss'],
                'short_term_advice': r['short_term_advice'],
                'mid_term_advice': r['mid_term_advice'],
                'long_term_advice': r['long_term_advice'],
                'analysis_detail': r['analysis_detail']
            })
            
        data['performance'][symbol] = {
            'recommendation': dict(latest_rec),
            'all_mentions': all_mentions,
            'history': [dict(h) for h in history]
        }
        
    # Pre-fetch custom watchlist stocks data
    data['watchlist_data'] = {}
    watchlist_path = os.path.join(docs_dir, 'watchlist.json')
    if os.path.exists(watchlist_path):
        try:
            with open(watchlist_path, 'r', encoding='utf-8') as f:
                watchlist_symbols = json.load(f)
            
            existing_symbols = {r['stock_symbol'] for r in recs}
            for symbol in watchlist_symbols:
                if symbol not in existing_symbols:
                    clean_sym = symbol.strip()
                    is_tw = any(c.isdigit() for c in clean_sym) or clean_sym.endswith('.TW') or clean_sym.endswith('.TWO')
                    market = 'TW' if is_tw else 'US'
                    logger.info("Pre-fetching custom watchlist stock: %s (%s)", clean_sym, market)
                    try:
                        stock_info = stock_data.get_stock_data(clean_sym, market)
                        hist_prices = stock_data.get_historical_prices(clean_sym, market, period="3mo")
                        if stock_info and not stock_info.get('error'):
                            data['watchlist_data'][clean_sym] = {
                                'symbol': clean_sym,
                                'name': stock_info['fundamentals'].get('company_name', clean_sym),
                                'market': market,
                                'latest_price': stock_info['current_price'],
                                'previous_close': stock_info['previous_close'],
                                'change_pct': stock_info['change_pct'],
                                'history': [{'tracked_date': h[0], 'current_price': h[1]} for h in hist_prices]
                            }
                    except Exception as e:
                        logger.error("Failed to pre-fetch custom stock %s: %s", clean_sym, e)
        except Exception as e:
            logger.error("Error processing custom watchlist: %s", e)
        
    # Write data.json
    with open(os.path.join(docs_dir, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        
    # Copy and transform HTML
    with open(os.path.join(base_dir, 'templates', 'dashboard.html'), 'r', encoding='utf-8') as f:
        html = f.read()
        
    # Adjust paths for static deployment
    html = html.replace('href="/static/style.css"', 'href="./static/style.css"')
    html = html.replace('src="/static/app.js"', 'src="./static/app.js"')
    
    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
        
    # Copy static assets
    shutil.copy2(os.path.join(base_dir, 'static', 'style.css'), os.path.join(docs_dir, 'static', 'style.css'))
    shutil.copy2(os.path.join(base_dir, 'static', 'app.js'), os.path.join(docs_dir, 'static', 'app.js'))
    
    logger.info("Static site generated successfully in docs/")
    return True
