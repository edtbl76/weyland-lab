# Demo — ODCS data contracts + conformance (B157)

Adopt the Open Data Contract Standard (a lab subset) as the one declarative shape for the mesh's data
contracts, generate them from the existing substance, and gate them three ways. Flow:
[flow-odcs-contracts.md](../diagrams/flow-odcs-contracts.md); decision + subset:
[data-contracts-odcs.md](../concepts/data-contracts-odcs.md).

## The point

Contract material existed everywhere (dbt tests, Soda, DataHub) and nowhere as *the* contract, and nothing
failed on a malformed one. Now every data product has one `*.odcs.yaml`, and CI fails if it drifts.

## CLI walkthrough (RUN against live infra)

**1. Generate a contract from the substance** (Trino columns+types · Soda rules · dbt descriptions):

```
kubectl -n data-mesh port-forward svc/trino-noauth 18200:8080 &
TRINO_HTTP=http://localhost:18200 python3 scripts/gen_odcs_contract.py \
  --domain music --product "Genre Taxonomy" --table iceberg.dbt.mart_fma_genre_tree \
  --id weyland-music-genre-taxonomy --out nodes/.../contracts/music/genre_taxonomy.odcs.yaml
```

RUN 2026-09-05 — produced all 6 music/health contracts (finance's 4 were hand-authored as the pattern).

**2. Structural gate** — every `*.odcs.yaml` carries the required fundamentals (no cluster):

```
bash scripts/check-odcs-contracts.sh --list
# ✓ x10 ; "OK — 10 ODCS contract(s) conform to the adopted subset."
```

**3. Live column conformance** — each declared column actually exists in Trino:

```
TRINO_HTTP=http://localhost:18200 bash scripts/check-odcs-contracts.sh --check-schema
# "OK — 10 ODCS contract(s) conform to the adopted subset."  (all columns present)
```

**The negative cases — prove the gates can fail:**

```
# structural: a non-semver version → exit 1 (bats: odcs-contracts.bats, 10 cases)
# --check-schema: a contract declaring a column not in Trino → exit 1 (RUN 2026-09-05, caught)
# fail closed: Trino unreachable during --check-schema → exit 2, never a clean pass
```

**4. dbt `contract: enforced`** — a mart schema change is caught at build, not just by the gate. Confirmed
by live `dbt build`s across **all three domains'** marts (contract types = verbatim Trino types):

```
# finance (4 marts)
dbt build --select mart_macro_indicators mart_company_financials mart_price_daily mart_price_features
# PASS=16 WARN=0 ERROR=0

# music + health product marts (contract: enforced on all 6)
dbt build --select mart_spotify_audio mart_artist_popularity mart_fma_genre_tree \
  mart_state_health_trends mart_country_health mart_personality_by_country
# PASS=32 WARN=0 ERROR=0 — the contracts hold against the real schema in every domain
```

**5. Products-without-contracts** — no data product ships uncontracted:

```
pytest tests/test_product_contract_coverage.py   # 10/10 Music/Health/Finance products contracted
```

## UI walkthrough (eyes-on)

1. Open **https://datahub.weyland.lab** → a finance/music/health dataset → **Contract** tab.
   **UAT — confirm:** the DataHub DataContract (the runtime mirror) shows the assertions the ODCS file
   declares; the ODCS YAML in `contracts/<domain>/` is the declarative source it corresponds to.

## Teardown

The contracts + generator + gates are read-only git artifacts. The confirming `dbt build` rebuilt the 4
finance marts (idempotent — the same thing the weekly `weyland_dbt_job` does). Kill the port-forward.
