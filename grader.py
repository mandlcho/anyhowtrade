"""Sell signal detection and pattern grading for OpenScan."""

import math

SIGNAL_DOMAINS = {
    "bearish_divergence": "momentum",
    "volume_climax": "volume",
    "below_ma50": "trend",
    "below_ma200": "trend",
    "rsi_oversold": "momentum",
    "rsi_overbought": "momentum",
    "extended_below_ma50": "trend",
    "macd_bearish_cross": "momentum",
    "high_distribution_volume": "volume",
}

RARITY_MULTIPLIERS = {
    "volume_climax": 0.3,
}

DOMAIN_POINTS = [15, 12, 9, 6, 3]


def detect_sell_signals(stock_data):
    signals = []
    momentum = stock_data.get("momentum", {})
    volume = stock_data.get("volume", {})
    ma = stock_data.get("moving_averages", {})

    if momentum.get("bearish_divergence"):
        signals.append({
            "type": "bearish_divergence",
            "domain": "momentum",
            "severity": "critical",
            "message": f"Bearish divergence — price near highs but RSI declining (RSI {momentum.get('rsi_14', '?')})",
        })

    if volume.get("volume_climax"):
        signals.append({
            "type": "volume_climax",
            "domain": "volume",
            "severity": "critical",
            "message": f"Volume climax detected — RVOL {volume.get('rvol', '?')}x. Distribution signal.",
        })

    if not ma.get("price_above_50ma", True):
        signals.append({
            "type": "below_ma50",
            "domain": "trend",
            "severity": "warning",
            "message": "Trading below 50-day MA. Trend structure weakening.",
        })

    if ma.get("price_above_200ma") is False:
        signals.append({
            "type": "below_ma200",
            "domain": "trend",
            "severity": "warning",
            "message": "Trading below 200-day MA. Long-term trend broken.",
        })

    rsi = momentum.get("rsi_14", 50)
    if rsi < 30:
        signals.append({
            "type": "rsi_oversold",
            "domain": "momentum",
            "severity": "warning",
            "message": f"RSI oversold at {rsi}. May indicate capitulation or further downside.",
        })

    if rsi > 80:
        signals.append({
            "type": "rsi_overbought",
            "domain": "momentum",
            "severity": "info",
            "message": f"RSI overbought at {rsi}. Watch for reversal.",
        })

    ext = ma.get("extension_from_50ma_pct", 0)
    if ext < -20:
        signals.append({
            "type": "extended_below_ma50",
            "domain": "trend",
            "severity": "critical",
            "message": f"Extended {ext:.1f}% below 50-day MA. Severe trend damage.",
        })

    macd_line = momentum.get("macd_line", 0)
    macd_signal = momentum.get("macd_signal", 0)
    macd_hist = momentum.get("macd_histogram", 0)
    if macd_line < macd_signal and momentum.get("macd_hist_direction") == "contracting":
        if macd_hist < 0:
            signals.append({
                "type": "macd_bearish_cross",
                "domain": "momentum",
                "severity": "info",
                "message": "MACD bearish crossover with contracting histogram.",
            })

    return signals


def compute_confluence_score(signals):
    if not signals:
        return 0, "C"

    domain_counts = {}
    for s in signals:
        domain = s.get("domain", "other")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    raw = 0
    for domain, count in domain_counts.items():
        for i in range(count):
            points = DOMAIN_POINTS[min(i, len(DOMAIN_POINTS) - 1)]
            raw += points

    for s in signals:
        mult = RARITY_MULTIPLIERS.get(s["type"])
        if mult:
            raw *= (1 + mult)

    score = min(100, int(math.sqrt(raw) * 10))

    if score >= 90:
        tier = "S"
    elif score >= 80:
        tier = "A"
    elif score >= 70:
        tier = "B"
    else:
        tier = "C"

    return score, tier


