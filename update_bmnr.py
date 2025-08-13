#!/usr/bin/env python3
"""
Generates bmnr.json with:
- Stock Price (last)
- Day's gain $ and Day's gain %
- Market Cap
- Market Cap Day's gain $ and Day's gain %
- Basic Shares Outstanding
- Assumed Diluted Shares Outstanding

Run whenever you want (hourly/daily) and publish bmnr.json (e.g., GitHub Pages).
"""

import json
from datetime import datetime, timezone
import math

import yfinance as yf


SYMBOL = "BMNR"
OUTFILE = "bmnr.json"

def to_float(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return float(x)
    except Exception:
        return None

def round_or_none(x, ndigits=2):
    return None if x is None else round(x, ndigits)

def main():
    t = yf.Ticker(SYMBOL)

    # --- Try fast_info first (lightweight, often has last/prev/market cap/shares) ---
    fast = {}
    try:
        fast = t.fast_info or {}
    except Exception:
        fast = {}

    last_price = to_float(fast.get("last_price"))
    prev_close = to_float(fast.get("previous_close"))
    market_cap = to_float(fast.get("market_cap"))
    basic_shares = to_float(fast.get("shares"))  # may be None

    # --- If last/prev missing, fall back to 2 days of history ---
    if last_price is None or prev_close is None:
        try:
            hist = t.history(period="2d", interval="1d", auto_adjust=False)
            if not hist.empty:
                # most recent row is last_price (close), previous row is prev_close
                closes = hist["Close"].dropna().tolist()
                if len(closes) >= 1 and last_price is None:
                    last_price = to_float(closes[-1])
                if len(closes) >= 2 and prev_close is None:
                    prev_close = to_float(closes[-2])
        except Exception:
            pass

    # --- If market cap missing, try to compute from shares*price, or pull from .info/.get_info ---
    if market_cap is None:
        # Try newer get_info (faster than .info; works on yfinance>=0.2.28)
        info = {}
        try:
            info = t.get_info() or {}
        except Exception:
            try:
                # Legacy .info as a fallback
                info = t.info or {}
            except Exception:
                info = {}

        if basic_shares is None:
            basic_shares = to_float(
                info.get("sharesOutstanding") or info.get("floatShares")
            )

        if market_cap is None:
            market_cap = to_float(
                info.get("marketCap") or (
                    (basic_shares * last_price) if (basic_shares and last_price) else None
                )
            )

    # --- Try to get diluted shares outstanding from income statement (annual) ---
    diluted_shares = None
    try:
        # yfinance get_income_stmt returns a DataFrame with line items as index.
        # Look for DilutedAverageShares or DilutedSharesOutstanding (names can vary).
        inc = t.get_income_stmt(freq="yearly")  # newer API
    except Exception:
        inc = None

    if inc is not None:
        candidates = [
            "DilutedAverageShares",
            "Diluted Average Shares",
            "DilutedSharesOutstanding",
            "Diluted Shares Outstanding",
            "WeightedAverageDilutedSharesOutstanding",
            "Weighted Average Diluted Shares Outstanding",
        ]
        for name in candidates:
            if name in inc.index and not inc.loc[name].dropna().empty:
                # pick the latest non-null value
                diluted_shares = to_float(inc.loc[name].dropna().iloc[0])
                break

    # If still missing, assume diluted == basic if basic exists
    if diluted_shares is None and basic_shares is not None:
        diluted_shares = basic_shares

    # --- Compute day gains on price ---
    day_gain = None
    day_gain_pct = None
    if last_price is not None and prev_close is not None and prev_close != 0:
        day_gain = last_price - prev_close
        day_gain_pct = (day_gain / prev_close) * 100.0

    # --- Compute day gain on market cap ---
    # Dollar change in market cap ≈ price change * basic shares
    mc_day_gain = None
    mc_day_gain_pct = None
    if basic_shares and day_gain is not None:
        mc_day_gain = day_gain * basic_shares
        # Percent change of market cap matches price percent change
        mc_day_gain_pct = day_gain_pct

    # --- Build result JSON ---
    result = {
        "symbol": SYMBOL,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),

        # Stock Price + Day Gain
        "price": round_or_none(last_price, 4),                 # keep a bit more precision
        "day_gain": round_or_none(day_gain, 4),
        "day_gain_pct": round_or_none(day_gain_pct, 4),        # % value, not string

        # Market Cap + Day Gain
        "market_cap": round_or_none(market_cap, 2),
        "market_cap_day_gain": round_or_none(mc_day_gain, 2),
        "market_cap_day_gain_pct": round_or_none(mc_day_gain_pct, 4),

        # Shares
        "basic_shares_outstanding": round_or_none(basic_shares, 0),
        "assumed_diluted_shares_outstanding": round_or_none(diluted_shares, 0),
    }

    # Write file
    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {OUTFILE}\n{json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
