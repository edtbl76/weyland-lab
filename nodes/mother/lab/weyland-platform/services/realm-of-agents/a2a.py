"""A2A JSON-RPC transport binding (B17 — the UI-spike front door).

The Realm's native surface is plain REST (`/route`, `/agents/{key}/message`). This module bolts the A2A-Protocol
JSON-RPC 2.0 binding on top so any *standard* A2A client — e.g. the `a2a-inspector` — can discover a card and send it a
`message/send`. It is a thin translator, nothing more: pull the text out of the A2A message envelope, hand it to the
SAME `dispatch`/`run_agent` the REST surface already uses, and wrap the answer back up as an A2A `Message`. No agent
logic lives here, and the REST endpoints are untouched (the operator's `delegate_to_realm` keeps POSTing `/route`).

Two endpoints, mirroring the two cards:
  POST /a2a          → Gná dispatches to the best-fit agent (the root card's `url`)
  POST /a2a/{key}    → one specific agent answers (a per-agent card's `url`)
"""
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import router as gna
from roster import BY_KEY

router = APIRouter()


def _text_from_params(params: dict) -> str:
    """Extract the concatenated text of an A2A message's text parts (`params.message.parts[].text`)."""
    message = (params or {}).get("message") or {}
    parts = message.get("parts") or []
    return " ".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and p.get("kind") == "text"
    ).strip()


def _agent_message(text: str) -> dict:
    """A2A `Message` (kind='message') — the synchronous reply shape for a completed `message/send`."""
    return {"role": "agent", "parts": [{"kind": "text", "text": text}], "messageId": uuid.uuid4().hex, "kind": "message"}


def _rpc_error(rpc_id, code: int, message: str):
    # JSON-RPC transport errors ride at HTTP 200 with an `error` object (per JSON-RPC 2.0 / A2A).
    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})


async def _handle(request: Request, key: str | None):
    try:
        body = await request.json()
    except Exception:
        return _rpc_error(None, -32700, "Parse error")
    rpc_id = body.get("id")
    method = body.get("method")
    if method != "message/send":
        # We advertise capabilities.streaming=False, so message/stream and anything else is unsupported.
        return _rpc_error(rpc_id, -32601, f"Method not found: {method}")
    text = _text_from_params(body.get("params"))
    if not text:
        return _rpc_error(rpc_id, -32602, "Invalid params: message has no text part")
    try:
        if key is None:
            _, answer = await gna.dispatch(text, None)
        else:
            spec = BY_KEY.get(key)
            if not spec:
                return _rpc_error(rpc_id, -32602, f"Invalid params: no agent '{key}'")
            answer = await gna.run_agent(spec, text, None)
    except Exception as exc:  # a run failure is an application error, not a protocol one
        return _rpc_error(rpc_id, -32603, f"Internal error: {exc}")
    return {"jsonrpc": "2.0", "id": rpc_id, "result": _agent_message(answer)}


@router.post("/a2a")
async def a2a_root(request: Request):
    """Root A2A endpoint — Gná classifies and runs the best-fit agent."""
    return await _handle(request, None)


@router.post("/a2a/{key}")
async def a2a_agent(request: Request, key: str):
    """Per-agent A2A endpoint — the named agent answers directly."""
    return await _handle(request, key)
