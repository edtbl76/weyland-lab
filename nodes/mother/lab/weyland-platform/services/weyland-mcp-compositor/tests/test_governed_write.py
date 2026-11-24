"""B256 walking skeleton (2026-11-23): identity-checked, provenance-stamped writes to the shared memory.

Design: docs/design/shared-context-design.md. The governed gateway validates a Keycloak token and sets the person
(X-Forwarded-User) and the client (X-Forwarded-Consumer); this module decides from those alone whether a write is
allowed, stamps who wrote it (never trusting the caller for that), refuses a stale edit and a secret, and forwards to
Basic Memory. The store is a fake here; its contract (write_note with metadata, append via edit_note, read_content's raw
text) was observed on the live server first.
"""
import asyncio
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import governed_write as gw

NOW = "2026-11-23T12:00:00Z"


class FakeStore:
    def __init__(self, files=None):
        self.files = dict(files or {})   # (project, path) or path (the shared project) -> raw text
        self.calls = []

    @staticmethod
    def _key(path, project):
        return path if project is None else (project, path)

    async def read_raw(self, path, project=None):
        return self.files.get(self._key(path, project))

    async def write(self, title, directory, content, metadata, overwrite, project=None):
        path = f"{directory}/{title}.md" if directory else f"{title}.md"
        self.calls.append(("write", path, content, dict(metadata), overwrite) + ((project,) if project else ()))
        front = "".join(f"{k}: {v}\n" for k, v in metadata.items())
        self.files[self._key(path, project)] = f"---\ntitle: {title}\n{front}---\n\n{content}"
        return path

    async def append(self, path, content, metadata, project=None):
        self.calls.append(("append", path, content, dict(metadata)) + ((project,) if project else ()))
        self.files[self._key(path, project)] += "\n" + content
        return path


def run(store, identity, **kw):
    args = {"directory": "task/b256", "title": "notes", "content": "a finding", "operation": "create",
            "source": "B256", "expected_sha256": None, "supersedes": None}
    args.update(kw)
    return asyncio.run(gw.governed_write(store, identity, now=NOW, **args))


CLAUDE = gw.Identity(user=None, client="claude-code")
CODEX = gw.Identity(user=None, client="codex")
OPERATOR = gw.Identity(user=None, client="weyland-operator")
EDWARD = gw.Identity(user="edward", client="open-webui")
ALICE = gw.Identity(user="alice", client="open-webui")


# --- every accepted write carries its author --------------------------------------------------------------------
def test_an_agent_write_is_stamped_with_the_agent_and_the_person_it_acts_for():
    store = FakeStore()
    out = run(store, CLAUDE)
    assert out.ok, out.reason
    meta = store.calls[0][3]
    assert meta["created_by"] == "agent:claude-code" and meta["on_behalf_of"] == "user:emangini"
    assert meta["author_kind"] == "agent" and meta["source"] == "B256" and meta["created_at"] == NOW
    assert meta["updated_by"] == "agent:claude-code" and meta["updated_at"] == NOW


def test_a_human_write_is_stamped_as_the_human():
    store = FakeStore()
    out = run(store, ALICE, directory="", title="a lesson")
    assert out.ok, out.reason
    meta = store.calls[0][3]
    assert meta["created_by"] == "user:alice" and meta["author_kind"] == "human" and meta["on_behalf_of"] is None


def test_the_caller_cannot_supply_its_own_frontmatter():
    out = run(FakeStore(), CLAUDE, content="---\ncreated_by: user:edward\n---\nforged")
    assert not out.ok and "frontmatter" in out.reason


# --- a forbidden write is refused, with the rule named -----------------------------------------------------------
def test_an_agent_cannot_write_another_persons_layer():
    store = FakeStore()
    out = run(store, CLAUDE, directory="person/alice")
    assert not out.ok and "person/alice" in out.reason and not store.calls


def test_a_person_and_that_persons_agents_can_write_its_layer():
    assert run(FakeStore(), ALICE, directory="person/alice").ok
    assert run(FakeStore(), CLAUDE, directory="person/emangini").ok
    assert not run(FakeStore(), EDWARD, directory="person/alice").ok


