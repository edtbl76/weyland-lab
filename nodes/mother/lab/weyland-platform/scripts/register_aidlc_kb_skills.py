#!/usr/bin/env python3
"""Bring the AIDLC knowledge-base repositories into the Bifrost Skills Repository as Agent Skills (B111).

The three .methodaidlc knowledge repos are large libraries of reusable, self-contained knowledge docs — each entry is a
skill. This generator ingests all three, scrubbing the proprietary "Method" brand (same as register_aidlc_skills.py):
  - engineering-knowledge-repository/  -> ek-<stem>   (design patterns, practices, architectures — ~395)
  - consulting-tools-repository/        -> ct-<stem>   (frameworks: adkar, bcg-matrix, jtbd, … — ~60)
  - industry-vertical-repository/<v>/   -> iv-<v>-<stem> (per-vertical insights — ~56)

Reuses scrub()/describe()/kebab()/_read()/LOADER from register_aidlc_skills.py (single source of that logic). Runs
LOCALLY (reads the files) and emits a self-contained loader piped into the cluster — .methodaidlc stays the source of
truth, nothing duplicated into git:
    python3 scripts/register_aidlc_kb_skills.py --dry
    python3 scripts/register_aidlc_kb_skills.py | kubectl -n weyland exec -i deploy/weyland-guard -- python -
Idempotent on the cluster side (create-if-absent by name).
"""
import base64
import importlib.util
import json
import os
import sys

_spec = importlib.util.spec_from_file_location("_r", os.path.join(os.path.dirname(__file__), "register_aidlc_skills.py"))
_r = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_r)
scrub, describe, kebab, _read, LOADER, ROOT = _r.scrub, _r.describe, _r.kebab, _r._read, _r.LOADER, _r.ROOT

# (dir, name-prefix, fixed-category-or-None). None → category derived per-vertical (industry is nested).
REPOS = [
    ("engineering-knowledge-repository", "ek", "engineering-knowledge"),
    ("consulting-tools-repository",      "ct", "consulting-tools"),
    ("industry-vertical-repository",     "iv", None),
]
SKIP = {"index", "readme"}   # keep _overview.md (useful vertical context)

def build():
    skills, seen = [], set()
    for repo, prefix, fixed_cat in REPOS:
        base_dir = os.path.join(ROOT, repo)
        for dp, _, files in os.walk(base_dir):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                stem = os.path.splitext(fn)[0]
                if stem.lower() in SKIP:
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), base_dir)
                parts = rel.split(os.sep)
                if len(parts) > 1:                          # nested (industry vertical)
                    vertical = parts[0]
                    name = kebab(f"{prefix}-{vertical}-{stem}")
                    category = fixed_cat or f"industry-{vertical}"
                else:
                    name = kebab(f"{prefix}-{stem}")
                    category = fixed_cat or "misc"
                name = name[:64].rstrip("-")
                while name in seen:                          # de-collide truncations
                    name = (name[:61].rstrip("-") + "-2")
                seen.add(name)
                title, body = _read(os.path.join(dp, fn))
                skills.append({
                    "name": name,
                    "version": "1.0.0",
                    "description": scrub(describe(title or stem.replace("-", " ").title(), body))[:1000],
                    "skill_md_body": scrub(body),
                    "compatibility": "claude-code,codex",
                    "allowed_tools": "",
                    "license": "Proprietary",
                    "metadata": {"category": category, "repo": repo},
                })
    skills.sort(key=lambda s: (s["metadata"]["category"], s["name"]))
    return skills

def main():
    skills = build()
    if "--dry" in sys.argv:
        from collections import Counter
        by = Counter(s["metadata"]["category"] for s in skills)
        for cat, n in sorted(by.items()):
            print(f"{n:4}  {cat}")
        print(f"\n{len(skills)} KB skills across {len(by)} categories.")
        # brand check
        import re
        bad = [s["name"] for s in skills if re.search(r"\b(Method|METHOD)\b", s["name"] + " " + s["description"] + " " + s["skill_md_body"])]
        print("residual 'Method' brand:", bad or "NONE")
        return
    payload = base64.b64encode(json.dumps(skills).encode()).decode()
    print("import base64, json")
    print(f'SKILLS = json.loads(base64.b64decode("{payload}").decode())')
    print(LOADER)

if __name__ == "__main__":
    main()
