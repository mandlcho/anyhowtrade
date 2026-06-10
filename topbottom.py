#!/usr/bin/env python3
"""AskLivermore-style top/bottom scanner using Moomoo OpenD.

Scans watchlists and/or holdings, then separates results into:
- reversal-up candidates
- pullback-buy candidates
- top / trim / avoid candidates

Read-only: no orders and no watchlist edits.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from moomoo import OpenQuoteContext, RET_OK

from db import get_positions, get_watchlist, init_db
from indicators import compute_bollinger, compute_macd, compute_rsi
from scanner import OPEND_HOST, OPEND_PORT, _fetch_history, _moomoo_code
from signals import check_buy_signals, check_sell_signals

DEFAULT_GROUPS = ("LEOPOLD", "TRUMP", "claude.watch")
DEFAULT_DB = "openscan.db"
MIN_ROWS = 220


@dataclass
class Candidate:
    ticker: str
    bucket: str
    label: str
    score: int
    risk: str
    action: str
    price: float
    signals: list[str]
    invalidation: float | None
    support: float | None
    resistance: float | None
    trade_or_watchlist: str
    pnl_pct: float | None = None
    shares: float | None = None
    avg_cost: float | None = None


def _clean_ticker(code: str) -> str:
    return code.split(".")[-1].upper() if "." in code else code.upper()


def _safe_float(value) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _pct(a: float, b: float) -> float:
    return ((a - b) / b) * 100 if b else 0.0


def _stoch_rsi(rsi: pd.Series, period: int = 14) -> pd.Series:
    low = rsi.rolling(period).min()
    high = rsi.rolling(period).max()
    return ((rsi - low) / (high - low)) * 100


def _near(value: float, target: float | None, pct: float) -> bool:
    return bool(target) and abs(_pct(value, float(target))) <= pct


def _recent_double(close: pd.Series, lookback: int = 63) -> bool:
    window = close.tail(lookback)
    if len(window) < 20:
        return False
    return close.iloc[-1] >= window.min() * 1.8


def _nearest_support(close: pd.Series, current: float) -> float | None:
    levels = [
        close.rolling(10).mean().iloc[-1],
        close.ewm(span=21).mean().iloc[-1],
        close.rolling(50).mean().iloc[-1],
    ]
    if len(close) >= 200:
        levels.append(close.rolling(200).mean().iloc[-1])
    below = [_safe_float(x) for x in levels if _safe_float(x) and _safe_float(x) <= current]
    return max(below) if below else None


def _nearest_resistance(high: pd.Series, current: float) -> float | None:
    candidates = [high.tail(20).max(), high.tail(50).max(), high.tail(126).max()]
    above = [_safe_float(x) for x in candidates if _safe_float(x) and _safe_float(x) >= current]
    return min(above) if above else None


def analyze_top_bottom(ticker: str, hist: pd.DataFrame, position: dict | None = None) -> dict:
    """Return scored top/bottom buckets for one ticker from daily OHLCV history."""
    open_ = hist["Open"]
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    current = float(close.iloc[-1])

    rsi = compute_rsi(close, 14)
    rsi_now = float(rsi.iloc[-1])
    rsi_5d_low = float(rsi.tail(6).min())
    rsi_5d_high = float(rsi.tail(6).max())
    stoch = _stoch_rsi(rsi).iloc[-1]
    stoch_now = _safe_float(stoch) or 50.0
    macd_line, signal_line, macd_hist = compute_macd(close)
    bb_upper, bb_mid, bb_lower = compute_bollinger(close)

    ma10 = close.rolling(10).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    vol50 = volume.rolling(50).mean().iloc[-1]
    rvol = float(volume.iloc[-1] / vol50) if vol50 else 0.0
    day_range = high.iloc[-1] - low.iloc[-1]
    close_pos = ((current - low.iloc[-1]) / day_range * 100) if day_range else 50.0
    chg_5d = _pct(current, close.iloc[-6]) if len(close) > 6 else 0.0
    chg_20d = _pct(current, close.iloc[-21]) if len(close) > 21 else 0.0
    ext_50 = _pct(current, ma50) if ma50 else 0.0
    ext_200 = _pct(current, ma200) if ma200 else 0.0
    trend_ok = bool(ma200 and current > ma200 and ma50 > ma200)
    recent_low = low.tail(20).min()
    recent_high = high.tail(20).max()

    buy_signals = [(name, detail) for name, fired, detail in check_buy_signals(hist) if fired]
    sell_signals = [(name, detail) for name, fired, detail in check_sell_signals(hist) if fired]

    bottom_signals: list[str] = []
    pullback_signals: list[str] = []
    top_signals: list[str] = []

    # Bottom/reversal-up prompt translations.
    if rsi_now < 40 and rsi_now > rsi_5d_low * 1.03:
        bottom_signals.append(f"RSI Oversold Reversion: RSI {rsi_now:.1f} rising from {rsi_5d_low:.1f}")
    if stoch_now < 25 and current > close.iloc[-2]:
        bottom_signals.append(f"Oversold Bounce: StochRSI {stoch_now:.0f}, green reversal day")
    if ma200 and _near(current, ma200, 3.0) and current > close.iloc[-2]:
        bottom_signals.append(f"200-Day Bounce: price within 3% of 200 SMA ${ma200:.2f}")
    if current <= recent_low * 1.04 and rsi_now > rsi.tail(20).min() * 1.05:
        bottom_signals.append("Bullish divergence: price near 20d low while RSI is improving")
    if low.tail(40).nsmallest(2).max() <= low.tail(40).nsmallest(2).min() * 1.06 and current > close.tail(10).max() * 0.98:
        bottom_signals.append("Double-bottom-ish: two similar recent lows with price pressing back up")
    for name, detail in buy_signals:
        if name in {"Bollinger Band bounce", "Reclaimed 10 MA", "Reclaimed 21 EMA"}:
            bottom_signals.append(f"{name}: {detail}")

    # Pullback-buy prompt translations.
    if trend_ok and _near(current, ema21, 3.0) and 35 <= rsi_now <= 60:
        pullback_signals.append(f"Pullback to 21 EMA: ${current:.2f} near EMA21 ${ema21:.2f}, RSI {rsi_now:.1f}")
    if trend_ok and _near(current, ma50, 4.0) and current >= ma50 * 0.97:
        pullback_signals.append(f"Constructive 50 SMA support test: ${current:.2f} vs ${ma50:.2f}")
    if trend_ok and chg_20d > 8 and chg_5d < 0 and rvol < 0.9:
        pullback_signals.append(f"Livermore Buy the Dip: uptrend pullback on quiet volume, 20d {chg_20d:+.1f}%")
    if trend_ok and close_pos >= 60 and current > close.iloc[-2] and rvol >= 1.0:
        pullback_signals.append(f"Demand returning: close position {close_pos:.0f}% with RVOL {rvol:.2f}x")

    # Top / sell prompt translations.
    if rsi_now > 70 and rsi_now < rsi_5d_high * 0.97:
        top_signals.append(f"RSI overbought fading: RSI {rsi_now:.1f} below 5d peak {rsi_5d_high:.1f}")
    if current >= recent_high * 0.99 and rsi_now < rsi.tail(20).max() * 0.95:
        top_signals.append("Bearish divergence: price near 20d high while RSI failed to confirm")
    if ext_50 > 15:
        top_signals.append(f"Parabolic/extended: {ext_50:+.1f}% above 50 SMA")
    if ext_200 > 40:
        top_signals.append(f"Very extended from 200 SMA: {ext_200:+.1f}%")
    if _recent_double(close) and (rsi_now < rsi_5d_high * 0.97 or macd_hist.iloc[-1] < macd_hist.iloc[-2]):
        top_signals.append("Recent Doubler losing momentum")
    if rvol > 1.5 and current < open_.iloc[-1] and close_pos < 40:
        top_signals.append(f"Volume Surge distribution: RVOL {rvol:.2f}x, weak close")
    if high.tail(5).max() >= bb_upper.tail(5).max() * 0.99 and current < bb_upper.iloc[-1] and current < close.iloc[-2]:
        top_signals.append("Buyable Gap/upper-band rejection risk: upper Bollinger test failed")
    for name, detail in sell_signals:
        if name in {"MACD bearish crossover", "MACD histogram contracting", "Heavy distribution day", "Below 10 MA", "Below 21 EMA", "Weak close (lower 20%)", "Bollinger Band rejection"}:
            top_signals.append(f"{name}: {detail}")

    support = _nearest_support(close, current)
    resistance = _nearest_resistance(high, current)
    position = position or {}
    avg_cost = _safe_float(position.get("avg_cost"))
    shares = _safe_float(position.get("shares"))
    pnl_pct = _pct(current, avg_cost) if avg_cost else None

    candidates: list[Candidate] = []

    def add_candidate(bucket: str, label: str, signals: list[str], base_score: int, invalidation: float | None):
        if not signals:
            return
        score = min(100, base_score + len(signals) * 12)
        if bucket == "top / trim / avoid candidates":
            risk = "High" if score >= 70 else "Medium" if score >= 45 else "Low"
            if pnl_pct is not None and pnl_pct > 8 and risk in {"High", "Medium"}:
                action = "Trim 25-50% / trail stop"
            elif risk == "High":
                action = "Avoid new buys / consider trim"
            else:
                action = "Watch for confirmation"
        else:
            risk = "High" if not trend_ok and bucket != "pullback-buy candidates" else "Medium" if score < 70 else "Low/Medium"
            action = "Starter trade candidate" if score >= 70 and risk != "High" else "Watchlist"
        trade_or_watchlist = "trade" if score >= 70 and risk != "High" else "watchlist"
        candidates.append(Candidate(
            ticker=ticker,
            bucket=bucket,
            label=label,
            score=score,
            risk=risk,
            action=action,
            price=round(current, 2),
            signals=signals[:6],
            invalidation=round(float(invalidation), 2) if invalidation else None,
            support=round(float(support), 2) if support else None,
            resistance=round(float(resistance), 2) if resistance else None,
            trade_or_watchlist=trade_or_watchlist,
            pnl_pct=round(float(pnl_pct), 1) if pnl_pct is not None else None,
            shares=shares,
            avg_cost=avg_cost,
        ))

    add_candidate(
        "reversal-up candidates",
        "possible bottom / reversal-up",
        bottom_signals,
        25,
        min(float(low.tail(5).min()), support or float(low.tail(5).min())),
    )
    add_candidate(
        "pullback-buy candidates",
        "trend pullback buy zone",
        pullback_signals,
        30,
        support or float(ema21),
    )
    add_candidate(
        "top / trim / avoid candidates",
        "top / pullback risk",
        top_signals,
        30,
        support or float(ema21),
    )

    return {
        "ticker": ticker,
        "price": round(current, 2),
        "rsi": round(rsi_now, 1),
        "ema21": round(float(ema21), 2),
        "ma50": round(float(ma50), 2),
        "ma200": round(float(ma200), 2) if ma200 else None,
        "rvol": round(rvol, 2),
        "pnl_pct": round(float(pnl_pct), 1) if pnl_pct is not None else None,
        "candidates": [asdict(c) for c in candidates],
    }


def _load_json_positions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict) and x.get("ticker")]


def load_holdings(db_path: str = DEFAULT_DB, latest_scan: str = "latest_scan.json") -> list[dict]:
    """Load holdings from local DB, falling back to latest_scan.json."""
    positions: list[dict] = []
    try:
        init_db(db_path)
        positions = get_positions(db_path)
    except sqlite3.Error:
        positions = []
    if positions:
        return positions
    return _load_json_positions(Path(latest_scan))


def load_moomoo_watchlist(ctx: OpenQuoteContext, group: str) -> list[str]:
    ret, data = ctx.get_user_security(group)
    if ret != RET_OK or data is None or data.empty:
        return []
    return [_clean_ticker(str(code)) for code in data["code"].tolist()]


def load_local_watchlist(db_path: str = DEFAULT_DB) -> list[str]:
    try:
        init_db(db_path)
        return get_watchlist(db_path)
    except sqlite3.Error:
        return []


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        t = item.upper().strip().replace("US.", "")
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def scan_tickers(ctx: OpenQuoteContext, tickers: list[str], positions: dict[str, dict]) -> dict:
    analyses = []
    errors = []
    for idx, ticker in enumerate(tickers):
        # OpenD history endpoint is capped at ~60 calls / 30 sec. Stay below it
        # so an "all" scan doesn't self-own after one enthusiastic burst.
        if idx:
            time.sleep(0.55)
        hist = _fetch_history(ctx, ticker, days=430)
        if hist.empty or len(hist) < 50:
            errors.append({"ticker": ticker, "error": f"insufficient data ({len(hist)} rows)"})
            continue
        try:
            analyses.append(analyze_top_bottom(ticker, hist, positions.get(ticker)))
        except Exception as exc:  # noqa: BLE001 - report and continue scanning other symbols
            errors.append({"ticker": ticker, "error": str(exc)})

    buckets = {
        "reversal-up candidates": [],
        "pullback-buy candidates": [],
        "top / trim / avoid candidates": [],
    }
    for analysis in analyses:
        for candidate in analysis["candidates"]:
            buckets[candidate["bucket"]].append(candidate)
    for rows in buckets.values():
        rows.sort(key=lambda x: (x["score"], x.get("pnl_pct") or 0), reverse=True)
    return {"analyses": analyses, "buckets": buckets, "errors": errors}


def print_report(payload: dict, limit: int) -> None:
    print(f"\nTop/bottom scan — {payload['scanned']} tickers @ {payload['timestamp']}")
    if payload.get("sources"):
        print("Sources: " + ", ".join(payload["sources"]))
    print("Read-only: no orders placed, no watchlists edited. Obviously.\n")

    for bucket, rows in payload["buckets"].items():
        print(bucket.upper())
        if not rows:
            print("  None")
            print()
            continue
        for row in rows[:limit]:
            pnl = f", P/L {row['pnl_pct']:+.1f}%" if row.get("pnl_pct") is not None else ""
            inv = f", invalidation ${row['invalidation']:.2f}" if row.get("invalidation") else ""
            sr = []
            if row.get("support"):
                sr.append(f"support ${row['support']:.2f}")
            if row.get("resistance"):
                sr.append(f"resistance ${row['resistance']:.2f}")
            sr_text = f" ({'; '.join(sr)})" if sr else ""
            print(
                f"  {row['ticker']}: {row['score']}/100, {row['risk']} risk, "
                f"{row['action']} — ${row['price']:.2f}{pnl}{inv}{sr_text}"
            )
            for sig in row["signals"][:3]:
                print(f"    - {sig}")
        print()

    if payload.get("errors"):
        print("Skipped:")
        for err in payload["errors"][:20]:
            print(f"  {err['ticker']}: {err['error']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for tops, bottoms, and pullback buys via Moomoo OpenD")
    parser.add_argument("tickers", nargs="*", help="Optional explicit tickers to scan")
    parser.add_argument("--mode", choices=("watchlist", "holdings", "all"), default="all")
    parser.add_argument("--groups", nargs="*", default=list(DEFAULT_GROUPS), help="Moomoo watchlist groups")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--output", default="topbottom_scan.json")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    sources: list[str] = []
    try:
        holdings = load_holdings(args.db)
        positions = {p["ticker"].upper(): p for p in holdings if p.get("ticker")}
        tickers: list[str] = []

        if args.tickers:
            tickers.extend(args.tickers)
            sources.append("explicit tickers")
        if args.mode in {"holdings", "all"}:
            tickers.extend(positions.keys())
            if positions:
                sources.append(f"holdings ({len(positions)})")
        if args.mode in {"watchlist", "all"}:
            local = load_local_watchlist(args.db)
            if local:
                tickers.extend(local)
                sources.append(f"local watchlist ({len(local)})")
            for group in args.groups:
                group_tickers = load_moomoo_watchlist(ctx, group)
                if group_tickers:
                    tickers.extend(group_tickers)
                    sources.append(f"Moomoo {group} ({len(group_tickers)})")

        tickers = _dedupe(tickers)
        result = scan_tickers(ctx, tickers, positions)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": args.mode,
            "sources": sources,
            "scanned": len(tickers),
            **result,
        }
        Path(args.output).write_text(json.dumps(payload, indent=2))
        print_report(payload, args.limit)
        print(f"Saved JSON: {args.output}")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
