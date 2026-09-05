# Flow — ODCS data contracts (B157): one standard, three gates

The mesh had contract SUBSTANCE scattered across dbt tests, Soda checks, and DataHub DataContracts, but no
single declarative standard and nothing that FAILED on a malformed contract. B157 adopts ODCS (a lab subset)
and gates it. See the decision doc [data-contracts-odcs.md](../concepts/data-contracts-odcs.md) and the demo
[odcs-contracts.md](../demos/odcs-contracts.md).

## From scattered substance to one contract

```mermaid
flowchart LR
    subgraph substance [the substance the mesh already knows]
        A[Trino information_schema<br/>columns + types]
        B[Soda checks<br/>DQ rules]
        C[dbt schema.yml<br/>descriptions]
        D[DomainConfig<br/>domain + owner]
    end
    A --> G[gen_odcs_contract.py]
    B --> G
    C --> G
    G --> Y[contracts/&lt;domain&gt;/*.odcs.yaml<br/>one ODCS v3 per data product]
    D --> Y
    Y --> M[DataHub DataContract<br/>runtime mirror of the assertions]
```

ODCS is the **declarative source** (what is promised); the DataHub DataContract is the **runtime mirror**
(whether it currently holds). Complementary, not redundant.

## Three gates, from cheap to live

```mermaid
flowchart TD
    Y[*.odcs.yaml] --> S{structural gate<br/>check-odcs-contracts.sh}
    S -->|malformed / missing field| F1[exit 1 — CI fails]
    S -->|toolchain / root missing| F2[exit 2 — could-not-run]
    S -->|ok| SC{--check-schema<br/>declared columns vs Trino}
    SC -->|a declared column absent| F3[exit 1]
    SC -->|Trino unreachable| F4[exit 2 — fail closed]
    SC -->|ok| PC{products-without-contracts<br/>pytest}
    PC -->|a product has no contract| F5[test fails]
    PC -->|ok| DB{dbt contract: enforced<br/>on the marts}
    DB -->|built type ≠ declared| F6[dbt build errors]
    DB -->|ok| OK[every product contracted,<br/>schema-conformant, build-enforced]
```

- **Structural** (`check-odcs-contracts.sh`, 10 bats) runs in CI — no cluster.
- **Live column conformance** (`--check-schema`) asserts each declared column exists in the Trino physical
  table — runs at close-out (needs the cluster); validated 2026-09-05, all 10 conform, a bogus column caught.
- **Products-without-contracts** (`test_product_contract_coverage.py`) fails if a Music/Health/Finance
  product has no contract — 10/10 covered.
- **dbt `contract: enforced`** on the finance marts catches a schema change at `dbt build` — confirmed live
  (`dbt build`, PASS=16, ERROR=0).
