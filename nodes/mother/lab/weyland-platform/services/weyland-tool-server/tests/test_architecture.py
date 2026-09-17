"""Architecture-test lane (B152) for weyland-tool-server — the shared verdict contract is framework-free.

guardrails/ here is verdict.py, the wire contract shared byte-for-byte with weyland-guard. It must stay
framework-free so a fastapi import can never propagate to every consumer of the shared type. main.py alone
wires it to HTTP. import-linter's grimp does static AST analysis, so this runs in the slim lane with only
import-linter installed.

Two tests: the real contract holds (0 broken), and a planted fastapi import BREAKS it by name — the failure is
asserted by REASON, never a bare non-zero exit (which would also pass on exit 127 = command-not-found)."""
import pathlib
import shutil
import subprocess

import pytest

SERVICE_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = pathlib.Path(__file__).resolve().parent / "arch" / "fixtures"

pytestmark = pytest.mark.skipif(
    shutil.which("lint-imports") is None,
    reason="import-linter not installed (add `import-linter` to requirements-test.txt for this lane)",
)


def _lint(config: str, cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["lint-imports", "--config", config],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_real_architecture_contracts_hold():
    """The shared verdict contract obeys the boundary — 0 contracts broken."""
    r = _lint(".importlinter", SERVICE_ROOT)
    assert r.returncode == 0, f"architecture contracts broken:\n{r.stdout}\n{r.stderr}"
    assert "0 broken" in r.stdout, r.stdout


def test_planted_violation_breaks_the_contract():
    """A guardrail that imports the web framework MUST break the contract — proven by REASON, not bare exit."""
    r = _lint(str(FIXTURES / "importlinter-violation.ini"), FIXTURES)
    # A missing binary exits 127 and a bare `!= 0` would pass on it — assert the real failure signal.
    assert r.returncode == 1, f"expected the violation to break the contract (rc=1), got {r.returncode}:\n{r.stdout}\n{r.stderr}"
    assert "1 broken" in r.stdout, r.stdout
    assert "badtool_pkg.bad -> fastapi" in r.stdout, f"the framework-import violation was not reported:\n{r.stdout}"
