# B14 read+act — MCP act-tools + shadow audit (design)

**Goal:** Turn on the tool-server's action routes as MCP tools for the B2 agents (Hermes first, OpenClaw
same URL), with every invocation recorded by the guardrail `act` hook in **shadow** (audit-only). This is
the "D" slice deferred by `b14-guardrails-design.md` — the read+act half of B14.

**Status of the other half:** the shadow guardrail *layer* (injection/toxicity/grounding on `/context/*`)
already shipped. This slice adds the `act` hook and the act-tool surface. Enforcement (the policy gate:
allowlist / rate-limit / `block`) is **deferred to the B35 pairing** — calibrate-and-enforce everything
(probabilistic grounding threshold + deterministic act policy) in one deliberate later pass.

---

## Scope

Expose the three existing, untagged action routes as MCP tools and audit each call:

- `POST /pipeline/trigger` — fire a Dagster job (`job_name`, already regex-validated; default `weyland_ingestion_job`)
- `POST /evals/run` — fire `weyland_eval_job`
- `POST /evals/score` — fire `weyland_eval_score_job`

These are low-risk, idempotent infra triggers on a single-user LAN — so this is a **learning + agent-prep**
slice, deliberately not production hardening (per the B14 framing).

### Non-goals (explicitly deferred)
- **Enforcement / blocking, allowlist, rate-limit** → B35 pairing (the policy gate).
- **Authentication, verified caller identity** → B17+B19 (MCP gateway).
- **Client-supplied identity** → never (anti-spoofing decision; see the `actor` seam).
- **Confirmation / human-in-the-loop** → not needed for these tools; revisit only if agents start firing
  surprising things.

---

## Architecture

### 1. MCP act surface — a separate `/mcp-act` mount (the governable boundary)

Stand up a **second `FastApiMCP` instance** for the act tools rather than mixing them into the read server:

- Read tools stay on `/mcp` (`include_tags=["mcp"]`) — unchanged.
- Act tools get tag `"mcp-act"` and are exposed by a second instance mounted at **`/mcp-act`**
  (`include_tags=["mcp-act"]`).

Why a separate mount, not just a second tag on one server:
- **Independently governable** — the gateway (B17+B19) later fronts *only* `/mcp-act` with auth/policy while
  `/mcp` stays open. A single mixed server would force the gateway to filter by tool name.
- **Opt-in to act** — agents must *explicitly register* the `/mcp-act` URL to gain action tools; read access
  never implies act access. Read and act are separately granted.

**Implementation assumption to verify first:** two `FastApiMCP` instances on one FastAPI app, mounted at
different paths. If `fastapi-mcp` does not cleanly support that, fall back to one server with the act routes
on an `mcp-act` tag plus a tool-name convention — the `actor`/audit design below is unaffected either way.

### 2. The `act` hook + `policy.audit` validator

A new shadow validator `policy.audit` runs on `Hook.ACT`. It **always returns `PASS`** and exists purely to
record the action — reusing the existing pipeline → metrics → `guardrail_verdicts` machinery, so act audits
appear in Prometheus and Postgres exactly like the read verdicts.

Each act route, before firing its Dagster job, calls:

```
GUARDRAILS.run(Hook.ACT, request_id, {"tool": "<route>", "params": {...}, "actor": <actor>})
```

The verdict's `reason` captures the action, e.g. `"trigger weyland_ingestion_job"`. Config:

```
Hook.ACT: [("policy.audit", Mode.SHADOW)]
```

Because the chain is shadow-only, `run()` fire-and-forgets the audit (zero added response latency) and the
action always proceeds — this slice never blocks.

### 3. The `actor` seam (forward-compatible, no theater)

Add **one nullable column**: `ALTER TABLE guardrail_verdicts ADD COLUMN actor TEXT`. It is populated on
**every** verdict (read *and* act) from a **trusted gateway header only** — `X-Forwarded-Consumer` (the
header APISIX/the future gateway injects after authenticating a consumer) — and is `NULL` when the header is
absent. Today it is always `NULL`.

The tool-server **never** reads a client-supplied actor claim. Identity flows in as a trusted upstream
assertion or not at all. The moment the gateway fronts the surface, verified identity lands in the same
column with zero code rework.

---

## Data

Reuses `guardrail_verdicts` (one additive column):

| column | act-hook value |
|---|---|
| `hook` | `act` |
| `validator` | `policy.audit` |
| `mode` | `shadow` |
| `decision` | `pass` |
| `score` | `NULL` |
| `reason` | action description (e.g. `trigger weyland_ingestion_job`) |
| `actor` | **(new)** trusted-header identity, `NULL` until the gateway lands |

---

## Testing (existing mock-based style)

- `policy.audit` returns a `PASS` verdict whose `reason` captures the tool+params.
- `Hook.ACT` config chain resolves to `[(policy.audit, shadow)]`.
- `actor` resolves from a trusted header when present, and is `None` when absent.
- Route wiring fires the `act` hook on each of the three tools (and the action still proceeds in shadow).

---

## Gateway handoff (B17+B19)

The full "what this slice left for the gateway to build on" lives **directly in the B17+B19 roadmap block**
in `aidlc-docs/backlog.md` — not duplicated here. It enumerates: the `/mcp-act` mount to front, the
`X-Forwarded-Consumer` → `actor` trusted-header convention, the shadow `act` hook awaiting an enforcing
policy validator (built with B35), and the "no client-supplied identity" decision — with references to the
implementing files. Keeping it in B17+B19 means the gateway work reads its own prerequisites in place.
