"""B256 walking skeleton (2026-11-23): identity-checked, provenance-stamped writes to the shared agent memory.

The governed gateway (weyland-mcp-gateway) validates a Keycloak token and sets the person (X-Forwarded-User, from
`preferred_username`) and the client (X-Forwarded-Consumer, from `azp`), stripping any value the caller sent. This
module decides from those two alone whether a write is allowed, stamps who wrote it (the caller never supplies its own
provenance), refuses a stale edit and a secret, and forwards to Basic Memory through a small store interface. Pure logic
plus that interface, so it is unit-tested without a network (tests/test_governed_write.py).

Layers (docs/design/shared-context-design.md § Context layers): project memory is the top level of the store;
`task/<item>/` is one item's working notes; `person/<name>/` is one person's. Write classes: `create` fails if the note
exists, `append` always succeeds, `replace` must carry the SHA-256 of the version the writer read. Move and delete are
not offered: they stay with humans, on the files. Reads are unchanged in this skeleton (the person layer's read rule is
the design's next step).
"""
import dataclasses
import datetime
import hashlib
import re

import yaml

# Agent clients that may write, the person each acts for, and the layers it may write. An unknown client is refused
# (fail closed). The operator joins the task layer only (scenario S3: incident findings); it stays read-only elsewhere.
AGENTS = {
    "claude-code": ("emangini", {"project", "task", "person"}),
    "codex": ("emangini", {"project", "task", "person"}),
    "opencode": ("emangini", {"project", "task", "person"}),
    "weyland-operator": (None, {"task"}),
}
HUMAN_LAYERS = {"project", "task", "person"}
OPERATIONS = ("create", "append", "replace", "supersede")
# Stale facts (design § Stale facts): a create is stamped with a date to be reviewed by; check-shared-memory.py lists the
# overdue ones for a person to confirm or supersede (flag, never delete). A person's own notes carry none.
REVIEW_DAYS = {"project": 180, "task": 30}
# The hand-off record (design § Hand-off record): task/<item>/handoff, after A2A's task states.
HANDOFF_TITLE = "handoff"
HANDOFF_SECTIONS = ("State", "Done", "Verified", "Open", "Next")
HANDOFF_STATES = ("working", "input-required", "done")

_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
# A small, high-confidence set; agent-memory-watch (gitleaks, every 15 min) still scans everything after the fact.
_SECRETS = re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}"
                      r"|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|lin_api_[A-Za-z0-9]{20,}"
                      r"|-----BEGIN [A-Z ]*PRIVATE KEY-----")


@dataclasses.dataclass(frozen=True)
class Identity:
    user: str | None     # the person (X-Forwarded-User); None for a machine token
    client: str | None   # the client (X-Forwarded-Consumer)


@dataclasses.dataclass(frozen=True)
class Outcome:
    ok: bool
    reason: str = ""
    path: str | None = None


def identity_from_headers(headers: dict) -> Identity:
    h = {k.lower(): v for k, v in (headers or {}).items()}
    return Identity(user=h.get("x-forwarded-user") or None, client=h.get("x-forwarded-consumer") or None)


