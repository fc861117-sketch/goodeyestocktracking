"""Normalize extracted stock identifiers before price lookup.

Project-specific aliases live in config/symbol_aliases.json so future fixes do
not require code changes.
"""

import json
import os
import re


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIAS_PATH = os.path.join(PROJECT_ROOT, "config", "symbol_aliases.json")


DEFAULT_UNTRACKABLE = {
    "ANTHROPIC",
    "CPU",
    "CPU STOCKS",
    "CRADLE",
    "EMPANON",
    "FLYBE",
    "N/A",
    "PERP",
    "SPACEX",
    "STRATLABS",
    "STRELABS",
    "TXF",
}


DEFAULT_ALIASES = {
    "CLOUDFLARE": {"symbol": "NET", "name": "Cloudflare", "market": "US"},
    "GOOGLE": {"symbol": "GOOGL", "name": "Alphabet", "market": "US"},
    "NVIDIA": {"symbol": "NVDA", "name": "NVIDIA", "market": "US"},
    "PALANTIR": {"symbol": "PLTR", "name": "Palantir", "market": "US"},
    "SK HYNIX": {"symbol": "000660.KS", "name": "SK Hynix", "market": "KR"},
    "TAKE-TWO INTERACTIVE": {"symbol": "TTWO", "name": "Take-Two Interactive", "market": "US"},
    "TPE: NVDA": {"symbol": "NVDA", "name": "NVIDIA", "market": "US"},
    "ZOOM TECHNOLOGIES": {"symbol": "ZM", "name": "Zoom Video", "market": "US"},
}


DEFAULT_SYMBOL_ALIASES = {
    "2311": {"symbol": "3711", "name": "ASE Technology", "market": "TW"},
    "4180": {"symbol": "4180.T", "name": "Appier Group", "market": "JP"},
    "6996 JP": {"symbol": "6996.T", "name": "Nichicon", "market": "JP"},
    "6996.JP": {"symbol": "6996.T", "name": "Nichicon", "market": "JP"},
    "6997.JP": {"symbol": "6997.T", "name": "Nippon Chemi-Con", "market": "JP"},
}


def _load_external_config():
    if not os.path.exists(ALIAS_PATH):
        return {}, {}, set()
    with open(ALIAS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    aliases = data.get("aliases") or {}
    symbol_aliases = data.get("symbol_aliases") or {}
    untrackable = set(data.get("untrackable_symbols") or [])
    return aliases, symbol_aliases, untrackable


def _entry_to_tuple(entry):
    if isinstance(entry, dict):
        return entry.get("symbol"), entry.get("name"), entry.get("market")
    return entry


def _merged_config():
    aliases = dict(DEFAULT_ALIASES)
    symbol_aliases = dict(DEFAULT_SYMBOL_ALIASES)
    untrackable = set(DEFAULT_UNTRACKABLE)

    external_aliases, external_symbol_aliases, external_untrackable = _load_external_config()
    aliases.update({symbol_key(k): v for k, v in external_aliases.items()})
    symbol_aliases.update({symbol_key(k): v for k, v in external_symbol_aliases.items()})
    untrackable.update(symbol_key(v) for v in external_untrackable)
    return aliases, symbol_aliases, untrackable


def symbol_key(value):
    return str(value or "").strip().upper()


def infer_market(symbol, fallback="TW"):
    clean = symbol_key(symbol)
    if clean.endswith((".TW", ".TWO")):
        return "TW"
    if clean.endswith(".T"):
        return "JP"
    if clean.endswith(".KS") or clean.endswith(".KQ"):
        return "KR"
    if clean.endswith((".SS", ".SZ")):
        return "CN"
    if re.fullmatch(r"\d{4,6}", clean):
        return "TW"
    return fallback or "US"


def _normalized_response(symbol, name, market, trackable=True, reason="unchanged"):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "market": market or infer_market(symbol),
        "trackable": trackable,
        "reason": reason,
    }


def normalize_symbol(symbol, name="", market=""):
    """Return normalized symbol metadata for price lookup and display."""
    raw_symbol = str(symbol or "").strip()
    raw_name = str(name or "").strip()
    key = symbol_key(raw_symbol)
    name_key = symbol_key(raw_name)
    aliases, symbol_aliases, untrackable = _merged_config()

    if key in untrackable or name_key in untrackable:
        return _normalized_response(
            raw_symbol,
            raw_name or raw_symbol,
            market or infer_market(raw_symbol),
            trackable=False,
            reason="not_publicly_traded",
        )

    if key in symbol_aliases:
        normalized_symbol, normalized_name, normalized_market = _entry_to_tuple(symbol_aliases[key])
        return _normalized_response(
            normalized_symbol,
            raw_name or normalized_name,
            normalized_market,
            reason="symbol_alias",
        )

    for alias_key in (key, name_key):
        if alias_key in aliases:
            normalized_symbol, normalized_name, normalized_market = _entry_to_tuple(aliases[alias_key])
            return _normalized_response(
                normalized_symbol,
                raw_name or normalized_name,
                normalized_market,
                reason="name_alias",
            )

    jp_match = re.fullmatch(r"(\d{4})\s*JP", key)
    if jp_match:
        return _normalized_response(
            f"{jp_match.group(1)}.T",
            raw_name or raw_symbol,
            "JP",
            reason="jp_suffix",
        )

    return _normalized_response(
        raw_symbol,
        raw_name or raw_symbol,
        market or infer_market(raw_symbol),
    )


def normalize_stock_record(record):
    normalized = normalize_symbol(
        record.get("stock_symbol"),
        record.get("stock_name"),
        record.get("market"),
    )
    record["stock_symbol"] = normalized["symbol"]
    record["stock_name"] = normalized["name"]
    record["market"] = normalized["market"]
    if not normalized["trackable"]:
        record["is_trackable"] = False
        record["tracking_note"] = normalized["reason"]
    else:
        record.pop("is_trackable", None)
        record.pop("tracking_note", None)
    return record
