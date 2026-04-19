# OpenScan Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted portfolio terminal dashboard that fetches live market data via yfinance, computes technical indicators, grades positions against scanner patterns, and displays everything in a dense Clark Moody-style terminal UI with draggable panels.

**Architecture:** Python FastAPI backend serves a single-page HTML frontend. Backend handles data fetching (yfinance), indicator computation, sell signal detection, and portfolio CRUD via SQLite. Frontend receives live updates via SSE and renders 11 draggable panels in a dark terminal aesthetic. Background scheduler auto-scans every 5 minutes during market hours.

**Tech Stack:** Python 3, FastAPI, uvicorn, yfinance, pandas, APScheduler, SQLite, vanilla JS/CSS, TradingView Lightweight Charts

**Spec:** `docs/superpowers/specs/2026-04-19-openscan-dashboard-design.md`
**Mockup:** `mockup.html`

---

## File Structure

```
asklivermore/
  server.py              # FastAPI app, routes, SSE, scheduler
  scanner.py             # Scanner engine — orchestrates fetch + analyze
  indicators.py          # Pure math: RSI, MACD, Bollinger, etc.
  grader.py              # Sell signal detection + pattern grading
  notifier.py            # Pushover/Telegram push notifications
  db.py                  # SQLite setup, migrations, CRUD queries
  static/
    index.html           # Single-page frontend (all CSS/JS inline)
  tests/
    test_indicators.py   # Unit tests for indicator math
    test_db.py           # Unit tests for database CRUD
    test_grader.py       # Unit tests for signal detection + grading
    test_scanner.py      # Integration tests for scanner engine
    test_server.py       # API endpoint tests with FastAPI TestClient
  openscan.db            # SQLite database (created on first run, gitignored)
  extracted-prompts.md   # Scanner pattern reference (existing file)
  requirements.txt       # Python dependencies
  .gitignore             # Ignore db, venv, __pycache__, etc.
```

---

### Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
yfinance==0.2.40
pandas==2.2.2
apscheduler==3.10.4
aiohttp==3.10.0
pytest==8.3.2
httpx==0.27.0
```

- [ ] **Step 2: Create .gitignore**

```
openscan.db
venv/
__pycache__/
*.pyc
.pytest_cache/
latest_scan.json
```

- [ ] **Step 3: Create empty tests/__init__.py**

Empty file.

- [ ] **Step 4: Install dependencies**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && pip install -r requirements.txt`

- [ ] **Step 5: Verify imports work**

Run: `source venv/bin/activate && python -c "import fastapi, uvicorn, yfinance, pandas, apscheduler, aiohttp; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Initialize git repo**

```bash
cd /Users/mandl/Desktop/projects/asklivermore
git init
git add requirements.txt .gitignore tests/__init__.py
git commit -m "chore: project setup with dependencies"
```

---

### Task 2: Database Layer

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for database initialization and CRUD**

```python
# tests/test_db.py
import os
import pytest
from db import (
    init_db, get_db, add_position, get_positions, update_position,
    delete_position, get_watchlist, set_watchlist, save_scan, get_latest_scan,
    get_config, set_config,
)

TEST_DB = "/tmp/openscan_test.db"


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_init_creates_tables():
    conn = get_db(TEST_DB)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    assert "positions" in tables
    assert "watchlist" in tables
    assert "scans" in tables
    assert "config" in tables


def test_add_and_get_positions():
    add_position(TEST_DB, "AAPL", 100, 150.0, "hold")
    add_position(TEST_DB, "MSFT", 50, 300.0, "div")
    positions = get_positions(TEST_DB)
    assert len(positions) == 2
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["shares"] == 100
    assert positions[0]["avg_cost"] == 150.0
    assert positions[0]["tag"] == "hold"
    assert positions[1]["ticker"] == "MSFT"


def test_update_position():
    add_position(TEST_DB, "AAPL", 100, 150.0, "hold")
    update_position(TEST_DB, "AAPL", shares=200, tag="sell")
    positions = get_positions(TEST_DB)
    assert positions[0]["shares"] == 200
    assert positions[0]["tag"] == "sell"


def test_delete_position():
    add_position(TEST_DB, "AAPL", 100, 150.0, "hold")
    delete_position(TEST_DB, "AAPL")
    assert len(get_positions(TEST_DB)) == 0


def test_watchlist():
    set_watchlist(TEST_DB, ["MSFT", "AAPL", "GOOGL"])
    tickers = get_watchlist(TEST_DB)
    assert set(tickers) == {"MSFT", "AAPL", "GOOGL"}
    set_watchlist(TEST_DB, ["AMD"])
    assert get_watchlist(TEST_DB) == ["AMD"]


def test_save_and_get_scan():
    scan_data = {"scan_id": "abc", "portfolio": []}
    save_scan(TEST_DB, "abc", scan_data)
    latest = get_latest_scan(TEST_DB)
    assert latest["scan_id"] == "abc"


def test_config():
    set_config(TEST_DB, "scan_interval", "5")
    assert get_config(TEST_DB, "scan_interval") == "5"
    assert get_config(TEST_DB, "missing_key", "default") == "default"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement db.py**

