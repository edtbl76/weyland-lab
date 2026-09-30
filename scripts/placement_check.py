"""Placement inventory guard (B198) — placement.yaml against the architecture model and the live estate.

WHY THIS EXISTS: before the Strix Halo box (B134) lands, every workload needs one answer — where it runs, what state it
holds, whether it can move, where it goes. Kubernetes placement was already guarded (applications.yaml ->
check-onboarding-completeness -> LikeC4), but host-native services were hand-listed and had drifted: a 2026-09-27 spot
check of rogueone found three STUD.io runners, mosquitto and dcgm-exporter running with no model entry, and nothing read
what rogueone ran at all. With one k8s node "which node does this need?" was never asked; with two it must be.

MODES
  --repo       (repo-guards, every push)  schema + enums, known hosts, every LikeC4 node / non-cluster component has a
               row, every row's likec4 exists, a pvc/host-path row is never movable.
  --live       (nightly CronJob)          k8s objects from kube-state-metrics, active systemd units per watched host
               from node-exporter (last 24h — a laptop sleeps), Proxmox guests from pve-exporter; each must match rows.
  --migration  print the Strix Halo migration table (markdown) for B134.

EXIT CODES (the coverage-guard contract): 0 clean · 1 drift, named · 2 a source could not be read — never a pass.
"""
import argparse
import base64
import glob
import json
import os
import re
import shlex
import subprocess  # nosec B404 — runs the fixed ssh/bash gather for the inventory's own hosts
import sys
import time
import urllib.parse
import urllib.request

import yaml

SYSTEMD = "systemd:"
USER_SYSTEMD = "user-systemd:"
ID_PREFIXES = ("k8s:", SYSTEMD, "pve:", "tool:", USER_SYSTEMD)
DECLARED_ONLY = ("tool:", USER_SYSTEMD)  # not visible to Prometheus: declared, never live-checked
STRIX = {"any", "k3s-worker", "inference-lxc", "stays", "every-node", "tbd"}
NEEDS_WHY = {"k3s-worker", "inference-lxc", "tbd"}
SCOPES = {"lab", "stud.io", "personal", "unused", "unknown"}
MOVE_FIXED = {"movable", "every-node"}
MOVE_REASONED = ("pinned:", "hardware-bound:")
KSM = {"Deployment": "deployment", "StatefulSet": "statefulset", "DaemonSet": "daemonset", "CronJob": "cronjob"}
# A unit is RUNNING when it was active in more than half of the HOST's samples over the last 24h. Not "active at any
# moment": D-Bus-activated OS helpers (systemd-hostnamed, flatpak-system-helper) run for minutes and exit, and any-moment
# made each a nightly finding (2026-09-28). The denominator is the host's own series (node_systemd_system_running), not
# the unit's — an on-demand unit's series exists only while it is loaded, so averaging over its own samples scored
# flatpak-system-helper 1.0. Measured on rogueone: real services and timers 1.0; those helpers 0.017 / 0.006. A
# sleeping laptop yields no samples for either side, so sleep does not count against a unit.
UNIT_QUERY = ('sum_over_time(node_systemd_unit_state{state="active",instance="%s"}[24h])'
              ' / on(instance) group_left count_over_time(node_systemd_system_running{instance="%s"}[24h]) > 0.5')
CLUSTER_NODE = "mother"
# B180 — repo files that are INSTALLED onto a host (units, drop-ins, /etc configs, apparmor, an installed script).
# Every file these match must be referenced by exactly one inventory `source`. Files run in place from the repo
# (the restic backup scripts, the GPU bench compose file, nodes/openclaw/bin, the vLLM helpers) are deliberately not
# matched: nothing installs them, so there is no host copy to drift.
HOST_FILE_GLOBS = (
    "nodes/*/host/**/*",
    "nodes/rogueone/systemd/*",
    "nodes/rogueone/apparmor/*",
    "nodes/weyland/whisper/*.service",
    "nodes/weyland/whisper/shim.py",
    "nodes/mother/lab/weyland-platform/services/*/*.service",
)
UNIT_PREFIXES = (SYSTEMD, USER_SYSTEMD)


class CannotRead(Exception):
    """A source could not be read — the guard must exit 2, never report a clean estate it did not see."""


