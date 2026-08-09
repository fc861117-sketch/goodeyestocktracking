"""Refresh prices inside docs/data.json for the static GitHub Pages site."""

import json
import os
import sys
from datetime import datetime, date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from modules import stock_data
from modules.symbol_normalizer import infer_market, normalize_stock_record, normalize_symbol


DATA_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")


def _symbol_key(symbol):
    return str(symbol or "").strip().upper()


def _market_for_symbol(symbol, fallback="TW"):
    return infer_market(symbol, fallback)


def _normalize_recommendations(recommendations):
    normalized = 0
    skipped = []
    for rec in recommendations:
        before = (
            rec.get("stock_symbol"),
            rec.get("stock_name"),
            rec.get("market"),
        )
        normalize_stock_record(rec)
        after = (
            rec.get("stock_symbol"),
            rec.get("stock_name"),
            rec.get("market"),
        )
        if before != after:
            normalized += 1
        if rec.get("is_trackable") is False:
            skipped.append(rec.get("stock_symbol") or rec.get("stock_name"))
    return normalized, sorted(set(_symbol_key(s) for s in skipped if s))


def _change_pct(current_price, base_price):
    if current_price is None or not base_price or base_price <= 0:
        return 0.0
    return round((current_price - base_price) / base_price * 100, 2)


def _fetch_prices(recommendations):
    symbols = {}
    for rec in recommendations:
        if rec.get("is_trackable") is False:
            continue
        symbol = _symbol_key(rec.get("stock_symbol"))
        if not symbol:
            continue
        symbols.setdefault(symbol, rec.get("market") or _market_for_symbol(symbol))

    prices = {}
    failures = []
    for symbol, market in symbols.items():
        price = stock_data.get_current_price(symbol, market)
        if price is None:
            failures.append(symbol)
            continue
        prices[symbol] = float(price)
    return prices, failures


def _update_recommendation(rec, prices):
    symbol = _symbol_key(rec.get("stock_symbol"))
    if symbol not in prices:
        return False

    current_price = prices[symbol]
    rec["latest_price"] = current_price
    rec["latest_change_pct"] = _change_pct(current_price, rec.get("price_at_mention"))
    rec["last_tracked"] = date.today().isoformat()
    return True


def _update_summary(summary, recommendations):
    changes = [
        rec for rec in recommendations
        if rec.get("latest_change_pct") is not None and rec.get("latest_price") is not None
    ]
    if not changes:
        return

    avg = sum(float(rec.get("latest_change_pct") or 0) for rec in changes) / len(changes)
    best = max(changes, key=lambda rec: float(rec.get("latest_change_pct") or 0))
    worst = min(changes, key=lambda rec: float(rec.get("latest_change_pct") or 0))

    summary["avg_performance"] = round(avg, 2)
    summary["best_performance"] = round(float(best.get("latest_change_pct") or 0), 2)
    summary["worst_performance"] = round(float(worst.get("latest_change_pct") or 0), 2)
    summary["best_performer"] = {
        "name": best.get("stock_name") or best.get("stock_symbol"),
        "symbol": best.get("stock_symbol"),
        "change": round(float(best.get("latest_change_pct") or 0), 2),
    }
    summary["worst_performer"] = {
        "name": worst.get("stock_name") or worst.get("stock_symbol"),
        "symbol": worst.get("stock_symbol"),
        "change": round(float(worst.get("latest_change_pct") or 0), 2),
    }


def _update_performance(data, prices):
    today = date.today().isoformat()
    performance = data.get("performance") or {}

    migrated = {}
    migrated_from = []
    for symbol, perf in performance.items():
        rec = perf.get("recommendation") or {}
        normalized = normalize_symbol(symbol, rec.get("stock_name"), rec.get("market"))
        if normalized["trackable"]:
            key = _symbol_key(normalized["symbol"])
            if key != _symbol_key(symbol):
                rec["stock_symbol"] = normalized["symbol"]
                rec["stock_name"] = rec.get("stock_name") or normalized["name"]
                rec["market"] = normalized["market"]
                migrated[normalized["symbol"]] = perf
                migrated_from.append(symbol)
        else:
            rec["is_trackable"] = False
            rec["tracking_note"] = normalized["reason"]
            key = _symbol_key(symbol)

        if key not in prices:
            continue

        current_price = prices[key]
        rec["latest_price"] = current_price
        rec["latest_change_pct"] = _change_pct(current_price, rec.get("price_at_mention"))
        rec["last_tracked"] = today

        history = perf.setdefault("history", [])
        history = [h for h in history if h.get("tracked_date") != today]
        history.append({
            "tracked_date": today,
            "current_price": current_price,
            "price_change_pct": rec["latest_change_pct"],
        })
        perf["history"] = sorted(history, key=lambda h: h.get("tracked_date") or "")

    for symbol in migrated_from:
        performance.pop(symbol, None)
    for symbol, perf in migrated.items():
        performance[symbol] = perf


def _update_details(data, prices):
    for detail in (data.get("details") or {}).values():
        for rec in detail.get("recommendations") or []:
            normalize_stock_record(rec)
            _update_recommendation(rec, prices)


def _update_watchlist(data):
    watchlist_data = data.get("watchlist_data") or {}
    for symbol, item in watchlist_data.items():
        normalized = normalize_symbol(symbol, item.get("name"), item.get("market"))
        if not normalized["trackable"]:
            item["is_trackable"] = False
            item["tracking_note"] = normalized["reason"]
            continue

        item["symbol"] = normalized["symbol"]
        item["market"] = normalized["market"]
        market = normalized["market"]
        stock_info = stock_data.get_stock_data(normalized["symbol"], market)
        if not stock_info or stock_info.get("current_price") is None:
            continue

        current_price = float(stock_info["current_price"])
        item["latest_price"] = current_price
        item["previous_close"] = stock_info.get("previous_close")
        item["change_pct"] = stock_info.get("change_pct")
        item["last_tracked"] = date.today().isoformat()

        hist_prices = stock_data.get_historical_prices(normalized["symbol"], market, period="3mo")
        if hist_prices:
            item["history"] = [
                {"tracked_date": d, "current_price": p}
                for d, p in hist_prices
            ]


def refresh_static_prices():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    recommendations = data.get("recommendations") or []
    normalized_count, skipped_symbols = _normalize_recommendations(recommendations)
    prices, failures = _fetch_prices(recommendations)

    updated = 0
    for rec in recommendations:
        if _update_recommendation(rec, prices):
            updated += 1

    _update_details(data, prices)
    _update_performance(data, prices)
    _update_summary(data.setdefault("summary", {}), recommendations)
    _update_watchlist(data)

    data["price_updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    data["price_update_stats"] = {
        "updated_recommendations": updated,
        "updated_symbols": len(prices),
        "normalized_recommendations": normalized_count,
        "skipped_untrackable": skipped_symbols,
        "failed_symbols": failures,
    }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    return data["price_update_stats"]


if __name__ == "__main__":
    stats = refresh_static_prices()
    print(json.dumps(stats, ensure_ascii=False))
