#!/usr/bin/env python3
"""lan_nodeport_watch.py — is every LAN NodePort answering, from rogueone? (B219, 2026-10-17)

WHY THIS EXISTS: the lab reaches in-cluster services from rogueone by `-lan` NodePort only (AGENTS.md, B218), and
nothing watched them. A NodePort that stopped answering stayed silent until someone needed it — the MySQL one never
worked at all (its PERMISSIVE sidecar swallowed MySQL's server-first greeting) from the day it was created until this
watcher's first probe. The vantage point is the point: the rogueone-only ports (Trino, Valkey, OpenSearch, MLflow)
REFUSE every source but 192.168.1.230, so an in-cluster blackbox probe can never test them. Run every 15 min by the
user timer nodes/rogueone/systemd/lan-nodeport-watch.{service,timer}; the verdict goes to an Uptime-Kuma PUSH monitor
(KUMA_LAN_PUSH_URL in scripts/.env), a dead-man's switch, so a watcher that stops running alerts too.

WHAT IT CHECKS: the NodePort inventory comes from the LIVE cluster (`kubectl get svc -A`), so a NodePort added
without a probe is a finding (UNPROBED), never silently unwatched; a probe left for a NodePort that is gone is a
finding (STALE PROBE). Each port is probed at the protocol level, not TCP alone — an HTTP answer below 500, Redis
`+PONG`, the Postgres SSL-request byte, MySQL's v10 greeting — because a sidecar or a policy can accept the TCP
connection and still deliver nothing. A NodePort whose workload is parked on purpose (replicas 0, store-park.sh) is
listed, not paged.

EXIT: 0 every port answers · 1 a port is down, unprobed, or a probe is stale · 2 could not check (kubectl failed, no
NodePort found). Fail closed: an inventory that cannot be read is never "all up".

    usage: python3 scripts/lan_nodeport_watch.py [--no-push]
"""
import json
import os
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# The host every NodePort answers on: the node's InternalIP, read from the cluster (single node: mother), so no address
# is hardcoded here and the IPv4 source survives (rogueone's ipBlock pins are IPv4). LAN_NODEPORT_HOST overrides.
HOST_ENV = "LAN_NODEPORT_HOST"
HEALTH, HEALTHZ, ROOT = "/health", "/healthz", "/"

# One probe per NodePort, keyed "<namespace>/<service>:<nodePort>" — observed live 2026-10-17, not assumed.
PROBES = {
    "argocd/argocd-server-lan:30880": ("http", HEALTHZ),
    "data-mesh/cassandra-lan:30942": ("tcp", None),             # CQL is binary; parked most of the time
    "data-mesh/clickhouse-lan:30123": ("http", "/ping"),
    "data-mesh/cockroachdb-lan:30257": ("pg", None),
    "data-mesh/datahub-gms-lan:30818": ("http", HEALTH),
    "data-mesh/gizmosql:31337": ("tcp", None),                  # Arrow Flight SQL (gRPC)
    "data-mesh/lakefs-lan:30800": ("http", "/_health"),
    "data-mesh/mongodb-lan:30017": ("tcp", None),               # OP_MSG is binary; parked most of the time
    "data-mesh/musicbrainz-postgres-lan:30544": ("pg", None),
    "data-mesh/mysql-lan:30306": ("mysql", None),
    "data-mesh/timescaledb-lan:30543": ("pg", None),
    "data-mesh/trino-lan:30843": ("https", "/v1/info"),       # B233: TLS-only password door; /v1/info needs no login
    "data-mesh/valkey-lan:30379": ("redis", None),
    "minio/minio-s3-lan:30990": ("http", "/minio/health/live"),
    "monitoring/prometheus-lan:30909": ("http", "/-/healthy"),
    "opensearch/opensearch-lan:30920": ("http", "/_cluster/health"),
    "weyland/litellm:30400": ("http", "/health/liveliness"),
    "weyland/mlflow-lan:30500": ("http", HEALTH),
    "weyland/neo4j:30085": ("http", ROOT),
    "weyland/neo4j:30086": ("tcp", None),                       # Bolt
    "weyland/neodash:30088": ("http", ROOT),
    "weyland/qdrant:30083": ("http", HEALTHZ),
    "weyland/qdrant:30084": ("tcp", None),                      # gRPC
    "weyland/sonarqube-api-lan:30969": ("http", "/api/system/status"),
    "weyland/uptime-kuma-lan:30301": ("http", ROOT),
    "weyland/weaviate:30087": ("http", "/v1/.well-known/ready"),
    "weyland/weaviate:32418": ("tcp", None),                    # gRPC
    "weyland/weaviate:32477": ("http", "/metrics"),
    "weyland/weyland-apisix:30090": ("http", ROOT),              # 404 at / still proves the gateway answers
    "weyland/weyland-apisix:32224": ("http", "/apisix/prometheus/metrics"),
    "weyland/weyland-tool-server:30080": ("http", HEALTH),
    "woodpecker/woodpecker-grpc-lan:30900": ("tcp", None),
    "woodpecker/woodpecker-http-lan:30980": ("http", HEALTHZ),
}
KINDS = {"http", "https", "tcp", "pg", "redis", "mysql"}
# The lab mkcert CA an https probe verifies against (the cert names the node IP the watcher dials). B233.
CA_ENV, CA_DEFAULT = "LAN_NODEPORT_CA", os.path.expanduser("~/.local/share/mkcert/rootCA.pem")