```python
# db.py
"""SQLite database layer for OpenScan."""

import sqlite3
import json
from datetime import datetime, timezone


_DEFAULT_DB = "openscan.db"


def init_db(db_path=_DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions (
            ticker TEXT PRIMARY KEY,
            shares REAL NOT NULL,
            avg_cost REAL NOT NULL,
            tag TEXT DEFAULT 'none',
            added_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            ticker TEXT PRIMARY KEY,
            added_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def get_db(db_path=_DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def add_position(db_path, ticker, shares, avg_cost, tag="none"):
    conn = get_db(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO positions (ticker, shares, avg_cost, tag, added_at) VALUES (?, ?, ?, ?, ?)",
        (ticker.upper(), shares, avg_cost, tag, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_positions(db_path=_DEFAULT_DB):
    conn = get_db(db_path)
    rows = conn.execute("SELECT ticker, shares, avg_cost, tag, added_at FROM positions ORDER BY ticker").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_position(db_path, ticker, shares=None, avg_cost=None, tag=None):
    conn = get_db(db_path)
    updates = []
    params = []
    if shares is not None:
        updates.append("shares = ?")
        params.append(shares)
    if avg_cost is not None:
        updates.append("avg_cost = ?")
        params.append(avg_cost)
    if tag is not None:
        updates.append("tag = ?")
        params.append(tag)
    if updates:
        params.append(ticker.upper())
        conn.execute(f"UPDATE positions SET {', '.join(updates)} WHERE ticker = ?", params)
        conn.commit()
    conn.close()


def delete_position(db_path, ticker):
    conn = get_db(db_path)
    conn.execute("DELETE FROM positions WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_watchlist(db_path=_DEFAULT_DB):
    conn = get_db(db_path)
    rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def set_watchlist(db_path, tickers):
    conn = get_db(db_path)
    conn.execute("DELETE FROM watchlist")
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT INTO watchlist (ticker, added_at) VALUES (?, ?)",
        [(t.upper(), now) for t in tickers],
    )
    conn.commit()
    conn.close()


def save_scan(db_path, scan_id, results):
    conn = get_db(db_path)
    conn.execute(
        "INSERT INTO scans (id, timestamp, results_json) VALUES (?, ?, ?)",
        (scan_id, datetime.now(timezone.utc).isoformat(), json.dumps(results, default=str)),
    )
    conn.commit()
    conn.close()


def get_latest_scan(db_path=_DEFAULT_DB):
    conn = get_db(db_path)
    row = conn.execute("SELECT results_json FROM scans ORDER BY timestamp DESC LIMIT 1").fetchone()
    conn.close()
    if row:
        return json.loads(row["results_json"])
    return None


def get_config(db_path, key, default=None):
    conn = get_db(db_path)
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_config(db_path, key, value):
    conn = get_db(db_path)
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && python -m pytest tests/test_db.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: database layer with positions, watchlist, scans, config CRUD"
```

---

### Task 3: Indicators Module

**Files:**
- Create: `indicators.py`
- Create: `tests/test_indicators.py`

This extracts the pure math functions from `fetch_signals.py` into a testable module.

- [ ] **Step 1: Write failing tests for indicator computations**

```python
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
        # Monotonically increasing prices -> RSI near 100
        prices = make_series([100 + i for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        assert rsi.iloc[-1] > 95

    def test_rsi_all_losses_near_0(self):
        # Monotonically decreasing prices -> RSI near 0
        prices = make_series([100 - i for i in range(30)])
        rsi = compute_rsi(prices, period=14)
        assert rsi.iloc[-1] < 5

    def test_rsi_mixed_around_50(self):
        # Alternating up/down -> RSI around 50
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
        last_idx = -1
        assert upper.iloc[last_idx] > lower.iloc[last_idx]

    def test_mid_is_sma(self):
        prices = make_series([100 + i for i in range(30)])
        _, mid, _ = compute_bollinger(prices, period=20, std_mult=2)
        expected_sma = prices.rolling(20).mean().iloc[-1]
        assert abs(mid.iloc[-1] - expected_sma) < 0.001
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_indicators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'indicators'`

- [ ] **Step 3: Implement indicators.py**

```python
# indicators.py
"""Pure technical indicator computations. No I/O, no side effects."""

import pandas as pd


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(series: pd.Series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    return upper, sma, lower
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_indicators.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add indicators.py tests/test_indicators.py
git commit -m "feat: indicators module with RSI, MACD, Bollinger computations"
```

---

### Task 4: Signal Detection (Grader)

**Files:**
- Create: `grader.py`
- Create: `tests/test_grader.py`

The grader takes computed indicator data for a stock and returns which sell signals are active, plus pattern grades and a confluence score. For v1 we implement the sell-side signals that are computable from price/volume data (no earnings or fundamental data).

- [ ] **Step 1: Write failing tests for signal detection**

```python
# tests/test_grader.py
import pytest
from grader import detect_sell_signals, compute_confluence_score, grade_minervini


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_grader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'grader'`

- [ ] **Step 3: Implement grader.py**

