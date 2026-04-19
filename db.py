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