class CannotRead(Exception):
    """The cluster inventory could not be read — the watcher cannot grade anything."""


def _connect(host, port, timeout):
    return socket.create_connection((host, port), timeout=timeout)


def _http(host, port, arg, timeout):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}{arg or ROOT}", timeout=timeout) as r:  # nosec B310 — LAN node IP
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    return (code < 500, f"HTTP {code}")


def _https(host, port, arg, timeout):
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=os.environ.get(CA_ENV, CA_DEFAULT))
    try:
        with urllib.request.urlopen(f"https://{host}:{port}{arg or ROOT}", timeout=timeout, context=ctx) as r:  # nosec B310 — LAN node IP
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except urllib.error.URLError as e:
        return (False, f"TLS/URL error: {e.reason}")
    return (code < 500, f"HTTPS {code}")


def _tcp(_s):
    return (True, "TCP open")


def _redis(s):
    s.sendall(b"PING\r\n")
    data = s.recv(16)
    return (data.startswith(b"+PONG"), f"replied {data[:16]!r}")


def _pg(s):
    s.sendall(b"\x00\x00\x00\x08\x04\xd2\x16\x2f")   # SSLRequest: a live Postgres answers 'S' or 'N'
    data = s.recv(1)
    return (data in (b"S", b"N"), f"SSL answer {data!r}")


def _mysql(s):
    try:
        data = s.recv(16)                            # server-first: the greeting arrives unprompted
    except socket.timeout:
        return (False, "no greeting (server-first protocol swallowed — a PERMISSIVE sidecar?)")
    ok = len(data) > 4 and data[4] == 0x0A
    return (ok, "greeting v10" if ok else f"no greeting, got {data[:8]!r}")


SOCKET_PROBES = {"tcp": _tcp, "redis": _redis, "pg": _pg, "mysql": _mysql}


def probe(host, port, kind, arg, timeout=5):
    """-> (ok, reason). Protocol-level: a connection that is accepted but answers nothing is DOWN."""
    try:
        if kind == "http":
            return _http(host, port, arg, timeout)
        if kind == "https":
            return _https(host, port, arg, timeout)
        fn = SOCKET_PROBES.get(kind)
        if fn is None:
            return (False, f"unknown probe kind {kind}")
        with _connect(host, port, timeout) as s:
            s.settimeout(timeout)
            return fn(s)
    except ConnectionRefusedError:
        return (False, "connection refused")
    except (socket.timeout, TimeoutError):
        return (False, "timed out")
    except OSError as e:
        return (False, f"{type(e).__name__}: {e}")


def _parked(svc, workloads):
    """A NodePort is parked when every workload its selector picks (same namespace) is at replicas 0."""
    sel = (svc.get("spec") or {}).get("selector") or {}
    if not sel:
        return False
    ns = svc["metadata"]["namespace"]
    picked = [w for w in workloads if w["metadata"]["namespace"] == ns
              and sel.items() <= (((w.get("spec") or {}).get("template") or {}).get("metadata") or {}).get("labels", {}).items()]
    return bool(picked) and all((w.get("spec") or {}).get("replicas", 1) == 0 for w in picked)


