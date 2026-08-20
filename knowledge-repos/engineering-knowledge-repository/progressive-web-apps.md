---
id: progressive-web-apps
tags: [pattern, frontend]
surfaces-at: [application-design]
related: [web-performance, server-side-rendering, caching-strategies, accessibility]
complexity: intermediate
---

# Progressive Web Apps

## What It Is
Web applications that use modern browser APIs to deliver app-like experiences — installability, offline capability, push notifications, and fast loading — without requiring a native app install. A Progressive Web App (PWA) is just a web application that meets a set of capability criteria: served over HTTPS, registers a service worker, and includes a web app manifest. Users can "install" PWAs from the browser to their home screen, and they launch in a standalone window without browser chrome. For content-heavy, commerce, or productivity applications, PWAs offer a compelling alternative to maintaining separate native mobile apps.

## When to Apply
- Applications where users would benefit from offline or low-connectivity support
- Consumer-facing products where install friction (vs. native app) matters
- Applications where push notifications drive re-engagement
- When maintaining separate iOS and Android native apps is not cost-effective

## Key Concepts
- **Service Worker**: A JavaScript file that runs in the background in a separate thread, acting as a programmable network proxy. Intercepts fetch requests, serves from cache when offline, handles push notifications, and enables background sync. Must be served from the same origin; requires HTTPS
- **Caching Strategies** (Workbox):
  - *Cache First*: Serve from cache immediately; update cache in background. Best for: static assets (JS, CSS, images) that change only on deploy
  - *Network First*: Try network; fall back to cache on failure. Best for: frequently updated API responses
  - *Stale While Revalidate*: Serve stale cached response immediately; fetch fresh in background. Best for: non-critical, frequently-accessed content
  - *Cache Only*: Serve only from cache. Best for: assets pre-cached during install
- **Workbox**: Google's library for service worker implementation. Provides recipe-based caching strategies, pre-caching support, and background sync. Use Workbox rather than hand-rolling service worker logic — the edge cases are numerous
- **Web App Manifest** (`manifest.json`): Defines PWA metadata — app name, icons, display mode (`standalone`, `fullscreen`), start URL, theme color. Required for installability and home screen appearance
- **Install Prompt**: Browser shows an installation prompt when PWA criteria are met. Capture the `beforeinstallprompt` event to show a custom in-app prompt at an appropriate moment (not immediately on page load)
- **Offline Experience**: Design explicitly for offline state — show cached content, queue actions for sync when back online (Background Sync API), and clearly indicate when the app is offline. An app that silently fails offline is worse than one that explains offline state
- **Push Notifications**: Requires user permission. Use the Push API + Notifications API. Server sends push via Web Push Protocol. Implement with care — unsolicited or frequent notifications lead to permission revocation
- **Lighthouse PWA Audit**: Lighthouse evaluates PWA criteria — HTTPS, service worker, manifest, offline functionality. Use as a checklist for PWA readiness
- **Framework Support**: Vite PWA Plugin, Next-PWA (for Next.js), and Create React App's built-in service worker support simplify PWA setup. Most meta-frameworks have PWA plugin support

## In Practice
Method uses PWA capabilities selectively — service workers for static asset caching on high-traffic marketing sites (improving repeat visit load times), and full offline support on field-use applications where connectivity is unreliable. Workbox handles all service worker caching logic. Push notifications are implemented only for high-value re-engagement use cases with explicit user opt-in flows.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Progressive Web Apps**: Service workers are powerful but tricky — a buggy service worker can serve stale content indefinitely or break the entire app for users until they clear the cache. Use Workbox rather than hand-rolling service worker logic. Design offline state explicitly — decide which content works offline, which fails gracefully, and which queues for sync. For most web applications, the biggest PWA win is service worker caching of static assets (JS, CSS) — repeat visits load instantly. Full offline support is a significant feature investment; scope it based on actual user offline behavior. → `engineering-knowledge-repository/progressive-web-apps.md`

## Related Entries
- [Web Performance](web-performance.md) — service worker caching is a performance optimization strategy for repeat visitors
- [Server-Side Rendering](server-side-rendering.md) — SSG output pairs well with PWA service worker caching
- [Caching Strategies](caching-strategies.md) — PWA caching strategies (cache-first, network-first) apply HTTP caching principles at the service worker layer
- [Accessibility](accessibility.md) — PWA experiences must maintain accessibility standards in standalone display mode
