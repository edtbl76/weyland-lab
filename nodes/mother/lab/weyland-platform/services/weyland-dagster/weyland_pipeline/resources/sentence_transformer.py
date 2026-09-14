from dagster import ConfigurableResource

from .onnx_embedder import OnnxEmbedder


class SentenceTransformerResource(ConfigurableResource):
    model_name: str = "BAAI/bge-base-en-v1.5"   # B74: 768-dim (was bge-small 384) for conceptual retrieval resolution

    def setup_for_execution(self, context) -> None:
        # U13: raw ONNX Runtime, byte-equivalent to the old SentenceTransformer(model_name). Name kept for the
        # dagster resource key + the many `sentence_transformer:` asset params that reference it.
        self._model = OnnxEmbedder(self.model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """B105: encode a whole list in ONE model call (internally mini-batched) instead of one call per chunk —
        turns a multi-hour per-chunk CPU re-embed into minutes. `show_progress_bar` prints a periodic tqdm line to
        stderr, visible in the Dagster op's compute logs (the observability half of B105)."""
        if not texts:
            return []
        return self._model.encode(
            texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True
        ).tolist()
