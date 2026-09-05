# Data contracts on the mesh — ODCS adoption decision (B157)

**Decision: adopt the Open Data Contract Standard (ODCS, Bitol / Linux Foundation) v3 as the canonical,
declarative shape for the mesh's data contracts — a justified lab SUBSET, not the full enterprise spec —
with a CI conformance gate.** This is the B157 evaluation and its outcome; it is also follow-up **E** of the
B158 self-serve-planes audit, which found the mesh had contract *substance* everywhere and a contract
*standard* nowhere.

## The problem ODCS solves here

The mesh already carried contract-ish material, but scattered across four surfaces, none of them the
contract:

- **dbt** `schema.yml` — column descriptions + `unique`/`not_null` tests (but no `contract: enforced`).
- **Soda** `checks/*.yml` — row-count, null, duplicate, freshness DQ rules.
- **DataHub** `DataContract` entities — `emit_data_contracts` bundles the Soda/GE/asset-check assertions per
  dataset at runtime.
- **DomainConfig** — owner, domain, the stores a dataset fans out to.

Nothing expressed a dataset's contract *as one declarative artifact*, and nothing *failed* when a contract
was incomplete. A consumer had to read four places to learn what a product guarantees.

## Why ODCS, and why a subset

ODCS is the emerging open standard (Bitol, under the Linux Foundation) for exactly this — one YAML file per
contract carrying fundamentals, schema (logical + physical), quality, SLAs, team, and support. Adopting the
*standard* (rather than inventing a bespoke shape) means the contracts are portable and tool-friendly.

The full v3 spec is broad (servers, roles with granular access, pricing, SLA micro-properties,
custom-property namespaces). A $0 single-node lab does not need pricing or fine-grained access tiers. So we
adopt a **subset** — the fields that make a contract *usable and governable here* — and leave the rest
available (ODCS is extensible; unused sections are simply absent).

### The adopted subset (what every `*.odcs.yaml` must carry)

| Section | Fields | Sourced from |
|---|---|---|
| **Fundamentals** | `apiVersion: v3.x` · `kind: DataContract` · `id` (unique) · `name` · `version` (semver) · `status` · `domain` · `dataProduct` · `tenant` | DomainConfig + the DataHub product taxonomy |
| **description** | `purpose` (required) · `usage` · `limitations` | dbt model descriptions + domain knowledge |
| **servers** | ≥1 physical location (trino catalog/schema/table) | Trino / the storage grid |
| **schema** | per table: `physicalName` + `properties[]`, each with `name` + `logicalType` (+ `physicalType`, `description`, `required`, `unique`) | Trino physical schema + dbt column docs |
| **quality** | the DQ rules (`unique`, `not_null`, `missing_percent < 100`, `duplicate_count = 0`, `row_count > 0`) | Soda checks + dbt tests |
| **slaProperties** | `frequency`, `retention` | the land schedule + lakeFS/Nessie versioning |
| **team** | ≥1 member with `role: owner` | DomainConfig owner |
| **support** | a runbook link | the demo/runbook |

### Relationship to the DataHub DataContract

ODCS is the **declarative source of truth** an author writes; the DataHub `DataContract` (via
`emit_data_contracts`) is the **runtime mirror** that shows the same guarantees in the catalog, bundling the
live assertion results. ODCS says *what is promised*; DataHub shows *whether it currently holds*. They are
complementary, not redundant — this adoption does not remove the DataHub contracts.

## What shipped (this increment)

- **Contracts** — the finance domain, the B158 live-test domain, fully expressed as ODCS:
  `contracts/finance/{macro_indicators,company_financials,market_prices,sec_filings}.odcs.yaml`
  (one per data product), mapped from the real substance above; declared columns verified against Trino.
- **Conformance gate** — `scripts/check-odcs-contracts.sh` validates every `*.odcs.yaml` against the adopted
  subset (fail-closed: exit 1 malformed, exit 2 could-not-run), 10 bats cases, wired into CI (`repo-guards`).

## Deliberately deferred (tracked, not silent)

- **The other domains** (music, health) — their contracts migrate the same way; finance is the worked
  pattern. *(Follow-on.)*
- **Live schema conformance** — a pass that asserts each declared column actually exists in Trino (the
  structural gate does not; the finance columns were hand-verified against Trino at authoring). *(Follow-on.)*
- **dbt `contract: enforced`** — turning the dbt models' own contract enforcement on, so a mart schema change
  is caught at build as well as by the ODCS gate. *(Follow-on.)*
- **Generating ODCS from the substance** — the contracts are hand-authored today; a generator from dbt
  `schema.yml` + Soda + DomainConfig would keep them in lockstep automatically. *(Follow-on.)*

These are the natural B157 continuation; the decision (adopt the subset), the worked contracts, and the gate
are done.
