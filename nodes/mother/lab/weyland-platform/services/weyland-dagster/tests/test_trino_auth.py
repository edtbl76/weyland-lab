"""Every Dagster call to Trino authenticates (B233, 2026-10-23).

Trino now takes a password, and only over HTTPS (8443, a cert from the lab's mkcert CA): plain HTTP stops trusting
X-Trino-User at the cutover. A call site that still dials :8080 without a credential works until that cutover and then
fails only at run time (the mart export, the Feast offline load). These load each caller with its heavy imports
stubbed (the slim test lane has no trino, dagster, pandas or pyarrow) and record what it hands the Trino client.
"""
import importlib.util
import os
import sys
import types

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weyland-dagster/


def _module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


class _Basic:
    def __init__(self, user, password):
        self.user, self.password = user, password


@pytest.fixture
def trino_stub(monkeypatch):
    calls = []
    dbapi = _module("trino.dbapi", connect=lambda **kw: calls.append(kw) or "conn")
    auth = _module("trino.auth", BasicAuthentication=_Basic)
    monkeypatch.setitem(sys.modules, "trino", _module("trino", dbapi=dbapi, auth=auth))
    monkeypatch.setitem(sys.modules, "trino.dbapi", dbapi)
    monkeypatch.setitem(sys.modules, "trino.auth", auth)
    monkeypatch.setenv("TRINO_USER", "dbt")
    monkeypatch.setenv("TRINO_PASSWORD", "pw-123")
    monkeypatch.delenv("TRINO_HOST", raising=False)
    monkeypatch.delenv("TRINO_CA", raising=False)
    return calls


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, relpath))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def ta(trino_stub, monkeypatch):
    pkg = _module("weyland_pipeline")
    pkg.__path__ = [os.path.join(_ROOT, "weyland_pipeline")]
    monkeypatch.setitem(sys.modules, "weyland_pipeline", pkg)
    monkeypatch.delitem(sys.modules, "weyland_pipeline.trino_auth", raising=False)
    return _load("weyland_pipeline/trino_auth.py", "weyland_pipeline.trino_auth")


def _assert_authenticated(kw, catalog="iceberg", schema="dbt"):
    assert kw["host"] == "trino.data-mesh.svc.cluster.local"
    assert kw["port"] == 8443 and kw["http_scheme"] == "https"
    assert kw["verify"] == "/etc/weyland-ca/rootCA.pem"       # the lab CA, never verify=False
    assert isinstance(kw["auth"], _Basic) and (kw["auth"].user, kw["auth"].password) == ("dbt", "pw-123")
    assert kw["user"] == "dbt"                                 # the session user IS the principal (Ranger {USER})
    assert (kw["catalog"], kw["schema"]) == (catalog, schema)


def test_connect_is_https_verified_and_authenticated(ta, trino_stub):
    assert ta.connect() == "conn"
    _assert_authenticated(trino_stub[0])


def test_connect_passes_catalog_and_schema(ta, trino_stub):
    ta.connect(catalog="postgresql", schema="public")
    _assert_authenticated(trino_stub[0], "postgresql", "public")


def test_a_missing_password_fails_closed_naming_the_secret(ta, trino_stub, monkeypatch):
    monkeypatch.delenv("TRINO_PASSWORD")
    with pytest.raises(RuntimeError, match="TRINO_PASSWORD is not set.*trino-dbt"):
        ta.connect()
    assert trino_stub == []                                    # never a silent no-auth connection


def test_subprocess_env_adds_the_ca_bundle_only_to_a_copy(ta, monkeypatch):
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    env = ta.subprocess_env()
    assert env["REQUESTS_CA_BUNDLE"] == "/etc/weyland-ca/rootCA.pem"
    assert env["TRINO_PASSWORD"] == "pw-123"
    assert "REQUESTS_CA_BUNDLE" not in os.environ              # the pod's own public-TLS calls keep certifi


def test_the_mart_export_connects_through_trino_auth(ta, trino_stub, monkeypatch):
    for name in ("pandas", "pyarrow", "pyarrow.parquet"):
        monkeypatch.setitem(sys.modules, name, _module(name))
    monkeypatch.setitem(sys.modules, "dagster", _module(
        "dagster", MetadataValue=object, Output=object,
        asset=lambda *a, **k: (a[0] if a and callable(a[0]) and not k else (lambda f: f))))
    assets = _module("weyland_pipeline.assets")
    assets.__path__ = [os.path.join(_ROOT, "weyland_pipeline", "assets")]
    monkeypatch.setitem(sys.modules, "weyland_pipeline.assets", assets)
    lib = _module("weyland_pipeline.assets.datasets_lib", io=_module("io"))
    monkeypatch.setitem(sys.modules, "weyland_pipeline.assets.datasets_lib", lib)
    me = _load("weyland_pipeline/assets/mart_export.py", "weyland_pipeline.assets.mart_export")
    me._trino_conn()
    _assert_authenticated(trino_stub[0])


def test_the_feast_offline_load_connects_through_trino_auth(ta, trino_stub, monkeypatch):
    monkeypatch.setenv("WEYLAND_PG_PASSWORD", "unused")   # feast_setup reads it at import
    for name in ("pandas", "sqlalchemy"):
        monkeypatch.setitem(sys.modules, name, _module(name))
    assets = _module("weyland_pipeline.assets")
    assets.__path__ = []
    monkeypatch.setitem(sys.modules, "weyland_pipeline.assets", assets)
    monkeypatch.setitem(sys.modules, "weyland_pipeline.assets.datasets_lib",
                        _module("weyland_pipeline.assets.datasets_lib", io=_module("io")))
    fs = _load("scripts/feast_setup.py", "feast_setup_under_test")
    fs._trino_conn()
    _assert_authenticated(trino_stub[0])
