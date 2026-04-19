import pytest
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
