#!/usr/bin/env python3
"""B253 (2026-11-20) — evaluate the Realm of Agents against simpler shapes of itself.

Three arms, all run by the deployed Realm's free-only `POST /eval/run` (the local lane, no fallbacks, no paid tools):
  realm   Gná routes and a lead delegates (the Realm as it is);
  routed  Gná routes and the chosen agent answers alone (routing without delegation);
  single  one agent holding every Realm tool, no routing (the control).
Tasks: services/weyland-dagster/weyland_pipeline/eval_sets/realm.json (each with the agents a correct router may pick and
a rubric). The judge is wl-judge-oss (gpt-oss:20b on rogueone, $0, a different model from the one judged), blind to the
arm, LiteLLM fallbacks off.

Modes (the wrapper scripts/realm-eval.sh drives them; runbook docs/runbooks/realm-of-agents.md § Evaluation (B253)):
  plan        local:      --tasks F --results F [--reps 3] [--limit N]  → JSONL of runs still to do (resumable)
  run         in-cluster: stdin plan JSONL → one result line per run (failures recorded, never dropped)
  judge-plan  local:      --tasks F --results F --scores F [--limit N]  → JSONL of blind judge inputs
  judge       in-cluster: stdin judge JSONL → one score line per answer
  report      local:      --tasks F --results F --scores F              → Markdown tables
In-cluster modes run in the dagster-user-code pod (the Realm's NetworkPolicy admits it; it holds LITELLM_* env).
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time

ARMS = ("realm", "routed", "single")
SEED = 253
REALM_URL = os.getenv("REALM_URL", "http://realm-of-agents.weyland.svc.cluster.local:8080")
RUN_TIMEOUT = float(os.getenv("REALM_EVAL_TIMEOUT", "900"))
JUDGE_MODEL = os.getenv("REALM_EVAL_JUDGE", "wl-judge-oss")


# --- shared ----------------------------------------------------------------------------------------------------------
def read_jsonl(stream) -> list:
    out = []
    for n, line in enumerate(stream, 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {n} is not JSON: {line[:80]}") from exc
    return out


def _read_file_jsonl(path: str) -> list:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return read_jsonl(fh)


def load_tasks(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        tasks = json.load(fh)["questions"]
    if not tasks:
        raise ValueError(f"no tasks in {path}")
    return tasks


def ref_of(task_id: str, arm: str, rep: int) -> str:
    """An opaque id for one run, so the judge's score maps back without the judge ever seeing the arm."""
    return hashlib.sha256(f"{task_id}|{arm}|{rep}".encode()).hexdigest()[:16]


def _order_key(*parts) -> str:
    """A fixed, seeded ordering (a hash, not a random generator): the same order on every run and every rerun."""
    return hashlib.sha256("|".join(map(str, (SEED, *parts))).encode()).hexdigest()


# --- plan ------------------------------------------------------------------------------------------------------------
def done_keys(lines) -> set:
    return {(r["id"], r["arm"], r["rep"]) for r in (json.loads(x) for x in lines if x.strip())}


def plan(tasks: list, done: set, arms=ARMS, reps: int = 3, limit: int | None = None) -> list:
    """Every (task, arm, rep) not yet done, rep by rep, task by task, with the arms in a seeded shuffle per task, so
    a slow period on the GPU lands on every arm alike and a rerun resumes exactly where it stopped."""
    out = []
    for rep in range(1, reps + 1):
        for t in tasks:
            for arm in sorted(arms, key=lambda a, r=rep, i=t["id"]: _order_key(r, i, a)):
                if (t["id"], arm, rep) not in done:
                    out.append({"id": t["id"], "arm": arm, "rep": rep, "q": t["q"], "kind": t["kind"]})
    return out[:limit] if limit else out


# --- run (in-cluster) ------------------------------------------------------------------------------------------------
def run_one(client, item: dict) -> dict:
    base = {"id": item["id"], "arm": item["arm"], "rep": item["rep"], "kind": item["kind"]}
    t0 = time.monotonic()
    try:
        resp = client.post("/eval/run", json={"task": item["q"], "arm": item["arm"]}, timeout=RUN_TIMEOUT)
    except Exception as exc:   # a timeout or a dropped connection is a failed run, recorded as one
        return {**base, "ok": False, "status": None, "error": f"{type(exc).__name__}: {exc}", "answer": "",
                "routed_to": None, "wall_seconds": round(time.monotonic() - t0, 2)}
    wall = round(time.monotonic() - t0, 2)
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = resp.text[:300]
        return {**base, "ok": False, "status": resp.status_code, "error": str(detail), "answer": "",
                "routed_to": None, "wall_seconds": wall}
    body = resp.json()
    rec = {**base, **{k: v for k, v in body.items() if k != "arm"}, "status": 200, "wall_seconds": wall}
    if not (body.get("answer") or "").strip():
        return {**rec, "ok": False, "error": "empty answer"}
    return {**rec, "ok": True}