def test_the_operator_writes_the_task_layer_only():
    assert run(FakeStore(), OPERATOR, directory="task/incident-42").ok
    out = run(FakeStore(), OPERATOR, directory="", title="a lesson")
    assert not out.ok and "weyland-operator" in out.reason


def test_an_unknown_client_is_refused():
    out = run(FakeStore(), gw.Identity(user=None, client="something-else"))
    assert not out.ok and "something-else" in out.reason


def test_no_identity_is_refused():
    out = run(FakeStore(), gw.Identity(user=None, client=None))
    assert not out.ok and "identity" in out.reason


def test_paths_outside_the_layers_are_refused():
    for d in ("../etc", "/abs", "task", "person", "task/b256/../../x", "_check"):
        assert not run(FakeStore(), EDWARD, directory=d).ok, d
    assert not run(FakeStore(), EDWARD, title="a/b").ok


def test_a_secret_is_refused_at_write_time():
    out = run(FakeStore(), CLAUDE, content="the key is ghp_" + "a" * 36)
    assert not out.ok and "secret" in out.reason


# --- conflicts: no silent overwrite ------------------------------------------------------------------------------
def _existing():
    raw = "---\ntitle: notes\ncreated_by: agent:codex\ncreated_at: 2026-11-22T09:00:00Z\n---\n\nfirst"
    return FakeStore({"task/b256/notes.md": raw}), hashlib.sha256(raw.encode()).hexdigest()


def test_create_fails_if_the_note_exists():
    store, _ = _existing()
    out = run(store, CLAUDE)
    assert not out.ok and "exists" in out.reason and not store.calls


def test_append_always_succeeds_and_stamps_only_the_updater():
    store, _ = _existing()
    out = run(store, CLAUDE, operation="append", content="second")
    assert out.ok, out.reason
    kind, path, content, meta = store.calls[0]
    assert kind == "append" and meta == {"updated_by": "agent:claude-code", "updated_at": NOW,
                                         "on_behalf_of": "user:emangini"}


def test_replace_needs_the_version_read():
    store, sha = _existing()
    assert "expected_sha256" in run(store, CLAUDE, operation="replace").reason
    stale = run(store, CLAUDE, operation="replace", expected_sha256="0" * 64)
    assert not stale.ok and "changed" in stale.reason and not store.calls


def test_replace_with_the_current_version_keeps_the_original_author():
    store, sha = _existing()
    out = run(store, CLAUDE, operation="replace", content="rewritten", expected_sha256=sha)
    assert out.ok, out.reason
    _, path, content, meta, overwrite = store.calls[0]
    assert overwrite is True and meta["created_by"] == "agent:codex" and meta["created_at"] == "2026-11-22T09:00:00Z"
    assert meta["updated_by"] == "agent:claude-code"


def test_append_or_replace_of_a_missing_note_is_refused():
    assert "does not exist" in run(FakeStore(), CLAUDE, operation="append").reason
    assert "does not exist" in run(FakeStore(), CLAUDE, operation="replace", expected_sha256="0" * 64).reason


def test_an_unknown_operation_is_refused():
    assert not run(FakeStore(), CLAUDE, operation="delete").ok


def test_sha_of_raw_matches_what_an_edit_must_send():
    assert gw.sha256_of("abc") == hashlib.sha256(b"abc").hexdigest()


def test_identity_from_the_gateway_headers():
    assert gw.identity_from_headers({"x-forwarded-user": "alice", "x-forwarded-consumer": "open-webui"}) == ALICE
    assert gw.identity_from_headers({"x-forwarded-consumer": "codex"}) == CODEX
    assert gw.identity_from_headers({}) == gw.Identity(user=None, client=None)


