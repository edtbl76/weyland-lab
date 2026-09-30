"""Tests for placement_check.py — the B198 placement inventory guard (placement.yaml vs the model and the live estate).

What these pin down are the DECISIONS: which rows are malformed, which LikeC4 elements lack a row, which running
workloads have no row (and which rows name nothing running), and when the guard must refuse to answer (exit 2) rather
than report a clean estate it could not see. The Prometheus response shapes are copied from real queries against the
lab's Prometheus (2026-09-27): kube-state-metrics `kube_*_created`, `pve_guest_info`, node-exporter
`node_systemd_unit_state`.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import placement_check as pc

MODEL = '''
specification { element node }
model {
  edward = actor "Edward"
  rogueone = node "rogueone" "laptop" {
    ollama = component "Ollama" "LLM serving"
    ragEmbed = component "rag-embed" "embed service"
  }
  weyland = system "weyland" "lab" {
    mother = node "mother VM" "k3s" {
      ai = zone "AI" {
        toolServer = component "weyland-tool-server" "FastAPI"
      }
    }
    whisper = node "whisper CT" "STT"
  }
}
views { view index { include * } }
'''


def _doc(rows=None, os_units=None, hosts=None):
    return {
        "hosts": hosts or {
            "weyland": {"kind": "proxmox-host"},
            "mother": {"kind": "qemu-vm"},
            "whisper": {"kind": "lxc"},
            "rogueone": {"kind": "laptop", "node_exporter": "192.168.1.230:9100"},
        },
        "host_os_units": {"rogueone": os_units if os_units is not None else ["ssh.service"]},
        "workloads": rows if rows is not None else [
            {"id": "k8s:weyland/Deployment/tool-server", "host": "mother", "state": "stateless", "move": "movable",
             "strix": "any", "managed": "argo"},
            {"id": "k8s:weyland/StatefulSet/qdrant", "host": "mother", "state": "pvc:local-path",
             "move": "pinned: local-path PV on mother", "strix": "stays", "managed": "argo"},
            {"id": "systemd:rogueone/ollama.service", "host": "rogueone", "state": "none",
             "move": "hardware-bound: CUDA", "strix": "stays", "managed": "systemd", "likec4": "ollama"},
            {"id": "systemd:rogueone/rag-embed.service", "host": "rogueone", "state": "stateless", "move": "movable",
             "strix": "k3s-worker", "managed": "systemd", "likec4": "ragEmbed", "why": "always-on node"},
            {"id": "pve:qemu/101", "host": "weyland", "state": "none", "move": "pinned: k3s server", "strix": "stays",
             "managed": "pve", "likec4": "mother"},
            {"id": "pve:lxc/103", "host": "weyland", "state": "none", "move": "movable", "strix": "tbd",
             "managed": "pve", "likec4": "whisper", "why": "owner decision"},
        ],
    }


# --- schema -------------------------------------------------------------------------------------------------------

def test_a_well_formed_inventory_has_no_schema_findings():
    assert pc.validate_schema(_doc()) == []


@pytest.mark.parametrize("field,value,expect", [
    ("host", "atlantis", "unknown host 'atlantis'"),
    ("strix", "moon", "strix 'moon'"),
    ("move", "wherever", "move 'wherever'"),
    ("scope", "hobby", "scope 'hobby'"),
])
def test_an_invalid_field_is_named(field, value, expect):
    doc = _doc()
    doc["workloads"][0][field] = value
    findings = pc.validate_schema(doc)
    assert any(expect in f and "tool-server" in f for f in findings), findings


def test_a_duplicate_id_is_a_finding():
    doc = _doc()
    doc["workloads"].append(dict(doc["workloads"][0]))
    assert any("duplicate" in f and "tool-server" in f for f in pc.validate_schema(doc))


def test_an_unknown_id_prefix_is_a_finding():
    doc = _doc()
    doc["workloads"][0]["id"] = "vm:whatever"
    assert any("id prefix" in f for f in pc.validate_schema(doc))


def test_a_stateful_row_marked_movable_is_a_finding():
    # Every local-path PV is bound to one node: a pvc row that claims it can move is a lie the migration would find.
    doc = _doc()
    doc["workloads"][1]["move"] = "movable"
    doc["workloads"][1]["strix"] = "any"
    assert any("qdrant" in f and "pvc" in f for f in pc.validate_schema(doc))


@pytest.mark.parametrize("strix", ["k3s-worker", "inference-lxc", "tbd"])
def test_a_deliberate_placement_needs_a_why(strix):
    doc = _doc()
    doc["workloads"][0]["strix"] = strix
    assert any("why" in f and "tool-server" in f for f in pc.validate_schema(doc))


def test_pinned_needs_a_reason():
    doc = _doc()
    doc["workloads"][1]["move"] = "pinned:"
    assert any("reason" in f and "qdrant" in f for f in pc.validate_schema(doc))


# --- LikeC4 -------------------------------------------------------------------------------------------------------

def test_the_model_parser_sees_nodes_and_their_components_but_not_mothers():
    els = pc.likec4_placed_elements(MODEL)
    assert els == {"rogueone", "ollama", "ragEmbed", "mother", "whisper"}


def test_a_model_element_with_no_row_is_a_finding():
    doc = _doc()
    doc["workloads"] = [r for r in doc["workloads"] if r.get("likec4") != "ragEmbed"]
    findings = pc.check_model(doc, MODEL)
    assert any("ragEmbed" in f for f in findings), findings


def test_a_row_naming_an_element_that_is_not_in_the_model_is_a_finding():
    doc = _doc()
    doc["workloads"][2]["likec4"] = "ollamaa"
    assert any("ollamaa" in f for f in pc.check_model(doc, MODEL))


def test_the_node_itself_needs_no_row_when_it_is_a_host():
    # rogueone IS a host (hosts:), not a workload — the host entry places it.
    assert pc.check_model(_doc(), MODEL) == []


def test_an_empty_model_refuses():
    with pytest.raises(pc.CannotRead):
        pc.likec4_placed_elements("model { }")


# --- live ---------------------------------------------------------------------------------------------------------

K8S = {"k8s:weyland/Deployment/tool-server", "k8s:weyland/StatefulSet/qdrant"}
UNITS = {"rogueone": {"ollama.service", "rag-embed.service", "ssh.service"}}
PVE = {"pve:qemu/101", "pve:lxc/103"}


def test_a_live_estate_matching_the_rows_is_clean():
    assert pc.check_live(_doc(), K8S, UNITS, PVE) == []


def test_a_running_k8s_workload_with_no_row_is_named_with_a_suggested_row():
    findings = pc.check_live(_doc(), K8S | {"k8s:data-mesh/Deployment/trino"}, UNITS, PVE)
    assert any("trino" in f and "no row" in f for f in findings), findings
    assert any('id: "k8s:data-mesh/Deployment/trino"' in f for f in findings)


def test_a_k8s_row_whose_workload_is_gone_is_named():
    findings = pc.check_live(_doc(), {"k8s:weyland/Deployment/tool-server"}, UNITS, PVE)
    assert any("qdrant" in f and "not running" in f for f in findings)


def test_an_active_host_unit_with_no_row_and_not_an_os_unit_is_named():
    units = {"rogueone": UNITS["rogueone"] | {"mystery.service"}}
    findings = pc.check_live(_doc(), K8S, units, PVE)
    assert any("mystery.service" in f for f in findings)


def test_an_os_unit_is_not_drift():
    assert pc.check_live(_doc(os_units=["ssh.service"]), K8S, UNITS, PVE) == []


def test_a_systemd_row_whose_unit_is_not_active_is_named_unless_on_demand():
    units = {"rogueone": {"ollama.service", "ssh.service"}}
    findings = pc.check_live(_doc(), K8S, units, PVE)
    assert any("rag-embed.service" in f and "not running" in f for f in findings)
    doc = _doc()
    doc["workloads"][3]["on_demand"] = True
    assert pc.check_live(doc, K8S, units, PVE) == []


def test_a_proxmox_guest_with_no_row_is_named():
    findings = pc.check_live(_doc(), K8S, UNITS, PVE | {"pve:lxc/104"})
    assert any("lxc/104" in f for f in findings)


def test_user_systemd_rows_are_declared_only():
    # node-exporter's systemd collector sees system units only; a user unit (restic-backup, ai-session-producer)
    # can be declared but not live-checked — it must never read as "not running".
    doc = _doc()
    doc["workloads"].append({"id": "user-systemd:rogueone/restic-backup.timer", "host": "rogueone", "state": "none",
                             "move": "pinned: backs up rogueone's own home", "strix": "stays", "managed": "systemd"})
    assert pc.validate_schema(doc) == []
    assert pc.check_live(doc, K8S, UNITS, PVE) == []


def test_tool_rows_are_declared_only():
    doc = _doc()
    doc["workloads"].append({"id": "tool:rogueone/editors", "host": "rogueone", "state": "none",
                             "move": "pinned: the workstation", "strix": "stays", "managed": "desktop"})
    assert pc.check_live(doc, K8S, UNITS, PVE) == []


# --- reading Prometheus -------------------------------------------------------------------------------------------

def _vec(*metrics):
    return {"status": "success", "data": {"resultType": "vector",
                                          "result": [{"metric": m, "value": [1790564337.7, "1"]} for m in metrics]}}


def test_k8s_objects_come_from_the_four_kube_state_metrics_families():
    answers = {
        "kube_deployment_created": _vec({"namespace": "weyland", "deployment": "tool-server"}),
        "kube_statefulset_created": _vec({"namespace": "weyland", "statefulset": "qdrant"}),
        "kube_daemonset_created": _vec({"namespace": "monitoring", "daemonset": "node-exporter"}),
        "kube_cronjob_created": _vec({"namespace": "weyland", "cronjob": "pg-backup"}),
    }
    got = pc.k8s_objects(lambda q: answers[q])
    assert got == {"k8s:weyland/Deployment/tool-server", "k8s:weyland/StatefulSet/qdrant",
                   "k8s:monitoring/DaemonSet/node-exporter", "k8s:weyland/CronJob/pg-backup"}


def test_an_empty_kube_state_metrics_family_refuses():
    # 0 deployments is not a cluster with no deployments — it is kube-state-metrics not answering.
    with pytest.raises(pc.CannotRead):
        pc.k8s_objects(lambda q: _vec())


def test_active_units_keep_services_and_timers_only():
    ans = _vec({"name": "ollama.service", "state": "active", "instance": "192.168.1.230:9100"},
               {"name": "sshd.socket", "state": "active", "instance": "192.168.1.230:9100"},
               {"name": "backup.timer", "state": "active", "instance": "192.168.1.230:9100"})
    got = pc.active_units(lambda q: ans, _doc()["hosts"])
    assert got == {"rogueone": {"ollama.service", "backup.timer"}}


def test_a_watched_host_with_no_series_in_24h_refuses():
    # rogueone sleeps; the query looks back 24h. Nothing in 24h means we cannot see it — never "nothing running".
    with pytest.raises(pc.CannotRead, match="rogueone"):
        pc.active_units(lambda q: _vec(), _doc()["hosts"])


def test_the_unit_query_looks_back_24h():
    seen = []
    pc.active_units(lambda q: seen.append(q) or _vec({"name": "a.service", "state": "active",
                                                      "instance": "192.168.1.230:9100"}), _doc()["hosts"])
    assert "[24h]" in seen[0]


def test_a_unit_counts_as_running_only_if_active_most_of_the_day():
    # D-Bus-activated OS helpers (systemd-hostnamed, flatpak-system-helper) are active for seconds and then exit; any-
    # moment-in-24h made each one a nightly finding (2026-09-28). A workload is active across most samples; a helper
    # is not. Sleep does not count against a unit: a sleeping laptop produces no samples at all.
    seen = []
    pc.active_units(lambda q: seen.append(q) or _vec({"name": "a.service", "state": "active",
                                                      "instance": "192.168.1.230:9100"}), _doc()["hosts"])
    assert "> 0.5" in seen[0]
    # The denominator is the HOST's samples, not the unit's: an on-demand unit's series exists only while it is
    # loaded, so averaging over its own samples scored flatpak-system-helper 1.0 after a few minutes up (2026-09-28).
    assert "sum_over_time(node_systemd_unit_state" in seen[0]
    assert "count_over_time(node_systemd_system_running" in seen[0]


def test_pve_guests():
    ans = _vec({"id": "qemu/101", "name": "mother"}, {"id": "lxc/103", "name": "whisper"})
    assert pc.pve_guests(lambda q: ans) == {"pve:qemu/101", "pve:lxc/103"}


def test_a_prometheus_error_refuses():
    with pytest.raises(pc.CannotRead):
        pc.pve_guests(lambda q: {"status": "error", "error": "bad query"})


# --- migration plan -----------------------------------------------------------------------------------------------

def test_the_migration_table_lists_deliberate_moves_and_counts_the_rest():
    md = pc.migration_table(_doc())
    assert "rag-embed.service" in md and "always-on node" in md
    assert "lxc/103" in md and "owner decision" in md
    assert "tool-server" not in md.split("## Summary")[0]
    assert "any: 1" in md and "stays: 3" in md


# --- main / exit codes --------------------------------------------------------------------------------------------

def test_main_repo_mode_passes_on_a_clean_inventory(tmp_path, capsys):
    p = tmp_path / "placement.yaml"
    import yaml
    p.write_text(yaml.safe_dump(_doc()))
    m = tmp_path / "model.likec4"
    m.write_text(MODEL)
    assert pc.main(["--repo", "--file", str(p), "--model", str(m)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_repo_mode_is_1_on_drift(tmp_path, capsys):
    import yaml
    doc = _doc()
    doc["workloads"] = [r for r in doc["workloads"] if r.get("likec4") != "ragEmbed"]
    p = tmp_path / "placement.yaml"
    p.write_text(yaml.safe_dump(doc))
    m = tmp_path / "model.likec4"
    m.write_text(MODEL)
    assert pc.main(["--repo", "--file", str(p), "--model", str(m)]) == 1
    assert "ragEmbed" in capsys.readouterr().err


def test_main_is_2_when_the_inventory_is_unreadable(tmp_path, capsys):
    p = tmp_path / "placement.yaml"
    p.write_text("workloads: [unclosed")
    m = tmp_path / "model.likec4"
    m.write_text(MODEL)
    assert pc.main(["--repo", "--file", str(p), "--model", str(m)]) == 2


def test_main_is_2_when_the_inventory_has_no_rows(tmp_path):
    p = tmp_path / "placement.yaml"
    p.write_text("hosts: {}\nworkloads: []\n")
    m = tmp_path / "model.likec4"
    m.write_text(MODEL)
    assert pc.main(["--repo", "--file", str(p), "--model", str(m)]) == 2


def test_live_mode_without_a_prometheus_url_is_2(tmp_path, monkeypatch, capsys):
    # No baked-in URL (Sonar S5332, 2026-09-28): the CronJob passes --prometheus explicitly; a bare --live with neither the
    # flag nor PROMETHEUS_URL must refuse, never guess an endpoint.
    import yaml
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)
    p = tmp_path / "placement.yaml"
    p.write_text(yaml.safe_dump(_doc()))
    assert pc.main(["--live", "--file", str(p)]) == 2
    assert "PROMETHEUS_URL" in capsys.readouterr().err


def test_the_real_inventory_passes_repo_mode():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert pc.main(["--repo", "--file", os.path.join(root, "placement.yaml"),
                    "--model", os.path.join(root, "docs/architecture/weyland.likec4")]) == 0


# --- B180: host config + host files --------------------------------------------------------------------------------
# One inventory: host units (systemd:/user-systemd: rows) gain `source` (repo path) + `path` (installed path), and a
# `host_config` section holds host files that are not units (drop-ins, /etc configs, apparmor, installed scripts).

def _hc(**kw):
    e = {"id": "file:mother/etc/sysctl.d/99-weyland-buildkit.conf", "host": "mother",
         "path": "/etc/sysctl.d/99-weyland-buildkit.conf", "source": "nodes/mother/host/sysctl.d/99-weyland-buildkit.conf",
         "owner": "B57"}
    e.update(kw)
    return e


def test_a_well_formed_host_config_entry_passes(tmp_path):
    doc = _doc()
    doc["host_config"] = [_hc()]
    (tmp_path / "nodes/mother/host/sysctl.d").mkdir(parents=True)
    (tmp_path / "nodes/mother/host/sysctl.d/99-weyland-buildkit.conf").write_text("x=1\n")
    assert pc.check_sources(doc, str(tmp_path)) == []


@pytest.mark.parametrize("field,value,expect", [
    ("host", "atlantis", "unknown host"),
    ("path", "etc/relative.conf", "absolute"),
    ("source", None, "source"),
])
def test_a_malformed_host_config_entry_is_named(tmp_path, field, value, expect):
    doc = _doc()
    doc["host_config"] = [_hc(**{field: value})]
    assert any(expect in f for f in pc.validate_schema(doc)), pc.validate_schema(doc)


def test_a_source_that_does_not_exist_is_a_finding(tmp_path):
    doc = _doc()
    doc["host_config"] = [_hc(source="nodes/mother/host/gone.conf")]
    assert any("gone.conf" in f and "does not exist" in f for f in pc.check_sources(doc, str(tmp_path)))


def test_a_unit_row_source_is_checked_too(tmp_path):
    doc = _doc()
    doc["workloads"].append({"id": "systemd:mother/weyland-image-prune.timer", "host": "mother", "state": "none",
                             "move": "pinned: prunes mother's images", "strix": "stays", "managed": "systemd",
                             "source": "nodes/mother/host/systemd/weyland-image-prune.timer",
                             "path": "/etc/systemd/system/weyland-image-prune.timer"})
    assert any("weyland-image-prune.timer" in f for f in pc.check_sources(doc, str(tmp_path)))


def test_every_host_file_in_the_repo_must_be_referenced_once(tmp_path):
    for rel in ("nodes/mother/host/sysctl.d/99-weyland-buildkit.conf", "nodes/rogueone/systemd/orphan.timer"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x\n")
    doc = _doc()
    doc["host_config"] = [_hc()]
    findings = pc.check_repo_host_files(doc, str(tmp_path))
    assert any("orphan.timer" in f and "no inventory entry" in f for f in findings), findings
    assert not any("99-weyland-buildkit" in f for f in findings)


def test_a_host_file_referenced_twice_is_a_finding(tmp_path):
    rel = "nodes/mother/host/sysctl.d/99-weyland-buildkit.conf"
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text("x\n")
    doc = _doc()
    doc["host_config"] = [_hc(), _hc(id="file:mother/etc/other.conf", path="/etc/other.conf")]
    assert any("99-weyland-buildkit" in f and "2 inventory entries" in f
               for f in pc.check_repo_host_files(doc, str(tmp_path)))


# --- B180: installed content vs git --------------------------------------------------------------------------------

def test_effective_content_ignores_comments_and_blank_lines():
    a = "# header v1\n[Service]\n\nEnvironment=X=1\n"
    b = "# header v2 — reworded\n[Service]\nEnvironment=X=1\n\n"
    assert pc.effective(a) == pc.effective(b)
    assert pc.effective(a) != pc.effective("[Service]\nEnvironment=X=2\n")


def test_compare_installed_reports_missing_drift_and_comment_only():
    repo = {"a": "[S]\nX=1\n", "b": "[S]\nX=1\n", "c": "# old\n[S]\nX=1\n", "d": "[S]\nX=1\n"}
    host = {"a": "[S]\nX=1\n", "b": "[S]\nX=2\n", "c": "# new\n[S]\nX=1\n", "d": None}
    got = {k: pc.compare_installed(repo[k], host[k]) for k in repo}
    assert got == {"a": "same", "b": "DRIFT", "c": "comment-only", "d": "NOT INSTALLED"}


def test_every_hand_installed_unit_must_be_inventoried():
    doc = _doc()
    doc["workloads"].append({"id": "systemd:mother/weyland-image-prune.timer", "host": "mother", "state": "none",
                             "move": "pinned: x", "strix": "stays", "managed": "systemd"})
    installed = {"mother": {"weyland-image-prune.timer", "mystery.service"}}
    findings = pc.check_installed_units(doc, installed)
    assert any("mystery.service" in f and "not in the inventory" in f for f in findings)
    assert not any("weyland-image-prune" in f for f in findings)


# --- B180: the nightly host check (one SSH gather per host) --------------------------------------------------------
import base64


def _b64(t):
    return base64.b64encode(t.encode()).decode()


def test_parse_host_output_reads_files_units_failed_and_timers():
    out = "\n".join([
        f"F /etc/a.conf {_b64('[S]\nX=1\n')}",
        "F /etc/missing.conf -",
        "U weyland-image-prune.timer",
        "U weyland-image-prune.service",
        "X broken.service",
        "T weyland-image-prune.timer 1790000000",
        "T never.timer -",
    ])
    g = pc.parse_host_output(out)
    assert g["files"] == {"/etc/a.conf": "[S]\nX=1\n", "/etc/missing.conf": None}
    assert g["units"] == {"weyland-image-prune.timer", "weyland-image-prune.service"}
    assert g["failed"] == {"broken.service"}
    assert g["timers"] == {"weyland-image-prune.timer": 1790000000, "never.timer": None}


def test_parse_host_output_with_no_lines_refuses():
    with pytest.raises(pc.CannotRead):
        pc.parse_host_output("")


def _host_doc():
    doc = _doc()
    doc["hosts"]["mother"]["access"] = "ssh emangini@mother"
    doc["workloads"].append({"id": "systemd:mother/weyland-image-prune.timer", "host": "mother", "state": "none",
                             "move": "pinned: x", "strix": "stays", "managed": "systemd", "every": "7d",
                             "source": "t.timer", "path": "/etc/systemd/system/weyland-image-prune.timer"})
    doc["host_config"] = [{"id": "file:mother/etc/a.conf", "host": "mother", "path": "/etc/a.conf", "source": "a.conf"}]
    return doc


def _gathered(**kw):
    g = {"files": {"/etc/a.conf": "[S]\nX=1\n", "/etc/systemd/system/weyland-image-prune.timer": "[T]\nOnCalendar=x\n"},
         "units": {"weyland-image-prune.timer"}, "failed": set(), "timers": {"weyland-image-prune.timer": NOW - 3600}}
    g.update(kw)
    return {"mother": g}


NOW = 1790600000
REPO = {"a.conf": "[S]\nX=1\n", "t.timer": "[T]\nOnCalendar=x\n"}


def test_a_host_matching_the_inventory_is_clean():
    assert pc.check_hosts(_host_doc(), _gathered(), REPO.get, NOW) == []


def test_drift_and_not_installed_are_findings_comment_only_is_not():
    g = _gathered(files={"/etc/a.conf": "# reworded\n[S]\nX=1\n", "/etc/systemd/system/weyland-image-prune.timer": None})
    findings = pc.check_hosts(_host_doc(), g, REPO.get, NOW)
    assert any("weyland-image-prune.timer" in f and "NOT INSTALLED" in f for f in findings)
    assert not any("/etc/a.conf" in f for f in findings)          # comment-only: information, not drift
    g = _gathered(files={"/etc/a.conf": "[S]\nX=2\n", "/etc/systemd/system/weyland-image-prune.timer": "[T]\nOnCalendar=x\n"})
    assert any("/etc/a.conf" in f and "DRIFT" in f for f in pc.check_hosts(_host_doc(), g, REPO.get, NOW))


def test_a_failed_inventoried_unit_is_a_finding():
    g = _gathered(failed={"weyland-image-prune.timer"})
    assert any("weyland-image-prune.timer" in f and "failed" in f for f in pc.check_hosts(_host_doc(), g, REPO.get, NOW))


def test_a_timer_that_has_not_fired_within_twice_its_period_is_stale():
    g = _gathered(timers={"weyland-image-prune.timer": NOW - 15 * 86400})   # 15 days > 2 x 7d
    assert any("weyland-image-prune.timer" in f and "stale" in f for f in pc.check_hosts(_host_doc(), g, REPO.get, NOW))
    g = _gathered(timers={"weyland-image-prune.timer": None})
    assert any("never" in f for f in pc.check_hosts(_host_doc(), g, REPO.get, NOW))


def test_an_uninventoried_hand_installed_unit_is_a_finding():
    g = _gathered(units={"weyland-image-prune.timer", "mystery.service"})
    assert any("mystery.service" in f for f in pc.check_hosts(_host_doc(), g, REPO.get, NOW))


@pytest.mark.parametrize("every,seconds", [("4h", 14400), ("1d", 86400), ("7d", 604800)])
def test_every_parses(every, seconds):
    assert pc.every_seconds(every) == seconds


def test_the_host_script_asks_for_every_inventoried_path_and_timer():
    script = pc.host_script(["/etc/a.conf"], [("weyland-image-prune.timer", False)], user=False)
    assert "/etc/a.conf" in script and "weyland-image-prune.timer" in script and "--user" not in script
    assert "--user show" in pc.host_script([], [("restic-backup.timer", True)], user=True)


def test_a_system_timer_on_a_host_with_user_units_is_queried_without_user():
    # 2026-09-29: rogueone has both scopes; the system timer studio-masterdb-backup.timer was asked with --user,
    # came back empty and was reported "never triggered" although it fired that night.
    script = pc.host_script([], [("studio-masterdb-backup.timer", False), ("restic-backup.timer", True)], user=True)
    timer_lines = {ln.split("show")[0] + ln.split("--value ")[1].split(";")[0]
                   for ln in script.splitlines() if "LastTriggerUSec" in ln}
    assert timer_lines == {"v=$(systemctl studio-masterdb-backup.timer 2>/dev/null)",
                           "v=$(systemctl --user restic-backup.timer 2>/dev/null)"}


def test_gather_all_passes_each_timer_its_own_scope(monkeypatch):
    doc = {"hosts": {"rogueone": {"access": "local"}}, "workloads": [
        {"id": "systemd:rogueone/studio-masterdb-backup.timer", "host": "rogueone", "every": "1d"},
        {"id": "user-systemd:rogueone/restic-backup.timer", "host": "rogueone", "every": "1d"}]}
    seen = {}
    monkeypatch.setattr(pc, "host_script", lambda paths, timers, user: seen.setdefault("t", (timers, user)) and "")
    monkeypatch.setattr(pc, "_gather", lambda access, script: "U x.service")
    pc.gather_all(doc)
    assert seen["t"] == ([("studio-masterdb-backup.timer", False), ("restic-backup.timer", True)], True)
