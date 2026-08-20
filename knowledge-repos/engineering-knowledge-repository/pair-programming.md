---
id: pair-programming
tags: [methodology, team-practices, developer-experience]
surfaces-at: [code-generation]
related: [mob-programming, test-driven-development, trunk-based-development, code-review-practices]
complexity: foundational
---

# Pair Programming

## What It Is
An Extreme Programming practice where two developers work together at one workstation, sharing a keyboard and screen. One is the **Driver** (writes code) and the other is the **Navigator** (reviews, thinks ahead, spots issues). Roles switch frequently. The goal is not two people doing the work of one — it's continuous code review, shared context, and joint problem-solving that produces higher quality output than either could produce alone.

## When to Apply
- Complex, high-risk features where two sets of eyes prevent costly mistakes
- Onboarding new team members — pairing accelerates knowledge transfer better than documentation
- Tackling unfamiliar technology where both engineers are learning together
- Debugging difficult problems where a second perspective breaks tunnel vision
- Passing knowledge to avoid single points of failure (bus factor)

## When Not to Apply
- Routine, well-understood tasks where the overhead isn't justified
- Engineers doing deep focused work that benefits from extended solo concentration
- When one partner is significantly distracted or unavailable — pairing poorly is worse than not pairing
- Remote teams with high-latency connections where screen-sharing is painful

## Key Concepts
- **Driver**: Writes the code — focuses on tactical, line-by-line concerns
- **Navigator**: Reviews, thinks strategically, looks ahead — keeps the bigger picture in view
- **Role Switching**: Switch driver/navigator regularly (every 15-30 minutes) — keeps both engaged
- **Ping-Pong Pairing**: One writes the test (TDD); the other writes the implementation; switch. A powerful combination with TDD.
- **Remote Pairing**: Tools like VS Code Live Share, tuple, or JetBrains Code With Me enable remote pairing — works well when latency is low
- **Flow and Productivity**: Pairing maintains focus and avoids rabbit holes. The navigator catches "we shouldn't be doing this at all" earlier than solo review.

## In Practice
Pair programming is a Method engagement recommendation for high-complexity features and onboarding sprints. It's not meant to be used 100% of the time — most teams pair on complex/risky work and go solo on routine work. The most underrated benefit is knowledge transfer: pairing a senior with a junior engineer for a sprint does more for the junior's growth than any code review cycle.

## Engineering Knowledge
💡 **Engineering Knowledge — Pair Programming**: Two engineers, one keyboard, continuous code review. The navigator catches what the driver is too close to see. Don't think of it as half the throughput — complex features done in pairs produce fewer defects and require less rework. Ping-pong pairing (one writes test, one writes implementation, switch) is the best way to do TDD in pairs. Use it selectively: complex features, unfamiliar tech, onboarding. Don't force it on routine work. → `engineering-knowledge-repository/methodologies/pair-programming.md`

## Related Entries
- [Test-Driven Development](test-driven-development.md) — ping-pong pairing combines pairing with TDD for maximum effect
- [Mob Programming](mob-programming.md) — pair programming extended to the whole team
- [Code Review Practices](../team-practices/code-review-practices.md) — pairing is continuous, synchronous code review
