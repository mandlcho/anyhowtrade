"""Push notification service for OpenScan. Supports Pushover and Telegram."""

import aiohttp


def format_alert_message(alert):
    severity = alert["severity"].upper()
    return f"[{severity}] {alert['ticker']}: {alert['message']}"


def should_notify(severity, seen_today, ticker=None, signal_type=None):
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
