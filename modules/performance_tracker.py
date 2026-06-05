"""
Performance Tracker - updates current prices for all tracked recommendations.
Calculates price changes since the recommendation date.
"""

import logging
from datetime import date
from modules import database as db
from modules import stock_data

logger = logging.getLogger(__name__)


def update_all_prices():
    """
    Update current prices for all recommendations that have a price_at_mention.
    Saves new performance tracking entries for today.
    
    Returns:
        dict with update statistics
    """
    recs = db.get_all_trackable_recommendations()

    if not recs:
        logger.info("No trackable recommendations found.")
        return {'updated': 0, 'failed': 0, 'total': 0}

    today = date.today().isoformat()
    updated = 0
    failed = 0

    logger.info("Updating prices for %d recommendations...", len(recs))

    for rec in recs:
        symbol = rec['stock_symbol']
        market = rec['market'] or 'TW'
        price_at_mention = rec['price_at_mention']

        try:
            current_price = stock_data.get_current_price(symbol, market)

            if current_price is None:
                logger.warning("Could not get price for %s", symbol)
                failed += 1
                continue

            # Calculate change percentage
            if price_at_mention and price_at_mention > 0:
                change_pct = round(
                    (current_price - price_at_mention) / price_at_mention * 100, 2
                )
            else:
                change_pct = 0.0

            db.save_performance(
                recommendation_id=rec['id'],
                tracked_date=today,
                current_price=current_price,
                price_change_pct=change_pct
            )

            updated += 1
            logger.info("Updated %s: %.2f → %.2f (%+.2f%%)",
                         symbol, price_at_mention, current_price, change_pct)

        except Exception as e:
            logger.error("Failed to update %s: %s", symbol, e)
            failed += 1

    stats = {
        'updated': updated,
        'failed': failed,
        'total': len(recs),
        'date': today,
    }

    logger.info("Price update complete: %d updated, %d failed out of %d total",
                 updated, failed, len(recs))

    return stats
