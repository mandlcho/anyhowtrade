"""Sell and buy signal detection engine.

Each checker returns a list of (signal_name, fired: bool, detail: str) tuples.
Signal logic uses only OHLCV history + indicators — no I/O.
"""

import pandas as pd
from indicators import compute_rsi, compute_macd, compute_bollinger


# ---------------------------------------------------------------------------
# Sell signals (10)
# ---------------------------------------------------------------------------

def check_sell_signals(hist: pd.DataFrame) -> list[tuple[str, bool, str]]:
    """Run 10 sell signals against a stock's OHLCV history.

    Parameters
    ----------
    hist : DataFrame with columns Open, High, Low, Close, Volume (≥50 rows).

    Returns
    -------
    List of (signal_name, fired, detail) tuples.
    """
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    current = close.iloc[-1]

    # Pre-compute indicators
    rsi = compute_rsi(close, 14)
    rsi_now = rsi.iloc[-1]
    macd_line, signal_line, macd_hist = compute_macd(close)
    bb_upper, bb_mid, bb_lower = compute_bollinger(close)

    ma10 = close.rolling(10).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]

    vol_50avg = volume.rolling(50).mean().iloc[-1]
    rvol = volume.iloc[-1] / vol_50avg if vol_50avg > 0 else 0

    signals = []

    # 1. RSI >70 + falling from 5-day peak
    rsi_5d_peak = rsi.iloc[-6:].max()
    rolling_over = rsi_now < rsi_5d_peak * 0.97
    fired = rsi_now > 70 and rolling_over
    signals.append((
        "RSI overbought + fading",
        fired,
        f"RSI {rsi_now:.1f}, 5d peak {rsi_5d_peak:.1f}"
    ))

    # 2. Bearish divergence (price near 20d high, RSI making lower high)
    recent_20_close = close.tail(20)
    recent_20_rsi = rsi.tail(20)
    price_near_high = current >= recent_20_close.max() * 0.99
    rsi_lower_high = rsi_now < recent_20_rsi.max() * 0.95
    fired = price_near_high and rsi_lower_high
    signals.append((
        "Bearish divergence",
        fired,
        f"Price near 20d high, RSI {rsi_now:.1f} vs 20d RSI peak {recent_20_rsi.max():.1f}"
    ))

    # 3. MACD crosses below signal line
    macd_prev = macd_line.iloc[-2]
    sig_prev = signal_line.iloc[-2]
    macd_now = macd_line.iloc[-1]
    sig_now = signal_line.iloc[-1]
    fired = macd_prev >= sig_prev and macd_now < sig_now
    signals.append((
        "MACD bearish crossover",
        fired,
        f"MACD {macd_now:.2f} crossed below signal {sig_now:.2f}"
    ))

    # 4. MACD histogram contracting 3+ consecutive bars
    h = macd_hist.tail(5)
    contracting_count = 0
    for i in range(len(h) - 1, 0, -1):
        if abs(h.iloc[i]) < abs(h.iloc[i - 1]):
            contracting_count += 1
        else:
            break
    fired = contracting_count >= 3
    signals.append((
        "MACD histogram contracting",
        fired,
        f"{contracting_count} consecutive contracting bars"
    ))

    # 5. Heavy distribution day (RVOL >1.5x + red candle)
    red_candle = close.iloc[-1] < close.iloc[-2]
    fired = rvol > 1.5 and red_candle
    signals.append((
        "Heavy distribution day",
        fired,
        f"RVOL {rvol:.2f}x, change {((current - close.iloc[-2]) / close.iloc[-2] * 100):.2f}%"
    ))

    # 6. Price closes below 10 MA
    fired = current < ma10
    signals.append((
        "Below 10 MA",
        fired,
        f"Price ${current:.2f} vs 10 MA ${ma10:.2f}"
    ))

    # 7. Price closes below 21 EMA
    fired = current < ema21
    signals.append((
        "Below 21 EMA",
        fired,
        f"Price ${current:.2f} vs 21 EMA ${ema21:.2f}"
    ))

    # 8. Close in lower 20% of day's range
    day_range = high.iloc[-1] - low.iloc[-1]
    if day_range > 0:
        close_position = (current - low.iloc[-1]) / day_range * 100
    else:
        close_position = 50.0
    fired = close_position < 20
    signals.append((
        "Weak close (lower 20%)",
        fired,
        f"Close position {close_position:.1f}% of day's range"
    ))

    # 9. BB upper band rejection (hit upper band within 5 days, now reversing)
    bb_upper_recent = bb_upper.tail(5)
    high_recent = high.tail(5)
    touched_upper = (high_recent >= bb_upper_recent * 0.99).any()
    reversing = current < bb_upper.iloc[-1] and current < close.iloc[-2]
    fired = touched_upper and reversing
    signals.append((
        "Bollinger Band rejection",
        fired,
        f"Upper BB ${bb_upper.iloc[-1]:.2f}, price ${current:.2f}"
    ))

    # 10. Overextended >15% above 50 MA
    ext_pct = ((current - ma50) / ma50) * 100
    fired = ext_pct > 15
    signals.append((
        "Overextended from 50 MA",
        fired,
        f"{ext_pct:+.1f}% from 50 MA (${ma50:.2f})"
    ))

    return signals


# ---------------------------------------------------------------------------
# Buy signals (10)
# ---------------------------------------------------------------------------

