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
JWKS_URL = os.environ["KEYCLOAK_JWKS_URL"]                 # https://keycloak.weyland.lab/realms/weyland/protocol/openid-connect/certs
ISSUER = os.environ["KEYCLOAK_ISSUER"]                     # https://keycloak.weyland.lab/realms/weyland
AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE") or None     # optional; Keycloak often sets aud=account, so default off
ACTOR_CLAIM = os.environ.get("ACTOR_CLAIM", "azp")         # client_credentials → azp = the agent's client_id
ALLOWED_PREFIXES = ("/mcp-act", "/mcp",                    # the MCP mounts (order: /mcp-act before /mcp — both start "/mcp")
                    "/pipeline/trigger", "/evals/run", "/evals/score")  # + the tool-server act endpoints the operator
                                                          #   calls directly (not via MCP) — routed here for a verified actor

# Hop-by-hop / identity headers we never forward upstream. `authorization` + `x-forwarded-consumer` are dropped so the
# ONLY actor the tool-server sees is the one WE set from the validated token (a client can't smuggle its own).
_DROP_REQ = {"host", "authorization", "x-forwarded-consumer", "content-length", "connection", "transfer-encoding"}
_DROP_RESP = {"content-length", "connection", "transfer-encoding", "content-encoding"}

_jwks = PyJWKClient(JWKS_URL)                              # fetches + caches the realm signing keys
_client = httpx.AsyncClient(timeout=httpx.Timeout(None), follow_redirects=False)


def _actor_from_bearer(request: Request) -> str | None:
    """Validate the Bearer JWT (signature via JWKS + issuer + exp) and return the actor claim. Raises on bad token."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    signing_key = _jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token, signing_key, algorithms=["RS256"], issuer=ISSUER,
        audience=AUDIENCE, options={"verify_aud": AUDIENCE is not None},
    )
    return claims.get(ACTOR_CLAIM) or claims.get("preferred_username") or claims.get("sub")


async def _proxy(request: Request) -> StreamingResponse | JSONResponse:
    path = request.url.path
    if not any(path == p or path.startswith(p + "/") or path.startswith(p) for p in ALLOWED_PREFIXES):
        return JSONResponse({"error": "not found"}, status_code=404)

    try:
        actor = _actor_from_bearer(request)
    except Exception as exc:                              # bad/expired/forged token → 401, never 500
        return JSONResponse({"error": "unauthorized", "detail": str(exc)}, status_code=401)
    if not actor:
        return JSONResponse({"error": "unauthorized", "detail": "missing/invalid Bearer token"}, status_code=401)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQ}
    headers["X-Forwarded-Consumer"] = actor              # the whole point — set from the VALIDATED claim

    upstream = _client.build_request(
        request.method,
        # read /mcp → the compositor (aggregated read-only fleet) when configured; acts (/mcp-act, /pipeline, /evals) → tool-server.
        (COMPOSITOR if (COMPOSITOR and (path == "/mcp" or path.startswith("/mcp/"))) else TOOL_SERVER) + path,
        headers=headers,
        content=request.stream(), params=request.query_params,
    )
    resp = await _client.send(upstream, stream=True)     # stream both ways (MCP Streamable-HTTP is SSE-capable)
    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _DROP_RESP}   # keeps content-type
    return StreamingResponse(
        resp.aiter_raw(), status_code=resp.status_code, headers=out_headers,
        background=BackgroundTask(resp.aclose),          # close the upstream stream once the client finishes
    )


async def _health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


app = Starlette(routes=[
    Route("/health", _health),
    Route("/mcp-act/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp-act", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp/{path:path}", _proxy, methods=["GET", "POST", "DELETE"]),
    Route("/mcp", _proxy, methods=["GET", "POST", "DELETE"]),
    # tool-server act endpoints the operator posts to directly — proxied so the gateway sets the verified actor.
    Route("/pipeline/trigger", _proxy, methods=["POST"]),
    Route("/evals/run", _proxy, methods=["POST"]),
    Route("/evals/score", _proxy, methods=["POST"]),
])
