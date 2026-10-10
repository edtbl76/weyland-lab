"""Validate the Bifrost Skills registry SoT (register_bifrost_skills.py).

The `SKILLS` list is the git source of truth for the Bifrost Skills Repository. A malformed entry (a non-kebab
name, an empty body, a DUPLICATE name) breaks the idempotent register at runtime — a duplicate is exactly what
produced the "skill name already exists" run on 2026-09-23. This guards the list's shape, and by importing the
module it also exercises the module-level data (so the script counts toward coverage instead of sitting at 0% and
regressing the ratchet). `httpx` is lazy-imported inside `main()`, so importing here needs no network deps.
"""
import re

import pytest

import register_bifrost_skills as reg   # conftest.py puts scripts/ on sys.path (bare-name import, as the script runs)

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def test_skills_list_is_wellformed():
    skills = reg.SKILLS
    assert skills, "SKILLS is empty"
    for entry in skills:
        assert len(entry) == 4, f"skill tuple must be (name, category, description, body): {entry[:1]}"
        name, category, description, body = entry
        assert _KEBAB.match(name), f"skill name is not kebab-case: {name!r}"
        assert category.strip(), f"{name}: empty category"
        assert description.strip(), f"{name}: empty description"
        assert body.strip(), f"{name}: empty body"


def test_skill_names_are_unique():
    # A duplicate name makes the register POST collide ("already exists") — fail here, not at deploy time.
    names = [s[0] for s in reg.SKILLS]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate skill names: {dupes}"


def test_loop_skills_are_present():
    # The B175 loop-library seed — guard that the four loop-shaped skills stay registered.
    names = {s[0] for s in reg.SKILLS}
    expected = {"dod-gate", "master-the-tool-walk", "pr-lifecycle-reconcile", "full-guard-suite-preship"}
    assert expected <= names, f"missing loop skills: {sorted(expected - names)}"


# ---- B204: reconcile = create the missing, publish a new version of the changed, leave the equal alone ----------
# The fake mirrors the shapes OBSERVED on live Bifrost v2.2.6 (2026-10-09, read-only GET): the list is
# {skills, total, limit, offset}, pages by `offset`, and every item's `skill_md_body` is EMPTY; the real body is only
# in GET /api/skills/{id}, wrapped as {"skill": {...}}.

GIT = ("demo-skill", "deploy", "A demo skill.", "Step 1.\nStep 2.\n")


class _Resp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text or str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 300:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeBifrost:
    """Bifrost's skills API, in memory. `live` = full skill dicts; the list endpoint blanks their bodies."""

    def __init__(self, live=(), page=100, put_status=200, post_status=200, list_status=200):
        self.live = {s["name"]: dict(s) for s in live}
        self.page, self.put_status, self.post_status, self.list_status = page, put_status, post_status, list_status
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        if path == "/api/skills":
            if self.list_status >= 300:
                return _Resp(self.list_status, {"error": "nope"})
            off = (params or {}).get("offset", 0)
            items = [{**s, "skill_md_body": ""} for s in self.live.values()][off:off + self.page]
            return _Resp(200, {"skills": items, "total": len(self.live), "limit": 50, "offset": off})
        sid = path.rsplit("/", 1)[1]
        for s in self.live.values():
            if s["id"] == sid:
                return _Resp(200, {"skill": s})
        return _Resp(404, {"error": "not found"})

    def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        return _Resp(self.post_status, {"skill": {"id": "new"}})

    def put(self, path, json=None):
        self.calls.append(("PUT", path, json))
        return _Resp(self.put_status, {"skill": {"id": path.rsplit("/", 1)[1]}})

    def writes(self):
        return [c for c in self.calls if c[0] in ("POST", "PUT")]


def _live(name=GIT[0], category=GIT[1], description=GIT[2], body=GIT[3], version="1.1.0", sid="id-1"):
    return {"id": sid, "name": name, "description": description, "metadata": {"category": category},
            "skill_md_body": body, "latest_version": version}


def test_changed_body_sends_exactly_one_put_with_git_body_and_bumped_patch():
    fake = FakeBifrost([_live(body="stale body")])
    counts = reg.reconcile(fake, [GIT])
    assert fake.writes() == [("PUT", "/api/skills/id-1", {
        "description": GIT[2], "skill_md_body": GIT[3], "version": "1.1.1", "compatibility": reg.COMPAT,
        "allowed_tools": "", "license": "MIT", "metadata": {"category": GIT[1]}})]
    assert counts == {"created": 0, "updated": 1, "unchanged": 0, "failed": 0}


