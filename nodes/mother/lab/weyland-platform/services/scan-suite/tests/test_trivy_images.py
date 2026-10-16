"""trivy_images() — scan the images the manifests DEPLOY, not just the source tree (2026-10-16).

Why: 14 Dockerfiles install 103 Python packages straight from `pip install` lines (23 pinned, 80 unpinned), and no
source scanner reads a Dockerfile's pip line. tool-server's `mcp==1.28.1` sat in one through GHSA-84m7-p3x7-pcfv: the
source scan only saw it in the OTHER services' requirements files. Scanning the built image sees every installed
package, however it got there.

Which images: `scripts/ci/images.tsv` (name · build context · the manifests whose tag tracks it), at the tag the FIRST
listed manifest pins (`registry.weyland.lab/<name>:<tag>`, the lockstep rule images.tsv states). A repo without
images.tsv (every non-weyland repo) is skipped. A scan that fails or returns no report is recorded as BROKEN — never
as zero findings — and trivy-images.json carries the broken list so scan-diff.py can refuse to compare.
"""
import json


def _tsv(tmp_path, rows):
    p = tmp_path / "scripts" / "ci"
    p.mkdir(parents=True)
    (p / "images.tsv").write_text("# header\n" + "".join("\t".join(r) + "\n" for r in rows))


def _manifest(tmp_path, rel, text):
    m = tmp_path / "nodes/mother/lab/weyland-platform" / rel
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(text)


def _report(*vulns):
    return {"SchemaVersion": 2, "ArtifactName": "x", "Results": [{"Target": "Python", "Vulnerabilities": [
        {"VulnerabilityID": vid, "PkgName": pkg, "Severity": sev} for vid, pkg, sev in vulns]}]}


def test_deployed_images_reads_the_tag_each_first_manifest_pins(scan, tmp_path):
    _tsv(tmp_path, [("weyland-tool-server", "services/weyland-tool-server", "k8s/weyland-tool-server.yaml"),
                    ("feast-server", "services/weyland-dagster::Dockerfile.feast", "k8s/data-mesh/feast-server.yaml k8s/x.yaml")])
    _manifest(tmp_path, "k8s/weyland-tool-server.yaml", "image: registry.weyland.lab/weyland-tool-server:git-af3ae0c8\n")
    _manifest(tmp_path, "k8s/data-mesh/feast-server.yaml", "  image: registry.weyland.lab/feast-server:git-d3291ab9  # c\n")
    refs, missing = scan.deployed_images(str(tmp_path))
    assert refs == ["registry.weyland.lab/feast-server:git-d3291ab9",
                    "registry.weyland.lab/weyland-tool-server:git-af3ae0c8"]
    assert missing == []


def test_an_image_whose_manifest_pins_no_tag_is_named_missing_not_skipped(scan, tmp_path):
    _tsv(tmp_path, [("store-scaler", "services/store-scaler", "k8s/data-mesh/store-scaler.yaml")])
    _manifest(tmp_path, "k8s/data-mesh/store-scaler.yaml", "image: something-else:1\n")
    refs, missing = scan.deployed_images(str(tmp_path))
    assert refs == [] and missing == ["store-scaler"]


def test_a_repo_without_images_tsv_is_skipped(scan, tmp_path, monkeypatch, captured_posts):
    monkeypatch.setattr(scan, "SRC", str(tmp_path))
    monkeypatch.setattr(scan, "OUT", str(tmp_path))
    scan.trivy_images()
    assert not (tmp_path / "trivy-images.json").exists()
    assert not [p for p in captured_posts if p[0] == "trivy-images"]


