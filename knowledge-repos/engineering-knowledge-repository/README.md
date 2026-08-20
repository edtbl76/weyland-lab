# NYK — Now You Know

> *"Knowing is half the battle."*

NYK is Method's Engineering Knowledge Base. It captures industry-standard methodologies, design patterns, architectural styles, and engineering practices — and surfaces them at the right moment during delivery.

---

## Two Ways to Use NYK

### 1. Workflow-Integrated (AI-Surfaced)
During Engineering stages in the Method AIDLC workflow, the AI consults `index.md` and surfaces relevant NYK statements inline — at the exact moment a decision is being made. A junior engineer follows the link and learns. A senior engineer already knows it and moves on.

### 2. Standalone (Human-Searchable)
Browse by category, search by tag, or navigate the index directly. NYK is a reference library for Method Engineering teams — useful in and out of any active workflow.

---

## Directory Structure

```
engineering-knowledge-repository/
├── README.md                    ← You are here
├── index.md                     ← Machine-readable stage → entry mapping (AI lookup)
│
├── methodologies/               ← Structured approaches to software development
│   ├── domain-driven-design.md
│   ├── test-driven-development.md
│   └── behavior-driven-development.md
│
├── architectural-philosophy/    ← High-order thinking about system design
│   ├── evolutionary-architecture.md
│   ├── solid-principles.md
│   ├── hexagonal-architecture.md
│   ├── clean-architecture.md
│   └── twelve-factor-app.md
│
├── architectural-styles/        ← Structural patterns for system organization
│   ├── event-driven-architecture.md
│   ├── cqrs.md
│   ├── microservices.md
│   ├── modular-monolith.md
│   ├── api-gateway-pattern.md
│   ├── backend-for-frontend.md
│   └── serverless.md
│
├── design-patterns/             ← Reusable solutions to recurring code-level problems
│   ├── repository-pattern.md
│   ├── factory-pattern.md
│   ├── observer-pattern.md
│   ├── strategy-pattern.md
│   ├── builder-pattern.md
│   ├── decorator-pattern.md
│   ├── facade-pattern.md
│   ├── adapter-pattern.md
│   ├── command-pattern.md
│   └── dependency-injection.md
│
├── data/                        ← Data architecture and modeling patterns
│   ├── data-mesh.md
│   ├── event-sourcing.md
│   ├── change-data-capture.md
│   └── polyglot-persistence.md
│
├── infrastructure/              ← Resilience and operational patterns
│   ├── circuit-breaker.md
│   ├── strangler-fig.md
│   ├── saga-pattern.md
│   ├── outbox-pattern.md
│   ├── bulkhead-pattern.md
│   ├── retry-pattern.md
│   └── dead-letter-queue.md
│
├── deployment/                  ← Release strategies and deployment patterns
│   ├── blue-green-deployment.md
│   ├── canary-deployment.md
│   └── feature-flags.md
│
├── testing/                     ← Testing strategies and approaches
│   ├── contract-testing.md
│   └── test-pyramid.md
│
├── security/                    ← Security patterns and protocols
│   ├── oauth2-oidc.md
│   ├── autonomous-remediation.md
│   ├── legacy-vulnerability-program.md
│   └── software-bill-of-materials.md
│
├── ai-ml/                       ← AI/ML architecture and orchestration patterns
│   ├── model-abstraction-layer.md
│   ├── model-routing.md
│   ├── harness-engineering.md
│   ├── harness-guides-and-sensors.md
│   ├── harnessability.md
│   ├── autonomous-coding-loop.md
│   ├── planner-generator-evaluator.md
│   ├── haas.md
│   └── aidlc.md
│
└── platform/                    ← Developer platform and self-service infrastructure
    ├── internal-developer-platform.md
    └── golden-path.md
```

> **Note**: Several entries (team-topologies, internal-developer-portal, developer-experience, gitops, etc.) live at the repository root rather than in a category subdirectory. These are indexed and fully functional — they predate the subdirectory convention or span multiple categories.

---

## Entry Format

Every NYK entry follows this structure:

```markdown
---
id: kebab-case-id
tags: [tag1, tag2, ...]
surfaces-at: [stage-name1, stage-name2, ...]
related: [entry-id1, entry-id2, ...]
complexity: foundational | intermediate | advanced
---

# Name

## What It Is
## When to Apply
## When Not to Apply
## Key Concepts
## In Practice
## Engineering Knowledge
## Related Entries
```

**Frontmatter fields:**
- `id` — unique identifier, matches filename (kebab-case)
- `tags` — keywords for search and discovery
- `surfaces-at` — which AIDLC stages trigger this entry (used by AI lookup via index.md)
- `related` — IDs of related entries
- `complexity` — entry depth level; helps engineers gauge reading investment

---

## How NYK Surfaces in the Workflow

At applicable Engineering stages, the AI:
1. Looks up the current stage in `nyk/index.md`
2. Retrieves the list of relevant entry IDs
3. Reads each entry's `NYK Statement`
4. Surfaces statements as **Engineering Insights** before the question set, with a link to the full entry

Example inline output:
```
💡 NYK — Domain-Driven Design: You're designing a domain model. Consider
organizing around Bounded Contexts before defining entities — it prevents
model pollution across team boundaries. → nyk/methodologies/domain-driven-design.md
```

---

## Entry Count by Category

| Category | Count |
|---|---|
| methodologies | 3 |
| architectural-philosophy | 5 |
| architectural-styles | 7 |
| design-patterns | 10 |
| data | 4 |
| infrastructure | 7 |
| deployment | 3 |
| testing | 2 |
| security | 4 |
| ai-ml | 9 |
| platform | 2 |
| root-level | ~20 |
| **Total indexed** | **~76** |

---

## How to Contribute

**Adding a new entry:**
1. Create the MD file in the appropriate category directory
2. Follow the entry format above exactly — frontmatter is required
3. Add the entry to `index.md` under relevant stages and tags
4. Update the Directory Structure and Entry Count table in this README

**Adding a new category:**
1. Create the subdirectory
2. Add it to the Directory Structure in this README
3. Add it to `index.md` under `## Categories`

**Updating an existing entry:**
1. Edit the file
2. If `surfaces-at` or `tags` changed, update `index.md` accordingly

**Ownership**: Method Engineering teams. Questions or contributions → Engineering leadership.
