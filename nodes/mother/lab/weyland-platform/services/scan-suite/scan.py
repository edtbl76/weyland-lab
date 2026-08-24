#!/usr/bin/env python3
"""B69 Wave 4 — code-scan suite orchestrator.

Runs each free scanner over the cloned repo at /src, POSTs per-tool severity counts to the Port `code-quality`
webhook (env PORT_INGEST_URL — same payload as the existing semgrep/trivy Jobs), and writes each tool's raw JSON
to /out (an emptyDir). Port holds the durable per-tool trend; the finding detail lives in this pod's logs (+ the
/out JSON while the pod exists). Every tool runs BEST-EFFORT: one failing or finding nothing never aborts the
rest. SonarQube is NOT here — it needs the server + a Java build (own CronJob).

The tool roster is declared in the repo-root `quality-tools.yaml` (SOURCE OF TRUTH; `scripts/check-quality-tools.sh`
guards scan.py + the docs against it). weyland houses the build suite going forward, so the suite is MULTI-LANGUAGE
— Python + Go + shell + docker + IaC + live HTTP-headers; a tool no-ops cleanly on a repo lacking its language (0 Go
here → the Go tools post 0, correct for a multi-repo suite).
"""
import json, os, subprocess, datetime, urllib.request, glob

SRC = os.environ.get("SCAN_SRC", "/src")
OUT = os.environ.get("SCAN_OUT", "/out")
TARGET = "weyland-lab"
PORT_URL = os.environ.get("PORT_INGEST_URL")
os.makedirs(OUT, exist_ok=True)


def sh(cmd, outfile=None):
    """Run a command best-effort; optionally redirect stdout to a file. Never raises."""
    print(f"\n$ {' '.join(cmd)}", flush=True)
    try:
        if outfile:
            with open(outfile, "w") as f:
                subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, timeout=1800, check=False)
        else:
            subprocess.run(cmd, timeout=1800, check=False)
    except Exception as e:
        print(f"  ! {e}", flush=True)


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"  ! parse {path}: {e}", flush=True)
        return None


# Every post() result lands here so archive() can render the HTML summary without re-parsing /out. Order is run
# order, which is also the order the operator watched them scroll past.
RESULTS = []


def z():
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


