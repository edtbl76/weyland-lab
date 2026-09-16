"""Test harness for weyland-tool-server.

main.py runs as a flat module and, at import time, does three things that need handling before it can load in
a bare test env: it calls ``sentry_sdk.init``, it calls ``validate_required_secrets()`` (which raises unless the
DB/Neo4j password env vars are set), and it builds two ``FastMCP.from_fastapi(app).http_app()`` sub-apps and
mounts them. So here we: put the service dir on ``sys.path``; set the required secret env vars; and stub the
heavy client libraries (psycopg2 / weaviate / neo4j / qdrant_client / sentry_sdk / fastmcp) that are imported at
module scope. onnxruntime/tokenizers are imported lazily inside ``OnnxBge`` and never touched here.

The real deps we KEEP (fastapi/httpx/pydantic/prometheus_client) are what the tests assert against — TestClient
responses, real Prometheus output, real Verdict objects. Backends are stubbed per-test and asserted by the shape
of what the handler returns, never "a mock was called". The live store/LLM round-trips are validated in the
running system.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# validate_required_secrets() runs at import and raises without these.
os.environ.setdefault("WEYLAND_DB_PASSWORD", "test-pw")
os.environ.setdefault("NEO4J_PASSWORD", "test-pw")


def _mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# sentry_sdk.init(...) runs at module scope — make it a no-op.
_mod("sentry_sdk", init=lambda *a, **k: None)

# DB / vector-store / graph clients: imported at module scope, only USED inside functions (which tests
# monkeypatch). The annotations `qdrant_client.QdrantClient` / `weaviate.WeaviateClient` are evaluated at
# import, so the classes must exist as attributes.
_mod("psycopg2", connect=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db in tests")))
_mod("qdrant_client", QdrantClient=type("QdrantClient", (), {}))
_neo4j = _mod("neo4j", GraphDatabase=type("GraphDatabase", (), {}))
weaviate = _mod("weaviate", WeaviateClient=type("WeaviateClient", (), {}))
_mod("weaviate.classes")
_mod("weaviate.classes.query", MetadataQuery=type("MetadataQuery", (), {"__init__": lambda self, **k: None}))

# FastMCP: from_fastapi(app).http_app() is built + mounted at module scope. Return a real (empty) Starlette
# app so app.mount() gets a valid ASGI app; the MCP surface itself is not under test here.


class _FastMCP:
    @classmethod
    def from_fastapi(cls, app, **k):
        return cls()

    def http_app(self, **k):
        from starlette.applications import Starlette
        return Starlette()


_mod("fastmcp", FastMCP=_FastMCP)
_mod("fastmcp.server")
_mod("fastmcp.server.providers")
_mod(
    "fastmcp.server.providers.openapi",
    RouteMap=lambda **k: None,
    MCPType=type("MCPType", (), {"TOOL": "TOOL", "EXCLUDE": "EXCLUDE"}),
)
