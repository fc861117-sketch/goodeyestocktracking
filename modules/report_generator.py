"""
Report Generator - orchestrates the analysis pipeline and saves results to DB.
"""

import logging
from modules import database as db
from modules import stock_data
from modules import ai_analyzer

logger = logging.getLogger(__name__)


def generate_report(video_info, transcript, api_key):
    """
    Run the full analysis pipeline for a video and save results to DB.
    
    Args:
        video_info: dict with video_id, title, url, published_at
        transcript: Full transcript text
        api_key: Gemini API key
    
    Returns:
        dict with the full report data
    """
    video_id = video_info['video_id']
    logger.info("=" * 60)
    logger.info("Generating report for: %s", video_info['title'])
    logger.info("=" * 60)

    # Step 1: AI Content Analysis
    logger.info("[Step 1/4] Analyzing content with AI...")
    analysis = ai_analyzer.analyze_content(transcript, api_key)

    # Step 2: Save video with summary
    summary_text = '\n'.join(analysis.get('summary', []))
    db.save_video(
        video_id=video_id,
        title=video_info['title'],
        url=video_info['url'],
        published_at=video_info.get('published_at', ''),
        transcript=transcript,
        summary=summary_text
    )

    # Step 3: For each identified stock, fetch data and generate advice
    recommendations = []
    stocks = analysis.get('stocks', [])

    if not stocks:
        logger.warning("No stocks identified in the content.")
    else:
        logger.info("[Step 2/4] Processing %d identified stocks...", len(stocks))

    for i, stock_info in enumerate(stocks, 1):
        symbol = stock_info.get('stock_symbol', '')
        name = stock_info.get('stock_name', '')
        market = stock_info.get('market', 'TW')

        if not symbol:
            logger.warning("Skipping stock with no symbol: %s", name)
            continue

        logger.info("[Step 3/4] Fetching data for %s (%s) [%d/%d]...",
                     name, symbol, i, len(stocks))

        # Fetch stock market data
        try:
            market_data = stock_data.get_stock_data(symbol, market)
        except Exception as e:
            logger.error("Failed to get data for %s: %s", symbol, e)
            market_data = {'current_price': None, 'error': str(e)}

        # Generate investment advice with AI
        logger.info("[Step 4/4] Generating investment advice for %s...", name)
        try:
            advice = ai_analyzer.generate_investment_advice(
                stock_info, market_data, api_key
            )
        except Exception as e:
            logger.error("Failed to generate advice for %s: %s", symbol, e)
            advice = {
                'target_price': None,
                'buy_price': None,
                'stop_loss': None,
                'short_term_advice': f'分析失敗: {str(e)}',
                'mid_term_advice': '',
                'long_term_advice': '',
                'analysis_detail': '',
            }

        # Save recommendation to DB
        current_price = market_data.get('current_price')
        rec_id = db.save_recommendation(
            video_id=video_id,
            stock_symbol=symbol,
            stock_name=name,
            market=market,
            sentiment=stock_info.get('sentiment', 'neutral'),
            gooaye_opinion=stock_info.get('gooaye_opinion', ''),
            price_at_mention=current_price,
            target_price=advice.get('target_price'),
            buy_price=advice.get('buy_price'),
            stop_loss=advice.get('stop_loss'),
            short_term_advice=advice.get('short_term_advice', ''),
            mid_term_advice=advice.get('mid_term_advice', ''),
            long_term_advice=advice.get('long_term_advice', ''),
            sector=stock_info.get('sector', ''),
            analysis_detail=advice.get('analysis_detail', ''),
        )

        # Save historical performance tracking entries (past 3 months)
        if current_price:
            try:
                hist_prices = stock_data.get_historical_prices(symbol, market, period="3mo")
                if hist_prices:
                    logger.info("Saving %d historical price points for %s...", len(hist_prices), symbol)
                    for hist_date, hist_price in hist_prices:
                        change_pct = round((hist_price - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
                        db.save_performance(
                            recommendation_id=rec_id,
                            tracked_date=hist_date,
                            current_price=hist_price,
                            price_change_pct=change_pct
                        )
                else:
                    # Fallback to just today's entry
                    from datetime import date
                    db.save_performance(
                        recommendation_id=rec_id,
                        tracked_date=date.today().isoformat(),
                        current_price=current_price,
                        price_change_pct=0.0
                    )
            except Exception as e:
                logger.error("Failed to save historical performance for %s: %s", symbol, e)
                from datetime import date
                db.save_performance(
                    recommendation_id=rec_id,
                    tracked_date=date.today().isoformat(),
                    current_price=current_price,
                    price_change_pct=0.0
                )

        recommendations.append({
            'id': rec_id,
            'stock_symbol': symbol,
            'stock_name': name,
            'market': market,
            'sentiment': stock_info.get('sentiment'),
            'current_price': current_price,
            'advice': advice,
        })

        logger.info("✓ Saved recommendation for %s (%s): price=%.2f, target=%s",
                     name, symbol, current_price or 0,
                     advice.get('target_price'))

    report = {
        'video': video_info,
        'analysis': analysis,
        'recommendations': recommendations,
    }

    logger.info("=" * 60)
    logger.info("Report complete: %d stocks analyzed", len(recommendations))
    logger.info("=" * 60)

    return report
