"""Minimal Telegram Bot API client — long-poll getUpdates + sendMessage over raw httpx (B66 Part 2).

No python-telegram-bot: the operator only needs these two calls, and owning the loop keeps the ingress explicit and
the dependency surface small. Long-poll is outbound-only (getUpdates holds the connection open), so it works from the
LAN with no inbound webhook."""
import os

import httpx

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_API_BASE = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
_POLL_TIMEOUT = int(os.getenv("TELEGRAM_POLL_TIMEOUT", "30"))
_MAX_LEN = 4096   # Telegram hard cap per message


def _url(method: str) -> str:
    return f"{_API_BASE}/bot{_TOKEN}/{method}"


def configured() -> bool:
    """True if a bot token is set — the ingress only starts when it is."""
    return bool(_TOKEN)


async def get_updates(client: httpx.AsyncClient, offset: int) -> list[dict]:
    """Long-poll for updates since `offset`. Returns the raw update dicts (possibly empty). The HTTP read timeout
    exceeds the server-side long-poll so a quiet period isn't mistaken for a failure."""
    r = await client.get(_url("getUpdates"),
                         params={"offset": offset, "timeout": _POLL_TIMEOUT},
                         timeout=_POLL_TIMEOUT + 10)
    r.raise_for_status()
    return r.json().get("result", [])


async def send_message(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    """Send a text reply (truncated to Telegram's 4096-char cap)."""
    if len(text) > _MAX_LEN:
        text = text[:_MAX_LEN - 16] + "\n…(truncated)"
    r = await client.post(_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=30)
    r.raise_for_status()
