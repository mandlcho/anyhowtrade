"""FastAPI server for OpenScan — REST API, SSE, and background scheduler."""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from db import (
    init_db,
    add_position,
    get_positions,
    update_position,
    delete_position,
    get_watchlist,
    set_watchlist,
    save_scan,
    get_latest_scan,
    get_config,
    set_config,
)
from scanner import run_scan
from notifier import Notifier


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_db_path: str = os.environ.get("OPENSCAN_DB", "openscan.db")
_sse_clients: list[asyncio.Queue] = []
_notifier: Optional[Notifier] = None
_scan_lock: Optional[asyncio.Lock] = None
_scheduler = None

DEFAULT_WATCHLIST = [
    "MSFT", "AAPL", "GOOGL", "AMD", "NVDA", "META", "TSLA", "NFLX",
    "CRM", "ADBE", "ORCL", "AVGO", "COST", "WMT", "JNJ", "PG",
    "V", "MA", "JPM", "BAC", "DIS", "NKE", "SBUX", "HD", "LOW",
]

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------

def init_app(db_path: str):
    """Initialize application state — database, notifier, seed watchlist."""
    global _db_path, _notifier, _scan_lock

    _db_path = db_path
    _scan_lock = asyncio.Lock()

    # Build notifier from config
    pushover_token = get_config(db_path, "pushover_token")
    pushover_user = get_config(db_path, "pushover_user")
    telegram_token = get_config(db_path, "telegram_token")
    telegram_chat_id = get_config(db_path, "telegram_chat_id")
    _notifier = Notifier(
        pushover_token=pushover_token,
        pushover_user=pushover_user,
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
    )

    # Seed default watchlist if empty
    if not get_watchlist(db_path):
        set_watchlist(db_path, DEFAULT_WATCHLIST)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler

    db_path = os.environ.get("OPENSCAN_DB", "openscan.db")
    init_db(db_path)
    init_app(db_path)

    # Start background scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _scheduled_scan,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*/5",
                timezone="America/New_York",
            ),
        )
        _scheduler.start()
    except Exception:
        pass  # Scheduler is optional — don't break startup

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# SSE broadcast helper
# ---------------------------------------------------------------------------

async def _broadcast(event: str, data):
    payload = json.dumps(data, default=str)
    msg = f"event: {event}\ndata: {payload}\n\n"
    for q in list(_sse_clients):
        try:
            await q.put(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Scheduled scan
# ---------------------------------------------------------------------------

async def _scheduled_scan():
    global _scan_lock, _db_path, _notifier

    if _scan_lock is None:
        return

    async with _scan_lock:
        loop = asyncio.get_event_loop()
        positions = get_positions(_db_path)
        watchlist_tickers = get_watchlist(_db_path)

        log_msgs = []

        def log_cb(level, msg):
            log_msgs.append({"level": level, "message": msg})
            asyncio.run_coroutine_threadsafe(
                _broadcast("log", {"level": level, "message": msg}),
                loop,
            )

        results = await loop.run_in_executor(
            None,
            lambda: run_scan(positions, watchlist_tickers, log_callback=log_cb),
        )

        save_scan(_db_path, results["scan_id"], results)
        await _broadcast("scan_complete", results)

        # Send notifications
        if _notifier and _notifier.is_configured():
            for alert in results.get("alerts", []):
                await _notifier.send_alert(alert)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PositionIn(BaseModel):
    ticker: str
    shares: float
    avg_cost: float
    tag: Optional[str] = "none"


class PositionUpdate(BaseModel):
    shares: Optional[float] = None
    avg_cost: Optional[float] = None
    tag: Optional[str] = None


class WatchlistIn(BaseModel):
    tickers: list[str]


class ConfigIn(BaseModel):
    scan_interval: Optional[str] = None
    pushover_token: Optional[str] = None
    pushover_user: Optional[str] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes — Frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index = STATIC_DIR / "index.html"
    return HTMLResponse(content=index.read_text(), status_code=200)


# ---------------------------------------------------------------------------
# Routes — Portfolio
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
async def api_get_portfolio():
    return get_positions(_db_path)


@app.post("/api/portfolio")
async def api_add_position(body: PositionIn):
    add_position(_db_path, body.ticker, body.shares, body.avg_cost, body.tag or "none")
    positions = get_positions(_db_path)
    for p in positions:
        if p["ticker"] == body.ticker.upper():
            return p
    return {"ticker": body.ticker.upper()}


@app.put("/api/portfolio/{ticker}")
async def api_update_position(ticker: str, body: PositionUpdate):
    update_position(_db_path, ticker, shares=body.shares, avg_cost=body.avg_cost, tag=body.tag)
    return {"ok": True}


@app.delete("/api/portfolio/{ticker}")
async def api_delete_position(ticker: str):
    delete_position(_db_path, ticker)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — Watchlist
# ---------------------------------------------------------------------------

@app.get("/api/watchlist")
async def api_get_watchlist():
    return get_watchlist(_db_path)


@app.put("/api/watchlist")
async def api_set_watchlist(body: WatchlistIn):
    set_watchlist(_db_path, body.tickers)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — Config
# ---------------------------------------------------------------------------

CONFIG_KEYS = [
    "scan_interval",
    "pushover_token",
    "pushover_user",
    "telegram_token",
    "telegram_chat_id",
]


@app.get("/api/config")
async def api_get_config():
    return {k: get_config(_db_path, k) for k in CONFIG_KEYS}


@app.put("/api/config")
async def api_set_config(body: ConfigIn):
    global _notifier
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        set_config(_db_path, key, value)

    # Rebuild notifier if credentials changed
    _notifier = Notifier(
        pushover_token=get_config(_db_path, "pushover_token"),
        pushover_user=get_config(_db_path, "pushover_user"),
        telegram_token=get_config(_db_path, "telegram_token"),
        telegram_chat_id=get_config(_db_path, "telegram_chat_id"),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — Scan
# ---------------------------------------------------------------------------

@app.post("/api/scan")
async def api_trigger_scan():
    global _scan_lock, _db_path

    loop = asyncio.get_event_loop()
    positions = get_positions(_db_path)
    watchlist_tickers = get_watchlist(_db_path)

    log_msgs = []

    def log_cb(level, msg):
        log_msgs.append({"level": level, "message": msg})

    results = await loop.run_in_executor(
        None,
        lambda: run_scan(positions, watchlist_tickers, log_callback=log_cb),
    )

    save_scan(_db_path, results["scan_id"], results)
    await _broadcast("scan_complete", results)
    return results


@app.get("/api/latest")
async def api_get_latest():
    return get_latest_scan(_db_path)


# ---------------------------------------------------------------------------
# Routes — History
# ---------------------------------------------------------------------------

@app.get("/api/history/{ticker}")
async def api_get_history(ticker: str):
    import yfinance as yf

    loop = asyncio.get_event_loop()

    def fetch():
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period="1y")
        records = []
        for ts, row in hist.iterrows():
            records.append({
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            })
        return records

    return await loop.run_in_executor(None, fetch)


# ---------------------------------------------------------------------------
# Routes — SSE
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def api_events(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            _sse_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=3000, reload=True)
