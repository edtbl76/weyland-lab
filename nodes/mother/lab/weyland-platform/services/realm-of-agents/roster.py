"""The Realm of Agents roster — the single source of truth in code (mirrors aidlc-docs/a2a-agent-roster.md).

Every agent is a thin spec: which realm it belongs to, its plain-English job, the role prompt (a Bifrost prompt name +
a baked fallback), the LiteLLM `wl-*` lane it thinks with, and the MCP tool subsystems it may touch. Leads additionally
name the members they supervise. The A2A Agent Cards, the router, and the runnable graphs are all built from this list —
add an agent here and it shows up everywhere."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    key: str                       # slug / A2A card name
    god: str                       # display name
    realm: str                     # Root | Valhalla | Vanaheim | Midgard | the Well
    role: str                      # short function label
    what: str                      # plain-English job (card description)
    why: str                       # reason for the mythic name
    lane: str = "wl-default"       # LiteLLM brain alias
    tool_prefixes: tuple = ()      # MCP subsystems this agent may use (substring match on fleet tool names)
    status: str = "new"            # live | new | planned
    lead: bool = False             # realm lead (supervisor over `members`)
    members: tuple = ()            # member keys a lead delegates to


# key: (god, realm, role, what, why, lane, tool_prefixes, status, lead, members)
ROSTER: list[AgentSpec] = [
    # --- Root ----------------------------------------------------------------------------------------------------
    AgentSpec("operator", "the Operator", "Root", "supervisor",
              "Top boss. Takes the request, decides who handles it, runs the confirm rails.",
              "Odin's high seat Hlidskjalf — sees into every realm.",
              lane="wl-agentic", status="live", lead=True,
              members=("odin", "kvasir", "verdandi", "tyr")),
    AgentSpec("gna", "Gná", "Root", "dispatch",
              "Given a task, picks which agent should do it.",
              "Frigg's swift messenger who rides everywhere.",
              lane="wl-speed"),

    # --- Valhalla · engineering (led by Odin) --------------------------------------------------------------------
    AgentSpec("odin", "Odin", "Valhalla", "orchestrator",
              "Breaks a goal into steps, delegates, merges results, owns the outcome.",
              "The Allfather, master of Valhalla.",
              lane="wl-agentic", lead=True,
              members=("mimir", "brokkr", "forseti", "hermodr", "heimdall", "huginn", "muninn")),
    AgentSpec("mimir", "Mímir", "Valhalla", "architect",
              "Decides structure, interfaces, and tradeoffs before code is written.",
              "The well of wisdom Odin consults.", lane="wl-reason", tool_prefixes=("context7", "datahub")),
    AgentSpec("brokkr", "Brokkr", "Valhalla", "engineer",
              "Writes the actual code.", "The dwarf-smith who forged the gods' weapons.", lane="wl-coding"),
    AgentSpec("forseti", "Forseti", "Valhalla", "test",
              "Verifies behavior, edge cases, regressions, acceptance criteria.",
              "God of justice who settles every dispute.", lane="wl-coding"),
    AgentSpec("hermodr", "Hermóðr", "Valhalla", "devops",
              "Deploy, environments, observability, operational flow.",
              "The messenger who rides to deliver.", lane="wl-agentic", tool_prefixes=("k8s", "grafana")),
    AgentSpec("heimdall", "Heimdall", "Valhalla", "security",
              "Guards boundaries — authz/authn, data exposure, vulnerabilities.",
              "Guardian of the Bifröst — literally our gateway's name.", lane="wl-reason"),
    AgentSpec("huginn", "Huginn", "Valhalla", "code review",
              "Reviews for correctness and architectural alignment.",
              "Odin's raven Thought — flies out and reports back.", lane="wl-coding"),
    AgentSpec("muninn", "Muninn", "Valhalla", "code quality",
              "Consistency, simplification, conventions.",
              "Odin's raven Memory — flies out and reports back.", lane="wl-coding"),

    # --- Vanaheim · knowledge (led by Kvasir) --------------------------------------------------------------------
    AgentSpec("kvasir", "Kvasir", "Vanaheim", "strategy",
              "Applies the consulting frameworks; synthesizes insight.",
              "The wisest being, born of the gods' truce.", lane="wl-reason", lead=True,
              members=("njordr", "freyja", "bragi")),
    AgentSpec("njordr", "Njörðr", "Vanaheim", "AIDLC delivery",
              "Runs the delivery-lifecycle stages methodically.",
              "Vanir god of order and safe passage.", lane="wl-agentic"),
    AgentSpec("freyja", "Freyja", "Vanaheim", "industry lens",
              "Analyzes a problem through a vertical's lens.",
              "Vanir seeress who sees across the worlds.", lane="wl-default"),
    AgentSpec("bragi", "Bragi", "Vanaheim", "prompt engineering",
              "Writes, critiques, and generates prompts.",
              "God of poetic craft and eloquence.", lane="wl-reason"),

    # --- Midgard · data & platform (led by Verðandi) -------------------------------------------------------------
    AgentSpec("verdandi", "Verðandi", "Midgard", "observability",
              "What's happening right now in metrics, logs, traces. First job: the B109 dashboard audit.",
              "The Norn of the present — 'that which is happening'.",
              lane="wl-agentic", tool_prefixes=("grafana",), lead=True,
              members=("vor", "saga", "yggdrasil", "fulla")),
    AgentSpec("vor", "Vör", "Midgard", "data quality",
              "Is the data true and correct? DQ contracts.",
              "Goddess from whom nothing can be concealed.", lane="wl-coding", tool_prefixes=("trino",)),
    AgentSpec("saga", "Sága", "Midgard", "SQL / analytics",
              "Queries the data for answers.",
              "Seeress who drinks wisdom from the deep.", lane="wl-coding", tool_prefixes=("trino", "postgres")),
    AgentSpec("yggdrasil", "Yggdrasil", "Midgard", "graph / lineage",
              "Relationships and lineage across the estate.",
              "The world-tree that connects everything.", lane="wl-reason", tool_prefixes=("neo4j",)),
    AgentSpec("fulla", "Fulla", "Midgard", "catalog steward",
              "Keeps the catalog, descriptions, and lineage tidy.",
              "Keeper of Frigg's casket and secrets.", lane="wl-default", tool_prefixes=("datahub",)),

    # --- the Well · research · eval · content · safety (led by Tyr) -----------------------------------------------
    AgentSpec("tyr", "Tyr", "the Well", "eval judge",
              "Scores the quality of an output.", "God of law and oaths.", lane="wl-judge", lead=True,
              members=("odroerir", "ratatoskr", "snotra", "syn")),
    AgentSpec("odroerir", "Óðrœrir", "the Well", "RAG / retrieval",
              "Grounded answers from the corpus (the existing weyland-agent, B70).",
              "The vessel holding the mead of knowledge.", lane="wl-rag", status="live",
              tool_prefixes=("context",)),
    AgentSpec("ratatoskr", "Ratatoskr", "the Well", "web research",
              "Fetches and synthesizes information from the web.",
              "The squirrel messenger who runs Yggdrasil carrying news.", lane="wl-agentic",
              tool_prefixes=("perplexity",)),
    AgentSpec("snotra", "Snotra", "the Well", "scribe",
              "Summaries, changelogs, release notes, postmortems.",
              "Goddess of eloquence and good order.", lane="wl-default"),
    AgentSpec("syn", "Syn", "the Well", "safety",
              "PII / injection / grounding guard on inputs and outputs.",
              "Goddess who guards the door and denies entry.", lane="wl-reason"),
]

BY_KEY: dict[str, AgentSpec] = {a.key: a for a in ROSTER}
REALMS = ("Root", "Valhalla", "Vanaheim", "Midgard", "the Well")


def in_realm(realm: str) -> list[AgentSpec]:
    return [a for a in ROSTER if a.realm == realm]


# --- Baked role-prompt fallbacks (used if the Bifrost Prompt Repo is unreachable) --------------------------------
# The Bifrost prompt name is `role-<key>`; these fallbacks keep every agent runnable with no registry round-trip.
_COMMON = ("You are {god}, the {role} agent in the weyland homelab's Realm of Agents. {what} "
           "Stay strictly in your role; if a request needs another specialist, say which one. "
           "Ground every claim in a tool result where you have tools; never tell the user to run a command themselves.")


def fallback_prompt(spec: AgentSpec) -> str:
    from roles import ROLE_PROMPTS   # rich per-agent prompts where written; generic template otherwise
    return ROLE_PROMPTS.get(spec.key) or _COMMON.format(god=spec.god, role=spec.role, what=spec.what)
