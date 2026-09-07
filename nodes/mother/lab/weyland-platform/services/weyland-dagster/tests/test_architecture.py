"""Architecture-test lane (B152 category 1) — enforces the datasets_lib boundary with import-linter.

The real `.importlinter` forbids the pure leaf modules (the `*_parse` files, `_collect`, `land_core`,
`domain_job_plan`, `lakefs_repo`, …) from importing dagster, because `conftest.load_isolated` loads them
WITHOUT the dagster runtime. A leaf that grows `import dagster` silently loses that isolated coverage — the
exact class that took the dagster code server down (the autodiscovery `AssetChecksDefinition` bug).

import-linter uses grimp's static AST analysis, so it runs in the slim no-dagster lane where the boundary
actually matters. Two tests: the real contract holds (Green), and a planted violation BREAKS it by name
(the deliberately-failing fixture — proves the rule catches a real violation, not just that it loads).
The failure assertion checks the REASON in the output, never a bare non-zero exit (which would also pass on
exit 127 = command-not-found)."""
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
    """The production leaves obey the boundary — 0 contracts broken."""
    r = _lint(".importlinter", SERVICE_ROOT)
    assert r.returncode == 0, f"architecture contracts broken:\n{r.stdout}\n{r.stderr}"
    assert "0 broken" in r.stdout, r.stdout


def test_planted_violation_breaks_the_contract():
    """A leaf that imports dagster MUST break the contract — proven by REASON, not bare exit code."""
    r = _lint(str(FIXTURES / "importlinter-violation.ini"), FIXTURES)
    # A missing binary exits 127 and a bare `!= 0` would pass on it — assert the real failure signal.
    assert r.returncode == 1, f"expected the violation to break the contract (rc=1), got {r.returncode}:\n{r.stdout}\n{r.stderr}"
    out = r.stdout.upper()
    assert "BROKEN" in out, f"import-linter did not report a broken contract:\n{r.stdout}"
    assert "must not import dagster" in r.stdout, f"the specific forbidden-import reason is missing:\n{r.stdout}"
