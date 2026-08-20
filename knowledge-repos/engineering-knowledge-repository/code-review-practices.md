---
id: code-review-practices
tags: [methodology, team-practices, developer-experience]
surfaces-at: [code-generation]
related: [definition-of-done, pair-programming, trunk-based-development, technical-debt-management]
complexity: foundational
---

# Code Review Practices

## What It Is
The process by which engineers review each other's code changes before merging — for correctness, clarity, security, performance, and design. Good code review is a knowledge-sharing and quality-assurance practice, not a gatekeeping ritual. The goal is to improve the code and share knowledge, not to demonstrate superiority or create bottlenecks.

## When to Apply
- All production code changes — code review should be a team norm, not an optional step
- When the Definition of Done includes a review requirement (it should)
- Security-sensitive changes — always require a security-aware reviewer

## When Not to Apply
- Pair programming already constitutes continuous review — a separate PR review may add overhead without additional value for code written in a pair
- Time-critical hotfixes — review after merging when necessary; not skipping the review entirely, just re-sequencing

## Key Concepts
- **Reviewer Focus Areas**: Correctness (does it work?), Clarity (can someone read this in 6 months?), Security (any vulnerabilities?), Design (does it fit the architecture?), Tests (are they meaningful?)
- **Constructive Tone**: Feedback should be specific, kind, and focused on the code — not the author. Distinguish opinions from blocking issues.
- **Conventional Comments**: A labeling system for PR comments — `[nit]` (minor style), `[blocking]` (must fix), `[question]` (needs clarification), `[suggestion]` (optional improvement). Reduces ambiguity about what must be addressed.
- **Small PRs**: Small, focused pull requests get better reviews — large PRs fatigue reviewers and produce superficial feedback. Aim for < 400 lines changed.
- **Review Turnaround**: Reviews completed within one business day — review latency is a significant developer experience problem and directly increases lead time
- **Asynchronous by Default**: For most changes; use pairing for complex design reviews that benefit from synchronous discussion
- **Not a Bureaucracy**: If review is consistently a bottleneck, diagnose: are PRs too large? Are there too few reviewers? Is the bar unclear?

## In Practice
Method's code review standard: all changes reviewed before merging, conventional comments to signal blocking vs. non-blocking feedback, PR size kept below 400 lines, same-day review SLA within the team. For security-sensitive changes (auth, data access, external API calls), require a reviewer who has reviewed the threat model.

## Engineering Knowledge
💡 **Engineering Knowledge — Code Review Practices**: Review for correctness, clarity, security, and design — not style (that's what linters are for). Use conventional comments: `[blocking]`, `[nit]`, `[question]` so the author knows what's required vs. optional. Keep PRs small — large PRs get rubber-stamped. Review within one business day — review latency is a direct contributor to long lead times. The goal is to improve the code and share knowledge, not to demonstrate authority. → `engineering-knowledge-repository/team-practices/code-review-practices.md`

## Related Entries
- [Definition of Done](definition-of-done.md) — code review is typically a DoD criterion
- [Pair Programming](../methodologies/pair-programming.md) — pairing is continuous, synchronous code review
- [Trunk-Based Development](../methodologies/trunk-based-development.md) — small PRs and fast reviews enable trunk-based development
