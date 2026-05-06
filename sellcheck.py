#!/usr/bin/env python3
"""Sell signal checker — scans current positions for reversal signals.

Loads positions from latest_scan.json, runs 10 sell signals on each via OpenD.
Stocks with 6+ signals are added to the 'claude.sell' moomoo watchlist.
"""

import json
import sys

import pandas as pd
from moomoo import OpenQuoteContext, ModifyUserSecurityOp, RET_OK

from scanner import _fetch_history, _moomoo_code, OPEND_HOST, OPEND_PORT
from signals import check_sell_signals

THRESHOLD = 6
WATCHLIST_GROUP = "claude.sell"
WATCH_GROUP = "claude.watch"


def main():
    # Load positions
    try:
        with open("latest_scan.json") as f:
            positions = json.load(f)
    except FileNotFoundError:
        print("ERROR: latest_scan.json not found. Run a scan first.")
        sys.exit(1)

    if not positions:
        print("No positions found in latest_scan.json.")
        sys.exit(0)

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    triggered = []
    fading_vol = []
    results = []

    for pos in positions:
        ticker = pos["ticker"]
        avg_cost = pos["avg_cost"]
        shares = pos["shares"]

        hist = _fetch_history(ctx, ticker)
        if hist.empty or len(hist) < 50:
            results.append({"ticker": ticker, "error": "Insufficient data"})
            continue

        current = hist["Close"].iloc[-1]
        pnl_pct = ((current - avg_cost) / avg_cost) * 100

        sigs = check_sell_signals(hist)
        fired_count = sum(1 for _, fired, _ in sigs if fired)
        fired_signals = [(name, detail) for name, fired, detail in sigs if fired]

        # Volume trend detection
        vol_50avg = hist["Volume"].rolling(50).mean().iloc[-1]
        rvol_3d = hist["Volume"].tail(3).mean() / vol_50avg if vol_50avg > 0 else 0
        rvol_10d = hist["Volume"].tail(10).mean() / vol_50avg if vol_50avg > 0 else 0
        price_5d_chg = ((current - hist["Close"].iloc[-6]) / hist["Close"].iloc[-6]) * 100 if len(hist) > 6 else 0
        is_fading = price_5d_chg > 3 and rvol_3d < 0.7 and rvol_10d > rvol_3d

        if is_fading:
            fading_vol.append(ticker)

        results.append({
            "ticker": ticker,
            "current": current,
            "avg_cost": avg_cost,
            "shares": shares,
            "pnl_pct": pnl_pct,
            "fired_count": fired_count,
            "fired_signals": fired_signals,
            "triggered": fired_count >= THRESHOLD,
            "vol_fading": is_fading,
            "rvol_3d": rvol_3d,
            "price_5d_chg": price_5d_chg,
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
            print(f"  SELL SIGNAL: {ticker} ({count}/10) — ${r['current']:.2f} ({r['pnl_pct']:+.1f}%)")
            for name, detail in r["fired_signals"]:
                print(f"    * {name}: {detail}")
            print()
        else:
            fading_tag = " ⚠ VOL FADING" if r.get("vol_fading") else ""
            print(f"  {ticker}: {count}/10 — OK{fading_tag}" + (f" (+{r['price_5d_chg']:.0f}% on {r['rvol_3d']:.2f}x vol)" if r.get("vol_fading") else ""))

    # Auto-add fading volume stocks to claude.watch
    if fading_vol:
        print()
        codes = [_moomoo_code(t) for t in fading_vol]
        ret, data = ctx.modify_user_security(WATCH_GROUP, ModifyUserSecurityOp.ADD, codes)
        if ret == RET_OK:
            print(f"  ⚠ Added to '{WATCH_GROUP}' (fading volume): {', '.join(fading_vol)}")
        else:
            print(f"  Warning: Could not add to '{WATCH_GROUP}': {data}")

    # Add triggered stocks to claude.sell watchlist
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
        print("  No sell signals triggered.")

    ctx.close()


if __name__ == "__main__":
    main()
