"""Tests for rag-embed — the warm embedding service. The contract the producer depends on: /health advertises the
model + dim, and /embed returns one vector per input text, an empty list for empty input, and 422 for non-string
input (never a half-broken batch). Real requests/responses via TestClient against a stubbed (dimension-fixed) model.
"""
import app as embed
from fastapi.testclient import TestClient

client = TestClient(embed.app)


def test_health_advertises_model_and_dim():
    body = client.get("/health").json()
    assert body == {"status": "ok", "model": embed.MODEL_NAME, "dim": 384, "device": embed.DEVICE}


def test_embed_empty_texts_returns_empty_vectors():
    body = client.post("/embed", json={"texts": []}).json()
    assert body == {"vectors": [], "dim": 384, "model": embed.MODEL_NAME}


def test_embed_returns_one_vector_per_text():
    body = client.post("/embed", json={"texts": ["alpha", "beta", "gamma"]}).json()
    assert len(body["vectors"]) == 3
    assert all(len(v) == 384 for v in body["vectors"])
    assert body["dim"] == 384 and body["model"] == embed.MODEL_NAME


def test_embed_rejects_non_string_items_with_422():
    # A nested list is not a str under any pydantic version (int could lax-coerce under v1), so this is a
    # stable assertion that non-string input never reaches encode() as a half-valid batch.
    r = client.post("/embed", json={"texts": ["ok", ["nope"]]})
    assert r.status_code == 422
