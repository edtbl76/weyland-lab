"""capabilities_skill: render capabilities.yaml + repos.yaml into the `weyland-capabilities` Agent Skill (B241).

The skill is what makes Weyland's capabilities discoverable from any managed repository: it is published to the
Bifrost plugin marketplace and installed at user level. These tests pin the rendering (coverage comes from repos.yaml
lanes, never duplicated), the validation (a capability that names an unknown lane or a missing runbook fails), and the
generated block inside register_bifrost_skills.py (rewritten by --write, compared by --check in CI).
"""
import pytest

import capabilities_skill as cs

REPOS = {"repos": [
    {"name": "weyland-lab", "status": "active", "linear_project": "Weyland Lab",
     "lanes": {"ci": True, "scan": True, "pr": True, "catalog": True, "backup": True, "iac": True}},
    {"name": "stud.io", "status": "active", "linear_project": "Stud.IO",
     "lanes": {"ci": True, "scan": True, "pr": True, "catalog": True, "backup": True, "iac": True}},
    {"name": "Algopedia", "status": "active", "linear_project": "Algopedia",
     "lanes": {"ci": False, "scan": True, "pr": True, "catalog": True, "backup": True, "iac": True}},
    {"name": "midi_real_book", "status": "stale", "lanes": {"catalog": True}},
]}

CAPS = {"capabilities": [
    {"key": "onboarding", "name": "Join Weyland's lanes", "summary": "steps per lane", "scope": "all",
     "use": ["Run onboard-repo.sh"], "runbook": "repo-coverage.md"},
    {"key": "ci", "name": "CI on Woodpecker", "summary": "pipelines", "scope": "lane", "lane": "ci",
     "use": ["woodpecker-cli pipeline create"], "runbook": "woodpecker.md"},
    {"key": "code-search", "name": "Code search", "summary": "indexed search", "scope": "weyland",
     "use": ["weyland-lab only today"], "runbook": "code-intelligence.md"},
]}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    for rb in ("repo-coverage.md", "woodpecker.md", "code-intelligence.md"):
        (tmp_path / "docs" / "runbooks" / rb).write_text("# x\n")
    return tmp_path


def test_a_valid_registry_has_no_errors(root):
    assert cs.validate(CAPS, root) == []


@pytest.mark.parametrize("change, reason", [
    ({"scope": "lane", "lane": "nonsense"}, "unknown lane"),
    ({"scope": "lane", "lane": None}, "needs a lane"),
    ({"scope": "everywhere"}, "unknown scope"),
    ({"runbook": "nope.md"}, "does not exist"),
    ({"use": []}, "no use steps"),
])
def test_invalid_capabilities_are_refused_with_the_reason(root, change, reason):
    bad = {"capabilities": [dict(CAPS["capabilities"][0], **change)]}
    errors = cs.validate(bad, root)
    assert any(reason in e for e in errors), errors


def test_duplicate_keys_are_refused(root):
    dup = {"capabilities": [CAPS["capabilities"][0], dict(CAPS["capabilities"][0])]}
    assert any("duplicate" in e for e in cs.validate(dup, root))


def test_render_lists_every_capability_with_steps_and_runbook():
    body = cs.render(CAPS, REPOS)
    for cap in CAPS["capabilities"]:
        assert f"### {cap['name']}" in body
        assert cap["use"][0] in body
        assert cap["runbook"] in body


def test_lane_coverage_comes_from_repos_yaml_for_active_repos_only():
    body = cs.render(CAPS, REPOS)
    rows = {ln.split("|")[1].strip(): ln for ln in body.splitlines() if ln.startswith("| ") and "|" in ln[2:]}
    assert "yes" in rows["stud.io"].split("|")[3] and "no" in rows["Algopedia"].split("|")[3]
    assert "midi_real_book" not in body          # stale repos are not offered anything
    assert "Repos with it now: weyland-lab, stud.io" in body


def test_scope_wording_says_who_has_it():
    body = cs.render(CAPS, REPOS)
    assert "Every managed repository" in body
    assert "weyland-lab only today" in body


