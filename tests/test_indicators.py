# tests/test_indicators.py
import pandas as pd
import numpy as np
import pytest
from indicators import compute_rsi, compute_macd, compute_bollinger


def make_series(values):
    return pd.Series(values, dtype=float)


class TestRSI:
    def test_rsi_returns_series(self):
        prices = make_series(list(range(100, 120)))
        result = compute_rsi(prices, period=14)
        assert isinstance(result, pd.Series)
        assert len(result) == len(prices)

    def test_rsi_all_gains_near_100(self):
        prices = make_series([100 + i for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        assert rsi.iloc[-1] > 95

    def test_rsi_all_losses_near_0(self):
        prices = make_series([100 - i for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        assert rsi.iloc[-1] < 5

    def test_rsi_mixed_around_50(self):
        prices = make_series([100 + (1 if i % 2 == 0 else -1) for i in range(50)])
        rsi = compute_rsi(prices, period=14)
        assert 40 < rsi.iloc[-1] < 60


class TestMACD:
    def test_macd_returns_three_series(self):
        prices = make_series([100 + i * 0.5 for i in range(50)])
        macd_line, signal_line, histogram = compute_macd(prices)
        assert isinstance(macd_line, pd.Series)
        assert isinstance(signal_line, pd.Series)
        assert isinstance(histogram, pd.Series)

    def test_macd_uptrend_positive(self):
        prices = make_series([100 + i for i in range(50)])
        macd_line, _, _ = compute_macd(prices)
        assert macd_line.iloc[-1] > 0

    def test_histogram_is_macd_minus_signal(self):
        prices = make_series([100 + i * 0.3 + np.sin(i) for i in range(50)])
        macd_line, signal_line, histogram = compute_macd(prices)
        np.testing.assert_allclose(
            histogram.values, (macd_line - signal_line).values, atol=1e-10
        )


class TestBollinger:
    def test_bollinger_returns_three_series(self):
        prices = make_series([100 + np.sin(i) for i in range(30)])
        upper, mid, lower = compute_bollinger(prices, period=20, std_mult=2)
        assert isinstance(upper, pd.Series)
        assert isinstance(mid, pd.Series)
        assert isinstance(lower, pd.Series)

    def test_upper_above_lower(self):
        prices = make_series([100 + np.sin(i) * 5 for i in range(30)])
        upper, mid, lower = compute_bollinger(prices, period=20, std_mult=2)
        assert upper.iloc[-1] > lower.iloc[-1]

    def test_mid_is_sma(self):
        prices = make_series([100 + i for i in range(30)])
        _, mid, _ = compute_bollinger(prices, period=20, std_mult=2)
        expected_sma = prices.rolling(20).mean().iloc[-1]
        assert abs(mid.iloc[-1] - expected_sma) < 0.001
