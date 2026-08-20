# Industry Vertical Repository

Method's Industry Vertical Repository (IVR) captures domain context, regulatory landscape, common system archetypes, and engagement patterns for the industries Method works in. It surfaces at the right moment in the delivery workflow — and seeds the future solutions/pre-sales phase.

---

## Two Ways to Use the IVR

### 1. Workflow-Integrated (AI-Surfaced)
During applicable Inception and Engineering stages, the AI checks the active engagement's Industry Vertical (from `aidlc-docs/aidlc-state.md`), consults `index.md`, and surfaces relevant Industry Insight statements inline — before questions are asked. A consultant new to the domain learns the landscape. An experienced practitioner confirms context and moves on.

### 2. Standalone (Human-Searchable)
Browse by vertical, search by tag, or navigate the index directly. Useful for pre-engagement research, staffing conversations, and solutions scoping.

---

## Directory Structure

```
industry-vertical-repository/
├── README.md                              ← You are here
├── index.md                               ← Machine-readable vertical + stage → entry mapping
│
├── healthcare/                            (7 entries)
│   ├── _overview.md
│   ├── prior-authorization.md
│   ├── patient-identity.md
│   ├── ehr-integration.md
│   ├── revenue-cycle.md
│   ├── care-management.md
│   └── telehealth.md
│
├── financial-services/                    (5 entries)
│   ├── _overview.md
│   ├── payments-processing.md
│   ├── kyc-aml.md
│   ├── lending.md
│   └── insurance.md
│
├── energy-utilities/                      (5 entries)
│   ├── _overview.md
│   ├── grid-management.md
│   ├── smart-metering.md
│   ├── energy-trading.md
│   └── renewable-integration.md
│
├── manufacturing/                         (7 entries)
│   ├── _overview.md
│   ├── mes.md
│   ├── iiot-predictive-maintenance.md
│   ├── plm.md
│   ├── digital-twin.md
│   ├── supply-chain-visibility.md
│   └── quality-management.md
│
├── automotive/                            (6 entries)
│   ├── _overview.md
│   ├── connected-vehicle.md
│   ├── adas-autonomous.md
│   ├── ev-charging.md
│   ├── automotive-software-development.md
│   └── automotive-manufacturing.md
│
├── media-entertainment/                   (5 entries)
│   ├── _overview.md
│   ├── streaming-platform.md
│   ├── content-supply-chain.md
│   ├── rights-management.md
│   └── ad-tech.md
│
├── retail/                                (5 entries)
│   ├── _overview.md
│   ├── order-management.md
│   ├── inventory-management.md
│   ├── customer-data-platform.md
│   └── store-operations.md
│
├── telecom/                               (5 entries)
│   ├── _overview.md
│   ├── billing-charging.md
│   ├── network-inventory.md
│   ├── digital-channels.md
│   └── 5g-network-slicing.md
│
├── logistics/                             (4 entries)
│   ├── _overview.md
│   ├── tms.md
│   ├── last-mile.md
│   └── supply-chain-visibility.md
│
├── travel-hospitality/                    (4 entries)
│   ├── _overview.md
│   ├── booking-engine.md
│   ├── revenue-management.md
│   └── loyalty.md
│
└── government/                            (3 entries)
    ├── _overview.md
    ├── case-management.md
    └── digital-identity.md
```

---

## Entry Format

Every IVR entry follows this structure:

```markdown
---
id: kebab-case-id
vertical: [vertical-name]
tags: [tag1, tag2, ...]
surfaces-at: [requirements-analysis, application-design, ...]
related: [entry-id1, entry-id2, ...]
---

# Entry Name

## What It Is
## Why It Matters in [Vertical]
## Key Concepts
## Common Patterns / Gotchas
## Industry Insight
## Solutions Context
## Related Entries
```

**Frontmatter fields:**
- `id` — unique identifier, matches filename (kebab-case)
- `vertical` — the industry vertical this entry belongs to
- `tags` — keywords for search and discovery
- `surfaces-at` — which AIDLC stages trigger this entry
- `related` — IDs of related entries (IVR or EKR cross-references)

**Section notes:**
- `Industry Insight` — the surfaced statement shown inline during the workflow. Keep it to 2–3 sentences.
- `Solutions Context` — scoping anchors, common engagement patterns, and risk factors for this domain. Surfaced during the Solutions phase; not surfaced during delivery stages.

---

## How IVR Surfaces in the Workflow

At applicable stages, the AI:
1. Reads the active `Industry Vertical` from `aidlc-docs/aidlc-state.md`
2. Looks up the vertical and stage in `index.md`
3. Reads each relevant entry's `Industry Insight` field
4. Surfaces statements as **Industry Insights** before the question set, with a link to the full entry

Example inline output:
```
🏥 Industry Insight — Prior Authorization: You're designing a healthcare workflow. Prior auth is a state machine with payer-specific variations — model it as such from the start. Real-time PA (RTPA) is mandated for many payers under CMS rules and changes the latency profile significantly. → industry-vertical-repository/healthcare/prior-authorization.md
```

---

## Solutions Context

Each entry includes a `## Solutions Context` section. This is the IVR's bridge between sales, solutions, and delivery — the shared knowledge layer that gives pre-sales and solutions teams domain grounding before an engagement begins.

Solutions Context is surfaced during the Solutions phase of the workflow. It is not surfaced during delivery stages.

---

## How to Contribute

**Adding a new entry:**
1. Create the MD file in the appropriate vertical directory
2. Follow the entry format above — frontmatter is required
3. Add the entry to `index.md` under the relevant vertical and stages
4. Update the Directory Structure in this README

**Adding a new vertical:**
1. Create the vertical directory with at least `_overview.md`
2. Add it to the Directory Structure in this README
3. Add it to `index.md` under `## By Vertical`

**Updating an existing entry:**
1. Edit the file
2. If `surfaces-at` or `tags` changed, update `index.md` accordingly

**Ownership**: Method Engineering and Delivery Operations. Questions or contributions → Delivery leadership.