def mode_run(stdin, stdout) -> int:
    import httpx
    items = read_jsonl(stdin)
    if not items:
        print("run: no items on stdin", file=sys.stderr)
        return 2
    with httpx.Client(base_url=REALM_URL) as client:
        for item in items:
            rec = run_one(client, item)
            stdout.write(json.dumps(rec) + "\n")
            stdout.flush()   # one line per run, so a dropped exec keeps every finished run
            print(f"run {item['id']} {item['arm']} rep{item['rep']}: {'ok' if rec['ok'] else 'FAIL'} "
                  f"{rec['wall_seconds']}s", file=sys.stderr, flush=True)
    return 0


# --- judge -----------------------------------------------------------------------------------------------------------
_JUDGE_SYSTEM = (
    "You grade one answer to one task against a rubric. For EACH rubric criterion, decide strictly whether the answer "
    "meets it (true) or not (false); a claim the answer makes without support does not meet a criterion that asks for "
    "real facts. Then give an overall score from 1 (useless) to 5 (fully correct and complete). Length is not quality. "
    'Reply with ONLY a JSON object: {"met": [true|false, ... one per criterion, in order], "score": 1-5, '
    '"reason": "one sentence"}.')


def judge_plan(tasks: list, results: list, scored: set, limit: int | None = None) -> list:
    """Blind judge inputs for every successful run not yet scored: the task, its rubric and the answer, tied back by an
    opaque ref. The arm, the agent and the measurements are left out on purpose. Seeded shuffle, so the judge does not
    see one arm's answers in a block."""
    by_id = {t["id"]: t for t in tasks}
    items = []
    for r in results:
        if not r.get("ok"):
            continue
        ref = ref_of(r["id"], r["arm"], r["rep"])
        if ref in scored:
            continue
        t = by_id[r["id"]]
        items.append({"ref": ref, "q": t["q"], "rubric": t["rubric"], "answer": r["answer"]})
    items.sort(key=lambda it: _order_key(it["ref"]))
    return items[:limit] if limit else items


def parse_verdict(text: str, n_criteria: int) -> dict:
    """The judge's JSON, fenced or bare. Anything malformed is an error, never a score."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in the verdict")
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"verdict is not JSON: {exc}") from exc
    met, score = v.get("met"), v.get("score")
    if not isinstance(met, list) or len(met) != n_criteria or not all(isinstance(x, bool) for x in met):
        raise ValueError(f"met must be {n_criteria} booleans, got {met!r}")
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
        raise ValueError(f"score must be 1-5, got {score!r}")
    return {"met": met, "score": score, "reason": str(v.get("reason", ""))[:300]}


def judge_one(client, item: dict, model: str = JUDGE_MODEL) -> dict:
    rubric = "\n".join(f"{i}. {c}" for i, c in enumerate(item["rubric"], 1))
    user = f"TASK:\n{item['q']}\n\nRUBRIC ({len(item['rubric'])} criteria):\n{rubric}\n\nANSWER:\n{item['answer']}"
    body = {"model": model, "temperature": 0, "disable_fallbacks": True,
            "messages": [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": user}]}
    try:
        resp = client.post("/chat/completions", json=body, timeout=600)
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return {"ref": item["ref"], "ok": True, **parse_verdict(text, len(item["rubric"]))}
    except Exception as exc:   # an unreachable judge or a bad verdict is a judge error, rerun later, never a score
        return {"ref": item["ref"], "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def mode_judge(stdin, stdout) -> int:
    import httpx
    items = read_jsonl(stdin)
    if not items:
        print("judge: no items on stdin", file=sys.stderr)
        return 2
    base = os.environ["LITELLM_BASE_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['LITELLM_API_KEY']}"}
    with httpx.Client(base_url=base if base.endswith("/v1") else base + "/v1", headers=headers) as client:
        for item in items:
            out = judge_one(client, item)
            stdout.write(json.dumps(out) + "\n")
            stdout.flush()
            print(f"judge {item['ref']}: {'ok' if out['ok'] else 'ERROR'}", file=sys.stderr, flush=True)
    return 0


# --- report ----------------------------------------------------------------------------------------------------------
def _mean(xs):
    return statistics.fmean(xs) if xs else None


def _sd(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def _score_run(r: dict, scores: dict, accept: list) -> tuple:
    """(rubric fraction, judge score or None, routed correctly or None) for one run. A failed run scores 0; a
    successful run with no valid score is an error (judge it first), never a silent 0."""
    if not r.get("ok"):
        return 0.0, None, None
    s = scores.get(ref_of(r["id"], r["arm"], r["rep"]))
    if not s or not s.get("ok"):
        raise ValueError(f"unjudged success: {r['id']} {r['arm']} rep{r['rep']} (run the judge first)")
    routed = (r["routed_to"] in accept) if r.get("routed_to") else None
    return sum(s["met"]) / len(s["met"]), s["score"], routed


def _arm_summary(rs: list, by_id: dict, scores: dict) -> dict:
    rubric, judge, by_kind, routed, misroutes = [], [], {}, [], []
    for r in rs:
        frac, score, good = _score_run(r, scores, by_id[r["id"]]["accept"])
        rubric.append(frac)
        by_kind.setdefault(by_id[r["id"]]["kind"], []).append(frac)
        if score is not None:
            judge.append(score)
        if good is not None:
            routed.append(good)
            if not good:
                misroutes.append((r["id"], r["routed_to"]))
    ok = [r for r in rs if r.get("ok")]
    return {
        "runs": len(rs), "failures": len(rs) - len(ok),
        "rubric_mean": _mean(rubric), "rubric_sd": _sd(rubric), "judge_mean": _mean(judge),
        "by_kind": {k: {"runs": len(v), "rubric_mean": _mean(v)} for k, v in sorted(by_kind.items())},
        "tokens_mean": _mean([r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in ok]),
        "seconds_mean": _mean([r["wall_seconds"] for r in ok]),
        "tool_calls_mean": _mean([r.get("tool_calls", 0) for r in ok]),
        "delegations_mean": _mean([r.get("delegations", 0) for r in ok]),
        "answer_chars_mean": _mean([len(r.get("answer") or "") for r in ok]),
        "routing_accuracy": _mean([1.0 if g else 0.0 for g in routed]),
        "misroutes": sorted(misroutes),
    }


def summarise(tasks: list, results: list, scores: dict) -> dict:
    """Per arm: rubric fraction (a failed run scores 0), judge score, tokens, latency, tool calls, delegations, and
    routing accuracy against each task's accept list. A successful run with no score stops the report: judge it first."""
    by_id = {t["id"]: t for t in tasks}
    return {arm: _arm_summary([r for r in results if r["arm"] == arm], by_id, scores)
            for arm in sorted({r["arm"] for r in results})}


