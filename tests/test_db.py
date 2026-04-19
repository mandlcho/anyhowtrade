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