def nodeports(services):
    """-> {"<ns>/<svc>:<nodePort>": service} for every NodePort Service port."""
    ports = {}
    for s in services:
        if (s.get("spec") or {}).get("type") != "NodePort":
            continue
        key0 = f"{s['metadata']['namespace']}/{s['metadata']['name']}"
        for p in s["spec"].get("ports") or []:
            if p.get("nodePort"):
                ports[f"{key0}:{p['nodePort']}"] = s
    return ports


def evaluate(services, workloads, probes, probe_fn, host="127.0.0.1"):
    """-> (exit code, report lines). Pure decision logic; probe_fn(host, port, kind, arg) does the I/O."""
    ports = nodeports(services)
    if not ports:
        return 2, ["no NodePort found in the cluster inventory — refusing to report all up"]
    lines, rc, up, parked = [], 0, 0, 0
    for key in sorted(ports):
        if key not in probes:
            lines.append(f"UNPROBED {key} — add a probe to PROBES in scripts/lan_nodeport_watch.py"); rc = 1
            continue
        if _parked(ports[key], workloads):
            lines.append(f"parked  {key} (its workload is at replicas 0)"); parked += 1
            continue
        kind, arg = probes[key]
        ok, why = probe_fn(host, int(key.rsplit(":", 1)[1]), kind, arg)
        if ok:
            up += 1
        else:
            lines.append(f"DOWN    {key} [{kind}] — {why}"); rc = 1
    for key in sorted(set(probes) - set(ports)):
        lines.append(f"STALE PROBE {key} — no such NodePort in the cluster; remove it from PROBES"); rc = 1
    lines.append(f"lan-nodeport-watch: {up} up, {parked} parked, {len(ports)} NodePort(s) — exit {rc}")
    return rc, lines


def node_ip(nodes):
    """The first node's InternalIP — where every NodePort answers. Raises CannotRead when there is none."""
    for n in nodes:
        for a in (n.get("status") or {}).get("addresses") or []:
            if a.get("type") == "InternalIP":
                return a["address"]
    raise CannotRead("no node with an InternalIP in the cluster inventory")


def read_cluster():
    """-> (services, workloads, nodes) from the live cluster. Raises CannotRead — never an empty 'all clear'."""
    out = {}
    for what in ("svc", "deploy,sts", "nodes"):
        try:
            r = subprocess.run(["kubectl", "get", what, "-A", "-o", "json"], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise CannotRead(f"kubectl get {what}: {e}") from e
        if r.returncode != 0:
            raise CannotRead(f"kubectl get {what}: {r.stderr.strip()[:200]}")
        try:
            out[what] = json.loads(r.stdout)["items"]
        except (ValueError, KeyError) as e:
            raise CannotRead(f"kubectl get {what}: unreadable output ({e})") from e
    return out["svc"], out["deploy,sts"], out["nodes"]


def push(url, rc, summary):
    """Report the verdict to the Kuma push monitor. A missed heartbeat is itself the alarm, so a failed push only logs."""
    if not url:
        print("KUMA_LAN_PUSH_URL unset — verdict NOT reported to Kuma (runbook lan-access.md § Watch)", file=sys.stderr)
        return
    q = urllib.parse.urlencode({"status": "up" if rc == 0 else "down", "msg": summary[:250]})
    try:
        urllib.request.urlopen(f"{url}?{q}", timeout=15).read()  # nosec B310 — the operator's own Kuma push URL
    except OSError as e:   # URLError is an OSError
        print(f"could not reach Kuma ({e}) — the push monitor will alert on the missed heartbeat", file=sys.stderr)


ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", ".env")


def push_url(env_file=ENV_FILE):
    """KUMA_LAN_PUSH_URL from the environment, else that ONE key from scripts/.env — never the whole file."""
    if os.environ.get("KUMA_LAN_PUSH_URL") is not None:
        return os.environ["KUMA_LAN_PUSH_URL"]
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k.strip() == "KUMA_LAN_PUSH_URL":
                    return v.strip().strip("'\"")
    except OSError:
        pass
    return ""


def main(argv):
    try:
        services, workloads, nodes = read_cluster()
        host = os.environ.get(HOST_ENV) or node_ip(nodes)
        rc, lines = evaluate(services, workloads, PROBES, probe, host)
    except CannotRead as e:
        rc, lines = 2, [f"could not read the cluster inventory: {e}"]
    print("\n".join(lines))
    if "--no-push" not in argv:
        bad = [l for l in lines if not l.startswith(("parked", "lan-nodeport-watch:"))]
        push(push_url(), rc, "; ".join(bad) or lines[-1])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