# --- schema -------------------------------------------------------------------------------------------------------

def _row_findings(r, hosts):
    rid = r.get("id", "<no id>")
    out = []
    if not str(rid).startswith(ID_PREFIXES):
        out.append(f"{rid}: id prefix must be one of {', '.join(ID_PREFIXES)}")
    if r.get("host") not in hosts:
        out.append(f"{rid}: unknown host '{r.get('host')}'")
    strix, move, scope = r.get("strix"), str(r.get("move", "")), r.get("scope", "lab")
    if strix not in STRIX:
        out.append(f"{rid}: strix '{strix}' is not one of {sorted(STRIX)}")
    if strix in NEEDS_WHY and not r.get("why"):
        out.append(f"{rid}: strix '{strix}' is a decision and needs a `why`")
    if scope not in SCOPES:
        out.append(f"{rid}: scope '{scope}' is not one of {sorted(SCOPES)}")
    if scope == "unused" and not r.get("why"):
        out.append(f"{rid}: scope 'unused' needs a `why`")
    if move.startswith(MOVE_REASONED):
        if not move.split(":", 1)[1].strip():
            out.append(f"{rid}: move '{move}' needs a reason after the colon")
    elif move not in MOVE_FIXED:
        out.append(f"{rid}: move '{move}' is not movable / every-node / pinned: <reason> / hardware-bound: <reason>")
    state = str(r.get("state", ""))
    if state.startswith(("pvc", "host-path")) and move in MOVE_FIXED and rid.startswith("k8s:"):
        out.append(f"{rid}: state '{state}' is bound to one node, so it cannot be `{move}` (pvc/host-path is pinned)")
    return out


def validate_schema(doc):
    hosts = doc.get("hosts") or {}
    rows = doc.get("workloads") or []
    findings, seen = [], set()
    for r in rows:
        rid = r.get("id")
        if rid in seen:
            findings.append(f"{rid}: duplicate id")
        seen.add(rid)
        findings.extend(_row_findings(r, hosts))
    for host in (doc.get("host_os_units") or {}):
        if host not in hosts:
            findings.append(f"host_os_units: unknown host '{host}'")
    for e in doc.get("host_config") or []:
        eid = e.get("id")
        if eid in seen:
            findings.append(f"{eid}: duplicate id")
        seen.add(eid)
        findings.extend(_host_config_findings(e, hosts))
    return findings


def _host_config_findings(e, hosts):
    eid = e.get("id", "<no id>")
    out = []
    if not str(eid).startswith("file:"):
        out.append(f"{eid}: host_config id must start with file:")
    if e.get("host") not in hosts:
        out.append(f"{eid}: unknown host '{e.get('host')}'")
    if not str(e.get("path") or "").startswith("/"):
        out.append(f"{eid}: path '{e.get('path')}' must be absolute (where the file is installed)")
    if not e.get("source"):
        out.append(f"{eid}: host_config needs a `source` (its repo path)")
    return out


# --- B180: sources + repo host files -------------------------------------------------------------------------------

def _sourced(doc):
    """Every inventory entry that names a repo `source`: unit rows and host_config entries."""
    return [e for e in (doc.get("workloads") or []) + (doc.get("host_config") or []) if e.get("source")]


def check_sources(doc, root):
    return [f"{e['id']}: source '{e['source']}' does not exist in the repo"
            for e in _sourced(doc) if not os.path.isfile(os.path.join(root, e["source"]))]


def repo_host_files(root):
    found = set()
    for pattern in HOST_FILE_GLOBS:
        found |= {os.path.relpath(p, root) for p in glob.glob(os.path.join(root, pattern), recursive=True)
                  if os.path.isfile(p)}
    return found


def check_repo_host_files(doc, root):
    refs = {}
    for e in _sourced(doc):
        refs[e["source"]] = refs.get(e["source"], 0) + 1
    out = []
    for rel in sorted(repo_host_files(root)):
        n = refs.get(rel, 0)
        if n == 0:
            out.append(f"{rel}: installed-on-a-host file with no inventory entry (add a unit row or host_config entry)")
        elif n > 1:
            out.append(f"{rel}: referenced by {n} inventory entries (exactly one expected)")
    return out


