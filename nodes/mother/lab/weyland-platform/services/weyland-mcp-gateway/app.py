"""weyland-mcp-gateway — the B17+B19 MCP gateway (Phase 1: the server edge).

A thin auth reverse-proxy in front of the tool-server's MCP mounts. It does exactly three things the tool-server
can't do for itself, and nothing more:

  1. AUTHENTICATE — require a Keycloak-issued Bearer JWT (validated against the realm JWKS). Un-authed → 401.
  2. INJECT THE ACTOR — set `X-Forwarded-Consumer` = the token's actor claim (default `azp` = the client_id of a
     client_credentials agent), STRIPPING any client-supplied value (anti-spoof). The tool-server already reads that
     header into `guardrail_verdicts.actor` (the B14 seam), so verified identity flows downstream with zero
     tool-server change — and that real actor is what unblocks the enforcing act policy gate (Phase 2).
  3. PASS THROUGH — stream the raw MCP Streamable-HTTP (JSON-RPC / SSE) to the backend `/mcp` (read) + `/mcp-act`
     (act) mounts, unchanged.

  /mcp-memory (B182, 2026-10-04) → a memory-ONLY compositor (the shared agent memory's 7 read tools). Built for Open
  WebUI, which forwards EACH PERSON'S own Keycloak token (`system_oauth`) — so a human caller is identified as
  themselves: X-Forwarded-User = the validated `preferred_username` (machine/service-account tokens carry none).
  Per-user identity instead of a shared Bifrost virtual key, and no stored secret.

NOT FastMCP: FastMCP is for *composing* MCP servers, and its proxy middleware can't inject a derived upstream header
(the one thing we need). FastMCP is held for later multi-server composition (see the design doc). This is a
single-backend auth-front, which is a reverse-proxy, ~not~ an MCP server.
"""
import os

import httpx
import jwt
from jwt import PyJWKClient
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, StreamingResponse
from starlette.routing import Route

TOOL_SERVER = os.environ["TOOL_SERVER_URL"].rstrip("/")   # http://weyland-tool-server.weyland.svc:8080
COMPOSITOR = (os.environ.get("COMPOSITOR_URL") or "").rstrip("/")   # if set, READ /mcp routes to the FastMCP compositor
                                                          #   (aggregated read-only fleet); acts stay on TOOL_SERVER.
MEMORY = (os.environ.get("MEMORY_COMPOSITOR_URL") or "").rstrip("/")   # /mcp-memory → the memory-only compositor;
                                                          #   unset → /mcp-memory is a 404 (never the tool-server).
JWKS_URL = os.environ["KEYCLOAK_JWKS_URL"]                 # https://keycloak.weyland.lab/realms/weyland/protocol/openid-connect/certs
ISSUER = os.environ["KEYCLOAK_ISSUER"]                     # https://keycloak.weyland.lab/realms/weyland
AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE") or None     # optional; Keycloak often sets aud=account, so default off
ACTOR_CLAIM = os.environ.get("ACTOR_CLAIM", "azp")         # client_credentials → azp = the agent's client_id
FLEET_PATH = "/mcp-fleet"                                 # → COMPOSITOR (the read-only fleet)
MEMORY_PATH = "/mcp-memory"                               # → MEMORY (the memory-only compositor)
ALLOWED_PREFIXES = (FLEET_PATH, MEMORY_PATH, "/mcp-act", "/mcp",     # /mcp-fleet → compositor (read fleet); /mcp-act + /mcp → tool-server
                    "/pipeline/trigger", "/evals/run", "/evals/score")  # + the tool-server act endpoints the operator
                                                          #   calls directly (not via MCP) — routed here for a verified actor

# Hop-by-hop / identity headers we never forward upstream. `authorization` + `x-forwarded-consumer` are dropped so the
# ONLY actor the tool-server sees is the one WE set from the validated token (a client can't smuggle its own).
_DROP_REQ = {"host", "authorization", "x-forwarded-consumer", "x-forwarded-user", "content-length", "connection",
             "transfer-encoding"}
_DROP_RESP = {"content-length", "connection", "transfer-encoding", "content-encoding"}

_jwks = PyJWKClient(JWKS_URL)                              # fetches + caches the realm signing keys
_client = httpx.AsyncClient(timeout=httpx.Timeout(None), follow_redirects=False)


