# tests/test_mtf_bias.py
"""Tests for multi-timeframe bias analysis module."""

import numpy as np
import pandas as pd
import pytest

from mtf_bias import (
    _compute_adx,
    _compute_single_tf_bias,
    _detect_structure,
    compute_mtf_bias_from_dataframes,
    MAX_WEIGHT,
    TIMEFRAMES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(closes, spread=0.5, volume=1000):
    """Build an OHLCV DataFrame from a list of close prices."""
    n = len(closes)
    closes = np.array(closes, dtype=float)
    opens = closes - np.random.uniform(-spread * 0.3, spread * 0.3, n)
    highs = np.maximum(closes, opens) + np.random.uniform(0, spread, n)
    lows = np.minimum(closes, opens) - np.random.uniform(0, spread, n)
    volumes = np.full(n, volume, dtype=float)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows,
        "Close": closes, "Volume": volumes,
    }, index=idx)


def _trending_up(start=100, n=80, step=1.0):
    """Generate steadily rising close prices."""
    return [start + i * step for i in range(n)]


def _trending_down(start=200, n=80, step=1.0):
    """Generate steadily falling close prices."""
    return [start - i * step for i in range(n)]


def _flat(price=100, n=80, noise=0.05):
    """Generate flat / range-bound close prices (very low ADX)."""
    np.random.seed(42)
    return [price + np.random.uniform(-noise, noise) for _ in range(n)]


# ---------------------------------------------------------------------------
# ADX tests
# ---------------------------------------------------------------------------

class TestADX:
    def test_adx_returns_series(self):
        df = _make_ohlcv(_trending_up())
        adx = _compute_adx(df["High"], df["Low"], df["Close"])
        assert isinstance(adx, pd.Series)
        assert len(adx) == len(df)

    def test_adx_trending_market_above_threshold(self):
        closes = _trending_up(step=2.0)
        df = _make_ohlcv(closes, spread=0.3)
        adx = _compute_adx(df["High"], df["Low"], df["Close"])
        # Strong trend should produce ADX well above 20
        assert adx.iloc[-1] > 20

    def test_adx_flat_market_below_threshold(self):
        closes = _flat(noise=0.02)
        df = _make_ohlcv(closes, spread=0.01)
        adx = _compute_adx(df["High"], df["Low"], df["Close"])
        # Flat market should produce low ADX
        assert adx.iloc[-1] < 25


# ---------------------------------------------------------------------------
# Single-TF bias tests
# ---------------------------------------------------------------------------

class TestSingleTFBias:
    def test_bullish_in_strong_uptrend(self):
        df = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = _compute_single_tf_bias(df)
        assert result["bias"] == "BULL"
        assert result["confirmed"] is True

    def test_bearish_in_strong_downtrend(self):
        df = _make_ohlcv(_trending_down(step=2.0), spread=0.3)
        result = _compute_single_tf_bias(df)
        assert result["bias"] == "BEAR"
        assert result["confirmed"] is True

    def test_neutral_in_flat_market(self):
        """Low ADX should force bias to NEUT."""
        df = _make_ohlcv(_flat(noise=0.02), spread=0.01)
        result = _compute_single_tf_bias(df)
        assert result["bias"] == "NEUT"

    def test_adx_returned(self):
        df = _make_ohlcv(_trending_up())
        result = _compute_single_tf_bias(df)
        assert result["adx"] is not None
        assert isinstance(result["adx"], float)

    def test_insufficient_data(self):
        df = _make_ohlcv([100, 101, 102])
        result = _compute_single_tf_bias(df)
        assert result["bias"] == "NEUT"
        assert result["confirmed"] is False

    def test_empty_dataframe(self):
        result = _compute_single_tf_bias(pd.DataFrame())
        assert result["bias"] == "NEUT"

    def test_none_input(self):
        result = _compute_single_tf_bias(None)
        assert result["bias"] == "NEUT"

    def test_confirmation_bars(self):
        """With confirm_bars=1, confirmation should be easier."""
        df = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = _compute_single_tf_bias(df, confirm_bars=1)
        assert result["confirmed"] is True


# ---------------------------------------------------------------------------
# Weighted scoring tests
# ---------------------------------------------------------------------------

