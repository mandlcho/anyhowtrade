#!/usr/bin/env python3
"""
Sell Signal Analyzer — fetches market data and computes technical indicators
for portfolio positions. Output is designed to be analyzed by Claude Code CLI
using the AskLivermore extracted sell prompts.
"""

import yfinance as yf
import pandas as pd
import json
import sys
from datetime import datetime

PORTFOLIO = [
    {"ticker": "UNH",  "shares": 100, "avg_cost": 321.081},
    {"ticker": "SMR",  "shares": 300, "avg_cost": 21.00},
    {"ticker": "IREN", "shares": 700, "avg_cost": 55.114},
    {"ticker": "CPRT", "shares": 100, "avg_cost": 48.413},
    {"ticker": "CIFR", "shares": 225, "avg_cost": 17.467},
    {"ticker": "BBAI", "shares": 400, "avg_cost": 9.08},
    {"ticker": "ASST", "shares": 30,  "avg_cost": 27.466},
    {"ticker": "AMZN", "shares": 45,  "avg_cost": 216.731},
]

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def compute_bollinger(series, period=20, std_mult=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return upper, sma, lower

def analyze_stock(pos):
    ticker = pos["ticker"]
    try:
        stock = yf.Ticker(ticker)
        # 1 year of daily data
        hist = stock.history(period="1y")
        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "error": "Insufficient data"}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current_price = close.iloc[-1]
        prev_close = close.iloc[-2]

        # Moving averages
        ma10 = close.rolling(10).mean().iloc[-1]
        ma21 = close.ewm(span=21).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma150 = close.rolling(150).mean().iloc[-1] if len(close) >= 150 else None
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        # Distance from MAs (% extension)
        ext_from_50ma = ((current_price - ma50) / ma50) * 100
        ext_from_200ma = ((current_price - ma200) / ma200) * 100 if ma200 else None

        # RSI
        rsi_14 = compute_rsi(close, 14).iloc[-1]
        rsi_5_ago = compute_rsi(close, 14).iloc[-6] if len(close) > 6 else None

        # MACD
        macd_line, signal_line, macd_hist = compute_macd(close)
        macd_current = macd_line.iloc[-1]
        macd_signal = signal_line.iloc[-1]
        macd_hist_current = macd_hist.iloc[-1]
        macd_hist_prev = macd_hist.iloc[-2]

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = compute_bollinger(close)
        bb_upper_val = bb_upper.iloc[-1]
        bb_lower_val = bb_lower.iloc[-1]
        bb_width = ((bb_upper_val - bb_lower_val) / bb_mid.iloc[-1]) * 100
        bb_position = ((current_price - bb_lower_val) / (bb_upper_val - bb_lower_val)) * 100

        # Volume analysis
        vol_50avg = volume.rolling(50).mean().iloc[-1]
        vol_today = volume.iloc[-1]
        rvol = vol_today / vol_50avg if vol_50avg > 0 else 0

        # Volume trend (last 5 days avg vs 50-day avg)
        vol_5avg = volume.tail(5).mean()
        vol_trend = vol_5avg / vol_50avg if vol_50avg > 0 else 0

        # 52-week high/low
        high_52w = high.max()
        low_52w = low.min()
        pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100
        pct_from_52w_low = ((current_price - low_52w) / low_52w) * 100

        # Recent price action
        change_1d = ((current_price - prev_close) / prev_close) * 100
        change_5d = ((current_price - close.iloc[-6]) / close.iloc[-6]) * 100 if len(close) > 6 else None
        change_20d = ((current_price - close.iloc[-21]) / close.iloc[-21]) * 100 if len(close) > 21 else None
        change_60d = ((current_price - close.iloc[-61]) / close.iloc[-61]) * 100 if len(close) > 61 else None

        # ADR% (14-day)
        daily_range_pct = ((high - low) / close * 100).tail(14).mean()

        # Check for momentum divergence (price higher high but RSI lower high)
        rsi_series = compute_rsi(close, 14)
        recent_20_close = close.tail(20)
        recent_20_rsi = rsi_series.tail(20)

        price_making_new_highs = current_price >= recent_20_close.max() * 0.99
        rsi_below_recent_peak = rsi_14 < recent_20_rsi.max() * 0.95
        bearish_divergence = price_making_new_highs and rsi_below_recent_peak

        # Volume climax detection (today's volume vs recent)
        vol_max_10d = volume.tail(10).max()
        volume_climax = vol_today >= vol_max_10d * 0.95 and rvol >= 2.0

        # Close position in day's range
        day_range = high.iloc[-1] - low.iloc[-1]
        if day_range > 0:
            close_position_pct = ((current_price - low.iloc[-1]) / day_range) * 100
        else:
            close_position_pct = 50

        # P&L
        unrealized_pnl = (current_price - pos["avg_cost"]) * pos["shares"]
        unrealized_pnl_pct = ((current_price - pos["avg_cost"]) / pos["avg_cost"]) * 100
        position_value = current_price * pos["shares"]

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "avg_cost": pos["avg_cost"],
            "shares": pos["shares"],
            "position_value": round(position_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "price_action": {
                "change_1d_pct": round(change_1d, 2),
                "change_5d_pct": round(change_5d, 2) if change_5d else None,
                "change_20d_pct": round(change_20d, 2) if change_20d else None,
                "change_60d_pct": round(change_60d, 2) if change_60d else None,
                "adr_14d_pct": round(daily_range_pct, 2),
                "close_position_in_range_pct": round(close_position_pct, 1),
            },
            "moving_averages": {
                "ma10": round(ma10, 2),
                "ema21": round(ma21, 2),
                "ma50": round(ma50, 2),
                "ma150": round(ma150, 2) if ma150 else None,
                "ma200": round(ma200, 2) if ma200 else None,
                "extension_from_50ma_pct": round(ext_from_50ma, 2),
                "extension_from_200ma_pct": round(ext_from_200ma, 2) if ext_from_200ma else None,
                "price_above_50ma": current_price > ma50,
                "price_above_200ma": current_price > ma200 if ma200 else None,
            },
            "momentum": {
                "rsi_14": round(rsi_14, 2),
                "rsi_5_days_ago": round(rsi_5_ago, 2) if rsi_5_ago else None,
                "macd_line": round(macd_current, 3),
                "macd_signal": round(macd_signal, 3),
                "macd_histogram": round(macd_hist_current, 3),
                "macd_hist_direction": "expanding" if abs(macd_hist_current) > abs(macd_hist_prev) else "contracting",
                "bearish_divergence": bearish_divergence,
            },
            "volatility": {
                "bb_upper": round(bb_upper_val, 2),
                "bb_lower": round(bb_lower_val, 2),
                "bb_width_pct": round(bb_width, 2),
                "bb_position_pct": round(bb_position, 1),
            },
            "volume": {
                "today_volume": int(vol_today),
                "avg_50d_volume": int(vol_50avg),
                "rvol": round(rvol, 2),
                "vol_5d_vs_50d": round(vol_trend, 2),
                "volume_climax": volume_climax,
            },
            "range_52w": {
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "pct_from_52w_high": round(pct_from_52w_high, 2),
                "pct_from_52w_low": round(pct_from_52w_low, 2),
            },
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def main():
    print(f"\n{'='*70}")
    print(f"  SELL SIGNAL ANALYSIS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}\n")

    results = []
    for pos in PORTFOLIO:
        print(f"  Fetching {pos['ticker']}...", end=" ", flush=True)
        result = analyze_stock(pos)
        results.append(result)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            pnl = result["unrealized_pnl_pct"]
            emoji = "+" if pnl >= 0 else ""
            print(f"${result['current_price']} ({emoji}{pnl}%)")

    # Save full JSON for Claude analysis
    output_path = "/Users/mandl/Desktop/projects/asklivermore/latest_scan.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n  Full data saved to: {output_path}")
    print(f"  Run 'claude' and ask it to analyze latest_scan.json with the sell prompts.\n")

    # Print summary table
    print(f"{'Ticker':<8} {'Price':>8} {'P&L%':>8} {'RSI':>6} {'Ext50':>7} {'RVOL':>6} {'BDiv':>5} {'VClim':>5}")
    print("-" * 62)
    for r in results:
        if "error" in r:
            print(f"{r['ticker']:<8} {'ERROR':>8}")
            continue
        print(f"{r['ticker']:<8} "
              f"${r['current_price']:>7.2f} "
              f"{r['unrealized_pnl_pct']:>7.1f}% "
              f"{r['momentum']['rsi_14']:>5.1f} "
              f"{r['moving_averages']['extension_from_50ma_pct']:>6.1f}% "
              f"{r['volume']['rvol']:>5.1f}x "
              f"{'YES' if r['momentum']['bearish_divergence'] else 'no':>5} "
              f"{'YES' if r['volume']['volume_climax'] else 'no':>5}")
    print()

if __name__ == "__main__":
    main()
