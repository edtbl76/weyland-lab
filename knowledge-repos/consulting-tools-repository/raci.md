---
id: raci
tags: [organizational, delivery]
surfaces-at: [validated-intent, workflow-planning]
related: [stakeholder-mapping, okrs, dependency-mapping, adkar, organizational-design]
complexity: foundational
---

# RACI Matrix

## What It Is
A responsibility assignment matrix that clarifies who is Responsible, Accountable, Consulted, and Informed for each activity, decision, or deliverable in a program or process. RACI eliminates the two most common causes of program dysfunction: diffused accountability (everyone thinks someone else owns it) and over-consultation (decisions require input from everyone, producing gridlock). Named for its four roles — Responsible (does the work), Accountable (ultimately answerable, one person only), Consulted (provides input before action), Informed (notified of outcomes) — the matrix provides a shared reference for who does what in every team interaction.

## When to Use
- Program kickoff: establishing ownership for deliverables before work begins
- When a program is slowing down because decisions require too many approvals
- Cross-functional programs spanning multiple teams or organizations (Method + client + vendors)
- When deliverable ownership is disputed or unclear mid-program
- Organizational design: defining decision rights alongside role definitions

## Key Concepts
- **Responsible (R)**: The person(s) who do the actual work. There can be multiple R's for a task, but at least one is required
- **Accountable (A)**: The single person ultimately answerable for the task being completed correctly. Only one A per task — this is the rule that has the most impact and creates the most resistance. Multiple A's are no A's
- **Consulted (C)**: People whose input is sought before the task is completed or the decision is made. Two-way communication. Being Consulted does not mean approval rights
- **Informed (I)**: People who are notified after the task is completed or the decision is made. One-way communication. Being Informed does not mean approval rights
- **RACI Anti-patterns**:
  - Multiple A's per task — diffused accountability
  - Too many C's — creates consultation drag; most C's should be I's
  - A ≠ R — the accountable person is not involved in the work and cannot actually be accountable
  - RACI as a paperwork exercise — filled out once, never referenced again
- **DACI Variant**: Some organizations use DACI (Driver, Approver, Contributors, Informed) where the Approver has explicit decision authority. Useful when "Accountable" is ambiguous about whether that means decision rights or delivery accountability
- **RACI for Decisions vs. Activities**: RACI works for both deliverable ownership (who produces the architecture document) and decision ownership (who decides the technology stack). Decision RACIs are often more valuable and more contentious
- **Cross-Organizational RACI**: In client engagements, Method appears in the RACI alongside client teams, vendors, and other partners. Establishing this explicitly in the first week prevents ownership disputes throughout the program

## Method Application
Method establishes a program RACI at kickoff for every client engagement. The most important rows are decisions, not deliverables — particularly decisions about scope, architecture, and program direction. The RACI review typically surfaces misaligned expectations between Method and the client about who has final say on key decisions.

## Consulting Insight
🎯 **Consulting Tool — RACI Matrix**: The most valuable part of building a RACI is the resistance it surfaces. When you present a draft RACI and a stakeholder says "I thought I was Accountable for that, not the CTO" — that is a program-threatening conflict that needed to be surfaced on day one, not week eight. The RACI's job is not to document ownership that everyone already agrees on; it's to surface ownership conflicts early, when they are still resolvable through conversation rather than escalation. → `consulting-tools-repository/raci.md`

## Related Entries
- [Stakeholder Mapping](stakeholder-mapping.md) — stakeholder map identifies who should be in the RACI; RACI assigns their roles
- [OKRs](okrs.md) — OKR ownership requires RACI-level clarity on who is accountable for each Key Result
- [Dependency Mapping](dependency-mapping.md) — dependencies create cross-team RACI requirements; who is accountable when a dependency is missed?
- [ADKAR](adkar.md) — RACI supports ADKAR's Reinforcement step: people sustain change when accountability is clear
- [Organizational Design](organizational-design.md) — RACI is a tool within organizational design; role definitions without RACI produce ownership gaps
