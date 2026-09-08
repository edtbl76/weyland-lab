# API lifecycle management (B155)

The estate had a human API inventory ([api.md](../api.md)) but no *governance*: nothing said who owns an
API, what version it is, whether it is published / deprecated / retired, and nothing caught a breaking
change. B12 (a static API registry) was cancelled for exactly that gap — the lifecycle framing is what it
lacked. This is that governance, across the whole lifecycle **design → published → deprecated → retired**.

## The pieces

| Piece | What it is |
|---|---|
| **Catalog** — `apis.yaml` | The machine-readable source of truth (sibling to `applications.yaml`). Each API declares `owner` (a real service), `kind`, `status`, `version`, `base`, `consumers`, and — for a typed contract — a captured `spec` snapshot + a live `spec_source`. |
| **Contract snapshots** — `docs/api/specs/` | The committed baseline of each typed contract: 5 FastAPI OpenAPI specs (tool-server / guard / agent / operator / realm-http) + the realm A2A agent card, captured live and normalized. |
| **Breaking-change engine** — `scripts/lib/api_spec_diff.py` | Diffs two specs and classifies every change **BREAKING** or **COMPATIBLE** by consumer-compatibility rules (removed operation/response-field/enum-value, new required field = breaking; additive = compatible). Handles OpenAPI 3.x + A2A cards; unknown/mismatched kinds are *cannot-compare*, never a silent pass. |
| **Lifecycle guard** — `check-api-lifecycle.sh` (repo-guards, CI) | Governs the catalog at PR time: every API declares owner (resolving) + kind + status + version; a published typed API carries a snapshot; a deprecated API declares `retire_by` + `successor`; a retired API has no consumers; and the **contract lock is current**. |
| **Contract lock** — `docs/api/specs/contract-lock.json` + `gen-api-contract-lock.sh` | The **PR-time breaking-change enforcement**. The lock records each snapshot-backed API's approved baseline + version. The guard fails if a snapshot changed vs its lock; re-locking (`gen-api-contract-lock.sh`) diffs current-vs-baseline with the engine and **REFUSES a breaking change unless the major version was bumped**. Git-independent (the baseline lives in the lock), so a breaking change cannot ship without a deliberate major bump. |
| **Drift cron** — `api-drift` (03:20, ns monitoring) | The runtime half: fetches each API's live spec and diffs it against the committed snapshot with the engine. Catches a deployed API that drifted from its governed contract without the catalog/snapshot/version being updated. Unreachable sources are skipped; a breaking diff fails the Job → Telegram. |

## Versioning policy

- **`version` is a governed semver the team maintains** (not necessarily the framework's `info.version`,
  which FastAPI leaves at a default). It is the number consumers reason about.
- **A breaking change to a published API requires a MAJOR bump — enforced at PR time.** "Breaking" is
  what `api_spec_diff.py` classifies: a removed operation, a removed response field, a removed enum value,
  a newly-required request field. When you re-capture a snapshot, `gen-api-contract-lock.sh` diffs it
  against the locked baseline and **refuses to re-lock a breaking change unless the major version bumped**;
  the CI guard fails until the lock is current. So the enforcement is not just nightly (drift cron) — it
  is a merge gate.
- **Additive changes** (a new optional field, a new operation, a new response field) are compatible and
  need only a MINOR/PATCH bump.
- Changing an API's contract is a three-step move: **re-capture the snapshot → bump the version →
  migrate consumers** (or revert). The drift cron fails until the snapshot matches the deployed reality.

## Deprecation & retirement policy

- **`status: deprecated`** must carry `deprecation.retire_by` (a date) and `deprecation.successor` (the
  API id consumers should move to). The guard enforces both, and that the successor is a real API.
- **`status: retired`** must have **no `consumers`** — nothing may still call a retired API. Migrate
  consumers off it (updating their `apis.yaml` consumer lists) before flipping it to retired.
- A retired API's entry stays in the catalog as the record; its snapshot stays as the historical contract.

## Consumer / producer visibility

Each API lists its `consumers`; each is owned by one service (`owner`). Together with the snapshots this
answers *who calls this, and what exactly does it promise* — the visibility B12 never had. (The reverse
index — every service's APIs — is `--list` on the guard.)

## Honest scope

- **Typed contracts are captured; protocol/opaque ones are catalogued but not snapshotted.** The 5
  FastAPI services + the realm A2A card have machine-readable specs, so they get snapshots + drift
  detection. The MCP surfaces (`mcp-gateway`, `mcp-fleet`) and OpenAI-shape gateways (`bifrost`,
  `litellm`, `ollama`, `whisper`) are catalogued with owner/version/status but carry no snapshot —
  capturing an MCP `tools/list` schema is a lifecycle follow-on. The guard only *requires* a snapshot
  for a published **openapi/a2a** API, so this is explicit, not a silent gap.
- **The breaking-change engine is operation- and shallow-schema-level**, not a full semantic OpenAPI
  validator — it catches the changes that actually break the estate's consumers (a removed route, a new
  required field, a dropped response field). What it cannot compare, it says so.
- Contract *tests* (B152) are the other enforcement arm: a contract test asserts a consumer/provider
  agree on a seam; this asserts the published contract itself doesn't change incompatibly.
