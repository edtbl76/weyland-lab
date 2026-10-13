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
import os, re, sys, json, glob, datetime as dt
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

# Project-dir PREFIX -> (project, service): directories created per task, e.g. the Emdash conveyor's worktrees
# (B179/B185 — each run gets `…-emdash-worktrees-weyland-<hash>-emdash-<run>`). Without this they were never counted.
SCOPE_PREFIXES = {
    "-home-edwardmangini-emdash-worktrees-weyland-": ("weyland-lab", "weyland-lab"),
}

# --- B185 lane 1: per-issue attribution ------------------------------------------------------------------------------
# An issue becomes CURRENT on (a) a human prompt naming exactly one issue, (b) a CHANGED session title naming one, or
# (c) a conveyor run's `issue-readiness.sh EMA-###` call. Tool results and assistant text are never used: they quote
# issues constantly (9,723 + 2,926 mentions in one session vs 616 in its prompts, observed 2026-10-12).
ISSUE_RE = re.compile(r"\b(EMA-\d+|B\d{1,3}(?:\.\d+)?)\b")
READINESS_RE = re.compile(r"issue-readiness\.sh\s+(EMA-\d+)")
IDLE_SECONDS = 300          # a gap longer than this between main-thread events is idle, counted nowhere
UNATTRIBUTED = None


def _one_issue(text):
    """The single issue a text names, or None when it names none or several (ambiguous)."""
    ids = set(ISSUE_RE.findall(text or ""))
    return ids.pop() if len(ids) == 1 else None


def _human_text(ev):
    """A real human prompt's text, or None: tool results and injected notices also arrive as `type: user`."""
    content = (ev.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str) or content.lstrip().startswith("<"):   # <task-notification>, <system-reminder>…
        return None
    return content


def _readiness_issue(msg):
    for blk in (msg.get("content") or []):
        if isinstance(blk, dict) and blk.get("type") == "tool_use":
            m = READINESS_RE.search(str((blk.get("input") or {}).get("command", "")))
            if m:
                return m.group(1)
    return None


def _new_bucket():
    return {"active_minutes": 0.0, "output_tokens": 0, "api_equiv_value_usd": 0.0, "assistant_turns": 0,
            "first_at": None}                      # when the issue first became current: the start of its cycle time


class _Attribution:
    """Walks a session's events in order; see the rules above. Time is main-thread only (sidechain subagents overlap
    it); tokens count wherever they were spent."""

    def __init__(self):
        self.current = UNATTRIBUTED
        self.last_title = None
        self.prev_ts = None
        self.human_prompts = 0
        self.buckets = defaultdict(_new_bucket)
        self.switches = []                         # (timestamp, issue) — which issue was current when a subagent began

    def _clock(self, ev):
        ts = ev.get("timestamp")
        if not ts or ev.get("isSidechain"):
            return
        now = parse_ts(ts)
        if self.prev_ts is not None:
            gap = (now - self.prev_ts).total_seconds()
            if 0 < gap <= IDLE_SECONDS:
                self.buckets[self.current]["active_minutes"] += gap / 60.0
        self.prev_ts = now

    def _marker(self, ev):
        t = ev.get("type")
        if t == "user":
            text = _human_text(ev)
            if text is not None:
                self.human_prompts += 1
                return _one_issue(text)
        elif t == "custom-title":
            title = ev.get("customTitle")
            if title != self.last_title:          # re-logged nearly every turn: only a CHANGE switches
                self.last_title = title
                return _one_issue(title)
        elif t == "assistant" and self.current is UNATTRIBUTED:   # a run naming nothing yet; an attended session
            return _readiness_issue(ev.get("message") or {})       # checking the queue must not steal its issue
        return None

    def add(self, ev, out_tokens=0, value=0.0, new_turn=False):
        self._clock(ev)                            # the gap BEFORE this event belongs to the issue current until now
        if new_turn:
            self.charge(self.current, out_tokens, value)
        issue = self._marker(ev)
        if issue and issue != self.current:
            self.current = issue
            ts = ev.get("timestamp")
            self.switches.append((parse_ts(ts) if ts else None, issue))
            b = self.buckets[issue]
            b["first_at"] = b["first_at"] or ts

    def charge(self, issue, out_tokens, value, turns=1):
        b = self.buckets[issue]
        b["output_tokens"] += out_tokens
        b["api_equiv_value_usd"] += value
        b["assistant_turns"] += turns

    def issue_at(self, when):
        """The issue current at `when` (a subagent's start); before any switch, unattributed."""
        issue = UNATTRIBUTED
        for ts, i in self.switches:
            if ts is None or ts <= when:
                issue = i
            else:
                break
        return issue

    def result(self):
        def tidy(b):
            return {**b, "active_minutes": round(b["active_minutes"], 1),
                    "api_equiv_value_usd": round(b["api_equiv_value_usd"], 4)}
        named = {k: v for k, v in self.buckets.items() if k is not UNATTRIBUTED}
        return {"issues": {k: tidy(named[k]) for k in sorted(named)},
                "unattributed": tidy(self.buckets[UNATTRIBUTED]),
                "human_prompts": self.human_prompts}


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