def test_trivy_images_scans_each_ref_and_counts_by_severity(scan, tmp_path, monkeypatch, captured_posts):
    _tsv(tmp_path, [("a", "services/a", "k8s/a.yaml"), ("b", "services/b", "k8s/b.yaml")])
    _manifest(tmp_path, "k8s/a.yaml", "image: registry.weyland.lab/a:git-1\n")
    _manifest(tmp_path, "k8s/b.yaml", "image: registry.weyland.lab/b:git-2\n")
    monkeypatch.setattr(scan, "SRC", str(tmp_path))
    monkeypatch.setattr(scan, "OUT", str(tmp_path))
    reports = {"registry.weyland.lab/a:git-1": _report(("CVE-1", "mcp", "HIGH"), ("CVE-2", "x", "CRITICAL")),
               "registry.weyland.lab/b:git-2": _report(("CVE-3", "y", "LOW"))}
    monkeypatch.setattr(scan, "_trivy_image", lambda ref: reports[ref])
    scan.trivy_images()
    out = json.loads((tmp_path / "trivy-images.json").read_text())
    assert sorted(out["images"]) == sorted(reports) and out["broken"] == [] and out["missing"] == []
    assert captured_posts[-1] == ("trivy-images", {"critical": 1, "high": 1, "medium": 0, "low": 1})


def test_a_scan_that_returns_no_report_is_broken_not_zero(scan, tmp_path, monkeypatch, captured_posts):
    _tsv(tmp_path, [("a", "services/a", "k8s/a.yaml")])
    _manifest(tmp_path, "k8s/a.yaml", "image: registry.weyland.lab/a:git-1\n")
    monkeypatch.setattr(scan, "SRC", str(tmp_path))
    monkeypatch.setattr(scan, "OUT", str(tmp_path))
    monkeypatch.setattr(scan, "_trivy_image", lambda ref: None)
    scan.trivy_images()
    out = json.loads((tmp_path / "trivy-images.json").read_text())
    assert out["broken"] == ["registry.weyland.lab/a:git-1"] and out["images"] == {}


def test_a_report_without_trivys_schema_is_not_a_report(scan):
    assert scan._is_trivy_report(_report()) is True
    assert scan._is_trivy_report({"Results": []}) is False      # no SchemaVersion/ArtifactName: an error, not a scan
    assert scan._is_trivy_report(None) is False


def test_hand_built_images_referenced_by_manifests_are_scanned_too(scan, tmp_path):
    # weyland-agent, ray-head, mcp-server-datahub, weyland-jupyter are hand-tagged, so images.tsv never lists them; the
    # first version of this step scanned only images.tsv and so missed exactly the images most likely to drift.
    _tsv(tmp_path, [("weyland-tool-server", "services/weyland-tool-server", "k8s/weyland-tool-server.yaml")])
    _manifest(tmp_path, "k8s/weyland-tool-server.yaml", "image: registry.weyland.lab/weyland-tool-server:git-af3ae0c8\n")
    _manifest(tmp_path, "k8s/weyland-agent/deployment.yaml", "image: registry.weyland.lab/weyland-agent:v9   # note\n")
    _manifest(tmp_path, "k8s/ray/ray-head.yaml", "  image: registry.weyland.lab/ray-head:v8\n  other: registry.weyland.lab/ray-head:v8\n")
    _manifest(tmp_path, "k8s/jupyterhub/jupyterhub-values.yaml",
              "singleuser:\n  image:\n    # comment\n    name: registry.weyland.lab/weyland-jupyter\n    tag: v1\n")
    refs, missing = scan.deployed_images(str(tmp_path))
    assert refs == ["registry.weyland.lab/ray-head:v8", "registry.weyland.lab/weyland-agent:v9",
                    "registry.weyland.lab/weyland-jupyter:v1", "registry.weyland.lab/weyland-tool-server:git-af3ae0c8"]
    assert missing == []


def test_a_manifest_reference_without_a_tag_is_not_scanned_as_latest(scan, tmp_path):
    _tsv(tmp_path, [])
    _manifest(tmp_path, "k8s/x.yaml", "image: registry.weyland.lab/thing\n")
    refs, _ = scan.deployed_images(str(tmp_path))
    assert refs == []
