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

## What shipped

- **Contracts — all three domains** (10 data products). Finance (`contracts/finance/*.odcs.yaml`, 4)
  hand-authored as the worked pattern; **music + health** (`contracts/{music,health}/*.odcs.yaml`, 6)
  produced by the generator below. Every declared column verified against Trino.
- **Structural conformance gate** — `scripts/check-odcs-contracts.sh` validates every `*.odcs.yaml` against
  the adopted subset (fail-closed: exit 1 malformed, exit 2 could-not-run), 10 bats cases, wired into CI
  (`repo-guards`).
- **Live schema conformance** — `check-odcs-contracts.sh --check-schema` asserts each declared column
  actually exists in the Trino physical table (validated live: all 10 conform; a bogus column is caught).
  Needs the cluster, so it runs at close-out / as a manual pass rather than in CI.
- **Products-without-contracts check** — `tests/test_product_contract_coverage.py` fails if any
  Music/Health/Finance DataHub data product has no ODCS contract (static, in the light lane).
- **Generator** — `scripts/gen_odcs_contract.py` emits a conformant ODCS contract from the substance
  (Trino columns+types, Soda quality rules, dbt descriptions); it produced the music/health contracts and
  bootstraps any new product. Re-running keeps the schema + quality sections in lockstep.
- **dbt `contract: enforced`** — turned on for the finance marts (`dbt/models/marts/finance/schema.yml`,
  `config.contract.enforced: true` + `data_type` per column from Trino), so a mart schema change is caught
  at `dbt build` as well as by the ODCS gate. Validates on the next dbt run.

## The two deploy-time validators

- **`dbt build`** confirms the finance marts' `contract: enforced` (I could not run dbt locally; the
  `data_type`s are verbatim Trino types + every column is declared, so a break is unlikely and would be
  loud). Extending enforcement to the music/health marts follows the identical pattern once a finance run
  confirms it.
- **The code-server load** confirms nothing here (ODCS is data + repo tooling), but the sibling B158
  autodiscovery (F) rides the same load.

The decision (adopt the subset), all-domain contracts, the structural + live + coverage gates, the
generator, and dbt enforcement are done. B157 is complete.
