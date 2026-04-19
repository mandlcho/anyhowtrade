import pytest
from grader import detect_sell_signals, compute_confluence_score, grade_minervini, compute_health, compute_synergy


def make_stock_data(**overrides):
    """Build a stock data dict with sensible defaults, override as needed."""
    base = {
        "ticker": "TEST",
        "current_price": 100.0,
        "avg_cost": 90.0,
        "shares": 100,
        "momentum": {
            "rsi_14": 55.0,
            "bearish_divergence": False,
            "macd_line": 1.0,
            "macd_signal": 0.8,
            "macd_histogram": 0.2,
            "macd_hist_direction": "expanding",
        },
        "volume": {
            "rvol": 1.0,
            "volume_climax": False,
            "vol_5d_vs_50d": 1.0,
        },
        "moving_averages": {
            "ma50": 95.0,
            "ma150": 90.0,
            "ma200": 85.0,
            "extension_from_50ma_pct": 5.0,
            "price_above_50ma": True,
            "price_above_200ma": True,
        },
        "range_52w": {
            "pct_from_52w_high": -5.0,
            "pct_from_52w_low": 30.0,
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            base[k].update(v)
        else:
            base[k] = v
    return base


class TestDetectSellSignals:
    def test_no_signals_healthy_stock(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        assert len(signals) == 0

    def test_bearish_divergence_detected(self):
        data = make_stock_data(momentum={"bearish_divergence": True, "rsi_14": 65.0})
        signals = detect_sell_signals(data)
        types = [s["type"] for s in signals]
        assert "bearish_divergence" in types

    def test_volume_climax_detected(self):
        data = make_stock_data(volume={"volume_climax": True, "rvol": 3.5})
        signals = detect_sell_signals(data)
        types = [s["type"] for s in signals]
        assert "volume_climax" in types

    def test_below_ma50_detected(self):
        data = make_stock_data(
            current_price=90.0,
            moving_averages={"ma50": 95.0, "price_above_50ma": False},
        )
        signals = detect_sell_signals(data)
        types = [s["type"] for s in signals]
        assert "below_ma50" in types

    def test_rsi_oversold_detected(self):
        data = make_stock_data(momentum={"rsi_14": 25.0})
        signals = detect_sell_signals(data)
        types = [s["type"] for s in signals]
        assert "rsi_oversold" in types

    def test_extended_below_cost_detected(self):
        data = make_stock_data(
            current_price=60.0,
            avg_cost=100.0,
            moving_averages={"extension_from_50ma_pct": -25.0},
        )
        signals = detect_sell_signals(data)
        types = [s["type"] for s in signals]
        assert "extended_below_ma50" in types

    def test_severity_levels(self):
        data = make_stock_data(
            momentum={"bearish_divergence": True, "rsi_14": 25.0},
            volume={"volume_climax": True, "rvol": 3.0},
        )
        signals = detect_sell_signals(data)
        severities = {s["type"]: s["severity"] for s in signals}
        assert severities["volume_climax"] == "critical"
        assert severities["bearish_divergence"] == "critical"


class TestConfluenceScore:
    def test_no_signals_zero_score(self):
        assert compute_confluence_score([]) == (0, "C")

    def test_single_signal_low_tier(self):
        signals = [{"type": "below_ma50", "domain": "trend"}]
        score, tier = compute_confluence_score(signals)
        assert score > 0
        assert tier == "C"

    def test_multi_domain_higher_score(self):
        signals_same = [
            {"type": "below_ma50", "domain": "trend"},
            {"type": "extended_below_ma50", "domain": "trend"},
        ]
        signals_diff = [
            {"type": "below_ma50", "domain": "trend"},
            {"type": "volume_climax", "domain": "volume"},
        ]
        score_same, _ = compute_confluence_score(signals_same)
        score_diff, _ = compute_confluence_score(signals_diff)
        assert score_diff > score_same


class TestMinervini:
    def test_passes_all_criteria(self):
        data = make_stock_data(
            current_price=100.0,
            moving_averages={
                "ma50": 95.0, "ma150": 90.0, "ma200": 85.0,
                "price_above_50ma": True, "price_above_200ma": True,
            },
            range_52w={"pct_from_52w_high": -10.0, "pct_from_52w_low": 40.0},
        )
        result = grade_minervini(data)
        assert result["passes"]
        assert result["criteria_met"] == 8

    def test_fails_below_50ma(self):
        data = make_stock_data(
            current_price=90.0,
            moving_averages={
                "ma50": 95.0, "ma150": 90.0, "ma200": 85.0,
                "price_above_50ma": False, "price_above_200ma": True,
            },
        )
        result = grade_minervini(data)
        assert not result["passes"]
        assert result["criteria_met"] < 8


class TestComputeHealth:
    def test_healthy_stock_gets_hold(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        health = compute_health(data, signals)
        assert health["action"] == "HOLD"
        assert health["health_score"] >= 70
        assert health["health_grade"] in ("A", "B")
        assert "let it ride" in health["verdict"] or "Sit tight" in health["verdict"]

    def test_critical_signals_get_sell(self):
        data = make_stock_data(
            current_price=40.0,
            avg_cost=100.0,
            unrealized_pnl_pct=-60.0,
            momentum={"bearish_divergence": True, "rsi_14": 22.0},
            volume={"volume_climax": True, "rvol": 3.5},
            moving_averages={"price_above_50ma": False, "price_above_200ma": False, "extension_from_50ma_pct": -30.0},
        )
        signals = detect_sell_signals(data)
        health = compute_health(data, signals)
        assert health["action"] == "SELL"
        assert health["health_score"] < 30
        assert health["health_grade"] in ("D", "F")

    def test_warning_signals_get_watch(self):
        data = make_stock_data(
            momentum={"bearish_divergence": True, "rsi_14": 45.0},
            moving_averages={"price_above_50ma": True, "price_above_200ma": True},
        )
        signals = detect_sell_signals(data)
        health = compute_health(data, signals)
        assert health["action"] in ("WATCH", "HOLD")

    def test_verdict_contains_ticker(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        health = compute_health(data, signals)
        assert "TEST" in health["verdict"]

    def test_all_fields_present(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        health = compute_health(data, signals)
        assert "health_score" in health
        assert "health_grade" in health
        assert "action" in health
        assert "verdict" in health


class TestComputeSynergy:
    def test_healthy_stock_has_buy_criteria(self):
        data = make_stock_data(
            current_price=100.0,
            unrealized_pnl_pct=15.0,
            moving_averages={
                "ma50": 95.0, "ma150": 90.0, "ma200": 85.0,
                "price_above_50ma": True, "price_above_200ma": True,
                "extension_from_50ma_pct": 5.0,
            },
            momentum={
                "rsi_14": 50.0, "bearish_divergence": False,
                "macd_line": 2.0, "macd_signal": 1.0,
                "macd_histogram": 1.0, "macd_hist_direction": "expanding",
            },
            range_52w={"pct_from_52w_high": -5.0, "pct_from_52w_low": 60.0},
        )
        signals = detect_sell_signals(data)
        minervini = grade_minervini(data)
        synergy = compute_synergy(data, signals, minervini)
        assert synergy["buy_count"] >= 5
        assert synergy["buy_synergy"] is True
        assert synergy["sell_synergy"] is False

    def test_broken_stock_has_sell_synergy(self):
        data = make_stock_data(
            current_price=40.0,
            avg_cost=100.0,
            unrealized_pnl_pct=-60.0,
            moving_averages={
                "ma50": 60.0, "ma150": 70.0, "ma200": 80.0,
                "price_above_50ma": False, "price_above_200ma": False,
                "extension_from_50ma_pct": -33.0,
            },
            momentum={
                "rsi_14": 22.0, "bearish_divergence": True,
                "macd_line": -3.0, "macd_signal": -1.0,
                "macd_histogram": -2.0, "macd_hist_direction": "expanding",
            },
            volume={"rvol": 3.0, "volume_climax": True, "vol_5d_vs_50d": 1.5},
            price_action={
                "change_1d_pct": -5.0, "change_5d_pct": -15.0,
                "close_position_in_range_pct": 10.0,
            },
            range_52w={"pct_from_52w_high": -55.0, "pct_from_52w_low": 5.0},
            volatility={"bb_position_pct": 2.0},
        )
        signals = detect_sell_signals(data)
        synergy = compute_synergy(data, signals)
        assert synergy["sell_count"] >= 5
        assert synergy["sell_synergy"] is True

    def test_neutral_stock_no_synergy(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        synergy = compute_synergy(data, signals)
        assert synergy["sell_synergy"] is False
        # Might or might not have buy synergy depending on defaults

    def test_returns_criteria_lists(self):
        data = make_stock_data()
        signals = detect_sell_signals(data)
        synergy = compute_synergy(data, signals)
        assert isinstance(synergy["sell_criteria"], list)
        assert isinstance(synergy["buy_criteria"], list)
        assert isinstance(synergy["sell_count"], int)
        assert isinstance(synergy["buy_count"], int)
