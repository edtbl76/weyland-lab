"""How every Dagster call reaches Trino (B233, 2026-10-23).

Trino authenticates now: a password, and only over HTTPS (8443, a cert from the lab's mkcert CA). Before B233 every
caller self-asserted X-Trino-User on plain HTTP, so Ranger's per-user policies could be bypassed by claiming a
privileged name. The pod's login is `dbt` (TRINO_USER / TRINO_PASSWORD from the `trino-dbt` Secret; the lab CA from
`weyland-mkcert-ca` at /etc/weyland-ca). Read at call time, so a test or a run can set them late. Dagster-free on
purpose: the mart export and scripts/feast_setup.py both import it.
"""
import os

_HOST = "trino.data-mesh.svc.cluster.local"
_CA = "/etc/weyland-ca/rootCA.pem"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set: Trino takes a password only (B233); the pod needs the trino-dbt Secret")
    return value


def ca_path() -> str:
    return os.environ.get("TRINO_CA", _CA)


def connect(catalog: str = "iceberg", schema: str = "dbt"):
    """A DB-API connection to Trino as the pod's own identity, TLS verified against the lab CA."""
    import trino

    user, password = _required("TRINO_USER"), _required("TRINO_PASSWORD")
    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", _HOST), port=int(os.environ.get("TRINO_HTTPS_PORT", "8443")),
        user=user, catalog=catalog, schema=schema, http_scheme="https",
        auth=trino.auth.BasicAuthentication(user, password), verify=ca_path(),
    )


def subprocess_env() -> dict:
    """The environment for the Soda and GE subprocesses: their Trino clients take no CA option, so the lab CA goes in
    REQUESTS_CA_BUNDLE for that process only (the pod's own calls to public HTTPS keep the default bundle)."""
    env = dict(os.environ)
    env["REQUESTS_CA_BUNDLE"] = ca_path()
    return env
