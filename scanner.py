"""Scanner engine — orchestrates data fetching via Moomoo OpenD, indicator
computation, signal detection, grading, and full scan result assembly."""

import uuid
from datetime import datetime, timezone, timedelta

import pandas as pd
from moomoo import (
    OpenQuoteContext, RET_OK, KLType, AuType, KL_FIELD,
    SubType, Market,
)

from indicators import compute_rsi, compute_macd, compute_bollinger
from grader import detect_sell_signals, compute_confluence_score, grade_minervini, compute_health


# ---------------------------------------------------------------------------
# OpenD connection settings
# ---------------------------------------------------------------------------

OPEND_HOST = "127.0.0.1"
OPEND_PORT = 11111


def _moomoo_code(ticker):
    """Convert plain ticker to moomoo format: AAPL -> US.AAPL"""
    if "." in ticker:
        return ticker  # already formatted
    return f"US.{ticker.upper()}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _noop(level, msg):
    pass


def _make_logger(log_callback):
    return log_callback if callable(log_callback) else _noop


def _round(val, n=2):
    if val is None:
        return None
    try:
        return round(float(val), n)
    except (TypeError, ValueError):
        return None


def _get_quote_ctx():
    """Create and return a moomoo OpenQuoteContext."""
    return OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)


def _fetch_history(quote_ctx, ticker, days=365):
    """Fetch historical daily K-line data from OpenD.

    Returns a pandas DataFrame with columns: Open, High, Low, Close, Volume
    indexed by date. Returns empty DataFrame on failure.
    """
    code = _moomoo_code(ticker)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    ret, data, _ = quote_ctx.request_history_kline(
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

    # Normalize column names to match our indicator functions
    df = pd.DataFrame({
        "Open": data["open"].values,
        "High": data["high"].values,
        "Low": data["low"].values,
        "Close": data["close"].values,
        "Volume": data["volume"].values,
    }, index=pd.to_datetime(data["time_key"]))

    return df


def _fetch_snapshot(quote_ctx, tickers):
    """Fetch real-time market snapshot for a list of tickers.

    Returns a dict keyed by plain ticker with snapshot data.
    """
    codes = [_moomoo_code(t) for t in tickers]
    ret, data = quote_ctx.get_market_snapshot(codes)

    if ret != RET_OK or data is None or data.empty:
        return {}

    result = {}
    for _, row in data.iterrows():
        # Extract plain ticker from "US.AAPL" format
        code = row.get("code", "")
        plain_ticker = code.split(".")[-1] if "." in code else code
        result[plain_ticker] = row.to_dict()

    return result


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_stock(position, log_callback=None, quote_ctx=None):
    """Fetch 1y of OHLCV for a position and compute all indicators + signals.

    Parameters
    ----------
    position : dict
        Must contain: ticker, shares, avg_cost. Optional: tag.
    log_callback : callable or None
        Called as log_callback(level, msg) for diagnostic output.
    quote_ctx : OpenQuoteContext or None
        Reuse an existing context. If None, creates and closes its own.

    Returns
    -------
    dict
        Full scan result for the position, or a dict with "error" key on
        failure.
    """
    log = _make_logger(log_callback)
    ticker = position["ticker"]
    own_ctx = quote_ctx is None

    try:
        if own_ctx:
            quote_ctx = _get_quote_ctx()

        log("info", f"Fetching {ticker} via OpenD")
        hist = _fetch_history(quote_ctx, ticker)

        if hist.empty or len(hist) < 50:
            log("warn", f"{ticker}: insufficient data ({len(hist)} rows)")
            return {"ticker": ticker, "error": "Insufficient data"}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current_price = close.iloc[-1]
        prev_close = close.iloc[-2]

        # ------------------------------------------------------------------ #
        # Moving averages
        # ------------------------------------------------------------------ #
        ma10 = close.rolling(10).mean().iloc[-1]
        ema21 = close.ewm(span=21).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma150 = close.rolling(150).mean().iloc[-1] if len(close) >= 150 else None
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        ext_from_50ma = ((current_price - ma50) / ma50) * 100 if ma50 else None
        ext_from_200ma = ((current_price - ma200) / ma200) * 100 if ma200 else None

        # ------------------------------------------------------------------ #
        # Momentum — RSI, MACD
        # ------------------------------------------------------------------ #
        rsi_series = compute_rsi(close, 14)
        rsi_14 = rsi_series.iloc[-1]
        rsi_5_ago = rsi_series.iloc[-6] if len(close) > 6 else None

        macd_line, signal_line, macd_hist = compute_macd(close)
        macd_current = macd_line.iloc[-1]
        macd_signal_val = signal_line.iloc[-1]
        macd_hist_current = macd_hist.iloc[-1]
        macd_hist_prev = macd_hist.iloc[-2]
        macd_hist_direction = (
            "expanding" if abs(macd_hist_current) > abs(macd_hist_prev) else "contracting"
        )

        # Bearish divergence: price near 20-day high but RSI below its recent peak
        recent_20_close = close.tail(20)
        recent_20_rsi = rsi_series.tail(20)
        price_making_new_highs = current_price >= recent_20_close.max() * 0.99
        rsi_below_recent_peak = rsi_14 < recent_20_rsi.max() * 0.95
        bearish_divergence = bool(price_making_new_highs and rsi_below_recent_peak)

        # ------------------------------------------------------------------ #
        # Bollinger Bands
        # ------------------------------------------------------------------ #
        bb_upper, bb_mid, bb_lower = compute_bollinger(close)
        bb_upper_val = bb_upper.iloc[-1]
        bb_lower_val = bb_lower.iloc[-1]
        bb_mid_val = bb_mid.iloc[-1]
        bb_width = ((bb_upper_val - bb_lower_val) / bb_mid_val) * 100 if bb_mid_val else None
        bb_range = bb_upper_val - bb_lower_val
        bb_position = (
            ((current_price - bb_lower_val) / bb_range) * 100 if bb_range else None
        )

        # ------------------------------------------------------------------ #
        # Volume
        # ------------------------------------------------------------------ #
        vol_50avg = volume.rolling(50).mean().iloc[-1]
        vol_today = volume.iloc[-1]
        rvol = vol_today / vol_50avg if vol_50avg > 0 else 0
        vol_5avg = volume.tail(5).mean()
        vol_5d_vs_50d = vol_5avg / vol_50avg if vol_50avg > 0 else 0

        # Volume climax: today's vol is near 10-day max AND RVOL >= 2x
        vol_max_10d = volume.tail(10).max()
        volume_climax = bool(vol_today >= vol_max_10d * 0.95 and rvol >= 2.0)

        # ------------------------------------------------------------------ #
        # 52-week range
        # ------------------------------------------------------------------ #
        high_52w = high.max()
        low_52w = low.min()
        pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100
        pct_from_52w_low = ((current_price - low_52w) / low_52w) * 100

        # ------------------------------------------------------------------ #
        # Price action
        # ------------------------------------------------------------------ #
        change_1d = ((current_price - prev_close) / prev_close) * 100
        change_5d = ((current_price - close.iloc[-6]) / close.iloc[-6]) * 100 if len(close) > 6 else None
        change_20d = ((current_price - close.iloc[-21]) / close.iloc[-21]) * 100 if len(close) > 21 else None
        change_60d = ((current_price - close.iloc[-61]) / close.iloc[-61]) * 100 if len(close) > 61 else None

        # ADR% (14-day average daily range)
        adr_14d = ((high - low) / close * 100).tail(14).mean()

        # Close position within day's range
        day_range = high.iloc[-1] - low.iloc[-1]
        close_position_pct = (
            ((current_price - low.iloc[-1]) / day_range) * 100 if day_range > 0 else 50.0
        )

        # ------------------------------------------------------------------ #
        # P&L
        # ------------------------------------------------------------------ #
        avg_cost = position["avg_cost"]
        shares = position["shares"]
        unrealized_pnl = (current_price - avg_cost) * shares
        unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost) * 100
        position_value = current_price * shares

        # ------------------------------------------------------------------ #
        # Assemble intermediate stock_data dict (used by grader)
        # ------------------------------------------------------------------ #
        stock_data = {
            "ticker": ticker,
            "current_price": _round(current_price),
            "avg_cost": avg_cost,
            "shares": shares,
            "tag": position.get("tag", ""),
            "position_value": _round(position_value),
            "unrealized_pnl": _round(unrealized_pnl),
            "unrealized_pnl_pct": _round(unrealized_pnl_pct),
            "price_action": {
                "change_1d_pct": _round(change_1d),
                "change_5d_pct": _round(change_5d),
                "change_20d_pct": _round(change_20d),
                "change_60d_pct": _round(change_60d),
                "adr_14d_pct": _round(adr_14d),
                "close_position_in_range_pct": _round(close_position_pct, 1),
            },
            "moving_averages": {
                "ma10": _round(ma10),
                "ema21": _round(ema21),
                "ma50": _round(ma50),
                "ma150": _round(ma150),
                "ma200": _round(ma200),
                "extension_from_50ma_pct": _round(ext_from_50ma),
                "extension_from_200ma_pct": _round(ext_from_200ma),
                "price_above_50ma": bool(current_price > ma50) if ma50 else None,
                "price_above_200ma": bool(current_price > ma200) if ma200 else None,
            },
            "momentum": {
                "rsi_14": _round(rsi_14),
                "rsi_5_days_ago": _round(rsi_5_ago),
                "macd_line": _round(macd_current, 3),
                "macd_signal": _round(macd_signal_val, 3),
                "macd_histogram": _round(macd_hist_current, 3),
                "macd_hist_direction": macd_hist_direction,
                "bearish_divergence": bearish_divergence,
            },
            "volatility": {
                "bb_upper": _round(bb_upper_val),
                "bb_lower": _round(bb_lower_val),
                "bb_width_pct": _round(bb_width),
                "bb_position_pct": _round(bb_position, 1),
            },
            "volume": {
                "today_volume": int(vol_today),
                "avg_50d_volume": int(vol_50avg),
                "rvol": _round(rvol),
                "vol_5d_vs_50d": _round(vol_5d_vs_50d),
                "volume_climax": volume_climax,
            },
            "range_52w": {
                "high_52w": _round(high_52w),
                "low_52w": _round(low_52w),
                "pct_from_52w_high": _round(pct_from_52w_high),
                "pct_from_52w_low": _round(pct_from_52w_low),
            },
        }

        # ------------------------------------------------------------------ #
        # Grading & signals
        # ------------------------------------------------------------------ #
        active_signals = detect_sell_signals(stock_data)
        confluence_score, confluence_tier = compute_confluence_score(active_signals)
        minervini = grade_minervini(stock_data)

        health = compute_health(stock_data, active_signals)

        stock_data["active_signals"] = active_signals
        stock_data["confluence_score"] = confluence_score
        stock_data["confluence_tier"] = confluence_tier
        stock_data["health_score"] = health["health_score"]
        stock_data["health_grade"] = health["health_grade"]
        stock_data["action"] = health["action"]
        stock_data["verdict"] = health["verdict"]
        stock_data["scanner_grades"] = {
            "minervini": minervini,
        }

        log("info", f"{ticker}: price={_round(current_price)}, RSI={_round(rsi_14)}, signals={len(active_signals)}")
        return stock_data

    except Exception as exc:
        log("error", f"{ticker}: {exc}")
        return {"ticker": ticker, "error": str(exc)}
    finally:
        if own_ctx and quote_ctx is not None:
            quote_ctx.close()


