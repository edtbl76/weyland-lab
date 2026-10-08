"""Tests for scripts/register_bifrost_loops.py — publishes the B175 loop library into Bifrost's Prompt Repository.

Git (knowledge-repos/loop-library, bundled to scripts/loop_library.json) is the source of truth, so unlike
register_bifrost_prompts.py — which skips an existing prompt — this publisher must ADD A VERSION when a loop changed
and do nothing when it did not (no version churn on the weekly reconcile). The fake below encodes the Prompt
Repository shapes OBSERVED live on 2026-10-08: GET /folders -> {"folders":[{id,name}]}, GET /prompts ->
{"prompts":[{id,name,folder_id}]}, GET /prompts/{id}/versions -> {"versions":[{is_latest, messages:[{message:{role,
content}}]}]}. No httpx and no network: the client is injected.
"""
import json

import pytest

import register_bifrost_loops as loops   # conftest.py puts scripts/ on sys.path (bare-name import, as the script runs)

LOOP = {"id": "ci-watch", "title": "The CI watch", "category": "Operations", "description": "Watch CI.",
        "terminal_condition": "The pipeline reaches success, or a step fails twice.", "prompt": "Trigger it."}


class FakeBifrost:
    """An in-memory Prompt Repository answering with the observed shapes."""

    def __init__(self, folders=None, prompts=None, versions=None, fail_post=None):
        self.folders = folders or []
        self.prompts = prompts or []
        self.versions = versions or {}
        self.posts = []
        self.fail_post = fail_post

    def get(self, path):
        self.gets = getattr(self, "gets", []) + [path]
        if path == "/api/prompt-repo/folders":
            return {"folders": self.folders}
        if path.startswith("/api/prompt-repo/prompts?"):
            return {"prompts": self.prompts}
        pid = path.split("/")[-2]
        return {"versions": self.versions.get(pid, [])}

    def post(self, path, body):
        self.posts.append((path, body))
        if self.fail_post and self.fail_post in path:
            return 500, {"error": "boom"}
        if path.endswith("/folders"):
            self.folders.append({"id": "f-new", "name": body["name"]})
            return 200, {"folder": {"id": "f-new"}}
        if path.endswith("/prompts"):
            self.prompts.append({"id": "p-new", "name": body["name"], "folder_id": body["folder_id"]})
            return 200, {"prompt": {"id": "p-new"}}
        return 200, {"version": {"id": 1}}


def _latest(content):
    return [{"is_latest": True, "messages": [{"message": {"role": "user", "content": content}}]}]


def test_the_message_carries_the_terminal_condition_and_the_prompt():
    text = loops.message(LOOP)
    assert "Stop when:" in text and LOOP["terminal_condition"] in text and text.rstrip().endswith("Trigger it.")


def test_a_new_loop_creates_the_folder_the_prompt_and_its_first_version():
    fake = FakeBifrost()
    summary = loops.publish(fake, [LOOP])
    paths = [p for p, _ in fake.posts]
    assert paths == ["/api/prompt-repo/folders", "/api/prompt-repo/prompts", "/api/prompt-repo/prompts/p-new/versions"]
    assert fake.posts[1][1]["name"] == "loop-ci-watch"
    version = fake.posts[2][1]
    assert version["messages"] == [{"role": "user", "content": loops.message(LOOP)}]
    assert "Operations" in version["commit_message"] and "variables" not in version   # variables 400 on this API
    assert summary == {"created": 1, "updated": 0, "unchanged": 0, "failed": 0, "orphans": []}


def test_an_unchanged_loop_posts_nothing():
    fake = FakeBifrost(folders=[{"id": "f1", "name": "loop-library"}],
                       prompts=[{"id": "p1", "name": "loop-ci-watch", "folder_id": "f1"}],
                       versions={"p1": _latest(loops.message(LOOP))})
    assert loops.publish(fake, [LOOP])["unchanged"] == 1
    assert fake.posts == []


def test_a_changed_loop_gets_a_new_version_not_a_skip():
    fake = FakeBifrost(folders=[{"id": "f1", "name": "loop-library"}],
                       prompts=[{"id": "p1", "name": "loop-ci-watch", "folder_id": "f1"}],
                       versions={"p1": _latest("an older text")})
    assert loops.publish(fake, [LOOP])["updated"] == 1
    assert fake.posts == [("/api/prompt-repo/prompts/p1/versions", fake.posts[0][1])]


def test_the_prompt_list_is_requested_unpaged():
    fake = FakeBifrost(folders=[{"id": "f1", "name": "loop-library"}])
    loops.publish(fake, [LOOP])
    assert "/api/prompt-repo/prompts?limit=1000" in fake.gets


def test_a_published_loop_no_longer_in_git_is_reported_not_deleted():
    fake = FakeBifrost(folders=[{"id": "f1", "name": "loop-library"}],
                       prompts=[{"id": "p9", "name": "loop-retired", "folder_id": "f1"},
                                {"id": "p2", "name": "loop-elsewhere", "folder_id": "other"}],
                       versions={})
    summary = loops.publish(fake, [LOOP])
    assert summary["orphans"] == ["loop-retired"]            # only this folder's prompts count
    assert not any("p9" in p for p, _ in fake.posts)


def test_a_failed_version_post_is_counted_and_fails_the_run(capsys):
    fake = FakeBifrost(fail_post="/versions")
    summary = loops.publish(fake, [LOOP])
    assert summary["failed"] == 1
    assert loops.exit_code(summary) == 1


def test_the_bundle_must_hold_loops(tmp_path):
    empty = tmp_path / "loop_library.json"
    empty.write_text(json.dumps({"loops": []}))
    with pytest.raises(ValueError):
        loops.read_bundle(empty)
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"loops": [LOOP]}))
    assert loops.read_bundle(good) == [LOOP]


def test_the_shipped_bundle_is_readable_and_every_loop_has_a_terminal_condition():
    shipped = loops.read_bundle(loops.BUNDLE)
    assert shipped and all(len(x["terminal_condition"]) >= 25 for x in shipped)