```python
# grader.py
"""Sell signal detection and pattern grading for OpenScan."""

import math


# Signal domain mappings for confluence scoring
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

# Rarity multipliers per spec
RARITY_MULTIPLIERS = {
    "volume_climax": 0.3,  # volume spikes are common
}

# Diminishing returns: points for nth signal in same domain
DOMAIN_POINTS = [15, 12, 9, 6, 3]


def detect_sell_signals(stock_data):
    """Detect active sell signals for a stock. Returns list of signal dicts."""
    signals = []
    momentum = stock_data.get("momentum", {})
    volume = stock_data.get("volume", {})
    ma = stock_data.get("moving_averages", {})

    # Bearish divergence
    if momentum.get("bearish_divergence"):
        signals.append({
            "type": "bearish_divergence",
            "domain": "momentum",
            "severity": "critical",
            "message": f"Bearish divergence — price near highs but RSI declining (RSI {momentum.get('rsi_14', '?')})",
        })

    # Volume climax
    if volume.get("volume_climax"):
        signals.append({
            "type": "volume_climax",
            "domain": "volume",
            "severity": "critical",
            "message": f"Volume climax detected — RVOL {volume.get('rvol', '?')}x. Distribution signal.",
        })

    # Below MA50
    if not ma.get("price_above_50ma", True):
        signals.append({
            "type": "below_ma50",
            "domain": "trend",
            "severity": "warning",
            "message": "Trading below 50-day MA. Trend structure weakening.",
        })

    # Below MA200
    if ma.get("price_above_200ma") is False:
        signals.append({
            "type": "below_ma200",
            "domain": "trend",
            "severity": "warning",
            "message": "Trading below 200-day MA. Long-term trend broken.",
        })

    # RSI oversold
    rsi = momentum.get("rsi_14", 50)
    if rsi < 30:
        signals.append({
            "type": "rsi_oversold",
            "domain": "momentum",
            "severity": "warning",
            "message": f"RSI oversold at {rsi}. May indicate capitulation or further downside.",
        })

    # RSI overbought
    if rsi > 80:
        signals.append({
            "type": "rsi_overbought",
            "domain": "momentum",
            "severity": "info",
            "message": f"RSI overbought at {rsi}. Watch for reversal.",
        })

    # Extended below MA50 (> 20% below)
    ext = ma.get("extension_from_50ma_pct", 0)
    if ext < -20:
        signals.append({
            "type": "extended_below_ma50",
            "domain": "trend",
            "severity": "critical",
            "message": f"Extended {ext:.1f}% below 50-day MA. Severe trend damage.",
        })

    # MACD bearish crossover
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
    """
    Compute confluence score using domain independence and diminishing returns.
    Returns (score 0-100, tier S/A/B/C).
    """
    if not signals:
        return 0, "C"

    # Group by domain
    domain_counts = {}
    for s in signals:
        domain = s.get("domain", "other")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    # Compute raw score with diminishing returns
    raw = 0
    for domain, count in domain_counts.items():
        for i in range(count):
            points = DOMAIN_POINTS[min(i, len(DOMAIN_POINTS) - 1)]
            raw += points

    # Apply rarity multipliers (bonus for rare signals)
    for s in signals:
        mult = RARITY_MULTIPLIERS.get(s["type"])
        if mult:
            raw *= (1 + mult)

    # Square-root normalization to 0-100
    score = min(100, int(math.sqrt(raw) * 10))

    # Tier classification
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
    """
    Grade against Minervini's 8-point Stage 2 trend template.
    Returns dict with passes (bool), criteria_met (int), details (list).
    """
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
        ("200-day MA trending up", ma200 > 0),  # Simplified: assume up if exists
        ("Within 25% of 52-week high", pct_from_high >= -25),
        ("At least 25% above 52-week low", pct_from_low >= 25),
        ("Relative strength upper tier", pct_from_high >= -15),  # Proxy: near highs = strong RS
    ]

    met = sum(1 for _, passed in criteria if passed)
    return {
        "passes": met == 8,
        "criteria_met": met,
        "criteria": [{"name": name, "passed": passed} for name, passed in criteria],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_grader.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add grader.py tests/test_grader.py
git commit -m "feat: sell signal detection, confluence scoring, Minervini grading"
```

---

### Task 5: Scanner Engine

**Files:**
- Create: `scanner.py`
- Create: `tests/test_scanner.py`

The scanner orchestrates: fetch data from yfinance, compute indicators, detect signals, compute grades, and build the full scan result.

- [ ] **Step 1: Write failing tests for scanner**

```python
# tests/test_scanner.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scanner'`

- [ ] **Step 3: Implement scanner.py**