# ---------------------------------------------------------------------------
# Market internals
# ---------------------------------------------------------------------------

def get_market_internals(log_callback=None, quote_ctx=None):
    """Fetch price and daily change for major market indices via OpenD snapshot.

    Returns
    -------
    dict with keys: sp500, nasdaq, vix, yield_10y
    """
    log = _make_logger(log_callback)
    own_ctx = quote_ctx is None

    # Moomoo uses ETF proxies for indices since direct index quotes
    # may not be available. SPY/QQQ are close proxies.
    symbols = {
        "sp500": "US.SPY",
        "nasdaq": "US.QQQ",
        "vix": "US.UVXY",   # VIX proxy ETF
    }

    result = {}
    try:
        if own_ctx:
            quote_ctx = _get_quote_ctx()

        codes = list(symbols.values())
        ret, data = quote_ctx.get_market_snapshot(codes)

        if ret != RET_OK or data is None or data.empty:
            log("error", "Failed to fetch market internals snapshot")
            for key in symbols:
                result[key] = {"price": None, "change_pct": None, "error": "Snapshot failed"}
            return result

        for _, row in data.iterrows():
            code = row.get("code", "")
            # Find which key this code maps to
            for key, moo_code in symbols.items():
                if code == moo_code:
                    price = _round(row.get("last_price"))
                    prev_close = row.get("prev_close_price")
                    change_pct = None
                    if price and prev_close and prev_close > 0:
                        change_pct = _round(((price - prev_close) / prev_close) * 100)
                    result[key] = {"price": price, "change_pct": change_pct}
                    break

        # Fill any missing keys
        for key in symbols:
            if key not in result:
                result[key] = {"price": None, "change_pct": None}

    except Exception as exc:
        log("error", f"Market internals error: {exc}")
        for key in symbols:
            result[key] = {"price": None, "change_pct": None, "error": str(exc)}
    finally:
        if own_ctx and quote_ctx is not None:
            quote_ctx.close()

    return result


