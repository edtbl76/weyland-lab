"""Tests for the A2A Agent Cards — the discovery artifacts a supervisor or peer reads to address an agent.

The card shape must satisfy the A2A AgentCard contract (protocolVersion, name, url, provider.organization+url,
capabilities, skills[]), and the ``url`` must be derived from the *incoming request* origin so a card advertises
whatever host actually reached it — with a clean fallback to PUBLIC_BASE_URL and no double slashes. All pure dict
building over the roster; no server needed.
"""
import cards
import config
import roster


def test_card_has_required_a2a_fields():
    c = cards.card(roster.ROSTER[0], base="http://x")
    for field in ("protocolVersion", "name", "url", "version", "capabilities", "skills", "provider"):
        assert field in c, f"card missing {field}"
    assert c["provider"]["organization"] == "weyland" and c["provider"]["url"]
    assert c["preferredTransport"] == "JSONRPC"


def test_card_url_is_derived_from_the_request_base():
    spec = roster.BY_KEY["odin"]
    c = cards.card(spec, base="http://host:8080")
    assert c["url"] == "http://host:8080/a2a/odin"


def test_card_base_trailing_slash_is_stripped():
    c = cards.card(roster.ROSTER[0], base="http://host/")
    assert "//a2a" not in c["url"] and c["url"].startswith("http://host/a2a/")


def test_card_falls_back_to_public_base_when_no_request():
    c = cards.card(roster.ROSTER[0], base=None)
    assert c["url"].startswith(config.PUBLIC_BASE_URL.rstrip("/") + "/a2a/")


def test_card_versions_come_from_config():
    c = cards.card(roster.ROSTER[0], base="http://x")
    assert c["protocolVersion"] == config.A2A_PROTOCOL_VERSION
    assert c["version"] == config.VERSION


def test_card_describes_the_agent_from_its_spec():
    spec = roster.BY_KEY["heimdall"]
    c = cards.card(spec, base="http://x")
    assert c["name"] == spec.god and c["description"] == spec.what and c["realm"] == spec.realm
    assert c["metadata"]["lane"] == spec.lane and c["metadata"]["status"] == spec.status
    assert c["skills"] and c["skills"][0]["description"] == spec.what


def test_all_cards_is_one_per_agent():
    all_c = cards.all_cards(base="http://x")
    assert len(all_c) == len(roster.ROSTER)
    assert {c["key"] for c in all_c} == set(roster.BY_KEY)


def test_root_card_advertises_every_agent_as_a_skill():
    rc = cards.root_card(base="http://host")
    assert rc["url"] == "http://host/a2a"
    assert rc["name"] == "Realm of Agents"
    assert len(rc["skills"]) == len(roster.ROSTER)
    assert rc["provider"]["organization"] == "weyland"
