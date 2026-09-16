"""Tests for sync_prompts.py — the Bifrost↔Langfuse/MLflow prompt reconciliation logic (B103).

The content-hash is the reconciliation key (versions drift per-tool), and the inbound pull is LOOP-SAFE: it only
pulls a downstream native edit when its content-hash DIFFERS from Bifrost's canonical, and resolves a both-stores
conflict by last-write-wins on timestamp. Get the hash, the {{var}}↔{var} dialect translation, or the diff wrong and
you either sync-loop forever or silently drop a human edit. All pure except reconcile_inbound, whose I/O edges
(_bifrost_ids / _langfuse_native / _mlflow_native / httpx.Client) are stubbed so the DECISION is what's asserted.
"""
import sync_prompts as sp


# ── _hash: content identity ──────────────────────────────────────────────────────────────────────────
def test_hash_is_deterministic_and_content_keyed():
    m = [{"role": "system", "content": "hi {{name}}"}]
    assert sp._hash(m) == sp._hash([dict(m[0])])          # same content → same hash
    assert len(sp._hash(m)) == 12


def test_hash_changes_with_content_or_order():
    a = [{"role": "system", "content": "A"}, {"role": "user", "content": "B"}]
    assert sp._hash(a) != sp._hash([a[1], a[0]])          # order is part of identity
    assert sp._hash(a) != sp._hash([{"role": "system", "content": "A"}, {"role": "user", "content": "C"}])


# ── dialect translation ──────────────────────────────────────────────────────────────────────────────
def test_to_mlflow_text_single_message_is_bare_content_with_var_translation():
    # single-message prompts map to bare content so they match existing MLflow templates (idempotent)
    assert sp._to_mlflow_text([{"role": "system", "content": "Hello {{ name }}!"}]) == "Hello {name}!"


def test_to_mlflow_text_multi_message_is_role_tagged():
    out = sp._to_mlflow_text([{"role": "system", "content": "sys"}, {"role": "user", "content": "{{q}}"}])
    assert out == "[system]\nsys\n\n[user]\n{q}"


def test_to_bifrost_from_mlflow_role_heuristic_and_reverse_translation():
    assert sp._to_bifrost_from_mlflow("Ask {topic}", "greeting_system") == \
        [{"role": "system", "content": "Ask {{topic}}"}]
    assert sp._to_bifrost_from_mlflow("Ask {topic}", "greeting")[0]["role"] == "user"


def test_var_dialects_round_trip():
    bf = [{"role": "user", "content": "x {{a}} y {{b}}"}]
    ml = sp._to_mlflow_text(bf)
    assert ml == "x {a} y {b}"
    assert sp._to_bifrost_from_mlflow(ml, "p")[0]["content"] == "x {{a}} y {{b}}"


# ── _epoch: last-write-wins timestamp ────────────────────────────────────────────────────────────────
def test_epoch_from_mlflow_ms_number():
    assert sp._epoch(1_700_000_000_000) == 1_700_000_000.0     # epoch-ms → seconds


def test_epoch_from_iso_string_and_junk():
    assert sp._epoch("2026-09-16T00:00:00Z") > 0               # ISO parses
    assert sp._epoch("not-a-date") == 0.0                      # fail-safe → 0, never raises


# ── reconcile_inbound: the loop-safe diff/merge decision ─────────────────────────────────────────────
class _FakeBifrostClient:
    def __init__(self, *a, **k):
        self.posts = []

    def post(self, path, json=None):
        self.posts.append((path, json))

    def get(self, *a, **k):
        raise AssertionError("reconcile should not GET on the bifrost client in these tests")


def _wire(monkeypatch, *, ids, langfuse=None, mlflow=None, mirror=False):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk"); monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    fake = _FakeBifrostClient()
    monkeypatch.setattr(sp, "httpx", type("h", (), {"Client": lambda *a, **k: fake}))
    monkeypatch.setattr(sp, "_bifrost_ids", lambda: ids)
    monkeypatch.setattr(sp, "_langfuse_native", lambda c, name: langfuse)
    monkeypatch.setattr(sp, "_mlflow_native", lambda name: mlflow)
    monkeypatch.setattr(sp, "MIRROR_MLFLOW", mirror)
    return fake


def test_reconcile_skips_when_downstream_matches_canonical(monkeypatch):
    items = [{"name": "p1", "messages": [{"role": "user", "content": "same"}]}]
    same = ([{"role": "user", "content": "same"}], 100.0)     # langfuse content == bifrost canonical
    fake = _wire(monkeypatch, ids={"p1": "id1"}, langfuse=same)
    assert sp.reconcile_inbound(items) == 0                   # loop-safe: no pull when hashes match
    assert fake.posts == []


def test_reconcile_pulls_native_edit_when_hash_differs(monkeypatch):
    items = [{"name": "p1", "messages": [{"role": "user", "content": "old"}]}]
    edited = ([{"role": "user", "content": "NEW human edit"}], 200.0)
    fake = _wire(monkeypatch, ids={"p1": "id1"}, langfuse=edited)
    assert sp.reconcile_inbound(items) == 1
    path, payload = fake.posts[0]
    assert path == "/api/prompt-repo/prompts/id1/versions"
    assert payload["messages"] == [{"role": "user", "content": "NEW human edit"}]
    assert payload["commit_message"].startswith("reconciled-from-langfuse:")


def test_reconcile_skips_when_name_absent_in_bifrost(monkeypatch):
    items = [{"name": "p1", "messages": [{"role": "user", "content": "old"}]}]
    edited = ([{"role": "user", "content": "new"}], 200.0)
    fake = _wire(monkeypatch, ids={}, langfuse=edited)        # native edit but no bifrost id
    assert sp.reconcile_inbound(items) == 0 and fake.posts == []


def test_reconcile_conflict_is_last_write_wins_by_timestamp(monkeypatch):
    items = [{"name": "p1", "messages": [{"role": "user", "content": "old"}]}]
    lf = ([{"role": "user", "content": "from-langfuse"}], 100.0)
    mf = ([{"role": "user", "content": "from-mlflow"}], 300.0)   # newer → wins
    fake = _wire(monkeypatch, ids={"p1": "id1"}, langfuse=lf, mlflow=mf, mirror=True)
    assert sp.reconcile_inbound(items) == 1
    _, payload = fake.posts[0]
    assert payload["messages"][0]["content"] == "from-mlflow"
    assert payload["commit_message"].startswith("reconciled-from-mlflow:")
