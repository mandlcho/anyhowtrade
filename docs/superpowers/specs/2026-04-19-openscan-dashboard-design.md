# OpenScan — Portfolio Terminal Dashboard

**Date:** 2026-04-19
**Status:** Design
**Reference mockup:** `mockup.html`

---

## 1. Purpose

OpenScan is a self-hosted portfolio terminal dashboard that fetches live market data, computes technical indicators, runs 47 scanner patterns against holdings, and surfaces sell signals and buy opportunities — all in a dense, dark terminal-style UI inspired by Clark Moody's Bitcoin dashboard.

**Target user:** A single user (the portfolio owner) running locally on their Mac, accessing from both desktop browser and phone (same WiFi or tunnel).

---

## 2. Architecture

### Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python 3 + FastAPI | Existing scanner is Python; natural fit |
| Frontend | Single HTML page, vanilla JS, CSS | Zero build tooling, self-contained |
| Charting | TradingView Lightweight Charts (free) | Professional look, dark theme support, small footprint |
| Database | SQLite | Portfolio config, scan history, layout preferences |
| Notifications | Pushover or Telegram bot | Phone push alerts for urgent signals |
| Data source | Moomoo OpenD (moomoo-api) | Real-time US market data via local OpenD gateway. Stocks use `US.TICKER` format. `request_history_kline()` for OHLCV, `get_market_snapshot()` for real-time snapshots. Requires OpenD running on localhost:11111. Market internals via US.SPY, US.QQQ, plus index tickers. Future: options chain data for IV/Greeks. |

### How It Runs

```
python server.py
```

- Starts FastAPI on `localhost:3000`
- Serves the frontend HTML at `/`
- Exposes REST API at `/api/*`
- Background scheduler triggers scans automatically

### Process Flow

```
Browser <--> FastAPI (localhost:3000)
                |
                +--> Scanner Engine (yfinance + indicators + pattern grading)
                |
                +--> SQLite (portfolio config, scan history)
                |
                +--> Notification Service (Pushover/Telegram, optional)
```

---

## 3. Scanning

### Triggers

1. **On page load** — frontend calls `/api/scan` when the dashboard opens
2. **Every 5 minutes during market hours** — background scheduler (9:30am - 4:00pm ET, Mon-Fri)
3. **Manual button** — "SCAN" button in the header bar fires `/api/scan`

### What a Scan Does

1. Fetch 1 year of daily OHLCV data from yfinance for each portfolio position
2. Compute technical indicators (same as current `fetch_signals.py`):
   - Moving averages: MA10, EMA21, MA50, MA150, MA200
   - Extension from MAs (%)
   - RSI(14), MACD (line/signal/histogram)
   - Bollinger Bands (upper/lower/width/position)
   - Volume: today, 50d avg, RVOL, 5d trend, volume climax detection
   - Bearish divergence detection
   - Price action: 1d/5d/20d/60d changes, ADR%, close position in range
   - 52-week high/low distance
   - Position P&L ($ and %)
3. Run scanner pattern grading against the 47 patterns from `extracted-prompts.md`
4. Compute confluence scores per the scoring system (domain independence, rarity multipliers, diminishing returns, square-root normalization, tier classification S/A/B/C)
5. Check blue chip watchlist (configurable list of ~25 tickers) for undervalued opportunities
6. Generate alerts for positions with active sell signals
7. Save results to SQLite (scan history)
8. Push notifications for urgent alerts (if configured)
9. Return full results as JSON to the frontend via SSE

### Scan Output Schema

