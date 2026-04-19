"""Multi-Timeframe Bias Analysis — ported from Pine Script to Python/OpenD.

Computes directional bias across 7 timeframes (1m, 5m, 15m, 1H, 4H, D, W)
using Dual EMA crossover + ADX trend filter + confirmation bars, then
produces a weighted overall signal and market structure detection (CHoCH/BOS).
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Try importing moomoo KLType constants; fall back to a simple namespace
# so the module can still be tested without moomoo installed.
try:
    from moomoo import KLType, AuType, KL_FIELD, RET_OK, OpenQuoteContext
except ImportError:  # pragma: no cover
    KLType = None
    OpenQuoteContext = None

# ---------------------------------------------------------------------------
# OpenD helpers (duplicated from scanner to avoid circular import)
# ---------------------------------------------------------------------------

OPEND_HOST = "127.0.0.1"
OPEND_PORT = 11111


def _moomoo_code(ticker):
    """Convert plain ticker to moomoo format: AAPL -> US.AAPL"""
    if "." in ticker:
        return ticker
    return f"US.{ticker.upper()}"


def _get_quote_ctx():
    """Create and return a moomoo OpenQuoteContext."""
    if OpenQuoteContext is None:
        raise RuntimeError("moomoo is not installed")
    return OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)


# ---------------------------------------------------------------------------
# Timeframe configuration
# ---------------------------------------------------------------------------

TIMEFRAMES = [
    {"label": "1m",  "weight": 1},
    {"label": "5m",  "weight": 1},
    {"label": "15m", "weight": 1},
    {"label": "1H",  "weight": 2},
    {"label": "4H",  "weight": 2},
    {"label": "D",   "weight": 3},
    {"label": "W",   "weight": 3},
]

MAX_WEIGHT = sum(tf["weight"] for tf in TIMEFRAMES)  # 13

# Map label -> moomoo KLType attribute name
_KL_MAP = {
    "1m":  "K_1M",
    "5m":  "K_5M",
    "15m": "K_15M",
    "1H":  "K_60M",
    "4H":  "K_4H",
    "D":   "K_DAY",
    "W":   "K_WEEK",
}

# How many calendar days of history to request per timeframe
_DAYS_MAP = {
    "1m":  3,
    "5m":  10,
    "15m": 20,
    "1H":  60,
    "4H":  120,
    "D":   365,
    "W":   730,
}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_tf_candles(quote_ctx, ticker, tf_label, days=None):
    """Fetch OHLCV candles for a single timeframe from OpenD.

    Returns a DataFrame with columns: Open, High, Low, Close, Volume.
    Returns an empty DataFrame on failure.
    """
    if KLType is None:
        return pd.DataFrame()

    kl_attr = _KL_MAP.get(tf_label)
    if kl_attr is None:
        return pd.DataFrame()

    ktype = getattr(KLType, kl_attr, None)
    if ktype is None:
        # 4H may not exist in older moomoo versions — resample from 1H
        if tf_label == "4H":
            return _resample_4h(quote_ctx, ticker)
        return pd.DataFrame()

    code = _moomoo_code(ticker)
    if days is None:
        days = _DAYS_MAP.get(tf_label, 60)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        ret, data, _ = quote_ctx.request_history_kline(
            code,
            start=start_date,
            end=end_date,
            ktype=ktype,
            autype=AuType.QFQ,
            fields=[KL_FIELD.ALL],
            max_count=500,
        )
    except Exception:
        return pd.DataFrame()

    if ret != RET_OK or data is None or data.empty:
        return pd.DataFrame()

    df = pd.DataFrame({
        "Open": data["open"].values,
        "High": data["high"].values,
        "Low": data["low"].values,
        "Close": data["close"].values,
        "Volume": data["volume"].values,
    }, index=pd.to_datetime(data["time_key"]))

    return df


def _resample_4h(quote_ctx, ticker):
    """Build 4-hour candles by resampling 1-hour data."""
    df_1h = _fetch_tf_candles(quote_ctx, ticker, "1H", days=120)
    if df_1h.empty or len(df_1h) < 4:
        return pd.DataFrame()
    resampled = df_1h.resample("4h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()
    return resampled


# ---------------------------------------------------------------------------
# ADX calculation  (Wilder's smoothing = RMA = ewm with alpha=1/length)
# ---------------------------------------------------------------------------

def _rma(series, length):
    """Wilder's smoothing / Running Moving Average (same as Pine ta.rma)."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()