def compute_health(stock_data, signals):
    """Compute a health score (0-100) and action label for a position.

    Returns dict with:
        health_score: 0-100 (100 = perfect health)
        health_grade: A/B/C/D/F
        action: "SELL" | "WATCH" | "HOLD" | "ADD"
        verdict: one-line plain English summary
    """
    score = 100
    reasons_bad = []
    reasons_good = []

    # --- Penalty: active signals ---
    for s in signals:
        if s["severity"] == "critical":
            score -= 25
            reasons_bad.append(s["type"].replace("_", " "))
        elif s["severity"] == "warning":
            score -= 15
            reasons_bad.append(s["type"].replace("_", " "))
        elif s["severity"] == "info":
            score -= 5

    # --- Penalty: P&L ---
    pnl_pct = stock_data.get("unrealized_pnl_pct", 0) or 0
    if pnl_pct < -40:
        score -= 20
        reasons_bad.append(f"down {pnl_pct:.0f}%")
    elif pnl_pct < -20:
        score -= 10
        reasons_bad.append(f"down {pnl_pct:.0f}%")
    elif pnl_pct < -10:
        score -= 5

    # --- Penalty: trend ---
    ma = stock_data.get("moving_averages", {})
    if ma.get("price_above_50ma") is False and ma.get("price_above_200ma") is False:
        score -= 15
        reasons_bad.append("below all MAs")
    elif ma.get("price_above_50ma") is False:
        score -= 8

    # --- Bonus: strength ---
    momentum = stock_data.get("momentum", {})
    rsi = momentum.get("rsi_14", 50) or 50

    if ma.get("price_above_50ma") and ma.get("price_above_200ma"):
        score += 5
        reasons_good.append("above all MAs")

    if 40 <= rsi <= 60:
        score += 3
        reasons_good.append("RSI neutral")
    elif rsi < 30:
        reasons_bad.append(f"RSI oversold ({rsi:.0f})")

    if pnl_pct > 15:
        score += 5
        reasons_good.append(f"up {pnl_pct:.0f}%")

    # Clamp
    score = max(0, min(100, score))

    # Grade
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    elif score >= 20:
        grade = "D"
    else:
        grade = "F"

    # Action label
    ticker = stock_data.get("ticker", "?")
    tag = stock_data.get("tag", "")

    if score < 30 or (len([s for s in signals if s["severity"] == "critical"]) >= 2):
        action = "SELL"
    elif score < 50 or len([s for s in signals if s["severity"] == "critical"]) >= 1:
        action = "WATCH"
    elif score >= 80 and rsi < 40 and pnl_pct > -5:
        action = "ADD"
    else:
        action = "HOLD"

    # Override: if user tagged as "sell", reinforce
    if tag == "sell" and action == "HOLD":
        action = "WATCH"

    # Verdict — one plain English sentence
    if action == "SELL":
        if reasons_bad:
            verdict = f"{ticker}: {', '.join(reasons_bad[:2]).capitalize()}. Consider cutting this position."
        else:
            verdict = f"{ticker}: Multiple warning signs. Consider selling."
    elif action == "WATCH":
        if reasons_bad:
            verdict = f"{ticker}: {', '.join(reasons_bad[:2]).capitalize()}. Monitor closely."
        else:
            verdict = f"{ticker}: Some concerns. Keep an eye on it."
    elif action == "ADD":
        verdict = f"{ticker}: Healthy and oversold. Could be a buying opportunity."
    else:
        if reasons_good:
            verdict = f"{ticker}: {', '.join(reasons_good[:2]).capitalize()}. No action needed."
        else:
            verdict = f"{ticker}: Stable. No action needed."

    return {
        "health_score": score,
        "health_grade": grade,
        "action": action,
        "verdict": verdict,
    }


SYNERGY_THRESHOLD = 5