```json
{
  "scan_id": "uuid",
  "timestamp": "2026-04-19T15:59:00-04:00",
  "market_status": "open|closed|pre|post",
  "portfolio": [
    {
      "ticker": "AMZN",
      "tag": "hold",
      "current_price": 249.99,
      "avg_cost": 216.73,
      "shares": 45,
      "position_value": 11249.55,
      "unrealized_pnl": 1496.82,
      "unrealized_pnl_pct": 15.34,
      "price_action": { ... },
      "moving_averages": { ... },
      "momentum": { ... },
      "volatility": { ... },
      "volume": { ... },
      "range_52w": { ... },
      "scanner_grades": {
        "minervini_trend": "A",
        "can_slim": "B+",
        ...
      },
      "confluence_score": 82,
      "confluence_tier": "A",
      "active_signals": []
    }
  ],
  "alerts": [
    {
      "ticker": "BBAI",
      "severity": "critical",
      "type": "volume_climax",
      "message": "Volume climax detected — RVOL 3.2x on -8.4% day."
    }
  ],
  "watchlist": [
    {
      "ticker": "MSFT",
      "price": 388.45,
      "reason": "-18% from ATH, PE below 5Y avg"
    }
  ],
  "market_internals": {
    "sp500": { "price": 5282.70, "change_pct": -0.74 },
    "nasdaq": { "price": 16286.45, "change_pct": -0.89 },
    "vix": 29.65,
    "yield_10y": 4.33,
    "advance_decline": 0.62,
    "new_highs": 34,
    "new_lows": 187,
    "put_call_ratio": 1.12
  }
}
```

---

## 4. Frontend

### Visual Design