def _claims_from_bearer(request: Request) -> dict | None:
    """Validate the Bearer JWT (signature via JWKS + issuer + exp) and return its claims; None if there is no Bearer.
    Raises on a bad token."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    signing_key = _jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(
        token, signing_key, algorithms=["RS256"], issuer=ISSUER,
        audience=AUDIENCE, options={"verify_aud": AUDIENCE is not None},
    )


def identity(claims: dict) -> tuple[str | None, str | None]:
    """(actor, user) from validated claims. actor = the client the caller came through (`azp` by default — unchanged,
    policy.gate keys on it). user = the person (`preferred_username`), or None for a machine: Keycloak names a
    client_credentials token's user `service-account-<client>`, which is the client again, not a person."""
    actor = claims.get(ACTOR_CLAIM) or claims.get("preferred_username") or claims.get("sub")
    user = claims.get("preferred_username")
    if not user or user.startswith("service-account-"):
        user = None
    return actor, user


def target_url(path: str) -> str | None:
    """The backend URL for `path`, or None when its backend is not configured (→ 404)."""
    if path.startswith(FLEET_PATH) and COMPOSITOR:
        return COMPOSITOR + "/mcp" + path[len(FLEET_PATH):]
    if path.startswith(MEMORY_PATH):
        return MEMORY + "/mcp" + path[len(MEMORY_PATH):] if MEMORY else None
    return TOOL_SERVER + path


def _logfmt(value) -> str:
    """A logfmt value: `-` for none, quoted (with escapes) when it holds a space, quote, `=` or backslash."""
    if value is None or value == "":
        return "-"
    v = str(value)
    if any(c in v for c in ' "=\\'):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def audit_line(method: str, path: str, actor, user, status: int) -> str:
    """The structured audit record for one request (2026-10-05): who reached which backend, and the outcome.
    Same shape as `pr-lifecycle-audit` — a tag + logfmt — so Loki can `|= "mcp-gateway-audit" | logfmt`."""
    return (f"mcp-gateway-audit method={_logfmt(method)} path={_logfmt(path)} actor={_logfmt(actor)} "
            f"user={_logfmt(user)} status={status}")


async def _proxy(request: Request) -> StreamingResponse | JSONResponse:
    """Every request — forwarded or denied — leaves exactly one audit line. actor/user come only from the validated
    token (`_handle`), never from a header the client sent."""
    resp, actor, user = await _handle(request)
    print(audit_line(request.method, request.url.path, actor, user, resp.status_code), flush=True)
    return resp


async def _handle(request: Request) -> tuple:
    """(response, actor, user). actor/user are None until the token has been validated."""
    path = request.url.path
    if not any(path == p or path.startswith(p + "/") or path.startswith(p) for p in ALLOWED_PREFIXES):
        return JSONResponse({"error": "not found"}, status_code=404), None, None

    try:
        claims = _claims_from_bearer(request)
    except Exception as exc:                              # bad/expired/forged token → 401, never 500
        return JSONResponse({"error": "unauthorized", "detail": str(exc)}, status_code=401), None, None
    actor, user = identity(claims) if claims else (None, None)
    if not actor:
        return (JSONResponse({"error": "unauthorized", "detail": "missing/invalid Bearer token"}, status_code=401),
                None, None)

    # /mcp-fleet → the compositor (aggregated read-only fleet), /mcp-memory → the memory-only compositor, each
    # rewritten to its /mcp mount. Everything else — RAG reads (/mcp) and acts (/mcp-act, /pipeline, /evals) — goes
    # to the tool-server.
    url = target_url(path)
    if url is None:
        return (JSONResponse({"error": "not found", "detail": f"{path} has no backend configured"}, status_code=404),
                actor, user)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQ}
    headers["X-Forwarded-Consumer"] = actor              # the whole point — set from the VALIDATED claim
    if user:
        headers["X-Forwarded-User"] = user               # the person, for a human token; absent for a machine
    upstream = _client.build_request(
        request.method, url, headers=headers,
        content=request.stream(), params=request.query_params,
    )
    resp = await _client.send(upstream, stream=True)     # stream both ways (MCP Streamable-HTTP is SSE-capable)
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _DROP_RESP}   # keeps content-type
    return StreamingResponse(
        resp.aiter_raw(), status_code=resp.status_code, headers=out_headers,
        background=BackgroundTask(resp.aclose),          # close the upstream stream once the client finishes
    ), actor, user


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Starlette(routes=[
    Route("/health", _health),
    Route(FLEET_PATH + "/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route(FLEET_PATH, _proxy, methods=["GET", "POST", "DELETE"]),
    Route(MEMORY_PATH + "/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route(MEMORY_PATH, _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp-act/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp-act", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp", _proxy, methods=["GET", "POST", "DELETE"]),
    # tool-server act endpoints the operator posts to directly — proxied so the gateway sets the verified actor.
    Route("/pipeline/trigger", _proxy, methods=["POST"]),
    Route("/evals/run", _proxy, methods=["POST"]),
    Route("/evals/score", _proxy, methods=["POST"]),
])
