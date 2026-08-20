---
id: server-side-rendering
tags: [pattern, frontend, backend, performance]
surfaces-at: [application-design, functional-design]
related: [state-management, web-performance, cdn, caching-strategies, backend-for-frontend]
complexity: intermediate
---

# Server-Side Rendering

## What It Is
A spectrum of rendering strategies that move HTML generation from the browser to the server, improving initial load performance, SEO, and user-perceived speed. The key strategies — SSR (Server-Side Rendering), SSG (Static Site Generation), and ISR (Incremental Static Regeneration) — determine when and how HTML is produced. Modern meta-frameworks like Next.js, Nuxt, SvelteKit, and Remix implement all three. The choice of rendering strategy is one of the most impactful architectural decisions in a frontend application.

## When to Apply
- Applications where SEO matters (search engines index server-rendered HTML better than client-rendered SPA content)
- Applications with slow perceived initial load (LCP improvement)
- Marketing sites, content-heavy pages, or e-commerce product pages (SSG or ISR)
- Applications where authenticated, personalized content is needed on the first load (SSR)

## Key Concepts
- **Client-Side Rendering (CSR)**: The browser downloads a near-empty HTML shell, downloads JavaScript, executes it, and then renders the page. Slowest initial load (LCP), worst SEO. All state management and data fetching happens client-side. Appropriate for: highly interactive dashboards, authenticated internal tools where SEO doesn't matter
- **Server-Side Rendering (SSR)**: On every request, the server fetches data, renders HTML, and sends it to the browser. Browser hydrates the HTML with React/Vue event listeners. Fastest first meaningful paint for personalized content. Best for: authenticated pages with per-user data, real-time data
  - Downsides: Server must run on every request; higher infrastructure cost; TTFB dependent on data fetch speed
- **Static Site Generation (SSG)**: HTML is rendered at build time and served as static files from a CDN. Fastest possible TTFB and LCP — just a CDN file serve. Best for: marketing pages, documentation, blogs, content that changes infrequently
  - Downsides: Rebuilds required for content changes; build time grows with page count
- **Incremental Static Regeneration (ISR)**: SSG with on-demand or time-based revalidation. Static pages are served from CDN; the server revalidates pages in the background when they become stale (`revalidate: 60`). Best of both worlds for semi-dynamic content
  - Next.js ISR: `export const revalidate = 60` (App Router) or `getStaticProps` with `revalidate`
- **React Server Components (RSC)**: Components that execute entirely on the server, with zero JavaScript shipped to the client. Composable with Client Components. Next.js App Router uses RSC by default. Fundamentally changes the mental model — server data fetching and rendering are co-located in the component
- **Hydration**: The process of attaching React event handlers to server-rendered HTML. Hydration errors (content mismatch between server and client render) are a common pitfall — avoid using browser-only APIs or random values during initial render
- **Streaming**: Next.js and Remix support streaming HTML responses — the server sends HTML chunks as they're ready, rather than waiting for all data. Improves TTFB while maintaining SSR benefits. React Suspense boundaries define streaming chunks
- **Rendering Strategy by Page Type**:
  - Home page, marketing pages: SSG or ISR
  - Blog posts, product pages: ISR (updated on publish)
  - User dashboard, personalized pages: SSR or CSR
  - Admin tools: CSR acceptable
  - Real-time features: CSR with client-side subscriptions

## In Practice
Method uses Next.js App Router for most web applications. Marketing and content pages use RSC with ISR revalidation. Authenticated dashboard pages use RSC for initial data load with client components for interactivity. Static content is served via CloudFront CDN. React Server Components reduced client-side JavaScript bundles by 40% on recent engagements.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Server-Side Rendering**: Don't default to a full SPA when SSR or SSG would be better — CSR is the worst option for LCP and SEO. Choose rendering strategy per page, not per application: most pages can be SSG or ISR; only personalized pages need SSR. With Next.js App Router, React Server Components are the default — embrace them for data fetching and keep Client Components for interactivity only. Hydration errors are caused by rendering differences between server and client — never use `Math.random()`, `Date.now()`, or browser APIs in initial render without guarding with `useEffect`. → `engineering-knowledge-repository/server-side-rendering.md`

## Related Entries
- [State Management](state-management.md) — SSR changes server state hydration patterns; React Server Components change data fetching location
- [Web Performance](web-performance.md) — SSR and SSG directly improve LCP and Core Web Vitals
- [CDN](cdn.md) — SSG/ISR pages are served from CDN edge nodes for maximum TTFB performance
- [Caching Strategies](caching-strategies.md) — SSR responses can be cached at the CDN layer with appropriate cache-control headers
- [Backend for Frontend](backend-for-frontend.md) — BFF patterns complement SSR for data aggregation and API orchestration
