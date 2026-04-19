import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from scanner import analyze_stock, run_scan, get_market_internals


def make_mock_history(days=252, start_price=100.0):
    """Create realistic-looking OHLCV DataFrame."""
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=days)
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, days)
    close = start_price * np.cumprod(1 + returns)
    high = close * (1 + np.random.uniform(0, 0.03, days))
    low = close * (1 - np.random.uniform(0, 0.03, days))
    open_ = close * (1 + np.random.normal(0, 0.01, days))
    volume = np.random.randint(1_000_000, 10_000_000, days).astype(float)
    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low,
        "Close": close, "Volume": volume,
    }, index=dates)


class TestAnalyzeStock:
    @patch("scanner.yf.Ticker")
    def test_returns_full_result(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = make_mock_history()
        mock_ticker_cls.return_value = mock_ticker

        result = analyze_stock({"ticker": "TEST", "shares": 100, "avg_cost": 100.0, "tag": "hold"})

        assert result["ticker"] == "TEST"
        assert "current_price" in result
        assert "momentum" in result
        assert "volume" in result
        assert "moving_averages" in result
        assert "scanner_grades" in result
        assert "active_signals" in result
        assert "confluence_score" in result

    @patch("scanner.yf.Ticker")
    def test_handles_insufficient_data(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result = analyze_stock({"ticker": "BAD", "shares": 10, "avg_cost": 50.0, "tag": "none"})
        assert "error" in result

    @patch("scanner.yf.Ticker")
    def test_handles_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network error")
        result = analyze_stock({"ticker": "ERR", "shares": 10, "avg_cost": 50.0, "tag": "none"})
        assert "error" in result


class TestGetMarketInternals:
    @patch("scanner.yf.Ticker")
    def test_returns_index_data(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        hist = make_mock_history(days=5)
        mock_ticker.history.return_value = hist
        mock_ticker_cls.return_value = mock_ticker

        internals = get_market_internals()
        assert "sp500" in internals
        assert "nasdaq" in internals
        assert "vix" in internals
