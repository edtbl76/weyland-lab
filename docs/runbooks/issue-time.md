# Time per Linear issue — agent time, owner time, lead and cycle time (B185)

How long did an issue take? The owner rarely touches an issue by hand — the agents do the work — so lane 1 measures
**agent time**: the Claude Code session logs on rogueone, attributed to the issue the session was working on, joined
with Linear's own dates for **lead time** and **cycle time**. **Lane 2** (2026-10-15) adds the owner's own time per
issue from **Clockify** (a manual timer button on every Linear issue). Its automatic half, **ActivityWatch**, was
retired on 2026-10-23 after failing its memory trial. See § Owner time. Lane 1 attributes
per harness from the session logs, so it does not need Bifrost 2.3's per-app metrics label (B212: that label stayed
`app=""` in testing and was not verified; [concepts/bifrost-2-3-evaluation.md](../concepts/bifrost-2-3-evaluation.md)).

| Piece | Where |
|---|---|
| Producer (attribution) | `nodes/mother/lab/weyland-platform/scripts/ai_session_feeder.py` — the B62 producer; writes `issues{}` into each session summary |
| Report | `scripts/issue-time.sh` (the command) → `nodes/mother/lab/weyland-platform/scripts/issue_time_report.py` (logic) |
| Port view | blueprint `tofu/port/issue_time.tf` · dashboard `tofu/port/pages/time_per_issue.json` · entities pushed by `issue-time.sh --port` |
| Session summaries | `~/.cache/ai-sessions/*.json` on rogueone, mirrored to MinIO `ai-sessions/` by `ai-session-producer.timer` (every 4 h at :07) |
| Linear dates | the B194 nightly snapshot, `weyland/linear-backup/snapshots/<ts>/issues.json.gz` ([linear-backup.md](linear-backup.md)) |
| Tests | `nodes/mother/lab/weyland-platform/scripts/tests/test_ai_session_feeder.py`, `test_issue_time_report.py` (CI `test-python`) · `scripts/tests/issue-time.bats` (CI `test-shell`) |
| Owner time (lane 2) | `nodes/mother/lab/weyland-platform/scripts/owner_time.py` → `~/.cache/owner-time/owner_time.json`; tests `test_owner_time.py` |
| ActivityWatch | **retired 2026-10-23** — failed its trial on memory (below); units and binaries removed, its 16 MB database kept in `~/.local/share/activitywatch` (restic-backed) |
| Clockify | free plan; the Chrome extension *Clockify Time Tracker* (timer on Linear issues); `CLOCKIFY_API_KEY` in `scripts/.env` |
| Flow | [flow-issue-time-attribution.md](../diagrams/flow-issue-time-attribution.md) |

All commands run on **rogueone**. Nothing leaves rogueone but issue ids and numbers — never prompt text, window titles,
URLs or Clockify entry text.

## Report time per issue

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-time.sh
```

`scripts/issue-time.sh` fetches the newest B194 Linear snapshot (`issues.json.gz` + `workflowStates.json.gz`) into
`~/.cache` and prints one row
per Linear issue, most agent time first: `agent_h` (active main-thread hours), `sessions`, `lead_d`
(completedAt − createdAt), `cycle_d` (completedAt − the earlier of the Linear start and the first agent activity; the
Linear start is the one the B194 dbt mart `mart_linear_issue_cycle_time` uses: `startedAt`, else the first history move
into a started-type state, read from the same snapshot's `workflowStates.json.gz`),
`out_tok` (output tokens, subagents included), `own_aw_h` and `own_clk_h` (the owner's own hours from ActivityWatch — always `-`
since it was retired — and Clockify, § Owner time). `-` = not known (open issue, no start known before completion, or an owner source not
collected — never shown as 0).

| Option | Does |
|---|---|
| (none) | the table |
| `--json` | the same rows as JSON (adds `api_equiv_usd`, `first_agent_at`, `unmapped`) |
| `--port` | push to Port: one `issue_time` entity per issue, every one read back, entities no longer in the report deleted, and the **Time per Issue** dashboard upserted from git. Reads `tofu/port/.env`. |

Exit codes: **0** ok · **1** `--port` read-back did not match what was written · **2** could not run — no snapshot
listed, the fetch failed, no Port credentials, no or unreadable session summaries, an unreadable snapshot, or a Port API
error. Never an empty report.

To refresh the summaries first (the timer does this every 4 h, and then runs `--port` itself):
```
systemctl --user start ai-session-producer.service
```

## View it in Port

**Port → Catalog sidebar → Time per Issue** (`https://app.port.io`, dashboard `time_per_issue`):
- **Agent hours (all issues)** · **Issues with agent time** · **Average cycle time (days)** (issues with a cycle time).
- **Time per issue** — a table of `issue_time` entities sorted by agent hours. Each row's `Linear issue` relation
  opens the issue's own `linearIssue` page, which lists its time under related entities.

How it is built:
- **Blueprint** `issue_time` — OpenTofu, `nodes/mother/lab/weyland-platform/tofu/port/issue_time.tf`. The time lives
  BESIDE the Linear integration's `linearIssue`, related to it, not on it: `linearIssue` is integration-owned and the
  integration revises it on upgrade ([port.md](port.md) § What is deliberately UI-managed).
