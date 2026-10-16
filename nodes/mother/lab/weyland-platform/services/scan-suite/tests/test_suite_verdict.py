"""The suite's exit verdict (2026-10-16): a crashed tool or an unscanned image fails the run, after everything ran.

Why: every tool runs best-effort and the suite always exited 0. A crashed tool posts nothing, and an image trivy could
not scan was simply left out of the `trivy-images` counts, so Port's Code Health numbers dropped and nothing said so —
absence read as a lower count. Now the suite still runs every tool and posts every result, then exits 3 (a SCAN
DEFECT, distinct from 1) naming what is missing. The CronJob's podFailurePolicy fails the Job on 3 without a retry
(rerunning a 55-minute scan would not fix a crash), and KubeJobFailed carries it to Telegram.
"""


def test_a_clean_run_is_exit_0(scan, monkeypatch):
    monkeypatch.setattr(scan, "CRASHED", [])
    monkeypatch.setattr(scan, "IMAGES_BROKEN", [])
    code, reasons = scan.suite_verdict()
    assert code == 0 and reasons == []


def test_a_crashed_tool_is_exit_3_naming_it(scan, monkeypatch):
    monkeypatch.setattr(scan, "CRASHED", ["semgrep"])
    monkeypatch.setattr(scan, "IMAGES_BROKEN", [])
    code, reasons = scan.suite_verdict()
    assert code == 3
    assert any("semgrep" in r for r in reasons)


def test_an_unscanned_image_is_exit_3_naming_it(scan, monkeypatch):
    monkeypatch.setattr(scan, "CRASHED", [])
    monkeypatch.setattr(scan, "IMAGES_BROKEN", ["registry.weyland.lab/a:git-1"])
    code, reasons = scan.suite_verdict()
    assert code == 3
    assert any("registry.weyland.lab/a:git-1" in r for r in reasons)


def test_trivy_images_records_broken_images_for_the_verdict(scan, tmp_path, monkeypatch, captured_posts):
    p = tmp_path / "scripts" / "ci"
    p.mkdir(parents=True)
    (p / "images.tsv").write_text("a\tservices/a\tk8s/a.yaml\n")
    m = tmp_path / "nodes/mother/lab/weyland-platform/k8s"
    m.mkdir(parents=True)
    (m / "a.yaml").write_text("image: registry.weyland.lab/a:git-1\n")
    monkeypatch.setattr(scan, "SRC", str(tmp_path))
    monkeypatch.setattr(scan, "OUT", str(tmp_path))
    monkeypatch.setattr(scan, "IMAGES_BROKEN", [])
    monkeypatch.setattr(scan, "_trivy_image", lambda ref: None)
    scan.trivy_images()
    assert scan.IMAGES_BROKEN == ["registry.weyland.lab/a:git-1"]


def test_run_tools_records_a_crash_and_keeps_going(scan, monkeypatch):
    monkeypatch.setattr(scan, "CRASHED", [])
    ran = []

    def boom():
        raise RuntimeError("no binary")

    def fine():
        ran.append("fine")

    scan.run_tools([boom, fine])
    assert scan.CRASHED == ["boom"] and ran == ["fine"]
