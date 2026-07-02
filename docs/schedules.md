# Weyland — Master Schedule

Single source of truth for **everything that runs on a timer** in the lab: Dagster schedules,
DataHub managed-ingestion sources, and any other cron-driven jobs. Keep this updated whenever a
schedule is added, moved, or disabled (same discipline as [hosts.md](hosts.md) / [api.md](api.md)).

## ⚠ The timezone trap — read this first

Different systems interpret their cron expressions in **different timezones**. A schedule that
*looks* clear in one UI can collide with another once both are normalized:

| System | Timezone | Why |
|---|---|---|
| **Dagster** | **UTC** | `ScheduleDefinition`s set no `execution_timezone` → Dagster defaults to UTC. |
| **DataHub** managed ingestion | **America/New_York (EDT/EST)** | Set per-source in the ingestion UI; the schedule column renders local. |

**Everything below is normalized to UTC** so collisions are visible. EDT = UTC−4 (EST = UTC−5 in
winter — recheck the DataHub offsets after the DST change).

> To remove the trap entirely, pin Dagster schedules with `execution_timezone="America/New_York"`
> (or set DataHub sources to UTC). Until then, do the ±4h conversion by hand.

## Master timetable (UTC)

Heavy = embeds/writes or large scans (guard the node's RAM). Light = metadata/read-only.

| UTC | System | Job / source | Cadence | Weight |
|---|---|---|---|---|
| **02:17** | Dagster | `weyland_ingestion_job` (RAG fan-out, serialized) | daily | **HEAVY** |
| 00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00 | Dagster | `ai_session` | every 4h | light |
| 00:25 / 04:25 / 08:25 / … | Dagster | `timeseries` (→ TimescaleDB hypertables) | every 4h | med |
| 00:40 / 06:40 / 12:40 / 18:40 | Dagster | `datahub_catalog_emit` (custom emitters) | every 6h | light |
| 00:50 / 06:50 / 12:50 / 18:50 | Dagster | `catalog` (model lookup) | every 6h | light |
| 07:00 (03:00 EDT) | Dagster | `datasets_music_land` | daily — **STOPPED** | heavy |
| 08:00 (04:00 EDT) | Dagster | `datasets_health_land` | daily — **STOPPED** | heavy |
| 05:00 (01:00 EDT) | DataHub | Grafana | daily | light |
| 05:15 (01:15 EDT) | DataHub | Iceberg (Nessie) | daily | light |
| 05:30 (01:30 EDT) | DataHub | MLflow | daily | light |
| 05:45 (01:45 EDT) | DataHub | Superset | daily | light |
| 07:00 (03:00 EDT) | DataHub | Neo4j | daily | light |
| 07:15 (03:15 EDT) | DataHub | Postgres (weyland core) | daily | med |
| **07:30 (03:30 EDT)** | DataHub | **CockroachDB** | weekly (Sun) rec. | med |
| 07:45 (03:45 EDT) | DataHub | MongoDB | weekly (Sun) rec. | med |
| 08:45 (04:45 EDT) | DataHub | Postgres — MusicBrainz | weekly (Sun) rec. | **heavy scan** |

Note the two `03:00 EDT` / `07:00 UTC` entries (music-land + Neo4j ingestion) — harmless only
because music-land is **STOPPED**. If you enable it, move one.

## Design rules

1. **Keep DataHub out of Dagster's UTC clusters.** The busy UTC bands are `00:00–00:50` (ai +
   timeseries + emit + catalog stack up) and `02:17` (heavy ingestion). In EDT those are the *evening*
   (20:00–20:50 and 22:17 EDT) — well clear of the DataHub 12 am–5 am EDT window. The only Dagster
   jobs that reach into that window are the every-4h/6h firings at **04:00, 04:25, 02:40, 02:50 EDT**
   — DataHub sources must dodge those six minutes.
2. **Spread the heavy stores.** Postgres-core, Cockroach, Mongo, MusicBrainz never share a 15-min slot;
   MusicBrainz (39M-row `COUNT(*)` scans under `profile_table_level_only`) sits alone at 04:45 EDT.
3. **Static data → weekly, not daily.** CockroachDB (brfss/nhis), the Mongo *datasets*, and MusicBrainz
   were loaded once and never change. Daily re-profiling just re-scans them for the same numbers. Run
   those **weekly** (`30 3 * * 0` etc.); reserve **daily** for stores Dagster actively writes.
4. **One node, one RAM pool.** Dagster runs execute *in* the user-code pod; DataHub ingestion runs in
   its executor. Both draw on mother's ~32 GB. Staggering is a memory guard, not just tidiness — this
   is the same constraint that drove `max_concurrent_runs: 1` and the serialized ingestion job.

## Change log

- 2026-07-02 — Doc created. Recommended DataHub ingestion stagger (was clustered 12–5 am EDT at
  :00/:30, with CockroachDB at 12 am EDT = 04:00 UTC colliding with Dagster `ai_session`). CockroachDB
  → `30 3 * * *` EDT (or weekly `30 3 * * 0`).
