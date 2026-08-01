"""A2A Agent Cards — the discovery artifacts.

Each agent publishes a card shaped after the A2A Protocol AgentCard (name, description, url, version, capabilities,
skills[]). A supervisor (the Operator) or a peer reads a card to learn what an agent does and where to reach it, then
sends it a task — no hard-wiring. We publish a card per agent AND a root card for the whole service, so callers can
discover the realm at one URL and address any agent within it."""
from config import PUBLIC_BASE_URL, VERSION
from roster import ROSTER, AgentSpec

_CAPS = {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False}


def card(spec: AgentSpec) -> dict:
    """An A2A-shaped AgentCard for one agent."""
    return {
        "name": spec.god,
        "key": spec.key,
        "description": spec.what,
        "url": f"{PUBLIC_BASE_URL}/agents/{spec.key}",
        "version": VERSION,
        "provider": {"organization": "weyland", "realm": spec.realm},
        "capabilities": _CAPS,
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{
            "id": spec.role.replace(" ", "-"),
            "name": f"{spec.god} — {spec.role}",
            "description": spec.what,
            "tags": [spec.realm.lower().replace("the ", ""), spec.role, "a2a"],
        }],
        "metadata": {"lane": spec.lane, "status": spec.status, "lead": spec.lead,
                     "members": list(spec.members), "nameLore": spec.why},
    }


def all_cards() -> list[dict]:
    return [card(a) for a in ROSTER]


def root_card() -> dict:
    """The service-level card: discover the whole Realm at one URL, with every agent as a referenced skill."""
    return {
        "name": "Realm of Agents",
        "description": "24 corpus-backed agents in five groups (Valhalla, Vanaheim, Midgard, the Well) under the Operator.",
        "url": PUBLIC_BASE_URL,
        "version": VERSION,
        "provider": {"organization": "weyland"},
        "capabilities": _CAPS,
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{"id": a.key, "name": f"{a.god} ({a.realm})", "description": a.what, "tags": [a.realm.lower()]}
                   for a in ROSTER],
    }
