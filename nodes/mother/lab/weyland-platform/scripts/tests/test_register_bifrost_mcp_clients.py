"""Tests for register_bifrost_mcp_clients.py — the request bodies it sends to Bifrost's `POST /api/mcp/client`.

2026-11-11 (B192): Bifrost v2 rejects an OAuth client without an `oauth_config` block (live: 400 "OAuth configuration is
required when auth_type is 'oauth'"). Linear and Hugging Face had been created on an older Bifrost without one, so a
restore from git would have failed for both. Their OAuth values below match the live clients (read 2026-11-11).
"""
import register_bifrost_mcp_clients as r


def _by_name():
    return {name: r.http_body(name, url, auth) for name, url, auth in r.HTTP}


def test_every_oauth_client_carries_an_oauth_config(monkeypatch):
    monkeypatch.setenv("GITHUB_MCP_OAUTH_CLIENT_ID", "Ov23-test-client")
    for name, body in _by_name().items():
        if body["auth_type"] == "oauth":
            cfg = body.get("oauth_config")
            assert cfg, f"{name}: oauth client without oauth_config (Bifrost v2 rejects it with a 400)"
            assert cfg.get("registration_url") or cfg.get("client_id"), f"{name}: neither DCR nor a client id"


def test_github_without_its_client_id_is_refused_by_name_not_posted(monkeypatch):
    monkeypatch.delenv("GITHUB_MCP_OAUTH_CLIENT_ID", raising=False)
    body = _by_name()["GitHub_Remote"]

    class NoPost:
        def post(self, path, json):
            raise AssertionError("a broken OAuth client must not be posted")

    ok, line = r.create(NoPost(), set(), "GitHub_Remote", body)
    assert ok is False and "GITHUB_MCP_OAUTH_CLIENT_ID" in line


def test_an_existing_client_is_left_alone():
    class NoPost:
        def post(self, path, json):
            raise AssertionError("existing clients are never re-posted")

    assert r.create(NoPost(), {"Jam"}, "Jam", {"name": "Jam"}) == (True, f"{'Jam':14} EXISTS")


def test_no_auth_clients_send_no_oauth_config():
    for name, body in _by_name().items():
        if body["auth_type"] == "none":
            assert "oauth_config" not in body, name


def test_jam_token_is_read_scoped_and_uses_dynamic_registration():
    jam = _by_name()["Jam"]
    assert jam["connection_string"] == {"value": "https://mcp.jam.dev/mcp", "type": "plain_text"}
    cfg = jam["oauth_config"]
    assert cfg["scopes"] == ["mcp:read"]                  # the token itself cannot write
    assert cfg["registration_url"] == "https://api.jam.dev/oauth/register"
    assert "client_id" not in cfg and "client_secret" not in cfg   # DCR + PKCE: no secret in git or the cluster


def test_linear_and_hugging_face_match_their_live_oauth_settings():
    by = _by_name()
    assert by["Linear"]["oauth_config"]["registration_url"] == "https://mcp.linear.app/register"
    assert by["Linear"]["oauth_config"]["scopes"] == ["read", "write"]
    assert by["Hugging_Face"]["oauth_config"]["registration_url"] == "https://huggingface.co/oauth/register"


def test_a_failed_create_makes_the_run_fail():
    class Resp:
        status_code, text = 400, '{"error":"OAuth configuration is required"}'

        def json(self):
            return {}

    class Fake:
        def post(self, path, json):
            return Resp()

    ok, line = r.create(Fake(), set(), "Jam", {"name": "Jam"})
    assert ok is False and "FAILED" in line


def test_an_oauth_create_prints_where_to_authorize():
    class Resp:
        status_code, text = 200, ""

        def json(self):
            return {"status": "pending_oauth", "authorize_url": "https://api.jam.dev/oauth/authorize?x=1",
                    "complete_url": "/api/mcp/client/cfg1/complete-oauth"}

    class Fake:
        def post(self, path, json):
            return Resp()

    ok, line = r.create(Fake(), set(), "Jam", {"name": "Jam"})
    assert ok is True
    assert "authorize: https://api.jam.dev/oauth/authorize?x=1" in line
    assert "complete-oauth" in line
