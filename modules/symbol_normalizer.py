"""Normalize extracted stock identifiers before price lookup."""

import re


UNTRACKABLE_SYMBOLS = {
    "ANTHROPIC",
    "CRADLE",
    "CPU類股",
    "EMPANON",
    "FLYBE",
    "N/A",
    "PERP",
    "SPACEX",
    "STRATLABS",
    "STRELABS",
    "TXF",
    "台中亞都麗緻",
    "日股斜坡減速器",
}


ALIASES = {
    "CLOUDFLARE": ("NET", "Cloudflare", "US"),
    "GOOGLE": ("GOOGL", "Alphabet", "US"),
    "NVIDIA": ("NVDA", "NVIDIA", "US"),
    "PALANTIR": ("PLTR", "Palantir", "US"),
    "SK HYNIX": ("000660.KS", "SK Hynix", "KR"),
    "TAKE-TWO INTERACTIVE": ("TTWO", "Take-Two Interactive", "US"),
    "TPE: NVDA": ("NVDA", "NVIDIA", "US"),
    "ZOOM TECHNOLOGIES": ("ZM", "Zoom Video", "US"),
    "花網": ("NET", "Cloudflare", "US"),
    "日月光投控": ("3711", "日月光投控", "TW"),
    "華潤微": ("688396.SS", "華潤微", "CN"),
    "斯蘭微": ("600460.SS", "斯蘭微", "CN"),
    "江海股份": ("002484.SZ", "江海股份", "CN"),
}


SYMBOL_ALIASES = {
    "2311": ("3711", "日月光投控", "TW"),
    "4180": ("4180.T", "Appier Group", "JP"),
    "6996 JP": ("6996.T", "Nichicon", "JP"),
    "6996.JP": ("6996.T", "Nichicon", "JP"),
    "6997.JP": ("6997.T", "Nippon Chemi-Con", "JP"),
}


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


def normalize_symbol(symbol, name="", market=""):
    """Return normalized symbol metadata for price lookup and display."""
    raw_symbol = str(symbol or "").strip()
    raw_name = str(name or "").strip()
    key = symbol_key(raw_symbol)
    name_key = symbol_key(raw_name)

    if key in UNTRACKABLE_SYMBOLS or name_key in UNTRACKABLE_SYMBOLS:
        return {
            "symbol": raw_symbol,
            "name": raw_name or raw_symbol,
            "market": market or infer_market(raw_symbol),
            "trackable": False,
            "reason": "not_publicly_traded",
        }

    if key in SYMBOL_ALIASES:
        normalized_symbol, normalized_name, normalized_market = SYMBOL_ALIASES[key]
        return {
            "symbol": normalized_symbol,
            "name": raw_name or normalized_name,
            "market": normalized_market,
            "trackable": True,
            "reason": "symbol_alias",
        }

    if key in ALIASES:
        normalized_symbol, normalized_name, normalized_market = ALIASES[key]
        return {
            "symbol": normalized_symbol,
            "name": raw_name or normalized_name,
            "market": normalized_market,
            "trackable": True,
            "reason": "name_alias",
        }

    if name_key in ALIASES:
        normalized_symbol, normalized_name, normalized_market = ALIASES[name_key]
        return {
            "symbol": normalized_symbol,
            "name": raw_name or normalized_name,
            "market": normalized_market,
            "trackable": True,
            "reason": "name_alias",
        }

    jp_match = re.fullmatch(r"(\d{4})\s*JP", key)
    if jp_match:
        return {
            "symbol": f"{jp_match.group(1)}.T",
            "name": raw_name or raw_symbol,
            "market": "JP",
            "trackable": True,
            "reason": "jp_suffix",
        }

    return {
        "symbol": raw_symbol,
        "name": raw_name or raw_symbol,
        "market": market or infer_market(raw_symbol),
        "trackable": True,
        "reason": "unchanged",
    }


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
    return record
