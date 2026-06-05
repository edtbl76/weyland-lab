import weaviate
from dagster import ConfigurableResource


class WeaviateResource(ConfigurableResource):
    host: str
    port: int = 8080
    grpc_port: int = 50051

    def get_client(self) -> weaviate.WeaviateClient:
        return weaviate.connect_to_custom(
            http_host=self.host,
            http_port=self.port,
            http_secure=False,
            grpc_host=self.host,
            grpc_port=self.grpc_port,
            grpc_secure=False,
        )
