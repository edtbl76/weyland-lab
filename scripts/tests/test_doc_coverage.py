"""doc_coverage: every deployed app has a runbook and a place on a map (B239 batch C).

The B239 audit found core systems with no runbook (Dagster, the tool-server, the RAG indexer) and deployed apps on no
map (Sourcebot, Zoekt, Promptfoo), and nothing caught either. Fuzzy text matching made that audit slow and noisy, so
the registry (`applications.yaml`) now names each app's runbook explicitly and this guard checks it exactly:
`runbook:` must name an existing runbook, or be null with a `runbook_gap:` reason (a known gap, reported, not
hidden). Map presence matches the app's name, key or `map_label:` in at least one `docs/*-map.html`.
"""
import doc_coverage as dc


def _tree(tmp_path, runbooks=("dagster.md",), maps=None):
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    for r in runbooks:
        (tmp_path / "docs" / "runbooks" / r).write_text("# x\n")
    for name, text in (maps or {"platform-map.html": "<div>Dagster</div><div>Sourcebot</div>"}).items():
        (tmp_path / "docs" / name).write_text(text)
    return tmp_path


def _app(key, **kw):
    return {"key": key, "name": kw.pop("name", key.title()), "deployed": kw.pop("deployed", True), **kw}


def test_an_app_with_an_existing_runbook_and_a_map_entry_passes(tmp_path):
    root = _tree(tmp_path)
    r = dc.check([_app("weyland-dagster", name="Dagster", runbook="dagster.md")], root)
    assert r.errors == [] and r.gaps == []


def test_a_missing_runbook_field_is_an_error(tmp_path):
    r = dc.check([_app("weyland-dagster", name="Dagster")], _tree(tmp_path))
    assert any("weyland-dagster" in e and "no runbook: field" in e for e in r.errors)


def test_a_runbook_that_does_not_exist_is_an_error(tmp_path):
    r = dc.check([_app("weyland-dagster", name="Dagster", runbook="dagstr.md")], _tree(tmp_path))
    assert any("dagstr.md" in e and "does not exist" in e for e in r.errors)


def test_an_anchor_after_the_runbook_name_is_allowed(tmp_path):
    r = dc.check([_app("weyland-dagster", name="Dagster", runbook="dagster.md#logs")], _tree(tmp_path))
    assert r.errors == []


def test_a_null_runbook_with_a_reason_is_a_reported_gap_not_an_error(tmp_path):
    r = dc.check([_app("sourcebot", name="Sourcebot", runbook=None, runbook_gap="B239 batch D")], _tree(tmp_path))
    assert r.errors == []
    assert r.gaps == ["sourcebot: B239 batch D"]


def test_a_null_runbook_without_a_reason_is_an_error(tmp_path):
    r = dc.check([_app("sourcebot", name="Sourcebot", runbook=None)], _tree(tmp_path))
    assert any("sourcebot" in e and "runbook_gap" in e for e in r.errors)


def test_an_app_on_no_map_is_an_error(tmp_path):
    root = _tree(tmp_path, runbooks=("x.md",), maps={"platform-map.html": "<div>Dagster</div>"})
    r = dc.check([_app("zoekt", name="Zoekt", runbook="x.md")], root)
    assert any("zoekt" in e and "no map" in e for e in r.errors)


def test_map_label_overrides_the_name_for_matching(tmp_path):
    root = _tree(tmp_path, runbooks=("x.md",), maps={"realm-of-agents-map.html": "<div>A2A Inspector</div>"})
    r = dc.check([_app("a2a-inspector", name="a2a-inspector", runbook="x.md", map_label="A2A Inspector")], root)
    assert r.errors == []


def test_map_matching_is_case_insensitive_and_whole_word(tmp_path):
    root = _tree(tmp_path, runbooks=("x.md",), maps={"platform-map.html": "<span>RAY head</span> trayicon"})
    assert dc.check([_app("ray", name="Ray", runbook="x.md")], root).errors == []
    # "ray" inside "trayicon" alone must not count
    root2 = _tree(tmp_path / "b", runbooks=("x.md",), maps={"platform-map.html": "<span>trayicon</span>"})
    assert dc.check([_app("ray", name="Ray", runbook="x.md")], root2).errors


def test_apps_not_deployed_here_are_skipped(tmp_path):
    r = dc.check([_app("coderabbit", deployed=False)], _tree(tmp_path))
    assert r.errors == [] and r.checked == 0


def test_cli_without_a_registry_exits_2(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    cli = Path(__file__).resolve().parents[1] / "check-doc-coverage.py"
    r = subprocess.run([sys.executable, str(cli), "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2 and "no registry" in r.stderr


def test_no_maps_at_all_fails_closed(tmp_path):
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    (tmp_path / "docs" / "runbooks" / "x.md").write_text("# x\n")
    r = dc.check([_app("ray", name="Ray", runbook="x.md")], tmp_path)
    assert any("no maps" in e for e in r.errors)
