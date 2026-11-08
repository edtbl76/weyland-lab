"""scratch_vault: the decisions behind the `vault` and `vault-rm` shortcuts (B187 follow-on).

claude-obsidian previews every write and applies only with the plan's hash; this module checks that the plan stays
inside the new vault before approving it, and that `vault-rm` deletes only a real scratch vault. The claude-obsidian
CLI is faked here; its real JSON contract was observed in the B187 run (status dry-run, changed_paths,
approved_plan_sha256; then status complete).
"""
import json

import pytest

import scratch_vault as sv


@pytest.mark.parametrize("topic, reason", [
    ("", "empty"),
    ("B22-search", "lowercase"),
    ("b187", "B-number"),
    ("b22-search", "B-number"),
    ("../etc", "lowercase"),
    ("meta search", "lowercase"),
])
def test_topic_names_are_plain_lowercase_slugs_without_b_numbers(topic, reason):
    with pytest.raises(sv.VaultError, match=reason):
        sv.validate_topic(topic)


def test_a_good_topic_passes():
    assert sv.validate_topic("metasearch") == "metasearch"
    assert sv.validate_topic("dify-2") == "dify-2"


def _plan(vault, paths, status="dry-run", sha="a" * 64):
    return json.dumps({"status": status, "changed_paths": paths, "approved_plan_sha256": sha})


def test_plan_inside_the_vault_is_approved(tmp_path):
    v = tmp_path / "metasearch"
    assert sv.approve_plan(_plan(v, [".gitignore", "wiki/index.md"]), v) == "a" * 64


@pytest.mark.parametrize("paths, reason", [
    (["../outside.md"], "outside"),
    (["/etc/passwd"], "outside"),
    ([], "no paths"),
])
def test_plan_that_escapes_or_is_empty_is_refused(tmp_path, paths, reason):
    with pytest.raises(sv.VaultError, match=reason):
        sv.approve_plan(_plan(tmp_path / "v", paths), tmp_path / "v")


def test_plan_that_is_not_a_preview_is_refused(tmp_path):
    with pytest.raises(sv.VaultError, match="dry-run"):
        sv.approve_plan(_plan(tmp_path / "v", ["a.md"], status="complete"), tmp_path / "v")


class FakeCli:
    """Records the claude-obsidian argv it was given and answers like the real CLI."""

    def __init__(self, apply_status="complete", plan_paths=(".gitignore", "wiki/index.md")):
        self.calls = []
        self.apply_status = apply_status
        self.plan_paths = list(plan_paths)

    def __call__(self, argv):
        self.calls.append(argv)
        if "--apply" in argv:
            target = argv[argv.index("init") + 1]
            from pathlib import Path
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / ".claude-obsidian.json").write_text("{}")
            return json.dumps({"status": self.apply_status})
        return _plan(None, self.plan_paths, sha="b" * 64)


def test_create_previews_then_applies_with_the_plans_hash(tmp_path):
    cli = FakeCli()
    path = sv.create("metasearch", tmp_path, cli)
    assert path == tmp_path / "metasearch"
    preview, apply = cli.calls
    assert "--apply" not in preview
    assert apply[apply.index("--approved-plan-sha256") + 1] == "b" * 64
    assert "--apply" in apply


def test_create_fails_when_the_apply_does_not_complete(tmp_path):
    with pytest.raises(sv.VaultError, match="did not complete"):
        sv.create("metasearch", tmp_path, FakeCli(apply_status="conflict"))


def test_create_refuses_a_plan_that_escapes(tmp_path):
    cli = FakeCli(plan_paths=["../x.md"])
    with pytest.raises(sv.VaultError, match="outside"):
        sv.create("metasearch", tmp_path, cli)
    assert len(cli.calls) == 1  # never applied


def test_create_reuses_an_existing_vault_without_writing(tmp_path):
    (tmp_path / "metasearch").mkdir()
    (tmp_path / "metasearch" / ".claude-obsidian.json").write_text("{}")
    cli = FakeCli()
    assert sv.create("metasearch", tmp_path, cli) == tmp_path / "metasearch"
    assert cli.calls == []


def test_create_refuses_an_existing_folder_that_is_not_a_vault(tmp_path):
    (tmp_path / "metasearch").mkdir()
    with pytest.raises(sv.VaultError, match="not a scratch vault"):
        sv.create("metasearch", tmp_path, FakeCli())


def test_removable_returns_a_real_vault(tmp_path):
    (tmp_path / "metasearch").mkdir()
    (tmp_path / "metasearch" / ".claude-obsidian.json").write_text("{}")
    assert sv.removable("metasearch", tmp_path) == tmp_path / "metasearch"


def test_removable_refuses_a_missing_folder(tmp_path):
    with pytest.raises(sv.VaultError, match="no scratch vault"):
        sv.removable("metasearch", tmp_path)


def test_removable_refuses_a_folder_that_is_not_a_vault(tmp_path):
    (tmp_path / "notes").mkdir()
    with pytest.raises(sv.VaultError, match="not a scratch vault"):
        sv.removable("notes", tmp_path)


def test_removable_refuses_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / ".claude-obsidian.json").write_text("{}")
    (tmp_path / "linked").symlink_to(real)
    with pytest.raises(sv.VaultError, match="symlink"):
        sv.removable("linked", tmp_path)
