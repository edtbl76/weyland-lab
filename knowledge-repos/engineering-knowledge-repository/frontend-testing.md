---
id: frontend-testing
tags: [pattern, frontend, testing]
surfaces-at: [application-design, functional-design]
related: [component-architecture, state-management, testing-strategies, accessibility, ci-cd]
complexity: intermediate
---

# Frontend Testing

## What It Is
The set of testing practices for web applications — unit tests for individual functions and components, integration tests for component interactions and user flows, and end-to-end tests for complete user journeys through the browser. Frontend testing has historically been under-invested relative to backend testing, but modern tooling (Vitest, Testing Library, Playwright) has made frontend testing fast, reliable, and maintainable. The testing trophy model (few E2E → many integration → some unit) reflects what provides the highest confidence per test.

## When to Apply
- Every frontend feature (tests are part of the definition of done)
- Components in a shared design system or component library
- Complex user flows with business-critical outcomes (checkout, auth, forms)
- Any frontend code that will be maintained long-term

## Key Concepts
- **Testing Trophy** (Kent C. Dodds): Favor integration tests over unit tests for frontend:
  - *E2E (top)*: Few; test critical user journeys through the real browser and real backend. Expensive; slow; high confidence. Playwright, Cypress
  - *Integration (middle, most)*: Test component interactions as a user would — render a component, simulate user events, assert on the resulting DOM. Testing Library + Vitest/Jest
  - *Unit (bottom)*: Pure functions, hooks, utilities. Fast; cheap; narrow scope
  - *Static (foundation)*: TypeScript + ESLint catch errors at compile time; no runtime cost
- **Testing Library Philosophy**: "Test behavior, not implementation." Query by accessible role or label text, not by CSS class or DOM structure. Tests that break when you rename a CSS class are not testing behavior — they're testing implementation details
  - ✅ `getByRole('button', { name: 'Submit' })` — tests what users see
  - ❌ `querySelector('.btn-primary')` — tests implementation details
- **Vitest**: The standard test runner for Vite-based projects. Fast (native ESM, no transpilation), Jest-compatible API, runs in Node or browser-like environment via jsdom/happy-dom. Replaces Jest for most new projects
- **React Testing Library**: Renders React components into jsdom, provides queries, and fires user events via `@testing-library/user-event`. Works with Vitest or Jest
- **Playwright**: Microsoft's E2E testing framework. Supports Chromium, Firefox, and WebKit. Faster and more reliable than Selenium; better developer experience than Cypress. The standard for new E2E test suites
- **Storybook**: Component development and documentation tool that serves as a visual test harness. Stories define component states; Chromatic adds screenshot diffing for visual regression testing
- **Component Test Strategy**:
  - Test user interactions: click, type, submit form
  - Test state transitions: loading → loaded → error
  - Test accessibility: labels, roles, keyboard navigation
  - Do NOT test: internal state, exact DOM structure, implementation details
- **Mocking**:
  - Mock HTTP requests with MSW (Mock Service Worker) — intercepts requests at the network level, not at the module level. Tests remain unaware of the HTTP client being used
  - Mock time-based behavior with `vi.useFakeTimers()`
  - Avoid mocking React Query or component internals — test through the user interface
- **Testing Async UI**: Use `waitFor` and `findBy*` queries for async state. Don't use arbitrary `setTimeout` — Testing Library's async utilities handle retry logic correctly

## In Practice
Method frontend projects use Vitest + React Testing Library for unit and integration tests. Integration tests cover the major user flows for each feature. Playwright covers 3-5 critical E2E journeys (login, checkout, key feature paths). MSW mocks API responses in integration tests. Storybook documents components; Chromatic runs visual regression testing on PR branches. Tests run in CI as a required gate before merge.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Frontend Testing**: Write more integration tests than unit tests — a test that renders a component, clicks a button, and asserts the result survived a refactor; a test that asserts internal state values did not. Use Testing Library's `getByRole` and `getByLabelText` — they test behavior and double as accessibility checks. Use MSW for API mocking — it mocks at the network layer, not the module layer, making tests realistic regardless of the HTTP client. Playwright for E2E is the modern choice over Cypress — faster, cross-browser, better async handling. → `engineering-knowledge-repository/frontend-testing.md`

## Related Entries
- [Component Architecture](component-architecture.md) — well-structured components with clear props are far easier to test
- [State Management](state-management.md) — test state transitions through the UI, not by directly inspecting state stores
- [Testing Strategies](testing-strategies.md) — frontend testing fits within the broader testing strategy (testing trophy vs. testing pyramid)
- [Accessibility](accessibility.md) — Testing Library's semantic queries double as accessibility compliance checks
- [CI/CD](ci-cd.md) — frontend tests run as CI gates before merge and deployment
