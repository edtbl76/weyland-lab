#!/usr/bin/env python3
"""
B62 — AI-dev usage data product, PRODUCER stage (mirrors the B37 / aidlc-kb pattern).

Runs on rogueone (where the Claude Code logs live). Parses the relevant project
logs into per-session summary JSON (metrics only — NO conversation content) and
writes one file per session to a local out dir. A `mc mirror <outdir> weyland/ai-sessions/`
then ships them to MinIO, where the Dagster `ai_session_ingest` asset reads them and
upserts to Port. Pure stdlib — no pip deps.

Env (optional):
  AI_SESSIONS_OUT   default ~/.cache/ai-sessions   (where summary JSONs are written)
"""
import os, sys, json, glob, datetime as dt
from collections import defaultdict

PROJECTS_ROOT = os.path.expanduser("~/.claude/projects")
OUT_DIR = os.path.expanduser(os.environ.get("AI_SESSIONS_OUT", "~/.cache/ai-sessions"))

# project-dir basename -> (project label, Port service id or None). Etudes folds into midi_real_book.
SCOPE = {
    "-home-edwardmangini-IdeaProjects-weyland":                              ("weyland-lab", "weyland-lab"),
    "-home-edwardmangini-Documents-Studio-STUD-io":                          ("stud.io", "stud-io"),
    "-home-edwardmangini-IdeaProjects-midi-real-book":                       ("midi_real_book", "midi-real-book"),
    "-home-edwardmangini-IdeaProjects-Etudes":                              ("midi_real_book", "midi-real-book"),
    "-home-edwardmangini-IdeaProjects-emangini-tailwind-nextjs-contentlayer": ("emangini-tailwind", "emangini-tailwind"),
}

# $ per 1M tokens: (input, output, cache_read, cache_write). EDIT to your plan / list prices.
# value = API-equivalent (what pay-per-use WOULD cost); on a subscription, $0 actually changes hands.
PRICING = {
    "opus":   (15.0, 75.0, 1.50, 18.75),
    "sonnet": (3.0,  15.0, 0.30, 3.75),
    "haiku":  (0.80, 4.0,  0.08, 1.00),
    "fable":  (3.0,  15.0, 0.30, 3.75),
}
def price_tier(model):
    m = (model or "").lower()
    for k, v in PRICING.items():
        if k in m:
            return v
    return PRICING["sonnet"]

def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def parse_session(path):
    first_ts = last_ts = None
    user_turns = asst_turns = tools = 0
    inp = out = cr = cc = 0
    models = set()
    value = 0.0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = ev.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            t = ev.get("type")
            if t == "user":
                user_turns += 1
            elif t == "assistant":
                asst_turns += 1
                msg = ev.get("message") or {}
                model = msg.get("model")
                if model:
                    models.add(model)
                u = msg.get("usage") or {}
                i = u.get("input_tokens", 0) or 0
                o = u.get("output_tokens", 0) or 0
                r = u.get("cache_read_input_tokens", 0) or 0
                c = u.get("cache_creation_input_tokens", 0) or 0
                inp += i; out += o; cr += r; cc += c
                pi, po, pr, pc = price_tier(model)
                value += (i * pi + o * po + r * pr + c * pc) / 1_000_000
                for blk in (msg.get("content") or []):
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        tools += 1
    if first_ts is None:
        return None
    dur = (parse_ts(last_ts) - parse_ts(first_ts)).total_seconds() / 60.0
    return {
        "session_id": os.path.splitext(os.path.basename(path))[0],
        "started_at": first_ts, "ended_at": last_ts,
        "duration_minutes": round(dur, 1),
        "user_turns": user_turns, "assistant_turns": asst_turns,
        "input_tokens": inp, "output_tokens": out,
        "cache_read_tokens": cr, "cache_creation_tokens": cc,
        "total_tokens": inp + out,                      # fresh tokens; cache lives in its own fields
        "models": sorted(models), "tools_invoked": tools,
        "api_equiv_value_usd": round(value, 2),         # what API pay-per-use would have cost
    }

def collect():
    out = []
    for dirname, (project, service) in SCOPE.items():
        for path in glob.glob(os.path.join(PROJECTS_ROOT, dirname, "*.jsonl")):
            s = parse_session(path)
            if s:
                s["project"], s["service"] = project, service
                out.append(s)
    return out

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sessions = collect()
    for s in sessions:
        with open(os.path.join(OUT_DIR, f'{s["session_id"]}.json'), "w", encoding="utf-8") as f:
            json.dump(s, f)
    agg = defaultdict(lambda: [0, 0, 0.0])
    for s in sessions:
        a = agg[s["project"]]
        a[0] += 1; a[1] += s["output_tokens"]; a[2] += s["api_equiv_value_usd"]
    print(f"wrote {len(sessions)} session summaries to {OUT_DIR}", file=sys.stderr)
    for p, (n, otk, val) in sorted(agg.items()):
        print(f"  {p:18s} {n:3d} sessions  {otk:>12,} output tok  ${val:>10,.2f} API-equiv value", file=sys.stderr)

if __name__ == "__main__":
    main()