def post(tool, c):
    total = sum(c.values())
    payload = {"tool": tool, "target": TARGET, "critical": c["critical"], "high": c["high"],
               "medium": c["medium"], "low": c["low"], "total": total,
               "scannedAt": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"  = {tool}: {c['critical']}C / {c['high']}H / {c['medium']}M / {c['low']}L (total {total})", flush=True)
    RESULTS.append({"tool": tool, "critical": c["critical"], "high": c["high"],
                    "medium": c["medium"], "low": c["low"], "total": total})
    if not PORT_URL:
        print("  (PORT_INGEST_URL unset — skipping POST)", flush=True)
        return
    try:
        req = urllib.request.Request(PORT_URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        print("  POST", urllib.request.urlopen(req, timeout=30).status, flush=True)
    except Exception as e:
        print(f"  ! POST {tool}: {e}", flush=True)


def post_hotspot(payload):
    """B90: POST one code-maat hotspot to the same ingest URL. kind:"hotspot" routes it to the code_hotspot
    blueprint mapping; silent per-item (top-N loop) so it doesn't drown the log."""
    if not PORT_URL:
        return
    try:
        req = urllib.request.Request(PORT_URL, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"  ! POST hotspot {payload.get('file')}: {e}", flush=True)


# ---- per-tool runners: run + parse -> {critical,high,medium,low} -> post ----


def secret_files():
    """B69/B97 — closes the gap that let the n8n encryption key sit committed for 5 weeks.

    gitleaks `dir` HONORS .gitignore, so a file that is BOTH tracked in git AND matched by a .gitignore rule is
    invisible to it — which is exactly the most dangerous case: someone .gitignore'd a secret that was ALREADY
    committed, believing that hid it (the n8n key's own .gitignore comment literally admits this). The file stays
    in the repo, fully readable, but every content scanner skips it.

    This finds that intersection DIRECTLY, no entropy heuristics (which would flood on the accepted shared dev
    password + sealed-secret ciphertext): every git-tracked file that the .gitignore rules also match. The magic
    is `check-ignore --no-index` — WITHOUT it, git reports a tracked file as "not ignored" (tracking wins); WITH
    it, it evaluates the raw gitignore rules, revealing the tracked-but-rule-matched files. Near-zero false
    positives: a tracked+ignored file is almost always a secret hidden after the fact. Marked CRITICAL because,
    unlike the noisier scanners, this check is precise — a hit here is real and must not get lost in triage.
    """
    c = z()
    try:
        tracked = subprocess.run(["git", "-C", SRC, "ls-files"], capture_output=True, text=True,
                                 timeout=120, check=False).stdout.splitlines()
        if not tracked:
            print("  ! secret-files: no tracked files (is /src a git repo?)", flush=True)
            post("secret-files", c)
            return
        r = subprocess.run(["git", "-C", SRC, "check-ignore", "--no-index", "--stdin"],
                           input="\n".join(tracked), capture_output=True, text=True, timeout=120, check=False)
        flagged = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        for f in flagged:
            print(f"  !! TRACKED AND GITIGNORED (committed secret hidden after the fact?): {f}", flush=True)
        c["critical"] = len(flagged)
    except Exception as e:
        print(f"  ! secret-files: {e}", flush=True)
    post("secret-files", c)

def gitleaks():
    sh(["gitleaks", "dir", SRC, "-f", "json", "-r", f"{OUT}/gitleaks.json", "--exit-code", "0"])
    d = load(f"{OUT}/gitleaks.json") or []
    c = z(); c["critical"] = len(d)  # any committed secret = critical
    post("gitleaks", c)


def checkov():
    sh(["checkov", "-d", SRC, "-o", "json", "--compact", "--soft-fail",
        "--skip-path", "openclaw", "--skip-path", "site-techdocs"], outfile=f"{OUT}/checkov.json")
    d = load(f"{OUT}/checkov.json")
    frames = d if isinstance(d, list) else ([d] if d else [])
    m = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    c = z()
    for fr in frames:
        for chk in ((fr.get("results") or {}).get("failed_checks") or []):
            c[m.get((chk.get("severity") or "").upper(), "medium")] += 1  # OSS often lacks severity -> medium
    post("checkov", c)


def kubescape():
    sh(["kubescape", "scan", SRC, "--format", "json", "--output", f"{OUT}/kubescape.json"])
    d = load(f"{OUT}/kubescape.json") or {}
    sd = d.get("summaryDetails") or {}
    c = z()

    # Read kubescape's OWN per-severity RESOURCE counts. Three numbers live in this file and they measure
    # different things — picking the wrong one produced a metric that tracked the scanner, not the cluster:
    #   controlsSeverityCounters  -> failed rule CLASSES        (7 -> 16 across one policy update)
    #   resourcesSeverityCounters -> failed RESOURCES by severity (115 -> 522 across the same update)  <- we use this
    #   ResourceCounters.failedResources -> DISTINCT failing resources (113 -> 119)  <- the stable one
    # We report resourcesSeverityCounters because it is actionable ("97 containers run as root" beats "1 control
    # failed") and it fills Port's C/H/M/L schema.
    #
    # KNOW THIS WHEN READING THE TREND: kubescape DOWNLOADS ITS POLICY SET AT SCAN TIME. When upstream grew the
    # set 52 -> 127 controls (2026-08-21) this number jumped 115 -> 522 with nothing in this repo changing. A
    # spike here is "kubescape shipped rules" until proven otherwise — cross-check `failedResources` (logged
    # below), which barely moves across policy updates and is the honest posture trend.
    #
    # History: the previous parser read `resourceCounters` (lowercase) but kubescape emits `ResourceCounters`.
    # Python dicts are case-sensitive, so the lookup silently returned {} and the code fell through to counting
    # one per failed CONTROL — accidentally reproducing controlsSeverityCounters while appearing to count
    # resources. A silent wrong-key lookup that still returns a plausible number is the worst kind.
    rs = sd.get("resourcesSeverityCounters") or {}
    for band in ("critical", "high", "medium", "low"):
        c[band] = rs.get(f"{band}Severity", 0) or 0

    rc = sd.get("ResourceCounters") or {}
    if rc:
        print(f"  ~ kubescape: {rc.get('failedResources', 0)} distinct failing resources of "
              f"{rc.get('failedResources', 0) + rc.get('passedResources', 0)} scanned "
              f"({len(sd.get('controls') or {})} controls in today's policy set)", flush=True)
    post("kubescape", c)


def hadolint():
    files = subprocess.run(["find", SRC, "-iname", "Dockerfile*", "-not", "-path", "*/openclaw/*"],
                           capture_output=True, text=True).stdout.split()
    findings = []
    for df in files:
        r = subprocess.run(["hadolint", "-f", "json", df], capture_output=True, text=True)
        try:
            findings += json.loads(r.stdout or "[]")
        except Exception:
            pass
    json.dump(findings, open(f"{OUT}/hadolint.json", "w"))
    m = {"error": "high", "warning": "medium", "info": "low", "style": "low"}
    c = z()
    for f in findings:
        c[m.get((f.get("level") or "").lower(), "low")] += 1
    post("hadolint", c)


def bandit():
    sh(["bandit", "-r", SRC, "-f", "json", "-o", f"{OUT}/bandit.json", "--exit-zero",
        "-x", "openclaw,site-techdocs,node_modules"])
    d = load(f"{OUT}/bandit.json") or {}
    m = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    c = z()
    for r in (d.get("results") or []):
        c[m.get((r.get("issue_severity") or "").upper(), "low")] += 1
    post("bandit", c)


def osv():
    # --config is REQUIRED, not optional. Without it osv-scanner v1.9.1 never applies
    # /src/osv-scanner.toml: it looks for a config beside each scanned lockfile, and the accepted
    # findings live in nested paths (services/weyland-dagster, k8s/flink/sql-runner) that have no
    # co-located config — and even the one that DOES have a co-located toml was not honoured under
    # `-r`. Found 2026-08-23 during the B135 DoD Pillar 7 run: every group in osv.json came back
    # `ignored: null`, i.e. the whole accept-list had never applied. sqlparse@0.5.5 (documented via
    # PackageOverrides) and lz4-java (a long, careful IgnoredVulns rationale) were both being
    # re-reported as live highs every week.
    #
    # This is the file's own failure mode turned on itself: a control that looks maintained —
    # the toml exists, is thorough, is under review — while covering nothing. Do not drop this flag.
    sh(["osv-scanner", "--format", "json", "--config", f"{SRC}/osv-scanner.toml", "-r", SRC],
       outfile=f"{OUT}/osv.json")
    d = load(f"{OUT}/osv.json") or {}
    c = z()
    for res in (d.get("results") or []):
        for pkg in (res.get("packages") or []):
            for v in (pkg.get("vulnerabilities") or []):
                sev = ""
                for s in (v.get("severity") or []):
                    sev = s.get("score", "") or sev
                # OSV severity is CVSS vector/score; bucket by leading CVSS number when present, else HIGH
                band = "high"
                try:
                    num = float(str(sev).split(":")[0].split("/")[0])
                    band = "critical" if num >= 9 else "high" if num >= 7 else "medium" if num >= 4 else "low"
                except Exception:
                    pass
                c[band] += 1
    post("osv-scanner", c)


def shellcheck():
    files = subprocess.run(["find", SRC, "-name", "*.sh", "-not", "-path", "*/openclaw/*"],
                           capture_output=True, text=True).stdout.split()
    findings = []
    if files:
        r = subprocess.run(["shellcheck", "-f", "json"] + files, capture_output=True, text=True)
        try:
            findings = json.loads(r.stdout or "[]")
        except Exception:
            pass
    json.dump(findings, open(f"{OUT}/shellcheck.json", "w"))
    m = {"error": "high", "warning": "medium", "info": "low", "style": "low"}
    c = z()
    for f in findings:
        c[m.get((f.get("level") or "").lower(), "low")] += 1
    post("shellcheck", c)


def semgrep():
    # exclude sealed-secrets/: SealedSecret encryptedData is ENCRYPTED ciphertext (safe to commit by design), but
    # semgrep's generic-secret detector false-positives on the base64 blobs. gitleaks (smarter) doesn't. (B89)
    # --jobs/--max-memory are NOT tuning knobs here, they are the difference between finishing and being SIGKILLed.
    # semgrep defaults --jobs to the host CPU count; on mother (16 cores) that forked ~16 workers, each holding the
    # rule set + file ASTs, and blew the pod's memory cgroup mid-scan (exit 137, 2026-08-20). A cgroup memory limit
    # does not shrink os.cpu_count(), so semgrep cannot discover the bound on its own — it has to be told.
    # --max-memory is per-worker (MB): semgrep skips a file that would exceed it instead of dying, so the scan
    # degrades to "one file unscanned" rather than "no semgrep results at all", which suits a best-effort suite.
    sh(["semgrep", "scan", "--config", "auto", "--json", "--output", f"{OUT}/semgrep.json",
        "--jobs", "4", "--max-memory", "2000",
        "--exclude", "node_modules", "--exclude", "openclaw", "--exclude", "site-techdocs",
        "--exclude", "sealed-secrets", SRC])
    d = load(f"{OUT}/semgrep.json") or {}
    m = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}  # semgrep has no "critical"
    c = z()
    for f in (d.get("results") or []):
        k = m.get(((f.get("extra") or {}).get("severity") or "").upper())
        if k:
            c[k] += 1
    post("semgrep", c)


