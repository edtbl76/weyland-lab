"""Tests for scripts/lib/woodpecker_pipeline.py — reads the weyland-lab CI pipeline, which since B200 (2026-11-18) is a
directory of workflows (.woodpecker/*.yml) instead of one .woodpecker.yml. Every guard that inspects the pipeline's
steps (check-maps, image provenance, select-fixtures, the netpol and apt tests) goes through it.

What these pin down: a directory and a single file both work (the guards' test fixtures are single files); only
*.yml / *.yaml count (the README in .woodpecker/ is not a workflow); each step carries its workflow; and anything it
cannot read is an error, never an empty pipeline that a guard would read as "nothing to check, all clean".
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

import woodpecker_pipeline as wp

STEP = "steps:\n  - name: {n}\n    image: alpine:3.20\n    commands: [echo {n}]\n"


def _dir(tmp_path, files):
    d = tmp_path / ".woodpecker"
    d.mkdir()
    for name, text in files.items():
        (d / name).write_text(text)
    return d


def test_a_directory_yields_every_workflow_in_name_order(tmp_path):
    d = _dir(tmp_path, {"b.yml": STEP.format(n="two"), "a.yml": STEP.format(n="one"), "README.md": "# not a workflow\n"})
    assert [name for name, _ in wp.workflows(str(d))] == ["a", "b"]


def test_steps_carry_their_workflow(tmp_path):
    d = _dir(tmp_path, {"a.yml": STEP.format(n="one"), "b.yaml": STEP.format(n="two")})
    assert [(w, s["name"]) for w, s in wp.steps(str(d))] == [("a", "one"), ("b", "two")]


def test_a_single_file_is_one_workflow_named_after_it(tmp_path):
    f = tmp_path / "pipe.yml"
    f.write_text(STEP.format(n="only"))
    assert [(w, s["name"]) for w, s in wp.steps(str(f))] == [("pipe", "only")]


def test_files_lists_the_workflow_files(tmp_path):
    d = _dir(tmp_path, {"a.yml": STEP.format(n="one"), "README.md": "x"})
    assert wp.files(str(d)) == [str(d / "a.yml")]


def test_a_missing_path_is_an_error_not_an_empty_pipeline(tmp_path):
    with pytest.raises(wp.PipelineError, match="not found"):
        wp.steps(str(tmp_path / "absent"))


def test_a_directory_with_no_workflow_is_an_error(tmp_path):
    d = _dir(tmp_path, {"README.md": "x"})
    with pytest.raises(wp.PipelineError, match="no workflow"):
        wp.steps(str(d))


def test_an_unparseable_workflow_is_an_error_naming_the_file(tmp_path):
    d = _dir(tmp_path, {"bad.yml": "steps: [unclosed\n"})
    with pytest.raises(wp.PipelineError, match="bad.yml"):
        wp.steps(str(d))


def test_a_workflow_without_a_step_list_is_an_error(tmp_path):
    d = _dir(tmp_path, {"a.yml": "labels: {backend: kubernetes}\n"})
    with pytest.raises(wp.PipelineError, match="a.yml"):
        wp.steps(str(d))


def test_the_real_pipeline_reads(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    got = wp.steps(os.path.join(root, ".woodpecker"))
    assert len(got) > 50 and {"platform", "finish"} <= {w for w, _ in got}
