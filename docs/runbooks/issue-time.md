# Time per Linear issue — agent session time, lead and cycle time (B185 lane 1)

How long did an issue take? The owner rarely touches an issue by hand — the agents do the work — so lane 1 measures
**agent time**: the Claude Code session logs on rogueone, attributed to the issue the session was working on, joined
with Linear's own dates for **lead time** and **cycle time**. Lane 2 (owner time via ActivityWatch) is a separate,
later trial (`docs/backlog.md` B185, Linear EMA-243).

| Piece | Where |
|---|---|
| Producer (attribution) | `nodes/mother/lab/weyland-platform/scripts/ai_session_feeder.py` — the B62 producer; writes `issues{}` into each session summary |
| Report | `nodes/mother/lab/weyland-platform/scripts/issue_time_report.py` |
| Session summaries | `~/.cache/ai-sessions/*.json` on rogueone, mirrored to MinIO `ai-sessions/` by `ai-session-producer.timer` (every 4 h at :07) |
| Linear dates | the B194 nightly snapshot, `weyland/linear-backup/snapshots/<ts>/issues.json.gz` ([linear-backup.md](linear-backup.md)) |
| Tests | `nodes/mother/lab/weyland-platform/scripts/tests/test_ai_session_feeder.py`, `test_issue_time_report.py` (CI `test-python`) |
| Flow | [flow-issue-time-attribution.md](../diagrams/flow-issue-time-attribution.md) |

All commands run on **rogueone**. Nothing leaves rogueone but issue ids and numbers — never prompt text.

## Report time per issue

```
mc cp -q "weyland/linear-backup/snapshots/$(mc ls weyland/linear-backup/snapshots/ | tail -1 | awk '{print $NF}')issues.json.gz" /home/edwardmangini/.cache/linear-issues.json.gz && python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/issue_time_report.py --sessions /home/edwardmangini/.cache/ai-sessions --issues /home/edwardmangini/.cache/linear-issues.json.gz
```

One row per Linear issue, most agent time first: `agent_h` (active main-thread hours), `sessions`, `lead_d`
(completedAt − createdAt), `cycle_d` (completedAt − the earlier of Linear's startedAt and the first agent activity),
`out_tok` (output tokens, subagents included). `-` = not known (open issue, or no start known before completion).
`--json` prints the rows as JSON (adds `api_equiv_usd`, `first_agent_at`, `unmapped`).

Exit codes: **0** report printed · **2** an input is absent or unreadable (no session summaries, a summary that is not
JSON, no summary carrying attribution, a snapshot that is not gzip/JSON or holds no issues) — never an empty report.

To refresh the summaries first (the timer does this every 4 h):
```
systemctl --user start ai-session-producer.service
```

## How a minute is attributed

Walking each session in order, an issue becomes **current** on exactly three markers; the time and tokens after it
belong to it until the next marker:

| Marker | Switches when | Why |
|---|---|---|
| A human prompt | it names exactly ONE id (`EMA-###` or `B###`/`B###.#`) | two ids ("compare B179 with B204") are ambiguous |
| The session title (`custom-title`) | it CHANGES and names one id | it is re-logged nearly every turn; a repeat must not pull time back |
| An `issue-readiness.sh EMA-###` tool call | nothing is current yet | how a conveyor run names its issue; in an attended session it is a queue check, not a switch |

Never markers: tool results, assistant text, injected notices (`<task-notification>`, `<system-reminder>`). They quote
issues constantly — 9,723 + 2,926 mentions in one session against 616 in its prompts.

- **Active time** = gaps of at most 300 s between main-thread events; a longer gap is idle, counted nowhere.
- **Subagents** (`<session>/subagents/agent-*.jsonl`): their tokens go to the issue current when they started; their
  time overlaps the parent's and is not added.
- Activity before any issue is named is **unattributed** (1.8 % of active time on 2026-10-12).
- A B number maps to its Linear issue by title prefix (`B179 — …` → EMA-237). Two issues with one number: the
  unarchived one wins; still two → shown under the B number, flagged `(unmapped)`, never guessed.

## Limits — read before trusting a number

- **Sticky attribution.** Time stays on an issue until a prompt names another. A long, broad item (B119, a 5-day
  Linear walk-through) collects everything said in between. Name the issue when switching work.
- **Coverage.** Claude Code prunes transcripts after ~30 days; summaries in `~/.cache/ai-sessions` outlive them but
  only those written since 2026-10-12 carry `issues{}`. `first_agent_at` is the first activity still on record.
- **Rework after close.** Agent activity that begins after `completedAt` (a closed item named again) is agent time but
  never starts the cycle.
- **Linear `startedAt`** is null on 241 of 292 issues, so most cycle times start at the first agent activity.

## Token counts corrected 2026-10-12 (B62)

Claude Code logs one record per content block, each repeating the message's full `usage`. The feeder summed records,
overstating tokens and API-equivalent $ about 2.7x (7,836 records for 3,146 messages in one session). Summaries now
count each message once and carry `"usage_counted": "per-message"`; a summary WITHOUT that field predates the fix,
its transcript is gone, and its token and $ numbers are high. Subagent tokens, previously not counted at all, are now
in the totals (`subagents` = how many).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| exit 2 `no session in … carries per-issue attribution` | Summaries predate B185: run `systemctl --user start ai-session-producer.service` |
| exit 2 `cannot read Linear snapshot` | The `mc cp` failed or copied a partial file — re-run it; check the snapshot with [linear-backup.md](linear-backup.md) |
| An issue's hours look far too high | Sticky attribution (above): check the session's prompts named the next issue when work moved on |
| A B number shows `(unmapped)` | Two live Linear issues share the number — fix the duplicate title in Linear |