def _compute_adx(high, low, close, length=14):
    """Compute ADX from high/low/close Series.

    Returns a Series of ADX values (same length as input).
    """
    up = high.diff()
    down = -low.diff()

    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0),
                        index=close.index, dtype=float)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0),
                         index=close.index, dtype=float)

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = _rma(tr, length)
    plus_di = 100.0 * _rma(plus_dm, length) / atr
    minus_di = 100.0 * _rma(minus_dm, length) / atr

    dx_denom = plus_di + minus_di
    dx = pd.Series(
        np.where(dx_denom != 0, 100.0 * (plus_di - minus_di).abs() / dx_denom, 0.0),
        index=close.index, dtype=float,
    )

    adx = _rma(dx, length)
    return adx


# ---------------------------------------------------------------------------
# Single-timeframe bias
# ---------------------------------------------------------------------------

def _compute_single_tf_bias(df, fast=9, slow=21, adx_len=14,
                             adx_threshold=20, confirm_bars=3):
    """Compute bias for one timeframe given an OHLCV DataFrame.

    Returns dict with keys: bias ("BULL"/"BEAR"/"NEUT"), adx (float),
    confirmed (bool), raw_bias_series (for internal use).
    """
    if df is None or df.empty or len(df) < max(slow, adx_len) + confirm_bars:
        return {"bias": "NEUT", "adx": None, "confirmed": False}

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)

    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()

    # Raw bias per bar: +1 BULL, -1 BEAR, 0 NEUT
    raw_bias = pd.Series(0, index=close.index, dtype=int)
    bull_mask = (fast_ema > slow_ema) & (close > fast_ema)
    bear_mask = (fast_ema < slow_ema) & (close < fast_ema)
    raw_bias[bull_mask] = 1
    raw_bias[bear_mask] = -1

    # ADX filter — force neutral when ADX < threshold
    adx = _compute_adx(high, low, close, adx_len)
    adx_current = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else None

    filtered_bias = raw_bias.copy()
    weak_trend = adx < adx_threshold
    filtered_bias[weak_trend] = 0

    # Confirmation: bias must be the same for last N bars
    last_n = filtered_bias.iloc[-confirm_bars:]
    if len(last_n) < confirm_bars:
        confirmed = False
        final_bias = 0
    else:
        vals = last_n.values
        if np.all(vals == vals[0]):
            confirmed = True
            final_bias = int(vals[0])
        else:
            confirmed = False
            final_bias = int(filtered_bias.iloc[-1])

    label_map = {1: "BULL", -1: "BEAR", 0: "NEUT"}
    return {
        "bias": label_map[final_bias],
        "adx": round(adx_current, 1) if adx_current is not None else None,
        "confirmed": confirmed,
    }


# ---------------------------------------------------------------------------
# Swing detection + CHoCH / BOS (market structure)
# ---------------------------------------------------------------------------

