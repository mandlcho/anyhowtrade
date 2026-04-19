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