# ---------------------------------------------------------------------------
# Watchlist scanner
# ---------------------------------------------------------------------------

def scan_watchlist(tickers, log_callback=None, quote_ctx=None):
    """Scan tickers for undervalued / oversold setups.

    Criteria (must match >= 2):
    - Price >15% below 52-week high
    - RSI < 40
    - Price near or below 200-day MA (within 2%)

    Returns
    -------
    list of dicts with ticker and matched criteria
    """
    log = _make_logger(log_callback)
    own_ctx = quote_ctx is None
    hits = []

    try:
        if own_ctx:
            quote_ctx = _get_quote_ctx()

        for sym in tickers:
            try:
                log("debug", f"Watchlist scan: {sym}")
                hist = _fetch_history(quote_ctx, sym)

                if hist.empty or len(hist) < 50:
                    continue

                close = hist["Close"]
                high = hist["High"]
                current_price = float(close.iloc[-1])

                high_52w = float(high.max())
                pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100

                rsi_14 = float(compute_rsi(close, 14).iloc[-1])

                ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
                near_below_200ma = (
                    (current_price <= ma200 * 1.02) if ma200 else False
                )

                criteria_matched = []
                if pct_from_52w_high <= -15:
                    criteria_matched.append("price_below_52w_high_15pct")
                if rsi_14 < 40:
                    criteria_matched.append("rsi_below_40")
                if near_below_200ma:
                    criteria_matched.append("near_below_200ma")

                if len(criteria_matched) >= 2:
                    hits.append({
                        "ticker": sym,
                        "current_price": _round(current_price),
                        "pct_from_52w_high": _round(pct_from_52w_high),
                        "rsi_14": _round(rsi_14),
                        "ma200": _round(ma200),
                        "criteria_matched": criteria_matched,
                    })
            except Exception as exc:
                log("error", f"Watchlist {sym}: {exc}")
    finally:
        if own_ctx and quote_ctx is not None:
            quote_ctx.close()

    return hits


