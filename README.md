# OpenScan / AnyhowTrade

Portfolio terminal dashboard with real-time US market data via Moomoo OpenD. Scans your holdings against technical indicators, surfaces sell/buy signals, detects volume trend shifts, and gives you a PB EMA structural read — all from the command line or a dark web dashboard.

## What It Does

- Fetches real-time stock data from Moomoo OpenD (not delayed Yahoo data)
- Computes RSI, MACD, Bollinger Bands, moving averages, volume analysis
- Detects 10 sell signals and 10 buy signals per position
- Detects volume trend shifts: fading rallies, building momentum, distribution
- PB EMA analysis: 200 EMA of Highs (upper) and Closes (lower) on Daily + 4H
- Auto-adds flagged positions to moomoo watchlists (claude.sell, claude.watch)
- Grades positions with health scores and plain English verdicts
- Scans a blue chip watchlist for undervalued opportunities
- Auto-scans every 5 minutes during market hours
- Push notifications via Pushover or Telegram

## Requirements

- macOS
- Python 3.10+
- [Moomoo account](https://www.moomoo.com) (free, for OpenD access)
- [Moomoo OpenD](https://www.moomoo.com/download/OpenAPI) installed in `/Applications/moomoo_OpenD.app`

## Setup (first time)

```bash
git clone https://github.com/mandlcho/anyhowtrade.git openscan
cd openscan

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Seed your portfolio into the database
python3 seed.py
```

Edit `seed.py` to match your actual positions before running it.

## Usage

```bash
./start.sh
```

That's it. The script will:

1. Launch Moomoo OpenD (if not already running)
2. Wait for OpenD to connect (if it needs login, it'll pause for you)
3. Start the OpenScan server on `http://localhost:3000`
4. Open the dashboard in your browser

Press `Ctrl+C` to stop.

## Claude Code Slash Commands

This project ships with Claude Code slash commands for terminal-based analysis. Run them by typing `/commandname` in a Claude Code session from the project root.

### `/sellcheck`

Runs 10 sell signals across all current positions. Stocks with 6+ signals are auto-added to the `claude.sell` moomoo watchlist. Also detects **volume fading** (price up >3% in 5 days but RVOL dropping) and auto-adds those to `claude.watch`.

**10 sell signals checked:**
1. RSI overbought (>70) + rolling over
2. Bearish divergence
3. MACD bearish crossover
4. MACD histogram contracting 3+ bars
5. Heavy distribution day (RVOL >1.5x, red candle)
6. Price below 10 MA
7. Price below 21 EMA
8. Close in lower 20% of range
9. Bollinger Band upper rejection
10. Overextended >15% above 50 MA

### `/buycheck [tickers]`

Runs 10 buy signals. Defaults to Mag 7 (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA) or any tickers you pass. Stocks with 6+ signals are auto-added to `claude.buy`.

**10 buy signals checked:**
1. RSI oversold (<40) + turning up
2. Bullish divergence
3. MACD bullish crossover
4. MACD histogram expanding bullish 3+ bars
5. Heavy accumulation day (RVOL >1.5x, green candle)
6. Price reclaims 10 MA
7. Price reclaims 21 EMA
8. Close in upper 80% of range
9. Bollinger Band lower bounce
10. Pullback to 50 MA support (within 3%)

### `/pb [tickers]`

PB EMA scanner — 200-period EMA of Highs (upper band) and Closes (lower band) on Daily and 4H timeframes. Fetches live data from OpenD, prints the last 3 candles per timeframe, and applies a 9-label structural classification.

**9 PB EMA labels:**
1. Heading toward PB EMA
2. Bouncing off PB EMA
3. Falling below PB EMA
4. Reclaiming PB EMA
5. Breaking out above PB EMA
6. Breaking out below PB EMA
7. Wick-through and rejection at PB EMA
8. Trading inside PB EMA band
9. Failed reclaim of PB EMA

No tickers = scans all positions from `latest_scan.json`. Pass tickers to scan specific stocks.

### `/watch [add|remove|list] [tickers]`

Manage the `claude.watch` moomoo watchlist.

```
/watch             → list current watchlist
/watch MSFT        → add MSFT
/watch add MSFT AAPL
/watch remove MSFT
```

## Dashboard

Dark terminal-style UI inspired by [Clark Moody's Bitcoin Dashboard](https://dashboard.clarkmoody.com/).

**12 draggable panels:**

| Panel | What It Shows |
|-------|--------------|
| Portfolio Value | Total equity, day P&L, unrealized P&L |
| Active Alerts | Positions with sell/buy signals firing |
| Holdings Table | All positions sorted by urgency — action label, health bar, verdict |
| Scanner Grades | Minervini trend template + confluence score for selected stock |
| Market Internals | SPY, QQQ, VIX with price and change |
| Blue Chip Watchlist | Undervalued opportunities from a configurable list |
| High Volume | Stocks trading >7M shares — momentum filter |
| Position Detail | Deep dive metrics including VOL TREND + candlestick chart |
| Momentum Heatmap | Visual P&L grid |
| Sell Signal Matrix | Which signals are firing on which stocks |
| Scan Log | Terminal-style scan activity |
| Debug Log | Verbose output for troubleshooting |

- Drag panels by their header to rearrange (layout persists)
- Lock/unlock button to prevent accidental moves
- Light/dark theme toggle
- Click any ticker row for detailed view + chart

## Volume Trend Detection

Every position scan now includes a **VOL TREND** indicator:

| Label | Condition |
|-------|-----------|
| FADING | Price up >3% in 5 days, but 3-day RVOL <0.7x and declining |
| BUILDING | Price up >3% in 5 days with 3-day RVOL >1.2x |
| DIST | Price down >3% in 5 days with 3-day RVOL >1.2x (distribution) |
| NEUTRAL | None of the above |

Fading positions are auto-flagged in `/sellcheck` and added to `claude.watch`.

## How Signals Work

OpenScan evaluates 10 sell criteria and 10 buy criteria independently per position.

**When 6+ criteria align** → signal triggers. These are suggestions, not orders. The dashboard explains each signal in plain English.

**Action labels:**
- **SELL** — Multiple serious concerns. Worth considering reducing the position.
- **WATCH** — Some yellow flags. Keep an eye on it.
- **HOLD** — Looking healthy. No reason to touch it.
- **ADD** — Pulling back while healthy. Potential entry opportunity.

## Notifications (optional)

Configure push notifications via the config API:

```bash
# Pushover (one-time $5 app)
curl -X PUT http://localhost:3000/api/config \
  -H "Content-Type: application/json" \
  -d '{"pushover_token": "YOUR_TOKEN", "pushover_user": "YOUR_USER_KEY"}'

# Or Telegram (free)
curl -X PUT http://localhost:3000/api/config \
  -H "Content-Type: application/json" \
  -d '{"telegram_token": "YOUR_BOT_TOKEN", "telegram_chat_id": "YOUR_CHAT_ID"}'
```

Notifications fire once per signal per day (no spam on 5-min scans).

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard |
| POST | `/api/scan` | Trigger a scan |
| GET | `/api/latest` | Most recent scan results |
| GET | `/api/portfolio` | List positions |
| POST | `/api/portfolio` | Add position |
| DELETE | `/api/portfolio/{ticker}` | Remove position |
| GET | `/api/watchlist` | List watchlist |
| PUT | `/api/watchlist` | Update watchlist |
| GET | `/api/history/{ticker}` | 1 year OHLCV chart data |
| GET | `/api/events` | SSE stream (live scan updates) |

## Data Source

Real-time data via [Moomoo OpenD](https://openapi.moomoo.com/moomoo-api-doc/en/) running locally on `localhost:11111`. Supports US stocks and options chain data (IV, Greeks, delta, theta).

## Pine Scripts

The `pine/` directory contains TradingView Pine Script indicators:

- `mtf_bias.pine` — Multi-timeframe bias ruleset (ported to `mtf_bias.py`)
