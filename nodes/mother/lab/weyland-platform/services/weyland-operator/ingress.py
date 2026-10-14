"""Telegram long-poll ingress for the operator (B66 Part 2).

One asyncio task: getUpdates (offset-tracked) → per message → allowlist (the sender, B209) → guard-in → session-aware agent → guard-out
→ reply → persist. Blocking work (the LangGraph agent + psycopg2 session I/O) runs in asyncio.to_thread so the event
loop (and /health) stays responsive. Messages from people not on the allowlist are ignored silently. The offset advances BEFORE handling
so a poison message can't wedge the loop."""
import asyncio
import os
import uuid

import httpx
from prometheus_client import Counter

import act
import agent
import session
import telegram
from guard import guard

# B209 (2026-10-14): the allowlist names PEOPLE (Telegram user ids), checked on every message against `from.id`. It used
# to match the chat id, so in an allowlisted group any member's "yes" fired a pending act. A private chat's id equals its
# user's id, so a pre-B209 private-chat entry still admits that person. Group chats are admitted only when listed in
# TELEGRAM_ALLOWED_CHATS, and the sender must still be an allowed user.
_USERS = {s.strip() for s in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if s.strip()}
_CHATS = {s.strip() for s in os.getenv("TELEGRAM_ALLOWED_CHATS", "").split(",") if s.strip()}
_MSGS = Counter("operator_telegram_messages_total", "Telegram messages by outcome", ["outcome"])
_AFFIRM = {"yes", "y", "yep", "yeah", "yup", "confirm", "ok", "okay", "sure", "go", "do it", "proceed"}
_NEGATE = {"no", "n", "nope", "cancel", "stop", "abort", "nvm", "nevermind", "never mind"}


def _sender(msg: dict) -> int | None:
    """The allowed person who sent `msg`, or None. Refuses a message with no sender (a channel post) and one sent as an
    anonymous group admin (`sender_chat` set): no person, no authority. In a group, the chat must also be listed."""
    sender = msg.get("from") or {}
    uid = sender.get("id")
    if uid is None or msg.get("sender_chat") or str(uid) not in _USERS:
        return None
    chat = msg.get("chat") or {}
    if chat.get("type") == "private":
        return uid if chat.get("id") == uid else None
    return uid if str(chat.get("id")) in _CHATS else None


async def _handle(client: httpx.AsyncClient, msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    if not text:
        return
    uid = _sender(msg)
    if uid is None:
        _MSGS.labels("ignored").inc()
        return
    actor = f"operator:telegram:{uid}"
    history, pending = await asyncio.to_thread(session.load, chat_id)
    low = text.strip().lower()

    # Confirm-step: a pending proposal awaits yes/no. The APP fires (not the LLM) — only on an explicit yes.
    if pending:
        if low in _AFFIRM:
            result = await asyncio.to_thread(act.fire, pending, actor)
            await asyncio.to_thread(session.save, chat_id, history + [("user", text), ("assistant", result)], None)
            _MSGS.labels("acted").inc()
            await telegram.send_message(client, chat_id, result)
            return
        if low in _NEGATE:
            await asyncio.to_thread(session.save, chat_id, history + [("user", text), ("assistant", "Cancelled.")], None)
            _MSGS.labels("cancelled").inc()
            await telegram.send_message(client, chat_id, "Cancelled — nothing was run.")
            return
        pending = None   # neither yes nor no → user moved on; drop the stale proposal, handle as a fresh message

    request_id = str(uuid.uuid4())
    if await asyncio.to_thread(guard, "input", request_id, {"query": text}, actor):
        _MSGS.labels("blocked").inc()
        await telegram.send_message(client, chat_id, "⛔ Message blocked by input guard.")
        return
    try:
        # session_id = Telegram chat_id → every message in a chat groups into one Langfuse session
        reply, proposal = await agent.run(text, history, session_id=str(chat_id), user_id=actor)   # async — fleet MCP tools are async-only
    except Exception as exc:
        _MSGS.labels("error").inc()
        await telegram.send_message(client, chat_id, f"⚠️ Something went wrong: {exc}")
        return

    if proposal and proposal.get("tool"):
        prompt = f"⚠️ Confirm: {act.describe(proposal)}\n\nReply *yes* to run or *no* to cancel."
        if await asyncio.to_thread(guard, "output", request_id, {"answer": prompt, "sources": []}, actor):
            _MSGS.labels("blocked").inc()
            await telegram.send_message(client, chat_id, "⛔ Reply blocked by output guard.")
            return
        await asyncio.to_thread(session.save, chat_id, history + [("user", text), ("assistant", prompt)], proposal)
        _MSGS.labels("proposed").inc()
        await telegram.send_message(client, chat_id, prompt)
        return

    if await asyncio.to_thread(guard, "output", request_id, {"answer": reply, "sources": []}, actor):
        _MSGS.labels("blocked").inc()
        await telegram.send_message(client, chat_id, "⛔ Reply blocked by output guard.")
        return
    await asyncio.to_thread(session.save, chat_id, history + [("user", text), ("assistant", reply)], None)
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
