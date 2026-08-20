---
id: code-formatting-and-linting
tags: [methodology, developer-experience, backend, frontend]
surfaces-at: [application-design]
related: [ci-cd, code-review-practices, local-development-environment, trunk-based-development]
complexity: foundational
---

# Code Formatting and Linting

## What It Is
Automated tools that enforce consistent code style (formatting) and catch common programming errors, anti-patterns, and style violations (linting) — without requiring human reviewers to care about them. Formatters rewrite code to match a canonical style; linters flag problems without necessarily fixing them. Running both automatically (in pre-commit hooks and CI) eliminates style debates from code review, reduces cognitive load, and catches a class of bugs before they reach review.

## When to Apply
- Every codebase with more than one contributor
- Any project where code review time is spent on style comments
- CI pipelines for all production services

## Key Concepts
- **Formatters (opinionated, auto-fix)**:
  - *JavaScript/TypeScript*: Prettier — the de facto standard. Zero-config, opinionated. Run with `prettier --write`
  - *Python*: Black (formatting) + isort (import ordering). Ruff can replace both with higher performance
  - *Go*: `gofmt` / `goimports` — built into the language; non-negotiable in Go projects
  - *Rust*: `rustfmt` — built into the toolchain
  - *Java/Kotlin*: Google Java Format, ktfmt
- **Linters (analysis, flag issues)**:
  - *JavaScript/TypeScript*: ESLint — configurable rules for code quality, security patterns, framework-specific practices
  - *Python*: Ruff (replaces Flake8, pylint, isort in one fast tool), mypy for type checking
  - *Go*: `golangci-lint` — aggregates dozens of linters with a single config file
  - *CSS/SCSS*: Stylelint
- **Configuration as Code**: Store formatter and linter configs in the project root (`.prettierrc`, `pyproject.toml`, `.eslintrc`, `.golangci.yml`). All developers and CI use the same rules — no "works on my machine" style divergence
- **Pre-commit Hooks**: Run formatters and linters automatically before every commit using `pre-commit` (Python framework supporting all languages), Husky (Node.js), or lefthook. Catch issues before they enter the commit history
  - `pre-commit install` sets up hooks from `.pre-commit-config.yaml`
  - Run fast checks (format, lint) pre-commit; run slow checks (tests) in CI only
- **CI Enforcement**: Formatters and linters must also run in CI as a gate — pre-commit hooks can be bypassed (`git commit --no-verify`). A CI lint check is the source of truth
- **Editor Integration**: VS Code, JetBrains, and Neovim support running formatters on save via extensions (Prettier, Black formatter, rust-analyzer). Eliminates the "I forgot to format before committing" class of CI failures
- **Type Checking**: Typed languages (TypeScript, Python with mypy, Go) benefit from static type checking as an additional linting step. `tsc --noEmit` in CI, `mypy` in CI. Catches a different class of bugs than style linting
- **Lint Rules to Avoid**: Overly strict or stylistic rules that generate too many false positives train teams to ignore lint output. Start with a sensible base config; add rules deliberately. A lint step with 200 warnings is equivalent to no lint step

## In Practice
Method projects use Prettier + ESLint for TypeScript/JavaScript, Ruff for Python, and golangci-lint for Go. All formatters run on save in VS Code via workspace settings. Pre-commit hooks (using the `pre-commit` framework) enforce formatting and linting before every commit. CI runs `lint` and `type-check` as mandatory gates before tests. Lint configuration files are committed to the repo root and pinned to specific tool versions.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Code Formatting and Linting**: Eliminate style comments from code review — they waste reviewer time and cause friction. Use an opinionated formatter (Prettier, Black, gofmt) with zero discussion about its choices. Run it automatically pre-commit and enforce it in CI. For Python, replace Flake8 + pylint + isort with Ruff — it's faster and covers all three. ESLint and TypeScript's `--strict` mode together catch a meaningful class of runtime bugs before they ship. Don't accumulate hundreds of lint warnings — fix them or turn off the rule. → `engineering-knowledge-repository/code-formatting-and-linting.md`

## Related Entries
- [CI/CD](ci-cd.md) — formatting and linting run as CI gates before tests
- [Code Review Practices](code-review-practices.md) — automation handles style; code review focuses on logic, design, and correctness
- [Local Development Environment](local-development-environment.md) — editor integration and pre-commit hooks enforce formatting locally
- [Trunk-Based Development](trunk-based-development.md) — fast formatting/linting gates complement short-lived branches and frequent commits