def _detect_structure(df, swing_length=5):
    """Detect swing highs/lows, trend direction, CHoCH, and BOS.

    Returns dict with keys: trend, last_choch, last_bos.
    """
    result = {
        "trend": "undefined",
        "last_choch": None,
        "last_bos": None,
    }

    if df is None or df.empty or len(df) < swing_length * 2 + 1:
        return result

    high = df["High"].values.astype(float)
    low = df["Low"].values.astype(float)
    close = df["Close"].values.astype(float)
    n = len(df)

    # --- Detect swing highs and lows (pivots) ---
    swing_highs = []  # (index, value)
    swing_lows = []

    for i in range(swing_length, n - swing_length):
        # Swing high: high[i] is the max of surrounding bars
        is_sh = True
        for j in range(i - swing_length, i + swing_length + 1):
            if j != i and high[j] >= high[i]:
                is_sh = False
                break
        if is_sh:
            swing_highs.append((i, high[i]))

        # Swing low: low[i] is the min of surrounding bars
        is_sl = True
        for j in range(i - swing_length, i + swing_length + 1):
            if j != i and low[j] <= low[i]:
                is_sl = False
                break
        if is_sl:
            swing_lows.append((i, low[i]))

    if len(swing_highs) < 2 and len(swing_lows) < 2:
        return result

    # --- Determine trend from swing structure ---
    current_trend = 0  # 1=up, -1=down
    last_swing_high = None
    last_swing_low = None
    prev_swing_high = None
    prev_swing_low = None

    # Build a merged timeline of swings to track trend evolution
    all_swings = [(idx, val, "high") for idx, val in swing_highs] + \
                 [(idx, val, "low") for idx, val in swing_lows]
    all_swings.sort(key=lambda x: x[0])

    last_choch = None
    last_bos = None

    for idx, val, stype in all_swings:
        if stype == "high":
            if prev_swing_high is not None:
                if val > prev_swing_high:
                    current_trend = 1  # Higher high
                elif val < prev_swing_high:
                    current_trend = -1  # Lower high
            prev_swing_high = val
            last_swing_high = (idx, val)
        else:  # low
            if prev_swing_low is not None:
                if val > prev_swing_low:
                    current_trend = 1  # Higher low
                elif val < prev_swing_low:
                    current_trend = -1  # Lower low
            prev_swing_low = val
            last_swing_low = (idx, val)

    # --- Detect CHoCH and BOS on recent bars ---
    # Scan the most recent bars (after last swing) for structure breaks
    if last_swing_high is not None and last_swing_low is not None:
        sh_idx, sh_val = last_swing_high
        sl_idx, sl_val = last_swing_low

        # Check recent closes for breaks
        scan_start = max(sh_idx, sl_idx) + 1
        for i in range(scan_start, n):
            prev_close = close[i - 1] if i > 0 else close[i]

            # Bullish break above last swing high
            if close[i] > sh_val and prev_close <= sh_val:
                if current_trend == -1:
                    # CHoCH: reversal from downtrend
                    last_choch = {
                        "type": "bullish",
                        "price": round(float(sh_val), 2),
                        "bar_index": i,
                    }
                    current_trend = 1
                elif current_trend == 1:
                    # BOS: continuation in uptrend
                    last_bos = {
                        "type": "bullish",
                        "price": round(float(sh_val), 2),
                        "bar_index": i,
                    }

            # Bearish break below last swing low
            if close[i] < sl_val and prev_close >= sl_val:
                if current_trend == 1:
                    # CHoCH: reversal from uptrend
                    last_choch = {
                        "type": "bearish",
                        "price": round(float(sl_val), 2),
                        "bar_index": i,
                    }
                    current_trend = -1
                elif current_trend == -1:
                    # BOS: continuation in downtrend
                    last_bos = {
                        "type": "bearish",
                        "price": round(float(sl_val), 2),
                        "bar_index": i,
                    }

    trend_map = {1: "uptrend", -1: "downtrend", 0: "undefined"}
    result["trend"] = trend_map.get(current_trend, "undefined")
    result["last_choch"] = last_choch
    result["last_bos"] = last_bos

    return result


# ---------------------------------------------------------------------------
# Verdict text generation
# ---------------------------------------------------------------------------

