"""bge embedder on raw ONNX Runtime (U13) — a SentenceTransformer-compatible drop-in for the bge family.

Replaces `sentence_transformers.SentenceTransformer` for the two embedding paths in this service (the
`SentenceTransformerResource` KB embedder = bge-base/768, and the datasets_lib vector-store hydrator =
bge-small/384). bge pooling is CLS token ([:,0]) + L2 normalize; verified byte-equivalent to
sentence-transformers (cosine 1.0), so the hydrated pgvector/Qdrant/Weaviate/Neo4j/LanceDB vectors need NO
re-embedding. Runtime deps: onnxruntime + tokenizers + numpy only (torch/transformers/sentence-transformers
gone). Mirrors the OnnxBge class in weyland-tool-server/main.py + weyland-agent/retrievers.py — same math,
here with a SentenceTransformer-shaped `.encode()` because these call sites use the SentenceTransformer API.

This is a pure leaf (no dagster import), so tests/conftest.py `load_isolated` can load callers that import it
without the dagster runtime (see .importlinter)."""
import os

# HF model name → baked ONNX export dir (Dockerfile builder stage writes both). Env-overridable for local runs.
ONNX_MODEL_DIRS = {
    "BAAI/bge-base-en-v1.5": os.environ.get("BGE_BASE_ONNX_DIR", "/app/bge_onnx_base"),
    "BAAI/bge-small-en-v1.5": os.environ.get("BGE_SMALL_ONNX_DIR", "/app/bge_onnx_small"),
}


class OnnxEmbedder:
    """SentenceTransformer-shaped bge embedder. `encode(str)` → 1-D np array; `encode(list[str])` → 2-D np
    array — so `.tolist()` and `[v.tolist() for v in vecs]` at the call sites both keep working unchanged."""

    def __init__(self, model_name: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        model_dir = ONNX_MODEL_DIRS.get(model_name, model_name)   # accept a raw dir too
        self._sess = ort.InferenceSession(f"{model_dir}/model.onnx", providers=["CPUExecutionProvider"])
        self._tok = Tokenizer.from_file(f"{model_dir}/tokenizer.json")
        self._tok.enable_truncation(max_length=512)
        self._tok.enable_padding()   # pad within each batch → rectangular tensors for batched inference
        self._names = [i.name for i in self._sess.get_inputs()]

    def encode(self, sentences, normalize_embeddings: bool = True, batch_size: int = 64,
               show_progress_bar: bool = False, **_ignored):
        """SentenceTransformer.encode-compatible. Extra kwargs (convert_to_numpy, device, …) are ignored."""
        import numpy as np
        single = isinstance(sentences, str)
        texts = [sentences] if single else list(sentences)
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        out = []
        for i in range(0, len(texts), batch_size):
            encs = self._tok.encode_batch(texts[i:i + batch_size])
            avail = {"input_ids": [e.ids for e in encs],
                     "attention_mask": [e.attention_mask for e in encs],
                     "token_type_ids": [e.type_ids for e in encs]}
            feed = {n: np.array(avail[n], dtype=np.int64) for n in self._names}
            cls = self._sess.run(None, feed)[0][:, 0]     # (b, seq, dim) -> CLS token -> (b, dim)
            if normalize_embeddings:
                cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.append(cls.astype(np.float32))
        arr = np.concatenate(out, axis=0)
        return arr[0] if single else arr