# --- B180: installed content vs git --------------------------------------------------------------------------------

NOT_INSTALLED = "NOT INSTALLED"
DRIFT = "DRIFT"


def effective(text):
    """The lines that change behaviour: comment (#, ;) and blank lines removed, surrounding whitespace ignored."""
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(("#", ";"))]


def compare_installed(repo_text, host_text):
    if host_text is None:
        return NOT_INSTALLED
    if host_text == repo_text:
        return "same"
    return "comment-only" if effective(host_text) == effective(repo_text) else DRIFT


def check_installed_units(doc, installed):
    """installed: {host: {unit file names hand-installed on it}} → each must be an inventoried unit row or an
    allow-listed OS/installer unit (host_os_units)."""
    known = {r["id"] for r in doc.get("workloads") or [] if r["id"].startswith(UNIT_PREFIXES)}
    os_units = doc.get("host_os_units") or {}
    out = []
    for host, units in sorted(installed.items()):
        for u in sorted(units):
            if u in set(os_units.get(host, [])):
                continue
            if f"{SYSTEMD}{host}/{u}" not in known and f"{USER_SYSTEMD}{host}/{u}" not in known:
                out.append(f"{host}: unit {u} is installed on the host but not in the inventory")
    return out


# --- LikeC4 -------------------------------------------------------------------------------------------------------

_ELEMENT = re.compile(r'^\s*(\w+)\s*=\s*(\w+)\s+"')


def _model_block(text):
    m = re.search(r"^model\s*\{", text, re.MULTILINE)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def _is_placed(kind, stack):
    """A node is always placed; any other element is placed when its nearest enclosing node is not the k3s node."""
    if kind == "node":
        return True
    in_node = next((s for s in reversed(stack) if s[1] == "node"), None)
    return bool(in_node) and in_node[0] != CLUSTER_NODE


def _track_braces(code, stack):
    """Keep the element stack aligned on lines that open or close a block without declaring an element."""
    net = code.count("{") - code.count("}")
    for _ in range(-net):
        if stack:
            stack.pop()
    stack.extend([("", "")] * max(net, 0))


def likec4_placed_elements(text):
    """Every `node` element, plus every element nested inside a node other than the k3s node (whose components are k8s
    workloads, placed by the live k8s rows and by check-onboarding-completeness)."""
    stack, placed = [], set()
    for line in _model_block(text).splitlines():
        code = line.split("//", 1)[0]
        m = _ELEMENT.match(code)
        if not m:
            _track_braces(code, stack)
            continue
        eid, kind = m.group(1), m.group(2)
        if _is_placed(kind, stack):
            placed.add(eid)
        if code.count("{") > code.count("}"):
            stack.append((eid, kind))
    if not placed:
        raise CannotRead("no node elements parsed from the LikeC4 model")
    return placed


def check_model(doc, model_text):
    placed = likec4_placed_elements(model_text)
    hosts = set((doc.get("hosts") or {}).keys())
    named = {r.get("likec4") for r in doc.get("workloads") or [] if r.get("likec4")}
    out = [f"LikeC4 element '{e}' has no placement row (add a row with likec4: {e})"
           for e in sorted(placed - named - hosts)]
    all_ids = set(re.findall(r'^\s*(\w+)\s*=\s*\w+\s+"', _model_block(model_text), re.MULTILINE))
    out += [f"row likec4 '{e}' is not an element in the LikeC4 model" for e in sorted(named - all_ids)]
    return out



# --- B180: the nightly host check ---------------------------------------------------------------------------------
# One gather per host (local bash, or over SSH / `pct exec`): the installed copy of every inventoried file, the
# hand-installed unit files, the failed units, and each tracked timer's last trigger. Run by machine-inv-drift
# (rogueone, nightly), which already holds the fleet SSH keys and reports through Kuma → Telegram.

_UNIT_FIND = "-maxdepth 1 -type f \\( -name '*.service' -o -name '*.timer' \\) -printf 'U %f\\n'"


