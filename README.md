# OpenScan

Portfolio terminal dashboard with real-time US market data via Moomoo OpenD. Scans your holdings against technical indicators and scanner patterns, surfaces sell/buy signals in plain English, and tells you what needs attention.

## What It Does

- Fetches real-time stock data from Moomoo OpenD (not delayed Yahoo data)
- Computes RSI, MACD, Bollinger Bands, moving averages, volume analysis
- Detects sell signals (bearish divergence, volume climax, trend breaks)
- Grades positions with health scores and plain English verdicts
- Fires **synergy alerts** when 5+ criteria align for sell or buy
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

## Dashboard

Dark terminal-style UI inspired by [Clark Moody's Bitcoin Dashboard](https://dashboard.clarkmoody.com/).

**11 draggable panels:**

| Panel | What It Shows |
|-------|--------------|
| Portfolio Value | Total equity, day P&L, unrealized P&L |
| Active Alerts | Positions with sell/buy synergy signals firing |
| Holdings Table | All positions sorted by urgency — action label, health bar, verdict |
| Scanner Grades | Minervini trend template + confluence score for selected stock |
| Market Internals | SPY, QQQ, VIX with price and change |
| Blue Chip Watchlist | Undervalued opportunities from a configurable list |
| Position Detail | Deep dive metrics + candlestick chart for selected stock |
| Momentum Heatmap | Visual P&L grid |
| Sell Signal Matrix | Which signals are firing on which stocks |
| Scan Log | Terminal-style scan activity |
| Debug Log | Verbose output for troubleshooting |

- Drag panels by their header to rearrange (layout persists)
- Lock/unlock button to prevent accidental moves
- Light/dark theme toggle
- Click any ticker row for detailed view + chart
- Add/remove positions from the UI

## How Signals Work

OpenScan evaluates 13 sell criteria and 13 buy criteria independently:

**When 5+ criteria align** → synergy alert fires. These are suggestions, not orders. The dashboard explains each signal in plain English and always makes clear it's your call.

**Action labels:**
- **SELL** — Multiple serious concerns. Worth considering reducing the position.
- **WATCH** — Some yellow flags. Keep an eye on it, but no rush.
- **HOLD** — Looking healthy. No reason to touch it.
- **ADD** — Pulling back while healthy. Could be a good entry if you believe in it.

## Notifications (optional)

Configure push notifications in the dashboard via the config API:

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

Real-time data via [Moomoo OpenD](https://openapi.moomoo.com/moomoo-api-doc/en/) running locally. Requires OpenD gateway on `localhost:11111`. Supports US stocks, with future potential for options chain data (IV, Greeks).

## Pine Scripts

The `pine/` directory contains TradingView Pine Script indicators preserved from the original repo:

- `mtf_bias.pine` — Multi-timeframe bias ruleset
