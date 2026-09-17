"""Test harness for rag-embed/app.py.

app.py loads a SentenceTransformer at module scope (the warm GPU model) and calls encode() in /embed. Stub
`sentence_transformers` before import with a fake model: fixed embedding dimension + an encode() that returns an
object with .tolist() (what the handler calls). fastapi/pydantic stay real so TestClient exercises real request
validation and responses. The real model/CUDA path is validated on the GPU host, not here.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_DIM = 384


class _Vecs:
    def __init__(self, n):
        self.n = n

    def tolist(self):
        return [[0.1] * _DIM for _ in range(self.n)]


class _FakeModel:
    def __init__(self, *a, **k):
        """No state needed — the fake model only reports a fixed embedding dimension."""

    def get_sentence_embedding_dimension(self):
        return _DIM

    def encode(self, texts, **k):
        return _Vecs(len(list(texts)))


_st = types.ModuleType("sentence_transformers")
_st.SentenceTransformer = _FakeModel
sys.modules["sentence_transformers"] = _st