def trivy():
    ign = f"{SRC}/.trivyignore"
    cmd = ["trivy", "fs", "--offline-scan", "--scanners", "vuln,secret,misconfig",
           "--severity", "CRITICAL,HIGH,MEDIUM,LOW", "--no-progress", "--format", "json",
           "--output", f"{OUT}/trivy.json", "--skip-dirs", "**/node_modules,**/openclaw,site-techdocs"]
    if os.path.exists(ign):
        cmd += ["--ignorefile", ign]
    sh(cmd + [SRC])
    d = load(f"{OUT}/trivy.json") or {}
    m = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    c = z()
    for r in (d.get("Results") or []):
        for key in ("Vulnerabilities", "Misconfigurations", "Secrets"):
            for f in (r.get(key) or []):
                b = m.get((f.get("Severity") or "").upper())
                if b:
                    c[b] += 1
    post("trivy", c)


def codemaat():
    # Behavioral analysis (the free CodeScene equivalent) — NOT severity-based, so no Port POST. Emit the top
    # change-hotspots (files touched most = highest maintenance risk) to the log + save the CSV for review.
    log = f"{OUT}/maat.log"
    # safe.directory is now set once in __main__ before the runner loop (secret_files also needs it).
    # code-maat -c git2 requires the "--hash--date--author" log shape (NOT the legacy [%h] %aN %ad %s format).
    sh(["git", "-C", SRC, "log", "--all", "--numstat", "--date=short", "--no-renames", "--pretty=format:--%h--%ad--%aN"], outfile=log)
    sh(["java", "-jar", "/opt/code-maat.jar", "-l", log, "-c", "git2", "-a", "revisions"],
       outfile=f"{OUT}/maat-hotspots.csv")
    try:
        rows = open(f"{OUT}/maat-hotspots.csv").read().splitlines()
        print("\n  code-maat — top change-hotspots (entity,n-revs):", flush=True)
        for r in rows[1:16]:
            print(f"    {r}", flush=True)
        # B90: push the top-20 hotspots to Port (code_hotspot blueprint). rows are `entity,n-revs` (header at [0]).
        now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        posted = 0
        for r in rows[1:21]:
            fname, _, revs = r.rpartition(",")
            if fname and revs.strip().isdigit():
                post_hotspot({"kind": "hotspot", "file": fname, "revisions": int(revs),
                              "target": TARGET, "scannedAt": now})
                posted += 1
        print(f"  = code-maat: posted {posted} hotspots to Port", flush=True)
    except Exception as e:
        print(f"  ! code-maat: {e}", flush=True)


