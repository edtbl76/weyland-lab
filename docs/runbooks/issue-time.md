# Time per Linear issue — agent time, owner time, lead and cycle time (B185)

How long did an issue take? The owner rarely touches an issue by hand — the agents do the work — so lane 1 measures
**agent time**: the Claude Code session logs on rogueone, attributed to the issue the session was working on, joined
with Linear's own dates for **lead time** and **cycle time**. **Lane 2** (2026-10-15) adds the owner's own time per
issue from two sources: **ActivityWatch** (automatic: the Linear tab or window in front of you) and **Clockify** (a
manual timer button on every Linear issue, for when you want an explicit count). See § Owner time.

| Piece | Where |
|---|---|
| Producer (attribution) | `nodes/mother/lab/weyland-platform/scripts/ai_session_feeder.py` — the B62 producer; writes `issues{}` into each session summary |
| Report | `scripts/issue-time.sh` (the command) → `nodes/mother/lab/weyland-platform/scripts/issue_time_report.py` (logic) |
| Port view | blueprint `tofu/port/issue_time.tf` · dashboard `tofu/port/pages/time_per_issue.json` · entities pushed by `issue-time.sh --port` |
| Session summaries | `~/.cache/ai-sessions/*.json` on rogueone, mirrored to MinIO `ai-sessions/` by `ai-session-producer.timer` (every 4 h at :07) |
| Linear dates | the B194 nightly snapshot, `weyland/linear-backup/snapshots/<ts>/issues.json.gz` ([linear-backup.md](linear-backup.md)) |
| Tests | `nodes/mother/lab/weyland-platform/scripts/tests/test_ai_session_feeder.py`, `test_issue_time_report.py` (CI `test-python`) · `scripts/tests/issue-time.bats` (CI `test-shell`) |
| Owner time (lane 2) | `nodes/mother/lab/weyland-platform/scripts/owner_time.py` → `~/.cache/owner-time/owner_time.json` (+ `aw-day-*.json`, `resources.jsonl`); tests `test_owner_time.py` |
| ActivityWatch | v0.14.1 in `~/.local/opt/activitywatch-v0.14.1`, user units `nodes/rogueone/systemd/aw-{server,watcher-window,watcher-afk}.service`, **127.0.0.1:5600 only**; the Chrome extension *ActivityWatch Web Watcher* |
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
`out_tok` (output tokens, subagents included), `own_aw_h` and `own_clk_h` (the owner's own hours from ActivityWatch and
Clockify, § Owner time). `-` = not known (open issue, no start known before completion, or an owner source not
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
It prints one line, e.g. `owner_time: 1 issue(s); ActivityWatch 2 day(s), Clockify ok; trial CPU 0.78% of a core, RSS
73.5 MB`, and writes `~/.cache/owner-time/owner_time.json`. Exit **0** written · **2** a source could not be read
(ActivityWatch down, a Clockify API error, a malformed result): nothing is written, so the last true file stays.

**How a minute is counted** (ActivityWatch, through its own query language, so idle and duplicate time is AW's call):
- **A Linear tab** counts toward the id in its URL (`/issue/EMA-243`). Its title carries the EMA id *and* the backlog
  number (`EMA-243 B185 — …`), so reading the title would count the same minute twice.
- **Another window or tab** (IDE, terminal, GitHub) counts toward its title's single EMA id, else its single B number,
  else nothing. Two ids in one title = unattributed (never guessed).
- **Browser time counts only while Chrome is the active window**, and every minute is intersected with *not AFK*.
- Each day is computed into `aw-day-YYYY-MM-DD.json`; the totals sum every day file, so a run recomputes only the last
  2 days. To rebuild after losing `~/.cache/owner-time` (the AW database is restic-backed):
  `owner_time.py --env-file … --days 60`.

**Clockify** — open a Linear issue, press the Clockify button beside its status, stop it when done. The entry is named
`[EMA-###] <title>` and counts once finished (a running timer is reported, not counted). A hand-typed entry counts when
it names one issue (`B185 review`). The free API allows 30 requests/hour; a run uses about 2.

**The trial's kill criteria** (EMA-243): more than **1% CPU** (average since start, of one core) or more than
**150 MB resident memory** across the three `aw-*` units, measured over a week. Every run appends a sample to
`~/.cache/owner-time/resources.jsonl` and prints `OVER BUDGET: …` if either is broken. The week's verdict:
```
python3 -c "import json; r=[json.loads(l) for l in open('/home/edwardmangini/.cache/owner-time/resources.jsonl')]; print(len(r),'samples · max CPU % of a core', max(x['cpu_pct_of_one_core'] for x in r), '· max RSS MB', max(x['rss_mb'] for x in r), '· over budget', sum(1 for x in r if x['over_budget']))"
```
Kill it (if a criterion fails): `systemctl --user disable --now aw-watcher-window aw-watcher-afk aw-server`, then remove
the three units and their `placement.yaml` rows in one change.

**Restore drill** (the AW database is in the nightly restic set; a live SQLite file never diffs equal, so check it
opens and matches instead):
```
set -a; . /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/backup/.env; set +a; T=$(mktemp -d); restic restore latest --target "$T" --include "$HOME/.local/share/activitywatch" && python3 -c "import sqlite3,sys; f=lambda p: sqlite3.connect('file:'+p+'?mode=ro',uri=True); r=f(sys.argv[1]); l=f(sys.argv[2]); q='SELECT name FROM buckets ORDER BY name'; ok=r.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and r.execute(q).fetchall()==l.execute(q).fetchall(); print('RESTORE OK' if ok else 'RESTORE MISMATCH')" "$T$HOME/.local/share/activitywatch/aw-server-rust/sqlite.db" "$HOME/.local/share/activitywatch/aw-server-rust/sqlite.db"; rm -rf "$T"
```

**Check the services:**
```
systemctl --user is-active aw-server aw-watcher-window aw-watcher-afk && curl -s http://127.0.0.1:5600/api/0/buckets/ | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)))"
```
Expect three `active` lines and three buckets: `aw-watcher-afk_rogueone`, `aw-watcher-web-chrome_rogueone`,
`aw-watcher-window_rogueone`. No `aw-watcher-web-chrome_*` bucket = the Chrome extension
isn't installed or can't reach the server.

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