def check_buy_signals(hist: pd.DataFrame) -> list[tuple[str, bool, str]]:
    """Run 10 buy signals against a stock's OHLCV history.

    Parameters
    ----------
    hist : DataFrame with columns Open, High, Low, Close, Volume (≥50 rows).

    Returns
    -------
    List of (signal_name, fired, detail) tuples.
    """
    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    volume = hist["Volume"]
    current = close.iloc[-1]

    # Pre-compute indicators
    rsi = compute_rsi(close, 14)
    rsi_now = rsi.iloc[-1]
    macd_line, signal_line, macd_hist = compute_macd(close)
    bb_upper, bb_mid, bb_lower = compute_bollinger(close)

    ma10 = close.rolling(10).mean().iloc[-1]
    ma10_prev = close.rolling(10).mean().iloc[-2]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    ema21_prev = close.ewm(span=21).mean().iloc[-2]
    ma50 = close.rolling(50).mean().iloc[-1]

    vol_50avg = volume.rolling(50).mean().iloc[-1]
    rvol = volume.iloc[-1] / vol_50avg if vol_50avg > 0 else 0

    signals = []

    # 1. RSI <40 + turning up (rising from 5-day trough)
    rsi_5d_trough = rsi.iloc[-6:].min()
    turning_up = rsi_now > rsi_5d_trough * 1.03
    fired = rsi_now < 40 and turning_up
    signals.append((
        "RSI oversold + turning up",
        fired,
        f"RSI {rsi_now:.1f}, 5d trough {rsi_5d_trough:.1f}"
    ))

    # 2. Bullish divergence (price near 20d low, RSI making higher low)
    recent_20_close = close.tail(20)
    recent_20_rsi = rsi.tail(20)
    price_near_low = current <= recent_20_close.min() * 1.01
    rsi_higher_low = rsi_now > recent_20_rsi.min() * 1.05
    fired = price_near_low and rsi_higher_low
    signals.append((
        "Bullish divergence",
        fired,
        f"Price near 20d low, RSI {rsi_now:.1f} vs 20d RSI trough {recent_20_rsi.min():.1f}"
    ))

    # 3. MACD crosses above signal line
    macd_prev = macd_line.iloc[-2]
    sig_prev = signal_line.iloc[-2]
    macd_now = macd_line.iloc[-1]
    sig_now = signal_line.iloc[-1]
    fired = macd_prev <= sig_prev and macd_now > sig_now
    signals.append((
        "MACD bullish crossover",
        fired,
        f"MACD {macd_now:.2f} crossed above signal {sig_now:.2f}"
    ))

    # 4. MACD histogram expanding bullish 3+ consecutive bars
    h = macd_hist.tail(5)
    expanding_count = 0
    for i in range(len(h) - 1, 0, -1):
        if h.iloc[i] > h.iloc[i - 1] and h.iloc[i] > 0:
            expanding_count += 1
        else:
            break
    fired = expanding_count >= 3
    signals.append((
        "MACD histogram expanding",
        fired,
        f"{expanding_count} consecutive expanding bullish bars"
    ))

    # 5. Heavy accumulation day (RVOL >1.5x + green candle)
    green_candle = close.iloc[-1] > close.iloc[-2]
    fired = rvol > 1.5 and green_candle
    signals.append((
        "Heavy accumulation day",
        fired,
        f"RVOL {rvol:.2f}x, change {((current - close.iloc[-2]) / close.iloc[-2] * 100):+.2f}%"
    ))

    # 6. Price reclaims 10 MA from below
    prev_below_10ma = close.iloc[-2] < ma10_prev
    now_above_10ma = current > ma10
    fired = prev_below_10ma and now_above_10ma
    signals.append((
        "Reclaimed 10 MA",
        fired,
        f"Price ${current:.2f} crossed above 10 MA ${ma10:.2f}"
    ))

    # 7. Price reclaims 21 EMA from below
    prev_below_21ema = close.iloc[-2] < ema21_prev
    now_above_21ema = current > ema21
    fired = prev_below_21ema and now_above_21ema
    signals.append((
        "Reclaimed 21 EMA",
        fired,
        f"Price ${current:.2f} crossed above 21 EMA ${ema21:.2f}"
    ))

    # 8. Close in upper 80% of day's range (strong close)
    day_range = high.iloc[-1] - low.iloc[-1]
    if day_range > 0:
        close_position = (current - low.iloc[-1]) / day_range * 100
    else:
        close_position = 50.0
    fired = close_position >= 80
    signals.append((
        "Strong close (upper 80%)",
        fired,
        f"Close position {close_position:.1f}% of day's range"
    ))

    # 9. BB lower band bounce (hit lower band within 5 days, now reversing up)
    bb_lower_recent = bb_lower.tail(5)
    low_recent = low.tail(5)
    touched_lower = (low_recent <= bb_lower_recent * 1.01).any()
    bouncing = current > bb_lower.iloc[-1] and current > close.iloc[-2]
    fired = touched_lower and bouncing
    signals.append((
        "Bollinger Band bounce",
        fired,
        f"Lower BB ${bb_lower.iloc[-1]:.2f}, price ${current:.2f}"
    ))

    # 10. Pullback within 3% of 50 MA (support test)
    dist_from_50ma = abs((current - ma50) / ma50) * 100
    near_50ma = dist_from_50ma <= 3
    above_or_at = current >= ma50 * 0.97
    fired = near_50ma and above_or_at
    signals.append((
        "Pullback to 50 MA support",
        fired,
        f"Price ${current:.2f} is {dist_from_50ma:.1f}% from 50 MA (${ma50:.2f})"
    ))

    return signals
