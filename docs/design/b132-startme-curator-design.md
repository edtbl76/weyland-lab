# B132 — start.me Curator: design decisions (in progress)

Move the 1,968-link taxonomy into a **database**, build an **application** around it, and give
it a browser client that files a new bookmark into the right widget **at save time**.

The taxonomy was built 2026-08-05 → 2026-08-08 and is in daily use. The capture client is the
visible half; the durable half is getting the corpus out of a loose JSON file in `~/Downloads/`
and into queryable, backed-up storage inside the lab.

> **Read and write paths are both verified against the live account** (reads 2026-08-18, writes
> 2026-08-22). The write spike created a widget and a bookmark on Weyland Lab and read both back
> from the tree. The API is real and usable; what remains is design, not feasibility.

## Problem

The taxonomy is done and in daily use. The failure mode now is **entropy at the edges**: every
new bookmark is a decision against 147 widgets, and the cost of deciding is high enough that
links get parked instead of filed. Parking is what produced `Misc.` (195 links) the first time.

The vendor Bookmarker extension makes this worse, not better — it saves to a start.me **inbox**,
which is a `Misc.` that fills itself.

**Requirement, stated by the operator:** the decision happens at save time and the item is
*done*. No queue, no backlog, no second pass. An inbox that grows is the thing being designed
against.

## What exists (the asset this is built on)

Rebuilt from 2,214 raw links over 2026-08-05 → 08-08; imported and in production since 08-08.

| Metric | Before | After |
|---|---|---|
| Links | 2,214 | **1,968** |
| Pages | 9 | **14** |
| Widgets | 85 | **147** |
| Links in `Misc.` catch-alls | 195 | **0** |
| Links with descriptions | 16% | **100%** |
| Widgets over 45 links | 14 | **0** |
| Duplicate URLs | ~1% | **0** |

Source of truth: `~/Downloads/startme-work/final_taxonomy.json` (1,968 objects:
`page, widget, title, url, description, old`). Reconciled against the live account
2026-08-18 — **147/147 widgets match, zero unmatched.**

Excluded by design: **Weyland Lab** (page `9319571`, 8 widgets, ~100 links) is invisible and
sits outside every calculation. The 8 pre-rebuild pages are retained with `is_archived: true`.

### Locked taxonomy rules

These are operator rules, established through the rebuild. **They go in the classifier prompt
verbatim** — without them a model reverts to filing by content type, which is the failure the
rebuild corrected.

- **L1 — Subject beats medium.** A resource about one subject files under that subject, whatever
  medium it is. Real Python → `Python`, not `Learning & Community`. Only genuinely multi-subject
  resources (freeCodeCamp, Codecademy) live on Learning & Community. A widget named after a
  content type is the smell that produced `Books & Publishing` and `Repos`.
- **L2 — Split papers from tools, never by subtopic.** When a widget outgrows ~45, split by
  content type (`— Papers` / `— Tools & Learning`), not finer topic. Subtopic splits force
  re-litigating the boundary on every new link; paper-vs-tool is a question the link answers
  itself.
- **L3 — Name by the reach-for moment.** Widget names encode *what you are doing when you reach
  for this*, not what the objects are. `Deployment and Delivery`, not `CI/CD Tools`.

### Sizing rules

- Widget 15–40 links; over 45 → split per L2; under 6 → merge, **unless small and precise**
  (merging orphans recreates `Misc.` under a new name).
- Page 6–10 widgets. AI Research (18) and AI Engineering (20) knowingly exceed this — they hold
  a third of the collection.
- **No `Misc.` widget may be created.** Ever. This is the invariant the whole rebuild bought.

## Finding — start.me has an undocumented write API

The earlier conclusion "start.me has no write API" was **wrong**. It was true of the *public*
API. The vendor Bookmarker extension (`obgopghdefjihikoknnjfooahlleabno`, v7.3.0) ships an
unminified-enough client for a full private one, read out of
`~/.config/google-chrome/Default/Extensions/.../js/background.js`.

