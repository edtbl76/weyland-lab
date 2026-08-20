---
id: behavior-driven-development
tags: [methodology, testing]
surfaces-at: [user-stories, requirements-analysis, code-generation]
related: [test-driven-development, contract-testing]
complexity: foundational
---

# Behavior-Driven Development (BDD)

## What It Is
An extension of TDD that shifts the focus from technical tests to business behaviors. BDD uses a structured natural language format (Given/When/Then) to describe system behavior in terms that both engineers and non-technical stakeholders can read and validate. BDD tests are acceptance criteria made executable.

## When to Apply
- User stories that need precise, testable acceptance criteria
- Cross-functional teams where business stakeholders need to validate behavior
- Features with complex conditional logic that benefit from scenario-based thinking
- When acceptance testing needs to be automated

## When Not to Apply
- Internal infrastructure or platform code with no user-observable behavior
- Unit-level logic better expressed as TDD tests
- Teams without the discipline to maintain living documentation — stale Gherkin is worse than no Gherkin

## Key Concepts
- **Given/When/Then**: The three-part scenario structure. *Given* establishes context. *When* describes the action. *Then* states the expected outcome.
- **Feature file**: A plain-text file containing scenarios in Gherkin syntax — readable by anyone on the team.
- **Step definitions**: The code that maps Gherkin phrases to test automation.
- **Living documentation**: BDD scenarios serve as up-to-date specification. If the scenario passes, the behavior is implemented correctly.
- **Three Amigos**: The practice of writing scenarios collaboratively between a developer, tester, and product person — reduces misalignment before any code is written.

## In Practice
BDD is most valuable at the User Stories and Requirements Analysis stages — writing scenarios alongside stories ensures acceptance criteria are unambiguous before Engineering starts. During Code Generation, scenarios drive the implementation and become the automated acceptance test suite. Three Amigos conversations between Product Management, Engineering, and Design surface misalignment early.

## Engineering Knowledge
💡 **Engineering Knowledge — Behavior-Driven Development**: Acceptance criteria written as Given/When/Then scenarios are unambiguous and executable. Consider expressing user story acceptance criteria in BDD format — it surfaces edge cases before Engineering starts and becomes your automated acceptance test suite. → `engineering-knowledge-repository/methodologies/behavior-driven-development.md`

## Related Entries
- [Test-Driven Development](test-driven-development.md) — BDD builds on TDD principles
- [Contract Testing](../testing/contract-testing.md) — BDD at the service contract level