# ---- Python (added when weyland became the build-suite home; see repo-root quality-tools.yaml) ----


def ruff():
    # Python lint+format. ruff has no severity field — bucket by code family: S* (flake8-bandit security) high,
    # F*/E9* (real errors) medium, everything else (style) low.
    r = subprocess.run(["ruff", "check", SRC, "--output-format", "json", "--no-cache",
                        "--exclude", "openclaw,site-techdocs,node_modules"],
                       capture_output=True, text=True, timeout=1800, check=False)
    open(f"{OUT}/ruff.json", "w").write(r.stdout or "[]")
    c = z()
    try:
        for f in json.loads(r.stdout or "[]"):
            code = f.get("code") or ""
            c["high" if code.startswith("S") else "medium" if code.startswith(("F", "E9")) else "low"] += 1
    except Exception as e:
        print(f"  ! ruff: {e}", flush=True)
    post("ruff", c)


def pip_audit():
    # Python dependency CVEs (PyPI advisory DB) — a 2nd engine next to osv. pip-audit gives no severity → all high.
    reqs = subprocess.run(["find", SRC, "-name", "requirements*.txt",
                           "-not", "-path", "*/node_modules/*", "-not", "-path", "*/openclaw/*"],
                          capture_output=True, text=True).stdout.split()
    c = z()
    for rq in reqs:
        r = subprocess.run(["pip-audit", "-r", rq, "-f", "json", "--progress-spinner", "off"],
                           capture_output=True, text=True, timeout=600, check=False)
        try:
            for dep in (json.loads(r.stdout or "{}").get("dependencies") or []):
                c["high"] += len(dep.get("vulns") or [])
        except Exception:
            pass
    post("pip-audit", c)


