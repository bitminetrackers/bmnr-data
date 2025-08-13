import yfinance as yf
import json
from datetime import datetime, timezone
import subprocess

# ---------- Configuration ----------
symbol = "BMNR"
repo_branch = "main"
dilution_factor = 1.2  # estimate diluted shares as 120% of basic shares

# ---------- Fetch Data ----------
ticker = yf.Ticker(symbol)
hist = ticker.history(period="1d")

if hist.empty:
    print("No data found for", symbol)
    exit()

price = hist["Close"].iloc[-1]
open_price = hist["Open"].iloc[-1]
day_gain = price - open_price
day_gain_pct = (day_gain / open_price) * 100

# Safe access to fast_info
fast = ticker.fast_info or {}
market_cap = fast.get("market_cap")
basic_shares_outstanding = fast.get("shares")  # may be None

# Fallback: compute basic shares if missing
if basic_shares_outstanding is None and market_cap and price:
    basic_shares_outstanding = market_cap / price

# Estimate diluted shares
assumed_diluted_shares_outstanding = round(
    basic_shares_outstanding * dilution_factor if basic_shares_outstanding else None
)

# ---------- Write JSON ----------
output = {
    "symbol": symbol,
    "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    "price": round(price, 2),
    "day_gain": round(day_gain, 2),
    "day_gain_pct": round(day_gain_pct, 4),
    "market_cap": market_cap,
    "market_cap_day_gain": round(market_cap * (day_gain_pct / 100), 1) if market_cap else None,
    "market_cap_day_gain_pct": round(day_gain_pct, 4),
    "basic_shares_outstanding": basic_shares_outstanding,
    "assumed_diluted_shares_outstanding": assumed_diluted_shares_outstanding
}

with open("bmnr.json", "w") as f:
    json.dump(output, f, indent=2)

print("Updated bmnr.json")

# ---------- Git Push (overwrite commit) ----------
subprocess.run(["git", "add", "bmnr.json"])
subprocess.run(["git", "commit", "--amend", "--no-edit"])
subprocess.run(["git", "push", "--force", "origin", repo_branch])