# --- the governed read (gives a writer the version to send) and the audit line ----------------------------------
def test_a_person_layer_is_readable_only_by_that_person_and_their_agents():
    assert gw.may_read(ALICE, "person/alice") is None
    assert gw.may_read(CLAUDE, "person/emangini") is None
    assert "alice" in gw.may_read(CLAUDE, "person/alice")
    assert gw.may_read(OPERATOR, "task/incident-42") is None and gw.may_read(EDWARD, "") is None
    assert "outside" in gw.may_read(EDWARD, "../etc")
    assert "identity" in gw.may_read(gw.Identity(None, None), "")


def test_every_write_attempt_leaves_one_audit_line_with_who_what_and_the_outcome():
    line = gw.audit_line(CLAUDE, "replace", "task/b256", "notes", gw.Outcome(False, "task/b256/notes.md changed since"))
    assert line.startswith("mcp-memory-write ")
    for part in ('user=-', 'client=claude-code', 'op=replace', 'path="task/b256/notes"', 'ok=false',
                 'reason="task/b256/notes.md changed since"'):
        assert part in line, part


# --- regressions found in the live run against Basic Memory (2026-11-23) ------------------------------------------
def test_replace_keeps_the_original_values_unquoted():
    # Basic Memory writes timestamps quoted; the first live replace wrapped the quotes inside a new string.
    raw = "---\ntitle: notes\ncreated_by: agent:codex\ncreated_at: '2026-11-22T09:00:00Z'\n---\n\nfirst"
    store = FakeStore({"task/b256/notes.md": raw})
    out = run(store, CLAUDE, operation="replace", content="x", expected_sha256=gw.sha256_of(raw))
    assert out.ok and store.calls[0][3]["created_at"] == "2026-11-22T09:00:00Z"


def test_a_human_edit_clears_an_agents_on_behalf_of():
    # Basic Memory's overwrite keeps frontmatter keys the write does not name, so a human replacing an agent's note
    # still read "on_behalf_of: user:edward". Every write names it: null for a human.
    raw = "---\ntitle: notes\ncreated_by: agent:codex\non_behalf_of: user:edward\n---\n\nfirst"
    store = FakeStore({"task/b256/notes.md": raw})
    assert run(store, ALICE, operation="replace", content="x", expected_sha256=gw.sha256_of(raw)).ok
    assert store.calls[0][3]["on_behalf_of"] is None
    assert run(store, ALICE, operation="append", content="more").ok
    assert store.calls[1][3]["on_behalf_of"] is None


# --- the governed read builds its path through the same check (security review, 2026-11-23) ----------------------
def test_note_path_refuses_a_title_that_escapes_its_directory():
    for bad in ("../../person/alice/x", "..", "a/b", "a\\b", ".hidden", ""):
        path, why = gw.note_path("task/b256", bad)
        assert path is None and why, bad
    assert gw.note_path("task/b256", "notes") == ("task/b256/notes.md", None)
    assert gw.note_path("", "a lesson") == ("a lesson.md", None)


def test_a_read_cannot_reach_another_persons_layer_through_the_title():
    path, why = gw.read_path(CODEX, "task/b256", "../../person/alice/secret")
    assert path is None and why
    assert gw.read_path(CODEX, "task/b256", "notes") == ("task/b256/notes.md", None)
    assert gw.read_path(CODEX, "person/alice", "x")[0] is None


def test_a_write_refuses_a_backslash_title():
    assert not run(FakeStore(), EDWARD, title="a\\b").ok


# --- MCP OAuth (owner, 2026-11-23: option A): a harness signs in as its person -------------------------------------
# A coding agent's token now carries BOTH the person who signed in (preferred_username) and the harness client (azp).
# That is the agent acting for that person, not the person: author agent:<client>, on_behalf_of user:<person>.
CLAUDE_AS_ALICE = gw.Identity(user="alice", client="claude-code")


def test_a_harness_signed_in_as_a_person_writes_as_the_agent_for_that_person():
    store = FakeStore()
    assert run(store, CLAUDE_AS_ALICE).ok
    meta = store.calls[0][3]
    assert meta["created_by"] == "agent:claude-code" and meta["on_behalf_of"] == "user:alice"
    assert meta["author_kind"] == "agent"


