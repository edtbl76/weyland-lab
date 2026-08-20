---
id: documentation-as-code
tags: [methodology, team-practices, developer-experience]
surfaces-at: [requirements-analysis, code-generation]
related: [developer-experience, architecture-decision-records, definition-of-done]
complexity: foundational
---

# Documentation as Code

## What It Is
The practice of writing and maintaining documentation using the same tools and workflows as code — plain text files (Markdown, AsciiDoc) stored in version control, reviewed in pull requests, tested in CI, and deployed automatically. Documentation lives alongside the code it describes, versioned together, reviewed by the same team. The alternative — wikis, Confluence pages, Word documents — drift from reality as code evolves; docs-as-code stays current because it lives in the same repository and review process.

## When to Apply
- All technical documentation for software systems — API docs, architecture guides, runbooks, ADRs
- Any team that already uses Git and pull requests — zero additional tooling barrier
- Systems where documentation accuracy is critical (APIs, operational runbooks, security procedures)

## When Not to Apply
- High-fidelity design documents, diagrams requiring rich formatting, or stakeholder presentations — better suited to design tools or presentation software
- Non-technical audiences who are not comfortable with Git-based workflows

## Key Concepts
- **Markdown**: The de facto standard for docs-as-code — readable as plain text, renders in GitHub/GitLab, supported by all static site generators
- **Docs in Repo**: Documentation lives in the same repository as the code — `docs/` directory, ADR directory, OpenAPI spec, README files. Reviewed in PRs, versioned with releases
- **Static Site Generators**: Convert Markdown docs to deployed documentation sites — MkDocs (Material theme), Docusaurus, Hugo. Deployed via CI to GitHub Pages or similar
- **Linting**: Docs can be linted like code — `markdownlint`, `vale` (prose style linter) catch formatting errors and style inconsistencies in CI
- **Diagrams as Code**: Mermaid, PlantUML, and C4 diagrams embedded in Markdown — version-controlled, reviewable in PRs, no binary image files
- **Definition of Done Integration**: DoD includes documentation updates — code PRs that change behavior must include corresponding documentation updates
- **API Documentation**: OpenAPI spec is the canonical API doc — generated from spec-first workflow, deployed as Swagger UI or Redoc automatically in CI

## In Practice
Method stores all project documentation in the `docs/` directory of the service repository — architecture diagrams, ADRs, runbooks, API docs. MkDocs with Material theme generates the documentation site deployed to GitHub Pages. Mermaid diagrams are embedded in Markdown. `vale` linting runs in CI. Documentation updates are part of the Definition of Done — PRs without relevant doc updates are not approved.

## Engineering Knowledge
💡 **Engineering Knowledge — Documentation as Code**: Documentation that lives outside the codebase drifts. Put it in Git, review it in PRs, deploy it in CI. Markdown in `docs/` is the baseline — add MkDocs or Docusaurus for a deployed site. Use Mermaid for diagrams-as-code rather than binary image files. Add `vale` or `markdownlint` to CI. Make doc updates part of the Definition of Done — if the behavior changed, the docs must change in the same PR. → `engineering-knowledge-repository/team-practices/documentation-as-code.md`

## Related Entries
- [Developer Experience](developer-experience.md) — good documentation is a core developer experience investment
- [Architecture Decision Records](architecture-decision-records.md) — ADRs are the premier example of documentation as code
- [Definition of Done](definition-of-done.md) — DoD enforces documentation updates as part of every feature
