---
id: inner-source
tags: [methodology, team-practices, developer-experience]
surfaces-at: [application-design, requirements-analysis]
related: [team-topologies, developer-experience, architecture-decision-records]
complexity: intermediate
---

# Inner Source

## What It Is
The practice of applying open-source software development principles inside an organization. Teams can contribute to codebases they don't own — submitting pull requests, reviewing code, and raising issues — using the same collaborative model as external open source. Inner source breaks down silos between teams and distributes knowledge across the organization rather than concentrating it in individual team ownership.

## When to Apply
- Platform teams that build shared internal libraries, SDKs, or tooling
- Organizations where multiple teams use shared components but contributions are bottlenecked through one team
- Large engineering organizations with siloed teams that rarely collaborate on shared code
- When a team needs a feature in another team's service and the owning team lacks bandwidth

## When Not to Apply
- Very small organizations where informal collaboration already works
- Systems with strict access controls where broad contribution is inappropriate (security-sensitive, compliance-constrained)
- Early-stage codebases where consistency matters more than distributed contribution

## Key Concepts
- **Trusted Committer**: The gatekeeper of a repository — reviews external PRs, ensures code quality and alignment with project vision (analogous to OSS maintainer)
- **Guest Contributor**: An engineer contributing to a codebase their team doesn't own — follows the project's contribution guidelines
- **Contribution Guidelines**: Documented standards (coding style, testing requirements, PR process) that enable guest contributors to contribute effectively without hand-holding
- **Issue-Based Coordination**: Communicate contributions via issues/tickets before writing code — aligns with owning team priorities and avoids wasted effort
- **Discoverability**: Inner source only works if teams can find what's available to contribute to — internal portals, catalogs (Backstage), or wikis make repos discoverable

## In Practice
Inner source is most effective for platform-level shared components — internal SDKs, shared UI libraries, internal tooling, API clients. The owning team acts as a Trusted Committer: they set direction, review PRs, but accept contributions from any internal team. Method recommends inner source for Platform teams in Team Topologies-aligned organizations — it reduces the bottleneck of a central platform team that can't keep up with all stream-aligned team needs.

## Engineering Knowledge
💡 **Engineering Knowledge — Inner Source**: Apply open-source collaboration principles inside the organization. Teams contribute to repos they don't own via PRs; a Trusted Committer from the owning team reviews and merges. Best for shared platform code (internal SDKs, shared libraries) where a single owning team becomes a bottleneck. Requires discoverable repos and contribution guidelines — without them, inner source doesn't happen. → `engineering-knowledge-repository/team-practices/inner-source.md`

## Related Entries
- [Team Topologies](team-topologies.md) — platform teams are the primary candidates for inner source adoption
- [Developer Experience](developer-experience.md) — inner source improves DX by enabling self-service contributions
- [Architecture Decision Records](architecture-decision-records.md) — ADRs document the decisions that guide inner source contributors