def detect_secrets():
    # 3rd secrets engine (Yelp). Excludes the sealed-secrets ciphertext (encrypted, safe to commit) so it doesn't
    # flood; MEDIUM (advisory) — a committed .secrets.baseline is the follow-up to quiet the shared-dev-password FPs.
    r = subprocess.run(["detect-secrets", "scan", SRC, "--exclude-files",
                        r"(node_modules|openclaw|site-techdocs|sealed-secrets|package-lock\.json|\.secrets\.baseline)"],
                       capture_output=True, text=True, timeout=900, check=False)
    open(f"{OUT}/detect-secrets.json", "w").write(r.stdout or "{}")
    c = z()
    try:
        c["medium"] = sum(len(v) for v in (json.loads(r.stdout or "{}").get("results") or {}).values())
    except Exception as e:
        print(f"  ! detect-secrets: {e}", flush=True)
    post("detect-secrets", c)


def headers():
    # NOVEL to weyland — live HTTP security-header check against the ingress hosts declared in docs/hosts.md
    # (in-cluster DNS resolves *.weyland.lab via coredns-custom → LAN). Each MISSING security header on a reachable
    # host = one medium finding. A down/unreachable host is blackbox's concern, not a header finding — skipped.
    import re, ssl
    want = ["strict-transport-security", "content-security-policy", "x-frame-options",
            "x-content-type-options", "referrer-policy"]
    hostsmd = os.path.join(SRC, "docs", "hosts.md")
    # hosts.md lists ingresses as BARE names (realm.weyland.lab) — extract those, prepend https://. (NOT the literal
    # "*.weyland.lab" wildcard — the [a-z0-9] start excludes it.)
    hosts = sorted(set(re.findall(r"[a-z0-9][a-z0-9-]*\.weyland\.lab", open(hostsmd).read()))) \
        if os.path.exists(hostsmd) else []
    # TLS verify off ON PURPOSE: header-presence probe of the lab's OWN *.weyland.lab hosts (self-signed wildcard,
    # no lab CA in this pod's trust store); we read response headers, transmit nothing — cert validity isn't the
    # control here (same posture as the blackbox synthetic prober). Documented so it's a decision, not an oversight.
    ctx = ssl.create_default_context(); ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # nosemgrep  # noqa: S323
    c = z(); reachable = evaluated = 0
    for h in hosts:
        try:
            resp = urllib.request.urlopen(f"https://{h}", timeout=8, context=ctx)
        except Exception:
            continue  # unreachable / non-HTTPS backend / on-demand host — blackbox's concern, not a header finding
        reachable += 1
        if "text/html" not in (resp.headers.get("Content-Type") or "").lower():
            continue  # not a browser page (registry/API/JSON) → browser security headers don't apply
        evaluated += 1
        present = {k.lower() for k in resp.headers.keys()}
        c["medium"] += len([x for x in want if x not in present])
    print(f"  headers: {reachable} reachable / {evaluated} HTML of {len(hosts)} hosts in hosts.md", flush=True)
    post("headers", c)


