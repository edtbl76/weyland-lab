from dagster import ConfigurableResource
from qdrant_client import QdrantClient


class QdrantResource(ConfigurableResource):
    host: str
    port: int = 6333

    def get_client(self) -> QdrantClient:
        # Default client timeout (~5s) chokes on a one-time full rewrite (757 docs of delete+upsert +
        # an exact orphan-count over the whole collection). 120s covers the heavy backfill; normal
        # incremental runs finish well inside it.
        return QdrantClient(host=self.host, port=self.port, timeout=120)
