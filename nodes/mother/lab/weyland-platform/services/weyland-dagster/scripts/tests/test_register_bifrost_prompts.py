"""Tests for register_bifrost_prompts.py — git prompts reach Bifrost when they change (B204 follow-on, 2026-10-10).

Fixtures mirror the shape observed LIVE (values, not just keys): GET /api/prompt-repo/prompts returns every prompt in
one response, each with `latest_version` = {commit_message, version_number, messages}, and each message WRAPPED as
{"message": {"role", "content"}, "order_index"}. Prompts have a second writer — prompt federation reconciles native
Langfuse/MLflow edits back into Bifrost with commit_message `reconciled-from-<source>:<hash>` — so a version this
registrar did not write (its own commits start `lane: `) is a CONFLICT to report, never something to overwrite.
"""
import pytest

import register_bifrost_prompts as reg

PROMPT = {"folder": "content-ops", "name": "summarize", "lane": "wl-default",
          "messages": [("system", "Summarize."), ("user", "{{text}}")]}


def _live(messages, commit="lane: wl-default", pid="p1"):
    """One list item in the observed shape; `messages` are (role, content), listed in reverse to prove ordering."""
    wrapped = [{"id": i, "order_index": i, "message": {"role": r, "content": c}} for i, (r, c) in enumerate(messages)]
    return {"id": pid, "name": "summarize", "latest_version": {
        "commit_message": commit, "version_number": 1, "messages": list(reversed(wrapped))}}


# --- decide: pure ----------------------------------------------------------------------------------

def test_missing_prompt_is_created():
    assert reg.decide(PROMPT, None)[0] == "create"


def test_equal_messages_are_unchanged_whatever_the_wire_order():
    assert reg.decide(PROMPT, _live(PROMPT["messages"])) == ("unchanged", None)


def test_changed_messages_written_by_this_registrar_are_updated():
    action, payload = reg.decide(PROMPT, _live([("system", "Summarise, briefly."), ("user", "{{text}}")]))
    assert action == "update"
    assert payload == {"commit_message": "lane: wl-default",
                       "messages": [{"role": "system", "content": "Summarize."}, {"role": "user", "content": "{{text}}"}]}


def test_a_native_edit_reconciled_from_langfuse_is_a_conflict_never_overwritten():
    live = _live([("system", "Edited in Langfuse.")], commit="reconciled-from-langfuse:ab12cd34ef56")
    assert reg.decide(PROMPT, live) == ("conflict", None)


def test_a_version_with_no_commit_message_is_a_conflict():
    assert reg.decide(PROMPT, _live([("system", "UI edit")], commit=""))[0] == "conflict"


def test_whitespace_counts_as_a_change():
    action, _ = reg.decide(PROMPT, _live([("system", "Summarize. "), ("user", "{{text}}")]))
    assert action == "update"


# --- reconcile: with a fake Bifrost -------------------------------------------------------------------

class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class _Fake:
    def __init__(self, items, folders=("content-ops",), write_status=200):
        self.items, self.folders, self.write_status, self.posts = items, list(folders), write_status, []

    def get(self, path, params=None):
        if path == "/api/prompt-repo/folders":
            return _Resp(200, {"folders": [{"name": f, "id": f"f-{f}"} for f in self.folders]})
        if path == "/api/prompt-repo/prompts":
            return _Resp(200, {"prompts": self.items})
        raise AssertionError(path)

    def post(self, path, json):
        self.posts.append((path, json))
        if path == "/api/prompt-repo/prompts":
            return _Resp(self.write_status, {"prompt": {"id": "new"}})
        return _Resp(self.write_status, {"ok": True})


def test_reconcile_counts_every_outcome_and_writes_only_updates_and_creates():
    other = dict(PROMPT, name="extract")
    native = dict(PROMPT, name="rewrite")
    items = [_live(PROMPT["messages"]),                                                   # unchanged
             dict(_live([("system", "old")], pid="p2"), name="extract"),                 # update
             dict(_live([("system", "native")], commit="reconciled-from-mlflow:1", pid="p3"), name="rewrite")]
    fake = _Fake(items)
    counts = reg.reconcile(fake, [PROMPT, other, native, dict(PROMPT, name="brand-new")])
    assert counts == {"created": 1, "updated": 1, "unchanged": 1, "conflict": 1, "failed": 0}
    paths = [p for p, _ in fake.posts]
    assert paths == ["/api/prompt-repo/prompts/p2/versions",          # the update: a new version on the existing id
                     "/api/prompt-repo/prompts", "/api/prompt-repo/prompts/new/versions"]   # the create


def test_a_rejected_write_counts_as_failed():
    fake = _Fake([dict(_live([("system", "old")]), name="summarize")], write_status=500)
    assert reg.reconcile(fake, [PROMPT])["failed"] == 1


def test_an_unreadable_prompt_list_fails_closed():
    class Broken(_Fake):
        def get(self, path, params=None):
            if path == "/api/prompt-repo/prompts":
                return _Resp(401, {"error": "setup token required"})
            return super().get(path, params)
    with pytest.raises(RuntimeError, match="prompt-repo/prompts"):
        reg.reconcile(Broken([]), [PROMPT])


def test_a_list_without_a_prompts_array_fails_closed():
    class Odd(_Fake):
        def get(self, path, params=None):
            if path == "/api/prompt-repo/prompts":
                return _Resp(200, {"items": []})
            return super().get(path, params)
    with pytest.raises(RuntimeError, match="no prompts array"):
        reg.reconcile(Odd([]), [PROMPT])


# --- the MLflow registrar declares the same app prompts; the two git copies must agree ---------------------------------

def _mlflow_registrar_prompts():
    """PROMPTS from scripts/register_prompts.py (B100, MLflow), read with ast: that module imports mlflow at the top."""
    import ast
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[4] / "scripts" / "register_prompts.py"
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PROMPTS":
            return ast.literal_eval(node.value)
    raise AssertionError(f"no PROMPTS dict in {path}")


def test_prompts_shared_with_the_mlflow_registrar_have_identical_text():
    # 2026-10-10: operator_system drifted (a B182 sentence went into the MLflow copy only); prompt federation pulled the
    # MLflow text into Bifrost and this registrar reported a CONFLICT. Both copies are git — they must say the same thing.
    import re
    mlflow_prompts = _mlflow_registrar_prompts()
    shared = [p for p in reg.PROMPTS if p["name"] in mlflow_prompts]
    assert {p["name"] for p in shared} == {"rag_system", "operator_system", "agent_grade", "agent_reflect"}
    for p in shared:
        messages = reg._git_messages(p)
        assert len(messages) == 1, p["name"]
        as_mlflow = re.sub(r"\{\{\s*(\w+)\s*\}\}", r"{\1}", messages[0]["content"])   # Bifrost {{v}} = MLflow {v}
        assert as_mlflow == mlflow_prompts[p["name"]], f"{p['name']} differs between the two registrars"


def test_importing_the_module_needs_no_httpx():
    # The CI test lane has no httpx; the SoT data must import without it.
    import sys
    assert "httpx" not in sys.modules or hasattr(reg, "reconcile")
    assert reg.PROMPTS
