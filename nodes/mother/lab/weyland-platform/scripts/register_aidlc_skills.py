#!/usr/bin/env python3
"""Bring the AIDLC / Method rule library into the Bifrost Skills Repository as Agent Skills (B111).

⛔ RETIRED as of B133 (AIDLC-v2 migration, 2026-08-20) — this generator NO LONGER RUNS in weyland.

It reads the Method rule tree (`.methodaidlc/.method-rule-details/` + `.aidlc-rule-details/`), which the v2
migration removed from this repo (retired to `~/methodaidlc-retired/`, tarball + the `method-aidlc` installer repo).
Its 52 skills REMAIN REGISTERED in Bifrost from the last successful run — they are FROZEN, not regenerable here.
To rebuild them you must first restore a Method source tree and point AIDLC_ROOT at it, or re-derive the procedures
from the v2 stage files under `.claude/aidlc-common/stages/`. See docs/runbooks/aidlc-workflow.md#accepted-gaps.

Kept in-tree (rather than deleted) because it is the only executable record of how those frozen skills were derived,
and because AIDLC_ROOT makes it runnable again against a restored source. It now FAILS LOUDLY when the source is
absent — previously it emitted a zero-skill loader that reported "0 created" and looked like success.

The .methodaidlc rule files ARE reusable procedures (one per AIDLC stage / ritual / extension / common rule). This
generator reads them from the repo and turns each into a Bifrost skill (name `aidlc-<stem>`, body = the rule content).

NOTE: the KB skills generator (`register_aidlc_kb_skills.py`, 511 skills) is a DIFFERENT script and is NOT retired —
its knowledge repos were decoupled to `knowledge-repos/` and it still runs normally.

RUN MODEL — the Bifrost API is only reachable in-cluster, but the rule files are only on the workstation. So this
generator runs LOCALLY (reads the files) and EMITS a self-contained loader to stdout that is piped into the cluster:

    python3 scripts/register_aidlc_skills.py --dry     # review the derived skill list locally, no writes
    python3 scripts/register_aidlc_skills.py | kubectl -n weyland exec -i deploy/weyland-guard -- python -

Two-layer resolution (matches the CLAUDE.md workflow): for a given phase/stem the METHOD layer wins; the base AIDLC
layer fills gaps it doesn't cover. Idempotent on the cluster side (create-if-absent by name).
"""
import base64
import json
import os
import re
import sys

def _find_aidlc():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != "/":
        cand = os.path.join(d, ".methodaidlc")
        if os.path.isdir(cand):
            return cand
        d = os.path.dirname(d)
    return ".methodaidlc"

ROOT = os.getenv("AIDLC_ROOT") or _find_aidlc()
# Knowledge repos (engineering-knowledge / consulting-tools / industry-vertical) were moved OUT of
# .methodaidlc into a standalone, committed home during the AIDLC-v2 migration — they are DATA that
# feeds Bifrost skills/prompts + the DataHub glossary, independent of the (retired) Method workflow.
def _find_kb():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != "/":
        cand = os.path.join(d, "knowledge-repos")
        if os.path.isdir(cand):
            return cand
        d = os.path.dirname(d)
    return "knowledge-repos"
KB_ROOT = os.getenv("AIDLC_KB_ROOT") or _find_kb()   # self-discovers; survives .methodaidlc removal
LAYERS = [(".method-rule-details", "method"), (".aidlc-rule-details", "aidlc")]
SKIP_STEMS = {"readme", "welcome-message"}   # branding / index, not procedures

