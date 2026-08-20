---
id: exploratory-testing
tags: [methodology, testing]
surfaces-at: [code-generation, user-stories]
related: [end-to-end-testing, shift-left-testing, definition-of-done]
complexity: foundational
---

# Exploratory Testing

## What It Is
A manual testing approach where the tester simultaneously designs and executes tests, using the system's behavior as feedback to guide the next action — rather than following pre-written test scripts. Exploratory testing leverages human creativity, domain knowledge, and intuition to find defects that scripted tests and automated suites miss. It is structured through test charters and time-boxed sessions, not free-form "clicking around."

## When to Apply
- Before and after releases to find defects that automated tests didn't catch
- New features during development — exploratory testing provides rapid feedback on usability and edge cases
- Risk-based testing of high-value areas — testers allocate exploration time proportionally to risk
- Onboarding — new team members explore the system to build understanding while simultaneously testing it

## When Not to Apply
- Regression verification that automated tests should handle — don't use human time for automatable work
- High-volume repetitive checks (verify 1000 records) — automation is more reliable

## Key Concepts
- **Test Charter**: A mission statement for an exploratory session — "Explore the checkout flow using coupon codes to discover security and calculation bugs." Provides focus without scripting
- **Session-Based Test Management (SBTM)**: Time-boxed sessions (60-90 minutes) with charters, followed by a debrief. Produces a record of what was explored and found
- **Heuristics**: Mental models testers apply to find bugs — SFDPOT (Structure, Function, Data, Platform, Operations, Time), boundary values, error guessing
- **Bug Taxonomy**: Classifying found defects — helps testers spot patterns and allocate exploration focus
- **Paired Exploratory Testing**: Two testers working together — one operates, one observes and thinks critically. Higher defect detection rate
- **Test Notes**: Real-time notes taken during a session — what was tried, what was found, what questions arose. Essential for debrief and reporting

## In Practice
Method incorporates exploratory testing as part of the Definition of Done for user-facing features. QA engineers conduct charter-based exploratory sessions before sprint demos. Bugs found in exploratory testing are logged with reproduction steps and enter the backlog. Exploratory testing is particularly valuable for new user flows and integration touch points.

## Engineering Knowledge
💡 **Engineering Knowledge — Exploratory Testing**: Not all testing should be scripted. Exploratory testing uses charters and time-boxed sessions to find defects that automated suites miss — especially usability, edge case, and integration issues. Structure sessions with a charter ("explore payment flow with expired cards") and time box them to 60-90 minutes. Take notes. Debrief after. Pair when possible. This is not ad-hoc clicking — it's skilled investigation guided by heuristics and domain knowledge. → `engineering-knowledge-repository/testing/exploratory-testing.md`

## Related Entries
- [End-to-End Testing](end-to-end-testing.md) — exploratory testing complements automated E2E coverage
- [Shift-Left Testing](shift-left-testing.md) — exploratory sessions can happen early, not just pre-release
- [Definition of Done](../team-practices/definition-of-done.md) — DoD includes exploratory testing for user-facing features