```python
# scanner.py
"""Scanner engine — fetches market data and computes full analysis per stock."""

import yfinance as yf
import pandas as pd
import uuid
from datetime import datetime, timezone

from indicators import compute_rsi, compute_macd, compute_bollinger
from grader import detect_sell_signals, compute_confluence_score, grade_minervini


def analyze_stock(position, log_callback=None):
    """Analyze a single stock position. Returns full result dict."""
    ticker = position["ticker"]
    tag = position.get("tag", "none")

    def log(msg, level="INFO"):
        if log_callback:
            log_callback(level, msg)

    try:
        log(f"Fetching {ticker}...")
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "error": "Insufficient data"}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        current_price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])

        # Moving averages
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ema21 = float(close.ewm(span=21).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma150 = float(close.rolling(150).mean().iloc[-1]) if len(close) >= 150 else None
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

        ext_from_50ma = ((current_price - ma50) / ma50) * 100
        ext_from_200ma = ((current_price - ma200) / ma200) * 100 if ma200 else None

        # RSI
        rsi_series = compute_rsi(close, 14)
        rsi_14 = float(rsi_series.iloc[-1])
        rsi_5_ago = float(rsi_series.iloc[-6]) if len(close) > 6 else None

        # MACD
        macd_line, signal_line, macd_hist = compute_macd(close)
        macd_current = float(macd_line.iloc[-1])
        macd_signal_val = float(signal_line.iloc[-1])
        macd_hist_current = float(macd_hist.iloc[-1])
        macd_hist_prev = float(macd_hist.iloc[-2])

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = compute_bollinger(close)
        bb_upper_val = float(bb_upper.iloc[-1])
        bb_lower_val = float(bb_lower.iloc[-1])
        bb_mid_val = float(bb_mid.iloc[-1])
        bb_width = ((bb_upper_val - bb_lower_val) / bb_mid_val) * 100
        bb_position = ((current_price - bb_lower_val) / (bb_upper_val - bb_lower_val)) * 100

        # Volume
        vol_50avg = float(volume.rolling(50).mean().iloc[-1])
        vol_today = float(volume.iloc[-1])
        rvol = vol_today / vol_50avg if vol_50avg > 0 else 0
        vol_5avg = float(volume.tail(5).mean())
        vol_trend = vol_5avg / vol_50avg if vol_50avg > 0 else 0

        # 52-week high/low
        high_52w = float(high.max())
        low_52w = float(low.min())
        pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100
        pct_from_52w_low = ((current_price - low_52w) / low_52w) * 100

        # Price action
        change_1d = ((current_price - prev_close) / prev_close) * 100
        change_5d = ((current_price - float(close.iloc[-6])) / float(close.iloc[-6])) * 100 if len(close) > 6 else None
        change_20d = ((current_price - float(close.iloc[-21])) / float(close.iloc[-21])) * 100 if len(close) > 21 else None
        change_60d = ((current_price - float(close.iloc[-61])) / float(close.iloc[-61])) * 100 if len(close) > 61 else None

        # ADR%
        daily_range_pct = float(((high - low) / close * 100).tail(14).mean())

        # Bearish divergence
        recent_20_close = close.tail(20)
        recent_20_rsi = rsi_series.tail(20)
        price_making_new_highs = current_price >= float(recent_20_close.max()) * 0.99
        rsi_below_recent_peak = rsi_14 < float(recent_20_rsi.max()) * 0.95
        bearish_divergence = price_making_new_highs and rsi_below_recent_peak

        # Volume climax
        vol_max_10d = float(volume.tail(10).max())
        volume_climax = vol_today >= vol_max_10d * 0.95 and rvol >= 2.0

        # Close position in range
        day_range = float(high.iloc[-1]) - float(low.iloc[-1])
        close_position_pct = ((current_price - float(low.iloc[-1])) / day_range * 100) if day_range > 0 else 50

        # P&L
        unrealized_pnl = (current_price - position["avg_cost"]) * position["shares"]
        unrealized_pnl_pct = ((current_price - position["avg_cost"]) / position["avg_cost"]) * 100
        position_value = current_price * position["shares"]

        result = {
            "ticker": ticker,
            "tag": tag,
            "current_price": round(current_price, 2),
            "avg_cost": position["avg_cost"],
            "shares": position["shares"],
            "position_value": round(position_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "price_action": {
                "change_1d_pct": round(change_1d, 2),
                "change_5d_pct": round(change_5d, 2) if change_5d else None,
                "change_20d_pct": round(change_20d, 2) if change_20d else None,
                "change_60d_pct": round(change_60d, 2) if change_60d else None,
                "adr_14d_pct": round(daily_range_pct, 2),
                "close_position_in_range_pct": round(close_position_pct, 1),
            },
            "moving_averages": {
                "ma10": round(ma10, 2),
                "ema21": round(ema21, 2),
                "ma50": round(ma50, 2),
                "ma150": round(ma150, 2) if ma150 else None,
                "ma200": round(ma200, 2) if ma200 else None,
                "extension_from_50ma_pct": round(ext_from_50ma, 2),
                "extension_from_200ma_pct": round(ext_from_200ma, 2) if ext_from_200ma else None,
                "price_above_50ma": current_price > ma50,
                "price_above_200ma": current_price > ma200 if ma200 else None,
            },
            "momentum": {
                "rsi_14": round(rsi_14, 2),
                "rsi_5_days_ago": round(rsi_5_ago, 2) if rsi_5_ago else None,
                "macd_line": round(macd_current, 3),
                "macd_signal": round(macd_signal_val, 3),
                "macd_histogram": round(macd_hist_current, 3),
                "macd_hist_direction": "expanding" if abs(macd_hist_current) > abs(macd_hist_prev) else "contracting",
                "bearish_divergence": bearish_divergence,
            },
            "volatility": {
                "bb_upper": round(bb_upper_val, 2),
                "bb_lower": round(bb_lower_val, 2),
                "bb_width_pct": round(bb_width, 2),
                "bb_position_pct": round(bb_position, 1),
            },
            "volume": {
                "today_volume": int(vol_today),
                "avg_50d_volume": int(vol_50avg),
                "rvol": round(rvol, 2),
                "vol_5d_vs_50d": round(vol_trend, 2),
                "volume_climax": volume_climax,
            },
            "range_52w": {
                "high_52w": round(high_52w, 2),
                "low_52w": round(low_52w, 2),
                "pct_from_52w_high": round(pct_from_52w_high, 2),
                "pct_from_52w_low": round(pct_from_52w_low, 2),
            },
        }

        # Grading
        log(f"Grading {ticker}...", "DEBUG")
        signals = detect_sell_signals(result)
        confluence_score, confluence_tier = compute_confluence_score(signals)
        minervini = grade_minervini(result)

        result["active_signals"] = signals
        result["confluence_score"] = confluence_score
        result["confluence_tier"] = confluence_tier
        result["scanner_grades"] = {
            "minervini_trend": minervini,
        }

        log(f"{ticker}: ${current_price} | {len(signals)} signals | tier {confluence_tier}")
        return result

    except Exception as e:
        log(f"Error analyzing {ticker}: {e}", "ERROR")
        return {"ticker": ticker, "error": str(e)}


def get_market_internals(log_callback=None):
    """Fetch market index data: S&P 500, NASDAQ, VIX, 10Y yield."""
    def log(msg, level="INFO"):
        if log_callback:
            log_callback(level, msg)

    internals = {}
    indices = {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "vix": "^VIX",
        "yield_10y": "^TNX",
    }

    for name, symbol in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change_pct = ((price - prev) / prev) * 100
                internals[name] = {"price": round(price, 2), "change_pct": round(change_pct, 2)}
            else:
                internals[name] = {"price": 0, "change_pct": 0}
        except Exception as e:
            log(f"Error fetching {name}: {e}", "ERROR")
            internals[name] = {"price": 0, "change_pct": 0}

    return internals


def scan_watchlist(tickers, log_callback=None):
    """Scan watchlist tickers for undervalued opportunities."""
    def log(msg, level="INFO"):
        if log_callback:
            log_callback(level, msg)

    results = []
    for ticker_symbol in tickers:
        try:
            log(f"Watchlist: checking {ticker_symbol}...", "DEBUG")
            stock = yf.Ticker(ticker_symbol)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 200:
                continue

            close = hist["Close"]
            current_price = float(close.iloc[-1])
            high_52w = float(hist["High"].max())
            pct_from_high = ((current_price - high_52w) / high_52w) * 100
            rsi = float(compute_rsi(close, 14).iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1])

            reasons = []
            criteria_met = 0

            if pct_from_high <= -15:
                reasons.append(f"{pct_from_high:.0f}% from ATH")
                criteria_met += 1
            if rsi < 40:
                reasons.append(f"RSI {rsi:.0f}")
                criteria_met += 1
            if current_price <= ma200 * 1.02:
                reasons.append("Near 200MA support")
                criteria_met += 1

            if criteria_met >= 2:
                results.append({
                    "ticker": ticker_symbol,
                    "price": round(current_price, 2),
                    "reason": ", ".join(reasons),
                })
        except Exception as e:
            log(f"Watchlist error {ticker_symbol}: {e}", "ERROR")

    return results


def run_scan(positions, watchlist_tickers=None, log_callback=None):
    """Run a full scan: portfolio + market internals + watchlist."""
    def log(msg, level="INFO"):
        if log_callback:
            log_callback(level, msg)

    scan_id = str(uuid.uuid4())[:8]
    log(f"Starting scan {scan_id}...")

    # Analyze portfolio
    portfolio_results = []
    for pos in positions:
        result = analyze_stock(pos, log_callback)
        portfolio_results.append(result)

    # Market internals
    log("Fetching market internals...")
    market = get_market_internals(log_callback)

    # Watchlist
    watchlist_results = []
    if watchlist_tickers:
        log(f"Scanning {len(watchlist_tickers)} watchlist tickers...")
        watchlist_results = scan_watchlist(watchlist_tickers, log_callback)

    # Collect alerts
    alerts = []
    for r in portfolio_results:
        for signal in r.get("active_signals", []):
            if signal["severity"] in ("critical", "warning"):
                alerts.append({
                    "ticker": r["ticker"],
                    "severity": signal["severity"],
                    "type": signal["type"],
                    "message": signal["message"],
                })

    # Determine market status
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()
    if weekday >= 5:
        market_status = "closed"
    elif (hour == 9 and minute >= 30) or (10 <= hour < 16):
        market_status = "open"
    elif hour < 9 or (hour == 9 and minute < 30):
        market_status = "pre"
    elif hour >= 16:
        market_status = "post"
    else:
        market_status = "closed"

    scan_result = {
        "scan_id": scan_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_status": market_status,
        "portfolio": portfolio_results,
        "alerts": alerts,
        "watchlist": watchlist_results,
        "market_internals": market,
    }

    log(f"Scan {scan_id} complete. {len(alerts)} alerts.", "INFO")
    return scan_result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scanner.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scanner.py tests/test_scanner.py
git commit -m "feat: scanner engine with stock analysis, market internals, watchlist scanning"
```

