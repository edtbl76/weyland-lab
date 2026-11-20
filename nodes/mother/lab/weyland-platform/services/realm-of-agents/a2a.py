"""A2A JSON-RPC transport binding (B17 front door; A2A v1 for Bifrost's Agent Gateway since B249, 2026-11-19).

The Realm's native surface is plain REST (`/route`, `/agents/{key}/message`). This module bolts the A2A JSON-RPC 2.0
binding on top. It is a thin translator: pull the text out of the A2A message, hand it to the SAME `dispatch`/`run_agent`
the REST surface uses, and wrap the answer back up as an A2A message. No agent logic lives here.

Two protocol versions on the same URLs:
  * A2A v1 — method `SendMessage`, parts `{"text": …}`, roles `ROLE_USER`/`ROLE_AGENT`, the result wrapped as
    `{"message": {...}}` (shapes from a2a-go v2.5.0, the client Bifrost's gateway uses). This is how the operator
    reaches the Realm: through Bifrost, with its own virtual key, every conversation in Bifrost's Agent Logs.
  * A2A 0.3 — method `message/send`, parts `{"kind": "text", …}`: direct callers such as the a2a-inspector.

Spend (B209: the Realm spends nothing unless the caller is entitled). Both methods run FREE-ONLY, except a v1 call that
asks for paid (`metadata.allow_paid` is true) AND carries the token Bifrost sends on every call it forwards to the Realm
(`X-Realm-Gateway-Token`, the registration's `runtime_auth`; the same secret is `REALM_GATEWAY_TOKEN` here). Bifrost
grants the Realm only to the operator's key, so the token means "the operator, through the gateway". Until 2026-11-19
this binding never entered free_only, so every A2A call ran on the paid lane: a gap against B209, closed here.

The A2A context id is the dispatch's session id (made when the caller sends none and returned in the reply), so
Langfuse and Bifrost's Agent Logs key a conversation alike.

Endpoints, mirroring the cards:
  POST /a2a          → Gná dispatches to the best-fit agent (the root card)
  POST /a2a/{key}    → one specific agent answers (a per-agent card)
"""
import hmac
import os
import uuid
from contextlib import nullcontext

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import router as gna
from budget import free_only
from roster import BY_KEY

router = APIRouter()

GATEWAY_TOKEN = os.getenv("REALM_GATEWAY_TOKEN", "")
GATEWAY_HEADER = "X-Realm-Gateway-Token"
V1, V03 = "SendMessage", "message/send"


def _text(message: dict, v1: bool) -> str:
    """The concatenated text parts of an A2A message: v1 `{"text": …}`, 0.3 `{"kind": "text", "text": …}`."""
    parts = (message or {}).get("parts") or []
    if v1:
        texts = [p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
    else:
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("kind") == "text"]
    return " ".join(texts).strip()


def _paid(request: Request, message: dict) -> bool:
    """Paid only for a v1 call through the gateway that asks for it (see the module docstring)."""
    asked = ((message or {}).get("metadata") or {}).get("allow_paid") is True
    sent = request.headers.get(GATEWAY_HEADER, "")
    return asked and bool(GATEWAY_TOKEN) and hmac.compare_digest(sent.encode(), GATEWAY_TOKEN.encode())


def _rpc_error(rpc_id, code: int, message: str):
    # JSON-RPC transport errors ride at HTTP 200 with an `error` object (per JSON-RPC 2.0 / A2A).
    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})


def _who(key: str) -> dict:
    spec = BY_KEY[key]
    return {"routed_to": key, "god": spec.god, "role": spec.role, "realm": spec.realm}


async def _handle(request: Request, key: str | None):
    try:
        body = await request.json()
    except Exception:
        return _rpc_error(None, -32700, "Parse error")
    rpc_id, method = body.get("id"), body.get("method")
    if method not in (V1, V03):
        # capabilities.streaming is False and there are no tasks, so only the two send methods exist.
        return _rpc_error(rpc_id, -32601, f"Method not found: {method}")
    v1 = method == V1
    message = (body.get("params") or {}).get("message") or {}
    text = _text(message, v1)
    if not text:
        return _rpc_error(rpc_id, -32602, "Invalid params: message has no text part")
    if key is not None and key not in BY_KEY:
        return _rpc_error(rpc_id, -32602, f"Invalid params: no agent '{key}'")
    context_id = (message.get("contextId") or uuid.uuid4().hex) if v1 else None
    try:
        with nullcontext() if (v1 and _paid(request, message)) else free_only():
            if key is None:
                chosen, answer = await gna.dispatch(text, None, session_id=context_id)
            else:
                chosen, answer = key, await gna.run_agent(BY_KEY[key], text, None, session_id=context_id)
    except Exception as exc:  # a run failure is an application error, not a protocol one
        return _rpc_error(rpc_id, -32603, f"Internal error: {exc}")
    if v1:
        reply = {"messageId": uuid.uuid4().hex, "contextId": context_id, "role": "ROLE_AGENT",
                 "parts": [{"text": answer}], "metadata": _who(chosen)}
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"message": reply}}
    reply = {"role": "agent", "parts": [{"kind": "text", "text": answer}], "messageId": uuid.uuid4().hex,
             "kind": "message"}
    return {"jsonrpc": "2.0", "id": rpc_id, "result": reply}


@router.post("/a2a")
async def a2a_root(request: Request):
    """Root A2A endpoint — Gná classifies and runs the best-fit agent."""
    return await _handle(request, None)


@router.post("/a2a/{key}")
async def a2a_agent(request: Request, key: str):
    """Per-agent A2A endpoint — the named agent answers directly."""
    return await _handle(request, key)
