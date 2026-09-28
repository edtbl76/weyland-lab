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


def test_the_real_inventory_passes_repo_mode():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert pc.main(["--repo", "--file", os.path.join(root, "placement.yaml"),
                    "--model", os.path.join(root, "docs/architecture/weyland.likec4")]) == 0
