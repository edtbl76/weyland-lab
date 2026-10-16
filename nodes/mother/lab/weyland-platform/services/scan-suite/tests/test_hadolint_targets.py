"""hadolint() lints Dockerfiles only (2026-10-16).

Why: the target list was `find -iname 'Dockerfile*'`, which also matches any file whose NAME starts with "dockerfile" —
scripts/lib/dockerfile_installs.py and scripts/tests/dockerfile-installs.bats (the B213 ratchet) each came back as a
hadolint DL1000 parse error, two "new" HIGH findings that were never Dockerfiles. A Dockerfile is `Dockerfile`, a
`Dockerfile.<variant>` (Dockerfile.feast, Dockerfile.pyflink) or a `<name>.dockerfile`.
"""


def test_real_dockerfile_names_are_targets(scan):
    for name in ("Dockerfile", "dockerfile", "Dockerfile.feast", "Dockerfile.pyflink", "api.dockerfile",
                 "build.Dockerfile"):
        assert scan._is_dockerfile(name), name


def test_files_that_merely_start_with_dockerfile_are_not(scan):
    for name in ("dockerfile_installs.py", "dockerfile-installs.bats", "dockerfile-installs.baseline",
                 "Dockerfiles.md", "Dockerfile.md", "Dockerfile.sh"):
        assert not scan._is_dockerfile(name), name


def test_hadolint_skips_non_dockerfiles_in_the_tree(scan, tmp_path, monkeypatch, captured_posts):
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "Dockerfile").write_text("FROM alpine\n")
    (tmp_path / "svc" / "Dockerfile.feast").write_text("FROM alpine\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "dockerfile_installs.py").write_text("print(1)\n")
    linted = []
    real_run = scan.subprocess.run

    class R:
        stdout = "[]"

    def fake_run(cmd, **kw):
        if cmd[0] == "hadolint":
            linted.append(cmd[-1].rsplit("/", 1)[-1])
            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(scan, "SRC", str(tmp_path))
    monkeypatch.setattr(scan, "OUT", str(tmp_path))
    monkeypatch.setattr(scan.subprocess, "run", fake_run)
    scan.hadolint()
    assert sorted(linted) == ["Dockerfile", "Dockerfile.feast"]