- **Entities** — written by `issue-time.sh --port`, run by `ai-session-producer.service` after the MinIO mirror (every
  4 h). A failure fails the unit, which the nightly `machine-inv-drift` placement check turns into a Kuma alert.
- **Dashboard** — `tofu/port/pages/time_per_issue.json`, upserted on every push. Unlike the MCP-built dashboards it is
  in git, so it rebuilds itself. Edit the JSON, not the page in the UI: the next push overwrites UI edits.
- An issue with no `linearIssue` in Port (the integration did not sync it — EMA-206, 2026-10-13) keeps its time,
  without the relation; the push names it (`N without a linearIssue in Port`).

## Owner time (lane 2)

**Collect it now** (the producer timer does this every 4 h before `--port`):
```
python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/owner_time.py --env-file /home/edwardmangini/IdeaProjects/weyland/scripts/.env
```
It prints one line, e.g. `owner_time: 1 issue(s); Clockify ok; ActivityWatch retired`, and writes
`~/.cache/owner-time/owner_time.json`. Exit **0** written · **2** Clockify could not be read (an API error, a malformed
result, an unreadable env file): nothing is written, so the last true file stays.

**Clockify** — open a Linear issue, press the Clockify button beside its status, stop it when done. The entry is named
`[EMA-###] <title>` and counts once finished (a running timer is reported, not counted). A hand-typed entry counts when
it names one issue (`B185 review`). The free API allows 30 requests/hour; a run uses about 2.

**ActivityWatch — retired 2026-10-23 (the trial's verdict).** The automatic half of lane 2 ran as three user units for a
week against kill criteria set up front: more than 1% CPU (average, of one core) or more than 150 MB resident memory
across the three units. CPU passed (0.39% average, 0.79% peak). Memory failed: 27 of 53 samples over budget, peaking at
**180 MB**, and it grew with uptime (74 → 127 MB over 3.5 days, then 160 → 180 MB after a restart) rather than settling.
It attributed about 6.5 hours in 10 days, and its loose id matcher also counted non-issues (`UTF-8`, `M1-1`,
`S-1006409602`). The owner killed it: `systemctl --user disable --now aw-watcher-window aw-watcher-afk aw-server`, the
three units (repo and installed copies) and their `placement.yaml` rows removed, `~/.local/opt/activitywatch-v0.14.1`
deleted, the Chrome extension left to the owner. `owner_time.py` no longer contacts it and records it as
`{"status": "retired"}`, so the report shows its column as unknown, never zero. The database stays in
`~/.local/share/activitywatch` (16 MB, still in the restic set) in case the history is ever wanted; nothing reads it.

## Other options for owner time (2026-10-23)

ActivityWatch is retired and Clockify is barely used, so the owner's own time per issue has no working source. The
options, compared when B185 closed; evaluating them is **B235** (EMA-323, a spike that builds whatever it keeps):

| Option | How it counts | Cost and fit |
|---|---|---|
| **Wakapi** (self-hosted, WakaTime-compatible) | automatic, from IntelliJ's WakaTime plugin: coding time per project and per branch — a branch carrying the issue id attributes with no clicks | free, open source, one Go service; sees only IDE time, not Linear or browser reading |
| WakaTime (hosted) | the same plugin data | free tier keeps 2 weeks of history and is cloud; Wakapi is its $0 local equivalent |
| **Clockify** (wired today) | manual: the timer button on each Linear issue | free and working, but only counts when pressed (0.4 minutes in 10 days) |
| **Derive it, no tracker** | from Linear status changes (B194 snapshot) plus commit/PR times per issue | free, zero overhead; coarse — elapsed time, not hands-on time |
| Harvest / Everhour / Traqq / Toggl | manual timers | same limit as Clockify; Toggl has no Linear integration |
| solidtime / Kimai | self-hosted manual timers | a service to run for no gain over Clockify |
| Rize / Reclaim | automatic | paid — out under $0 |
| ActivityWatch | automatic, window and tab focus | **killed 2026-10-23** — failed its memory budget (§ Owner time) |

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
- **Linear `startedAt`** is null on 241 of 292 issues; the first history move into a started-type state fills 4 of
  them (the mart's rule), and most of the rest start at the first agent activity.

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
| exit 2 `cannot read Linear snapshot` / `could not fetch` | The snapshot copy failed or is partial — re-run; check the snapshot with [linear-backup.md](linear-backup.md) |
| exit 1 `read-back:` lines | Port stored something other than what was written — the named entity and property; re-run `--port`, then check the blueprint in `issue_time.tf` |
| `ai-session-producer.service` failed | `journalctl --user -u ai-session-producer` — the last command is the Port push; run `bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-time.sh --port` to see why |
| An issue's hours look far too high | Sticky attribution (above): check the session's prompts named the next issue when work moved on |
| A B number shows `(unmapped)` | Two live Linear issues share the number — fix the duplicate title in Linear |