def _f(x, fmt="{:.2f}"):
    return "n/a" if x is None else fmt.format(x)


def render(summary: dict) -> str:
    lines = ["| Arm | Runs | Failures | Rubric met (mean ± sd) | Single-realm | Multi-realm | Judge 1-5 | Tokens | "
             "Seconds | Tool calls | Delegations | Answer chars | Routing accuracy |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm, s in summary.items():
        k = s["by_kind"]
        lines.append(
            f"| {arm} | {s['runs']} | {s['failures']} | {_f(s['rubric_mean'])} ± {_f(s['rubric_sd'])} | "
            f"{_f(k.get('single', {}).get('rubric_mean'))} | {_f(k.get('multi', {}).get('rubric_mean'))} | "
            f"{_f(s['judge_mean'])} | {_f(s['tokens_mean'], '{:.0f}')} | {_f(s['seconds_mean'], '{:.0f}')} | "
            f"{_f(s['tool_calls_mean'], '{:.1f}')} | {_f(s['delegations_mean'], '{:.1f}')} | "
            f"{_f(s['answer_chars_mean'], '{:.0f}')} | {_f(s['routing_accuracy'])} |")
    for arm, s in summary.items():
        if s["misroutes"]:
            lines.append(f"\nMisroutes ({arm}): " + ", ".join(f"{t} → {a}" for t, a in s["misroutes"]))
    return "\n".join(lines) + "\n"


# --- CLI -------------------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("mode", choices=["plan", "run", "judge-plan", "judge", "report"])
    p.add_argument("--tasks")
    p.add_argument("--results")
    p.add_argument("--scores")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--limit", type=int)
    a = p.parse_args(argv)
    if a.mode == "run":
        return mode_run(sys.stdin, sys.stdout)
    if a.mode == "judge":
        return mode_judge(sys.stdin, sys.stdout)
    if not a.tasks:
        p.error(f"{a.mode} needs --tasks")
    tasks = load_tasks(a.tasks)
    results = _read_file_jsonl(a.results)
    if a.mode == "plan":
        for item in plan(tasks, {(r["id"], r["arm"], r["rep"]) for r in results}, reps=a.reps, limit=a.limit):
            print(json.dumps(item))
        return 0
    scores = {s["ref"]: s for s in _read_file_jsonl(a.scores) if s.get("ok")}
    if a.mode == "judge-plan":
        for item in judge_plan(tasks, results, set(scores), limit=a.limit):
            print(json.dumps(item))
        return 0
    if not results:
        print("report: no results", file=sys.stderr)
        return 2
    sys.stdout.write(render(summarise(tasks, results, scores)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
