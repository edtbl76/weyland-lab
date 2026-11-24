"""scripts/local-gates.py: the ONE command that replays CI's platform checks locally (B243, 2026-11-24).

AGENTS.md says "run the FULL local guard suite before any handoff", and until now there was no command for it: each
agent re-extracted the step commands from .woodpecker/platform.yml by hand. These tests pin the decisions the runner
makes: which steps run locally (the secret-free ones) and which are named as CI-only, that every step runs on a COPY
inside its own CI image (the repo is mounted read-only, so a root container can never write into the owner's tree),
and that a step missing from platform.yml is a failure, never a silent skip.
"""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("local_gates", ROOT / "scripts" / "local-gates.py")
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)

DOC = {"steps": [
    {"name": "yaml-syntax", "image": "pipelinecomponents/yamllint:latest", "commands": ["yamllint k8s/"]},
    {"name": "linear-sync", "image": "alpine:latest", "environment": {"LINEAR_API_KEY": {"from_secret": "x"}},
     "commands": ["sh scripts/check-linear-sync.sh"]},
    {"name": "test-python", "image": "python:3.12-slim", "environment": {"LANG_JUNIT_DIR": "reports/junit"},
     "commands": ["pip install -r r.txt", "bash scripts/run-lang-tests.sh python"]},
]}


def test_the_secret_free_steps_run_and_the_rest_are_named_ci_only():
    run, ci_only = lg.select(DOC, ["yaml-syntax", "test-python"])
    assert [s["name"] for s in run] == ["yaml-syntax", "test-python"]
    assert ci_only == ["linear-sync"]


def test_a_local_step_missing_from_platform_yml_fails_closed():
    with pytest.raises(lg.GateError, match="shell-tests"):
        lg.select(DOC, ["yaml-syntax", "shell-tests"])


def test_each_step_runs_on_a_copy_in_its_own_image_with_the_repo_read_only():
    step = DOC["steps"][2]
    argv = lg.docker_argv(step, pathlib.Path("/repo"))
    assert argv[:3] == ["docker", "run", "--rm"]
    assert "/repo:/src:ro" in argv and "python:3.12-slim" in argv
    assert argv[argv.index("--entrypoint") + 1] == "sh"
    assert "LANG_JUNIT_DIR=reports/junit" in argv
    script = argv[-1]
    assert script.startswith("set -e") and "cp -a /src /work" in script
    assert script.index("pip install -r r.txt") < script.index("run-lang-tests.sh python")


def test_secret_references_are_never_passed_into_a_container():
    argv = lg.docker_argv(DOC["steps"][1], pathlib.Path("/repo"))
    assert not any(a.startswith("LINEAR_API_KEY") for a in argv)


def test_the_verdict_is_a_pass_only_when_every_step_passed():
    assert lg.verdict({"a": 0, "b": 0}) == (True, "local-gates: PASS (2 steps)")
    ok, line = lg.verdict({"a": 0, "b": 1})
    assert not ok and "FAIL" in line and "b" in line
    assert lg.verdict({}) == (False, "local-gates: FAIL (no step ran)")


def test_the_step_list_can_come_from_a_trusted_file_while_the_tree_is_another(tmp_path, monkeypatch):
    # B243 fix branches: the branch under test must not be able to rewrite the steps that judge it.
    cfg = tmp_path / "platform.yml"
    cfg.write_text("steps:\n  - {name: shellcheck, image: koalaman/shellcheck-alpine:stable, commands: [true]}\n")
    seen = []
    monkeypatch.setattr(lg, "_run", lambda step, root, logs: seen.append((step["name"], root)) or 0)
    code = lg.main(["--root", str(tmp_path / "tree"), "--config", str(cfg), "--only", "shellcheck",
                    "--logs", str(tmp_path / "logs")])
    assert code == 0 and seen == [("shellcheck", (tmp_path / "tree").resolve())]
