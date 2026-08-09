"""Rebuild the local SQLite database from docs/data.json when needed."""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from modules import database as db


DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")


def bootstrap_db_from_static_data(force=False):
    """Create data/gooaye.db from static GitHub Pages data if DB is missing."""
    if os.path.exists(db.DB_PATH) and not force:
        return False
    if not os.path.exists(DATA_JSON_PATH):
        return False

    db.init_db()

    with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    rec_id_map = {}
    details = data.get("details") or {}

    for video_id, detail in details.items():
        video = detail.get("video") or {}
        db.save_video(
            video_id=video.get("video_id") or video_id,
            title=video.get("title") or "",
            url=video.get("url") or "",
            published_at=video.get("published_at") or "",
            transcript=video.get("transcript") or "",
            summary=video.get("summary") or "",
        )

        for rec in detail.get("recommendations") or []:
            new_id = db.save_recommendation(
                video_id=video.get("video_id") or video_id,
                stock_symbol=rec.get("stock_symbol") or "",
                stock_name=rec.get("stock_name") or "",
                market=rec.get("market") or "TW",
                sentiment=rec.get("sentiment") or "neutral",
                gooaye_opinion=rec.get("gooaye_opinion") or "",
                price_at_mention=rec.get("price_at_mention"),
                target_price=rec.get("target_price"),
                buy_price=rec.get("buy_price"),
                stop_loss=rec.get("stop_loss"),
                short_term_advice=rec.get("short_term_advice") or "",
                mid_term_advice=rec.get("mid_term_advice") or "",
                long_term_advice=rec.get("long_term_advice") or "",
                sector=rec.get("sector") or "",
                analysis_detail=rec.get("analysis_detail") or "",
            )
            if rec.get("id") is not None:
                rec_id_map[str(rec["id"])] = new_id

    for perf in (data.get("performance") or {}).values():
        old_id = ((perf.get("recommendation") or {}).get("id"))
        new_id = rec_id_map.get(str(old_id))
        if not new_id:
            continue
        for row in perf.get("history") or []:
            tracked_date = row.get("tracked_date")
            current_price = row.get("current_price")
            if not tracked_date or current_price is None:
                continue
            db.save_performance(
                recommendation_id=new_id,
                tracked_date=tracked_date,
                current_price=current_price,
                price_change_pct=row.get("price_change_pct") or 0.0,
            )

    return True


if __name__ == "__main__":
    created = bootstrap_db_from_static_data()
    print("created" if created else "skipped")
