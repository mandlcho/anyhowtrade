#!/usr/bin/env python3
"""PB EMA scanner — 200-period EMA of Highs (upper) and Closes (lower).

Fetches Daily and 4H (resampled from 60M) data via OpenD.

Usage:
    pb.py              — scan all tickers from latest_scan.json
    pb.py MSFT         — scan a specific ticker
    pb.py MSFT AAPL    — scan multiple tickers
"""

import json
import sys
from datetime import datetime, timedelta

import pandas as pd
from moomoo import OpenQuoteContext, KLType, AuType, KL_FIELD, RET_OK

from scanner import _moomoo_code, OPEND_HOST, OPEND_PORT


def _fetch_daily(ctx, ticker):
    code = _moomoo_code(ticker)
    end_date   = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")

    ret, data, _ = ctx.request_history_kline(
        code,
        start=start_date,
        end=end_date,
        ktype=KLType.K_DAY,
        autype=AuType.QFQ,
        fields=[KL_FIELD.ALL],
        max_count=1000,
    )
    if ret != RET_OK or data is None or data.empty:
        return pd.DataFrame()

    return pd.DataFrame({
        "Open":   data["open"].values,
        "High":   data["high"].values,
        "Low":    data["low"].values,
        "Close":  data["close"].values,
        "Volume": data["volume"].values,
    }, index=pd.to_datetime(data["time_key"]))


def _fetch_4h(ctx, ticker):
    code = _moomoo_code(ticker)
    end_date   = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")

    ret, data, _ = ctx.request_history_kline(
        code,
        start=start_date,
        end=end_date,
        ktype=KLType.K_60M,
        autype=AuType.QFQ,
        fields=[KL_FIELD.ALL],
        max_count=1200,
    )
    if ret != RET_OK or data is None or data.empty:
        return pd.DataFrame()

    df_60m = pd.DataFrame({
        "Open":   data["open"].values,
        "High":   data["high"].values,
        "Low":    data["low"].values,
        "Close":  data["close"].values,
        "Volume": data["volume"].values,
    }, index=pd.to_datetime(data["time_key"]))

    df_4h = df_60m.resample("4h").agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna()

    return df_4h


def _pb_ema(df, period=200):
    """Returns (pb_upper_series, pb_lower_series) — EMA of Highs and Closes."""
    pb_upper = df["High"].ewm(span=period, adjust=False).mean()
    pb_lower = df["Close"].ewm(span=period, adjust=False).mean()
    return pb_upper, pb_lower


def _position_label(close, pb_upper, pb_lower, close_prev, pb_upper_prev, pb_lower_prev):
    """Classify price vs PB EMA band."""
    pct_to_upper = (close - pb_upper) / pb_upper * 100
    pct_to_lower = (close - pb_lower) / pb_lower * 100

    # Transition labels take priority
    if close > pb_upper and close_prev <= pb_upper_prev:
        label = "Reclaiming Upper"
    elif close < pb_lower and close_prev >= pb_lower_prev:
        label = "Losing Lower"
    elif close > pb_upper:
        label = "Above Band"
    elif abs(pct_to_upper) <= 1.0 and close <= pb_upper:
        label = "At Upper Band"
    elif close >= pb_lower:
        label = "Inside Band"
    elif abs(pct_to_lower) <= 1.0:
        label = "At Lower Band"
    else:
        label = "Below Band"

    # Band expansion/compression
    upper_rising = pb_upper > pb_upper_prev
    lower_rising = pb_lower > pb_lower_prev
    if upper_rising and lower_rising:
        band_state = "Expanding"
    elif not upper_rising and not lower_rising:
        band_state = "Compressing"
    else:
        band_state = "Flat"

    return label, band_state, pct_to_upper, pct_to_lower


