---
id: hook-pattern
tags: [pattern, backend]
surfaces-at: [application-design, code-generation]
related: [template-method, observer, strategy, decorator]
complexity: intermediate
---

# Hook Pattern

## What It Is
A design mechanism that allows external code to intercept and extend a system's behavior at defined extension points — without modifying the base system. Hooks are predefined slots where custom logic can be injected before, after, or around a core operation. The hook pattern appears across many contexts: lifecycle hooks in frameworks (React's `useEffect`, Vue's `onMounted`), Git hooks (pre-commit, post-push), plugin hooks (WordPress actions/filters), and web framework middleware.

## When to Apply
- Building extensible frameworks or libraries where consumers need to inject behavior without forking
- Lifecycle management where setup/teardown logic should be co-located with the feature that needs it (React hooks model)
- Plugin systems that allow third-party extension without modifying core code
- Cross-cutting concerns (logging, validation, auth) that should be injectable at defined points

## When Not to Apply
- When simple inheritance or composition is sufficient — hooks add indirection
- When the extension points are not yet clear — premature hook design produces the wrong abstractions
- Simple scripts or applications with no extensibility requirements

## Key Concepts
- **Lifecycle Hooks**: Callbacks invoked at defined stages of an object or process lifecycle — `beforeSave()`, `afterCreate()`, `onDestroy()`. Common in ORMs (ActiveRecord), test frameworks (`beforeEach`), and UI frameworks
- **React Hooks**: Functions prefixed with `use` that let function components opt into React state and lifecycle features — `useState`, `useEffect`, `useContext`. A compositional alternative to class lifecycle methods
- **Git Hooks**: Shell scripts in `.git/hooks/` triggered at specific Git events — `pre-commit`, `commit-msg`, `pre-push`. Used for linting, testing, and secret scanning before code leaves the local machine
- **Framework Hooks / Filters**: WordPress-style action/filter system — code registers a function to run at a named hook point; the framework calls all registered functions. Classic open/closed principle implementation
- **Middleware as Hooks**: Express/Koa/Next.js middleware are hooks on the request/response lifecycle — each middleware can short-circuit or pass through
- **Difference from Template Method**: Template Method defines the skeleton in a base class and subclasses fill in steps. Hooks are typically registered externally at runtime rather than defined at compile time via inheritance

## In Practice
React hooks are the primary manifestation of this pattern in Method frontend work — custom hooks encapsulate stateful logic for reuse across components. Git hooks (via Husky) enforce pre-commit linting and secret scanning. Backend framework middleware (Express, Spring interceptors) provides server-side hooks for auth, logging, and request transformation.

## Engineering Knowledge
💡 **Engineering Knowledge — Hook Pattern**: Hooks let external code inject behavior at predefined extension points without modifying the core system. React hooks compose stateful logic into reusable units — custom hooks encapsulate fetch logic, form state, auth state. Git hooks (via Husky) run quality checks before commits leave the machine. Framework middleware hooks handle cross-cutting concerns (auth, logging, rate limiting) at the request lifecycle level. Unlike Template Method, hooks are registered at runtime — more flexible, more dynamic. → `engineering-knowledge-repository/design-patterns/hook-pattern.md`

## Related Entries
- [Template Method](template-method.md) — Template Method is the compile-time, inheritance-based precursor to runtime hooks
- [Observer](observer.md) — the Observer pattern is conceptually similar; hooks are typically single-point, observers are broadcast
- [Strategy](strategy.md) — Strategy swaps algorithms; hooks extend at fixed points
- [Decorator](decorator.md) — Decorator wraps behavior; hooks inject at named lifecycle points
