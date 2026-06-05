from dagster import ConfigurableResource
from qdrant_client import QdrantClient


class QdrantResource(ConfigurableResource):
    host: str
    port: int = 6333

    def get_client(self) -> QdrantClient:
        return QdrantClient(host=self.host, port=self.port)
