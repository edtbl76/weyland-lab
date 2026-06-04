import psycopg2
import psycopg2.extras
from dagster import ConfigurableResource


class PostgresResource(ConfigurableResource):
    host: str
    port: int = 5432
    dbname: str
    user: str
    password: str

    def get_connection(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
        )
