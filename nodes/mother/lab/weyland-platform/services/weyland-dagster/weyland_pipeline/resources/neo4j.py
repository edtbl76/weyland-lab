from dagster import ConfigurableResource
from neo4j import GraphDatabase, Driver


class Neo4jResource(ConfigurableResource):
    uri: str
    user: str
    password: str

    def get_driver(self) -> Driver:
        return GraphDatabase.driver(self.uri, auth=(self.user, self.password))
