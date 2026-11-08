"""Decisions behind the `vault` and `vault-rm` shortcuts (B187 follow-on). Stdlib only.

`create` drives claude-obsidian's preview-then-apply init: it approves the plan only when every path it would write
sits inside the new vault, then applies with that plan's hash. `removable` lets `vault-rm` delete only a real scratch
vault (a directory, not a symlink, holding `.claude-obsidian.json`) directly under the scratch-vault root.
Runbook: docs/runbooks/research-scratch-vault.md.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

MARKER = ".claude-obsidian.json"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
B_NUMBER = re.compile(r"^b\d+(\b|-|$)")


class VaultError(Exception):
    """A refusal with a reason the shortcut prints as-is."""


def validate_topic(topic: str) -> str:
    if not topic:
        raise VaultError("topic is empty: name the vault after its topic, e.g. `vault metasearch`")
    if not SLUG.match(topic):
        raise VaultError(f"topic {topic!r} must be lowercase letters, digits and hyphens")
    if B_NUMBER.match(topic):
        raise VaultError(f"topic {topic!r} looks like a B-number; name it by topic instead (owner, 2026-11-07)")
    return topic


def approve_plan(plan_json: str, vault: Path) -> str:
    """Return the plan's hash when it is a preview whose every path stays inside the vault; refuse otherwise."""
    plan = json.loads(plan_json)
    if plan.get("status") != "dry-run":
        raise VaultError(f"expected a dry-run preview, got status {plan.get('status')!r}")
    paths = plan.get("changed_paths") or []
    if not paths:
        raise VaultError("the preview lists no paths; refusing to apply an empty plan")
    root = vault.resolve()
    for p in paths:
        rel = p if isinstance(p, str) else p.get("path", "")
        target = (root / rel).resolve()
        if Path(rel).is_absolute() or (target != root and root not in target.parents):
            raise VaultError(f"the preview writes {rel!r}, outside {root}")
    sha = plan.get("approved_plan_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise VaultError("the preview has no approved_plan_sha256")
    return sha


def _init_argv(vault: Path, stamp: str, op_id: str) -> list[str]:
    return ["init", str(vault), "--generated-at", stamp, "--operation-id", op_id]


def create(topic: str, root: Path, run_cli: Callable[[list[str]], str], now: datetime | None = None) -> Path:
    """Create (or reuse) the vault for `topic`; `run_cli(argv)` runs claude-obsidian and returns its stdout."""
    vault = root / validate_topic(topic)
    if vault.exists():
        if vault.is_dir() and not vault.is_symlink() and (vault / MARKER).is_file():
            return vault
        raise VaultError(f"{vault} exists and is not a scratch vault; pick another topic")
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    argv = _init_argv(vault, stamp, f"{topic}-init")
    sha = approve_plan(run_cli(argv), vault)
    result = json.loads(run_cli(argv + ["--approved-plan-sha256", sha, "--apply"]))
    if result.get("status") != "complete" or not (vault / MARKER).is_file():
        raise VaultError(f"claude-obsidian init did not complete (status {result.get('status')!r})")
    return vault


def removable(topic: str, root: Path) -> Path:
    vault = root / validate_topic(topic)
    if vault.is_symlink():
        raise VaultError(f"{vault} is a symlink; refusing to delete through it")
    if not vault.exists():
        raise VaultError(f"no scratch vault named {topic!r} under {root}")
    if not vault.is_dir() or not (vault / MARKER).is_file():
        raise VaultError(f"{vault} is not a scratch vault (no {MARKER}); refusing to delete it")
    return vault
