"""Tests for fleet.load_fleet_tools' three outcomes (2026-10-02).

The caller must tell "not configured" (run without the fleet, by design) from "configured but failed" (retry, and do
not report Ready). Before this, both returned [] — and a Keycloak mint failure printed "OPERATOR_CLIENT_SECRET unset"
while the secret was in fact set, so the live operator ran 31h blind with a log line pointing at the wrong cause.
"""
import fleet


def test_no_client_secret_is_not_configured_and_returns_an_empty_fleet(monkeypatch, capsys):
    monkeypatch.setattr(fleet, "CLIENT_SECRET", "")
    assert fleet.load_fleet_tools() == []
    assert "unset" in capsys.readouterr().out


def test_a_secret_whose_token_cannot_be_minted_is_a_failure_to_retry_not_an_empty_fleet(monkeypatch, capsys):
    monkeypatch.setattr(fleet, "CLIENT_SECRET", "s3cret")
    monkeypatch.setattr(fleet, "_token", lambda: None)
    assert fleet.load_fleet_tools() is None
    out = capsys.readouterr().out
    assert "Keycloak" in out and "unset" not in out