@pytest.mark.parametrize("field", ["description", "category"])
def test_changed_description_or_category_is_an_update(field):
    fake = FakeBifrost([_live(**{field: "something else"})])
    assert reg.reconcile(fake, [GIT])["updated"] == 1
    assert [c[0] for c in fake.writes()] == ["PUT"]


def test_equal_skills_send_no_write_even_though_the_list_bodies_are_empty():
    # The list's skill_md_body is always "" — comparing against it would make every skill look changed (the bug the
    # first trial shipped). Equality must be judged on the per-skill GET's real body.
    other = ("other-skill", "loop", "Other.", "Body.")
    fake = FakeBifrost([_live(), _live(*other, sid="id-2")])
    counts = reg.reconcile(fake, [GIT, other])
    assert fake.writes() == []
    assert counts == {"created": 0, "updated": 0, "unchanged": 2, "failed": 0}


def test_whitespace_only_difference_is_a_change():
    fake = FakeBifrost([_live(body=GIT[3].rstrip("\n"))])
    assert reg.reconcile(fake, [GIT])["updated"] == 1


def test_missing_skill_is_created_with_post_exactly_as_before():
    fake = FakeBifrost([])
    counts = reg.reconcile(fake, [GIT])
    assert fake.writes() == [("POST", "/api/skills", {
        "name": GIT[0], "version": reg.VERSION, "description": GIT[2], "skill_md_body": GIT[3],
        "compatibility": reg.COMPAT, "allowed_tools": "", "license": "MIT", "metadata": {"category": GIT[1]}})]
    assert counts["created"] == 1


def test_a_skill_on_a_later_page_is_found_not_posted():
    # The list ignores `limit`; a skill past the first page must still be seen, or it is POSTed and collides.
    filler = [_live(name=f"filler-{i}", sid=f"f{i}") for i in range(5)]
    fake = FakeBifrost(filler + [_live()], page=2)
    counts = reg.reconcile(fake, [GIT])
    assert fake.writes() == [] and counts["unchanged"] == 1
    offsets = [c[2]["offset"] for c in fake.calls if c[:2] == ("GET", "/api/skills")]
    assert offsets == [0, 2, 4, 6], "must page by offset until an empty page"


def test_skills_not_in_git_are_never_read_or_written():
    fake = FakeBifrost([_live(), _live(name="ek-not-ours", sid="kb-1", body="x")])
    reg.reconcile(fake, [GIT])
    assert not [c for c in fake.calls if "kb-1" in c[1]]


@pytest.mark.parametrize("status", [409, 500, 503])
def test_a_failed_put_counts_as_failed(status):
    fake = FakeBifrost([_live(body="stale")], put_status=status)
    assert reg.reconcile(fake, [GIT]) == {"created": 0, "updated": 0, "unchanged": 0, "failed": 1}


@pytest.mark.parametrize("bad", ["1.1", "v1.1.0", "1.1.0-rc1", "", None, "latest"])
def test_non_semver_latest_version_fails_that_skill_and_is_never_guessed(bad):
    fake = FakeBifrost([_live(body="stale", version=bad)])
    assert reg.reconcile(fake, [GIT])["failed"] == 1
    assert fake.writes() == [], "no PUT may be sent with a guessed version"


def test_bump_patch():
    assert reg.bump_patch("1.1.0") == "1.1.1"
    assert reg.bump_patch("2.0.9") == "2.0.10"
    with pytest.raises(ValueError, match="not semver"):
        reg.bump_patch("1.2")


def test_unreachable_or_unauthorized_list_raises_before_any_write():
    # A 401 (missing setup token) or an outage must never read as "nothing exists" (which would POST everything)
    # nor as a partial "unchanged".
    fake = FakeBifrost([_live()], list_status=401)
    with pytest.raises(RuntimeError, match="401"):
        reg.reconcile(fake, [GIT])
    assert fake.writes() == []


def test_main_prints_the_summary_and_exits_1_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(reg, "reconcile", lambda client, skills: {"created": 1, "updated": 2, "unchanged": 3, "failed": 1})
    monkeypatch.setattr(reg, "_client", lambda: None)
    with pytest.raises(SystemExit) as e:
        reg.main()
    assert e.value.code == 1
    assert capsys.readouterr().out.strip().splitlines()[-1] == \
        f"done. 1 created, 2 updated, 3 unchanged, 1 failed. {len(reg.SKILLS)} skills total."


def test_main_exits_0_when_nothing_failed(monkeypatch, capsys):
    monkeypatch.setattr(reg, "reconcile", lambda client, skills: {"created": 0, "updated": 0, "unchanged": 4, "failed": 0})
    monkeypatch.setattr(reg, "_client", lambda: None)
    reg.main()
    assert "0 created, 0 updated, 4 unchanged, 0 failed" in capsys.readouterr().out