def compute_synergy(stock_data, signals, minervini=None):
    """Check if 5+ criteria align for a sell or buy signal.

    Evaluates a broad set of independent criteria across trend, momentum,
    volume, price action, and position P&L. When 5+ criteria from different
    domains agree, it's a high-conviction synergy signal worth notifying about.

    Returns dict with:
        sell_criteria: list of matched sell criteria names
        buy_criteria: list of matched buy criteria names
        sell_synergy: bool (5+ sell criteria aligned)
        buy_synergy: bool (5+ buy criteria aligned)
        sell_count: int
        buy_count: int
    """
    ma = stock_data.get("moving_averages", {})
    momentum = stock_data.get("momentum", {})
    volume = stock_data.get("volume", {})
    price_action = stock_data.get("price_action", {})
    r52 = stock_data.get("range_52w", {})
    volatility = stock_data.get("volatility", {})
    pnl_pct = stock_data.get("unrealized_pnl_pct", 0) or 0
    rsi = momentum.get("rsi_14", 50) or 50

    # --- SELL CRITERIA (each is an independent reason to be bearish) ---
    sell_criteria = []

    # Trend
    if ma.get("price_above_50ma") is False:
        sell_criteria.append("Below 50-day MA")
    if ma.get("price_above_200ma") is False:
        sell_criteria.append("Below 200-day MA")
    ext = ma.get("extension_from_50ma_pct", 0) or 0
    if ext < -15:
        sell_criteria.append(f"Extended {ext:.0f}% below 50MA")

    # Momentum
    if momentum.get("bearish_divergence"):
        sell_criteria.append("Bearish divergence")
    if rsi < 30:
        sell_criteria.append(f"RSI oversold ({rsi:.0f})")
    macd_line = momentum.get("macd_line", 0) or 0
    macd_signal = momentum.get("macd_signal", 0) or 0
    if macd_line < macd_signal and (momentum.get("macd_histogram", 0) or 0) < 0:
        sell_criteria.append("MACD bearish")

    # Volume
    if volume.get("volume_climax"):
        sell_criteria.append("Volume climax")
    rvol = volume.get("rvol", 1) or 1
    vol_trend = volume.get("vol_5d_vs_50d", 1) or 1
    if rvol >= 2.0 and (price_action.get("change_1d_pct", 0) or 0) < -2:
        sell_criteria.append("Heavy volume on red day")

    # Price action
    close_pos = price_action.get("close_position_in_range_pct", 50) or 50
    if close_pos < 20:
        sell_criteria.append("Closed in bottom 20% of range")
    change_5d = price_action.get("change_5d_pct", 0) or 0
    if change_5d < -10:
        sell_criteria.append(f"Down {change_5d:.0f}% in 5 days")

    # 52-week
    pct_from_high = r52.get("pct_from_52w_high", 0) or 0
    if pct_from_high < -30:
        sell_criteria.append(f"{pct_from_high:.0f}% from 52w high")

    # Volatility
    bb_pos = volatility.get("bb_position_pct", 50) or 50
    if bb_pos < 5:
        sell_criteria.append("At lower Bollinger Band")

    # P&L
    if pnl_pct < -25:
        sell_criteria.append(f"Position down {pnl_pct:.0f}%")

    # --- BUY CRITERIA (each is an independent reason to be bullish) ---
    buy_criteria = []

    # Trend
    if ma.get("price_above_50ma") and ma.get("price_above_200ma"):
        buy_criteria.append("Above all major MAs")
    ma150 = ma.get("ma150", 0) or 0
    ma200 = ma.get("ma200", 0) or 0
    if ma150 and ma200 and ma150 > ma200:
        buy_criteria.append("150MA > 200MA (uptrend)")

    # Momentum
    if 40 <= rsi <= 60:
        buy_criteria.append("RSI neutral zone")
    if macd_line > macd_signal and (momentum.get("macd_histogram", 0) or 0) > 0:
        buy_criteria.append("MACD bullish")
    if momentum.get("macd_hist_direction") == "expanding" and macd_line > 0:
        buy_criteria.append("MACD expanding positive")

    # Volume
    if rvol >= 1.5 and (price_action.get("change_1d_pct", 0) or 0) > 1:
        buy_criteria.append("Strong volume on green day")
    if vol_trend > 1.2:
        buy_criteria.append("Rising volume trend")

    # Price action
    if close_pos > 80:
        buy_criteria.append("Closed in top 20% of range")
    change_20d = price_action.get("change_20d_pct", 0) or 0
    if change_20d > 10:
        buy_criteria.append(f"Up {change_20d:.0f}% in 20 days")

    # 52-week
    if pct_from_high > -10:
        buy_criteria.append("Near 52-week high")
    pct_from_low = r52.get("pct_from_52w_low", 0) or 0
    if pct_from_low > 50:
        buy_criteria.append(f"{pct_from_low:.0f}% above 52w low")

    # Volatility
    if bb_pos > 60:
        buy_criteria.append("Upper Bollinger territory")

    # Minervini
    if minervini and minervini.get("passes"):
        buy_criteria.append("Minervini trend template passes")

    # P&L
    if pnl_pct > 10:
        buy_criteria.append(f"Position up {pnl_pct:.0f}%")

    sell_synergy = len(sell_criteria) >= SYNERGY_THRESHOLD
    buy_synergy = len(buy_criteria) >= SYNERGY_THRESHOLD

    return {
        "sell_criteria": sell_criteria,
        "buy_criteria": buy_criteria,
        "sell_synergy": sell_synergy,
        "buy_synergy": buy_synergy,
        "sell_count": len(sell_criteria),
        "buy_count": len(buy_criteria),
    }


def grade_minervini(stock_data):
    price = stock_data["current_price"]
    ma = stock_data.get("moving_averages", {})
    r52 = stock_data.get("range_52w", {})

    ma50 = ma.get("ma50", 0)
    ma150 = ma.get("ma150", 0)
    ma200 = ma.get("ma200", 0)
    pct_from_high = r52.get("pct_from_52w_high", -100)
    pct_from_low = r52.get("pct_from_52w_low", 0)

    criteria = [
        ("Price > 50-day MA", price > ma50 if ma50 else False),
        ("Price > 150-day MA", price > ma150 if ma150 else False),
        ("Price > 200-day MA", price > ma200 if ma200 else False),
        ("150-day MA > 200-day MA", ma150 > ma200 if ma150 and ma200 else False),
        ("200-day MA trending up", ma200 > 0),
        ("Within 25% of 52-week high", pct_from_high >= -25),
        ("At least 25% above 52-week low", pct_from_low >= 25),
        ("Relative strength upper tier", pct_from_high >= -15),
    ]

    met = sum(1 for _, passed in criteria if passed)
    return {
        "passes": met == 8,
        "criteria_met": met,
        "criteria": [{"name": name, "passed": passed} for name, passed in criteria],
    }