- **Dark terminal aesthetic** — near-black background (#0a0a0a), monospace font (JetBrains Mono), green/red for up/down, amber for highlights/tickers
- **Light mode toggle** — inverted color scheme, same layout and typography
- **Dense tiled grid** — CSS grid with `auto-fill, minmax(300px, 1fr)`, every pixel is data
- **Thin borders**, muted labels, bright values

### Panels

All panels are draggable (grab by header), snap to grid, and persist layout to localStorage.

| # | Panel | Content | Width |
|---|-------|---------|-------|
| 1 | Portfolio Value | Total equity, day P&L, unrealized P&L, cost basis, win/loss count | 1 col |
| 2 | Active Alerts | Positions with sell signals firing, severity icon, description | 1 col |
| 3 | Holdings Table | All positions: ticker, price, P&L%, RSI, Ext50MA, RVOL, signal, tag | 2 col |
| 4 | Scanner Grades | Selected stock's grades across all 47 scanners + confluence score | 1 col |
| 5 | Market Internals | S&P, NASDAQ, VIX, 10Y yield, A/D, highs/lows, P/C ratio | 1 col |
| 6 | Blue Chip Watchlist | Undervalued blue chips with price and reason | 1 col |
| 7 | Position Detail | Deep dive on clicked stock: all metrics in 2x4 grid + scanner summary | 1 col |
| 8 | Momentum Heatmap | 4-column grid of tiles colored by P&L intensity | 1 col |
| 9 | Sell Signal Matrix | Table of tickers vs signal types, filled squares for active | 1 col |
| 10 | Scan Log | Terminal-style timestamped log of scan activity | 1 col |
| 11 | Debug Log | Verbose output log for debugging (collapsible, scrollable) | 1 col |

### Interactions

- **Click ticker** in Holdings Table → Position Detail + Scanner Grades panels update to show that stock
- **SCAN button** in header → triggers scan, Scan Log streams progress
- **LOCK/UNLOCK button** → toggles panel dragging
- **Light/Dark toggle** → switches theme, persists to localStorage
- **Add position** → modal/form to add ticker, shares, cost, tag
- **Edit position** → click to edit tag (HOLD/SELL/DIV), shares, cost basis
- **Remove position** → delete from portfolio

### Theme System

CSS variables on `:root` with a `[data-theme="light"]` override:

**Dark (default):**
- Background: #0a0a0a
- Panel: #0f0f0f
- Text: #e8e6e3
- Muted: #3d3d3d
- Green: #4ec56c, Red: #e05252, Amber: #d4a843

**Light:**
- Background: #f0ede8
- Panel: #faf8f5
- Text: #1a1a1a
- Muted: #a0a0a0
- Green: #2d8a4e, Red: #c43030, Amber: #b08520

---

## 5. Backend API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve frontend HTML |
| POST | `/api/scan` | Trigger a scan, returns scan results |
| GET | `/api/latest` | Get most recent scan results |
| GET | `/api/portfolio` | Get portfolio positions and config |
| POST | `/api/portfolio` | Add a position |
| PUT | `/api/portfolio/{ticker}` | Update position (tag, shares, cost) |
| DELETE | `/api/portfolio/{ticker}` | Remove a position |
| GET | `/api/watchlist` | Get blue chip watchlist |
| PUT | `/api/watchlist` | Update watchlist tickers |
| GET | `/api/history/{ticker}` | Get OHLCV chart data for a ticker |
| GET | `/api/config` | Get app config (notification settings, scan interval) |
| PUT | `/api/config` | Update app config |

### Real-time Updates

**Server-Sent Events (SSE)** at `/api/events`:
- Scan progress messages (fetching ticker X, computing indicators, grading...)
- Scan complete with full results
- Alert notifications

SSE chosen over WebSocket because it's simpler, one-directional (server→client), and sufficient for this use case.

---

## 6. Database (SQLite)

### Tables

**positions**
```sql
CREATE TABLE positions (
  ticker TEXT PRIMARY KEY,
  shares REAL NOT NULL,
  avg_cost REAL NOT NULL,
  tag TEXT DEFAULT 'none',  -- 'hold', 'sell', 'div', 'none'
  added_at TEXT NOT NULL
);
```

**watchlist**
```sql
CREATE TABLE watchlist (
  ticker TEXT PRIMARY KEY,
  added_at TEXT NOT NULL
);
```

**scans**
```sql
CREATE TABLE scans (
  id TEXT PRIMARY KEY,
  timestamp TEXT NOT NULL,
  results_json TEXT NOT NULL
);
```

**config**
```sql
CREATE TABLE config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

---

## 7. Notifications

Optional — configured via the `/api/config` endpoint or a config panel.

**Pushover** (recommended):
- One-time $5 app purchase
- Set API token + user key in config
- Push on: critical sell signals (volume climax, bearish divergence on large positions), watchlist buy opportunities

**Telegram** (alternative):
- Free, create a bot via BotFather
- Set bot token + chat ID in config
- Same triggers as Pushover

**Notification rules:**
- Only fire once per signal per day (don't spam on every 5-min scan)
- Severity levels: `critical` (immediate push), `warning` (batched daily summary), `info` (log only)

---

## 8. Blue Chip Watchlist

A configurable list of ~25 blue chip tickers to scan for undervalued opportunities.

**Default list:** MSFT, AAPL, GOOGL, AMD, NVDA, META, TSLA, NFLX, CRM, ADBE, ORCL, AVGO, COST, WMT, JNJ, PG, V, MA, JPM, BAC, DIS, NKE, SBUX, HD, LOW

**What "undervalued" means (scanner criteria):**
- Price > 15% below 52-week high
- RSI < 40 (oversold territory)
- Trading near or below 200-day MA
- Any of the value scanners grading B+ or above (Buffett value, Lynch GARP, Munger 200W MA)

Positions that match 2+ criteria appear in the watchlist panel with a one-line reason.

---

## 9. Debug Log Panel

A dedicated panel for verbose output:
- All yfinance API calls and response times
- Indicator computation details per ticker
- Scanner pattern evaluation reasoning
- SSE connection status
- Errors and stack traces
- Collapsible (default collapsed), scrollable, monospace
- Filter by level: DEBUG, INFO, WARN, ERROR
- Clear button to reset

Backend sends debug log lines over the SSE stream tagged with level and timestamp.

---

## 10. File Structure

```
asklivermore/
  server.py              # FastAPI app, routes, scheduler
  scanner.py             # Scanner engine (refactored from fetch_signals.py)
  indicators.py          # Technical indicator computations
  grader.py              # Pattern grading logic (from extracted-prompts.md)
  notifier.py            # Pushover/Telegram notification service
  db.py                  # SQLite setup and queries
  static/
    index.html           # Single-page frontend (all CSS/JS inline)
  openscan.db            # SQLite database (created on first run)
  extracted-prompts.md   # Scanner pattern reference (existing)
  requirements.txt       # Python dependencies
```

---

## 11. Dependencies

```
fastapi
uvicorn
yfinance
pandas
aiohttp          # async HTTP for notifications
apscheduler      # background scan scheduler
```

---

## 12. Out of Scope (for v1)

- Historical performance tracking (did sell alerts actually precede drops?)
- Claude API integration for on-demand AI analysis
- Hosted/cloud deployment
- Multiple user accounts
- Options/crypto support
- Backtesting