def host_script(paths, timers, user):
    """The bash gather for one host. `timers`: (name, is_user_unit) pairs — each timer is queried in its OWN scope, since
    one host can carry both (rogueone). `user`: also list ~/.config/systemd/user and its failed units."""
    lines = ["set -u"]
    for p in paths:
        q = shlex.quote(p)
        lines.append(f'if [ -r {q} ]; then printf "F %s %s\\n" {q} "$(base64 -w0 {q})"; else printf "F %s -\\n" {q}; fi')
    lines.append(f"find /etc/systemd/system {_UNIT_FIND}")
    if user:
        lines.append(f'[ -d "$HOME/.config/systemd/user" ] && find "$HOME/.config/systemd/user" {_UNIT_FIND}')
        lines.append("systemctl --user --failed --no-legend --plain | awk '{print \"X \"$1}'")
    lines.append("systemctl --failed --no-legend --plain | awk '{print \"X \"$1}'")
    for t, is_user in timers:
        q = shlex.quote(t)
        scope = "--user " if is_user else ""
        # `--timestamp=unix` is ignored by `show --value` on systemd 255 (it returns "Tue 2026-09-29 02:56:39 EDT",
        # observed 2026-09-29), so convert the human date on the host; empty or "n/a" = never triggered.
        lines.append(f'v=$(systemctl {scope}show -p LastTriggerUSec --value {q} 2>/dev/null); '
                     f'e=$([ -n "$v" ] && [ "$v" != n/a ] && date -d "$v" +%s 2>/dev/null); '
                     f'printf "T %s %s\\n" {q} "${{e:--}}"')
    return "\n".join(lines) + "\n"


def parse_host_output(text):
    g = {"files": {}, "units": set(), "failed": set(), "timers": {}}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise CannotRead("the host gather returned nothing")
    for ln in lines:
        kind, _, rest = ln.partition(" ")
        if kind == "F":
            path, _, data = rest.rpartition(" ")
            g["files"][path] = None if data == "-" else base64.b64decode(data).decode("utf-8", "replace")
        elif kind == "U":
            g["units"].add(rest.strip())
        elif kind == "X":
            g["failed"].add(rest.strip())
        elif kind == "T":
            name, _, val = rest.partition(" ")
            g["timers"][name] = int(val) if val.strip().isdigit() else None
    return g


def every_seconds(every):
    m = re.fullmatch(r"(\d+)([mhd])", str(every))
    if not m:
        raise CannotRead(f"cannot parse every '{every}' (use e.g. 4h, 1d, 7d)")
    return int(m.group(1)) * {"m": 60, "h": 3600, "d": 86400}[m.group(2)]


def _host_entries(doc, host):
    units = [r for r in doc.get("workloads") or [] if r.get("host") == host and r["id"].startswith(UNIT_PREFIXES)]
    files = [e for e in doc.get("host_config") or [] if e.get("host") == host]
    return units, files


def _file_findings(entries, g, repo_read):
    out = []
    for e in entries:
        path = e.get("path")
        if not path:
            continue
        installed = g["files"].get(path)
        if e.get("source"):
            status = compare_installed(repo_read(e["source"]), installed)
        elif installed is None:
            status = NOT_INSTALLED
        else:
            status = "same"
        if status == DRIFT:
            out.append(f"{e['id']}: {DRIFT} at {path} (repo: {e['source']})")
        elif status == NOT_INSTALLED:
            out.append(f"{e['id']}: {NOT_INSTALLED} at {path}")
    return out


def _unit_state_findings(units, g, now):
    out = []
    for r in units:
        name = r["id"].split("/", 1)[1]
        if name in g["failed"]:
            out.append(f"{r['id']}: unit is in the failed state")
        if r.get("every"):
            last = g["timers"].get(name)
            if last is None:
                out.append(f"{r['id']}: timer has never triggered")
            elif now - last > 2 * every_seconds(r["every"]):
                out.append(f"{r['id']}: timer stale — last fired {int((now - last) / 3600)}h ago, every {r['every']}")
    return out


def check_hosts(doc, gathered, repo_read, now):
    out = []
    for host, g in sorted(gathered.items()):
        units, files = _host_entries(doc, host)
        out += _file_findings(units + files, g, repo_read)
        out += _unit_state_findings(units, g, now)
        out += check_installed_units(doc, {host: g["units"]})
    return out