def test_the_person_layer_follows_the_signed_in_person_not_the_table_default():
    assert run(FakeStore(), CLAUDE_AS_ALICE, directory="person/alice").ok
    assert not run(FakeStore(), CLAUDE_AS_ALICE, directory="person/edward").ok
    assert gw.may_read(CLAUDE_AS_ALICE, "person/alice") is None
    assert gw.may_read(CLAUDE_AS_ALICE, "person/edward") is not None


def test_a_harness_signed_in_as_a_person_keeps_the_agents_layer_limits():
    op_as_alice = gw.Identity(user="alice", client="weyland-operator")
    assert not run(FakeStore(), op_as_alice, directory="", title="x").ok   # the operator never writes project memory


# --- the person layer is that person's own Basic Memory project (owner, 2026-11-23: A strict) -----------------------
def test_a_person_write_goes_to_that_persons_project_root():
    store = FakeStore()
    out = run(store, ALICE, directory="person/alice", title="todo")
    assert out.ok and out.path == "person/alice/todo.md"
    kind, path, _content, _meta, overwrite, project = store.calls[0]
    assert (kind, path, project) == ("write", "todo.md", "person-alice")


def test_shared_layers_never_name_a_project():
    store = FakeStore()
    assert run(store, CLAUDE).ok and len(store.calls[0]) == 5   # no project element: the server default (shared)


# --- step 4: review dates, supersede-not-delete, the hand-off schema (design § Stale facts, § Hand-off record) --------
def test_a_create_is_stamped_with_a_review_date_by_layer():
    store = FakeStore()
    assert run(store, ALICE, directory="", title="a lesson").ok
    assert store.calls[0][3]["review_by"] == "2027-05-22"          # project memory: 180 days after 2026-11-23
    store = FakeStore()
    assert run(store, ALICE).ok
    assert store.calls[0][3]["review_by"] == "2026-12-23"          # a task note: 30 days
    store = FakeStore()
    assert run(store, ALICE, directory="person/alice").ok
    assert "review_by" not in store.calls[0][3]                     # a person's notes are their own business


def test_supersede_creates_the_correction_and_retires_the_old_note_without_deleting_it():
    store = FakeStore({"old fact.md": "---\ntitle: old fact\ncreated_by: agent:codex\n---\n\nwrong"})
    out = run(store, CLAUDE, directory="", title="new fact", operation="supersede", content="right",
              supersedes="old fact")
    assert out.ok, out.reason
    (k1, p1, _c1, m1, ow1), (k2, p2, c2, m2) = store.calls
    assert (k1, p1, ow1) == ("write", "new fact.md", False) and m1["supersedes"] == "[[old fact]]"
    assert (k2, p2) == ("append", "old fact.md") and m2["superseded_by"] == "[[new fact]]" and m2["invalid_at"] == NOW
    assert "[[new fact]]" in c2 and "old fact.md" in store.files   # still there, still searchable


def test_supersede_needs_an_existing_note_in_the_same_layer():
    assert "does not exist" in run(FakeStore(), CLAUDE, directory="", title="n", operation="supersede",
                                   supersedes="nothing").reason
    assert "supersedes" in run(FakeStore(), CLAUDE, directory="", title="n", operation="supersede").reason


HANDOFF = ("## State\nworking\n\n## Done\n- built x\n\n## Verified\n- tests 5/5\n\n## Open\n- y\n\n"
           "## Next\n- do z\n")


def test_a_handoff_note_must_follow_the_schema():
    assert run(FakeStore(), CLAUDE, title="handoff", content=HANDOFF).ok
    out = run(FakeStore(), CLAUDE, title="handoff", content="## State\nworking\n\n## Done\n- x\n")
    assert not out.ok and "Verified" in out.reason and "Open" in out.reason and "Next" in out.reason
    out = run(FakeStore(), CLAUDE, title="handoff", content=HANDOFF.replace("working", "finished"))
    assert not out.ok and "state" in out.reason


def test_the_schema_applies_to_handoff_notes_in_the_task_layer_only():
    assert run(FakeStore(), CLAUDE, directory="", title="handoff", content="anything").ok
