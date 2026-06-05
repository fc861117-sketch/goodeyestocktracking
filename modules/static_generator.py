import os
import json
import shutil
import logging
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
        'performance': {}
    }
    
    # Precompute details for each video
    for v in videos:
        v_recs = db.get_recommendations_for_video(v['video_id'])
        data['details'][v['video_id']] = {
            'video': dict(v),
            'recommendations': [dict(r) for r in v_recs]
        }
        
    # Precompute performance history for each recommendation
    for r in recs:
        history = db.get_performance_history(r['id'])
        data['performance'][r['id']] = {
            'recommendation': dict(r),
            'history': [dict(h) for h in history]
        }
        
    # Write data.json
    with open(os.path.join(docs_dir, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        
    # Copy and transform HTML
    with open(os.path.join(base_dir, 'templates', 'dashboard.html'), 'r', encoding='utf-8') as f:
        html = f.read()
        
    # Adjust paths for static deployment
    html = html.replace('href="/static/style.css"', 'href="./static/style.css"')
    html = html.replace('src="/static/app.js"', 'src="./static/app.js"')
    # Hide update prices button in static mode
    html = html.replace('id="btnUpdatePrices"', 'id="btnUpdatePrices" style="display:none"')
    
    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
        
    # Copy static assets
    shutil.copy2(os.path.join(base_dir, 'static', 'style.css'), os.path.join(docs_dir, 'static', 'style.css'))
    shutil.copy2(os.path.join(base_dir, 'static', 'app.js'), os.path.join(docs_dir, 'static', 'app.js'))
    
    logger.info("Static site generated successfully in docs/")
    return True
