"""RAG embedding service (B-RAG-STREAM step 2) — warm, rogueone, CPU.

A standing FastAPI service that holds the embedding model (EMBED_MODEL; bge-base-en-v1.5 since B74) resident and
exposes a batched /embed. The model loads ONCE at startup, so every request is warm — this is the
"embed exactly once, warm model" half of the streaming-indexer design (invariants I1, I6).

Contract (the producer is the only client):
  GET  /health          -> {"status","model","dim","device"}
  POST /embed {"texts":[str,...]} -> {"vectors":[[float,...],...],"dim":int,"model":str}

Vectors are L2-NORMALIZED (bge is trained for cosine; every vector store here uses cosine distance), so
consumers write them as-is. Native systemd service on rogueone — see services/rag-embed/rag-embed.service.
"""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
DEVICE = os.environ.get("EMBED_DEVICE", "cpu")  # CPU since 2026-09-27; see rag-embed.service
BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "64"))

app = FastAPI(title="weyland rag-embed", version="1.0")

# Load once at import (systemd starts one worker) — the warm model. An explicit device, never auto-detect: if
# EMBED_DEVICE names a device that is missing it fails fast + loud instead of silently landing somewhere else.
_model = SentenceTransformer(MODEL_NAME, device=DEVICE)
_DIM = _model.get_sentence_embedding_dimension()


class EmbedRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "dim": _DIM, "device": DEVICE}


@app.post("/embed")
def embed(req: EmbedRequest) -> dict:
    if not req.texts:
        return {"vectors": [], "dim": _DIM, "model": MODEL_NAME}
    if any(not isinstance(t, str) for t in req.texts):
        raise HTTPException(status_code=422, detail="texts must be a list of strings")
    vectors = _model.encode(
        req.texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,   # cosine stores → hand back unit vectors
        convert_to_numpy=True,
    )
    return {"vectors": vectors.tolist(), "dim": _DIM, "model": MODEL_NAME}
