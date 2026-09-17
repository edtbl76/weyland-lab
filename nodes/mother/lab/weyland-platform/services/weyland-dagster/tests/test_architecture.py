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
    """The production graph obeys every boundary — 0 contracts broken. Covers all four contracts:
    leaves-are-dagster-free, leaves-do-not-import-factories, resources-are-independent (B152 upper
    layering), and leaves-are-resource-free."""
    r = _lint(".importlinter", SERVICE_ROOT)
    assert r.returncode == 0, f"architecture contracts broken:\n{r.stdout}\n{r.stderr}"
    assert "0 broken" in r.stdout, r.stdout


def test_planted_violation_breaks_the_contract():
    """Planted violations MUST break the contracts — proven by REASON, not bare exit code. The fixture
    commits three violations at once: a leaf imports dagster, a leaf imports a resource, and a resource
    (submodule) imports the assets layer. All three forbidden contracts must report BROKEN."""
    r = _lint(str(FIXTURES / "importlinter-violation.ini"), FIXTURES)
    # A missing binary exits 127 and a bare `!= 0` would pass on it — assert the real failure signal.
    assert r.returncode == 1, f"expected the violations to break the contracts (rc=1), got {r.returncode}:\n{r.stdout}\n{r.stderr}"
    assert "3 broken" in r.stdout, f"expected all three contracts broken:\n{r.stdout}"
    # Each contract's specific forbidden import must appear — never just a bare failure count.
    assert "badleaf_pkg.leaf -> dagster" in r.stdout, f"dagster-free violation not reported:\n{r.stdout}"
    assert "badleaf_pkg.leaf -> badleaf_pkg.resource" in r.stdout, f"resource-free violation not reported:\n{r.stdout}"
    # resource SUBMODULE -> assets proves the package-level source_modules covers descendants.
    assert "badleaf_pkg.resource.thing -> badleaf_pkg.asset" in r.stdout, f"resources-independent violation not reported:\n{r.stdout}"
