# Design — weyland-guard scanner modernization (retire LLM Guard) · B117

## Problem

The **Scan** layer (`weyland-guard`) does its injection / toxicity / PII sanitization with **protectai/llm-guard**,
wrapped as three validators in `guardrails/validators/llm_guard.py` — `llm_guard.injection`, `llm_guard.toxicity`,
`llm_guard.pii` (all SHADOW). ProtectAI was acquired by Palo Alto Networks and the OSS repo's cadence dropped. The repo
isn't abandoned (PRs into late-2025, docs 2026), but the concern is fair *and* the modern replacements are purpose-built
and better-maintained — so the swap stands on its own merits.

**Scope: only these three validators.** The rest of `weyland-guard` is NOT llm-guard and stays untouched:
`grounding.py` (custom nli-deberta, B35), `llama_guard.py` (B115 Llama Guard Classify), `policy.py` (act `policy.gate`).

## Decision (2026-08-04)

Replace the three capabilities with actively-maintained, purpose-built tools — the swap **consolidates** onto tools
already in (or adjacent to) the stack, and **drops the llm-guard dependency entirely**.

| Capability | Replacement | Maintained | Rationale |
|---|---|---|---|
| PII | **Microsoft Presidio**, called directly | ✅ MIT, releases through 2026 | Near drop-in — llm-guard's `Sensitive` scanner *already just wraps Presidio* (B34, presidio + spaCy). We keep the same engine, drop the wrapper. |
| Injection / jailbreak | **Meta Llama Prompt Guard 2** (86M or 22M classifier) | ✅ Meta, 2026 | Purpose-built injection/jailbreak classifier; Llama Guard's *injection sibling* — serve it with the **same llama.cpp pattern** as the B115 Llama Guard. |
| Toxicity | **fold into Llama Guard** (already deployed) | ✅ | **Option A.** Llama Guard's unsafe S-categories (hate/harassment/sexual/…) already cover most toxic content → one fewer component. Rejected: Detoxify (stagnant), Guardrails-AI toxic (LLM-backed, slower). |

**Accepted tradeoff (toxicity):** Llama Guard is a *safety* classifier, not a *toxicity* one — mild rudeness outside an
S-category may not trip it. Acceptable for a $0 lab; revisit if the shadow data shows a real gap.

## Plan

1. **Presidio validator** — `guardrails/validators/pii_presidio.py` (`name="pii.presidio"`, OUTPUT). Use the Presidio
   `AnalyzerEngine` directly (already a transitive dep via the old wrapper); carry over the B34 entity calibration
   (drop IP/UUID false-positives). Same `Verdict` shape as today.
2. **Prompt Guard validator** — `guardrails/validators/prompt_guard.py` (`name="prompt_guard.injection"`, INPUT).
   **CORRECTION (2026-08-04):** Llama Prompt Guard 2 is a **DeBERTa encoder classifier** (86M/22M), NOT a generative
   Llama — so it is **NOT llama.cpp-servable**. It runs **IN-PROCESS** via a `transformers` `text-classification`
   pipeline, exactly like the llm-guard injection scanner it replaces (also a deberta classifier) and the grounding
   CrossEncoder — baked into the guard image, loaded offline. Binary (benign vs malicious); malicious-prob ≥ threshold
   → BLOCK. Model `project-free-llama/Llama-Prompt-Guard-2-22M` (ungated mirror; env `PROMPT_GUARD_MODEL` to swap to the
   gated official 86M with an HF token). **No new service to run** — simpler than first scoped.
3. **Toxicity** — no new validator. The existing `llama_guard.safety` (INPUT+OUTPUT) already carries the content-safety
   signal; document that it subsumes toxicity. (Optionally widen its category→verdict mapping to treat the
   hate/harassment categories as the toxicity signal.)
4. **Retire** `guardrails/validators/llm_guard.py`; drop the three `llm_guard.*` entries from `app.py` + `config.py`;
   remove `llm-guard` from the Dockerfile (keep `presidio-analyzer` + `spacy`/model, which llm-guard pulled in).
5. **Rollout** — new validators land in **SHADOW** (record-only, fail-open), exactly like the originals. Measure the FP
   rate on real traffic in `guardrail_verdicts` before promoting anything to `block`. Guard image bump (v9 → v10).

## Risks / open questions

- **Prompt Guard is a new model to serve** (small, CPU-fine) — one more llama.cpp server. Mitigated by reusing the
  Llama Guard pattern; decide 1B-tier-CPU placement (mother) vs on-demand.
- **Toxicity coverage gap** (above) — accept + watch the shadow data.
- **Presidio spaCy model** already baked (B34) — confirm no version drift when the llm-guard pin is removed.

## DoD acceptance criteria (all six pillars)

1. **Docs** — `arch.md` weyland-guard row updated (Scan no longer "≈ LLM Guard" — now Prompt Guard + Presidio + Llama
   Guard-for-toxicity); `runbooks/guardrails.md` (new validators + Prompt Guard serving); `concepts/guardrails.md` Scan
   row; api/hosts if Prompt Guard gets a service endpoint.
2. **Diagrams** — `flow-guardrails.md` updated (Scan validators); LikeC4 if Prompt Guard is a new component.
3. **Demos** — `demos/guardrails.md` Scan section re-run: injection→Prompt Guard, PII→Presidio, toxicity→Llama Guard,
   each producing a shadow verdict. The demo IS the test.
4. **Cleanup** — llm-guard fully removed (Dockerfile + validators + config); no dead `llm_guard.*` refs.
5. **Close-out** — backlog B117 → ✅DONE; Linear; memory (update [[b115-guardrails-platform]] + [[b34-pii-guard]]).
6. **Ops** — new validators scraped in `guardrail_verdicts` metrics; Prompt Guard server gets a down-alert +
   ServiceMonitor if it's a standing service; SHADOW→block promotion gated on measured FP.