def kebab(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-+", "-", s)

def scrub(t):
    """Remove the proprietary 'Method' brand from distributable skill content — the .methodaidlc source keeps it, the
    skills served/installed via Bifrost must not. Handles ALL-CAPS heading markers, mixed case, possessive, and paths."""
    # ALL-CAPS heading markers first: "## METHOD ADDITION: ..." / "## METHOD: X"
    t = re.sub(r"\bMETHOD ADDITION\b", "ADDITION", t)
    t = re.sub(r"\bMETHOD MODIFICATION\b", "MODIFICATION", t)
    t = re.sub(r"\bMETHOD RITUAL\b", "RITUAL", t)
    t = re.sub(r"\bMETHOD:\s*", "", t)                  # "## METHOD: Stage Ownership" -> "## Stage Ownership"
    t = re.sub(r"\bMETHOD\b", "AIDLC", t)               # any remaining all-caps
    t = t.replace(".method-rule-details", ".rule-details")   # path leak
    # mixed case
    t = re.sub(r"\bMethod[’']s\b", "the", t)      # possessive: "Method's four ..." -> "the four ..."
    t = re.sub(r"\bMethod\s+(?=[A-Z])", "", t)          # qualifier: "Method Override" -> "Override"
    t = re.sub(r"\bMethod\b", "AIDLC", t)               # bare noun: "per Method" -> "per AIDLC"
    t = re.sub(r"\ba AIDLC\b", "an AIDLC", t)
    t = re.sub(r"\bthe the\b", "the", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t

LAYER_MAP = {"method+aidlc": "base+extended", "method": "extended", "aidlc": "base"}

def describe(title, body):
    """One-line description: the H1 title + the first real prose sentence (skip bold-field lines / headings)."""
    for line in body.splitlines():
        t = line.strip()
        if not t or t.startswith(("#", ">", "|", "-", "*", "`")) or (t.startswith("**") and t.endswith(":")) or ":**" in t[:40]:
            continue
        t = re.sub(r"[*`\[\]]", "", t)
        return (f"{title} — {t}")[:1000]
    return f"{title} — AIDLC procedure."[:1000]

def _read(path):
    raw = open(path, encoding="utf-8").read().strip()
    title = next((l.lstrip("# ").strip() for l in raw.splitlines() if l.startswith("# ")), "")
    body = re.sub(r"^#\s+.*\n", "", raw, count=1).strip()   # drop redundant H1 (title lives in name/desc)
    return title, body

def build(root):
    # Collect each (phase, stem) across BOTH layers, then merge — the Method layer often only OVERRIDES/ADDS to the
    # base AIDLC procedure ("Execute all steps from the base file with ..."), so a faithful skill needs base + Method.
    coll, order = {}, []
    for sub, layer in LAYERS:
        base = os.path.join(root, sub)
        for dirpath, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".md") or "opt-in" in fn:
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), base)
                phase, stem = rel.split(os.sep)[0], os.path.splitext(fn)[0]
                if stem.lower() in SKIP_STEMS:
                    continue
                title, body = _read(os.path.join(dirpath, fn))
                key = (phase, stem)
                if key not in coll:
                    coll[key] = {}; order.append(key)
                coll[key][layer] = {"title": title, "body": body, "src": f"{sub}/{rel}"}
    skills = []
    for phase, stem in order:
        m, a = coll[(phase, stem)].get("method"), coll[(phase, stem)].get("aidlc")
        if m and a:
            title = m["title"] or a["title"]
            body = a["body"] + "\n\n---\n\n## Extended layer (overrides / additions)\n\n" + m["body"]
            layer = "method+aidlc"
        else:
            primary = m or a
            title, body = primary["title"], primary["body"]
            layer = "method" if m else "aidlc"
        skills.append({
            "name": kebab("aidlc-" + stem).replace("method-", ""),   # drop the brand from names too
            "version": "1.0.0",
            "description": scrub(describe(title or stem.replace("-", " ").title(), body)),
            "skill_md_body": scrub(body),
            "compatibility": "claude-code,codex",
            "allowed_tools": "",
            "license": "Proprietary",
            "metadata": {"category": f"aidlc-{phase}", "layer": LAYER_MAP[layer]},
        })
    skills.sort(key=lambda s: (s["metadata"]["category"], s["name"]))
    return skills

LOADER = r'''
import os, httpx
BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
c = httpx.Client(base_url=BASE, timeout=60)
existing, _off = set(), 0            # paginate — the skills list caps at 100/page
while True:
    _r = c.get("/api/skills?limit=100&offset=%d" % _off).json()
    _pg = _r.get("skills") or []
    existing |= {s["name"] for s in _pg}
    _off += len(_pg)
    if not _pg or _off >= _r.get("total", 0):
        break
created = skipped = 0
for sk in SKILLS:
    if sk["name"] in existing:
        skipped += 1; continue
    r = c.post("/api/skills", json=sk)
    ok = r.status_code < 300
    print(("CREATED " if ok else "FAILED  ") + sk["metadata"]["category"] + "/" + sk["name"] + ("" if ok else " " + r.text[:120]))
    created += ok
print("\ndone. %d created, %d existing, %d total AIDLC skills." % (created, skipped, len(SKILLS)))
'''

def _require_method_source(root):
    """Fail loudly if the retired Method rule tree is absent (B133).

    os.walk() over a missing directory yields nothing, so without this the generator emitted a VALID loader
    containing zero skills and printed "0 created, 0 existing" — indistinguishable from a clean no-op re-sync.
    A retired generator must announce that it is retired, not quietly produce an empty artifact.
    """
    present = [sub for sub, _ in LAYERS if os.path.isdir(os.path.join(root, sub))]
    if present:
        return
    sys.exit(
        "register_aidlc_skills.py: RETIRED — no Method rule source found.\n"
        f"  looked for {[s for s, _ in LAYERS]} under: {root}\n"
        "  The AIDLC-v2 migration (B133, 2026-08-20) removed .methodaidlc/ from this repo.\n"
        "  Its 52 skills remain REGISTERED in Bifrost but are FROZEN — not regenerable here.\n"
        "  To run anyway, restore a Method source and set AIDLC_ROOT, e.g.:\n"
        "    AIDLC_ROOT=~/methodaidlc-retired python3 scripts/register_aidlc_skills.py --dry\n"
        "  See docs/runbooks/aidlc-workflow.md#accepted-gaps\n"
        "  (For the 511 KB skills use register_aidlc_kb_skills.py — that one is NOT retired.)"
    )

def main():
    root = os.path.abspath(ROOT)
    _require_method_source(root)
    skills = build(root)
    if "--dry" in sys.argv:
        for s in skills:
            print(f"{s['metadata']['category']:22} {s['name']:34} body={len(s['skill_md_body']):5}  {s['description'][:70]}")
        print(f"\n{len(skills)} AIDLC skills across {len(set(s['metadata']['category'] for s in skills))} categories.")
        return
    payload = base64.b64encode(json.dumps(skills).encode()).decode()
    print("import base64, json")
    print(f'SKILLS = json.loads(base64.b64decode("{payload}").decode())')
    print(LOADER)

if __name__ == "__main__":
    main()