Auth is **cookie-only** — `fetch(url, {credentials: "include"})`. No CSRF token, no bearer, no
signature. Base `https://start.me`.

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/pages/tree_extension.json` | Full page → widget tree **with IDs** | ✅ verified 200 |
| GET | `/tools/check_link_exists?url=` | Dupe check — returns the existing item | ✅ verified 200 |
| GET | `/logged_in` | Session probe | ✅ verified 200 |
| POST | `/widget/{widgetId}/item` | **Create bookmark in a widget** | ✅ verified **201** |
| POST | `/widget/{widgetId}/items` | Batch create | ⚠️ source only |
| POST | `/page/{pageId}/widget` | Create widget | ✅ verified **201** |
| PATCH | `/users/unsorted_link/{id}` | Edit inbox item | ⚠️ source only |
| GET | `/tools/title?url=` | Title fetch | ⚠️ source only |

Two properties worth calling out:

**`check_link_exists` returns the item, not a boolean.**

```json
{"exists":[{"item_id":456920635,"title":"[1706.03762] Attention Is All You Need",
  "url":"https://arxiv.org/abs/1706.03762","description":"Abstract page for arXiv paper...",
  "status_code":200,"broken":false}]}
```

`status_code` + `broken` mean **start.me health-checks links server-side.** That is a free
replacement for `deadcheck.py` and a standing answer to "what rotted since the rebuild."

`exists` is an **array** — start.me expects a URL to legitimately live in several widgets. The
rebuild assumed one home per link; the API does not. Warn on hit, allow the save.

### Write spike result (2026-08-22)

Both writes verified end-to-end against Weyland Lab (page `9319571`) — created, then read back
from the tree.

```js
POST /page/{pageId}/widget   { widget_type: "urllist", column: 0, title } // → 201 {id}
POST /widget/{widgetId}/item { url, title, description }                  // → 201 (below)
```

```json
{"item_id":516347145,"link_id":84067200,"index":0,"folder_id":null,
 "title":"B132 write-path spike","description":"...","icon":null,
 "creator_id":8155674,"mute_broken":false,
 "url":"https://example.com/b132-spike","favicon":"https://f.start.me/example.com"}
