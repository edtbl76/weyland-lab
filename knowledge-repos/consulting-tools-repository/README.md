# Consulting Tools Repository

Method's library of consulting frameworks, strategy tools, and facilitation techniques — surfaced at the right moment during delivery and solutions work.

---

## Two Ways to Use

### 1. Workflow-Integrated (AI-Surfaced)
During applicable AIDLC stages, the AI consults `index.md` and surfaces relevant Consulting Insight statements inline — before questions are asked. The right framework at the right moment.

### 2. Standalone (Human-Searchable)
Browse by category, search by tag, or navigate the index directly. Useful for pre-engagement research, solutions scoping, workshop planning, and client conversations.

---

## Entry Format

```markdown
---
id: kebab-case-id
tags: [category, subcategory]
surfaces-at: [stage1, stage2]
related: [entry-id1, entry-id2]
complexity: foundational | intermediate | advanced
---

# Tool Name

## What It Is
## When to Use
## Key Concepts
## Method Application
## Consulting Insight
## Related Entries
```

**Frontmatter fields:**
- `id` — unique identifier, matches filename (kebab-case)
- `tags` — category and keyword tags for search and discovery
- `surfaces-at` — AIDLC stages that trigger this entry
- `related` — IDs of related entries (within this repo or cross-repo paths)
- `complexity` — reading investment: foundational / intermediate / advanced

**Consulting Insight** — the 2–3 sentence statement surfaced inline during the workflow. Written for a consultant about to facilitate or apply the tool, not a textbook explanation.

---

## Categories

| Category | Description | Count |
|----------|-------------|-------|
| `strategy` | Market analysis, competitive positioning, portfolio decisions | 19 |
| `technology-assessment` | Technology evaluation, vendor selection, due diligence | 9 |
| `product` | Product strategy, prioritization, goal-setting | 12 |
| `discovery` | Research methods, domain exploration, facilitation | 15 |
| `systems-thinking` | Complex systems, strategic situational awareness | 5 |
| `organizational` | Change management, roles, team design | 14 |
| `delivery` | Project structure, risk, estimation, dependencies | 13 |
| `facilitation` | Workshop tools, group decision-making, synthesis | 11 |
| `ddd` | Domain-Driven Design tools for boundary discovery and service design | 5 |
| **Total unique entries** | | **60** |

---

## How It Surfaces in the Workflow

At applicable stages, the AI:
1. Looks up the current stage in `index.md`
2. Retrieves relevant entry IDs
3. Reads each entry's `Consulting Insight` field
4. Surfaces statements as **Consulting Insights** before the question set, with a link to the full entry

Example inline output:
```
🎯 Consulting Tool — Double Diamond: You're entering a discovery phase. The Double Diamond's first diamond (Discover → Define) should precede any solution design — diverge broadly before converging on the right problem. Teams frequently skip Discover and go straight to Define, locking in a problem statement before they've validated it. → consulting-tools-repository/double-diamond.md
```

---

## How to Contribute

**Adding a new entry:**
1. Create the MD file in the repository root (flat structure)
2. Follow the entry format above — frontmatter is required
3. Add the entry to `index.md` under relevant stages
4. Update the Category count table in this README

**Ownership**: Method Consulting and Delivery leadership.
