import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from scanner import analyze_stock, run_scan, get_market_internals


def make_mock_history(days=252, start_price=100.0):
    """Create realistic-looking OHLCV DataFrame matching _fetch_history output."""
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


def make_mock_snapshot_df(codes):
    """Create a mock snapshot DataFrame matching moomoo get_market_snapshot output."""
    rows = []
    for code in codes:
        rows.append({
            "code": code,
            "last_price": 450.0,
            "prev_close_price": 448.0,
            "open_price": 449.0,
            "high_price": 452.0,
            "low_price": 447.0,
            "volume": 5000000,
        })
    return pd.DataFrame(rows)


class TestAnalyzeStock:
    @patch("scanner._fetch_history")
    @patch("scanner._get_quote_ctx")
    def test_returns_full_result(self, mock_ctx, mock_fetch):
        mock_ctx.return_value = MagicMock()
        mock_fetch.return_value = make_mock_history()

        result = analyze_stock({"ticker": "TEST", "shares": 100, "avg_cost": 100.0, "tag": "hold"})

        assert result["ticker"] == "TEST"
        assert "current_price" in result
        assert "momentum" in result
        assert "volume" in result
        assert "moving_averages" in result
        assert "scanner_grades" in result
        assert "active_signals" in result
        assert "confluence_score" in result

    @patch("scanner._fetch_history")
    @patch("scanner._get_quote_ctx")
    def test_handles_insufficient_data(self, mock_ctx, mock_fetch):
        mock_ctx.return_value = MagicMock()
        mock_fetch.return_value = pd.DataFrame()

        result = analyze_stock({"ticker": "BAD", "shares": 10, "avg_cost": 50.0, "tag": "none"})
        assert "error" in result

    @patch("scanner._get_quote_ctx")
    def test_handles_exception(self, mock_ctx):
        mock_ctx.side_effect = Exception("OpenD not running")
        result = analyze_stock({"ticker": "ERR", "shares": 10, "avg_cost": 50.0, "tag": "none"})
        assert "error" in result


class TestGetMarketInternals:
    @patch("scanner._get_quote_ctx")
    def test_returns_index_data(self, mock_ctx):
        ctx = MagicMock()
        snapshot_df = make_mock_snapshot_df(["US.SPY", "US.QQQ", "US.UVXY"])
        ctx.get_market_snapshot.return_value = (0, snapshot_df)  # RET_OK = 0
        mock_ctx.return_value = ctx

        internals = get_market_internals()
        assert "sp500" in internals
        assert "nasdaq" in internals
        assert "vix" in internals
        assert internals["sp500"]["price"] is not None
