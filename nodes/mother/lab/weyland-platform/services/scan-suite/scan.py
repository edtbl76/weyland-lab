#!/usr/bin/env python3
"""B69 Wave 4 — code-scan suite orchestrator.

Runs each free scanner over the cloned repo at /src, POSTs per-tool severity counts to the Port `code-quality`
webhook (env PORT_INGEST_URL — same payload as the existing semgrep/trivy Jobs), and writes each tool's raw JSON
to /out (an emptyDir). Port holds the durable per-tool trend; the finding detail lives in this pod's logs (+ the
/out JSON while the pod exists). Every tool runs BEST-EFFORT: one failing or finding nothing never aborts the
rest. SonarQube is NOT here — it needs the server + a Java build (own CronJob).
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
    sh(["semgrep", "scan", "--config", "auto", "--json", "--output", f"{OUT}/semgrep.json",
        "--exclude", "node_modules", "--exclude", "openclaw", "--exclude", "site-techdocs", SRC])
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
    sh(["git", "config", "--global", "--add", "safe.directory", SRC])  # clone runs as root, scan as uid 10001 -> git "dubious ownership"
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


if __name__ == "__main__":
    print(f"=== weyland code-scan suite @ {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}  src={SRC} ===", flush=True)
    for fn in (gitleaks, checkov, kubescape, hadolint, bandit, osv, shellcheck, semgrep, trivy, codemaat):
        try:
            fn()
        except Exception as e:
            print(f"  !! {fn.__name__} crashed: {e}", flush=True)
    print(f"\n=== suite complete; raw reports in {OUT} ===", flush=True)