def _build_verdict(tf_results, overall_bias, weighted_score, bull_count,
                   bear_count):
    """Generate a human-readable verdict string."""
    total_tf = len(tf_results)
    dominant = max(bull_count, bear_count)
    direction = "bullish" if bull_count >= bear_count else "bearish"

    if dominant == 0:
        return "No clear directional bias across timeframes. Market is choppy."

    # Check higher TF alignment
    higher_tfs = []
    for label in ("D", "W"):
        info = tf_results.get(label)
        if info and info["bias"] == ("BULL" if direction == "bullish" else "BEAR"):
            higher_tfs.append({"D": "Daily", "W": "Weekly"}[label])

    parts = []
    parts.append(f"{dominant} out of {total_tf} timeframes agree this stock is {direction}.")

    if len(higher_tfs) == 2:
        parts.append(f"The longer timeframes ({', '.join(higher_tfs)}) are leading the charge.")
    elif len(higher_tfs) == 1:
        parts.append(f"The {higher_tfs[0]} timeframe confirms the bias.")

    if dominant >= 6:
        parts.append("Very strong alignment — high conviction.")
    elif dominant >= 4:
        parts.append("Good alignment across multiple timeframes.")
    elif dominant <= 2:
        parts.append("Weak agreement — consider waiting for more confirmation.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_mtf_bias(ticker, quote_ctx=None):
    """Compute multi-timeframe bias for a ticker.

    Parameters
    ----------
    ticker : str
        Stock symbol (e.g. "AAPL" or "US.AAPL").
    quote_ctx : OpenQuoteContext or None
        Reuse an existing context. If None, creates and closes its own.

    Returns
    -------
    dict  — see module docstring for full structure.
    """
    own_ctx = quote_ctx is None
    if own_ctx:
        quote_ctx = _get_quote_ctx()

    try:
        tf_results = {}
        primary_df = None

        for tf in TIMEFRAMES:
            label = tf["label"]
            df = _fetch_tf_candles(quote_ctx, ticker, label)
            bias_info = _compute_single_tf_bias(df)
            tf_results[label] = bias_info

            # Use Daily as the primary TF for structure detection
            if label == "D" and not df.empty:
                primary_df = df

        return _assemble_result(tf_results, primary_df)
    finally:
        if own_ctx and quote_ctx is not None:
            quote_ctx.close()


def compute_mtf_bias_from_dataframes(tf_dataframes):
    """Compute MTF bias from pre-loaded DataFrames (useful for testing).

    Parameters
    ----------
    tf_dataframes : dict
        Keys are TF labels ("1m", "5m", etc.), values are OHLCV DataFrames.

    Returns
    -------
    dict
    """
    tf_results = {}
    primary_df = None

    for tf in TIMEFRAMES:
        label = tf["label"]
        df = tf_dataframes.get(label, pd.DataFrame())
        bias_info = _compute_single_tf_bias(df)
        tf_results[label] = bias_info

        if label == "D" and not df.empty:
            primary_df = df

    return _assemble_result(tf_results, primary_df)


def _assemble_result(tf_results, primary_df):
    """Build the final result dict from per-TF bias results."""
    # Weighted scoring
    weight_map = {tf["label"]: tf["weight"] for tf in TIMEFRAMES}
    weighted_bull = 0
    weighted_bear = 0
    bull_count = 0
    bear_count = 0

    for tf in TIMEFRAMES:
        label = tf["label"]
        info = tf_results.get(label, {})
        bias = info.get("bias", "NEUT")
        w = weight_map[label]

        if bias == "BULL":
            weighted_bull += w
            bull_count += 1
        elif bias == "BEAR":
            weighted_bear += w
            bear_count += 1

    weighted_score = weighted_bull - weighted_bear

    if weighted_score > 0:
        overall_bias = "BULLISH"
    elif weighted_score < 0:
        overall_bias = "BEARISH"
    else:
        overall_bias = "NEUTRAL"

    alignment_strength = max(bull_count, bear_count)

    # Structure detection on primary (daily) timeframe
    structure = _detect_structure(primary_df) if primary_df is not None else {
        "trend": "undefined",
        "last_choch": None,
        "last_bos": None,
    }

    verdict = _build_verdict(tf_results, overall_bias, weighted_score,
                             bull_count, bear_count)

    return {
        "timeframes": tf_results,
        "overall_bias": overall_bias,
        "weighted_score": weighted_score,
        "max_weighted": MAX_WEIGHT,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "alignment_strength": alignment_strength,
        "structure": structure,
        "verdict": verdict,
    }
