from dagster import ConfigurableResource
from sentence_transformers import SentenceTransformer


class SentenceTransformerResource(ConfigurableResource):
    model_name: str = "BAAI/bge-small-en-v1.5"

    def setup_for_execution(self, context) -> None:
        self._model = SentenceTransformer(self.model_name)

    def encode(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()