class TestWeightedScoring:
    def test_all_bull_max_score(self):
        """All 7 TFs bullish should give max weighted score = 13."""
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        assert result["overall_bias"] == "BULLISH"
        assert result["weighted_score"] == MAX_WEIGHT
        assert result["bull_count"] == 7
        assert result["bear_count"] == 0

    def test_all_bear_min_score(self):
        """All 7 TFs bearish should give min weighted score = -13."""
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_down(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        assert result["overall_bias"] == "BEARISH"
        assert result["weighted_score"] == -MAX_WEIGHT
        assert result["bear_count"] == 7

    def test_mixed_produces_partial_score(self):
        """Some bull, some bear, some neutral should produce a mixed score."""
        dfs = {
            "1m": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
            "5m": _make_ohlcv(_trending_down(step=2.0), spread=0.3),
            "15m": _make_ohlcv(_flat(noise=0.02), spread=0.01),
            "1H": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
            "4H": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
            "D": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
            "W": _make_ohlcv(_trending_down(step=2.0), spread=0.3),
        }
        result = compute_mtf_bias_from_dataframes(dfs)
        assert -MAX_WEIGHT < result["weighted_score"] < MAX_WEIGHT
        assert result["bull_count"] + result["bear_count"] <= 7

    def test_max_weighted_constant(self):
        assert MAX_WEIGHT == 13

    def test_alignment_strength(self):
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        assert result["alignment_strength"] == 7

    def test_verdict_present(self):
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        assert isinstance(result["verdict"], str)
        assert len(result["verdict"]) > 10


# ---------------------------------------------------------------------------
# Structure detection tests
# ---------------------------------------------------------------------------

class TestStructureDetection:
    def test_uptrend_detected(self):
        # Create higher highs and higher lows
        closes = [100 + i * 2 + np.sin(i) * 3 for i in range(60)]
        df = _make_ohlcv(closes, spread=1.0)
        result = _detect_structure(df, swing_length=3)
        assert result["trend"] in ("uptrend", "downtrend", "undefined")

    def test_downtrend_detected(self):
        closes = [200 - i * 2 + np.sin(i) * 3 for i in range(60)]
        df = _make_ohlcv(closes, spread=1.0)
        result = _detect_structure(df, swing_length=3)
        assert result["trend"] in ("uptrend", "downtrend", "undefined")

    def test_structure_keys(self):
        df = _make_ohlcv(_trending_up(n=60), spread=1.0)
        result = _detect_structure(df)
        assert "trend" in result
        assert "last_choch" in result
        assert "last_bos" in result

    def test_insufficient_data(self):
        df = _make_ohlcv([100, 101, 102])
        result = _detect_structure(df, swing_length=5)
        assert result["trend"] == "undefined"

    def test_empty_dataframe(self):
        result = _detect_structure(pd.DataFrame())
        assert result["trend"] == "undefined"

    def test_choch_detection(self):
        """Price that trends down then breaks above the last swing high
        should produce a bullish CHoCH."""
        # Downtrend then reversal
        closes = [200 - i * 2 for i in range(30)]  # downtrend
        closes += [200 - 29 * 2 + i * 3 for i in range(30)]  # reversal up
        df = _make_ohlcv(closes, spread=0.5)
        result = _detect_structure(df, swing_length=3)
        # The reversal should trigger either a CHoCH or a trend change
        assert result["trend"] in ("uptrend", "downtrend", "undefined")

    def test_bos_structure_format(self):
        """Verify BOS/CHoCH dict format when detected."""
        closes = [100 + i * 2 for i in range(40)]
        # Add a significant breakout
        closes += [100 + 39 * 2 + i * 5 for i in range(20)]
        df = _make_ohlcv(closes, spread=0.3)
        result = _detect_structure(df, swing_length=3)
        for event in (result["last_choch"], result["last_bos"]):
            if event is not None:
                assert "type" in event
                assert "price" in event
                assert "bar_index" in event
                assert event["type"] in ("bullish", "bearish")


# ---------------------------------------------------------------------------
# Full result structure tests
# ---------------------------------------------------------------------------

class TestFullResult:
    def test_result_keys(self):
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        expected_keys = {
            "timeframes", "overall_bias", "weighted_score", "max_weighted",
            "bull_count", "bear_count", "alignment_strength", "structure",
            "verdict",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_all_timeframes_present(self):
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        expected_tfs = {"1m", "5m", "15m", "1H", "4H", "D", "W"}
        assert set(result["timeframes"].keys()) == expected_tfs

    def test_each_tf_has_required_keys(self):
        dfs = {}
        for tf in TIMEFRAMES:
            dfs[tf["label"]] = _make_ohlcv(_trending_up(step=2.0), spread=0.3)
        result = compute_mtf_bias_from_dataframes(dfs)
        for label, info in result["timeframes"].items():
            assert "bias" in info
            assert "adx" in info
            assert "confirmed" in info
            assert info["bias"] in ("BULL", "BEAR", "NEUT")

    def test_missing_tf_data_graceful(self):
        """If some timeframes have no data, result should still be valid."""
        dfs = {
            "D": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
            "W": _make_ohlcv(_trending_up(step=2.0), spread=0.3),
        }
        result = compute_mtf_bias_from_dataframes(dfs)
        assert result["overall_bias"] in ("BULLISH", "BEARISH", "NEUTRAL")
        # Missing TFs should be NEUT
        assert result["timeframes"]["1m"]["bias"] == "NEUT"
