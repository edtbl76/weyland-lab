---
id: state-management
tags: [pattern, frontend, backend]
surfaces-at: [application-design, functional-design]
related: [component-architecture, server-side-rendering, cqrs, event-sourcing]
complexity: intermediate
---

# State Management

## What It Is
The patterns and libraries used to manage, synchronize, and share application state across components and layers. In frontend applications, state falls into distinct categories — server state (remote data fetched from APIs), client state (UI state like modal open/closed, selected items), and form state — each with different lifecycle, caching, and synchronization requirements. Choosing the right state management approach per category eliminates overengineering (global Redux store for everything) and avoids under-engineering (prop-drilling through 10 component levels).

## When to Apply
- Any frontend application with multiple components that need shared state
- Applications with server data that needs caching and synchronization
- Complex UI flows where state persists across navigation or sessions
- Applications with real-time data updates

## Key Concepts
- **State Categories**:
  - *Server state*: Data that lives on the server and is fetched asynchronously. Has caching, staleness, background refetching, and synchronization concerns. Best managed by dedicated server-state libraries
  - *Global client state*: UI state shared across distant components — authenticated user, theme, selected filters. Managed by context, Zustand, or Redux
  - *Local component state*: State scoped to a single component — form input values, loading spinners, toggle state. Managed with `useState` / `ref`
  - *URL state*: State encoded in the URL — search query, pagination, selected tab. Enables shareable URLs and browser back/forward
  - *Form state*: Validation, dirty tracking, submission state. Managed by React Hook Form, Formik
- **Server State Libraries**:
  - *TanStack Query (React Query)*: The standard for server state. Handles caching, background refetching, stale-while-revalidate, pagination, mutations, and optimistic updates. Reduces boilerplate and eliminates manual loading/error state management
  - *SWR*: Vercel's server state library; similar to React Query. Simpler API; less feature-rich
  - *RTK Query*: Redux Toolkit's built-in server state solution. Use when already using Redux for global state
- **Global Client State Libraries**:
  - *Zustand*: Minimal, flexible; small bundle, simple API. Preferred for most projects that need global state beyond what Context handles
  - *Redux Toolkit (RTK)*: Powerful; strong DevTools, time-travel debugging. Best for complex, heavily interdependent state with many actions. Higher boilerplate than Zustand
  - *Jotai / Recoil*: Atomic state models; good for fine-grained reactivity. Less common
  - *React Context*: Built-in; appropriate for infrequently-changing global state (theme, auth user). Causes full re-renders on every update — not suitable for high-frequency state changes
- **Common Anti-Patterns**:
  - *Global state for everything*: Putting local UI state (modal open/closed) in a global store adds complexity with no benefit
  - *Redundant server state in Redux*: Storing API responses in Redux when React Query would handle caching, refetching, and synchronization automatically
  - *Prop drilling*: Passing state through 5+ component levels instead of using context or a state library for shared state
- **State Colocation**: Keep state as close to where it's used as possible. Local component state → context → global store — escalate only when the data is genuinely shared
- **Optimistic Updates**: Update the UI immediately on mutation, then reconcile with the server response. TanStack Query and SWR provide built-in optimistic update patterns

## In Practice
Method React applications use TanStack Query for all server state — caching, loading/error states, and background refetching. Zustand manages global client state (auth user, notifications, theme). React Hook Form handles form state. URL state via `useSearchParams` for filterable/pageable views. Redux is not used for new projects — TanStack Query + Zustand covers the same ground with less complexity.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — State Management**: Most React state management complexity comes from mixing server state and client state in the same store. Use TanStack Query for server state (it handles caching, refetching, and synchronization automatically) and Zustand for global client state. Don't use Redux as your default — TanStack Query + Zustand covers 90% of use cases with less boilerplate. Keep state local (useState) until you have a concrete reason to lift it — premature global state is the frontend equivalent of premature abstraction. → `engineering-knowledge-repository/state-management.md`

## Related Entries
- [Component Architecture](component-architecture.md) — state management decisions shape how components are structured and composed
- [Server-Side Rendering](server-side-rendering.md) — SSR changes server state hydration and initial state delivery patterns
- [CQRS](cqrs.md) — CQRS and state management share the concept of separating read and write models