# ---------------------------------------------------------------------------
# Market status helper
# ---------------------------------------------------------------------------

def _market_status():
    """Return current US equity market status based on Eastern Time."""
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
    except ImportError:
        from datetime import timedelta as td
        et = timezone(td(hours=-4))

    now_et = datetime.now(et)
    weekday = now_et.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:
        return "closed"

    hour = now_et.hour
    minute = now_et.minute
    time_val = hour * 60 + minute

    pre_open = 4 * 60        # 04:00 ET
    open_ = 9 * 60 + 30      # 09:30 ET
    close_ = 16 * 60         # 16:00 ET
    after_close = 20 * 60    # 20:00 ET

    if time_val < pre_open or time_val >= after_close:
        return "closed"
    elif time_val < open_:
        return "pre"
    elif time_val < close_:
        return "open"
    else:
        return "post"


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_scan(positions, watchlist_tickers=None, log_callback=None):
    """Run a full portfolio scan.

    Parameters
    ----------
    positions : list of dicts
        Each dict must have: ticker, shares, avg_cost. Optional: tag.
    watchlist_tickers : list of str or None
        Additional tickers to scan for setups.
    log_callback : callable or None
        Optional logging hook called as log_callback(level, message).

    Returns
    -------
    dict
        Full scan result: scan_id, timestamp, market_status, portfolio,
        alerts, watchlist, market_internals.
    """
    log = _make_logger(log_callback)
    scan_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    market_status = _market_status()

    log("info", f"Starting scan {scan_id} — {len(positions)} positions")

    # Open a single quote context for the entire scan
    quote_ctx = _get_quote_ctx()

    try:
        # Analyze each portfolio position
        portfolio = []
        alerts = []
        for pos in positions:
            result = analyze_stock(pos, log_callback=log_callback, quote_ctx=quote_ctx)
            portfolio.append(result)

            # Collect alerts from active signals
            if "active_signals" in result:
                for sig in result["active_signals"]:
                    if sig.get("severity") in ("critical", "warning"):
                        alerts.append({
                            "ticker": result["ticker"],
                            "signal": sig["type"],
                            "severity": sig["severity"],
                            "message": sig["message"],
                        })

        # Market internals
        log("info", "Fetching market internals")
        market_internals = get_market_internals(log_callback=log_callback, quote_ctx=quote_ctx)

        # Watchlist scan
        watchlist = []
        if watchlist_tickers:
            log("info", f"Scanning watchlist: {len(watchlist_tickers)} tickers")
            watchlist = scan_watchlist(watchlist_tickers, log_callback=log_callback, quote_ctx=quote_ctx)

    finally:
        quote_ctx.close()

    log("info", f"Scan complete — {len(alerts)} alerts, {len(watchlist)} watchlist hits")

    return {
        "scan_id": scan_id,
        "timestamp": timestamp,
        "market_status": market_status,
        "portfolio": portfolio,
        "alerts": alerts,
        "watchlist": watchlist,
        "market_internals": market_internals,
    }