---

### Task 6: Notification Service

**Files:**
- Create: `notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests for notifier**

```python
# tests/test_notifier.py
import pytest
from unittest.mock import patch, AsyncMock
from notifier import format_alert_message, should_notify, Notifier


def test_format_alert_message():
    alert = {
        "ticker": "BBAI",
        "severity": "critical",
        "type": "volume_climax",
        "message": "Volume climax detected — RVOL 3.2x",
    }
    msg = format_alert_message(alert)
    assert "BBAI" in msg
    assert "CRITICAL" in msg or "critical" in msg.lower()


def test_should_notify_critical():
    assert should_notify("critical", set()) is True


def test_should_notify_dedup():
    seen = {("BBAI", "volume_climax")}
    assert should_notify("critical", seen, "BBAI", "volume_climax") is False


def test_should_notify_info_skipped():
    assert should_notify("info", set()) is False


class TestNotifier:
    def test_notifier_disabled_by_default(self):
        n = Notifier()
        assert not n.is_configured()

    def test_notifier_pushover_configured(self):
        n = Notifier(pushover_token="abc", pushover_user="xyz")
        assert n.is_configured()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notifier'`

- [ ] **Step 3: Implement notifier.py**

```python
# notifier.py
"""Push notification service for OpenScan. Supports Pushover and Telegram."""

import aiohttp


def format_alert_message(alert):
    severity = alert["severity"].upper()
    return f"[{severity}] {alert['ticker']}: {alert['message']}"


def should_notify(severity, seen_today, ticker=None, signal_type=None):
    """Determine if this alert warrants a push notification."""
    if severity == "info":
        return False
    if ticker and signal_type and (ticker, signal_type) in seen_today:
        return False
    return True


class Notifier:
    def __init__(self, pushover_token=None, pushover_user=None,
                 telegram_token=None, telegram_chat_id=None):
        self.pushover_token = pushover_token
        self.pushover_user = pushover_user
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self._seen_today = set()

    def is_configured(self):
        return bool(self.pushover_token and self.pushover_user) or \
               bool(self.telegram_token and self.telegram_chat_id)

    def reset_daily(self):
        self._seen_today.clear()

    async def send_alert(self, alert):
        key = (alert["ticker"], alert["type"])
        if not should_notify(alert["severity"], self._seen_today, alert["ticker"], alert["type"]):
            return False

        self._seen_today.add(key)
        message = format_alert_message(alert)

        if self.pushover_token:
            await self._send_pushover(message, alert["severity"])
        if self.telegram_token:
            await self._send_telegram(message)
        return True

    async def _send_pushover(self, message, severity):
        priority = 1 if severity == "critical" else 0
        async with aiohttp.ClientSession() as session:
            await session.post("https://api.pushover.net/1/messages.json", data={
                "token": self.pushover_token,
                "user": self.pushover_user,
                "message": message,
                "priority": priority,
                "title": "OpenScan Alert",
            })

    async def _send_telegram(self, message):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_notifier.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add notifier.py tests/test_notifier.py
git commit -m "feat: notification service with Pushover and Telegram support"
```

