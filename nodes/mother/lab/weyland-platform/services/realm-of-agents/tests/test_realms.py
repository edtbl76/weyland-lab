"""Tests for `_lead_messages` — the lead-agent prompt builder shared by run_lead and the streaming path.

The whole multi-agent design hinges on this: a capable model left alone just answers directly and the team never
runs, so the lead prompt must (a) make delegation a mandate, (b) hand the lead its explicit roster, and (c) give the
Root Operator a domain→realm routing map (its realm-lead members' generic roles don't self-describe their domain).
Get this wrong and tasks misroute or the team is silently bypassed. Pure string building over the roster.
"""
import realms
from roster import BY_KEY


def _sys(messages):
    assert messages[0][0] == "system"
    return messages[0][1]


def test_lead_messages_shape_system_then_user():
    msgs = realms._lead_messages(BY_KEY["odin"], "build a feature")
    assert msgs[0][0] == "system"
    assert msgs[-1] == ("user", "build a feature")


def test_lead_messages_mandates_delegation_and_lists_the_team():
    sys = _sys(realms._lead_messages(BY_KEY["odin"], "task"))
    assert "DELEGATE" in sys
    # every Valhalla member Odin leads is named in the team line
    for member in BY_KEY["odin"].members:
        assert BY_KEY[member].god in sys


def test_lead_messages_includes_the_baked_role_prompt():
    # _lead_messages starts from load_role(lead); the stubbed load_role returns "[role:<key>]"
    sys = _sys(realms._lead_messages(BY_KEY["odin"], "task"))
    assert "[role:odin]" in sys


def test_root_operator_gets_domain_to_realm_routing_map():
    sys = _sys(realms._lead_messages(BY_KEY["operator"], "task"))
    assert "Valhalla" in sys and "Vanaheim" in sys and "Midgard" in sys and "the Well" in sys
    assert "engineering" in sys and "DOMAIN" in sys


def test_realm_lead_gets_no_routing_map():
    # a realm lead (Odin) leads one discipline — the cross-realm routing map is Root-only
    sys = _sys(realms._lead_messages(BY_KEY["odin"], "task"))
    assert "Choose the realm(s) by the task's DOMAIN" not in sys


def test_lead_messages_inserts_history_between_system_and_user():
    hist = [("user", "earlier"), ("assistant", "reply")]
    msgs = realms._lead_messages(BY_KEY["odin"], "now", history=hist)
    assert msgs[0][0] == "system"
    assert msgs[1:3] == hist
    assert msgs[-1] == ("user", "now")
