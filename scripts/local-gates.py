#!/usr/bin/env python3
"""local-gates.py — replay CI's platform checks locally, each in its own CI image (B243, 2026-11-24).

The canonical command behind AGENTS.md's "run the FULL local guard suite before any handoff":

  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/local-gates.py            # every local step
  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/local-gates.py --root <worktree> --only shellcheck

It reads the steps from .woodpecker/platform.yml (so it never drifts from CI) and runs the secret-free ones. Each step
runs in its CI image on a COPY of the tree: the tree is mounted read-only, so a root container never writes into it.
Steps that need secrets or a cluster are listed as CI-only, never silently passed. A step named here but missing from
platform.yml fails. The SonarQube pre-check stays its own command (docs/runbooks/code-quality.md).
Exit 0 only when every step passed. Tests: scripts/tests/test_local_gates.py. Runbook: docs/runbooks/woodpecker.md.
"""
import argparse
import concurrent.futures
import pathlib
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL_STEPS = ["yaml-syntax", "repo-guards", "shellcheck", "shell-tests", "complexity-triage", "rego-policies",
               "test-python", "test-shell"]
# git refuses a tree owned by another user; the copy is root-owned inside the container, the original is not.
GIT_SAFE = ["GIT_CONFIG_COUNT=1", "GIT_CONFIG_KEY_0=safe.directory", "GIT_CONFIG_VALUE_0=*"]


class GateError(Exception):
    pass


def select(doc: dict, wanted: list) -> tuple:
    """(the steps to run, in `wanted` order; the names of every other step, which only CI runs)."""
    steps = {s["name"]: s for s in doc.get("steps") or []}
    missing = [n for n in wanted if n not in steps]
    if missing:
        raise GateError(f"not in .woodpecker/platform.yml: {', '.join(missing)}")
    return [steps[n] for n in wanted], [n for n in steps if n not in wanted]


def docker_argv(step: dict, root: pathlib.Path) -> list:
    env = []
    for key, value in (step.get("environment") or {}).items():
        if isinstance(value, (str, int, float)):   # a {from_secret: ...} reference never enters a local container
            env += ["-e", f"{key}={value}"]
    for pair in GIT_SAFE:
        env += ["-e", pair]
    script = "set -e\ncp -a /src /work\ncd /work\n" + "\n".join(step.get("commands") or [])
    return ["docker", "run", "--rm", "-v", f"{root}:/src:ro", *env, "--entrypoint", "sh", step["image"], "-c", script]


def verdict(codes: dict) -> tuple:
    if not codes:
        return False, "local-gates: FAIL (no step ran)"
    failed = [n for n, c in codes.items() if c != 0]
    if failed:
        return False, f"local-gates: FAIL ({', '.join(failed)}; {len(codes) - len(failed)} of {len(codes)} passed)"
    return True, f"local-gates: PASS ({len(codes)} steps)"


def _run(step: dict, root: pathlib.Path, logs: pathlib.Path) -> int:
    log = logs / f"{step['name']}.log"
    with log.open("w") as out:
        try:
            return subprocess.run(docker_argv(step, root), stdout=out, stderr=subprocess.STDOUT,
                                  timeout=3600).returncode
        except subprocess.TimeoutExpired:
            out.write("\nlocal-gates: step exceeded 3600 s\n")
            return 124


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="the tree to check (default: this repository)")
    ap.add_argument("--only", nargs="+", metavar="STEP", help=f"a subset of: {' '.join(LOCAL_STEPS)}")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--logs", help="directory for one log per step (default: a new temporary directory)")
    ap.add_argument("--config", help="the platform.yml to read steps from (default: <root>/.woodpecker/platform.yml); "
                                     "B243 fix branches pass the trusted checkout's, so a branch cannot rewrite its judge")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.root).resolve()
    try:
        doc = yaml.safe_load(pathlib.Path(a.config or root / ".woodpecker" / "platform.yml").read_text())
        run, ci_only = select(doc, a.only or LOCAL_STEPS)
    except (OSError, GateError, yaml.YAMLError) as exc:
        print(f"local-gates: FAIL ({exc})")
        return 2
    logs = pathlib.Path(a.logs or tempfile.mkdtemp(prefix="local-gates-"))
    logs.mkdir(parents=True, exist_ok=True)
    print(f"local-gates: {len(run)} step(s) on {root}; logs in {logs}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as pool:
        futures = {s["name"]: pool.submit(_run, s, root, logs) for s in run}
        codes = {name: f.result() for name, f in futures.items()}
    for name, code in codes.items():
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {name}" + ("" if code == 0 else f"  (exit {code}, {logs}/{name}.log)"))
    if not a.only:
        print(f"  CI only (secrets or cluster): {', '.join(ci_only)}")
    ok, line = verdict(codes)
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