def _gather(access, script):
    """Run the gather on one host: `local`, `ssh <target>`, or `ssh <target> pct exec <ctid>`."""
    parts = access.split()
    if parts == ["local"]:
        cmd = ["bash", "-s"]
    elif parts[:1] == ["ssh"] and len(parts) == 2:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", parts[1], "bash -s"]
    elif parts[:1] == ["ssh"] and parts[2:4] == ["pct", "exec"] and len(parts) == 5:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", parts[1], f"pct exec {parts[4]} -- bash -s"]
    else:
        raise CannotRead(f"unknown access '{access}'")
    res = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=120)  # nosec B603 — fixed argv
    if res.returncode != 0 and not res.stdout.strip():
        raise CannotRead(f"{access}: gather failed ({res.stderr.strip()[:200]})")
    return res.stdout


def gather_all(doc):
    gathered = {}
    for host, h in sorted((doc.get("hosts") or {}).items()):
        access = (h or {}).get("access")
        if not access:
            continue
        units, files = _host_entries(doc, host)
        paths = [e["path"] for e in units + files if e.get("path")]
        timers = [(r["id"].split("/", 1)[1], r["id"].startswith(USER_SYSTEMD)) for r in units if r.get("every")]
        user = any(r["id"].startswith(USER_SYSTEMD) for r in units)
        try:
            gathered[host] = parse_host_output(_gather(access, host_script(paths, timers, user)))
        except (CannotRead, OSError, subprocess.TimeoutExpired) as exc:
            raise CannotRead(f"{host}: {exc}") from exc
    return gathered

# --- live ---------------------------------------------------------------------------------------------------------

def _result(resp):
    if not isinstance(resp, dict) or resp.get("status") != "success":
        raise CannotRead(f"Prometheus error: {resp.get('error') if isinstance(resp, dict) else resp}")
    return resp["data"]["result"]


def k8s_objects(query):
    out = set()
    for kind, label in KSM.items():
        res = _result(query(f"kube_{label}_created"))
        if not res:
            raise CannotRead(f"kube_{label}_created returned nothing — kube-state-metrics is not answering")
        out |= {f"k8s:{m['metric']['namespace']}/{kind}/{m['metric'][label]}" for m in res}
    return out


def active_units(query, hosts):
    out = {}
    for host, h in hosts.items():
        inst = (h or {}).get("node_exporter")
        if not inst:
            continue
        res = _result(query(UNIT_QUERY % (inst, inst)))
        if not res:
            raise CannotRead(f"{host}: no systemd series from {inst} in the last 24h (asleep or exporter down)")
        out[host] = {m["metric"]["name"] for m in res if m["metric"]["name"].endswith((".service", ".timer"))}
    return out


def pve_guests(query):
    res = _result(query("pve_guest_info"))
    if not res:
        raise CannotRead("pve_guest_info returned nothing — pve-exporter is not answering")
    return {f"pve:{m['metric']['id']}" for m in res}


def suggest_row(rid, host="mother"):
    return (f'  - {{id: "{rid}", host: "{host}", state: "stateless", move: "movable", strix: "any", '
            f'managed: "argo"}}   # check state/move before committing')


def _running_set(rid, k8s, units, pve):
    if rid.startswith("k8s:"):
        return k8s
    if rid.startswith("pve:"):
        return pve
    host = rid[len(SYSTEMD):].split("/", 1)[0]
    return {f"{SYSTEMD}{host}/{u}" for u in units.get(host, set())} if host in units else None


def check_live(doc, k8s, units, pve):
    rows = doc.get("workloads") or []
    ids = {r["id"] for r in rows}
    os_units = doc.get("host_os_units") or {}
    running = set(k8s) | set(pve)
    for host, us in units.items():
        running |= {f"{SYSTEMD}{host}/{u}" for u in us if u not in set(os_units.get(host, []))}
    out = []
    for rid in sorted(running - ids):
        host = rid[len(SYSTEMD):].split("/", 1)[0] if rid.startswith(SYSTEMD) else "mother"
        out.append(f"{rid}: running with no row — add:\n{suggest_row(rid, host)}")
    for r in rows:
        rid = r["id"]
        if rid.startswith(DECLARED_ONLY) or r.get("on_demand"):
            continue
        live = _running_set(rid, k8s, units, pve)
        if live is not None and rid not in live:
            out.append(f"{rid}: row names something that is not running (remove the row, or mark on_demand: true)")
    return out


