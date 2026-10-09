"""Bifrost MCP watchdog (B203) — alert when an MCP client on the agent edge is not healthy.

WHY THIS EXISTS: Bifrost's `Linear` MCP client was disconnected before the B202 upgrade (2026-10-09) and nobody knew.
A client that drops keeps its tools advertised on `/mcp`, so the failure only shows when an agent calls a tool, and
Bifrost exports no client-state metric for Prometheus to alert on. The list API does report it: each client's `state`
(`healthy` on v2; v1 said `connected`) and, from v2.1, `last_failure` (stage, message, time).

WHAT IT DOES: reads every client from `GET /api/mcp/clients` (paged, with the setup token) and posts one
`BifrostMCPClientUnhealthy` alert per client whose state is not `healthy` to Alertmanager (→ Telegram). A client the
operator disabled (`config.disabled`) is deliberately off and is skipped. DRILL_CLIENT=<name> treats that one healthy
client as unhealthy, so a drill sends exactly one labelled alert.

EXIT CODES: 0 checked (alerts fired as needed) · 1 an alert could not be delivered (a watchdog that did not watch —
the failed Job pages through ScheduledJobFailed) · 2 could not read (no URL/token, the API locked or unreachable, an
empty or partial client list, a drill naming no client) — never a pass.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

SOURCE_LABEL = "bifrost-mcp-watchdog"
ALERTNAME = "BifrostMCPClientUnhealthy"
HEALTHY = "healthy"
PAGE = 25   # Bifrost's page size for this list (observed 2026-10-09)


class CannotRead(Exception):
    """The client list could not be read — exit 2, never a clean report."""


# --- verdicts ------------------------------------------------------------------------------------------------------

def _reason(client):
    reason = f"state {client.get('state') or '(none)'}"
    lf = client.get("last_failure") or {}
    if lf:
        detail = ", ".join(str(lf[k]) for k in ("stage", "message", "at", "time", "timestamp") if lf.get(k))
        reason += f" — last failure: {detail}"
    return reason


def verdicts(clients, drill=None):
    """[(client name, reason)] for every enabled client that is not healthy (or the one drill client)."""
    names = [(c.get("config") or {}).get("name") for c in clients]
    if drill and drill not in names:
        raise CannotRead(f"drill client {drill!r} is not one of the {len(names)} clients")
    out = []
    for c, name in zip(clients, names):
        if drill:
            if name == drill:
                out.append((name, f"DRILL — {name} is treated as unhealthy to test the alert path; nothing is wrong"))
            continue
        if (c.get("config") or {}).get("disabled"):
            continue
        if c.get("state") != HEALTHY:
            out.append((name, _reason(c)))
    return out


# --- Bifrost -------------------------------------------------------------------------------------------------------

def list_clients(get):
    got, offset, total = [], 0, None
    while total is None or offset < total:
        status, body = get("/api/mcp/clients", {"limit": PAGE, "offset": offset})
        if status != 200:
            raise CannotRead(f"GET /api/mcp/clients {status} (is BIFROST_SETUP_TOKEN set?)")
        rows = body.get("clients") or []
        total = body.get("total_count", len(rows))
        if not rows:
            break
        got += rows
        offset += len(rows)
    if not got:
        raise CannotRead("Bifrost returned no MCP clients — refusing to report a clean fleet")
    if len(got) < (total or 0):
        raise CannotRead(f"Bifrost said {total} clients but returned {len(got)} — refusing a partial check")
    return got


def _bifrost(url, token):
    def get(path, params):
        q = "&".join(f"{k}={v}" for k, v in params.items())
        req = urllib.request.Request(f"{url.rstrip('/')}{path}?{q}", headers={"X-Bifrost-Setup-Token": token})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 — URL comes from BIFROST_URL
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except (OSError, ValueError) as exc:
            raise CannotRead(f"Bifrost unreachable at {url}: {exc}") from exc
    return get


# --- alerts --------------------------------------------------------------------------------------------------------

def alert_payload(client, reason, drill=False):
    return [{"labels": {"alertname": ALERTNAME, "severity": "warning", "namespace": "weyland",
                        "mcp_client": client, "source": SOURCE_LABEL, "drill": "true" if drill else "false"},
             "annotations": {"summary": f"Bifrost MCP client '{client}': {reason}",
                             "description": f"{reason}. Its tools still show on /mcp but calls fail. Check the client in "
                                            "https://bifrost.weyland.lab (MCP catalog); OAuth clients need re-authorizing "
                                            "there; a recovered server needs `kubectl -n weyland rollout restart "
                                            "deploy/bifrost` (runbook: docs/runbooks/mcp-gateway.md § MCP watchdog)."}}]


def _post_alert(url, body):
    req = urllib.request.Request(f"{url.rstrip('/')}/api/v2/alerts", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30):  # nosec B310 — URL comes from ALERTMANAGER_URL
        pass


# --- main ----------------------------------------------------------------------------------------------------------

def _args(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--bifrost", default=os.environ.get("BIFROST_URL"))
    ap.add_argument("--token", default=os.environ.get("BIFROST_SETUP_TOKEN"))
    ap.add_argument("--alertmanager", default=os.environ.get("ALERTMANAGER_URL"))
    ap.add_argument("--drill", default=os.environ.get("DRILL_CLIENT"), help="treat this one client as unhealthy")
    return ap.parse_args(argv)


def main(argv=None):
    a = _args(argv)
    missing = [n for n, v in (("BIFROST_URL/--bifrost", a.bifrost), ("BIFROST_SETUP_TOKEN/--token", a.token),
                              ("ALERTMANAGER_URL/--alertmanager", a.alertmanager)) if not v]
    if missing:
        print(f"cannot check Bifrost MCP clients: missing {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        clients = list_clients(_bifrost(a.bifrost, a.token))
        found = verdicts(clients, a.drill)
    except CannotRead as exc:
        print(f"cannot check Bifrost MCP clients: {exc}", file=sys.stderr)
        return 2
    undelivered = 0
    for client, reason in found:
        print(f"ALERT {ALERTNAME} client={client!r} :: {reason}")
        try:
            _post_alert(a.alertmanager, alert_payload(client, reason, drill=bool(a.drill)))
        except OSError as exc:
            print(f"  !! Alertmanager POST failed: {exc}", file=sys.stderr)
            undelivered += 1
    print(f"checked {len(clients)} MCP client(s): {len(found)} alert(s) fired")
    return 1 if undelivered else 0


if __name__ == "__main__":
    sys.exit(main())
