"""The Hook/Decision wire contract between weyland-guard and weyland-tool-server.

WHY THIS EXISTS. `weyland-tool-server` carries its OWN copy of `guardrails/verdict.py`, byte-identical
to this service's, and its Dockerfile does `COPY guardrails /app/guardrails` from its own directory.
Nothing keeps the two in sync.

That copy is not incidental — it IS a wire contract. `weyland-tool-server/main.py` is an HTTP *client*
of this service:

    _GUARD_PATHS = {Hook.INPUT: "/guard/input", Hook.OUTPUT: "/guard/output", Hook.ACT: "/guard/act"}
    ...
    return Verdict(v.get("validator", "guard"), Decision.BLOCK, v.get("score"), v.get("reason", ""), 0)

So `Hook`'s VALUES become the URL path this service must route, and `Decision`'s values are what the
client parses out of this service's JSON. Add a fourth `Hook` here and tool-server cannot address the
new route; change a `Decision` string and tool-server misreads every response. Neither failure is
visible at build time, and both services would keep reporting healthy.

The duplication survived the B70 extraction that moved guardrails out of tool-server into this
service. It was found on 2026-08-26 by a graphify label collision (12 nodes named `verdict`) while
evaluating the tool for EMA-191 — not by looking for it, which is the point: nothing was looking.

WHY A TEST AND NOT DE-DUPLICATION. Sharing the module would mean either moving the Docker build
context up a level for both services or publishing an internal package. This is a lab; the file is
three enums and a dataclass, and it has been stable. A test that makes divergence LOUD is
proportionate, and it forces a conversation rather than silently permitting drift.

THIS TEST HAS BEEN SEEN TO FAIL. It was verified by perturbing the tool-server copy and confirming a
red run, then restoring — a guard nobody has watched fail is not a guard.
"""

from pathlib import Path

# tests/ -> weyland-guard/ -> services/
_SERVICES = Path(__file__).resolve().parents[2]
_OURS = _SERVICES / "weyland-guard" / "guardrails" / "verdict.py"
_THEIRS = _SERVICES / "weyland-tool-server" / "guardrails" / "verdict.py"


def _load(path: Path):
    """Exec the module in isolation so we compare FILES, not whatever is on sys.path.

    Importing `guardrails.verdict` twice would just hand back the same cached module and the test
    would pass unconditionally — the exact 'green for a reason unrelated to the code' failure this
    repo keeps hitting.
    """
    ns: dict = {}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), ns)
    return ns


def test_both_copies_exist():
    # If tool-server's copy is ever deleted, this test must fail LOUDLY rather than silently
    # comparing nothing and passing. An absent file is not agreement.
    assert _OURS.is_file(), f"missing {_OURS}"
    assert _THEIRS.is_file(), f"missing {_THEIRS}"


def test_hook_values_match():
    """Hook values are URL PATH segments in tool-server: /guard/<value>."""
    ours, theirs = _load(_OURS), _load(_THEIRS)
    assert {h.name: h.value for h in ours["Hook"]} == {h.name: h.value for h in theirs["Hook"]}


def test_decision_values_match():
    """Decision values are parsed out of this service's JSON response by tool-server."""
    ours, theirs = _load(_OURS), _load(_THEIRS)
    assert {d.name: d.value for d in ours["Decision"]} == {
        d.name: d.value for d in theirs["Decision"]
    }


def test_mode_values_match():
    """Mode is guard-internal (the /admin/mode toggle), but it lives in the copied file, so a change
    here is still a signal that the copies have diverged."""
    ours, theirs = _load(_OURS), _load(_THEIRS)
    assert {m.name: m.value for m in ours["Mode"]} == {m.name: m.value for m in theirs["Mode"]}


def test_verdict_fields_match():
    """tool-server constructs Verdict POSITIONALLY:
        Verdict(validator, Decision.BLOCK, score, reason, 0)
    so field ORDER is part of the contract, not just the names. Reordering here would silently
    mis-assign every field in the client.
    """
    ours, theirs = _load(_OURS), _load(_THEIRS)
    assert list(ours["Verdict"].__dataclass_fields__) == list(
        theirs["Verdict"].__dataclass_fields__
    )


def test_files_are_identical():
    """The broad backstop. The four checks above pin the contract this repo actually relies on; this
    one catches anything added to one copy and not the other — a new enum, a new field, a changed
    default. If the two ever NEED to diverge, delete this test deliberately and keep the four above.
    """
    assert _OURS.read_text(encoding="utf-8") == _THEIRS.read_text(encoding="utf-8"), (
        "weyland-guard and weyland-tool-server copies of guardrails/verdict.py have DIVERGED. "
        "They are a wire contract: Hook values are URL paths, Decision values are parsed from the "
        "response. Sync them, or split the contract deliberately."
    )
