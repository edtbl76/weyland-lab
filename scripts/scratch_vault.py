#!/usr/bin/env python3
"""Create or check a research scratch vault (the `vault` / `vault-rm` shortcuts).

  usage: scratch_vault.py create <topic>     create or reuse the vault; prints its path
         scratch_vault.py check-rm <topic>   prints the path only if it is a real scratch vault (the shell deletes it)

Environment: SCRATCH_VAULTS (default ~/Documents/scratch-vaults), CLAUDE_OBSIDIAN_HOME (default ~/claude-obsidian).
Exit codes: 0 done; 2 refused or failed, with the reason on stderr. Runbook: docs/runbooks/research-scratch-vault.md.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import scratch_vault as sv  # noqa: E402

HOME = Path.home()
ROOT = Path(os.environ.get("SCRATCH_VAULTS", HOME / "Documents" / "scratch-vaults"))
CLI = Path(os.environ.get("CLAUDE_OBSIDIAN_HOME", HOME / "claude-obsidian")) / "scripts" / "claude-obsidian.py"


def run_cli(argv: list[str]) -> str:
    r = subprocess.run([sys.executable, str(CLI), *argv], capture_output=True, text=True, cwd=CLI.parent.parent)
    if r.returncode != 0:
        raise sv.VaultError(f"claude-obsidian exited {r.returncode}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"create", "check-rm"}:
        print("usage: scratch_vault.py create <topic> | check-rm <topic>", file=sys.stderr)
        return 2
    action, topic = sys.argv[1], sys.argv[2]
    try:
        sv.validate_topic(topic)  # a bad name is refused first, whatever else is missing
        if action == "create":
            if not CLI.is_file():
                raise sv.VaultError(f"claude-obsidian not found at {CLI} (set CLAUDE_OBSIDIAN_HOME)")
            ROOT.mkdir(parents=True, exist_ok=True)
            print(sv.create(topic, ROOT, run_cli))
        else:
            print(sv.removable(topic, ROOT))
    except sv.VaultError as e:
        print(f"vault: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
