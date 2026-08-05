---
name: distill-doc
description: Turn a lab-specific docs-site page into a generic, shareable writeup of the underlying process/concept — strips lab specifics + secrets, outputs a Google Doc. Use when asked to extract or share the reusable substance of a page.
---

Use when the user wants to turn a weyland docs-site page into a **generic, shareable writeup** of the underlying process,
concept, or technique — stripping everything lab-specific so it can be handed to someone outside the lab.

**Input:** one or more source pages — a repo path (`docs/**/*.md`) or a `docs.weyland.lab` URL. Read the FULL source
(Read for a repo path, WebFetch for a URL) before writing anything.

**Generalize — this is the whole point:**
- **STRIP** every lab-specific: proper nouns (weyland, rogueone, mother, Hermes, and any service/pod/host name), IPs,
  hostnames, URLs, `B##` backlog numbers, internal file paths, ports, and anything secret or credential-shaped. **A
  shared doc must never leak the lab's internal topology or secrets — this is a hard rule, not a nicety.** When a
  concrete detail is load-bearing, replace it with a generic placeholder (`<your-gpu-host>`, `a 16GB GPU`, `the
  ingestion service`), never the real value.
- **KEEP** the transferable substance: the technique, the *why* (decision rationale + tradeoffs), the gotchas and
  failure modes, and the ordered steps. That is what the reader is actually there for.
- **DEFAULT: keep ONE concrete worked example** with generic values — a reader learns more from "here's how it looks"
  than from pure abstraction. If the user passes `--abstract`, drop worked examples and keep only the general process.
- Preserve the document structure (headings, numbered steps). Convert any lab-specific diagram to a generic one (rename
  the participants). **Title the output by the concept, not the source page** (e.g. "Local-primary LLM with cloud
  failover", not "weyland-operator brain").

**Output:**
- **Default → a Google Doc.** Create it via the Google Drive/Docs MCP (create a Google Doc with the generalized
  content) and return the shareable link. PDF is a one-click download from Docs, so there is no separate PDF step.
- `--md` → write the generalized markdown to the scratchpad instead, for the user to convert however they like.

**Before finalizing, show a short audit** so the user can catch over- or under-generalization:
- **Stripped:** the lab-specifics you removed or replaced.
- **Kept:** the transferable core.
- **⚠️ Check:** anything that *might* still be lab-identifying, or that you were unsure whether to keep — flag it
  explicitly rather than silently guessing.

Multiple pages → offer to combine them into one coherent writeup or produce one Doc each; ask which if it's ambiguous.
