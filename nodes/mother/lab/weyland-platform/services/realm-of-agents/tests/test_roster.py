"""Tests for the roster — the single source of truth in code for every agent (mirrors the a2a-agent-roster doc).

The router, the A2A cards, and the runnable graphs are all built from ``ROSTER``, so its integrity is load-bearing:
keys must be unique, every realm must be a known realm, and a lead's ``members`` must name agents that actually exist
(a dangling member key silently breaks delegation). ``in_realm`` and ``fallback_prompt`` are the two pure helpers
callers use, and both are exercised here independent of any runtime.
"""
import roster
import roles


def test_roster_keys_are_unique():
    keys = [a.key for a in roster.ROSTER]
    assert len(keys) == len(set(keys)), "duplicate agent key in ROSTER"


def test_by_key_indexes_every_agent():
    assert set(roster.BY_KEY) == {a.key for a in roster.ROSTER}
    assert all(roster.BY_KEY[a.key] is a for a in roster.ROSTER)


def test_every_agent_is_in_a_known_realm():
    assert all(a.realm in roster.REALMS for a in roster.ROSTER)


def test_leads_only_reference_real_members():
    # A dangling member key breaks delegation silently — the router hands work to a key with no agent.
    for a in roster.ROSTER:
        for member in a.members:
            assert member in roster.BY_KEY, f"{a.key} names unknown member {member!r}"


def test_only_leads_have_members():
    for a in roster.ROSTER:
        if a.members:
            assert a.lead, f"{a.key} has members but is not marked lead"


def test_in_realm_returns_only_that_realm():
    root = roster.in_realm("Root")
    assert {a.key for a in root} == {"operator", "gna"}
    assert all(a.realm == "Root" for a in root)


def test_in_realm_unknown_realm_is_empty():
    assert roster.in_realm("Asgard") == []


def test_in_realm_partitions_the_whole_roster():
    total = sum(len(roster.in_realm(r)) for r in roster.REALMS)
    assert total == len(roster.ROSTER)  # every agent lands in exactly one realm


def test_agentspec_is_frozen():
    import dataclasses

    spec = roster.ROSTER[0]
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        spec.key = "mutated"  # type: ignore[misc]


def test_fallback_prompt_prefers_baked_role_prompt():
    spec = next(s for s in roster.ROSTER if s.key in roles.ROLE_PROMPTS)
    assert roster.fallback_prompt(spec) == roles.ROLE_PROMPTS[spec.key]


def test_fallback_prompt_uses_generic_template_when_unbaked():
    spec = next(s for s in roster.ROSTER if s.key not in roles.ROLE_PROMPTS)
    prompt = roster.fallback_prompt(spec)
    # generic template is filled from the spec, not left as literal placeholders
    assert spec.god in prompt and spec.role in prompt and spec.what in prompt
    assert "{god}" not in prompt and "{role}" not in prompt
