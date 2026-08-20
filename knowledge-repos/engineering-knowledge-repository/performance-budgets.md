---
id: performance-budgets
tags: [methodology, performance, frontend]
surfaces-at: [application-design, nfr-requirements]
related: [web-performance, real-user-monitoring, ci-cd, frontend-build-tooling, service-level-objectives]
complexity: intermediate
---

# Performance Budgets

## What It Is
Explicit, measurable constraints on performance metrics that a product must not exceed — enforced in the development workflow, not just aspirationally documented. A performance budget defines thresholds like "initial JavaScript bundle < 200KB compressed," "LCP < 2.5s at p75," or "Time to Interactive < 5s on 3G." When a change would exceed the budget, it is blocked (CI fails, or a reviewer must explicitly approve the regression). Performance budgets make performance a first-class product requirement, not an afterthought addressed before launch.

## When to Apply
- Applications where web performance directly impacts business metrics (conversion, engagement, SEO)
- Teams that have experienced performance regression drift over time
- Greenfield projects where maintaining performance from the start is easier than recovering it later
- Applications with contractual or SLA-based performance requirements

## Key Concepts
- **Budget Types**:
  - *Quantity-based*: File size limits — total JS bundle size, image size, number of HTTP requests. Directly measurable in CI before deployment
  - *Timing-based*: User-facing metrics — LCP, INP, TTI, FCP. Measurable via Lighthouse CI or RUM
  - *Rule-based*: Lighthouse score thresholds — Performance score ≥ 90, Accessibility score ≥ 95
- **Enforcement in CI**: Performance budgets are only effective when enforced automatically:
  - *Lighthouse CI*: Runs Lighthouse in CI; fails the build if budgets are exceeded. Configurable thresholds in `lighthouserc.json`. Integrates with GitHub status checks
  - *Bundlesize / Size-Limit*: `size-limit` (Vite/webpack plugin) fails CI if any bundle exceeds configured size thresholds. Runs in seconds; fast feedback loop
  - *Web Vitals Monitoring*: Alert in Datadog or Sentry when RUM-measured p75 CWV exceeds budget thresholds post-deployment
- **Setting Initial Budgets**: Base budgets on current state with a 20% headroom, or on competitor benchmarks, or on Google's CWV "good" thresholds. Starting with a budget you already fail is counterproductive — establish a realistic baseline, then tighten over time
- **Budget Regression Approval**: When a PR would exceed a budget, require explicit approval from a performance-aware reviewer. This surfaces the tradeoff explicitly rather than allowing silent degradation. "This PR adds 50KB to the bundle — is that acceptable for this feature?"
- **Bundle Size Budget Examples**:
  - Initial JavaScript (parsed): < 200KB compressed
  - Per-route chunk: < 50KB compressed
  - Total third-party scripts: < 100KB
  - Largest single image: < 200KB
- **LCP Budget Examples** (from Google's "Good" thresholds):
  - LCP: < 2.5s (Good), < 4.0s (Needs Improvement), > 4.0s (Poor)
  - INP: < 200ms (Good)
  - CLS: < 0.1 (Good)
- **Performance Budget Document**: A `performance-budget.json` or equivalent committed to the repository, reviewed in architecture discussions, and referenced by CI configuration. Makes the budget a first-class artifact, not an informal expectation

## In Practice
Method frontend projects use `size-limit` to enforce JavaScript bundle budgets in CI — builds fail if the main bundle exceeds 200KB compressed. Lighthouse CI runs on every PR and blocks merge if Performance score drops below 85. RUM-measured LCP thresholds trigger alerts in Datadog when p75 exceeds 2.5s post-deployment. Bundle size history is tracked on a dashboard to visualize trends over time.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Performance Budgets**: A performance budget that isn't enforced in CI is just a wish. Use `size-limit` for bundle size budgets (runs in seconds, blocks PRs) and Lighthouse CI for timing budgets. Start with budgets you can currently meet, then tighten iteratively — a budget that fails from day one gets ignored. The most impactful budget for most web applications is the JavaScript bundle size budget: every KB of JS is downloaded, parsed, and compiled on every page load. Frame budget violations as tradeoffs, not failures — "this feature costs 30KB; is it worth it?" → `engineering-knowledge-repository/performance-budgets.md`

## Related Entries
- [Web Performance](web-performance.md) — performance budgets enforce the web performance metrics that matter for users
- [Real User Monitoring](real-user-monitoring.md) — RUM provides production data to validate that budgets are being met in real conditions
- [CI/CD](ci-cd.md) — performance budgets are enforced as CI gates
- [Frontend Build Tooling](frontend-build-tooling.md) — build tooling provides the bundle analysis data that budget enforcement tools consume
- [Service Level Objectives](service-level-objectives.md) — performance budgets are the frontend-specific form of SLOs