# ---- Go (for polyglot repos — Stud.io etc.; per go.mod module, clean no-op on weyland's 0-Go tree) ----


def _go_modules():
    return [os.path.dirname(p) for p in subprocess.run(
        ["find", SRC, "-name", "go.mod", "-not", "-path", "*/node_modules/*", "-not", "-path", "*/openclaw/*"],
        capture_output=True, text=True).stdout.split()]


def go_vet():
    c = z()
    for mod in _go_modules():
        r = subprocess.run(["go", "vet", "./..."], cwd=mod, capture_output=True, text=True, timeout=900, check=False)
        c["medium"] += len([ln for ln in r.stderr.splitlines() if ".go:" in ln])
    post("go-vet", c)


def gosec():
    c = z(); m = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    for mod in _go_modules():
        r = subprocess.run(["gosec", "-quiet", "-fmt", "json", "./..."], cwd=mod,
                           capture_output=True, text=True, timeout=900, check=False)
        try:
            for iss in (json.loads(r.stdout or "{}").get("Issues") or []):
                c[m.get((iss.get("severity") or "").upper(), "low")] += 1
        except Exception:
            pass
    post("gosec", c)


def govulncheck():
    c = z()
    for mod in _go_modules():
        r = subprocess.run(["govulncheck", "-format", "json", "./..."], cwd=mod,
                           capture_output=True, text=True, timeout=900, check=False)
        ids = set()
        for ln in (r.stdout or "").splitlines():
            try:
                f = json.loads(ln).get("finding")
                if f and f.get("trace") and f.get("osv"):
                    ids.add(f["osv"])
            except Exception:
                pass
        c["high"] += len(ids)
    post("govulncheck", c)


def staticcheck():
    c = z()
    for mod in _go_modules():
        r = subprocess.run(["staticcheck", "-f", "json", "./..."], cwd=mod,
                           capture_output=True, text=True, timeout=900, check=False)
        for ln in (r.stdout or "").splitlines():
            try:
                sev = (json.loads(ln).get("severity") or "").lower()
                c["medium" if sev in ("error", "warning") else "low"] += 1
            except Exception:
                pass
    post("staticcheck", c)


SEV_ORDER = ("critical", "high", "medium", "low")


def _sev_weight(r):
    """Sort key: worst-first. A single critical outranks any number of lows, so weight by band, not by total."""
    return (-r["critical"], -r["high"], -r["medium"], -r["low"], r["tool"])


def _prior_summary(s3, bucket, this_prefix):
    """Fetch the most recent PREVIOUS run's summary.json so the report can show deltas.

    Best-effort and deliberately quiet: a missing/corrupt prior summary means 'no trend column', never a failure.
    Prefixes are ISO-8601 timestamps, so lexical sort == chronological sort.
    """
    try:
        r = s3.list_objects_v2(Bucket=bucket, Delimiter="/")
        prefixes = sorted(p["Prefix"] for p in r.get("CommonPrefixes", []))
        prior = [p for p in prefixes if p < this_prefix]
        if not prior:
            return None
        obj = s3.get_object(Bucket=bucket, Key=f"{prior[-1]}summary.json")
        return json.loads(obj["Body"].read().decode())
    except Exception:
        return None


