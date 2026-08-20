---
id: single-page-application
tags: [pattern, frontend]
surfaces-at: [application-design]
related: [server-side-rendering, state-management, web-performance, frontend-build-tooling, component-architecture]
complexity: foundational
---

# Single-Page Application

## What It Is
A web application architecture where the browser loads a single HTML document once, and subsequent navigation is handled by JavaScript updating the DOM — without full page reloads. The server delivers an initial HTML shell and JavaScript bundle; client-side routing handles navigation between views. SPAs enable highly interactive, app-like experiences with smooth transitions and fast in-app navigation. The tradeoff is initial load performance (large JavaScript bundle before anything renders) and SEO challenges (search engines index the empty shell, not the rendered content). SPAs are the right choice for applications where interactivity and UX richness outweigh initial load and SEO concerns.

## When to Apply
- Authenticated, interactive web applications (dashboards, admin tools, SaaS products)
- Applications with complex UI state that persists across navigation
- Internal tools where SEO is irrelevant
- Applications where native-app-like interactions (animated transitions, drag-and-drop, complex forms) are required

## Key Concepts
- **Client-Side Routing**: A JavaScript router (React Router, TanStack Router, Vue Router) intercepts navigation events and renders the appropriate component tree without a server request. The URL changes; the page does not reload
- **Code Splitting**: The JavaScript bundle is split by route — only the code for the current route is loaded initially. Subsequent routes are loaded on demand as the user navigates. Eliminates the need to download the entire application on first load. React: `React.lazy` + dynamic imports. Automatic in Next.js and Vite-based setups
- **Initial Bundle Size**: The largest SPA performance problem. Every library added to the bundle is downloaded by every user before the app renders. Audit regularly with bundle analysis tools. Target: < 200KB initial JS (compressed)
- **Hydration (for SSR-enhanced SPAs)**: When an SPA uses SSR for the initial render (Next.js, Remix), the server sends pre-rendered HTML and the client "hydrates" it — attaches React event handlers without re-rendering. This combines the LCP benefits of SSR with SPA interactivity after hydration
- **History API vs. Hash Routing**: Modern SPAs use the History API (`/dashboard`, `/settings`) for clean URLs. Requires server configuration to serve `index.html` for all routes (otherwise direct navigation to `/dashboard` returns 404). Hash routing (`/#/dashboard`) works without server configuration but is ugly and uncommon
- **SPA vs. MPA (Multi-Page Application)**:
  - *SPA*: One HTML document; client-side routing; JavaScript-heavy; best for interactive apps
  - *MPA*: Server renders each page; full page loads on navigation; better SEO and initial load; simpler mental model
  - Modern answer: meta-frameworks (Next.js, Nuxt, SvelteKit) implement hybrid — SSR/SSG for initial load (MPA behavior) with client-side navigation after hydration (SPA behavior)
- **Common SPA Pitfalls**:
  - *Memory leaks*: Subscriptions, event listeners, and timers not cleaned up on component unmount
  - *Over-fetching*: Fetching all data on app load rather than on route load (code split your data fetching too)
  - *Deep linking*: Ensure server serves `index.html` for all SPA routes to support direct URL access
  - *Browser back/forward*: History management is complex; use a mature router library rather than rolling your own

## In Practice
Method builds SPAs for authenticated product applications (dashboards, admin tools, SaaS backends). React + React Router (or TanStack Router) + TanStack Query is the standard stack. Code splitting by route is automatic via Vite's dynamic import support. Initial bundle targets are enforced via Lighthouse CI. For public-facing applications (marketing, landing pages), Next.js hybrid rendering is used instead of a pure SPA.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Single-Page Application**: SPAs are not the right default for all web applications — choose SPA for authenticated, interactive applications and SSR/SSG for public-facing, content-heavy, or SEO-dependent pages. The biggest SPA trap is bundle size: split by route and audit dependencies regularly. Configure your web server to serve `index.html` for all routes — forgetting this breaks direct navigation and refreshes. For new projects, consider a meta-framework (Next.js, Remix) that gives SPA interactivity with SSR performance, rather than a pure CSR SPA. → `engineering-knowledge-repository/single-page-application.md`

## Related Entries
- [Server-Side Rendering](server-side-rendering.md) — SSR and hybrid rendering complement or replace pure SPA architecture for better initial load performance
- [State Management](state-management.md) — SPAs require explicit state management across route transitions
- [Web Performance](web-performance.md) — initial bundle size is the primary SPA performance concern
- [Frontend Build Tooling](frontend-build-tooling.md) — bundlers implement code splitting for SPA route-based chunking
- [Component Architecture](component-architecture.md) — route-level and feature-level component organization structures the SPA
