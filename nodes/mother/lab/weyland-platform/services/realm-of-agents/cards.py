"""A2A Agent Cards — the discovery artifacts.

Each agent publishes a card shaped after the A2A Protocol AgentCard (protocolVersion, name, description, url, version,
capabilities, skills[]). A supervisor (the Operator) or a peer reads a card to learn what an agent does and where to
reach it, then sends it a task — no hard-wiring. We publish a card per agent AND a root card for the whole service, so
callers can discover the realm at one URL and address any agent within it.

`url` is the agent's A2A JSON-RPC endpoint (the `/a2a` binding in a2a.py), and it is derived from the *incoming request*
so the card advertises whatever host actually reached it — in-cluster service, a port-forward, or the ingress — falling
back to PUBLIC_BASE_URL when there is no request. `preferredTransport: JSONRPC` tells clients how to speak to it."""
from config import A2A_PROTOCOL_VERSION, PUBLIC_BASE_URL, VERSION
from roster import ROSTER, AgentSpec

_CAPS = {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False}


def _base(base: str | None) -> str:
    return (base or PUBLIC_BASE_URL).rstrip("/")


def card(spec: AgentSpec, base: str | None = None) -> dict:
    """An A2A AgentCard for one agent. `base` is the request-derived origin (scheme://host[:port])."""
    b = _base(base)
    return {
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "name": spec.god,
        "key": spec.key,
        "role": spec.role,          # descriptive role — engineer / eval-judge / observability / …
        "realm": spec.realm,
        "description": spec.what,
        "url": f"{b}/a2a/{spec.key}",
        "preferredTransport": "JSONRPC",
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


def all_cards(base: str | None = None) -> list[dict]:
    return [card(a, base) for a in ROSTER]


def root_card(base: str | None = None) -> dict:
    """The service-level card: discover the whole Realm at one URL, with every agent as a referenced skill."""
    b = _base(base)
    return {
        "protocolVersion": A2A_PROTOCOL_VERSION,
        "name": "Realm of Agents",
        "description": "24 corpus-backed agents in five groups (Valhalla, Vanaheim, Midgard, the Well) under the Operator.",
        "url": f"{b}/a2a",
        "preferredTransport": "JSONRPC",
        "version": VERSION,
        "provider": {"organization": "weyland"},
        "capabilities": _CAPS,
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [{"id": a.key, "name": f"{a.god} ({a.realm})", "description": a.what, "tags": [a.realm.lower()]}
                   for a in ROSTER],
    }
