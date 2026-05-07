#!/usr/bin/env python3
"""Buy signal checker — scans current positions for accumulation signals.

Loads positions from latest_scan.json (or accepts ticker args).
Stocks with 6+ signals are added to the 'claude.buy' moomoo watchlist.
"""

import json
import sys

from moomoo import OpenQuoteContext, ModifyUserSecurityOp, RET_OK

from scanner import _fetch_history, _moomoo_code, OPEND_HOST, OPEND_PORT
from signals import check_buy_signals

THRESHOLD = 6
WATCHLIST_GROUP = "claude.buy"


def main():
    args = sys.argv[1:]
    if args:
        tickers = [t.upper().strip(",") for t in args]
    else:
        try:
            with open("latest_scan.json") as f:
                positions = json.load(f)
            tickers = [p["ticker"] for p in positions if "ticker" in p]
        except FileNotFoundError:
            print("ERROR: latest_scan.json not found. Run a scan first.")
            sys.exit(1)

    if not tickers:
        print("No tickers found.")
        sys.exit(0)

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    results = []

    for ticker in tickers:
        hist = _fetch_history(ctx, ticker)
        if hist.empty or len(hist) < 50:
            results.append({"ticker": ticker, "error": "Insufficient data"})
            continue

        current = hist["Close"].iloc[-1]
        ma50 = hist["Close"].rolling(50).mean().iloc[-1]
        ma200 = hist["Close"].rolling(200).mean().iloc[-1] if len(hist) >= 200 else None
        high_52w = hist["High"].max()
        pct_from_high = ((current - high_52w) / high_52w) * 100

        sigs = check_buy_signals(hist)
        fired_count = sum(1 for _, fired, _ in sigs if fired)
        fired_signals = [(name, detail) for name, fired, detail in sigs if fired]

        results.append({
            "ticker": ticker,
            "current": current,
            "ma50": ma50,
            "ma200": ma200,
            "pct_from_high": pct_from_high,
            "fired_count": fired_count,
            "fired_signals": fired_signals,
            "triggered": fired_count >= THRESHOLD,
        })

    # Output results
    print()
    triggered_tickers = []

    for r in sorted(results, key=lambda x: x.get("fired_count", 0), reverse=True):
        if "error" in r:
            print(f"  {r['ticker']}: {r['error']}")
            continue

        ticker = r["ticker"]
        count = r["fired_count"]

        if r["triggered"]:
            triggered_tickers.append(ticker)
            print(f"  BUY SIGNAL: {ticker} ({count}/10) — ${r['current']:.2f} ({r['pct_from_high']:+.1f}% from 52w high)")
            for name, detail in r["fired_signals"]:
                print(f"    * {name}: {detail}")
            print()
        else:
            print(f"  {ticker}: {count}/10 — ${r['current']:.2f} ({r['pct_from_high']:+.1f}% from 52w high)")
            for name, detail in r["fired_signals"]:
                print(f"    * {name}: {detail}")

    # Add triggered stocks to claude.buy watchlist
    if triggered_tickers:
        print()
        codes = [_moomoo_code(t) for t in triggered_tickers]
        ret, data = ctx.modify_user_security(WATCHLIST_GROUP, ModifyUserSecurityOp.ADD, codes)
        if ret == RET_OK:
            print(f"  Added to '{WATCHLIST_GROUP}' watchlist: {', '.join(triggered_tickers)}")
        else:
            print(f"  Warning: Could not add to '{WATCHLIST_GROUP}' watchlist: {data}")
    else:
        print()
        print("  No buy signals triggered.")

    ctx.close()


if __name__ == "__main__":
    main()
