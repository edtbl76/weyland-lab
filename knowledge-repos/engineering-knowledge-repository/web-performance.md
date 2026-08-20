---
id: web-performance
tags: [pattern, frontend, performance]
surfaces-at: [application-design, nfr-design]
related: [frontend-build-tooling, server-side-rendering, caching-strategies, cdn]
complexity: intermediate
---

# Web Performance

## What It Is
The discipline of measuring and improving the speed, responsiveness, and efficiency of web applications as perceived by users. Web performance directly impacts business outcomes: a 100ms improvement in load time can increase conversion rates by 1%; poor Core Web Vitals scores affect Google search rankings. Performance is not an afterthought — it is a non-functional requirement that must be designed for, measured, and monitored continuously.

## When to Apply
- Any user-facing web application where load time and responsiveness matter
- Applications with measurable Core Web Vitals metrics
- E-commerce or conversion-sensitive applications
- Applications serving mobile users or users on slow networks

## Key Concepts
- **Core Web Vitals (CWV)**: Google's set of standardized performance metrics:
  - *LCP (Largest Contentful Paint)*: Time until the largest visible content element renders. Target: < 2.5s. Affected by: server response time, render-blocking resources, image optimization
  - *INP (Interaction to Next Paint)*: Responsiveness to user input. Target: < 200ms. Replaces FID (First Input Delay) as of 2024. Affected by: long JavaScript tasks, heavy event handlers
  - *CLS (Cumulative Layout Shift)*: Visual stability — how much content shifts during load. Target: < 0.1. Caused by: images without dimensions, injected content, fonts loading late
- **Bundle Optimization**:
  - *Code Splitting*: Split the JavaScript bundle by route or component. Users download only the code for the current page. React: `React.lazy()` + `Suspense`; Next.js automatic code splitting per page
  - *Tree Shaking*: Bundlers remove unused exports. Requires ES module syntax. Avoid importing entire libraries (`import _ from 'lodash'`); import specific functions (`import debounce from 'lodash/debounce'`)
  - *Bundle Analysis*: Use `webpack-bundle-analyzer` or Vite's `rollup-plugin-visualizer` to identify large dependencies. Common offenders: moment.js (replace with date-fns), lodash (use native or cherry-pick)
- **Image Optimization**:
  - Use modern formats: WebP (30% smaller than JPEG), AVIF (50% smaller). Use `<picture>` for browser fallbacks
  - Size images to display size — don't serve a 2000px image in a 200px slot
  - Lazy-load off-screen images with `loading="lazy"` or Intersection Observer
  - Use a CDN with automatic image optimization (Cloudinary, Imgix, Next.js Image component)
- **Critical Rendering Path**:
  - Minimize render-blocking resources. CSS in `<head>`, JS with `defer` or `async` in `<body>`
  - Inline critical CSS (above-the-fold styles) to eliminate render-blocking stylesheet fetches
  - Preload key resources: `<link rel="preload" as="font">` for critical fonts, `<link rel="preconnect">` for third-party origins
- **Caching**:
  - Static assets (JS, CSS, images) should have long cache TTLs (1 year) with content-hash-based filenames. Bundlers add content hashes automatically (`main.abc123.js`)
  - HTML documents should have short or no-cache TTLs to ensure updated assets are picked up
  - CDN caching for static assets eliminates origin server round trips
- **JavaScript Performance**:
  - Long tasks (> 50ms) block the main thread and hurt INP. Break long synchronous operations with `setTimeout(0)` or use Web Workers
  - Debounce and throttle high-frequency event handlers (scroll, resize, input)
  - Virtualize long lists (react-virtual, TanStack Virtual) — rendering 10,000 DOM nodes is slow
- **Fonts**: Use `font-display: swap` or `optional` to prevent invisible text during font load. Subset fonts to include only needed characters. Use system fonts for non-brand text
- **Measurement**: Measure in real conditions, not just local. Tools: Lighthouse (lab), WebPageTest (lab), Google Search Console CWV report (field), RUM (Real User Monitoring) with Datadog, Sentry, or web-vitals library

## In Practice
Method tracks Core Web Vitals via Lighthouse CI in the deployment pipeline — builds fail if LCP or CLS exceed thresholds. Next.js Image component handles image optimization and lazy loading. JavaScript bundles are analyzed with `rollup-plugin-visualizer` before major releases. Real User Monitoring sends CWV data to Datadog. Fonts are subset and served from the CDN with `font-display: swap`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Web Performance**: LCP, INP, and CLS are the three metrics that matter most — measure them in production with Real User Monitoring, not just in Lighthouse. The fastest code is code that doesn't run: code split by route, tree-shake unused imports, and lazy-load images and off-screen components. Images are the single largest opportunity on most sites — convert to WebP/AVIF, resize to display dimensions, and lazy-load below the fold. Long JavaScript tasks are the primary cause of poor INP — profile with Chrome DevTools, then break up or offload to Web Workers. → `engineering-knowledge-repository/web-performance.md`

## Related Entries
- [Frontend Build Tooling](frontend-build-tooling.md) — bundlers perform code splitting, tree shaking, and asset optimization
- [Server-Side Rendering](server-side-rendering.md) — SSR and SSG fundamentally improve LCP by delivering pre-rendered HTML
- [Caching Strategies](caching-strategies.md) — HTTP caching and CDN caching eliminate unnecessary network round trips
- [CDN](cdn.md) — CDNs serve static assets from edge locations, reducing latency globally
