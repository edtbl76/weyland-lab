#!/usr/bin/env python3
"""Derive a large corpus of Bifrost prompts from the AIDLC knowledge base (B111) — parallels the skill corpus.

Each knowledge entry is naturally prompt-shaped: a consulting framework -> an "apply this framework" prompt; an AIDLC
stage -> a "run this stage" prompt; an industry entry -> a domain-lens prompt. This generator reads .methodaidlc and
emits foldered, model-agnostic prompts into Bifrost's Prompt Repository, scrubbing the proprietary "Method" brand (same
as the skill generators). Reuses scrub()/describe()/_read()/kebab()/ROOT from register_aidlc_skills.py.

RUN (locally reads the files, pipes the loader in-cluster; .methodaidlc stays the source of truth):
    python3 scripts/register_aidlc_prompts.py --dry
    python3 scripts/register_aidlc_prompts.py | kubectl -n weyland exec -i deploy/weyland-guard -- python -

Complements the hand-authored register_bifrost_prompts.py (task/system/eval prompts). Idempotent (create-if-absent by name).
"""
import base64
import importlib.util
import json
import os
import sys

_spec = importlib.util.spec_from_file_location("_r", os.path.join(os.path.dirname(__file__), "register_aidlc_skills.py"))
_r = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_r)
scrub, describe, kebab, _read, ROOT = _r.scrub, _r.describe, _r.kebab, _r._read, _r.ROOT

FOLDERS = [
    ("consulting-frameworks", "Apply a specific consulting/strategy framework to a problem — one prompt per framework."),
    ("aidlc-stages",          "Execute a specific AIDLC lifecycle stage against your context."),
    ("industry-lens",         "Analyze a problem through a specific industry vertical's domain knowledge."),
]

def _msgs(system, user):
    return [{"role": "system", "content": scrub(system)}, {"role": "user", "content": scrub(user)}]

def build():
    prompts, seen = [], set()
    def add(folder, name, lane, messages):
        name = kebab(name)
        if name in seen:
            return
        seen.add(name)
        prompts.append({"folder": folder, "name": name, "commit_message": f"lane: {lane}", "messages": messages})

    base = os.path.join(ROOT, "consulting-tools-repository")
    for fn in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not fn.endswith(".md") or fn.lower() in ("index.md", "readme.md"):
            continue
        title, body = _read(os.path.join(base, fn))
        t = title or fn[:-3].replace("-", " ").title()
        essence = describe(t, body)
        add("consulting-frameworks", "apply-" + fn[:-3], "wl-reason -> wl-default", _msgs(
            f"You are an expert strategy facilitator applying the {t} framework. {essence} Guide the analysis rigorously "
            f"and produce the framework's SPECIFIC structured outputs — not a generic essay. State assumptions where "
            f"inputs are missing; never invent facts to fill the framework.",
            f"Apply {t} to:\n\n{{{{subject}}}}"))

    for layer in (".method-rule-details", ".aidlc-rule-details"):
        for phase in ("inception", "construction", "operations", "pre-inception"):
            d = os.path.join(ROOT, layer, phase)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".md") or "opt-in" in fn:
                    continue
                title, body = _read(os.path.join(d, fn))
                t = title or fn[:-3].replace("-", " ").title()
                add("aidlc-stages", "run-" + fn[:-3], "wl-agentic -> wl-reason", _msgs(
                    f"You are executing the '{t}' stage of the AIDLC delivery workflow. {describe(t, body)} Produce the "
                    f"stage's expected artifacts and its gate output. Follow the procedure; flag what is missing or "
                    f"unknown rather than fabricating it.",
                    f"Execute the {t} stage for:\n\n{{{{context}}}}"))

    iv = os.path.join(ROOT, "industry-vertical-repository")
    for vertical in sorted(os.listdir(iv)) if os.path.isdir(iv) else []:
        vdir = os.path.join(iv, vertical)
        if not os.path.isdir(vdir):
            continue
        vnice = vertical.replace("-", " ").title()
        for fn in sorted(os.listdir(vdir)):
            if not fn.endswith(".md") or fn.lower() in ("index.md", "readme.md"):
                continue
            title, body = _read(os.path.join(vdir, fn))
            topic = title or fn[:-3].lstrip("_").replace("-", " ").title()
            add("industry-lens", f"{vertical}-{fn[:-3].lstrip('_')}", "wl-reason -> wl-default", _msgs(
                f"You are a {vnice} industry domain expert. Analyze the user's input through the specific lens of "
                f"{topic} in {vnice} — the relevant regulations, systems, data, metrics, and constraints. "
                f"{describe(topic, body)} Ground the analysis in real domain knowledge; flag assumptions.",
                f"Analyze through the {vnice} / {topic} lens:\n\n{{{{input}}}}"))

    prompts.sort(key=lambda p: (p["folder"], p["name"]))
    return prompts

LOADER = r'''
import os, httpx
BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
c = httpx.Client(base_url=BASE, timeout=60)
folders = {f["name"]: f["id"] for f in c.get("/api/prompt-repo/folders").json().get("folders") or []}
for name, desc in FOLDERS:
    if name not in folders:
        folders[name] = c.post("/api/prompt-repo/folders", json={"name": name, "description": desc}).json()["folder"]["id"]
existing = {p["name"] for p in c.get("/api/prompt-repo/prompts").json().get("prompts") or []}
created = skipped = 0
for p in PROMPTS:
    if p["name"] in existing:
        skipped += 1; continue
    pid = c.post("/api/prompt-repo/prompts", json={"name": p["name"], "folder_id": folders[p["folder"]]}).json()["prompt"]["id"]
    r = c.post("/api/prompt-repo/prompts/%s/versions" % pid, json={"commit_message": p["commit_message"], "messages": p["messages"]})
    ok = r.status_code < 300
    print(("CREATED " if ok else "FAILED  ") + p["folder"] + "/" + p["name"] + ("" if ok else " " + r.text[:100]))
    created += ok
print("\ndone. %d created, %d existing, %d total corpus prompts." % (created, skipped, len(PROMPTS)))
'''

def main():
    prompts = build()
    if "--dry" in sys.argv:
        from collections import Counter
        import re
        by = Counter(p["folder"] for p in prompts)
        for f, n in sorted(by.items()):
            print(f"{n:4}  {f}")
        bad = [p["name"] for p in prompts if re.search(r"\b(Method|METHOD)\b", json.dumps(p["messages"]))]
        print(f"\n{len(prompts)} corpus prompts across {len(by)} folders. residual brand: {bad or 'NONE'}")
        return
    payload = base64.b64encode(json.dumps({"FOLDERS": FOLDERS, "PROMPTS": prompts}).encode()).decode()
    print("import base64, json")
    print(f'_d = json.loads(base64.b64decode("{payload}").decode()); FOLDERS = _d["FOLDERS"]; PROMPTS = _d["PROMPTS"]')
    print(LOADER)

if __name__ == "__main__":
    main()
