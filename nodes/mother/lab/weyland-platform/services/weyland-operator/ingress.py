"""Telegram long-poll ingress for the operator (B66 Part 2).

One asyncio task: getUpdates (offset-tracked) → per message → allowlist → guard-in → session-aware agent → guard-out
→ reply → persist. Blocking work (the LangGraph agent + psycopg2 session I/O) runs in asyncio.to_thread so the event
loop (and /health) stays responsive. Non-allowlisted chats are ignored silently. The offset advances BEFORE handling
so a poison message can't wedge the loop."""
import asyncio
import os
import uuid

import httpx
from prometheus_client import Counter

import agent
import session
import telegram
from guard import guard

_ALLOWED = {s.strip() for s in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if s.strip()}
_MSGS = Counter("operator_telegram_messages_total", "Telegram messages by outcome", ["outcome"])


def _allowed(chat_id: int) -> bool:
    return str(chat_id) in _ALLOWED


async def _handle(client: httpx.AsyncClient, msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    if not text:
        return
    if not _allowed(chat_id):
        _MSGS.labels("ignored").inc()
        return
    actor = f"operator:telegram:{chat_id}"
    request_id = str(uuid.uuid4())
    if await asyncio.to_thread(guard, "input", request_id, {"query": text}, actor):
        _MSGS.labels("blocked").inc()
        await telegram.send_message(client, chat_id, "⛔ Message blocked by input guard.")
        return
    history = await asyncio.to_thread(session.load, chat_id)
    try:
        reply = await asyncio.to_thread(agent.run, text, history)
    except Exception as exc:
        _MSGS.labels("error").inc()
        await telegram.send_message(client, chat_id, f"⚠️ Something went wrong: {exc}")
        return
    if await asyncio.to_thread(guard, "output", request_id, {"answer": reply, "sources": []}, actor):
        _MSGS.labels("blocked").inc()
        await telegram.send_message(client, chat_id, "⛔ Reply blocked by output guard.")
        return
    await asyncio.to_thread(session.save, chat_id, history + [("user", text), ("assistant", reply)])
    _MSGS.labels("ok").inc()
    await telegram.send_message(client, chat_id, reply)


async def poll_loop() -> None:
    """Run until cancelled: long-poll Telegram and dispatch each message sequentially (one agent run at a time —
    avoids concurrent Ollama contention)."""
    offset = 0
    async with httpx.AsyncClient() as client:
        while True:
            try:
                updates = await telegram.get_updates(client, offset)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[telegram] getUpdates failed: {exc}", flush=True)
                await asyncio.sleep(3)
                continue
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                try:
                    await _handle(client, msg)
                except Exception as exc:
                    print(f"[telegram] handle failed: {exc}", flush=True)