# --- migration ----------------------------------------------------------------------------------------------------

def migration_table(doc):
    rows = doc.get("workloads") or []
    moves = [r for r in rows if r.get("strix") in NEEDS_WHY]
    lines = ["| Workload | Now on | State | Target | Why |", "|---|---|---|---|---|"]
    lines += [f"| `{r['id']}` | {r['host']} | {r.get('state', '')} | {r['strix']} | {r.get('why', '')} |"
              for r in sorted(moves, key=lambda r: (r["strix"], r["id"]))]
    counts = {}
    for r in rows:
        counts[r.get("strix")] = counts.get(r.get("strix"), 0) + 1
    summary = ", ".join(f"{k}: {counts[k]}" for k in sorted(counts))
    return "\n".join(lines) + f"\n\n## Summary\n\n{len(rows)} rows — {summary}\n"


# --- main ---------------------------------------------------------------------------------------------------------

def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise CannotRead(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict) or not doc.get("workloads"):
        raise CannotRead(f"{path} has no workloads — refusing to report OK")
    return doc


def _prom(url):
    def query(q):
        full = f"{url.rstrip('/')}/api/v1/query?" + urllib.parse.urlencode({"query": q})
        try:
            with urllib.request.urlopen(full, timeout=30) as resp:  # nosec B310 — URL comes from --prometheus / PROMETHEUS_URL
                return json.load(resp)
        except (OSError, ValueError) as exc:
            raise CannotRead(f"Prometheus unreachable at {url}: {exc}") from exc
    return query


def _run(args):
    doc = _load(args.file)
    if args.migration:
        print(migration_table(doc))
        return []
    findings = validate_schema(doc)
    if args.hosts:
        root = os.path.dirname(os.path.abspath(args.file))
        return findings + check_hosts(doc, gather_all(doc), lambda src: _read_repo(root, src), time.time())
    if args.live:
        if not args.prometheus:
            raise CannotRead("--live needs --prometheus <url> or PROMETHEUS_URL (the placement-coverage CronJob passes it)")
        q = _prom(args.prometheus)
        findings += check_live(doc, k8s_objects(q), active_units(q, doc.get("hosts") or {}), pve_guests(q))
    else:
        with open(args.model, encoding="utf-8") as f:
            findings += check_model(doc, f.read())
        root = os.path.dirname(os.path.abspath(args.file))   # sources are repo paths, relative to placement.yaml
        findings += check_sources(doc, root) + check_repo_host_files(doc, root)
    return findings


def _read_repo(root, src):
    path = os.path.join(root, src)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--repo", action="store_true", help="schema + LikeC4 checks (default)")
    mode.add_argument("--live", action="store_true", help="reconcile against Prometheus")
    mode.add_argument("--migration", action="store_true", help="print the Strix Halo migration table")
    mode.add_argument("--hosts", action="store_true",
                      help="B180: gather each host over its `access` and compare installed units/files with git")
    ap.add_argument("--file", default=os.path.join(root, "placement.yaml"))
    ap.add_argument("--model", default=os.path.join(root, "docs/architecture/weyland.likec4"))
    # No baked-in URL: the CronJob passes --prometheus explicitly, and a guessed endpoint is not a reading (S5332).
    ap.add_argument("--prometheus", default=os.environ.get("PROMETHEUS_URL"))
    args = ap.parse_args(argv)
    try:
        findings = _run(args)
    except (CannotRead, OSError) as exc:
        print(f"❌ cannot check placement: {exc}", file=sys.stderr)
        return 2
    if args.migration:
        return 0
    for f in findings:
        print(f"  ❌ {f}", file=sys.stderr)
    if findings:
        print(f"❌ placement drift: {len(findings)} finding(s). Fix placement.yaml (or the model).", file=sys.stderr)
        return 1
    mode_name = "repo"
    if args.live:
        mode_name = "live"
    elif args.hosts:
        mode_name = "hosts"
    print(f"OK — placement.yaml: {len(_load(args.file)['workloads'])} rows, {mode_name} check clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
