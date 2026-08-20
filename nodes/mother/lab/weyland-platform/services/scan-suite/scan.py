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


def z():
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


def post(tool, c):
    total = sum(c.values())
    payload = {"tool": tool, "target": TARGET, "critical": c["critical"], "high": c["high"],
               "medium": c["medium"], "low": c["low"], "total": total,
               "scannedAt": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"  = {tool}: {c['critical']}C / {c['high']}H / {c['medium']}M / {c['low']}L (total {total})", flush=True)
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
    m = {"Critical": "critical", "High": "high", "Medium": "medium", "Low": "low"}
    c = z()
    # summaryDetails.controls: {id: {name, statusInfo, scoreFactor, controlID, ...}} — count FAILED by severity band
    for ctl in ((d.get("summaryDetails") or {}).get("controls") or {}).values():
        if (ctl.get("status") or "").lower() == "failed" or (ctl.get("ResourcesFailedCount") or ctl.get("resourceCounters", {}).get("failedResources", 0)):
            sf = ctl.get("scoreFactor", 0) or 0
            band = "critical" if sf >= 9 else "high" if sf >= 7 else "medium" if sf >= 4 else "low"
            c[band] += 1
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
    sh(["osv-scanner", "--format", "json", "-r", SRC], outfile=f"{OUT}/osv.json")
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
    print(f"\n=== suite complete; raw reports in {OUT} ===", flush=True)