def _html(stamp, links, prior):
    """Self-contained HTML summary — no external CSS/JS, so it renders from a presigned URL with no network."""
    pri = {r["tool"]: r for r in (prior or {}).get("results", [])} if prior else {}
    rows = []
    tot = z()
    for r in sorted(RESULTS, key=_sev_weight):
        for k in SEV_ORDER:
            tot[k] += r[k]
        delta = ""
        if r["tool"] in pri:
            d = r["total"] - pri[r["tool"]]["total"]
            if d > 0:
                delta = f'<span class="up">+{d}</span>'
            elif d < 0:
                delta = f'<span class="down">{d}</span>'
            else:
                delta = '<span class="same">0</span>'
        else:
            delta = '<span class="same">new</span>'
        cells = "".join(
            f'<td class="n {k}">{r[k] or ""}</td>' for k in SEV_ORDER
        )
        raw = links.get(f"{r['tool']}.json")
        name = f'<a href="{raw}">{r["tool"]}</a>' if raw else r["tool"]
        cls = "bad" if r["critical"] else "warn" if r["high"] else ""
        rows.append(f'<tr class="{cls}"><td>{name}</td>{cells}<td class="n">{r["total"]}</td><td class="n">{delta}</td></tr>')

    other = "".join(
        f'<li><a href="{u}">{k}</a></li>' for k, u in sorted(links.items())
        if not any(k == f"{r['tool']}.json" for r in RESULTS)
    )
    prior_note = (f'vs previous run <code>{prior["stamp"]}</code>' if prior else "no previous run to compare")
    return f"""<!doctype html>
<meta charset="utf-8"><title>scan-suite {stamp}</title>
<style>
 :root{{color-scheme:light dark}}
 body{{font:14px/1.5 ui-sans-serif,system-ui,sans-serif;margin:2rem auto;max-width:60rem;padding:0 1rem}}
 h1{{font-size:1.3rem;margin:0 0 .2rem}} .sub{{opacity:.7;margin:0 0 1.5rem}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{padding:.4rem .6rem;border-bottom:1px solid #8884;text-align:left}}
 th{{font-weight:600;opacity:.8;font-size:.85rem;text-transform:uppercase;letter-spacing:.04em}}
 td.n{{text-align:right;font-variant-numeric:tabular-nums}}
 .critical{{color:#d21;font-weight:700}} .high{{color:#e60;font-weight:600}}
 .medium{{opacity:.75}} .low{{opacity:.5}}
 tr.bad td:first-child{{border-left:3px solid #d21;padding-left:.45rem}}
 tr.warn td:first-child{{border-left:3px solid #e60;padding-left:.45rem}}
 tfoot td{{font-weight:700;border-top:2px solid #8886}}
 .up{{color:#d21}} .down{{color:#0a7}} .same{{opacity:.45}}
 ul{{padding-left:1.2rem}} code{{font-size:.9em}}
</style>
<h1>code-scan-suite &mdash; {TARGET}</h1>
<p class="sub">{stamp} &middot; {prior_note} &middot; reports expire 90 days after the run</p>
<table>
 <thead><tr><th>Tool</th><th class="n">Crit</th><th class="n">High</th><th class="n">Med</th><th class="n">Low</th><th class="n">Total</th><th class="n">&Delta;</th></tr></thead>
 <tbody>{"".join(rows)}</tbody>
 <tfoot><tr><td>all tools</td>{"".join(f'<td class="n {k}">{tot[k]}</td>' for k in SEV_ORDER)}<td class="n">{sum(tot.values())}</td><td></td></tr></tfoot>
</table>
<p class="sub">Rows are worst-first: one critical outranks any number of lows. Tool names link to the raw JSON.</p>
{f"<h2>Other artifacts</h2><ul>{other}</ul>" if other else ""}
"""