---

### Task 7: FastAPI Server

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for API endpoints**

```python
# tests/test_server.py
import os
import pytest
from fastapi.testclient import TestClient

TEST_DB = "/tmp/openscan_test_server.db"
os.environ["OPENSCAN_DB"] = TEST_DB

from server import app, init_app
from db import init_db

@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    init_app(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


client = TestClient(app)


class TestPortfolioAPI:
    def test_get_empty_portfolio(self):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_position(self):
        resp = client.post("/api/portfolio", json={
            "ticker": "AAPL", "shares": 100, "avg_cost": 150.0, "tag": "hold"
        })
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    def test_add_and_get_positions(self):
        client.post("/api/portfolio", json={
            "ticker": "AAPL", "shares": 100, "avg_cost": 150.0
        })
        resp = client.get("/api/portfolio")
        assert len(resp.json()) == 1

    def test_update_position(self):
        client.post("/api/portfolio", json={
            "ticker": "AAPL", "shares": 100, "avg_cost": 150.0
        })
        resp = client.put("/api/portfolio/AAPL", json={"tag": "sell", "shares": 200})
        assert resp.status_code == 200

        positions = client.get("/api/portfolio").json()
        assert positions[0]["shares"] == 200
        assert positions[0]["tag"] == "sell"

    def test_delete_position(self):
        client.post("/api/portfolio", json={
            "ticker": "AAPL", "shares": 100, "avg_cost": 150.0
        })
        resp = client.delete("/api/portfolio/AAPL")
        assert resp.status_code == 200
        assert len(client.get("/api/portfolio").json()) == 0


class TestWatchlistAPI:
    def test_get_default_watchlist(self):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200

    def test_set_watchlist(self):
        resp = client.put("/api/watchlist", json={"tickers": ["MSFT", "AMD"]})
        assert resp.status_code == 200
        tickers = client.get("/api/watchlist").json()
        assert set(tickers) == {"AMD", "MSFT"}


class TestConfigAPI:
    def test_get_config(self):
        resp = client.get("/api/config")
        assert resp.status_code == 200

    def test_set_config(self):
        resp = client.put("/api/config", json={"scan_interval": "5"})
        assert resp.status_code == 200


class TestLatestScan:
    def test_no_scans_returns_null(self):
        resp = client.get("/api/latest")
        assert resp.status_code == 200
        assert resp.json() is None


class TestFrontend:
    def test_serves_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Implement server.py**

```python
# server.py
"""FastAPI server for OpenScan dashboard."""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from db import (
    init_db, add_position, get_positions, update_position,
    delete_position, get_watchlist, set_watchlist, save_scan,
    get_latest_scan, get_config, set_config,
)
from scanner import run_scan
from notifier import Notifier

# Default watchlist
DEFAULT_WATCHLIST = [
    "MSFT", "AAPL", "GOOGL", "AMD", "NVDA", "META", "TSLA", "NFLX",
    "CRM", "ADBE", "ORCL", "AVGO", "COST", "WMT", "JNJ", "PG",
    "V", "MA", "JPM", "BAC", "DIS", "NKE", "SBUX", "HD", "LOW",
]

# Global state
_db_path = os.environ.get("OPENSCAN_DB", "openscan.db")
_sse_clients: list[asyncio.Queue] = []
_notifier = Notifier()
_scan_lock = asyncio.Lock()
_scheduler = None


def init_app(db_path=None):
    global _db_path
    if db_path:
        _db_path = db_path
    init_db(_db_path)
    # Seed default watchlist if empty
    if not get_watchlist(_db_path):
        set_watchlist(_db_path, DEFAULT_WATCHLIST)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_app()
    # Start scheduler
    await _start_scheduler()
    yield
    # Shutdown scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)


# --- SSE ---

async def sse_broadcast(event_type, data):
    """Send an SSE event to all connected clients."""
    msg = f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
    dead = []
    for q in _sse_clients:
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        _sse_clients.remove(q)


@app.get("/api/events")
async def sse_endpoint(request: Request):
    queue = asyncio.Queue(maxsize=100)
    _sse_clients.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if queue in _sse_clients:
                _sse_clients.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Scan ---

async def _run_scan_async():
    """Run scan in background thread (yfinance is blocking I/O)."""
    async with _scan_lock:
        positions = get_positions(_db_path)
        if not positions:
            return None

        watchlist_tickers = get_watchlist(_db_path)

        async def log_callback(level, msg):
            await sse_broadcast("log", {"level": level, "message": msg, "timestamp": datetime.now().isoformat()})

        # Run blocking scan in executor
        loop = asyncio.get_event_loop()

        log_messages = []
        def sync_log(level, msg):
            log_messages.append({"level": level, "message": msg, "timestamp": datetime.now().isoformat()})

        result = await loop.run_in_executor(
            None, lambda: run_scan(positions, watchlist_tickers, sync_log)
        )

        # Broadcast accumulated log messages
        for log_msg in log_messages:
            await sse_broadcast("log", log_msg)

        # Save and broadcast
        save_scan(_db_path, result["scan_id"], result)
        await sse_broadcast("scan_complete", result)

        # Send notifications
        if _notifier.is_configured():
            for alert in result.get("alerts", []):
                await _notifier.send_alert(alert)

        return result


