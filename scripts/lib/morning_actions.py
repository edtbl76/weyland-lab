"""morning_actions.py — the ONLY code the B243 morning remediation runner uses to act (2026-11-24).

The owner approved four actions ("yes, approve all four"), listed with their exact argv in scripts/morning/allowlist.yaml.
`plan()` turns a request into a validated command or refuses it; `execute()` runs a plan and records it. Refused:
an action not on the list, a parameter that does not match its pattern, a missing or extra parameter, a second attempt
at the same item in one night (the ledger survives a runner restart), and a user timer that is not a scheduled job
placement.yaml lists on rogueone. Commands run from their argv list, never through a shell, so a parameter can only
ever be one argument. Tests: scripts/tests/test_morning_actions.py. Runbook: docs/runbooks/morning-remediation.md.
"""
import dataclasses
import json
import os
import pathlib
import re
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWLIST = ROOT / "scripts" / "morning" / "allowlist.yaml"
PLACEMENT = ROOT / "placement.yaml"
TIMEOUT_S = 300


class Refused(Exception):
    """The request is not something the allowlist permits."""


@dataclasses.dataclass(frozen=True)
class Plan:
    action: str
    params: dict
    argv: list
    stdin: str | None
    env_file: str | None


@dataclasses.dataclass(frozen=True)
class Result:
    ok: bool
    detail: str


def load_allowlist(path: pathlib.Path = ALLOWLIST) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _key(action: str, params: dict) -> str:
    return action + "|" + json.dumps(params, sort_keys=True)


class Ledger:
    """What the runner attempted tonight, one JSON list per night, so each item is tried at most once."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.entries = json.loads(self.path.read_text()) if self.path.exists() else []

    def attempted(self, action: str, params: dict) -> bool:
        return any(_key(e["action"], e["params"]) == _key(action, params) for e in self.entries)

    def record(self, plan: Plan, ok: bool, detail: str) -> None:
        self.entries.append({"action": plan.action, "params": plan.params, "ok": ok, "detail": detail[:500]})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=1))


def _scheduled_user_units() -> set:
    """rogueone .service units that placement.yaml lists together with their .timer (scheduled jobs only)."""
    text = PLACEMENT.read_text(encoding="utf-8")
    units = set(re.findall(r'"user-systemd:rogueone/([a-z0-9@._-]+)"', text))
    return {u for u in units if u.endswith(".service") and u[:-len(".service")] + ".timer" in units}


def plan(allow: dict, action: str, params: dict, *, date: str, ledger: Ledger) -> Plan:
    spec = (allow.get("actions") or {}).get(action)
    if not spec:
        raise Refused(f"{action!r} is not on the allowlist (scripts/morning/allowlist.yaml)")
    patterns = spec.get("params") or {}
    missing = sorted(set(patterns) - set(params))
    extra = sorted(set(params) - set(patterns))
    if missing:
        raise Refused(f"{action}: missing parameter(s) {', '.join(missing)}")
    if extra:
        raise Refused(f"{action}: unexpected parameter(s) {', '.join(extra)}")
    for name, pattern in patterns.items():
        if not isinstance(params[name], str) or not re.fullmatch(pattern, params[name]):
            raise Refused(f"{action}: parameter {name}={params[name]!r} does not match {pattern}")
    if action == "user-timer-rerun" and params["unit"] not in _scheduled_user_units():
        raise Refused(f"{params['unit']} is not a scheduled rogueone job in placement.yaml")
    if ledger.attempted(action, params):
        raise Refused(f"{action} {params} was already attempted tonight; never twice in one night")
    values = {**params, "date_compact": date.replace("-", "")}
    argv = [part.format(**values) for part in spec["argv"]]
    stdin = str(ROOT / spec["stdin"]) if spec.get("stdin") else None
    env_file = str(ROOT / spec["env_file"]) if spec.get("env_file") else None
    return Plan(action, dict(params), argv, stdin, env_file)


def _env_from(path: str | None, base: dict) -> dict:
    env = dict(base)
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return env


def execute(allow: dict, action: str, params: dict, *, date: str, ledger: Ledger, env: dict | None = None) -> Result:
    """Plan, run (argv only, a time limit), record. A refusal raises Refused before anything runs."""
    p = plan(allow, action, params, date=date, ledger=ledger)
    stdin = open(p.stdin, encoding="utf-8").read() if p.stdin else None
    try:
        done = subprocess.run(p.argv, input=stdin, capture_output=True, text=True, timeout=TIMEOUT_S,
                              env=_env_from(p.env_file, os.environ if env is None else env))
        ok, detail = done.returncode == 0, (done.stdout or done.stderr or "").strip()[-500:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        ok, detail = False, f"{type(exc).__name__}: {exc}"[:500]
    ledger.record(p, ok=ok, detail=detail)
    return Result(ok, detail)
