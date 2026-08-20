---
id: trunk-based-development
tags: [methodology, deployment, developer-experience]
surfaces-at: [code-generation, requirements-analysis]
related: [continuous-integration, feature-flags, pair-programming, test-driven-development]
complexity: intermediate
---

# Trunk-Based Development

## What It Is
A source control practice where all developers integrate their changes directly to a shared main branch (trunk) frequently — at least daily. Long-lived feature branches are avoided. Incomplete features are hidden behind feature flags, not kept on a private branch. Trunk-based development is the branching strategy that enables Continuous Integration and Continuous Delivery to work at their full potential.

## When to Apply
- Teams that practice Continuous Integration and want to realize its full benefits
- When long-lived branches are causing merge conflicts and integration pain
- When teams want to increase deployment frequency and reduce lead time
- Paired with feature flags to manage incomplete work on trunk

## When Not to Apply
- Open-source projects with large numbers of external contributors (where short-lived PRs from forks are standard)
- Teams without automated tests that can validate trunk is always releasable — trunk-based development requires fast, reliable CI
- When regulatory environments mandate explicit branch-per-feature for audit trails (though feature flags can satisfy this requirement)

## Key Concepts
- **Trunk / Main Branch**: The single shared branch — always in a releasable state
- **Short-Lived Branches**: If branches are used at all, they live for less than a day or two before merging to trunk
- **Continuous Integration**: Trunk-based development is the branching strategy CI requires — CI on long-lived branches is not true CI
- **Feature Flags**: The mechanism for shipping incomplete work to trunk — code is deployed but not activated
- **Branch by Abstraction**: Technique for making large refactors on trunk without breaking behavior — create an abstraction, implement both old and new behind it, cut over, remove old implementation
- **Feature Branch Anti-Pattern**: Long-lived branches delay integration — conflicts accumulate, trunk diverges, integration becomes painful

## In Practice
Trunk-based development is the branching strategy underlying Google's entire codebase. In Method engagements, it's the recommendation for teams that want to achieve high deployment frequency. The cultural shift is the hard part — developers must trust automated tests, commit small, and use feature flags. Teams coming from Gitflow need to unlearn the comfort of long-lived branches.

## Engineering Knowledge
💡 **Engineering Knowledge — Trunk-Based Development**: Merge to main at least daily. Long-lived branches are where integration pain is manufactured — the longer a branch lives, the worse the merge conflict. Feature flags hide incomplete work on trunk; short-lived branches handle code review. This is how high-frequency deployment actually works: the branch is always releasable because the team integrates continuously. Feature flags are the prerequisite, fast automated tests are the safety net. → `engineering-knowledge-repository/methodologies/trunk-based-development.md`

## Related Entries
- [Feature Flags](../deployment/feature-flags.md) — feature flags enable trunk-based development by hiding incomplete features on trunk
- [Continuous Integration](../deployment/continuous-integration.md) — trunk-based development is the branching strategy that makes CI real
- [Test-Driven Development](test-driven-development.md) — a fast test suite is the safety net that makes trunk-based development safe
