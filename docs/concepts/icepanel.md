# IcePanel vs LikeC4 (B236): DON'T ADOPT

**Verdict (2026-11-03): don't adopt IcePanel.** Its free plan can't hold the lab's architecture model, can't be kept in
sync from git, and every feature that would make it worth using is on a paid plan, which the $0 rule rules out. The lab
keeps its model as code in LikeC4 (`docs/architecture/weyland.likec4`, B64), embedded in the docs site and served at
`likec4.weyland.lab`. Runbook: [runbooks/likec4.md](../runbooks/likec4.md).

IcePanel is a hosted C4 tool: a model you drill into from system context down to components, with flows, tags, and a
model shared with viewers. B236 asked whether it adds something concrete over LikeC4 or only duplicates it.

## The free plan (read from icepanel.io/pricing, 2026-11-03)

| Free plan | The lab's need | Effect |
|---|---|---|
| **Up to 100 model objects** | The LikeC4 model has **156 elements** | The model doesn't fit; only a slice (for example the AI plane) would. |
| 1 editor, unlimited viewers | One owner | Fine. |
| **1 flow per diagram**, 2 tag groups | LikeC4 has no such limits | Fewer flows and tags than the lab already has. |
| Share links and embeds: **public** only | | Protected share links are paid. |
| Import API and Export API: **5 requests a month** (the pricing table's columns are ambiguous; the read and write APIs show 10,000 and 1,000 a month) | Git must stay the source of truth, so the model would be re-imported on every change | A model synced from git on each commit would exhaust it. |
| Next plan: **Growth, $40 per editor per month**, billed annually (14-day trial) | $0 budget | Out: a trial is not a free tier. Unlimited objects, domains and draft designs are all Growth features. |

## What was not done, and why

The spike's plan also included three hands-on steps. They were not attempted, because the pricing facts decide the
verdict on their own (owner, 2026-11-03: "proceed w/ close now don't adopt"):
- **Importing the model through a reproducible path.** The full model is over the free cap, and keeping even a slice
  in sync from git is capped by the import quota. Whether LikeC4 1.60 can export a format IcePanel reads (Structurizr
  JSON, JSON/YAML) was not checked.
- **The egress check.** Checking the model text for internal hostnames, IPs and secret-shaped strings before import
  wasn't needed, since nothing was sent.
- **A hands-on capability comparison.** For the record, from the documented features: IcePanel's flows, tag filters,
  review comments and decision records are its additions over LikeC4. The free plan caps or excludes each of them
  (1 flow per diagram, 2 tag groups; decision records are Growth).

## Re-evaluate when

- IcePanel's free plan rises above the model's element count and allows imports often enough to sync from git, or
- the lab gains budget for paid tools, in which case compare Growth against LikeC4 hands-on.

Backlog: B236 (Linear EMA-324). Related: B64 (LikeC4).