def print_ticker(ticker, df_daily, df_4h):
    print(f"\n{'='*64}")
    print(f"  TICKER: {ticker}")
    print(f"{'='*64}")

    # --- DAILY ---
    if df_daily.empty or len(df_daily) < 210:
        print("  [DAILY] Insufficient data (need 200+ bars)")
    else:
        pb_up, pb_lo = _pb_ema(df_daily)

        close_now   = df_daily["Close"].iloc[-1]
        close_prev  = df_daily["Close"].iloc[-2]
        up_now      = pb_up.iloc[-1]
        up_prev     = pb_up.iloc[-2]
        lo_now      = pb_lo.iloc[-1]
        lo_prev     = pb_lo.iloc[-2]

        label, band_state, pct_up, pct_lo = _position_label(
            close_now, up_now, lo_now, close_prev, up_prev, lo_prev
        )

        print(f"\n  [DAILY — last 3 candles]")
        for i in [-3, -2, -1]:
            ts  = df_daily.index[i]
            row = df_daily.iloc[i]
            u   = pb_up.iloc[i]
            l   = pb_lo.iloc[i]
            chg = (row["Close"] - df_daily["Close"].iloc[i-1]) / df_daily["Close"].iloc[i-1] * 100
            print(f"    {ts.strftime('%Y-%m-%d')} | O:{row['Open']:.2f} H:{row['High']:.2f} "
                  f"L:{row['Low']:.2f} C:{row['Close']:.2f} ({chg:+.1f}%) "
                  f"| PB_upper:{u:.2f}  PB_lower:{l:.2f}")

        print(f"\n  Daily PB_upper : {up_now:.2f}")
        print(f"  Daily PB_lower : {lo_now:.2f}")
        print(f"  Daily Close    : {close_now:.2f}")
        print(f"  vs PB_upper    : {pct_up:+.2f}%")
        print(f"  vs PB_lower    : {pct_lo:+.2f}%")
        print(f"  Position       : {label}")
        print(f"  Band State     : {band_state}")

    # --- 4H ---
    if df_4h.empty or len(df_4h) < 210:
        print(f"\n  [4H] Insufficient data (need 200+ 4H bars, got {len(df_4h)})")
    else:
        pb_up4, pb_lo4 = _pb_ema(df_4h)

        close_now   = df_4h["Close"].iloc[-1]
        close_prev  = df_4h["Close"].iloc[-2]
        up_now      = pb_up4.iloc[-1]
        up_prev     = pb_up4.iloc[-2]
        lo_now      = pb_lo4.iloc[-1]
        lo_prev     = pb_lo4.iloc[-2]

        label4, band_state4, pct_up4, pct_lo4 = _position_label(
            close_now, up_now, lo_now, close_prev, up_prev, lo_prev
        )

        print(f"\n  [4H — last 3 candles]")
        for i in [-3, -2, -1]:
            ts  = df_4h.index[i]
            row = df_4h.iloc[i]
            u   = pb_up4.iloc[i]
            l   = pb_lo4.iloc[i]
            chg = (row["Close"] - df_4h["Close"].iloc[i-1]) / df_4h["Close"].iloc[i-1] * 100
            print(f"    {ts.strftime('%Y-%m-%d %H:%M')} | O:{row['Open']:.2f} H:{row['High']:.2f} "
                  f"L:{row['Low']:.2f} C:{row['Close']:.2f} ({chg:+.1f}%) "
                  f"| PB_upper:{u:.2f}  PB_lower:{l:.2f}")

        print(f"\n  4H PB_upper : {up_now:.2f}")
        print(f"  4H PB_lower : {lo_now:.2f}")
        print(f"  4H Close    : {close_now:.2f}")
        print(f"  vs PB_upper : {pct_up4:+.2f}%")
        print(f"  vs PB_lower : {pct_lo4:+.2f}%")
        print(f"  Position    : {label4}")
        print(f"  Band State  : {band_state4}")

    print()


def main():
    args = sys.argv[1:]

    if args:
        tickers = [t.upper().strip(",") for t in args]
    else:
        try:
            with open("/Users/mandl/Desktop/projects/openscan/latest_scan.json") as f:
                positions = json.load(f)
            tickers = [p["ticker"] for p in positions if "ticker" in p]
        except FileNotFoundError:
            print("ERROR: latest_scan.json not found. Run a scan first.")
            sys.exit(1)

    if not tickers:
        print("No tickers found.")
        sys.exit(0)

    ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    try:
        for ticker in tickers:
            print(f"Fetching {ticker}...", end="", flush=True)
            df_daily = _fetch_daily(ctx, ticker)
            df_4h    = _fetch_4h(ctx, ticker)
            print(f" daily:{len(df_daily)}bars  4H:{len(df_4h)}bars")
            print_ticker(ticker, df_daily, df_4h)
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
