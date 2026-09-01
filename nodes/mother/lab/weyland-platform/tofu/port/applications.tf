# B60 DECOUPLING, EXECUTED 2026-08-24 (B137). This file deliberately declares NO resources.
#
# It used to hold `resource "port_entity" "component"` with `for_each = local.app_components`, generating
# 64 Port `component` entities from the B82 application registry
# (services/weyland-dagster/weyland_pipeline/applications.yaml).
#
# ── WHY IT IS GONE ────────────────────────────────────────────────────────────────────────────────
# The B60 split is: **blueprints are SCHEMA (OpenTofu, drift-checked); entities are DATA (managed by
# MCP, the integrations, and applications.yaml, free to evolve).** That decision was recorded in
# docs/runbooks/opentofu.md, and the `tofu state rm` half of it was never actually run. The entity
# resources stayed in state for weeks.
#
# The consequence was not cosmetic. `tofu plan` on this lane reported **0 to add, 64 to change,
# 0 to destroy** on every single invocation, because other writers legitimately own that data and
# tofu could only ever see their work as drift to revert.
#
# The plan proposed to remove four string props and the relations block from every component:
#
#     - "datahub_application_url" = null
#     - "lifecycle"               = null
#     - "source"                  = null
#     - "type"                    = null
#     - relations = { - many_relations = { …
#
# CHECKED AGAINST LIVE PORT RATHER THAN INFERRED FROM THE DIFF (2026-08-24), because a plan line
# saying `- "x" = null` does NOT by itself mean live data was at risk. Of the 64 components:
# `type`, `lifecycle` and `source` were populated on **0**, and no component had a non-empty
# relation, so those lines were tofu-state bookkeeping and nothing more. But
# `datahub_application_url` was populated on **30** (the data-applications, per B82), and that IS
# real data an apply would have cleared. So the hazard was genuine but bounded: 30 links, not
# "properties and relations off all 64".
#
# It also silently disabled the thing this lane exists for. `docs/runbooks/port.md` describes blueprints
# as "drift-checked", but a plan that is permanently dirty cannot detect anything: the signal was
# indistinguishable from the noise, exactly like a permanently-lit alert.
#
# ── WHERE COMPONENT ENTITIES COME FROM NOW ────────────────────────────────────────────────────────
# `applications.yaml` remains the ONE canonical registry. `datahub_emit.py::emit_applications` reads it
# and creates DataHub Application entities — but ONLY for rows with `datahub_application: true` (the ~30
# data-apps), and it writes to DataHub GMS ONLY. It does NOT touch Port.
#
# Port `component` entities are DATA created/updated out-of-band via the Port API/MCP when a component is
# added — there is NO code that auto-syncs the file into Port, and NO guard that reconciles the registry
# against live Port (`scripts/check-app-registry.sh` only reconciles Argo apps ↔ the registry, git-side).
# So a newly-registered `datahub_application: false` component can be committed, pass every git-side check,
# and still never reach the Port catalog. That is exactly what happened to `lancedb-exporter` (B78) and
# `port-k8s-exporter` (B145): both sat in the registry, absent from Port, until a manual API upsert on
# 2026-08-31 backfilled them (66/66 reconciled). If this keeps recurring, the fix is a reconciliation
# step (a Dagster op or a CI check that upserts registry→Port), NOT re-adding entity-as-code below.
#
# ── DO NOT RE-ADD ENTITY RESOURCES HERE ───────────────────────────────────────────────────────────
# If a future change makes entity-as-code look attractive again, read this comment first. It was tried,
# it produced constant sync friction, the decision to stop was made in B60, and executing it in B137 is
# what made `tofu plan` a usable drift check for the first time.
#
# Blueprints (the schema) live in blueprints.tf / catalog.tf / cost.tf and ARE codified. See
# docs/runbooks/opentofu.md § Port lane.
