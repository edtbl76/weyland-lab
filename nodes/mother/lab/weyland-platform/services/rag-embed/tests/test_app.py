"""Tests for rag-embed — the warm embedding service. The contract the producer depends on: /health advertises the
model + dim, and /embed returns one vector per input text, an empty list for empty input, and 422 for non-string
input (never a half-broken batch). Real requests/responses via TestClient against a stubbed (dimension-fixed) model.
"""
import app as embed
from fastapi.testclient import TestClient

client = TestClient(embed.app)


def test_health_advertises_model_and_dim():
    body = client.get("/health").json()
    assert body == {"status": "ok", "model": embed.MODEL_NAME, "revision": embed.REVISION, "dim": 384, "device": embed.DEVICE}


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


# --- the model revision is pinned (B216 DoD re-audit, 2026-10-21) ------------------------------------------------------
# rag-embed is the indexer; the query side embeds with BAAI/bge-base-en-v1.5 @ a5beb1e3 (services/*/onnx_models.json).
# An unpinned load follows Hugging Face `main`: if upstream moved it, newly indexed vectors would sit in a different
# space from the queries, silently. Known models default to the pinned revision; an unknown one must name its own.
import pytest  # noqa: E402

BASE, SMALL = "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"


def test_the_model_is_built_with_the_pinned_revision():
    import sentence_transformers
    built = sentence_transformers.SentenceTransformer.built_with
    assert built.get("revision") == embed.model_revision(embed.MODEL_NAME, None)
    assert len(built["revision"]) == 40


@pytest.mark.parametrize("name,rev", [("BAAI/bge-base-en-v1.5", BASE), ("BAAI/bge-small-en-v1.5", SMALL)])
def test_known_models_default_to_the_revision_the_query_side_pins(name, rev):
    assert embed.model_revision(name, None) == rev


def test_an_explicit_revision_wins():
    assert embed.model_revision("BAAI/bge-base-en-v1.5", "b" * 40) == "b" * 40


def test_an_unknown_model_without_a_revision_refuses_to_start():
    with pytest.raises(ValueError, match="no pinned revision for some/new-model"):
        embed.model_revision("some/new-model", None)


@pytest.mark.parametrize("bad", ["main", "v1.0", "a5beb1e3"])
def test_a_revision_that_is_not_a_full_commit_hash_is_refused(bad):
    with pytest.raises(ValueError, match="40-hex"):
        embed.model_revision("BAAI/bge-base-en-v1.5", bad)


def test_health_advertises_the_revision():
    assert client.get("/health").json()["revision"] == embed.REVISION
