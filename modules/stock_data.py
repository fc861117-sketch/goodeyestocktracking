"""
Stock Data Fetcher using yfinance and twstock.
Retrieves current prices, historical data, and fundamentals for TW and US stocks.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _get_tw_suffix(symbol):
    """Add .TW or .TWO suffix to Taiwan stock symbol for yfinance."""
    if '.' in symbol:
        return symbol
    # Most listed stocks use .TW, OTC stocks use .TWO
    # Try .TW first (more common)
    return f"{symbol}.TW"


def _clean_tw_symbol(symbol):
    """Return the numeric Taiwan stock code without exchange suffix."""
    return str(symbol).strip().upper().split('.')[0]


def _get_ticker_candidates(symbol, market="TW"):
    """Build yfinance ticker candidates, trying both listed and OTC Taiwan markets."""
    clean_symbol = str(symbol).strip().upper()
    if market != "TW":
        return [clean_symbol]
    if clean_symbol.endswith((".TW", ".TWO")):
        return [clean_symbol]
    clean_symbol = _clean_tw_symbol(clean_symbol)
    return [f"{clean_symbol}.TW", f"{clean_symbol}.TWO"]


def _extract_price_from_ticker(ticker):
    """Read current price from yfinance with fast_info and history fallbacks."""
    info = {}
    try:
        info = ticker.info or {}
    except Exception as e:
        logger.debug("yfinance info failed: %s", e)

    price = (
        info.get('currentPrice') or
        info.get('regularMarketPrice') or
        info.get('previousClose')
    )
    previous_close = info.get('previousClose')

    if not price:
        try:
            fast_info = ticker.fast_info or {}
            price = (
                fast_info.get('last_price') or
                fast_info.get('regular_market_price') or
                fast_info.get('previous_close')
            )
            previous_close = previous_close or fast_info.get('previous_close')
        except Exception as e:
            logger.debug("yfinance fast_info failed: %s", e)

    if not price:
        try:
            hist = ticker.history(period="5d")
            if not hist.empty:
                price = float(hist['Close'].dropna().iloc[-1])
                if len(hist['Close'].dropna()) >= 2:
                    previous_close = float(hist['Close'].dropna().iloc[-2])
        except Exception as e:
            logger.debug("yfinance price history fallback failed: %s", e)

    return price, previous_close, info


def get_stock_data(symbol, market="TW"):
    """
    Get comprehensive stock data for a given symbol.
    
    Args:
        symbol: Stock symbol (e.g., '2330' for TW, 'AAPL' for US)
        market: 'TW' or 'US'
    
    Returns:
        dict with current_price, history, moving_averages, fundamentals, volume_trend
    """
    import yfinance as yf

    ticker_candidates = _get_ticker_candidates(symbol, market)
    ticker_symbol = ticker_candidates[0]

    logger.info("Fetching stock data for %s (ticker: %s)", symbol, ticker_symbol)

    result = {
        'symbol': symbol,
        'ticker': ticker_symbol,
        'market': market,
        'current_price': None,
        'previous_close': None,
        'change_pct': None,
        'currency': 'TWD' if market == 'TW' else 'USD',
        'history_3m': None,
        'history_6m': None,
        'history_1y': None,
        'moving_averages': {},
        'fundamentals': {},
        'volume_avg': None,
        'fifty_two_week_high': None,
        'fifty_two_week_low': None,
        'error': None,
    }

    try:
        info = {}
        for candidate in ticker_candidates:
            ticker_symbol = candidate
            ticker = yf.Ticker(candidate)
            price, previous_close, info = _extract_price_from_ticker(ticker)
            if price:
                result['ticker'] = candidate
                result['current_price'] = float(price)
                result['previous_close'] = float(previous_close) if previous_close else None
                break

        if not info:
            ticker = yf.Ticker(result['ticker'])
            try:
                info = ticker.info or {}
            except Exception:
                info = {}

        if result['current_price'] and result['previous_close']:
            result['change_pct'] = round(
                (result['current_price'] - result['previous_close'])
                / result['previous_close'] * 100, 2
            )

        # 52-week range
        result['fifty_two_week_high'] = info.get('fiftyTwoWeekHigh')
        result['fifty_two_week_low'] = info.get('fiftyTwoWeekLow')

        # Fundamentals
        result['fundamentals'] = {
            'pe_ratio': info.get('trailingPE') or info.get('forwardPE'),
            'pb_ratio': info.get('priceToBook'),
            'dividend_yield': round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else None,
            'market_cap': info.get('marketCap'),
            'eps': info.get('trailingEps'),
            'revenue_growth': info.get('revenueGrowth'),
            'profit_margins': info.get('profitMargins'),
            'sector': info.get('sector', ''),
            'industry': info.get('industry', ''),
            'company_name': info.get('longName') or info.get('shortName', symbol),
        }

        # Historical data
        try:
            hist_1y = yf.Ticker(result['ticker']).history(period="1y")
            if not hist_1y.empty:
                result['history_1y'] = {
                    'start_price': round(float(hist_1y['Close'].iloc[0]), 2),
                    'end_price': round(float(hist_1y['Close'].iloc[-1]), 2),
                    'high': round(float(hist_1y['High'].max()), 2),
                    'low': round(float(hist_1y['Low'].min()), 2),
                    'change_pct': round(
                        (float(hist_1y['Close'].iloc[-1]) - float(hist_1y['Close'].iloc[0]))
                        / float(hist_1y['Close'].iloc[0]) * 100, 2
                    ),
                }

                # Moving averages from recent data
                closes = hist_1y['Close']
                if len(closes) >= 5:
                    result['moving_averages']['MA5'] = round(float(closes.tail(5).mean()), 2)
                if len(closes) >= 10:
                    result['moving_averages']['MA10'] = round(float(closes.tail(10).mean()), 2)
                if len(closes) >= 20:
                    result['moving_averages']['MA20'] = round(float(closes.tail(20).mean()), 2)
                if len(closes) >= 60:
                    result['moving_averages']['MA60'] = round(float(closes.tail(60).mean()), 2)
                if len(closes) >= 120:
                    result['moving_averages']['MA120'] = round(float(closes.tail(120).mean()), 2)

                # Volume average
                if 'Volume' in hist_1y.columns:
                    result['volume_avg'] = int(hist_1y['Volume'].tail(20).mean())

                # 3-month and 6-month subsets
                three_months_ago = datetime.now() - timedelta(days=90)
                six_months_ago = datetime.now() - timedelta(days=180)

                hist_3m = hist_1y[hist_1y.index >= three_months_ago.strftime('%Y-%m-%d')]
                if not hist_3m.empty:
                    result['history_3m'] = {
                        'start_price': round(float(hist_3m['Close'].iloc[0]), 2),
                        'end_price': round(float(hist_3m['Close'].iloc[-1]), 2),
                        'change_pct': round(
                            (float(hist_3m['Close'].iloc[-1]) - float(hist_3m['Close'].iloc[0]))
                            / float(hist_3m['Close'].iloc[0]) * 100, 2
                        ),
                    }

                hist_6m = hist_1y[hist_1y.index >= six_months_ago.strftime('%Y-%m-%d')]
                if not hist_6m.empty:
                    result['history_6m'] = {
                        'start_price': round(float(hist_6m['Close'].iloc[0]), 2),
                        'end_price': round(float(hist_6m['Close'].iloc[-1]), 2),
                        'change_pct': round(
                            (float(hist_6m['Close'].iloc[-1]) - float(hist_6m['Close'].iloc[0]))
                            / float(hist_6m['Close'].iloc[0]) * 100, 2
                        ),
                    }

        except Exception as e:
            logger.warning("Failed to fetch history for %s: %s", ticker_symbol, e)

        # If yfinance didn't return a price, try twstock for TW stocks
        if result['current_price'] is None and market == "TW":
            result['current_price'] = _get_twstock_price(symbol)

        logger.info("Stock data for %s: price=%s, PE=%s",
                     symbol, result['current_price'],
                     result['fundamentals'].get('pe_ratio'))

    except Exception as e:
        logger.error("Failed to fetch stock data for %s: %s", ticker_symbol, e)
        result['error'] = str(e)

        # Fallback to twstock for TW market
        if market == "TW":
            price = _get_twstock_price(symbol)
            if price:
                result['current_price'] = price

    return result


def _get_twstock_price(symbol):
    """Fallback: get current price from twstock for Taiwan stocks."""
    try:
        import twstock
        # Remove any suffix
        clean_symbol = _clean_tw_symbol(symbol)
        stock = twstock.Stock(clean_symbol)
        if stock.price and len(stock.price) > 0:
            return float(stock.price[-1])
    except Exception as e:
        logger.debug("twstock fallback failed for %s: %s", symbol, e)
    return None


def get_current_price(symbol, market="TW"):
    """
    Get just the current price for a stock (used for performance tracking).
    
    Returns:
        float or None
    """
    import yfinance as yf

    try:
        for ticker_symbol in _get_ticker_candidates(symbol, market):
            ticker = yf.Ticker(ticker_symbol)
            price, _, _ = _extract_price_from_ticker(ticker)
            if price:
                return float(price)

        # Fallback for TW stocks
        if market == "TW":
            return _get_twstock_price(symbol)

    except Exception as e:
        logger.warning("Failed to get price for %s: %s", symbol, e)

        # Fallback for TW stocks
        if market == "TW":
            return _get_twstock_price(symbol)

    return None


def get_historical_prices(symbol, market="TW", period="3mo"):
    """
    Get historical closing prices for a stock as a list of (date_str, price) tuples.
    """
    import yfinance as yf
    
    if market == "TW":
        ticker_symbols = []
        if '.' in symbol:
            ticker_symbols.append(symbol)
        else:
            ticker_symbols.append(f"{symbol}.TW")
            ticker_symbols.append(f"{symbol}.TWO")
    else:
        ticker_symbols = [symbol]
        
    for ticker_symbol in ticker_symbols:
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period=period)
            if not hist.empty:
                prices = []
                for index, row in hist.iterrows():
                    date_str = index.strftime('%Y-%m-%d')
                    price = round(float(row['Close']), 2)
                    prices.append((date_str, price))
                return prices
        except Exception as e:
            logger.warning("Failed to get historical prices for %s: %s", ticker_symbol, e)
            
    return []
