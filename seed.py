# seed.py
"""Seed the database with the current portfolio positions."""

from db import init_db, add_position, set_watchlist

PORTFOLIO = [
    {"ticker": "UNH",  "shares": 100, "avg_cost": 321.081, "tag": "div"},
    {"ticker": "SMR",  "shares": 300, "avg_cost": 21.00,   "tag": "sell"},
    {"ticker": "IREN", "shares": 700, "avg_cost": 55.114,  "tag": "none"},
    {"ticker": "CPRT", "shares": 100, "avg_cost": 48.413,  "tag": "none"},
    {"ticker": "CIFR", "shares": 225, "avg_cost": 17.467,  "tag": "none"},
    {"ticker": "BBAI", "shares": 400, "avg_cost": 9.08,    "tag": "sell"},
    {"ticker": "ASST", "shares": 30,  "avg_cost": 27.466,  "tag": "sell"},
    {"ticker": "AMZN", "shares": 45,  "avg_cost": 216.731, "tag": "hold"},
]

DEFAULT_WATCHLIST = [
    "MSFT", "AAPL", "GOOGL", "AMD", "NVDA", "META", "TSLA", "NFLX",
    "CRM", "ADBE", "ORCL", "AVGO", "COST", "WMT", "JNJ", "PG",
    "V", "MA", "JPM", "BAC", "DIS", "NKE", "SBUX", "HD", "LOW",
]

if __name__ == "__main__":
    init_db()
    for pos in PORTFOLIO:
        add_position("openscan.db", pos["ticker"], pos["shares"], pos["avg_cost"], pos["tag"])
        print(f"  Added {pos['ticker']}")
    set_watchlist("openscan.db", DEFAULT_WATCHLIST)
    print(f"  Watchlist: {len(DEFAULT_WATCHLIST)} tickers")
    print("Done.")
