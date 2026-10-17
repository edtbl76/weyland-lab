"""Tests for lan_nodeport_watch.py — is every LAN NodePort answering, from rogueone (B219)?

What these pin down: the inventory comes from the LIVE cluster, so a NodePort nobody wrote a probe for is a finding,
never silently unwatched; a probe left behind for a NodePort that no longer exists is a finding too (the reverse
sweep); a store parked on purpose (its workload at replicas 0) is listed, not paged; an unreadable or empty inventory
is "could not check" (2), never "all up". The protocol probes are exercised against real sockets on localhost, because
the point of the watcher is the protocol — MySQL's server-first greeting is exactly what TCP-only checking missed.
"""
import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import lan_nodeport_watch as w


def svc(ns, name, ports, selector=None):
    return {"metadata": {"namespace": ns, "name": name}, "spec": {"type": "NodePort",
            "selector": selector if selector is not None else {"app": name},
            "ports": [{"port": p, "nodePort": n} for p, n in ports]}}


def workload(ns, name, replicas, labels=None, kind="Deployment"):
    return {"kind": kind, "metadata": {"namespace": ns, "name": name},
            "spec": {"replicas": replicas, "template": {"metadata": {"labels": labels or {"app": name}}}}}


PROBES = {"weyland/mlflow-lan:30500": ("http", "/health"), "data-mesh/mysql-lan:30306": ("mysql", None)}


def fake_probe(answers):
    def probe(host, port, kind, arg):
        return answers[port]
    return probe


# --- the decisions ---------------------------------------------------------------------------------------------------

def test_every_port_up_is_exit_0():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)])]
    rc, lines = w.evaluate(inv, [], PROBES, fake_probe({30500: (True, "HTTP 200"), 30306: (True, "greeting v10")}))
    assert rc == 0
    assert any("2 up" in l for l in lines)


def test_a_port_that_does_not_answer_is_exit_1_and_named():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)])]
    rc, lines = w.evaluate(inv, [], PROBES, fake_probe({30500: (True, "HTTP 200"), 30306: (False, "no greeting")}))
    assert rc == 1
    assert any("DOWN" in l and "mysql-lan:30306" in l and "no greeting" in l for l in lines)


def test_a_nodeport_with_no_probe_is_a_finding_never_silently_unwatched():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)]),
           svc("weyland", "brand-new-lan", [(8080, 31999)])]
    rc, lines = w.evaluate(inv, [], PROBES, fake_probe({30500: (True, "ok"), 30306: (True, "ok")}))
    assert rc == 1
    assert any("UNPROBED" in l and "brand-new-lan:31999" in l for l in lines)


def test_a_probe_for_a_nodeport_that_no_longer_exists_is_a_finding():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)])]
    rc, lines = w.evaluate(inv, [], PROBES, fake_probe({30500: (True, "ok")}))
    assert rc == 1
    assert any("STALE PROBE" in l and "mysql-lan:30306" in l for l in lines)


def test_a_parked_store_is_listed_not_paged():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)], {"app": "mysql"})]
    loads = [workload("data-mesh", "mysql", 0)]
    calls = []

    def probe(host, port, kind, arg):
        calls.append(port)
        return (True, "ok")
    rc, lines = w.evaluate(inv, loads, PROBES, probe)
    assert rc == 0
    assert 30306 not in calls
    assert any("parked" in l and "mysql-lan:30306" in l for l in lines)


def test_a_running_store_is_probed_even_if_another_namespace_has_a_parked_namesake():
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)], {"app": "mysql"})]
    loads = [workload("other-ns", "mysql", 0), workload("data-mesh", "mysql", 1)]
    rc, _ = w.evaluate(inv, loads, PROBES, fake_probe({30500: (True, "ok"), 30306: (False, "refused")}))
    assert rc == 1


def test_an_empty_inventory_is_could_not_check_not_all_up():
    rc, lines = w.evaluate([], [], PROBES, fake_probe({}))
    assert rc == 2
    assert any("no NodePort" in l for l in lines)


