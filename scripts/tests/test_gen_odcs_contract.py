"""Tests for gen_odcs_contract.py — builds an ODCS v3 DataContract from a live table + dbt/soda metadata (B157).

The contract feeds the ODCS gates and the catalog, so its SHAPE is load-bearing: the right apiVersion/kind, one
property per column with logicalType/physicalType/description, the soda rules as quality (or a safe default), and the
medallion/source custom properties. The I/O sources (Trino columns, dbt schema.yml, soda checks) are stubbed so the
assembly LOGIC is what's asserted — no live Trino/files.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import gen_odcs_contract as g


# ── _logical: physical → logical type parsing ────────────────────────────────────────────────────────
def test_logical_is_case_insensitive_and_strips_params():
    assert g._logical("BIGINT") == g._logical("bigint")            # case-folded
    assert g._logical("varchar(255)") == g._logical("varchar")     # parameter stripped
    assert g._logical("decimal(10, 2)") == g._logical("decimal")


def test_logical_unknown_type_defaults_to_string():
    assert g._logical("some_exotic_udt") == "string"


# ── build_contract: the ODCS assembly ────────────────────────────────────────────────────────────────
def _stub_sources(monkeypatch, cols, descs=None, model_desc="", rules=None):
    monkeypatch.setattr(g, "trino_columns", lambda c, s, t: cols)
    monkeypatch.setattr(g, "dbt_descriptions", lambda d, t: (descs or {}, model_desc))
    monkeypatch.setattr(g, "soda_rules", lambda d, t: rules or [])


def test_build_contract_shape_and_properties(monkeypatch):
    _stub_sources(monkeypatch,
                  cols=[("track_id", "bigint"), ("name", "varchar(200)")],
                  descs={"track_id": "the track id"}, model_desc="Music tracks mart",
                  rules=["row_count > 0", "duplicate_count(track_id) = 0"])
    c = g.build_contract("music", "music_tracks", "iceberg.datasets_music.tracks", "cid-1", "gold", "spotify")

    assert c["apiVersion"] == "v3.0.0" and c["kind"] == "DataContract"
    assert c["id"] == "cid-1" and c["domain"] == "music" and c["dataProduct"] == "music_tracks"
    assert c["description"]["purpose"] == "Music tracks mart"           # dbt model desc wins
    props = c["schema"][0]["properties"]
    assert [p["name"] for p in props] == ["track_id", "name"]           # ordinal order preserved
    assert props[0]["physicalType"] == "bigint" and props[0]["description"] == "the track id"
    assert "description" not in props[1]                                 # undocumented column → no desc key
    assert c["quality"] == [{"property": "table", "rule": "row_count > 0"},
                            {"property": "table", "rule": "duplicate_count(track_id) = 0"}]
    assert c["servers"][0]["physicalName"] == "iceberg.datasets_music.tracks"
    cp = {x["property"]: x["value"] for x in c["customProperties"]}
    assert cp["medallion_layer"] == "gold" and cp["source_system"] == "spotify"


def test_build_contract_defaults_purpose_and_quality_when_metadata_absent(monkeypatch):
    _stub_sources(monkeypatch, cols=[("x", "integer")])                 # no descs, no model_desc, no soda rules
    c = g.build_contract("health", "hp", "iceberg.h.t", "cid-2", "silver", "cdc")
    assert c["description"]["purpose"] == "The hp data product of the health domain."   # fallback purpose
    assert c["quality"] == [{"property": "table", "rule": "row_count > 0"}]              # safe default rule


# ── to_yaml: serialization round-trips ───────────────────────────────────────────────────────────────
def test_to_yaml_round_trips(monkeypatch):
    import yaml
    _stub_sources(monkeypatch, cols=[("id", "bigint")])
    c = g.build_contract("music", "p", "a.b.c", "cid", "bronze", "src")
    assert yaml.safe_load(g.to_yaml(c)) == c                            # emitted YAML reparses to the same contract


# ── B233: the Trino read authenticates (HTTPS + password, the lab CA) ────────────────────────────────
class _Resp:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        import json
        return json.dumps(self._body).encode()


def _capture(monkeypatch, body):
    seen = []

    def fake_urlopen(req, timeout=None, context=None):
        seen.append((req, context))
        return _Resp(body)
    monkeypatch.setattr(g.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_trino_reads_send_basic_auth_over_a_verifying_tls_context(monkeypatch, tmp_path):
    import base64
    import ssl
    ca = tmp_path / "ca.pem"
    ca.write_text("")
    monkeypatch.setenv("TRINO_USER", "dbt")
    monkeypatch.setenv("TRINO_PASSWORD", "pw-123")
    monkeypatch.setattr(g, "_ca_context", lambda: ssl.create_default_context())
    seen = _capture(monkeypatch, {"data": [["c", "varchar"]]})
    assert g.trino_columns("iceberg", "dbt", "t") == [("c", "varchar")]
    req, ctx = seen[0]
    assert req.full_url == "https://trino.data-mesh.svc.cluster.local:8443/v1/statement"
    assert req.get_header("Authorization") == "Basic " + base64.b64encode(b"dbt:pw-123").decode()
    assert req.get_header("X-trino-user") is None              # never a self-asserted user
    assert ctx is not None and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_trino_read_without_a_password_fails_closed(monkeypatch):
    import pytest
    monkeypatch.setenv("TRINO_USER", "dbt")
    monkeypatch.delenv("TRINO_PASSWORD", raising=False)
    seen = _capture(monkeypatch, {})
    with pytest.raises(RuntimeError, match="TRINO_PASSWORD is not set"):
        g.trino_columns("iceberg", "dbt", "t")
    assert seen == []


def test_the_ca_context_loads_the_lab_ca_path(monkeypatch):
    loaded = []

    class _Ctx:
        def load_verify_locations(self, cafile=None):
            loaded.append(cafile)
    monkeypatch.setattr(g.ssl, "create_default_context", lambda: _Ctx())
    monkeypatch.setenv("TRINO_CA", "/etc/weyland-ca/rootCA.pem")
    ctx = g._ca_context()
    assert loaded == ["/etc/weyland-ca/rootCA.pem"]
    assert ctx.minimum_version == g.ssl.TLSVersion.TLSv1_2   # an explicit floor (Sonar S4423), not the library default