def archive():
    """Upload the raw per-tool JSON + a rendered HTML summary to MinIO so findings outlive the pod.

    Why this exists: OUT is an emptyDir, so before this the moment the next run deleted the pod every report was
    gone. Port keeps the per-tool COUNTS (the durable trend) but not one finding's detail. Retention is an ILM
    expiry rule on the bucket (90d), not a cron here.

    Browse the results in the S3 UIs the lab already runs — files.weyland.lab (Filestash) or minio.weyland.lab —
    both behind Keycloak. Deliberately NO presigned links: they add a two-endpoint signing dance (a presigned
    signature covers the host, so an in-cluster-signed URL is unopenable from a laptop) and a 7-day SigV4 expiry
    ceiling, to reach files an authenticated browser can already open directly.

    Best-effort like every other step: a MinIO outage must not fail a scan that already produced good results.
    """
    bucket = os.environ.get("SCAN_S3_BUCKET", "scan-reports")
    endpoint = os.environ.get("SCAN_S3_ENDPOINT")
    if not endpoint:
        print("  ~ archive: SCAN_S3_ENDPOINT unset — skipping upload (reports stay pod-local)", flush=True)
        return
    try:
        import boto3
    except ImportError:
        print("  !! archive: boto3 missing from the image — skipping upload", flush=True)
        return

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    prefix = f"{stamp}/"
    s3 = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1",
                      aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))

    prior = _prior_summary(s3, bucket, prefix)

    sent = 0
    for name in sorted(os.listdir(OUT)):
        path = os.path.join(OUT, name)
        if not os.path.isfile(path):
            continue
        try:
            s3.upload_file(path, bucket, prefix + name,
                           ExtraArgs={"ContentType": "application/json"} if name.endswith(".json") else None)
            sent += 1
        except Exception as e:
            print(f"  !! archive: {name} failed: {e}", flush=True)

    # summary.json is what the NEXT run diffs against for its delta column.
    try:
        s3.put_object(Bucket=bucket, Key=prefix + "summary.json", ContentType="application/json",
                      Body=json.dumps({"stamp": stamp, "target": TARGET, "results": RESULTS}, indent=1).encode())
        sent += 1
    except Exception as e:
        print(f"  !! archive: summary.json failed: {e}", flush=True)

    # Links are RELATIVE (just "trivy.json"), so they resolve correctly wherever the page is served from.
    # text/html is what makes a browser render it rather than download it.
    try:
        s3.put_object(Bucket=bucket, Key=prefix + "index.html", ContentType="text/html; charset=utf-8",
                      Body=_html(stamp, {n: n for n in sorted(os.listdir(OUT)) if os.path.isfile(os.path.join(OUT, n))},
                                 prior).encode())
        sent += 1
    except Exception as e:
        print(f"  !! archive: index.html failed: {e}", flush=True)

    print(f"  = archive: {sent} file(s) → s3://{bucket}/{prefix} (90d ILM)", flush=True)
    # Deep-link straight at this run's folder — nobody should have to click down a bucket tree to find it.
    # Base is env-configurable so swapping Filestash for the MinIO console is a manifest edit, not a code change.
    browse = os.environ.get("SCAN_BROWSE_BASE", "https://files.weyland.lab/files").rstrip("/")
    # Two different jobs, two different hosts — this is not redundancy:
    #   browse -> Filestash. A file MANAGER: great for navigating the raw JSON, but it renders .html in a
    #             syntax-highlighted CODE viewer, so the summary page is unreadable through it. (Verified
    #             2026-08-20: /files/<path>.html is treated as a directory; /view/<path>.html shows source.)
    #   report -> the MinIO S3 endpoint directly, which serves the object with the text/html Content-Type we
    #             set on upload, so a browser actually RENDERS it. Requires the bucket to allow anonymous
    #             download (`mc anonymous set download weyland/scan-reports`) — LAN-only, and these are
    #             findings for a repo that is already public.
    report = os.environ.get("SCAN_REPORT_BASE", "https://s3.weyland.lab").rstrip("/")
    print(f"    browse: {browse}/{bucket}/{stamp}/", flush=True)
    print(f"    report: {report}/{bucket}/{stamp}/index.html", flush=True)


if __name__ == "__main__":
    print(f"=== weyland code-scan suite @ {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}  src={SRC} ===", flush=True)
    # Hoisted from codemaat(): the clone runs as root, the scan as uid 10001 → git "dubious ownership". This must
    # be set BEFORE any git-using check (secret_files runs 2nd, codemaat last) or those checks silently no-op.
    sh(["git", "config", "--global", "--add", "safe.directory", SRC])
    for fn in (gitleaks, secret_files, detect_secrets, checkov, kubescape, hadolint, bandit, ruff,
               osv, pip_audit, shellcheck, semgrep, trivy, go_vet, gosec, govulncheck, staticcheck,
               headers, codemaat):
        try:
            fn()
        except Exception as e:
            print(f"  !! {fn.__name__} crashed: {e}", flush=True)
    # Archive LAST, after every tool has written its JSON — this is the step that makes the reports outlive the pod.
    try:
        archive()
    except Exception as e:
        print(f"  !! archive crashed: {e}", flush=True)
    print(f"\n=== suite complete; raw reports in {OUT} ===", flush=True)