def sha256_of(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _layer(directory: str):
    """(layer, owner) for a directory, or None when it is outside the layers."""
    if directory in ("", "/"):
        return "project", None
    parts = directory.strip("/").split("/")
    if len(parts) == 2 and parts[0] in ("task", "person") and _SEGMENT.match(parts[1]):
        return parts[0], parts[1]
    return None


def _acting(identity: Identity):
    """("agent", client, person it acts for) or ("human", person, None) or None. A known agent client is an agent even
    when its token names a person: since MCP OAuth (B256, 2026-11-23) a harness signs in AS its person, so the token
    carries both, and the person is who it acts for. A client-credentials token names none: the table's default."""
    if identity.client in AGENTS:
        return "agent", identity.client, identity.user or AGENTS[identity.client][0]
    if identity.user:
        return "human", identity.user, None
    return None


def _author(identity: Identity):
    """(author, kind, on_behalf_of) or an Outcome refusing an unusable identity."""
    acting = _acting(identity)
    if acting is None:
        if identity.client:
            return Outcome(False, f"client {identity.client!r} may not write the shared memory")
        return Outcome(False, "no identity: the gateway set neither a person nor a client")
    kind, who, acts_for = acting
    if kind == "human":
        return f"user:{who}", "human", None
    return f"agent:{who}", "agent", (f"user:{acts_for}" if acts_for else None)


def _allowed(identity: Identity, layer: str, owner: str | None) -> str | None:
    """None when allowed, else the reason."""
    kind, who, acts_for = _acting(identity)
    if kind == "human":
        if layer == "person" and owner != who:
            return f"person/{owner} belongs to {owner}, not {who}"
        return None if layer in HUMAN_LAYERS else f"layer {layer} is not writable"
    if layer not in AGENTS[who][1]:
        return f"{who} may not write the {layer} layer"
    if layer == "person" and owner != acts_for:
        return f"person/{owner} belongs to {owner}; {who} acts for {acts_for}"
    return None


def may_read(identity: Identity, directory: str) -> str | None:
    """None when `identity` may read notes in `directory` through the governed read, else the reason. The person layer
    is private to its person and that person's agents; everything else is readable by any identified caller."""
    if not identity.user and not identity.client:
        return "no identity: the gateway set neither a person nor a client"
    where = _layer(directory or "")
    if where is None:
        return f"{directory!r} is outside the layers (project root, task/<item>, person/<name>)"
    layer, owner = where
    if layer != "person":
        return None
    acting = _acting(identity)
    if acting is None:
        return "no identity the shared memory recognises"
    kind, who, acts_for = acting
    reader = who if kind == "human" else acts_for
    return None if reader == owner else f"person/{owner} is readable only by {owner} and {owner}'s agents"


def _logfmt(v) -> str:
    v = "-" if v in (None, "") else str(v)
    return f'"{v}"' if any(c in v for c in ' "=/') else v


def audit_line(identity: Identity, operation: str, directory: str, title: str, outcome: Outcome) -> str:
    """One structured line per write attempt (the gateway's own audit names the path, not the tool or the note)."""
    note = f"{directory.strip('/')}/{title}" if directory.strip("/") else title
    return (f"mcp-memory-write user={_logfmt(identity.user)} client={_logfmt(identity.client)} "
            f"op={_logfmt(operation)} path={_logfmt(note)} ok={'true' if outcome.ok else 'false'} "
            f"reason={_logfmt(outcome.reason)}")


def _front(raw: str) -> dict:
    """The note's frontmatter as YAML values (Basic Memory quotes timestamps; a naive split kept the quotes, and the
    first live replace wrote them back inside a new string). Unparseable frontmatter reads as empty."""
    m = re.match(r"\A---\n(.*?)\n---\n", raw, re.S)
    try:
        data = yaml.load(m.group(1), Loader=yaml.BaseLoader) if m else {}   # every scalar a string, as written
    except yaml.YAMLError:
        return {}
    return {k: v for k, v in (data or {}).items() if isinstance(v, str)}


def note_path(directory: str, title: str):
    """(path, None) for a note in one of the layers, or (None, reason). The ONE place a path is built, for reads and
    writes alike, so the layer check and the path the store sees cannot diverge (security review, 2026-11-23: the
    read tool once built its path from an unchecked title, and `../../person/<name>/…` escaped its directory)."""
    if _layer(directory or "") is None:
        return None, f"{directory!r} is outside the layers (project root, task/<item>, person/<name>)"
    if not title or any(c in title for c in "/\\") or title.startswith(".") or ".." in title:
        return None, f"title {title!r} is not a plain note name"
    d = (directory or "").strip("/")
    return (f"{d}/{title}.md" if d else f"{title}.md"), None


def store_location(directory: str, title: str):
    """(project, path, directory) where a validated note lives in Basic Memory. The person layer is that person's OWN
    project, `person-<name>`, at its root (owner, 2026-11-23: A strict), so no shared read tool can reach it; every
    other layer is the shared project (None = the server default) at the same path callers see."""
    layer, owner = _layer(directory or "")
    if layer == "person":
        return f"person-{owner}", f"{title}.md", ""
    d = (directory or "").strip("/")
    return None, (f"{d}/{title}.md" if d else f"{title}.md"), d


def read_path(identity: Identity, directory: str, title: str):
    """(path, None) when `identity` may read that note through the governed read, else (None, reason)."""
    why = may_read(identity, directory)
    if why:
        return None, why
    return note_path(directory, title)


def handoff_problem(content: str) -> str | None:
    """None when `content` follows the hand-off schema, else what is missing. Plain line parsing, no regex: the content
    comes from any agent, and an overlapping pattern (`\\s*\\n+`) could be made to backtrack (Sonar, 2026-11-24)."""
    lines = [line.strip() for line in content.splitlines()]
    missing = [s for s in HANDOFF_SECTIONS if f"## {s}" not in lines]
    if missing:
        return f"a hand-off note needs the sections {', '.join('## ' + m for m in missing)}"
    after = lines[lines.index("## State") + 1:]
    state = next((line for line in after if line), "").lower()
    if state not in HANDOFF_STATES:
        return f"a hand-off note's state must be one of {', '.join(HANDOFF_STATES)}, not {state!r}"
    return None


def _refusal(identity: Identity, directory: str, title: str, content: str, operation: str) -> str | None:
    """The first rule the request breaks, or None. Checked before the store is touched."""
    if operation not in OPERATIONS:
        return f"operation {operation!r} is not offered (one of {', '.join(OPERATIONS)})"
    _, why = note_path(directory, title)
    if why:
        return why
    if content.lstrip().startswith("---"):
        return "content may not carry its own frontmatter: provenance is stamped by the gateway"
    if _SECRETS.search(content):
        return "content looks like it holds a secret; secrets never enter the shared memory"
    layer = _layer(directory or "")
    if layer[0] == "task" and title == HANDOFF_TITLE and operation in ("create", "replace"):
        why = handoff_problem(content)
        if why:
            return why
    return _allowed(identity, *layer)


async def _supersede(store, *, path, where, old_where, title, old_title, content, stamp, created, now) -> Outcome:
    """Create the correcting note linked to the old one, then retire the old one in place (never deleted)."""
    project, spath, sdir = where
    if await store.read_raw(old_where[1], project=old_where[0]) is None:
        return Outcome(False, f"{old_title} does not exist in that layer: nothing to supersede")
    if await store.read_raw(spath, project=project) is not None:
        return Outcome(False, f"{path} exists: supersede into a new note")
    await store.write(title, sdir, content, {**created, **stamp, "supersedes": f"[[{old_title}]]"}, False,
                      project=project)
    await store.append(old_where[1], f"Superseded by [[{title}]] on {now[:10]}.",
                       {**stamp, "superseded_by": f"[[{title}]]", "invalid_at": now}, project=old_where[0])
    return Outcome(True, "superseded", path)


async def _apply(store, operation, *, path, where, title, content, stamp, created, expected_sha256) -> Outcome:
    """Run one write class. `path` is the note as callers see it; `where` = (project, path, directory) in the store."""
    project, spath, sdir = where
    raw = await store.read_raw(spath, project=project)
    if operation == "create":
        if raw is not None:
            return Outcome(False, f"{path} exists: append to it, or replace it with the version you read")
        await store.write(title, sdir, content, {**created, **stamp}, False, project=project)
        return Outcome(True, "created", path)
    if raw is None:
        return Outcome(False, f"{path} does not exist: create it first")
    if operation == "append":
        await store.append(spath, content, stamp, project=project)
        return Outcome(True, "appended", path)
    if not expected_sha256:
        return Outcome(False, "replace needs expected_sha256: the SHA-256 of the version you read")
    if expected_sha256 != sha256_of(raw):
        return Outcome(False, f"{path} changed since you read it: read it again and reapply your change")
    old = _front(raw)
    kept = {"created_by": old.get("created_by", "unknown"), "created_at": old.get("created_at", "unknown"),
            "author_kind": old.get("author_kind", created["author_kind"]), "source": created["source"]}
    await store.write(title, sdir, content, {**kept, **stamp}, True, project=project)
    return Outcome(True, "replaced", path)


async def governed_write(store, identity: Identity, *, directory: str, title: str, content: str, operation: str,
                         source: str, expected_sha256: str | None, now: str, supersedes: str | None = None) -> Outcome:
    author = _author(identity)
    if isinstance(author, Outcome):
        return author
    who, kind, on_behalf_of = author
    why = _refusal(identity, directory, title, content, operation)
    if why:
        return Outcome(False, why)
    path, _ = note_path(directory, title)   # already validated by _refusal
    # on_behalf_of is always named (null for a human): Basic Memory keeps frontmatter keys a write does not name, so a
    # human editing an agent's note would otherwise inherit the agent's "on behalf of" (found live, 2026-11-23).
    stamp = {"updated_by": who, "updated_at": now, "on_behalf_of": on_behalf_of}
    created = {"created_by": who, "created_at": now, "author_kind": kind, "source": source}
    days = REVIEW_DAYS.get(_layer(directory or "")[0])
    if days:
        created["review_by"] = (datetime.date.fromisoformat(now[:10]) + datetime.timedelta(days=days)).isoformat()
    if operation == "supersede":
        if not supersedes:
            return Outcome(False, "supersede needs supersedes: the title of the note it corrects, in the same layer")
        _, why = note_path(directory, supersedes)
        if why:
            return Outcome(False, why)
        return await _supersede(store, path=path, where=store_location(directory, title),
                                old_where=store_location(directory, supersedes), title=title, old_title=supersedes,
                                content=content, stamp=stamp, created=created, now=now)
    return await _apply(store, operation, path=path, where=store_location(directory, title), title=title,
                        content=content, stamp=stamp, created=created, expected_sha256=expected_sha256)