def _events(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


class _Usage:
    """Token/$ totals counted ONCE per message: Claude Code logs one record per content block and every one repeats the
    message's full usage (7,836 records for 3,146 messages in one session, 2026-10-12 — summing records overstated
    tokens and $ ~2.7x). A record without a message id is counted on its own."""

    def __init__(self):
        self.seen = set()
        self.turns = self.tools = 0
        self.inp = self.out = self.cr = self.cc = 0
        self.value = 0.0
        self.models = set()

    def add(self, msg):
        """Fold one assistant record in; returns (output_tokens, value) when it starts a new message, else None."""
        for blk in (msg.get("content") or []):
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                self.tools += 1                    # blocks differ between a message's records: each tool_use is real
        mid = msg.get("id")
        if mid is not None:
            if mid in self.seen:
                return None
            self.seen.add(mid)
        model = msg.get("model")
        if model:
            self.models.add(model)
        u = msg.get("usage") or {}
        i = u.get("input_tokens", 0) or 0
        o = u.get("output_tokens", 0) or 0
        r = u.get("cache_read_input_tokens", 0) or 0
        c = u.get("cache_creation_input_tokens", 0) or 0
        pi, po, pr, pc = price_tier(model)
        v = (i * pi + o * po + r * pr + c * pc) / 1_000_000
        self.turns += 1
        self.inp += i
        self.out += o
        self.cr += r
        self.cc += c
        self.value += v
        return o, v


def _add_subagents(session_path, usage, attribution):
    """Subagents log to <session>/subagents/agent-*.jsonl, outside the main log. Their tokens count toward the session
    and the issue current when they started; their time overlaps the parent's and is not added. Returns the count."""
    n = 0
    for sub in sorted(glob.glob(os.path.join(os.path.splitext(session_path)[0], "subagents", "*.jsonl"))):
        start = None
        before = (usage.out, usage.value, usage.turns)
        for ev in _events(sub):
            if start is None and ev.get("timestamp"):
                start = parse_ts(ev["timestamp"])
            if ev.get("type") == "assistant":
                usage.add(ev.get("message") or {})
        if start is None:
            continue
        n += 1
        attribution.charge(attribution.issue_at(start), usage.out - before[0], usage.value - before[1],
                           turns=usage.turns - before[2])
    return n


def parse_session(path):
    first_ts = last_ts = None
    user_turns = 0
    usage = _Usage()
    attribution = _Attribution()
    for ev in _events(path):
        ts = ev.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        t = ev.get("type")
        counted = None
        if t == "user":
            user_turns += 1
        elif t == "assistant":
            counted = usage.add(ev.get("message") or {})
        o, v = counted or (0, 0.0)
        attribution.add(ev, o, v, new_turn=counted is not None)
    if first_ts is None:
        return None
    subagents = _add_subagents(path, usage, attribution)
    dur = (parse_ts(last_ts) - parse_ts(first_ts)).total_seconds() / 60.0
    return {
        "session_id": os.path.splitext(os.path.basename(path))[0],
        "started_at": first_ts, "ended_at": last_ts,
        "duration_minutes": round(dur, 1),
        "user_turns": user_turns, "assistant_turns": usage.turns,
        "input_tokens": usage.inp, "output_tokens": usage.out,
        "cache_read_tokens": usage.cr, "cache_creation_tokens": usage.cc,
        "total_tokens": usage.inp + usage.out,          # fresh tokens; cache lives in its own fields
        "models": sorted(usage.models), "tools_invoked": usage.tools,
        "api_equiv_value_usd": round(usage.value, 2),   # what API pay-per-use would have cost
        "subagents": subagents,                         # their tokens are in the totals above
        "usage_counted": "per-message",                 # absent = a pre-2026-10-12 summary that summed every record
                                                        # (~2.7x high); its transcript is pruned, so it can't be redone
        **attribution.result(),                         # B185: issues{}, unattributed, human_prompts
    }

def _scoped_dirs():
    """(dirname, project, service) for every in-scope project dir: exact SCOPE names plus SCOPE_PREFIXES matches."""
    dirs = [(d, p, s) for d, (p, s) in SCOPE.items()]
    if os.path.isdir(PROJECTS_ROOT):
        for d in sorted(os.listdir(PROJECTS_ROOT)):
            for prefix, (p, s) in SCOPE_PREFIXES.items():
                if d.startswith(prefix):
                    dirs.append((d, p, s))
    return dirs


def collect():
    out = []
    for dirname, project, service in _scoped_dirs():
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
