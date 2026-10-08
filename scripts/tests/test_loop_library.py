"""Tests for scripts/loop_library.py — the B175 loop library's validator and bundler.

A loop is a reusable agent workflow: a prompt with checkpoints and an explicit terminal condition. The library's one
non-negotiable rule (EMA-233 acceptance criterion) is that an entry without a terminal condition is not accepted — a
loop that cannot say when it stops can run away. These tests pin that rule and the entry schema, the bundle the Dagster
publisher reads, and the exit-code contract (0 valid · 1 an entry is invalid · 2 the library could not be read).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loop_library  # noqa: E402

GOOD = """---
id: ci-watch
title: The CI watch
category: Operations
description: Watch a pipeline to a terminal state and fix what fails.
terminal_condition: The pipeline reaches success, or the same step fails twice after a fix.
source: docs/runbooks/woodpecker.md
---

## Prompt

Trigger the pipeline, then check it.
"""


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text)
    return tmp_path / name


def test_a_complete_entry_parses(tmp_path):
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md", GOOD))
    assert loop["id"] == "ci-watch"
    assert loop["category"] == "Operations"
    assert loop["prompt"] == "Trigger the pipeline, then check it."
    assert loop_library.problems(loop, "ci-watch") == []


@pytest.mark.parametrize("field", ["title", "category", "description", "terminal_condition"])
def test_a_missing_required_field_is_rejected(tmp_path, field):
    text = "\n".join(line for line in GOOD.splitlines() if not line.startswith(f"{field}:"))
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md", text))
    assert any(field in p for p in loop_library.problems(loop, "ci-watch"))


@pytest.mark.parametrize("vague", ["TBD", "when done", "n/a", "until it works"])
def test_a_placeholder_terminal_condition_is_rejected(tmp_path, vague):
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md",
                                     GOOD.replace("The pipeline reaches success, or the same step fails twice after a fix.", vague)))
    assert any("terminal_condition" in p for p in loop_library.problems(loop, "ci-watch"))


def test_an_unknown_category_is_rejected(tmp_path):
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md", GOOD.replace("category: Operations", "category: Misc")))
    assert any("category" in p for p in loop_library.problems(loop, "ci-watch"))


def test_the_id_must_match_the_file_name(tmp_path):
    loop = loop_library.parse(_write(tmp_path, "other-name.md", GOOD))
    assert any("id" in p for p in loop_library.problems(loop, "other-name"))


def test_an_empty_prompt_is_rejected(tmp_path):
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md", GOOD.replace("Trigger the pipeline, then check it.", "")))
    assert any("prompt" in p for p in loop_library.problems(loop, "ci-watch"))


def test_a_file_without_frontmatter_is_rejected(tmp_path):
    loop = loop_library.parse(_write(tmp_path, "ci-watch.md", "# just a heading\n\n## Prompt\n\nx\n"))
    assert loop_library.problems(loop, "ci-watch")


def test_validate_exit_codes(tmp_path, capsys):
    _write(tmp_path, "ci-watch.md", GOOD)
    _write(tmp_path, "README.md", "# the index, not a loop")
    assert loop_library.main(["validate", str(tmp_path)]) == 0
    _write(tmp_path, "broken.md", GOOD.replace("id: ci-watch", "id: broken").replace("terminal_condition:", "x:"))
    assert loop_library.main(["validate", str(tmp_path)]) == 1
    assert "broken" in capsys.readouterr().out


def test_an_empty_or_missing_library_is_exit_2_never_valid(tmp_path):
    assert loop_library.main(["validate", str(tmp_path)]) == 2          # no loops at all
    assert loop_library.main(["validate", str(tmp_path / "nope")]) == 2  # no directory


def test_bundle_is_sorted_stable_json_with_every_field(tmp_path):
    _write(tmp_path, "ci-watch.md", GOOD)
    _write(tmp_path, "a-first.md", GOOD.replace("id: ci-watch", "id: a-first"))
    bundle = json.loads(loop_library.bundle(tmp_path))
    assert [b["id"] for b in bundle["loops"]] == ["a-first", "ci-watch"]
    assert set(bundle["loops"][0]) >= {"id", "title", "category", "description", "terminal_condition", "prompt"}
    assert loop_library.bundle(tmp_path) == loop_library.bundle(tmp_path)   # byte-stable: the drift guard compares it


def test_bundle_refuses_an_invalid_library(tmp_path):
    _write(tmp_path, "ci-watch.md", GOOD.replace("terminal_condition:", "x:"))
    with pytest.raises(loop_library.InvalidLibrary):
        loop_library.bundle(tmp_path)