def test_the_description_names_the_triggers_an_agent_will_hit():
    d = cs.DESCRIPTION.lower()
    for word in ("ci", "scan", "linear", "managed", "weyland"):
        assert word in d


def test_splice_replaces_only_the_generated_block():
    text = "a = 1\n" + cs.BEGIN + "\nold\n" + cs.END + "\nb = 2\n"
    out = cs.splice(text, "new block")
    assert out == "a = 1\n" + cs.BEGIN + "\nnew block\n" + cs.END + "\nb = 2\n"


def test_splice_without_markers_fails_closed():
    with pytest.raises(ValueError, match="markers"):
        cs.splice("no markers here\n", "x")


def test_skill_md_has_frontmatter_then_the_body():
    md = cs.skill_md(CAPS, REPOS)
    head, body = md.split("\n---\n", 1)
    assert head.startswith("---\nname: weyland-capabilities\n")
    assert 'description: "' in head
    assert body == cs.render(CAPS, REPOS)


def test_install_writes_the_shared_file_and_links_each_harness(tmp_path):
    written = cs.install(cs.skill_md(CAPS, REPOS), tmp_path)
    real = tmp_path / ".agents" / "skills" / "weyland-capabilities" / "SKILL.md"
    assert real.read_text() == cs.skill_md(CAPS, REPOS)
    for harness in (".claude", ".codex"):
        link = tmp_path / harness / "skills" / "weyland-capabilities"
        assert link.is_symlink() and (link / "SKILL.md").read_text() == real.read_text()
        assert not str(link.readlink()).startswith("/")      # relative, like the existing skills
    assert written == [real]


def test_install_is_idempotent(tmp_path):
    md = cs.skill_md(CAPS, REPOS)
    cs.install(md, tmp_path)
    assert cs.install(md, tmp_path) == []                    # nothing changed, nothing written


def test_install_refuses_to_replace_a_real_folder_with_a_link(tmp_path):
    (tmp_path / ".claude" / "skills" / "weyland-capabilities").mkdir(parents=True)
    with pytest.raises(ValueError, match="not a symlink"):
        cs.install(cs.skill_md(CAPS, REPOS), tmp_path)


def test_installed_drift_is_reported(tmp_path):
    md = cs.skill_md(CAPS, REPOS)
    assert cs.installed_problems(md, tmp_path)               # nothing installed yet
    cs.install(md, tmp_path)
    assert cs.installed_problems(md, tmp_path) == []
    (tmp_path / ".agents" / "skills" / "weyland-capabilities" / "SKILL.md").write_text("old\n")
    assert any("differs" in p for p in cs.installed_problems(md, tmp_path))


def test_the_generated_block_is_a_skills_append_with_the_rendered_body():
    block = cs.block(CAPS, REPOS)
    ns = {"SKILLS": []}
    exec(block, ns)                               # noqa: S102 - our own generated source, under test
    (name, category, description, body), = ns["SKILLS"]
    assert name == "weyland-capabilities" and category == "meta"
    assert description == cs.DESCRIPTION and body == cs.render(CAPS, REPOS)


def test_the_bifrost_plugin_copy_installed_too_is_a_duplicate(tmp_path):
    # Once the Bifrost marketplace serves again it offers the same skill as plugin bifrost-weyland-capabilities. The
    # user file is the one that stays current (regenerated from repos.yaml), so the plugin copy must not be installed.
    import json
    md = cs.skill_md(CAPS, REPOS)
    cs.install(md, tmp_path)
    plugins = tmp_path / ".claude" / "plugins" / "installed_plugins.json"
    plugins.parent.mkdir(parents=True)
    plugins.write_text(json.dumps({"version": 2, "plugins": {"bifrost-weyland-conventions@bifrost-skills": []}}))
    assert cs.installed_problems(md, tmp_path) == []
    plugins.write_text(json.dumps({"version": 2, "plugins": {"bifrost-weyland-capabilities@bifrost-skills": []}}))
    assert any("duplicate" in p for p in cs.installed_problems(md, tmp_path))