```

**Three findings that shape the schema:**

- **`item_id` and `link_id` are distinct.** The *link* is the URL entity (url, title, description);
  the *item* is its placement in a widget (index, folder). One `link_id` can carry many
  `item_id`s across widgets — which is exactly why `check_link_exists` returns an array. **The
  database should mirror this split**: `link` and `item` as separate tables, not one flat row.
  `final_taxonomy.json` is flat and therefore cannot represent multi-homing.
- **`folder_id` is live in the data model.** That is the *group* layer abandoned during the
  rebuild (the Java 4-way split retired the last dependency on it). Currently null everywhere.
  Retain the column; do not design around it yet.
- **Creation returns 201, not 200.** The vendor client checks `if (200 != status) reject`, so
  **their own extension treats a successful create as a failure.** Any client we write must
  accept 201. Assume the vendor's status handling is unreliable generally.

**Widget types.** Three exist: `page_intro`, `urllist`, `twitter-timeline`. Only `urllist` holds
bookmarks. The classifier must filter to `urllist`, or it will offer an intro panel as a
destination.

### Risk

Private API. It can change without notice; the failure mode is the button stopping, which is
immediately visible and loses nothing. Mitigation is the fallback picker (below), not
versioning. Do not build anything on this that a manual path cannot replace.

## Design

Chrome MV3 extension, unpacked (no store listing, no dev fee).

**Flow on click (or `Alt+B`):**

1. `activeTab` → URL, title, `<meta name="description">`
2. Parallel GET `check_link_exists` + tree (cached, TTL 1h)
3. Target list = `urllist` widgets on pages where `is_archived === false`, minus Weyland Lab
4. One Haiku call → top 3 widgets, one-line rationale each, confidence flag
5. Popup: 3 ranked cards + **editable title + editable description**
6. Click → `POST /widget/{id}/item` → done, popup closes

**Why the description field is not optional.** Cross-page search (Ctrl+S) covers title, URL, and
description. Descriptions *are* the retrieval surface — that is why the rebuild took 16% → 100%.
Save time is the only moment one will ever get written. Pre-fill from page meta; let it be edited.

### The catalog problem

`tree_extension.json` returns widget **names**, not their contents. Names alone cannot separate
`Papers — Foundations` from `Papers — Architectures`. The classifier needs exemplars.

**Resolution: live tree for names and IDs, baked samples for disambiguation.** Generate ~5 sample
titles per widget from `final_taxonomy.json` once. Staleness is harmless — a 2026 exemplar still
describes what a widget is *for*. New widgets appear as targets immediately (live tree); they
simply carry no samples until regenerated.

**Key on widget ID, never on name.** Two page names drifted within days of import — the operator
renamed `Personal and Accounts` → `Personal & Accounts` and `Security & Identity` →
`Security and Identity` in the UI. Names are operator-editable; IDs are not.

### Failure modes

| Condition | Behaviour |
|---|---|
| Dupe found | Show where it lives + `broken` status. Offer *go there* / *add anyway* |
| Low confidence | Flag it, show 3 nearest, offer **Create new widget** (`POST /page/{id}/widget`) |
| Classifier down / no key | Fall back to searchable picker over all 147. **Never blocks the save** |
| POST fails | Popup stays open, error shown, edits preserved |
| Tree fetch fails | Use cached tree; if none, error with retry |

The low-confidence path is deliberately **a new named widget, never a catch-all.** Low confidence
is a signal that the taxonomy has a real gap — surfacing it is the point.

### Cost

~8k cached input + ~200 output per save. Fractions of a cent. Key in
`chrome.storage.local` — readable by anything that can read the Chrome profile. Acceptable for
single-operator personal use; **do not** extend this to anything multi-user without moving the
key server-side.

## Direction — database + application

**The extension is a client, not the product.** The 1,968-link corpus is the asset; start.me is
one rendering of it. The taxonomy moves into a **database**, and an application is built around
it. This was the original 2026-08-05 intent ("start.me becomes generated output, not the master
copy") — deferred then because no write path existed. The write API removes that blocker.

**Why this, and not a file:**

- `final_taxonomy.json` currently lives, unversioned and unbacked, in `~/Downloads/`. One `rm`
  from gone.
- It **cannot go in this repo — `weyland-lab` is public.** The 91 links under
  `Personal & Accounts` are health services, schools, memberships, finances. That corpus is a
  profile of the operator, not configuration. A database inside the lab is the correct home;
  a public git repo never is.
- Structure and links are queryable together — "what rotted", "what's over 45", "what has no
  description" stop being one-off Python scripts.

**Datastore — SQLite, decided 2026-08-22.** Postgres was the first instinct and was **wrong**:
it was reached for because the lab already runs it, not because the requirements asked for it.
The corpus is **1,968 rows (~825KB) with a single writer**. Multi-writer safety, pooling and
horizontal scale — everything Postgres buys — are all unused here, and the cost is a server,
credentials, and a NodePort hop.

SQLite wins on the requirements *and* on the goal:

- **One file.** Backup is a copy; versioning is a commit. The `~/Downloads/` risk dies outright.
- **No server, no credentials, no NodePort.** The friction that stopped the first attempt is gone.
- **FTS5** covers full-text over title + description natively — the same surface start.me's own
  cross-page search uses.
- **`sqlite-vec`** covers the embedding prefilter, so the pgvector argument survives the move.
- **Runs in the browser via WASM**, so the extension can query the corpus with no backend.
- **Shareable.** `datasette publish` turns the file into a browsable, queryable site with a JSON
  API. Sharing a subset is a `WHERE` clause — export the tech pages, omit `Personal & Accounts`.

What it gives up: the nightly `postgres-backup` CronJob was real durability for free. A single
file is the easiest possible thing to hand to restic → MinIO (**B130**).

**Code + corpus live in `edtbl76/startme-curator` (private).** The weyland repo is public, and the
corpus carries personal-account links; the private-API client should not be published either.

**Consequence for this design.** Everything above (dupe check, tree fetch, classifier, POST)
becomes the application's API surface. The Chrome extension is then a thin caller: capture,
show 3, confirm. Sync to start.me becomes a job, not the point.

### Working assumption — (a) DB is truth, start.me is the UI

Operator, 2026-08-18: *"I assume the DB will be the source of truth and the page will be the
'UI'."* Recorded as a **working assumption, not a locked decision** — it does not gate the write
spike, so it can firm up later.

The alternatives, kept for the record: **(b) replaced** — the application grows its own UI and
start.me is retired (most control, most work, and it rebuilds a UI that already exists);
**(c) sidecar** — start.me stays authoritative and the DB only powers classification and
reporting (least work, but the corpus stays hostage to a private API).

**Open edge — the operator edits in the UI.** Two pages were renamed directly in start.me within
days of import (`Personal and Accounts` → `Personal & Accounts`, `Security & Identity` →
`Security and Identity`). Under naive one-way sync those edits are destroyed on the next push.
So (a) needs a rule for UI-originated structure changes:

- **Reconcile-first** — every sync pulls the live tree, diffs it, and adopts structure changes
  (renames, new widgets, reorders) into the DB before pushing links. Renames are safe because
  the tree carries stable **widget IDs**; a rename is an ID whose title changed, not a new widget.
- **Split ownership** — start.me owns *structure* (pages, widgets, names, order), the DB owns
  *links* (title, url, description, placement). Simpler, and matches how the operator actually
  works, at the cost of the DB not being able to restructure.

Reconcile-first is the better fit for (a) and is cheap given IDs are stable. Decide before the
first sync job, not before the spike.

## Build order

0. **Decide the start.me role** (a/b/c above) — it determines whether sync is one-way, two-way,
   or absent.
1. ~~**Write-path spike.**~~ **✅ DONE 2026-08-22** — widget + item created on Weyland Lab and
   read back from the tree (201/201). Feasibility is settled; the gate is lifted.
2. **✅ DONE 2026-08-22 — schema + ingest + invariant tests.** `edtbl76/startme-curator`
   (private). SQLite; `link`/`item` split; `curated_*` views scope the taxonomy to the 14 pages;
   FTS5 over title + description; 11 tests encoding the rebuild's invariants. 1,968 links / 147
   widgets / 14 pages ingested, zero unresolved.
   **Bug the tests caught:** page titles are *not unique* — `Business` and `Music & Studio` each
   exist twice, live and archived — so resolving placement by title let an archived widget shadow
   the live one it shared a name with, silently filing 8 links onto a retired page. The original
   round-trip test compared titles too and was blind to it. Both fixed; a regression test now
   asserts nothing lands off-scope. **Restates the rule: key on IDs, never titles.**

3. **Extension skeleton, no AI.** Tree fetch, `urllist` filter, searchable picker, manual save.
   This is a shippable tool on its own — it already beats the vendor extension, which files to
   an inbox.
3. **✅ DONE 2026-08-22 — classifier.** Top three destinations with a one-line reason each,
   the manual picker retained underneath. Ranking degrades to the picker on any failure; filing
   never depends on it. Low confidence offers a *named* new widget and refuses to create `Misc.`

   **Two implementation notes.** The prompt uses a **forced strict tool call** rather than
   `output_config.format` — same validated-JSON guarantee, and the contract was confirmable.
   Strict schemas accept only a subset of JSON Schema (`type`, `properties`, `required`,
   `additionalProperties`, `items`, `description`, `enum`); `minItems`/`maxItems` returned a
   **400** and failed the whole request rather than being ignored. A test now walks the schema
   and asserts the keyword set. Model defaults to `claude-opus-5` (the design originally said
   Haiku) and is overridable from extension storage.

   **Quality is not yet assessed** — it returns recommendations; whether they respect L1–L3 in
   practice needs real use.

4. **Classifier tuning.** Prompt = L1–L3 verbatim + baked catalog + page meta. Top 3 + confidence.
4. **Health sweep (optional, later).** `check_link_exists` across all 1,968 → rot report.

Step 2 standing alone is the hedge: if the classifier disappoints, the tool is still worth having.

## Open

- Write-path unverified (step 1 gates everything).
- Delete/undo endpoint not yet located in the vendor source — needed for clean spike teardown.
- Whether the popup should offer a page-level override before widget selection, or trust ranking.
- Automation-browser auth is blocked (account uses Google SSO; Google refuses OAuth in automated
  browsers). Options: set a start.me password for a hands-free test loop, or keep driving reads
  via operator console paste.

## Appendix — live widget map (2026-08-18)

14 pages · 147 `urllist` widgets · 1,968 links. Weyland Lab and the 8 archived pages excluded.
IDs are the POST targets.

#### AI Engineering — page `9390701` · 20 widgets · 317 links

| widget id | widget | links |
|---|---|---|
| `83778633` | Hardware & GPUs | 27 |
| `83778634` | Model Providers & APIs | 27 |
| `83778632` | Datasets & Data | 32 |
| `83778636` | Blogs & Writing | 23 |
| `83778637` | Frameworks, Serving & SDKs | 22 |
| `83778635` | Data Engineering | 23 |
| `83778639` | Repos — Data, Search & Vector | 16 |
| `83778640` | Models & Weights | 15 |
| `83778638` | Repos — Agents & Prompting | 22 |
| `83778642` | Prompting & Provider Docs | 13 |
| `83778643` | Benchmarks & Leaderboards | 12 |
| `83778641` | Repos — Models & Fine-tuning | 14 |
| `83778645` | Learning & Courses | 11 |
| `83778646` | Repos — Infra & Dev Tools | 10 |
| `83778644` | Repos — Safety & Evaluation | 11 |
| `83778648` | Data Governance & Catalogs | 9 |
| `83778649` | Cheatsheets & Quick Reference | 8 |
| `83778647` | BI & Visualization | 10 |
| `83778651` | Eval & Observability | 5 |
| `83778650` | Cloud & Platforms | 7 |

#### AI Research — page `9390703` · 18 widgets · 344 links

| widget id | widget | links |
|---|---|---|
| `83778657` | Papers — Safety & Reliability | 33 |
| `83778658` | Papers — Fine-tuning & PEFT | 31 |
| `83778656` | Papers — Evaluation & Benchmarks | 37 |
| `83778660` | Papers — Architecture & Techniques | 27 |
| `83778661` | Papers — Efficiency & Inference | 27 |
| `83778659` | Papers — Prompting & Reasoning | 31 |
| `83778663` | Papers — Scaling & Training Dynamics | 20 |
| `83778664` | Case Studies & Industry Reports | 20 |
| `83778662` | Papers — RAG & Retrieval | 23 |
| `83778666` | Papers — Agents & Tool Use | 16 |
| `83778667` | Papers — Model Releases & System Cards | 15 |
| `83778665` | Papers — Alignment & Preference | 20 |
| `83778669` | Papers — Attention & Context | 10 |
| `83778670` | Repos — Paper Artifacts | 7 |
| `83778668` | Papers — Training Data & Corpora | 13 |
| `83778672` | Papers — Embeddings & Representation | 5 |
| `83778673` | Autonomous Vehicles | 3 |
| `83778671` | Papers — NLP & Language | 6 |

#### Business — page `9390690` · 11 widgets · 101 links

| widget id | widget | links |
|---|---|---|
| `83778541` | Regulators & Government Bodies | 16 |
| `83778542` | Market Data & Exchanges | 14 |
| `83778540` | People, Leadership & Communication | 20 |
| `83778544` | Business News | 8 |
| `83778545` | Compliance, Legal & IP | 8 |
| `83778543` | Consulting & Professional Orgs | 13 |
| `83778547` | Ethics & Inclusion | 5 |
| `83778548` | Banks, Brokers & Fintech | 4 |
| `83778546` | Ratings, Research & Indices | 8 |
| `83778550` | Enterprise Software | 1 |
| `83778549` | Industry Bodies & Verticals | 4 |

#### Developer Tooling — page `9390689` · 12 widgets · 91 links

| widget id | widget | links |
|---|---|---|
| `83778529` | Text, Docs & Conversion | 13 |
| `83778530` | API Design & Docs | 9 |
| `83778528` | Code Quality & Analysis | 13 |
| `83778532` | Testing & Quality | 8 |
| `83778533` | Developer Platforms & Portals | 8 |
| `83778531` | Editors & IDEs | 8 |
| `83778535` | CLI & Shell Tooling | 7 |
| `83778536` | Mock & Fake Data | 7 |
| `83778534` | Public & Sample APIs | 7 |
| `83778538` | Collaboration & Whiteboards | 3 |
| `83778539` | Image & Media Tools | 3 |
| `83778537` | Git & Version Control | 5 |

#### Foundations — page `9390652` · 5 widgets · 44 links

| widget id | widget | links |
|---|---|---|
| `83778319` | Math | 10 |
| `83778322` | Cognition & Psychology | 2 |
| `83778318` | CS + AI | 22 |
| `83778320` | Finance, Accounting & Economics | 6 |
| `83778321` | General Reading, Libraries & Textbooks | 4 |

#### Front End & Web Development — page `9390694` · 9 widgets · 129 links

| widget id | widget | links |
|---|---|---|
| `83778571` | Build & Dev Tooling | 17 |
| `83778572` | Node & Server-Side JS | 16 |
| `83778570` | Frameworks & Libraries | 41 |
| `83778574` | Accessibility | 12 |
| `83778575` | Browser Engines & Web Platform | 11 |
| `83778573` | CSS & Styling | 13 |
| `83778577` | Testing & Mocking | 7 |
| `83778578` | SEO & Web Analytics | 5 |
| `83778576` | Color & Type Tools | 7 |

#### Hubs, Registries & Assets — page `9390656` · 6 widgets · 71 links

| widget id | widget | links |
|---|---|---|
| `83778340` | Code Hosting & Directories | 15 |
| `83778341` | Package & Software Hubs | 14 |
| `83778339` | GitHub Profiles | 18 |
| `83778343` | Awesome Lists & Curated Collections | 7 |
| `83778344` | Canonical ID Registries | 3 |
| `83778342` | Assets, Icons & Fonts | 14 |

#### Languages & Ecosystems — page `9390692` · 9 widgets · 124 links

| widget id | widget | links |
|---|---|---|
| `83778562` | Java — Testing & Quality | 21 |
| `83778563` | Java — Libraries & Frameworks | 17 |
| `83778561` | Python | 33 |
| `83778565` | Java — Language & Docs | 12 |
| `83778566` | Java — Runtime & Build | 11 |
| `83778564` | Systems Languages (C/C++/Erlang/Rust/Go) | 13 |
| `83778568` | R & Statistical Computing | 4 |
| `83778569` | .NET & Microsoft Stack | 3 |
| `83778567` | Mobile | 10 |

#### Learning & Community — page `9390695` · 8 widgets · 149 links

| widget id | widget | links |
|---|---|---|
| `83778587` | OSS Foundations, Projects & Contributing | 28 |
| `83778588` | Courses, Platforms & Certifications | 28 |
| `83778586` | Engineering Blogs | 35 |
| `83778590` | Developer Portals & Communities | 16 |
| `83778591` | Podcasts, Talks & Newsletters | 8 |
| `83778589` | Tech News, Journals & Publications | 21 |
| `83778593` | Licensing & Governance | 6 |
| `83778592` | Practice, Labs & Challenges | 7 |

#### Music & Studio — page `9390655` · 4 widgets · 55 links

| widget id | widget | links |
|---|---|---|
| `83778336` | Watched Vendors | 10 |
| `83778338` | Craft & Reference | 4 |
| `83778335` | Licenses & Accounts | 34 |
| `83778337` | Gear & Instrument Vendors | 7 |

#### Personal & Accounts — page `9390679` · 10 widgets · 91 links

| widget id | widget | links |
|---|---|---|
| `83778450` | Tools — Productivity & Branding | 13 |
| `83778451` | Accounts — Health & Fitness | 11 |
| `83778449` | Accounts — Business & Dev Infrastructure | 24 |
| `83778453` | Professional Communities & Orgs | 7 |
| `83778454` | Home, Finance & Lifestyle | 7 |
| `83778452` | Education — Other Programs & Study | 7 |
| `83778456` | Education — Georgia Tech | 6 |
| `83778457` | Accounts — Travel & Loyalty | 5 |
| `83778455` | Martial Arts, Blades & Gear | 7 |
| `83778458` | Education — LSUS | 4 |

#### Platform & Infrastructure — page `9390697` · 13 widgets · 174 links

| widget id | widget | links |
|---|---|---|
| `83778596` | Linux | 21 |
| `83778597` | Distributed Systems — Tools & Learning | 20 |
| `83778595` | Distributed Systems — Papers | 23 |
| `83778599` | Containers & Orchestration | 16 |
| `83778600` | Database Tooling | 15 |
| `83778598` | Data Stores | 19 |
| `83778602` | Deployment & Delivery | 11 |
| `83778603` | APIs, Proxies & Edge | 10 |
| `83778601` | Cloud Platforms & Hosting | 12 |
| `83778605` | Observability & SRE | 8 |
| `83778606` | Integration & Process Automation | 7 |
| `83778604` | Streaming & Messaging | 9 |
| `83778607` | Hardware & Embedded | 3 |

#### Security and Identity — page `9390658` · 9 widgets · 71 links

| widget id | widget | links |
|---|---|---|
| `83778347` | Identity, Auth & Policy | 10 |
| `83778348` | AppSec & Vulnerability Scanning | 10 |
| `83778346` | Learning, Practice & Reference | 10 |
| `83778350` | Recon & Network Analysis | 8 |
| `83778351` | Governance & Compliance | 7 |
| `83778349` | Offensive & Pen Testing | 9 |
| `83778353` | Threat Intel & CVE | 6 |
| `83778354` | Security News & Conferences | 5 |
| `83778352` | Crypto, Keys & Encoding | 6 |

#### Software Design & Practice — page `9390699` · 13 widgets · 207 links

| widget id | widget | links |
|---|---|---|
| `83778619` | Specs, Formats & Protocols | 26 |
| `83778620` | Architecture — Modeling & Tools | 22 |
| `83778618` | Architecture — Concepts & Styles | 42 |
| `83778622` | Product Strategy & Frameworks | 19 |
| `83778623` | Engineering Practice & Manifestos | 16 |
| `83778621` | UX & Design Systems | 21 |
| `83778625` | Thinking Tools & Facilitation | 12 |
| `83778626` | Design Patterns & Refactoring | 8 |
| `83778624` | Standards Organizations & Registries | 14 |
| `83778628` | Metrics & Measurement | 7 |
| `83778629` | Green & Sustainable Engineering | 7 |
| `83778627` | SDLC & Delivery Practice | 8 |
| `83778630` | Style Guides & Conventions | 5 |