@app.post("/api/scan")
async def trigger_scan():
    result = await _run_scan_async()
    return result


@app.get("/api/latest")
async def get_latest():
    return get_latest_scan(_db_path)


# --- Portfolio CRUD ---

class PositionIn(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    tag: str = "none"


class PositionUpdate(BaseModel):
    shares: float | None = None
    avg_cost: float | None = None
    tag: str | None = None


@app.get("/api/portfolio")
async def list_positions():
    return get_positions(_db_path)


@app.post("/api/portfolio")
async def create_position(pos: PositionIn):
    add_position(_db_path, pos.ticker, pos.shares, pos.avg_cost, pos.tag)
    return {"ticker": pos.ticker.upper(), "status": "added"}


@app.put("/api/portfolio/{ticker}")
async def modify_position(ticker: str, update: PositionUpdate):
    update_position(_db_path, ticker, update.shares, update.avg_cost, update.tag)
    return {"ticker": ticker.upper(), "status": "updated"}


@app.delete("/api/portfolio/{ticker}")
async def remove_position(ticker: str):
    delete_position(_db_path, ticker)
    return {"ticker": ticker.upper(), "status": "deleted"}


# --- Watchlist ---

@app.get("/api/watchlist")
async def list_watchlist():
    return get_watchlist(_db_path)


class WatchlistIn(BaseModel):
    tickers: list[str]


@app.put("/api/watchlist")
async def update_watchlist(data: WatchlistIn):
    set_watchlist(_db_path, data.tickers)
    return {"status": "updated"}


# --- Config ---

@app.get("/api/config")
async def read_config():
    return {
        "scan_interval": get_config(_db_path, "scan_interval", "5"),
        "pushover_token": get_config(_db_path, "pushover_token", ""),
        "pushover_user": get_config(_db_path, "pushover_user", ""),
        "telegram_token": get_config(_db_path, "telegram_token", ""),
        "telegram_chat_id": get_config(_db_path, "telegram_chat_id", ""),
    }


class ConfigUpdate(BaseModel):
    scan_interval: str | None = None
    pushover_token: str | None = None
    pushover_user: str | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None


@app.put("/api/config")
async def write_config(data: ConfigUpdate):
    for key, val in data.model_dump(exclude_none=True).items():
        set_config(_db_path, key, val)
    # Reload notifier config
    _reload_notifier()
    return {"status": "updated"}


def _reload_notifier():
    global _notifier
    _notifier = Notifier(
        pushover_token=get_config(_db_path, "pushover_token"),
        pushover_user=get_config(_db_path, "pushover_user"),
        telegram_token=get_config(_db_path, "telegram_token"),
        telegram_chat_id=get_config(_db_path, "telegram_chat_id"),
    )


# --- Chart data ---

@app.get("/api/history/{ticker}")
async def get_history(ticker: str):
    import yfinance as yf
    loop = asyncio.get_event_loop()
    def fetch():
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if hist.empty:
            return []
        records = []
        for idx, row in hist.iterrows():
            records.append({
                "time": idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return records
    return await loop.run_in_executor(None, fetch)


# --- Scheduler ---

async def _start_scheduler():
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = AsyncIOScheduler()
        # Every 5 minutes, Mon-Fri, 9:30am-4:00pm ET
        _scheduler.add_job(
            _run_scan_async,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*/5",
                timezone="US/Eastern",
            ),
            id="market_hours_scan",
            replace_existing=True,
        )
        # Also run at 9:30 and 9:35 (scheduler starts at hour 9)
        _scheduler.start()
    except Exception:
        pass  # Scheduler optional — manual scan still works


# --- Frontend ---

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>OpenScan</h1><p>Frontend not found. Create static/index.html</p>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=3000, reload=True)
```

- [ ] **Step 4: Create a placeholder static/index.html so the frontend test passes**

Create `static/index.html` with:
```html
<!DOCTYPE html><html><head><title>OpenScan</title></head><body><h1>OpenScan</h1></body></html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_server.py -v`
Expected: All 11 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server.py static/index.html
git commit -m "feat: FastAPI server with REST API, SSE, scheduler, portfolio CRUD"
```

---

### Task 8: Seed Database with Current Portfolio

**Files:**
- Create: `seed.py`

A one-time script to migrate the hardcoded portfolio from `fetch_signals.py` into the database.

- [ ] **Step 1: Create seed.py**

```python
# seed.py
"""Seed the database with the current portfolio positions."""

from db import init_db, add_position, set_watchlist

PORTFOLIO = [
    {"ticker": "UNH",  "shares": 100, "avg_cost": 321.081, "tag": "div"},
    {"ticker": "SMR",  "shares": 300, "avg_cost": 21.00,   "tag": "sell"},
    {"ticker": "IREN", "shares": 700, "avg_cost": 55.114,  "tag": "none"},
    {"ticker": "CPRT", "shares": 100, "avg_cost": 48.413,  "tag": "none"},
    {"ticker": "CIFR", "shares": 225, "avg_cost": 17.467,  "tag": "none"},
    {"ticker": "BBAI", "shares": 400, "avg_cost": 9.08,    "tag": "sell"},
    {"ticker": "ASST", "shares": 30,  "avg_cost": 27.466,  "tag": "sell"},
    {"ticker": "AMZN", "shares": 45,  "avg_cost": 216.731, "tag": "hold"},
]

DEFAULT_WATCHLIST = [
    "MSFT", "AAPL", "GOOGL", "AMD", "NVDA", "META", "TSLA", "NFLX",
    "CRM", "ADBE", "ORCL", "AVGO", "COST", "WMT", "JNJ", "PG",
    "V", "MA", "JPM", "BAC", "DIS", "NKE", "SBUX", "HD", "LOW",
]

if __name__ == "__main__":
    init_db()
    for pos in PORTFOLIO:
        add_position("openscan.db", pos["ticker"], pos["shares"], pos["avg_cost"], pos["tag"])
        print(f"  Added {pos['ticker']}")
    set_watchlist("openscan.db", DEFAULT_WATCHLIST)
    print(f"  Watchlist: {len(DEFAULT_WATCHLIST)} tickers")
    print("Done.")
```

- [ ] **Step 2: Run it**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && python seed.py`
Expected: Prints each ticker added, then "Done."

- [ ] **Step 3: Commit**

```bash
git add seed.py
git commit -m "feat: seed script to migrate existing portfolio to database"
```

---

### Task 9: Frontend — Full Dashboard

**Files:**
- Modify: `static/index.html`

This is the largest task. The frontend is a single self-contained HTML file with all CSS and JS inline. It connects to the backend API and SSE for live updates, renders all 11 panels, supports drag-and-drop, light/dark theme toggle, and portfolio management.

The frontend code is based on the approved `mockup.html` but wired to real data. Due to the size of this file (~1500 lines), it is implemented as a single focused task rather than split across multiple tasks, since all parts depend on the shared CSS and JS infrastructure.

- [ ] **Step 1: Read the mockup for reference**

Read: `mockup.html` — use its CSS, panel structure, and visual design as the basis. The CSS variables, panel classes, data-row styles, table styles, drag-and-drop JS, and color scheme all carry over.

- [ ] **Step 2: Build static/index.html**

The file must include:

**CSS (carried from mockup + additions):**
- All CSS from mockup.html (dark theme variables, panel styles, table styles, data rows, etc.)
- Light theme: `[data-theme="light"]` selector overriding CSS variables
- Debug log panel styles (collapsible, scrollable, filter buttons)
- Modal styles for add/edit position forms
- SCAN button and theme toggle in header
- TradingView chart container styles

**HTML structure:**
- Header: OPENSCAN title, SCAN button, LOCK/UNLOCK, theme toggle (sun/moon icon), market status, last scan time
- Main grid: all 11 panels as `<div class="panel" data-panel-id="...">` elements
- Each panel renders from scan data using template functions
- Add Position modal (hidden by default)
- Footer: version, data source attribution

**JavaScript:**
- `fetchLatest()` — GET `/api/latest`, render all panels
- `triggerScan()` — POST `/api/scan`, disable button during scan
- `connectSSE()` — EventSource to `/api/events`, handle `log` and `scan_complete` events
- `renderPortfolioValue(data)` — update panel 1
- `renderAlerts(alerts)` — update panel 2
- `renderHoldings(portfolio)` — update panel 3 table, attach click handlers
- `renderScannerGrades(stock)` — update panel 4 for selected stock
- `renderMarketInternals(internals)` — update panel 5
- `renderWatchlist(watchlist)` — update panel 6
- `renderPositionDetail(stock)` — update panel 7
- `renderHeatmap(portfolio)` — update panel 8
- `renderSignalMatrix(portfolio)` — update panel 9
- `appendScanLog(msg)` — append to panel 10
- `appendDebugLog(msg)` — append to panel 11 with level filtering
- `selectTicker(ticker)` — called on Holdings row click, updates panels 4 + 7
- Drag-and-drop code (carried from mockup.html)
- Theme toggle: `document.documentElement.dataset.theme = theme; localStorage.setItem('openscan-theme', theme)`
- Layout persistence via localStorage
- Auto-scan on page load: `fetchLatest()` then `triggerScan()` if data is stale (> 5 min old)
- Portfolio CRUD: add/edit/delete via modal → POST/PUT/DELETE `/api/portfolio/*`
- TradingView Lightweight Charts: load via CDN script tag, render candlestick chart in Position Detail panel using data from GET `/api/history/{ticker}`

- [ ] **Step 3: Test manually**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && python server.py`

Open `http://localhost:3000` in browser. Verify:
1. Dashboard loads with dark theme
2. Click SCAN — data populates all panels
3. Click a ticker row — Position Detail and Scanner Grades update
4. Toggle light/dark mode
5. Drag panels — layout snaps and persists on reload
6. Scan Log shows progress messages
7. Debug Log shows verbose output

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: full terminal-style dashboard frontend with 11 panels, drag-and-drop, themes"
```

---

### Task 10: Integration Test — End to End

**Files:**
- No new files

- [ ] **Step 1: Run the full test suite**

Run: `cd /Users/mandl/Desktop/projects/asklivermore && source venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run the server and do a live scan**

Run: `python server.py`

Open `http://localhost:3000`, click SCAN, verify real data appears for all 8 portfolio positions.

- [ ] **Step 3: Verify on phone**

Find your Mac's local IP: `ifconfig | grep "inet " | grep -v 127.0.0.1`

Open `http://<your-ip>:3000` on your phone. Verify the dashboard is responsive and readable.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: integration verification complete"
```

---

## Summary

| Task | What it builds | Key files |
|------|---------------|-----------|
| 1 | Project setup | requirements.txt, .gitignore |
| 2 | Database layer | db.py, tests/test_db.py |
| 3 | Indicators module | indicators.py, tests/test_indicators.py |
| 4 | Signal detection & grading | grader.py, tests/test_grader.py |
| 5 | Scanner engine | scanner.py, tests/test_scanner.py |
| 6 | Notification service | notifier.py, tests/test_notifier.py |
| 7 | FastAPI server + API | server.py, tests/test_server.py |
| 8 | Seed database | seed.py |
| 9 | Full frontend dashboard | static/index.html |
| 10 | Integration testing | — |