def test_an_unreadable_cluster_is_exit_2(monkeypatch):
    def boom(*a, **k):
        raise w.CannotRead("kubectl: connection refused")
    monkeypatch.setattr(w, "read_cluster", boom)
    monkeypatch.setenv("KUMA_LAN_PUSH_URL", "")
    assert w.main([]) == 2


def test_the_real_probe_table_covers_its_own_keys_with_known_kinds():
    for key, (kind, _arg) in w.PROBES.items():
        assert kind in w.KINDS, key
        ns_name, _, port = key.rpartition(":")
        assert "/" in ns_name and port.isdigit(), key


# --- the protocol probes, against real sockets ------------------------------------------------------------------------

def _server(handler):
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(1)

    def run():
        conn, _ = srv.accept()
        try:
            handler(conn)
        finally:
            conn.close(); srv.close()
    threading.Thread(target=run, daemon=True).start()
    return srv.getsockname()[1]


def test_mysql_probe_reads_the_server_first_greeting():
    port = _server(lambda c: c.sendall(b"\x4a\x00\x00\x00\x0a8.4.0\x00"))
    ok, why = w.probe("127.0.0.1", port, "mysql", None)
    assert ok, why


def test_mysql_probe_fails_when_the_server_stays_silent():
    port = _server(lambda c: c.recv(1))   # accepts, never greets — the sidecar-swallowed case
    ok, why = w.probe("127.0.0.1", port, "mysql", None, timeout=1)
    assert not ok and "greeting" in why


def test_redis_probe_wants_pong():
    port = _server(lambda c: (c.recv(64), c.sendall(b"+PONG\r\n")))
    assert w.probe("127.0.0.1", port, "redis", None)[0]


def test_pg_probe_accepts_the_ssl_answer_byte():
    port = _server(lambda c: (c.recv(8), c.sendall(b"N")))
    assert w.probe("127.0.0.1", port, "pg", None)[0]


def test_tcp_probe_reports_a_refused_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()   # nothing listens
    ok, why = w.probe("127.0.0.1", port, "tcp", None, timeout=1)
    assert not ok and "refused" in why.lower()


def _http(status):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status); self.end_headers()

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    return srv.server_address[1]


@pytest.mark.parametrize("status,up", [(200, True), (302, True), (404, True), (503, False)])
def test_http_probe_counts_any_answer_below_500_as_up(status, up):
    port = _http(status)
    ok, why = w.probe("127.0.0.1", port, "http", "/x")
    assert ok is up, why


def test_push_url_reads_only_its_own_key_from_the_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("KUMA_LAN_PUSH_URL", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER_SECRET=nope\nKUMA_LAN_PUSH_URL='https://kuma.example/api/push/abc'\nANOTHER=x\n")
    assert w.push_url(str(env)) == "https://kuma.example/api/push/abc"
    assert "OTHER_SECRET" not in os.environ


def test_push_url_missing_everywhere_is_empty_not_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("KUMA_LAN_PUSH_URL", raising=False)
    assert w.push_url(str(tmp_path / "absent.env")) == ""


def test_the_host_is_the_nodes_internal_ip_not_a_hardcoded_address():
    nodes = [{"status": {"addresses": [{"type": "Hostname", "address": "mother"},
                                        {"type": "InternalIP", "address": "10.9.8.7"}]}}]
    assert w.node_ip(nodes) == "10.9.8.7"


def test_no_internal_ip_is_could_not_read():
    with pytest.raises(w.CannotRead):
        w.node_ip([{"status": {"addresses": [{"type": "Hostname", "address": "mother"}]}}])


def test_probes_go_to_the_host_evaluate_was_given():
    seen = []

    def probe(host, port, kind, arg):
        seen.append(host)
        return (True, "ok")
    inv = [svc("weyland", "mlflow-lan", [(5000, 30500)]), svc("data-mesh", "mysql-lan", [(3306, 30306)])]
    w.evaluate(inv, [], PROBES, probe, "10.9.8.7")
    assert seen == ["10.9.8.7", "10.9.8.7"]
