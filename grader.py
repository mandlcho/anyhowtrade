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
